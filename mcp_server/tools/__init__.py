"""
MCP Server Tools Registration Module

Provides tool registration and implementation for the Cognitive Memory System.
Includes 18 tools: store_raw_dialogue, compress_to_l2_insight, hybrid_search,
update_working_memory, store_episode, store_dual_judge_scores, get_golden_test_results,
ping, graph_add_node, graph_add_edge, graph_query_neighbors, graph_find_path,
get_node_by_name, get_edge, count_by_type, list_episodes, get_insight_by_id,
dissonance_check, and resolve_dissonance.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import psycopg2
import psycopg2.extras
from mcp.server import Server
from mcp.types import Tool
from openai import APIConnectionError, OpenAI, RateLimitError
from pgvector.psycopg2 import register_vector
from psycopg2.extensions import cursor as cursor_type
from psycopg2.extras import DictRow

from mcp_server.db.connection import get_connection
from mcp_server.tools.dual_judge import DualJudgeEvaluator
from mcp_server.tools.get_golden_test_results import handle_get_golden_test_results
from mcp_server.tools.graph_add_node import handle_graph_add_node
from mcp_server.tools.graph_add_edge import handle_graph_add_edge
from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors
from mcp_server.tools.graph_find_path import handle_graph_find_path
from mcp_server.tools.get_node_by_name import handle_get_node_by_name
from mcp_server.tools.get_edge import handle_get_edge
from mcp_server.tools.count_by_type import handle_count_by_type
from mcp_server.tools.list_episodes import handle_list_episodes
from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id
from mcp_server.tools.dissonance_check import handle_dissonance_check as handle_dissonance_check_impl, DISSONANCE_CHECK_TOOL
from mcp_server.tools.resolve_dissonance import handle_resolve_dissonance, RESOLVE_DISSONANCE_TOOL


def rrf_fusion(
    semantic_results: list[dict],
    keyword_results: list[dict],
    weights: dict,
    k: int = 60,
    graph_results: list[dict] | None = None,
) -> list[dict]:
    """
    Reciprocal Rank Fusion mit gewichteten Scores für 2 oder 3 Quellen.

    Formula (2 sources): score(doc) = w_s/(k+rank_s) + w_k/(k+rank_k)
    Formula (3 sources): score(doc) = w_s/(k+rank_s) + w_k/(k+rank_k) + w_g/(k+rank_g)

    If doc only in 1-2 result sets, only those terms are used.

    Args:
        semantic_results: Results from pgvector semantic search
        keyword_results: Results from full-text keyword search
        weights: {"semantic": 0.6, "keyword": 0.2, "graph": 0.2} (must sum to 1.0)
        k: Constant (60 is standard in literature)
        graph_results: Optional results from graph search (Story 4.6)

    Returns:
        Merged and sorted results by final RRF score
    """
    # Initialize graph_results if None
    if graph_results is None:
        graph_results = []

    # Empty result handling
    if not semantic_results and not keyword_results and not graph_results:
        return []  # All empty → return empty list (NOT an error)

    # Weight normalization: ensure weights sum to 1.0
    semantic_weight = weights.get("semantic", 0.6)
    keyword_weight = weights.get("keyword", 0.2)
    graph_weight = weights.get("graph", 0.2)

    # Normalize weights if they don't sum to 1.0
    total_weight = semantic_weight + keyword_weight + graph_weight
    if abs(total_weight - 1.0) > 1e-9:
        # Normalize to 1.0
        semantic_weight = semantic_weight / total_weight
        keyword_weight = keyword_weight / total_weight
        graph_weight = graph_weight / total_weight

    # Bug Fix 2025-12-06: Allow both int and str IDs (episodes use "episode_49" format)
    merged_scores: dict[int | str, dict] = {}

    # Semantic Search Scores
    for rank, result in enumerate(semantic_results, start=1):
        doc_id = result["id"]
        score = semantic_weight / (k + rank)
        merged_scores[doc_id] = result.copy()
        merged_scores[doc_id]["score"] = score

    # Keyword Search Scores (aggregate if doc already in merged_scores)
    for rank, result in enumerate(keyword_results, start=1):
        doc_id = result["id"]
        score = keyword_weight / (k + rank)

        if doc_id in merged_scores:
            # Doc in both result sets → aggregate scores
            merged_scores[doc_id]["score"] += score
        else:
            # New doc from keyword search
            merged_scores[doc_id] = result.copy()
            merged_scores[doc_id]["score"] = score

    # Graph Search Scores (aggregate if doc already in merged_scores)
    for rank, result in enumerate(graph_results, start=1):
        doc_id = result["id"]
        score = graph_weight / (k + rank)

        if doc_id in merged_scores:
            # Doc in existing result sets → aggregate scores
            merged_scores[doc_id]["score"] += score
        else:
            # New doc from graph search
            merged_scores[doc_id] = result.copy()
            merged_scores[doc_id]["score"] = score

    # Sort by final RRF score (descending)
    sorted_results = sorted(
        merged_scores.values(), key=lambda x: x["score"], reverse=True
    )

    return sorted_results


def _build_filter_clause(filter_params: dict | None) -> tuple[str, list]:
    """
    Build SQL WHERE clause from filter parameters.
    Supports top-level columns (io_category, is_identity, source_file)
    and metadata JSONB fields.
    """
    if not filter_params:
        return "", []

    clauses = []
    values = []

    for key, value in filter_params.items():
        # Check if key is a top-level column
        if key in ["io_category", "is_identity", "source_file"]:
            clauses.append(f"{key} = %s")
            values.append(value)
        # Otherwise assume it's in metadata JSONB
        else:
            clauses.append("metadata->>%s = %s")
            values.extend([key, str(value)])

    if not clauses:
        return "", []

    return " AND " + " AND ".join(clauses), values


async def semantic_search(
    query_embedding: list[float], top_k: int, conn: Any, filter_params: dict | None = None
) -> list[dict]:
    """
    Semantic search using pgvector cosine distance.

    Args:
        query_embedding: 1536-dim vector from OpenAI
        top_k: Number of results to return
        conn: PostgreSQL connection

    Returns:
        List of dicts with id, content, source_ids, distance, rank
    """
    # Register pgvector type (required once per connection)
    register_vector(conn)

    cursor = conn.cursor()

    # Build filter clause
    filter_clause, filter_values = _build_filter_clause(filter_params)

    # Cosine distance: <=> operator
    # Lower distance = higher similarity
    query = f"""
        SELECT id, content, source_ids, metadata, io_category, is_identity, source_file,
               embedding <=> %s::vector AS distance
        FROM l2_insights
        WHERE 1=1 {filter_clause}
        ORDER BY distance
        LIMIT %s;
        """
    
    # Combine parameters: embedding, filter_values, top_k
    params = [query_embedding] + filter_values + [top_k]
    
    cursor.execute(query, params)

    results = cursor.fetchall()

    # Add rank position (1-indexed)
    return [
        {
            "id": row["id"],
            "content": row["content"],
            "source_ids": row["source_ids"],
            "metadata": row["metadata"],
            "io_category": row["io_category"],
            "is_identity": row["is_identity"],
            "source_file": row["source_file"],
            "distance": row["distance"],
            "rank": idx + 1,
        }
        for idx, row in enumerate(results)
    ]


async def keyword_search(
    query_text: str, top_k: int, conn: Any, filter_params: dict | None = None,
    language: str = "simple"
) -> list[dict]:
    """
    Keyword search using PostgreSQL Full-Text Search.

    Bug Fix 2025-12-06: Changed default language from 'english' to 'simple'
    for better multi-language support. 'simple' doesn't apply stemming but
    does basic tokenization, which works better for German compound words
    like "Identitätsmaterial" or "Task-Completion-Modus".

    Args:
        query_text: Query string (e.g., "consciousness autonomy")
        top_k: Number of results to return
        conn: PostgreSQL connection
        filter_params: Optional filter parameters
        language: FTS language config ('simple', 'english', 'german', etc.)
                  Default: 'simple' for multi-language support

    Returns:
        List of dicts with id, content, source_ids, rank, rank_position
    """
    cursor = conn.cursor()

    # Build filter clause
    filter_clause, filter_values = _build_filter_clause(filter_params)

    # ts_rank: Relevance score (higher = better match)
    # plainto_tsquery: Converts plain text to tsquery (handles spaces, punctuation)
    # Using parameterized language config for multi-language support
    query = f"""
        SELECT id, content, source_ids, metadata, io_category, is_identity, source_file,
               ts_rank(
                   to_tsvector('{language}', content),
                   plainto_tsquery('{language}', %s)
               ) AS rank
        FROM l2_insights
        WHERE to_tsvector('{language}', content) @@ plainto_tsquery('{language}', %s)
        {filter_clause}
        ORDER BY rank DESC
        LIMIT %s;
        """

    # Combine parameters: query_text, query_text, filter_values, top_k
    params = [query_text, query_text] + filter_values + [top_k]

    cursor.execute(query, params)

    results = cursor.fetchall()

    # Add rank position (1-indexed)
    return [
        {
            "id": row["id"],
            "content": row["content"],
            "source_ids": row["source_ids"],
            "metadata": row["metadata"],
            "io_category": row["io_category"],
            "is_identity": row["is_identity"],
            "source_file": row["source_file"],
            "rank": row["rank"],
            "rank_position": idx + 1,
        }
        for idx, row in enumerate(results)
    ]


# ============================================================================
# Episode Memory Search Functions (Bug Fix 2025-12-06)
# ============================================================================


async def episode_semantic_search(
    query_embedding: list[float], top_k: int, conn: Any
) -> list[dict]:
    """
    Semantic search in episode_memory using pgvector cosine distance.

    Bug Fix 2025-12-06: Added to include episode memories in hybrid search.
    Episodes contain valuable lessons (query + reward + reflection) that
    should be searchable.

    Args:
        query_embedding: 1536-dim vector from OpenAI
        top_k: Number of results to return
        conn: PostgreSQL connection

    Returns:
        List of dicts with id, query, reflection, reward, distance, rank
    """
    # Register pgvector type (required once per connection)
    register_vector(conn)

    cursor = conn.cursor()

    # Cosine distance: <=> operator
    # Lower distance = higher similarity
    query = """
        SELECT id, query, reflection, reward, created_at,
               embedding <=> %s::vector AS distance
        FROM episode_memory
        ORDER BY distance
        LIMIT %s;
        """

    cursor.execute(query, [query_embedding, top_k])
    results = cursor.fetchall()

    # Format results for RRF fusion (needs 'id' and 'content' keys)
    return [
        {
            "id": f"episode_{row['id']}",  # Prefix to distinguish from l2_insights
            "content": f"Episode: {row['query']} → Reflection: {row['reflection']}",
            "source_type": "episode_memory",
            "episode_id": row["id"],
            "query": row["query"],
            "reflection": row["reflection"],
            "reward": row["reward"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "distance": row["distance"],
            "rank": idx + 1,
        }
        for idx, row in enumerate(results)
    ]


async def episode_keyword_search(
    query_text: str, top_k: int, conn: Any, language: str = "simple"
) -> list[dict]:
    """
    Keyword search in episode_memory using PostgreSQL Full-Text Search.

    Bug Fix 2025-12-06: Added to include episode memories in hybrid search.
    Uses 'simple' language by default for multi-language support.

    Args:
        query_text: Query string
        top_k: Number of results to return
        conn: PostgreSQL connection
        language: FTS language config (default: 'simple' for multi-language)

    Returns:
        List of dicts with id, query, reflection, reward, rank
    """
    cursor = conn.cursor()

    # Search in both query and reflection fields
    # Using 'simple' language for better multi-language support
    query = f"""
        SELECT id, query, reflection, reward, created_at,
               ts_rank(
                   to_tsvector('{language}', query || ' ' || reflection),
                   plainto_tsquery('{language}', %s)
               ) AS rank
        FROM episode_memory
        WHERE to_tsvector('{language}', query || ' ' || reflection)
              @@ plainto_tsquery('{language}', %s)
        ORDER BY rank DESC
        LIMIT %s;
        """

    cursor.execute(query, [query_text, query_text, top_k])
    results = cursor.fetchall()

    # Format results for RRF fusion
    return [
        {
            "id": f"episode_{row['id']}",  # Prefix to distinguish from l2_insights
            "content": f"Episode: {row['query']} → Reflection: {row['reflection']}",
            "source_type": "episode_memory",
            "episode_id": row["id"],
            "query": row["query"],
            "reflection": row["reflection"],
            "reward": row["reward"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "rank": row["rank"],
            "rank_position": idx + 1,
        }
        for idx, row in enumerate(results)
    ]


# Default relational keywords for query routing (Story 4.6)
DEFAULT_RELATIONAL_KEYWORDS = {
    "de": [
        "nutzt", "verwendet", "verbunden", "abhängig", "Projekt", "Technologie",
        "gehört zu", "hat", "benutzt", "verknüpft", "zusammenhängt", "basiert auf"
    ],
    "en": [
        "uses", "connected", "dependent", "project", "technology", "belongs to",
        "has", "relates to", "linked", "associated", "based on", "depends on"
    ],
}


def extract_entities_from_query(query_text: str) -> list[str]:
    """
    Extract entities from query text using simple pattern matching.

    Patterns:
    1. Capitalized words (e.g., "Python", "Next.js", "Agentic Business")
    2. Quoted strings (e.g., '"cognitive-memory"', "'PostgreSQL'")

    No NLP dependency - uses regex for simplicity and performance.

    Args:
        query_text: The query text to extract entities from

    Returns:
        List of extracted entity strings (deduplicated)
    """
    entities: list[str] = []

    # Pattern 1: Capitalized words (excluding sentence starts for short words)
    words = query_text.split()
    for i, word in enumerate(words):
        # Clean word from punctuation
        clean_word = word.strip('.,!?;:()[]{}')
        if not clean_word:
            continue

        # Check if word starts with uppercase
        if clean_word[0].isupper():
            # Include if not first word OR word length > 3 (likely a proper noun)
            if i > 0 or len(clean_word) > 3:
                entities.append(clean_word)

    # Pattern 2: Quoted strings (single or double quotes)
    quoted = re.findall(r'["\']([^"\']+)["\']', query_text)
    entities.extend(quoted)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_entities: list[str] = []
    for entity in entities:
        if entity.lower() not in seen:
            seen.add(entity.lower())
            unique_entities.append(entity)

    return unique_entities


def detect_relational_query(
    query_text: str,
    relational_keywords: dict[str, list[str]] | None = None
) -> tuple[bool, list[str]]:
    """
    Detect if a query contains relational keywords.

    Checks for relational patterns in both German and English.
    Case-insensitive matching.

    Args:
        query_text: The query text to analyze
        relational_keywords: Optional custom keyword lists {"de": [...], "en": [...]}

    Returns:
        Tuple of (is_relational: bool, matched_keywords: list[str])
    """
    if relational_keywords is None:
        relational_keywords = DEFAULT_RELATIONAL_KEYWORDS

    query_lower = query_text.lower()
    matched_keywords: list[str] = []

    # Check German keywords
    for keyword in relational_keywords.get("de", []):
        if keyword.lower() in query_lower:
            matched_keywords.append(keyword)

    # Check English keywords
    for keyword in relational_keywords.get("en", []):
        if keyword.lower() in query_lower:
            matched_keywords.append(keyword)

    is_relational = len(matched_keywords) > 0
    return is_relational, matched_keywords


def get_adjusted_weights(is_relational: bool, base_weights: dict | None = None) -> dict:
    """
    Get weights adjusted based on query type.

    Args:
        is_relational: True if query contains relational keywords
        base_weights: Optional base weights to use (default: 60/20/20)

    Returns:
        Weight dictionary {"semantic": float, "keyword": float, "graph": float}
    """
    if is_relational:
        # Relational query: boost graph weight
        return {"semantic": 0.4, "keyword": 0.2, "graph": 0.4}
    else:
        # Standard query: default weights
        if base_weights:
            return {
                "semantic": base_weights.get("semantic", 0.6),
                "keyword": base_weights.get("keyword", 0.2),
                "graph": base_weights.get("graph", 0.2),
            }
        return {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}


async def graph_search(
    query_text: str,
    top_k: int,
    conn: Any
) -> list[dict]:
    """
    Graph-based search with L2 Insight retrieval via node neighbors.

    Steps:
    1. Extract entities from query (capitalized words, quoted strings)
    2. For each entity, lookup node by name
    3. For found nodes, query direct neighbors (depth=1)
    4. For neighbors with vector_id, fetch L2 Insight
    5. Calculate relevance score based on edge weight
    6. Return ranked results

    Args:
        query_text: Query text to search for entities
        top_k: Maximum number of results to return
        conn: PostgreSQL connection

    Returns:
        List of L2 Insight dicts with graph-based relevance scores
    """
    from mcp_server.db.graph import get_node_by_name, query_neighbors

    logger = logging.getLogger(__name__)

    # Step 1: Extract entities from query
    entities = extract_entities_from_query(query_text)

    if not entities:
        logger.debug(f"No entities extracted from query: {query_text[:100]}")
        return []

    logger.debug(f"Extracted entities: {entities}")

    results: list[dict] = []
    seen_ids: set[int] = set()

    # Step 2-4: For each entity, lookup nodes and neighbors
    for entity in entities:
        # Lookup node by name
        node = get_node_by_name(entity)

        if not node:
            logger.debug(f"No node found for entity: {entity}")
            continue

        logger.debug(f"Found node for entity '{entity}': {node['name']} (id={node['id']})")

        # Query neighbors (depth=1 for performance)
        try:
            neighbors = query_neighbors(node["id"], relation_type=None, max_depth=1)
        except Exception as e:
            logger.warning(f"Failed to query neighbors for node {node['id']}: {e}")
            continue

        # Step 4: For neighbors with vector_id, fetch L2 Insight
        for neighbor in neighbors:
            vector_id = neighbor.get("properties", {}).get("vector_id") if neighbor.get("properties") else None

            # Also check if the node itself has a vector_id
            # Need to look up the actual node to get its vector_id
            neighbor_node = get_node_by_name(neighbor["name"])
            if neighbor_node and neighbor_node.get("vector_id"):
                vector_id = neighbor_node["vector_id"]

            if not vector_id:
                continue

            # Skip duplicates
            if vector_id in seen_ids:
                continue
            seen_ids.add(vector_id)

            # Fetch L2 Insight from database
            try:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, content, source_ids, metadata, io_category, is_identity, source_file
                    FROM l2_insights
                    WHERE id = %s;
                    """,
                    (vector_id,)
                )
                insight = cursor.fetchone()

                if insight:
                    # Calculate graph relevance score based on edge weight and distance
                    edge_weight = neighbor.get("weight", 1.0)
                    distance = neighbor.get("distance", 1)
                    # Score formula: edge_weight / distance (closer + stronger = higher score)
                    graph_score = edge_weight / distance

                    results.append({
                        "id": insight["id"],
                        "content": insight["content"],
                        "source_ids": insight["source_ids"],
                        "metadata": insight["metadata"],
                        "io_category": insight.get("io_category"),
                        "is_identity": insight.get("is_identity"),
                        "source_file": insight.get("source_file"),
                        "graph_score": graph_score,
                        "graph_distance": distance,
                        "source_entity": entity,
                        "source_relation": neighbor.get("relation", "UNKNOWN"),
                    })

            except Exception as e:
                logger.warning(f"Failed to fetch L2 insight {vector_id}: {e}")
                continue

    # Step 5-6: Sort by graph_score and add rank
    results.sort(key=lambda x: x["graph_score"], reverse=True)
    for idx, result in enumerate(results):
        result["rank"] = idx + 1

    logger.debug(f"Graph search found {len(results)} results for query: {query_text[:50]}")

    return results[:top_k]


# Custom exception for tool parameter validation
class ParameterValidationError(Exception):
    """Raised when tool parameters are invalid."""

    pass


def validate_parameters(params: dict[str, Any], schema: dict[str, Any]) -> None:
    """
    Validate tool parameters against JSON schema.

    Args:
        params: Parameters to validate
        schema: JSON schema for validation

    Raises:
        ParameterValidationError: If validation fails
    """
    try:
        # Use jsonschema if available, otherwise do basic validation
        try:
            from jsonschema import ValidationError, validate

            validate(instance=params, schema=schema)
        except ImportError:
            # Fallback to basic validation if jsonschema not available
            required_fields = schema.get("required", [])
            properties = schema.get("properties", {})

            for field in required_fields:
                if field not in params:
                    raise ParameterValidationError(
                        f"Missing required parameter: {field}"
                    ) from None

            for field, value in params.items():
                if field in properties:
                    field_schema = properties[field]
                    expected_type = field_schema.get("type")
                    if expected_type == "string" and not isinstance(value, str):
                        raise ParameterValidationError(
                            f"Parameter '{field}' must be a string"
                        ) from None
                    elif expected_type == "integer" and not isinstance(value, int):
                        raise ParameterValidationError(
                            f"Parameter '{field}' must be an integer"
                        ) from None
                    elif expected_type == "array" and not isinstance(value, list):
                        raise ParameterValidationError(
                            f"Parameter '{field}' must be an array"
                        ) from None

    except Exception as e:
        if "ValidationError" in str(type(e)):
            raise ParameterValidationError(str(e)) from None
        raise ParameterValidationError(f"Parameter validation failed: {e}") from None


def calculate_fidelity(content: str) -> float:
    """
    Calculate information density using simple POS heuristic.

    Counts semantic units (nouns, verbs, adjectives) vs. total tokens.
    Higher ratio = more semantic content per token.

    Args:
        content: Text content to analyze

    Returns:
        Float between 0.0 and 1.0 (density score)
    """
    if not content or not content.strip():
        return 0.0

    # Tokenize (simple whitespace split)
    tokens = content.split()
    if len(tokens) == 0:
        return 0.0

    # Count semantic units (simplified - no actual POS tagging)
    # Use heuristic: words >3 chars are likely semantic (nouns/verbs)
    # Filter out common stop words (English + German)
    stop_words = {
        # English:
        "the",
        "is",
        "at",
        "which",
        "on",
        "and",
        "or",
        "but",
        "with",
        "from",
        "to",
        "of",
        "in",
        "for",
        "a",
        "an",
        "this",
        "that",
        # German:
        "der",
        "die",
        "das",
        "und",
        "oder",
        "aber",
        "mit",
        "von",
        "zu",
        "für",
        "ein",
        "eine",
        "dies",
        "dass",
        "dem",
        "den",
        "des",
        "sich",
        "sind",
        "wird",
        "wurde",
        "auch",
        "nicht",
        "kann",
        "hat",
        "war",
        "bei",
        "aus",
        "nach",
        "vor",
        "auf",
        "über",
        "unter",
        "durch",
        "um",
        "bis",
    }

    semantic_count = 0
    for token in tokens:
        word = token.lower().strip('.,!?;:"')
        if len(word) > 3 and word not in stop_words:
            semantic_count += 1

    density = semantic_count / len(tokens)
    return min(1.0, density)  # Clamp to 1.0


async def get_embedding_with_retry(
    client: OpenAI, text: str, max_retries: int = 3
) -> list[float]:
    """
    Call OpenAI Embeddings API with exponential backoff retry.

    Args:
        client: OpenAI client instance
        text: Text to embed
        max_retries: Maximum number of retry attempts

    Returns:
        1536-dimensional embedding vector

    Raises:
        RuntimeError: If all retries fail
        ValueError: If API key is not configured
    """
    delays = [1, 2, 4]  # Exponential backoff in seconds
    logger = logging.getLogger(__name__)

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small", input=text, encoding_format="float"
            )
            embedding = response.data[0].embedding
            logger.info(f"Successfully generated embedding for {len(text)} characters")
            return embedding

        except RateLimitError as e:
            if attempt < max_retries - 1:
                delay = delays[attempt]
                logger.warning(
                    f"Rate limit hit, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Rate limit error after {max_retries} attempts: {e}")
                raise RuntimeError(
                    f"Failed to get embedding after {max_retries} attempts due to rate limiting"
                ) from e

        except APIConnectionError as e:
            if attempt < max_retries - 1:
                delay = delays[attempt]
                logger.warning(
                    f"API connection error, retrying in {delay}s... (attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"API connection error after {max_retries} attempts: {e}")
                raise RuntimeError(
                    f"Failed to get embedding after {max_retries} attempts due to connection errors"
                ) from e

        except Exception as e:
            logger.error(f"Unexpected OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API error: {e}") from e

    raise RuntimeError(f"Failed to get embedding after {max_retries} attempts")


async def handle_store_raw_dialogue(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Store raw dialogue data to L0 memory.

    Args:
        arguments: Tool arguments containing session_id, speaker, content, metadata

    Returns:
        Success response with id and timestamp, or error response
    """

    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        session_id = arguments.get("session_id")
        speaker = arguments.get("speaker")
        content = arguments.get("content")
        metadata = arguments.get("metadata")  # Optional

        # Convert metadata to JSON string for JSONB
        metadata_json = json.dumps(metadata) if metadata else None

        # Insert into database
        with get_connection() as conn:
            cursor: cursor_type = conn.cursor()
            cursor.execute(
                """
                INSERT INTO l0_raw (session_id, speaker, content, metadata)
                VALUES (%s, %s, %s, %s)
                RETURNING id, timestamp;
                """,
                (session_id, speaker, content, metadata_json),
            )
            result = cursor.fetchone()

            if not result:
                raise RuntimeError("INSERT did not return id and timestamp")

            row_id = int(result["id"])
            timestamp = result["timestamp"]
            # Commit transaction
            conn.commit()

            logger.info(f"Stored raw dialogue: id={row_id}, session={session_id}")

            return {
                "id": row_id,
                "timestamp": timestamp.isoformat(),
                "session_id": session_id,
                "status": "success",
            }

    except psycopg2.Error as e:
        logger.error(f"Database error in store_raw_dialogue: {e}")
        return {
            "error": "Database operation failed",
            "details": str(e),
            "tool": "store_raw_dialogue",
        }
    except Exception as e:
        logger.error(f"Unexpected error in store_raw_dialogue: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "store_raw_dialogue",
        }


async def handle_compress_to_l2_insight(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Compress dialogue data to L2 insight with OpenAI embedding.

    Args:
        arguments: Tool arguments containing content and source_ids

    Returns:
        Dict with insight ID, embedding status, and fidelity score
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        content = arguments.get("content")
        source_ids = arguments.get("source_ids")

        # Parameter validation
        if not content or not isinstance(content, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'content' parameter (must be string)",
                "tool": "compress_to_l2_insight",
            }

        # Accept empty list [] but reject None or non-list types
        if source_ids is None or not isinstance(source_ids, list):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'source_ids' parameter (must be array of integers)",
                "tool": "compress_to_l2_insight",
            }

        # Validate all source_ids are integers
        try:
            source_ids = [int(id) for id in source_ids]
        except (ValueError, TypeError) as e:
            return {
                "error": "Parameter validation failed",
                "details": f"All source_ids must be integers: {e}",
                "tool": "compress_to_l2_insight",
            }

        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-your-openai-api-key-here":
            return {
                "error": "OpenAI API key not configured",
                "details": "OPENAI_API_KEY environment variable not set or contains placeholder value",
                "tool": "compress_to_l2_insight",
            }

        client = OpenAI(api_key=api_key)

        # Calculate semantic fidelity
        fidelity_score = calculate_fidelity(content)
        fidelity_threshold = float(os.getenv("FIDELITY_THRESHOLD", "0.5"))

        # Prepare metadata
        metadata: dict[str, Any] = {
            "fidelity_score": fidelity_score,
            "fidelity_warning": fidelity_score < fidelity_threshold,
        }

        if fidelity_score < fidelity_threshold:
            metadata["warning_message"] = (
                f"Low information density ({fidelity_score:.2f} < {fidelity_threshold}) - consider more detailed compression"
            )

        logger.info(
            f"Computing embedding for content (fidelity: {fidelity_score:.2f}, warning: {metadata['fidelity_warning']})"
        )

        # Get embedding with retry logic
        embedding_status = "success"
        try:
            embedding = await get_embedding_with_retry(client, content)
        except RuntimeError as e:
            if "rate limiting" in str(e).lower():
                embedding_status = "retried"
            else:
                raise e

        # Store in database
        try:
            with get_connection() as conn:
                # Register vector type for pgvector
                register_vector(conn)

                cursor = conn.cursor()

                # Insert insight with embedding and metadata
                cursor.execute(
                    """
                    INSERT INTO l2_insights (content, embedding, source_ids, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, created_at;
                    """,
                    (content, embedding, source_ids, json.dumps(metadata)),
                )

                result = cursor.fetchone()
                conn.commit()

                insight_id = int(result["id"])
                created_at = result["created_at"].isoformat()
                logger.info(
                    f"Successfully stored L2 insight {insight_id} with {len(embedding)}-dimensional embedding"
                )

                return {
                    "id": insight_id,
                    "embedding_status": embedding_status,
                    "fidelity_score": fidelity_score,
                    "timestamp": created_at,
                }

        except psycopg2.Error as e:
            logger.error(f"Database error storing L2 insight: {e}")
            return {
                "error": "Database operation failed",
                "details": str(e),
                "tool": "compress_to_l2_insight",
            }

    except Exception as e:
        logger.error(f"Unexpected error in compress_to_l2_insight: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "compress_to_l2_insight",
        }


def generate_query_embedding(query_text: str) -> list[float]:
    """
    Generate embedding for query text using OpenAI API.

    Bug Fix 2025-12-06: Replaced mock embeddings with real OpenAI API calls.
    Mock embeddings caused semantic search failures because query vectors
    didn't match stored document vectors.

    Args:
        query_text: The query text to embed

    Returns:
        1536-dimensional embedding vector

    Raises:
        RuntimeError: If OpenAI API key is not configured or API call fails
    """
    logger = logging.getLogger(__name__)

    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        raise RuntimeError(
            "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
        )

    try:
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=query_text,
            encoding_format="float"
        )
        embedding = response.data[0].embedding
        logger.debug(f"Generated real embedding for query ({len(query_text)} chars)")
        return embedding

    except RateLimitError as e:
        logger.warning(f"OpenAI rate limit hit, retrying once: {e}")
        # Single retry with backoff
        time.sleep(1)
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=query_text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as retry_error:
            raise RuntimeError(f"Embedding generation failed after retry: {retry_error}") from retry_error

    except APIConnectionError as e:
        raise RuntimeError(f"OpenAI API connection failed: {e}") from e

    except Exception as e:
        raise RuntimeError(f"Embedding generation failed: {e}") from e


async def handle_hybrid_search(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Perform hybrid semantic + keyword + graph search with RRF fusion.

    Story 4.6: Extended with graph search integration and query routing.

    Args:
        arguments: Tool arguments containing query_text, optional query_embedding, top_k, weights

    Returns:
        Search results with fused scores, query type, and applied weights
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        query_embedding = arguments.get("query_embedding")  # Optional now
        query_text = arguments.get("query_text")
        top_k = arguments.get("top_k", 5)
        weights = arguments.get("weights")  # Now optional, will be determined by query routing
        filter_params = arguments.get("filter")

        # Parameter validation - query_text is required
        if not query_text or not isinstance(query_text, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'query_text' parameter (must be string)",
                "tool": "hybrid_search",
            }

        # Generate embedding if not provided
        if not query_embedding:
            logger.info(f"Generating embedding for query: {query_text}")
            query_embedding = generate_query_embedding(query_text)
        elif not isinstance(query_embedding, list):
            return {
                "error": "Parameter validation failed",
                "details": "'query_embedding' must be array of floats if provided",
                "tool": "hybrid_search",
            }

        if not isinstance(top_k, int) or top_k <= 0 or top_k > 100:
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'top_k' parameter (must be integer between 1 and 100)",
                "tool": "hybrid_search",
            }

        # Validate embedding dimension (1536 for OpenAI text-embedding-3-small)
        if len(query_embedding) != 1536:
            return {
                "error": "Parameter validation failed",
                "details": f"Invalid embedding dimension: {len(query_embedding)}. Expected 1536 for OpenAI text-embedding-3-small",
                "tool": "hybrid_search",
            }

        # Story 4.6: Query Routing - detect relational queries
        is_relational, matched_keywords = detect_relational_query(query_text)
        query_type = "relational" if is_relational else "standard"

        # Story 4.6: Backwards-compatible weight handling
        # Bug #1 fix: User-provided weights should always be respected
        if weights is None:
            # No weights provided → use query routing to determine weights
            applied_weights = get_adjusted_weights(is_relational)
        elif isinstance(weights, dict):
            # Weights provided - check for backwards compatibility (old 2-source format)
            if "graph" not in weights:
                # Old format: {"semantic": 0.7, "keyword": 0.3}
                # Bug #1 fix: Convert old format to new format, preserving user intent
                # Scale down semantic/keyword proportionally to add 0.2 graph weight
                semantic_weight = weights.get("semantic", 0.7)
                keyword_weight = weights.get("keyword", 0.3)

                # Normalize to make room for default graph weight (0.2)
                # Preserve the ratio between semantic and keyword weights
                total_old = semantic_weight + keyword_weight
                if total_old > 0:
                    # Scale down to 0.8 total, add 0.2 for graph
                    scale_factor = 0.8 / total_old
                    applied_weights = {
                        "semantic": semantic_weight * scale_factor,
                        "keyword": keyword_weight * scale_factor,
                        "graph": 0.2,
                    }
                else:
                    # Edge case: both weights are 0 → use defaults
                    applied_weights = get_adjusted_weights(is_relational)
            else:
                # New format: {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}
                applied_weights = {
                    "semantic": weights.get("semantic", 0.6),
                    "keyword": weights.get("keyword", 0.2),
                    "graph": weights.get("graph", 0.2),
                }
        else:
            # Invalid weights format → use defaults
            applied_weights = get_adjusted_weights(is_relational)

        # Execute searches
        with get_connection() as conn:
            # Run L2 Insights searches
            semantic_results = await semantic_search(query_embedding, top_k, conn, filter_params)
            keyword_results = await keyword_search(query_text, top_k, conn, filter_params)

            # Bug Fix 2025-12-06: Run Episode Memory searches
            # Episodes contain valuable lessons that should be searchable
            episode_semantic_results = await episode_semantic_search(query_embedding, top_k, conn)
            episode_keyword_results = await episode_keyword_search(query_text, top_k, conn)

            # Story 4.6: Run graph search
            graph_results = await graph_search(query_text, top_k, conn)

        # Bug Fix 2025-12-06: Merge episode results with L2 results for RRF fusion
        # Episodes use prefixed IDs ("episode_49") to distinguish from l2_insights IDs
        all_semantic_results = semantic_results + episode_semantic_results
        all_keyword_results = keyword_results + episode_keyword_results

        # Apply RRF fusion with all sources (including episodes)
        fused_results = rrf_fusion(
            all_semantic_results,
            all_keyword_results,
            applied_weights,
            k=60,
            graph_results=graph_results
        )

        # Select top-k results
        final_results = fused_results[:top_k]

        logger.info(
            f"Hybrid search completed: {len(semantic_results)} l2_semantic, "
            f"{len(episode_semantic_results)} episode_semantic, "
            f"{len(keyword_results)} l2_keyword, {len(episode_keyword_results)} episode_keyword, "
            f"{len(graph_results)} graph, {len(final_results)} fused (query_type={query_type})"
        )

        # Extended response format with episode counts
        return {
            "results": final_results,
            "query_embedding_dimension": len(query_embedding),
            "semantic_results_count": len(semantic_results),
            "keyword_results_count": len(keyword_results),
            "graph_results_count": len(graph_results),
            # Bug Fix 2025-12-06: Episode memory search counts
            "episode_semantic_count": len(episode_semantic_results),
            "episode_keyword_count": len(episode_keyword_results),
            "final_results_count": len(final_results),
            "query_type": query_type,
            "matched_keywords": matched_keywords if is_relational else [],
            "applied_weights": applied_weights,
            "weights": applied_weights,                 # Backwards-compatible alias
            "status": "success",
        }

    except psycopg2.Error as e:
        logger.error(f"Database error in hybrid_search: {e}")
        return {
            "error": "Database operation failed",
            "details": str(e),
            "tool": "hybrid_search",
        }
    except Exception as e:
        logger.error(f"Unexpected error in hybrid_search: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "hybrid_search",
        }


async def add_working_memory_item(
    content: str, importance: float, conn: psycopg2.extensions.connection
) -> int:
    """
    Add a new item to working memory with importance score and timestamp.

    Args:
        content: Content to store in working memory
        importance: Importance score (0.0-1.0)
        conn: PostgreSQL connection

    Returns:
        ID of the inserted item

    Raises:
        ValueError: If importance is outside valid range
        RuntimeError: If INSERT operation fails
    """
    cursor: cursor_type = conn.cursor()

    # Validate importance range
    if not (0.0 <= importance <= 1.0):
        raise ValueError(f"Importance must be between 0.0 and 1.0, got {importance}")

    # Insert item with automatic timestamp
    cursor.execute(
        """
        INSERT INTO working_memory (content, importance, last_accessed)
        VALUES (%s, %s, NOW())
        RETURNING id;
        """,
        (content, importance),
    )

    result = cursor.fetchone()
    if not result:
        raise RuntimeError("INSERT into working_memory did not return ID")

    return int(result["id"])


async def evict_lru_item(conn: psycopg2.extensions.connection) -> int | None:
    """
    Find oldest non-critical item for LRU eviction.

    Critical Items (importance >0.8) are NEVER evicted via LRU.
    If all items are critical, return None.

    Args:
        conn: PostgreSQL connection

    Returns:
        Item ID to evict, or None if no evictable items
    """
    cursor: cursor_type = conn.cursor()

    # Find oldest non-critical item
    cursor.execute(
        """
        SELECT id, content, importance, last_accessed
        FROM working_memory
        WHERE importance <= 0.8
        ORDER BY last_accessed ASC
        LIMIT 1;
        """
    )

    result = cursor.fetchone()

    if not result:
        # All items are critical (importance >0.8)
        # No eviction possible
        return None

    return int(result["id"])


async def force_evict_oldest_critical(conn: psycopg2.extensions.connection) -> int:
    """
    Force eviction of oldest item when all items are critical.

    Called when evict_lru_item() returns None (all items importance >0.8)
    but capacity is exceeded. Hard capacity limit overrides importance protection.

    Args:
        conn: PostgreSQL connection

    Returns:
        Item ID to force evict (oldest by last_accessed, ignoring importance)

    Raises:
        RuntimeError: If working memory is empty
    """
    cursor: cursor_type = conn.cursor()

    # Find oldest item, IGNORING importance
    cursor.execute(
        """
        SELECT id
        FROM working_memory
        ORDER BY last_accessed ASC
        LIMIT 1;
        """
    )

    result = cursor.fetchone()

    if not result:
        raise RuntimeError("Working Memory is empty, cannot evict")

    return int(result["id"])


async def archive_to_stale_memory(
    item_id: int, reason: str, conn: psycopg2.extensions.connection
) -> int:
    """
    Archive Working Memory item to Stale Memory before deletion.

    Args:
        item_id: Working Memory item ID
        reason: "LRU_EVICTION" or "MANUAL_ARCHIVE"
        conn: PostgreSQL connection

    Returns:
        Stale Memory archive ID

    Raises:
        ValueError: If working memory item not found
    """
    cursor: cursor_type = conn.cursor()

    # Load item from working_memory
    cursor.execute(
        "SELECT content, importance FROM working_memory WHERE id=%s;", (item_id,)
    )
    item = cursor.fetchone()

    if not item:
        raise ValueError(f"Working Memory item {item_id} not found")

    # Insert into stale_memory
    cursor.execute(
        """
        INSERT INTO stale_memory
        (original_content, importance, reason, archived_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id;
        """,
        (item["content"], item["importance"], reason),
    )

    archive_result = cursor.fetchone()
    archive_id = int(archive_result["id"])
    return archive_id


async def handle_update_working_memory(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Add item to Working Memory with atomic eviction handling.

    Args:
        arguments: Tool arguments containing content (string), importance (float, default 0.5)

    Returns:
        Success response with {added_id: int, evicted_id: Optional[int], archived_id: Optional[int]}
        or error response
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        content = arguments.get("content")
        importance = arguments.get("importance", 0.5)  # Default importance

        # Validate inputs
        if not content or not isinstance(content, str):
            return {
                "error": "Content is required and must be a non-empty string",
                "tool": "update_working_memory",
            }

        if not isinstance(importance, int | float):
            return {
                "error": "Importance must be a number between 0.0 and 1.0",
                "tool": "update_working_memory",
            }

        importance = float(importance)  # Convert to float

        if not (0.0 <= importance <= 1.0):
            return {
                "error": "Importance must be between 0.0 and 1.0",
                "tool": "update_working_memory",
            }

        # ENTIRE operation in single transaction to prevent race conditions
        with get_connection() as conn:
            try:
                cursor: cursor_type = conn.cursor()

                # 1. Add item
                added_id = await add_working_memory_item(content, importance, conn)

                # 2. Check capacity
                cursor.execute("SELECT COUNT(*) as count FROM working_memory;")
                count_result = cursor.fetchone()
                count = int(count_result["count"])
                # 3. Evict if needed (with fallback)
                evicted_id = None
                archived_id = None

                if count > 10:
                    evicted_id = await evict_lru_item(conn)

                    # FALLBACK: All items critical → force evict oldest
                    if evicted_id is None:
                        evicted_id = await force_evict_oldest_critical(conn)

                    # 4. Archive + Delete (within same transaction)
                    archived_id = await archive_to_stale_memory(
                        evicted_id, "LRU_EVICTION", conn
                    )
                    cursor.execute(
                        "DELETE FROM working_memory WHERE id=%s;", (evicted_id,)
                    )

                # SINGLE COMMIT for entire operation
                conn.commit()

                logger.info(
                    f"Updated working memory: added_id={added_id}, evicted_id={evicted_id}"
                )

                return {
                    "added_id": added_id,
                    "evicted_id": evicted_id,  # Optional[int]
                    "archived_id": archived_id,  # Optional[int]
                    "status": "success",
                }

            except Exception:
                # Rollback on ANY error
                conn.rollback()
                raise

    except ValueError as e:
        logger.error(f"Validation error in update_working_memory: {e}")
        return {
            "error": "Validation failed",
            "details": str(e),
            "tool": "update_working_memory",
        }
    except psycopg2.Error as e:
        logger.error(f"Database error in update_working_memory: {e}")
        return {
            "error": "Database operation failed",
            "details": str(e),
            "tool": "update_working_memory",
        }
    except Exception as e:
        logger.error(f"Unexpected error in update_working_memory: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "update_working_memory",
        }


async def add_episode(
    query: str, reward: float, reflection: str, conn: Any
) -> dict[str, Any]:
    """
    Store episode in database with embedding.

    Args:
        query: User query that triggered the episode
        reward: Reward score (-1.0 to 1.0)
        reflection: Verbalized lesson learned
        conn: Database connection

    Returns:
        Dictionary with episode ID, embedding status, and episode data
    """
    logger = logging.getLogger(__name__)

    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        raise RuntimeError("OpenAI API key not configured")

    client = OpenAI(api_key=api_key)

    # Get embedding for query (not reflection - query is used for similarity search)
    logger.info(f"Computing embedding for query: {query[:100]}...")
    try:
        embedding = await get_embedding_with_retry(client, query)
    except RuntimeError as e:
        logger.error(f"Failed to generate embedding after all retries: {e}")
        # Critical: embedding is required for retrieval, so we fail the entire operation
        raise RuntimeError(f"Embedding generation failed: {e}") from e

    # Register vector type for pgvector
    register_vector(conn)

    cursor = conn.cursor()

    # Insert episode with embedding
    cursor.execute(
        """
        INSERT INTO episode_memory (query, reward, reflection, embedding, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING id, created_at;
        """,
        (query, reward, reflection, embedding),
    )

    result = cursor.fetchone()
    episode_id = result["id"]
    created_at = result["created_at"]

    logger.info(f"Episode stored successfully with ID: {episode_id}")

    # CRITICAL: Explicit commit required - connection pool does NOT auto-commit
    conn.commit()

    return {
        "id": episode_id,
        "embedding_status": "success",
        "query": query,
        "reward": reward,
        "created_at": created_at.isoformat(),
    }


async def handle_store_episode(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Store episode memory with query, reward, and reflection.

    Args:
        arguments: Tool arguments containing query, reward, reflection

    Returns:
        Success response with episode ID or error response
    """
    logger = logging.getLogger(__name__)

    # Extract and validate parameters
    try:
        query = arguments["query"]
        reward = arguments["reward"]
        reflection = arguments["reflection"]
    except KeyError as e:
        return {
            "error": f"Missing required parameter: {e}",
            "details": f"Required parameters: query, reward, reflection. Missing: {e}",
            "tool": "store_episode",
            "embedding_status": "failed",
        }

    # Input validation
    if not isinstance(query, str) or not query.strip():
        return {
            "error": "Invalid query parameter",
            "details": "Query must be a non-empty string",
            "tool": "store_episode",
            "embedding_status": "failed",
        }

    if not isinstance(reflection, str) or not reflection.strip():
        return {
            "error": "Invalid reflection parameter",
            "details": "Reflection must be a non-empty string",
            "tool": "store_episode",
            "embedding_status": "failed",
        }

    if not isinstance(reward, int | float):
        return {
            "error": "Invalid reward parameter",
            "details": "Reward must be a number between -1.0 and 1.0",
            "tool": "store_episode",
            "embedding_status": "failed",
        }

    # Validate reward range BEFORE API call (save costs on invalid input)
    if reward < -1.0 or reward > 1.0:
        return {
            "error": "Reward out of range",
            "details": f"Reward {reward} is outside valid range [-1.0, 1.0]",
            "tool": "store_episode",
            "embedding_status": "failed",
        }

    # Store episode in database
    try:
        with get_connection() as conn:
            result = await add_episode(query, reward, reflection, conn)
            logger.info(f"Successfully stored episode with ID: {result['id']}")
            return result

    except RuntimeError as e:
        # Embedding or other critical failure
        logger.error(f"Episode storage failed: {e}")
        return {
            "error": "Episode storage failed",
            "details": str(e),
            "tool": "store_episode",
            "embedding_status": "failed",
        }

    except psycopg2.Error as e:
        # Database error
        logger.error(f"Database error storing episode: {e}")
        return {
            "error": "Database error",
            "details": f"Failed to store episode: {e}",
            "tool": "store_episode",
            "embedding_status": "failed",
        }

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error storing episode: {e}")
        return {
            "error": "Unexpected error",
            "details": f"Failed to store episode: {e}",
            "tool": "store_episode",
            "embedding_status": "failed",
        }


async def handle_store_dual_judge_scores(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Store dual judge evaluation scores using GPT-4o and Haiku for IRR validation.

    Evaluates documents with two independent judges and calculates Cohen's Kappa
    for methodologically valid ground truth creation.

    Args:
        arguments: Tool arguments containing:
            - query_id: int - Ground truth query ID
            - query: str - User query string
            - docs: list[dict] - Documents to evaluate with 'id' and 'content' keys

    Returns:
        Dictionary with judge scores, kappa calculation, and metadata
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract and validate parameters
        query_id = arguments.get("query_id")
        query = arguments.get("query")
        docs = arguments.get("docs")

        # Parameter validation
        if not isinstance(query_id, int) or query_id <= 0:
            return {
                "error": "Parameter validation failed",
                "details": "query_id must be a positive integer",
                "tool": "store_dual_judge_scores",
            }

        if not isinstance(query, str) or not query.strip():
            return {
                "error": "Parameter validation failed",
                "details": "query must be a non-empty string",
                "tool": "store_dual_judge_scores",
            }

        if not isinstance(docs, list) or len(docs) == 0:
            return {
                "error": "Parameter validation failed",
                "details": "docs must be a non-empty array of document objects",
                "tool": "store_dual_judge_scores",
            }

        # Validate document format
        for i, doc in enumerate(docs):
            if not isinstance(doc, dict):
                return {
                    "error": "Parameter validation failed",
                    "details": f"Document {i+1} must be an object with 'id' and 'content' keys",
                    "tool": "store_dual_judge_scores",
                }
            if "id" not in doc or "content" not in doc:
                return {
                    "error": "Parameter validation failed",
                    "details": f"Document {i+1} missing required 'id' or 'content' keys",
                    "tool": "store_dual_judge_scores",
                }
            if (
                not isinstance(doc.get("content"), str)
                or not doc.get("content").strip()
            ):
                return {
                    "error": "Parameter validation failed",
                    "details": f"Document {i+1} content must be a non-empty string",
                    "tool": "store_dual_judge_scores",
                }

        # Check API keys are configured
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if not openai_key or openai_key == "sk-your-openai-api-key-here":
            return {
                "error": "OpenAI API key not configured",
                "details": "OPENAI_API_KEY environment variable not set or contains placeholder value",
                "tool": "store_dual_judge_scores",
            }

        if not anthropic_key or anthropic_key == "sk-ant-your-anthropic-api-key-here":
            return {
                "error": "Anthropic API key not configured",
                "details": "ANTHROPIC_API_KEY environment variable not set or contains placeholder value",
                "tool": "store_dual_judge_scores",
            }

        # Initialize dual judge evaluator
        evaluator = DualJudgeEvaluator()

        # Evaluate documents
        logger.info(
            f"Starting dual judge evaluation for query_id={query_id}, {len(docs)} documents"
        )
        result = await evaluator.evaluate_documents(query_id, query, docs)

        logger.info(
            f"Dual judge evaluation completed: {result.get('status', 'unknown')}"
        )
        return result

    except RuntimeError as e:
        logger.error(f"Runtime error in dual judge evaluation: {e}")
        return {
            "error": "Dual judge evaluation failed",
            "details": str(e),
            "tool": "store_dual_judge_scores",
            "status": "failed",
        }

    except Exception as e:
        logger.error(f"Unexpected error in store_dual_judge_scores: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "store_dual_judge_scores",
            "status": "failed",
        }


async def handle_dissonance_check(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Handle dissonance check tool invocation.

    Args:
        arguments: Tool arguments containing context_node and optional scope

    Returns:
        Formatted dissonance check results
    """
    from mcp.server import Server

    # Extract parameters
    context_node = arguments.get("context_node")
    scope = arguments.get("scope", "recent")

    # Validate required parameters
    if not context_node or not isinstance(context_node, str):
        return {
            "error": "Parameter validation failed",
            "details": "context_node is required and must be a string",
            "tool": "dissonance_check",
        }

    if scope not in ["recent", "full"]:
        return {
            "error": "Parameter validation failed",
            "details": "scope must be 'recent' or 'full'",
            "tool": "dissonance_check",
        }

    # Create a server instance for the handler
    server = Server("cognitive-memory")

    # Call the actual handler
    results = await handle_dissonance_check_impl(server, context_node, scope)

    # Convert TextContent results to dict format
    if results and len(results) > 0:
        return {
            "result": results[0].text,
            "tool": "dissonance_check",
            "status": "success",
        }
    else:
        return {
            "error": "No results returned",
            "tool": "dissonance_check",
        }


async def handle_ping(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Simple ping tool for testing MCP connectivity.

    Args:
        arguments: Empty dict (no parameters required)

    Returns:
        Pong response for connectivity testing
    """
    return {
        "response": "pong",
        "timestamp": datetime.now(UTC).isoformat(),
        "tool": "ping",
        "status": "ok",
    }


def register_tools(server: Server) -> list[Tool]:
    """
    Register all MCP tools with the server.

    Args:
        server: MCP server instance

    Returns:
        List of registered tools
    """
    logger = logging.getLogger(__name__)

    # Tool definitions with JSON schemas for parameter validation
    tools = [
        Tool(
            name="store_raw_dialogue",
            description="Store raw dialogue data to L0 memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Unique identifier for the dialogue session",
                    },
                    "speaker": {
                        "type": "string",
                        "description": "Speaker identifier (user, assistant, etc.)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Dialogue content text",
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Additional metadata for the dialogue",
                    },
                },
                "required": ["session_id", "speaker", "content"],
            },
        ),
        Tool(
            name="compress_to_l2_insight",
            description="Compress dialogue data to L2 insight with OpenAI embedding and semantic fidelity check",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Compressed insight content to store with embedding",
                    },
                    "source_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Array of L0 raw memory IDs that were compressed into this insight",
                    },
                },
                "required": ["content", "source_ids"],
            },
        ),
        Tool(
            name="hybrid_search",
            description="Perform hybrid semantic + keyword search with RRF fusion. Embedding is generated automatically from query_text if not provided.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_text": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Query text for search (embedding generated automatically)",
                    },
                    "query_embedding": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 1536,
                        "maxItems": 1536,
                        "description": "Optional: 1536-dimensional query embedding (auto-generated from query_text if omitted)",
                    },
                    "top_k": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 5,
                        "description": "Maximum number of results to return",
                    },
                    "weights": {
                        "type": "object",
                        "properties": {
                            "semantic": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "default": 0.7,
                                "description": "Weight for semantic search results",
                            },
                            "keyword": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                                "default": 0.3,
                                "description": "Weight for keyword search results",
                            },
                        },
                        "default": {"semantic": 0.7, "keyword": 0.3},
                        "description": "Weights for fusing semantic and keyword results (must sum to 1.0)",
                    },
                },
                "required": ["query_text"],
            },
        ),
        Tool(
            name="update_working_memory",
            description="Add item to Working Memory with atomic eviction handling. Returns {added_id: int, evicted_id: Optional[int], archived_id: Optional[int]}",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Content to store in working memory",
                    },
                    "importance": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.5,
                        "description": "Importance score (0.0-1.0, default: 0.5)",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="store_episode",
            description="Store episode memory with query, reward, and reflection for verbal reinforcement learning",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "description": "User query that triggered the episode",
                    },
                    "reward": {
                        "type": "number",
                        "minimum": -1.0,
                        "maximum": 1.0,
                        "description": "Reward score from evaluation (-1.0=poor, +1.0=excellent)",
                    },
                    "reflection": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Verbalized lesson learned (format: 'Problem: ... Lesson: ...')",
                    },
                },
                "required": ["query", "reward", "reflection"],
            },
        ),
        Tool(
            name="store_dual_judge_scores",
            description="Store dual judge evaluation scores using GPT-4o and Haiku for IRR validation. Evaluates documents with two independent judges and calculates Cohen's Kappa for methodologically valid ground truth creation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Ground truth query ID (must exist in ground_truth table)",
                    },
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "description": "User query string for relevance evaluation",
                    },
                    "docs": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 50,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "integer",
                                    "description": "Document identifier",
                                },
                                "content": {
                                    "type": "string",
                                    "minLength": 1,
                                    "description": "Document content to evaluate for relevance",
                                },
                            },
                            "required": ["id", "content"],
                        },
                        "description": "Array of documents to evaluate with both judges",
                    },
                },
                "required": ["query_id", "query", "docs"],
            },
        ),
        Tool(
            name="get_golden_test_results",
            description="Execute Golden Test Set for daily Precision@5 tracking and model drift detection. Returns daily metrics and drift detection status.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="ping",
            description="Simple ping tool for testing connectivity",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="graph_add_node",
            description="Create or find a graph node with idempotent operation. Supports flexible metadata and optional vector linking to L2 insights.",
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Node type/category (e.g., 'Project', 'Technology', 'Client', 'Error', 'Solution')",
                    },
                    "name": {
                        "type": "string",
                        "description": "Unique name identifier for the node",
                    },
                    "properties": {
                        "type": "object",
                        "description": "Flexible metadata as key-value pairs",
                    },
                    "vector_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Optional foreign key to l2_insights.id for vector embedding linkage",
                    },
                },
                "required": ["label", "name"],
            },
        ),
        Tool(
            name="graph_add_edge",
            description="Create or update a relationship edge between graph nodes with auto-upsert of nodes. Supports standardized relations and optional weight scoring.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_name": {
                        "type": "string",
                        "description": "Name of source node (will be created if not exists)",
                    },
                    "target_name": {
                        "type": "string",
                        "description": "Name of target node (will be created if not exists)",
                    },
                    "relation": {
                        "type": "string",
                        "description": "Relationship type (e.g., 'USES', 'SOLVES', 'CREATED_BY', 'RELATED_TO', 'DEPENDS_ON')",
                    },
                    "source_label": {
                        "type": "string",
                        "description": "Label for source node if auto-created (default: 'Entity')",
                    },
                    "target_label": {
                        "type": "string",
                        "description": "Label for target node if auto-created (default: 'Entity')",
                    },
                    "weight": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Edge weight for relevance scoring (0.0-1.0, default: 1.0)",
                    },
                    "properties": {
                        "type": "object",
                        "description": "Flexible metadata as key-value pairs",
                    },
                },
                "required": ["source_name", "target_name", "relation"],
            },
        ),
        Tool(
            name="graph_query_neighbors",
            description="Find neighbor nodes of a given node with single-hop and multi-hop traversal. Supports filtering by relation type, depth-limited traversal, cycle detection, and bidirectional traversal (both/outgoing/incoming).",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the starting node to find neighbors for",
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Optional filter for specific relation types (e.g., 'USES', 'SOLVES', 'RELATED_TO')",
                    },
                    "depth": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 5,
                        "description": "Maximum traversal depth (1-5, default: 1)",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["both", "outgoing", "incoming"],
                        "description": "Traversal direction: 'both' (default) finds neighbors via incoming AND outgoing edges, 'outgoing' only follows edges where start node is source, 'incoming' only follows edges where start node is target",
                    },
                    "include_superseded": {
                        "type": "boolean",
                        "default": False,
                        "description": "If true, includes edges that have been superseded by EVOLUTION resolutions. Default: false (hide superseded)",
                    },
                },
                "required": ["node_name"],
            },
        ),
        Tool(
            name="graph_find_path",
            description="Find the shortest path between two nodes using BFS-based pathfinding with bidirectional traversal, cycle detection, and performance protection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "start_node": {
                        "type": "string",
                        "description": "Name of the starting node for pathfinding",
                    },
                    "end_node": {
                        "type": "string",
                        "description": "Name of the target node to find path to",
                    },
                    "max_depth": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                        "description": "Maximum traversal depth (1-10, default: 5)",
                    },
                },
                "required": ["start_node", "end_node"],
            },
        ),
        Tool(
            name="get_node_by_name",
            description="Retrieve a graph node by its unique name for write-then-verify operations. Returns node data if found, or graceful null response if not found (no exception).",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Unique name identifier of the node to retrieve",
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="get_edge",
            description="Retrieve a graph edge by source name, target name, and relation for write-then-verify operations. Returns edge data if found, or graceful null response if not found (no exception).",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Name of the source node",
                    },
                    "target_name": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Name of the target node",
                    },
                    "relation": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Relationship type (e.g., 'USES', 'SOLVES', 'CREATED_BY')",
                    },
                },
                "required": ["source_name", "target_name", "relation"],
            },
        ),
        Tool(
            name="count_by_type",
            description="Get counts of all memory types for audit and integrity checks. Returns counts for graph_nodes, graph_edges, l2_insights, episodes, working_memory, and raw_dialogues.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="list_episodes",
            description="List episode memory entries with pagination. Supports time filtering and offset-based pagination for audit purposes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of episodes to return (1-100, default: 50)",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 50,
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Number of episodes to skip (default: 0)",
                        "minimum": 0,
                        "default": 0,
                    },
                    "since": {
                        "type": "string",
                        "description": "ISO 8601 timestamp to filter episodes created after this time (optional)",
                        "format": "date-time",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_insight_by_id",
            description="Get a specific L2 insight by ID for spot verification. Returns content, source_ids, metadata, created_at. Does NOT return embedding (too large).",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "description": "L2 insight ID to retrieve",
                        "minimum": 1,
                    },
                },
                "required": ["id"],
            },
        ),
        DISSONANCE_CHECK_TOOL,
        RESOLVE_DISSONANCE_TOOL,
    ]

    # Tool handler mapping
    tool_handlers = {
        "store_raw_dialogue": handle_store_raw_dialogue,
        "compress_to_l2_insight": handle_compress_to_l2_insight,
        "hybrid_search": handle_hybrid_search,
        "update_working_memory": handle_update_working_memory,
        "store_episode": handle_store_episode,
        "store_dual_judge_scores": handle_store_dual_judge_scores,
        "get_golden_test_results": handle_get_golden_test_results,
        "ping": handle_ping,
        "graph_add_node": handle_graph_add_node,
        "graph_add_edge": handle_graph_add_edge,
        "graph_query_neighbors": handle_graph_query_neighbors,
        "graph_find_path": handle_graph_find_path,
        "get_node_by_name": handle_get_node_by_name,
        "get_edge": handle_get_edge,
        "count_by_type": handle_count_by_type,
        "list_episodes": handle_list_episodes,
        "get_insight_by_id": handle_get_insight_by_id,
        "dissonance_check": handle_dissonance_check,
        "resolve_dissonance": handle_resolve_dissonance,
    }

    # Register tool call handler (define once, outside the loop)
    @server.call_tool()  # type: ignore[misc]
    async def call_tool_handler(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Handle tool calls with parameter validation."""
        if name not in tool_handlers:
            raise ValueError(f"Unknown tool: {name}")

        # Find tool schema for validation
        tool_schema = next((t.inputSchema for t in tools if t.name == name), None)

        if tool_schema:
            try:
                validate_parameters(arguments, tool_schema)
            except ParameterValidationError as e:
                logger.error(f"Parameter validation failed for {name}: {e}")
                return {
                    "error": "Parameter validation failed",
                    "details": str(e),
                    "tool": name,
                }

        try:
            logger.info(
                f"Calling tool: {name} with arguments: {list(arguments.keys())}"
            )
            result = await tool_handlers[name](arguments)
            logger.info(f"Tool {name} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {
                "error": "Tool execution failed",
                "details": str(e),
                "tool": name,
            }

    logger.info(f"Registered {len(tools)} tools")
    return tools
