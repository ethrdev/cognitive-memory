#!/usr/bin/env python3
"""
Baseline Capture Script for Story 11.1.0

Captures performance baselines for all critical queries before RLS implementation:
- hybrid_search (semantic, top_k=10)
- graph_query_neighbors (1-hop and 3-hop)
- compress_to_l2_insight

Usage:
    python scripts/capture_baseline.py

Output:
    tests/performance/baseline_pre_rls.json

Story 11.1.0: Performance Baseline Capture (AC2: Baseline Capture Execution)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import initialize_pool, get_connection_sync
from mcp_server.tools import handle_hybrid_search
from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration (AC2: Baseline Capture Execution)
# =============================================================================

# Number of warmup iterations (discarded)
WARMUP_ITERATIONS = 5

# Number of measured iterations
MEASURED_ITERATIONS = 100

# Output path
OUTPUT_DIR = Path("tests/performance")
OUTPUT_FILE = OUTPUT_DIR / "baseline_pre_rls.json"

# Baseline schema (AC2, JSON validation)
BASELINE_SCHEMA = {
    "type": "object",
    "properties": {
        "metadata": {
            "type": "object",
            "properties": {
                "timestamp": {"type": "string"},
                "postgres_version": {"type": "string"},
                "hardware_info": {
                    "type": "object",
                    "properties": {
                        "cpu_count": {"type": "integer"},
                        "platform": {"type": "string"},
                        "python_version": {"type": "string"}
                    }
                },
                "row_counts": {
                    "type": "object",
                    "properties": {
                        "nodes": {"type": "integer"},
                        "edges": {"type": "integer"},
                        "l2_insights": {"type": "integer"}
                    }
                }
            },
            "required": ["timestamp", "postgres_version", "hardware_info", "row_counts"]
        },
        "baselines": {
            "type": "object",
            "patternProperties": {
                ".*": {
                    "type": "object",
                    "properties": {
                        "p50_ms": {"type": "number"},
                        "p95_ms": {"type": "number"},
                        "p99_ms": {"type": "number"},
                        "samples": {"type": "integer"}
                    },
                    "required": ["p50_ms", "p95_ms", "p99_ms", "samples"]
                }
            }
        }
    },
    "required": ["metadata", "baselines"]
}


# =============================================================================
# Performance Measurement Helper
# =============================================================================

class PerformanceMeasurement:
    """
    Performance measurement helper following LatencyBenchmark pattern.

    Reuses concepts from mcp_server/benchmarking/latency_benchmark.py
    """

    def __init__(self, name: str, warmup: int = WARMUP_ITERATIONS, iterations: int = MEASURED_ITERATIONS):
        self.name = name
        self.warmup = warmup
        self.iterations = iterations
        self.samples: list[float] = []

    async def measure(self, func, *args, **kwargs) -> dict[str, Any]:
        """
        Measure function execution time with warmup.

        Args:
            func: Async function to measure
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Dict with p50, p95, p99 latencies in milliseconds
        """
        logger.info(f"Measuring {self.name}...")

        # Warmup iterations (discarded)
        for i in range(self.warmup):
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Warmup iteration {i+1} failed: {e}")

        # Measured iterations
        self.samples = []

        for i in range(self.iterations):
            try:
                start = time.perf_counter()

                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    func(*args, **kwargs)

                elapsed_ms = (time.perf_counter() - start) * 1000
                self.samples.append(elapsed_ms)

                if (i + 1) % 20 == 0:
                    logger.debug(f"  Progress: {i+1}/{self.iterations} iterations")

            except Exception as e:
                logger.warning(f"Measured iteration {i+1} failed: {e}")

        # Calculate percentiles
        if not self.samples:
            logger.error(f"No valid samples for {self.name}")
            return {
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "samples": 0
            }

        sorted_samples = sorted(self.samples)

        return {
            "p50_ms": round(sorted_samples[len(sorted_samples) // 2], 2),
            "p95_ms": round(sorted_samples[int(len(sorted_samples) * 0.95)], 2),
            "p99_ms": round(sorted_samples[int(len(sorted_samples) * 0.99)], 2),
            "samples": len(self.samples)
        }


# =============================================================================
# Metadata Collection
# =============================================================================

def get_postgres_version() -> str:
    """
    Get PostgreSQL version for metadata (Task 2.4).

    Returns:
        Version string (e.g., "PostgreSQL 15.4")
    """
    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            result = cursor.fetchone()

            # Extract "PostgreSQL 15.4" from full string
            # Format: "PostgreSQL 15.4 on x86_64-pc-linux-gnu..."
            version_str = result["version"]
            parts = version_str.split()
            if len(parts) >= 3:
                return f"{parts[0]} {parts[1].split(',')[0]}"

            return version_str

    except Exception as e:
        logger.error(f"Failed to get PostgreSQL version: {e}")
        return "Unknown"


def get_hardware_info() -> dict[str, Any]:
    """Collect hardware information for metadata."""
    return {
        "cpu_count": os.cpu_count(),
        "platform": platform.platform(),
        "python_version": platform.python_version()
    }


def get_row_counts() -> dict[str, int]:
    """Get current row counts for metadata."""
    counts = {
        "nodes": 0,
        "edges": 0,
        "l2_insights": 0
    }

    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            # Count nodes
            cursor.execute("SELECT COUNT(*) as count FROM nodes")
            counts["nodes"] = cursor.fetchone()["count"]

            # Count edges
            cursor.execute("SELECT COUNT(*) as count FROM edges")
            counts["edges"] = cursor.fetchone()["count"]

            # Count L2 insights
            cursor.execute("SELECT COUNT(*) as count FROM l2_insights")
            counts["l2_insights"] = cursor.fetchone()["count"]

    except Exception as e:
        logger.error(f"Failed to get row counts: {e}")

    return counts


def get_metadata() -> dict[str, Any]:
    """Collect complete metadata for baseline."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "postgres_version": get_postgres_version(),
        "hardware_info": get_hardware_info(),
        "row_counts": get_row_counts()
    }


# =============================================================================
# Baseline Measurements
# =============================================================================

async def measure_hybrid_search() -> dict[str, Any]:
    """
    Measure hybrid_search performance (AC2).

    Query: hybrid_search (semantic, top_k=10)
    Threshold: p99 < 500ms
    """
    logger.info("Measuring hybrid_search baseline...")

    measurer = PerformanceMeasurement("hybrid_search_semantic_top10")

    # Test query for semantic search
    test_query = "PostgreSQL database performance optimization"

    # Create a simple measurement wrapper
    async def run_hybrid_search():
        result = await handle_hybrid_search({
            "query_text": test_query,
            "top_k": 10,
            "weights": {"semantic": 0.7, "keyword": 0.3}
        })

        if result.get("error"):
            raise RuntimeError(f"Hybrid search failed: {result['error']}")

        return result

    return await measurer.measure(run_hybrid_search)


async def measure_graph_query_neighbors_1hop() -> dict[str, Any]:
    """
    Measure graph_query_neighbors 1-hop performance (AC2).

    Query: graph_query_neighbors (1-hop)
    Threshold: p99 < 100ms
    """
    logger.info("Measuring graph_query_neighbors 1-hop baseline...")

    # First, get a test node
    with get_connection_sync() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM nodes LIMIT 1;"
        )
        result = cursor.fetchone()

        if not result:
            raise RuntimeError("No nodes found for graph query measurement")

        test_node = result["name"]

    measurer = PerformanceMeasurement("graph_query_neighbors_1hop")

    async def run_1hop_query():
        result = await handle_graph_query_neighbors({
            "node_name": test_node,
            "depth": 1
        })

        if result.get("error"):
            raise RuntimeError(f"Graph query failed: {result['error']}")

        return result

    return await measurer.measure(run_1hop_query)


async def measure_graph_query_neighbors_3hop() -> dict[str, Any]:
    """
    Measure graph_query_neighbors 3-hop performance (AC2).

    Query: graph_query_neighbors (3-hop)
    Threshold: p99 < 300ms
    """
    logger.info("Measuring graph_query_neighbors 3-hop baseline...")

    # First, get a test node
    with get_connection_sync() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM nodes LIMIT 1;"
        )
        result = cursor.fetchone()

        if not result:
            raise RuntimeError("No nodes found for graph query measurement")

        test_node = result["name"]

    measurer = PerformanceMeasurement("graph_query_neighbors_3hop")

    async def run_3hop_query():
        result = await handle_graph_query_neighbors({
            "node_name": test_node,
            "depth": 3
        })

        if result.get("error"):
            raise RuntimeError(f"Graph query failed: {result['error']}")

        return result

    return await measurer.measure(run_3hop_query)


async def measure_compress_to_l2_insight() -> dict[str, Any]:
    """
    Measure compress_to_l2_insight performance (AC2).

    Query: compress_to_l2_insight
    Threshold: p99 < 200ms
    """
    logger.info("Measuring compress_to_l2_insight baseline...")

    # Get sample dialogues for compression
    with get_connection_sync() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, content
            FROM raw_dialogues
            ORDER BY RANDOM()
            LIMIT 5;
            """
        )
        results = cursor.fetchall()

        if not results or len(results) < 5:
            logger.warning("Insufficient raw dialogues for compression measurement - SKIPPED")
            # Return skipped baseline to indicate this measurement wasn't performed
            return {
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "samples": 0,
                "skipped": True,
                "skip_reason": "Insufficient raw_dialogues (need at least 5)"
            }

        source_ids = [str(row["id"]) for row in results]
        sample_content = "\n".join([row["content"] for row in results])

    measurer = PerformanceMeasurement("compress_to_l2_insight")

    async def run_compress():
        # Import here to avoid circular dependency
        from mcp_server.tools import handle_compress_to_l2_insight

        result = await handle_compress_to_l2_insight({
            "content": sample_content,
            "source_ids": source_ids,
            "memory_strength": 0.5
        })

        if result.get("error"):
            raise RuntimeError(f"Compression failed: {result['error']}")

        return result

    return await measurer.measure(run_compress)


# =============================================================================
# JSON Validation
# =============================================================================

def validate_baseline_json(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate baseline JSON against schema (Task 4.4).

    Args:
        data: Baseline data to validate

    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []

    # Check required top-level keys
    if "metadata" not in data:
        errors.append("Missing required key: metadata")
    if "baselines" not in data:
        errors.append("Missing required key: baselines")

    # Validate metadata
    metadata = data.get("metadata", {})
    required_metadata_keys = ["timestamp", "postgres_version", "hardware_info", "row_counts"]
    for key in required_metadata_keys:
        if key not in metadata:
            errors.append(f"Missing required metadata key: {key}")

    # Validate baselines
    baselines = data.get("baselines", {})
    required_baseline_keys = ["p50_ms", "p95_ms", "p99_ms", "samples"]

    for query_name, baseline in baselines.items():
        for key in required_baseline_keys:
            if key not in baseline:
                errors.append(f"Missing required baseline key for {query_name}: {key}")

        # Validate data types
        if "p50_ms" in baseline and not isinstance(baseline["p50_ms"], (int, float)):
            errors.append(f"Invalid type for {query_name}.p50_ms: expected number")
        if "p95_ms" in baseline and not isinstance(baseline["p95_ms"], (int, float)):
            errors.append(f"Invalid type for {query_name}.p95_ms: expected number")
        if "p99_ms" in baseline and not isinstance(baseline["p99_ms"], (int, float)):
            errors.append(f"Invalid type for {query_name}.p99_ms: expected number")
        if "samples" in baseline and not isinstance(baseline["samples"], int):
            errors.append(f"Invalid type for {query_name}.samples: expected int")

    return len(errors) == 0, errors


# =============================================================================
# Main Entry Point
# =============================================================================

async def main_async():
    """Main async entry point."""
    logger.info("=" * 70)
    logger.info("BASELINE CAPTURE - Story 11.1.0 AC2")
    logger.info("=" * 70)

    # Initialize connection pool
    try:
        await initialize_pool()
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        return 1

    # Collect metadata
    logger.info("Collecting metadata...")
    metadata = get_metadata()
    logger.info(f"  PostgreSQL: {metadata['postgres_version']}")
    logger.info(f"  CPU Count: {metadata['hardware_info']['cpu_count']}")
    logger.info(f"  Row Counts: nodes={metadata['row_counts']['nodes']}, "
                f"edges={metadata['row_counts']['edges']}, "
                f"insights={metadata['row_counts']['l2_insights']}")

    # Measure all queries
    baselines: dict[str, dict[str, Any]] = {}

    try:
        # AC2: Measure hybrid_search
        baselines["hybrid_search_semantic_top10"] = await measure_hybrid_search()

        # AC2: Measure graph_query_neighbors 1-hop
        baselines["graph_query_neighbors_1hop"] = await measure_graph_query_neighbors_1hop()

        # AC2: Measure graph_query_neighbors 3-hop
        baselines["graph_query_neighbors_3hop"] = await measure_graph_query_neighbors_3hop()

        # AC2: Measure compress_to_l2_insight
        baselines["compress_to_l2_insight"] = await measure_compress_to_l2_insight()

    except Exception as e:
        logger.error(f"Failed to measure baselines: {e}")
        return 1

    # Build baseline data
    baseline_data = {
        "metadata": metadata,
        "baselines": baselines
    }

    # Validate JSON
    is_valid, errors = validate_baseline_json(baseline_data)

    if not is_valid:
        logger.error("JSON validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        return 1

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Write baseline file
    with open(OUTPUT_FILE, "w") as f:
        json.dump(baseline_data, f, indent=2)

    logger.info(f"Baseline saved to: {OUTPUT_FILE}")

    # Report summary
    logger.info("=" * 70)
    logger.info("BASELINE SUMMARY")
    logger.info("=" * 70)

    for query_name, baseline in baselines.items():
        if baseline.get("skipped"):
            logger.info(f"{query_name}: SKIPPED ({baseline.get('skip_reason', 'unknown')})")
        else:
            logger.info(f"{query_name}:")
            logger.info(f"  p50: {baseline['p50_ms']:.2f}ms")
            logger.info(f"  p95: {baseline['p95_ms']:.2f}ms")
            logger.info(f"  p99: {baseline['p99_ms']:.2f}ms")
            logger.info(f"  samples: {baseline['samples']}")

    logger.info("=" * 70)
    logger.info("BASELINE CAPTURE COMPLETE")
    logger.info("=" * 70)

    return 0


def main():
    """Main entry point for script."""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
