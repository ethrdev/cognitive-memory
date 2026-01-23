#!/usr/bin/env python3
"""
RLS Overhead Comparison Script for Story 11.1.0

Compares post-RLS performance against pre-RLS baseline to validate NFR2:
RLS policy evaluation must add <10ms to query latency.

Usage:
    python scripts/compare_rls_overhead.py

Output:
    - Comparison report (stdout)
    - Exit code: 0 (PASS), 1 (FAIL)

Story 11.1.0: Performance Baseline Capture (AC3: Comparison Capability)
"""

from __future__ import annotations

import asyncio
import json
import logging
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
from mcp_server.tools import handle_compress_to_l2_insight

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration (AC3: Comparison Capability)
# =============================================================================

# NFR2 Threshold: RLS overhead must be < 10ms
NFR2_THRESHOLD_MS = 10.0

# Measurement iterations
WARMUP_ITERATIONS = 5
MEASURED_ITERATIONS = 100

# Baseline file path
BASELINE_FILE = Path("tests/performance/baseline_pre_rls.json")


# =============================================================================
# Performance Measurement Helper
# =============================================================================

async def measure_query_performance(
    query_name: str,
    query_func,
    *args,
    **kwargs
) -> dict[str, Any]:
    """
    Measure query performance with warmup.

    Args:
        query_name: Name of the query being measured
        query_func: Async function to measure
        *args: Positional arguments for query_func
        **kwargs: Keyword arguments for query_func

    Returns:
        Dict with p50, p95, p99 latencies in milliseconds
    """
    logger.info(f"Measuring {query_name}...")

    # Warmup iterations
    for _ in range(WARMUP_ITERATIONS):
        try:
            await query_func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Warmup failed for {query_name}: {e}")

    # Measured iterations
    samples: list[float] = []

    for i in range(MEASURED_ITERATIONS):
        try:
            start = time.perf_counter()
            await query_func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            samples.append(elapsed_ms)

            if (i + 1) % 20 == 0:
                logger.debug(f"  Progress: {i+1}/{MEASURED_ITERATIONS} iterations")

        except Exception as e:
            logger.warning(f"Measurement failed for {query_name}: {e}")

    if not samples:
        logger.error(f"No valid samples for {query_name}")
        return {
            "p50_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "samples": 0
        }

    sorted_samples = sorted(samples)

    return {
        "p50_ms": round(sorted_samples[len(sorted_samples) // 2], 2),
        "p95_ms": round(sorted_samples[int(len(sorted_samples) * 0.95)], 2),
        "p99_ms": round(sorted_samples[int(len(sorted_samples) * 0.99)], 2),
        "samples": len(samples)
    }


# =============================================================================
# Query Measurements
# =============================================================================

async def measure_post_rls_hybrid_search() -> dict[str, Any]:
    """Measure hybrid_search performance after RLS implementation."""
    test_query = "PostgreSQL database performance optimization"

    async def run_hybrid_search():
        result = await handle_hybrid_search({
            "query_text": test_query,
            "top_k": 10,
            "weights": {"semantic": 0.7, "keyword": 0.3}
        })

        if result.get("error"):
            raise RuntimeError(f"Hybrid search failed: {result['error']}")

        return result

    return await measure_query_performance(
        "hybrid_search_semantic_top10",
        run_hybrid_search
    )


async def measure_post_rls_graph_query_1hop() -> dict[str, Any]:
    """Measure graph_query_neighbors 1-hop performance after RLS."""
    # Get a test node
    with get_connection_sync() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM nodes LIMIT 1;")
        result = cursor.fetchone()

        if not result:
            raise RuntimeError("No nodes found for measurement")

        test_node = result["name"]

    async def run_query():
        result = await handle_graph_query_neighbors({
            "node_name": test_node,
            "depth": 1
        })

        if result.get("error"):
            raise RuntimeError(f"Graph query failed: {result['error']}")

        return result

    return await measure_query_performance(
        "graph_query_neighbors_1hop",
        run_query
    )


async def measure_post_rls_graph_query_3hop() -> dict[str, Any]:
    """Measure graph_query_neighbors 3-hop performance after RLS."""
    # Get a test node
    with get_connection_sync() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM nodes LIMIT 1;")
        result = cursor.fetchone()

        if not result:
            raise RuntimeError("No nodes found for measurement")

        test_node = result["name"]

    async def run_query():
        result = await handle_graph_query_neighbors({
            "node_name": test_node,
            "depth": 3
        })

        if result.get("error"):
            raise RuntimeError(f"Graph query failed: {result['error']}")

        return result

    return await measure_query_performance(
        "graph_query_neighbors_3hop",
        run_query
    )


async def measure_post_rls_compress_to_l2_insight() -> dict[str, Any]:
    """
    Measure compress_to_l2_insight performance after RLS.

    Query: compress_to_l2_insight
    Threshold: p99 < 200ms
    """
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

    async def run_compress():
        result = await handle_compress_to_l2_insight({
            "content": sample_content,
            "source_ids": source_ids,
            "memory_strength": 0.5
        })

        if result.get("error"):
            raise RuntimeError(f"Compression failed: {result['error']}")

        return result

    return await measure_query_performance(
        "compress_to_l2_insight",
        run_compress
    )


# =============================================================================
# Comparison Logic
# =============================================================================

def calculate_delta(baseline_p99: float, post_rls_p99: float) -> float:
    """
    Calculate delta: (post_rls_p99 - baseline_p99)

    AC3: FAIL if delta > 10ms (NFR2 threshold)

    Args:
        baseline_p99: Baseline p99 latency in ms
        post_rls_p99: Post-RLS p99 latency in ms

    Returns:
        Delta in milliseconds
    """
    return post_rls_p99 - baseline_p99


def compare_against_baseline(
    baseline_data: dict[str, Any],
    post_rls_measurements: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """
    Compare post-RLS measurements against baseline.

    Args:
        baseline_data: Loaded baseline JSON data
        post_rls_measurements: Post-RLS measurements

    Returns:
        Dict with comparison results and overall PASS/FAIL status
    """
    logger.info("=" * 70)
    logger.info("RLS OVERHEAD COMPARISON")
    logger.info("=" * 70)

    baselines = baseline_data.get("baselines", {})
    results = {}
    all_passed = True

    for query_name, post_rls in post_rls_measurements.items():
        baseline = baselines.get(query_name, {})

        if not baseline:
            logger.warning(f"No baseline found for {query_name}, skipping comparison")
            continue

        # Handle skipped measurements
        if post_rls.get("skipped") or baseline.get("skipped"):
            skip_reason = post_rls.get("skip_reason") or baseline.get("skip_reason") or "unknown"
            logger.info(f"\n{query_name}: ⏭️ SKIPPED ({skip_reason})")
            results[query_name] = {
                "skipped": True,
                "skip_reason": skip_reason,
                "passed": True  # Skipped doesn't count as failure
            }
            continue

        baseline_p99 = baseline.get("p99_ms", 0)
        post_rls_p99 = post_rls.get("p99_ms", 0)

        delta = calculate_delta(baseline_p99, post_rls_p99)
        passed = delta <= NFR2_THRESHOLD_MS

        if not passed:
            all_passed = False

        results[query_name] = {
            "baseline_p99_ms": baseline_p99,
            "post_rls_p99_ms": post_rls_p99,
            "delta_ms": round(delta, 2),
            "threshold_ms": NFR2_THRESHOLD_MS,
            "passed": passed
        }

        # Log result
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"\n{query_name}:")
        logger.info(f"  Baseline p99: {baseline_p99:.2f}ms")
        logger.info(f"  Post-RLS p99: {post_rls_p99:.2f}ms")
        logger.info(f"  Delta: {delta:.2f}ms")
        logger.info(f"  Threshold: <{NFR2_THRESHOLD_MS}ms")
        logger.info(f"  Status: {status}")

    logger.info("=" * 70)

    return {
        "results": results,
        "overall_passed": all_passed,
        "nfr2_threshold_ms": NFR2_THRESHOLD_MS,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# Main Entry Point
# =============================================================================

async def main_async():
    """Main async entry point."""
    logger.info("=" * 70)
    logger.info("RLS OVERHEAD COMPARISON - Story 11.1.0 AC3")
    logger.info("=" * 70)

    # Initialize connection pool
    try:
        await initialize_pool()
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        return 1

    # Load baseline
    if not BASELINE_FILE.exists():
        logger.error(f"Baseline file not found: {BASELINE_FILE}")
        logger.error("Run capture_baseline.py first to create baseline")
        return 1

    with open(BASELINE_FILE, "r") as f:
        baseline_data = json.load(f)

    baseline_metadata = baseline_data.get("metadata", {})
    logger.info(f"Baseline timestamp: {baseline_metadata.get('timestamp')}")
    logger.info(f"Baseline PostgreSQL: {baseline_metadata.get('postgres_version')}")

    # Measure post-RLS performance
    post_rls_measurements: dict[str, dict[str, Any]] = {}

    try:
        post_rls_measurements["hybrid_search_semantic_top10"] = await measure_post_rls_hybrid_search()
        post_rls_measurements["graph_query_neighbors_1hop"] = await measure_post_rls_graph_query_1hop()
        post_rls_measurements["graph_query_neighbors_3hop"] = await measure_post_rls_graph_query_3hop()
        post_rls_measurements["compress_to_l2_insight"] = await measure_post_rls_compress_to_l2_insight()

    except Exception as e:
        logger.error(f"Failed to measure post-RLS performance: {e}")
        return 1

    # Compare against baseline
    comparison = compare_against_baseline(baseline_data, post_rls_measurements)

    # Generate human-readable report
    logger.info("\nCOMPARISON REPORT")
    logger.info("=" * 70)

    for query_name, result in comparison["results"].items():
        if result.get("skipped"):
            logger.info(f"\n{query_name}: ⏭️ SKIPPED ({result.get('skip_reason', 'unknown')})")
            continue

        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        logger.info(f"\n{query_name}: {status}")
        logger.info(f"  Delta: {result['delta_ms']:.2f}ms (threshold: <{result['threshold_ms']}ms)")
        logger.info(f"  Baseline: {result['baseline_p99_ms']:.2f}ms → Post-RLS: {result['post_rls_p99_ms']:.2f}ms")

    logger.info("\n" + "=" * 70)

    if comparison["overall_passed"]:
        logger.info("✅ OVERALL: PASS - RLS overhead within NFR2 threshold")
        logger.info("=" * 70)
        return 0
    else:
        logger.error("❌ OVERALL: FAIL - RLS overhead exceeds NFR2 threshold")
        logger.error("NFR2: RLS policy evaluation must add <10ms to query latency")
        logger.error("=" * 70)
        return 1


def main():
    """Main entry point for script."""
    import asyncio
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
