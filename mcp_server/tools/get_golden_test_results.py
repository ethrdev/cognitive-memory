"""
Golden Test Results Tool -

Daily execution of Golden Test Set for model drift detection.
Calculates Precision@5 metric, detects drift, and stores results in model_drift_log.

Hybrid Pattern:
- Core function: execute_golden_test() - callable directly from cron/Python
- MCP Wrapper: handle_get_golden_test_results() - callable via MCP protocol

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from openai import OpenAI
from pgvector.psycopg2 import register_vector

from mcp_server.db.connection import (
    get_connection_sync,
    get_connection_with_project_context_sync,
)
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata

# Import calculate_precision_at_5 from
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from validate_precision_at_5 import calculate_precision_at_5

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Loading
# =============================================================================


def load_config() -> dict[str, Any]:
    """
    Load calibrated hybrid search weights from config.yaml.

    Returns:
        Dict with hybrid_search_weights config

    Raises:
        RuntimeError: If config.yaml not found or invalid
    """
    config_path = Path(__file__).parent.parent.parent / "config.yaml"

    if not config_path.exists():
        raise RuntimeError(f"config.yaml not found at {config_path}")

    with open(config_path) as f:
        config = yaml.safe_load(f)

    if "hybrid_search_weights" not in config:
        raise RuntimeError("hybrid_search_weights not found in config.yaml")

    return config


# =============================================================================
# Core Golden Test Execution (Direct Python Callable)
# =============================================================================


def execute_golden_test(project_id: str | None = None) -> dict[str, Any]:
    """
    Execute Golden Test Set and calculate Precision@5 with drift detection.

    This is the CORE function - callable directly from cron jobs or Python scripts.
    Does NOT require MCP protocol overhead.

    Story 11.7.3: Uses project-scoped connection for RLS filtering.
    Each project calculates P@5 against its own golden test set.

    Backward Compatibility:
        The project_id parameter defaults to None, making this change backward compatible.
        Existing cron jobs and scripts will continue to work, automatically using the current
        project context from get_current_project().

    Args:
        project_id: Optional project ID (defaults to current project from context)

    Returns:
        Dict with:
        - date: str (YYYY-MM-DD)
        - precision_at_5: float (0.0-1.0)
        - num_queries: int
        - drift_detected: bool
        - baseline_p5: float | None (7-day rolling average)
        - current_p5: float (alias for precision_at_5)
        - drop_percentage: float (0.0-1.0, relative drop from baseline)
        - avg_retrieval_time: float (milliseconds)
        - embedding_model_version: str | None
        - project_id: str (project that executed this test)

    Raises:
        RuntimeError: If golden_test_set table is empty or API failures
    """
    # Story 11.7.3: Get project context if not provided
    if project_id is None:
        project_id = get_current_project()

    start_time = time.time()
    logger.info(f"Starting Golden Test Set execution for project {project_id}...")

    # Load configuration
    config = load_config()
    weights = {
        "semantic": config["hybrid_search_weights"]["semantic"],
        "keyword": config["hybrid_search_weights"]["keyword"],
    }
    logger.info(
        f"Loaded calibrated weights: semantic={weights['semantic']}, keyword={weights['keyword']}"
    )

    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        raise RuntimeError(
            "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
        )

    openai_client = OpenAI(api_key=api_key)
    embedding_model_version = None  # Will extract from API response headers

    # Story 11.7.3: Use project-scoped connection for RLS filtering
    # RLS automatically filters golden_test_set by project_id
    with get_connection_with_project_context_sync(read_only=True) as conn:
        cursor = conn.cursor()

        # Check if golden_test_set has queries for this project
        cursor.execute("SELECT COUNT(*) FROM golden_test_set")
        count_result = cursor.fetchone()
        query_count = int(count_result[0])

        if query_count == 0:
            raise RuntimeError(
                f"golden_test_set table is empty for project {project_id}! "
                "Cannot execute Golden Test. Run Streamlit UI to label queries first."
            )

        logger.info(f"Found {query_count} queries in golden_test_set for project {project_id}")

        # Load all queries with expected_docs (RLS filters by project_id)
        cursor.execute(
            """
            SELECT id, query, expected_docs
            FROM golden_test_set
            ORDER BY id
            """
        )
        queries = cursor.fetchall()

    # Execute Golden Test: For each query, calculate Precision@5
    precision_scores = []
    retrieval_times = []

    for idx, query_row in enumerate(queries, 1):
        query_id = query_row[0]
        query_text = query_row[1]
        expected_docs = query_row[2]  # List of L2 Insight IDs

        logger.info(f"Processing query {idx}/{query_count}: {query_text[:50]}...")

        # Step 1: Create embedding via OpenAI API
        try:
            embedding_response = openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=query_text,
                encoding_format="float",
            )
            query_embedding = embedding_response.data[0].embedding

            # Extract embedding model version from response (if available)
            if hasattr(embedding_response, "model"):
                embedding_model_version = embedding_response.model

        except Exception as e:
            logger.error(f"Failed to create embedding for query {query_id}: {e}")
            raise RuntimeError(
                f"OpenAI API error during embedding creation: {e}"
            ) from e

        # Step 2: Call hybrid_search via internal function (not MCP tool)
        # We'll implement inline semantic + keyword search with RRF fusion
        # Story 11.7.3: Use project-scoped connection for RLS filtering on l2_insights
        search_start = time.time()

        with get_connection_with_project_context_sync(read_only=True) as conn:
            register_vector(conn)
            cursor = conn.cursor()

            # Semantic search (RLS filters l2_insights by project_id via Migration 037)
            cursor.execute(
                """
                SELECT id
                FROM l2_insights
                ORDER BY embedding <=> %s::vector
                LIMIT 5
                """,
                (query_embedding,),
            )
            semantic_ids = [row[0] for row in cursor.fetchall()]

            # Keyword search (RLS filters l2_insights by project_id via Migration 037)
            cursor.execute(
                """
                SELECT id
                FROM l2_insights
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                ORDER BY ts_rank(
                    to_tsvector('english', content),
                    plainto_tsquery('english', %s)
                ) DESC
                LIMIT 5
                """,
                (query_text, query_text),
            )
            keyword_ids = [row[0] for row in cursor.fetchall()]

        # Simple RRF fusion for top-5 results
        k = 60
        rrf_scores = {}

        for rank, doc_id in enumerate(semantic_ids, 1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + weights["semantic"] / (
                k + rank
            )

        for rank, doc_id in enumerate(keyword_ids, 1):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + weights["keyword"] / (
                k + rank
            )

        # Sort by RRF score and take top-5
        sorted_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        retrieved_ids = [doc_id for doc_id, score in sorted_ids]

        search_end = time.time()
        retrieval_time = (search_end - search_start) * 1000  # Convert to milliseconds
        retrieval_times.append(retrieval_time)

        # Step 3: Calculate Precision@5
        precision = calculate_precision_at_5(retrieved_ids, expected_docs)
        precision_scores.append(precision)

        logger.info(
            f"  Query {idx}: P@5={precision:.2f}, retrieval_time={retrieval_time:.1f}ms"
        )

    # Step 4: Aggregate to macro-average Precision@5
    macro_avg_precision = sum(precision_scores) / len(precision_scores)
    avg_retrieval_time = sum(retrieval_times) / len(retrieval_times)

    logger.info(
        f"Golden Test execution complete: P@5={macro_avg_precision:.4f}, avg_retrieval_time={avg_retrieval_time:.1f}ms"
    )

    # Step 5: Drift Detection - Calculate 7-day rolling average baseline
    # Story 11.7.3: Use project-scoped connection for RLS filtering on model_drift_log
    today = date.today()

    with get_connection_with_project_context_sync(read_only=True) as conn:
        cursor = conn.cursor()

        # Query last 7 days of data for this project (excluding today)
        # RLS automatically filters by project_id
        cursor.execute(
            """
            SELECT AVG(precision_at_5) as baseline
            FROM model_drift_log
            WHERE date >= CURRENT_DATE - INTERVAL '7 days'
              AND date < CURRENT_DATE
            """,
        )

        baseline_result = cursor.fetchone()
        baseline_p5 = baseline_result[0] if baseline_result[0] is not None else None

    # Drift detection logic
    if baseline_p5 is None:
        # Less than 7 days of data - cannot detect drift yet
        drift_detected = False
        drop_percentage = 0.0
        logger.info("Drift detection disabled: less than 7 days of historical data")
    else:
        # Check if current P@5 dropped >5% (absolute) from baseline
        drop_absolute = baseline_p5 - macro_avg_precision
        drop_percentage = drop_absolute / baseline_p5 if baseline_p5 > 0 else 0.0

        drift_detected = drop_absolute > 0.05

        if drift_detected:
            logger.warning(
                f"🚨 DRIFT DETECTED! P@5 dropped {drop_absolute:.4f} (>{0.05}) from 7-day baseline {baseline_p5:.4f}"
            )
        else:
            logger.info(
                f"No drift detected: P@5={macro_avg_precision:.4f}, baseline={baseline_p5:.4f}, drop={drop_absolute:.4f}"
            )

    # Step 6: Store metrics in model_drift_log (UPSERT)
    # Story 11.7.3: Use project-scoped connection and include project_id in UPSERT
    # Note: ON CONFLICT now uses composite key (date, project_id) instead of just (date)
    with get_connection_with_project_context_sync() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO model_drift_log
            (date, precision_at_5, num_queries, avg_retrieval_time, embedding_model_version, drift_detected, baseline_p5, project_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (date, project_id) DO UPDATE SET
                precision_at_5 = EXCLUDED.precision_at_5,
                num_queries = EXCLUDED.num_queries,
                avg_retrieval_time = EXCLUDED.avg_retrieval_time,
                embedding_model_version = EXCLUDED.embedding_model_version,
                drift_detected = EXCLUDED.drift_detected,
                baseline_p5 = EXCLUDED.baseline_p5
            """,
            (
                today,
                macro_avg_precision,
                query_count,
                avg_retrieval_time,
                embedding_model_version,
                drift_detected,
                baseline_p5,
                project_id,  # Story 11.7.3: Store results per project
            ),
        )

        conn.commit()
        logger.info(f"Stored results in model_drift_log for date {today}, project {project_id}")

    # Step 7: Return response
    total_time = time.time() - start_time

    result = {
        "date": today.isoformat(),
        "precision_at_5": macro_avg_precision,
        "num_queries": query_count,
        "drift_detected": drift_detected,
        "baseline_p5": baseline_p5,
        "current_p5": macro_avg_precision,  # Alias for clarity
        "drop_percentage": drop_percentage,
        "avg_retrieval_time": avg_retrieval_time,
        "embedding_model_version": embedding_model_version,
        "total_execution_time": total_time,
        "project_id": project_id,  # Story 11.7.3: Include project_id in response
        "status": "success",
    }

    logger.info(
        f"Golden Test complete in {total_time:.2f}s for project {project_id}: P@5={macro_avg_precision:.4f}, drift={drift_detected}"
    )

    return result


# =============================================================================
# MCP Tool Wrapper (MCP Protocol Callable)
# =============================================================================


async def handle_get_golden_test_results(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    MCP Tool wrapper for Golden Test execution.

    This function is called via MCP protocol from Claude Code.
    It delegates to execute_golden_test() for actual implementation.

    Story 11.7.3: Pass project_id from middleware context to execute_golden_test()

    Args:
        arguments: Empty dict (no parameters required)

    Returns:
        Golden Test results or error response
    """
    logger.info("MCP Tool get_golden_test_results called")

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Story 11.7.3: Execute Golden Test with project_id (synchronous function)
        result = execute_golden_test(project_id=project_id)
        return add_response_metadata(result, project_id)

    except RuntimeError as e:
        logger.error(f"Golden Test execution failed: {e}")
        # If get_current_project() failed, project_id won't be available
        # Call again to get project_id for metadata, handle if it fails again
        try:
            project_id = get_current_project()
        except RuntimeError:
            project_id = "unknown"
        return add_response_metadata({
            "error": "Golden Test execution failed",
            "details": str(e),
            "tool": "get_golden_test_results",
            "status": "failed",
        }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in get_golden_test_results: {e}")
        # project_id is available if we got past the get_current_project() call
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "get_golden_test_results",
            "status": "failed",
        }, project_id)
