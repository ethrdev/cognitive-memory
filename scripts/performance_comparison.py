#!/usr/bin/env python3
"""
Performance Comparison Script for Story 11.8.3

Compares enforcing phase performance against Story 11.1.0 baseline to validate NFR2:
RLS overhead must be <10ms for hybrid_search and graph_query_neighbors.

Usage:
    python performance_comparison.py
    python performance_comparison.py --output comparison_report.json

Output:
    - Comparison report (stdout)
    - Optional JSON output file
    - Exit code: 0 (PASS), 1 (FAIL)

Story 11.8.3: Performance Validation (NFR2)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import get_connection_sync, initialize_pool
from mcp_server.tools import handle_hybrid_search
from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration (NFR2 from Epic 11)
# =============================================================================

# NFR2 Threshold: RLS overhead must be < 10ms
NFR2_THRESHOLD_MS = 10.0

# Measurement iterations
WARMUP_ITERATIONS = 5
MEASURED_ITERATIONS = 50

# Baseline file path (from Story 11.1.0)
BASELINE_FILE = Path("tests/performance/baseline_pre_rls.json")

# Output file for comparison report
DEFAULT_OUTPUT_FILE = Path("tests/performance/enforcing_comparison_report.json")


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

            if (i + 1) % 10 == 0:
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
        "mean_ms": round(sum(samples) / len(samples), 2),
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
        "samples": len(samples)
    }


# =============================================================================
# Query Measurements (Enforcing Phase)
# =============================================================================

async def measure_enforcing_hybrid_search() -> dict[str, Any]:
    """Measure hybrid_search performance with enforcing mode active."""
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
        "hybrid_search",
        run_hybrid_search
    )


async def measure_enforcing_graph_query_neighbors() -> dict[str, Any]:
    """Measure graph_query_neighbors performance with enforcing mode active."""
    # Get a test node
    with get_connection_sync() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM nodes LIMIT 1;")
        result = cursor.fetchone()

        if not result:
            logger.warning("No nodes found for graph_query measurement")
            return {
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "samples": 0,
                "skipped": True,
                "skip_reason": "No nodes found"
            }

        test_node = result["name"]

    async def run_graph_query():
        result = await handle_graph_query_neighbors({
            "node_name": test_node,
            "depth": 1
        })

        if result.get("error"):
            raise RuntimeError(f"Graph query failed: {result['error']}")

        return result

    return await measure_query_performance(
        "graph_query_neighbors",
        run_graph_query
    )


# =============================================================================
# Comparison Logic
# =============================================================================

def calculate_overhead(baseline_p99: float, enforcing_p99: float) -> float:
    """
    Calculate RLS overhead: (enforcing_p99 - baseline_p99)

    NFR2: FAIL if overhead > 10ms

    Args:
        baseline_p99: Baseline p99 latency in ms (from Story 11.1.0)
        enforcing_p99: Enforcing phase p99 latency in ms

    Returns:
        RLS overhead in milliseconds
    """
    return enforcing_p99 - baseline_p99


def compare_against_baseline(
    baseline_data: dict[str, Any],
    enforcing_measurements: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """
    Compare enforcing phase measurements against Story 11.1.0 baseline.

    Args:
        baseline_data: Loaded baseline JSON data from Story 11.1.0
        enforcing_measurements: Enforcing phase measurements

    Returns:
        Dict with comparison results and overall PASS/FAIL status
    """
    logger.info("=" * 70)
    logger.info("ENFORCING PHASE PERFORMANCE COMPARISON")
    logger.info("=" * 70)

    baselines = baseline_data.get("baselines", {})
    results = {}
    all_passed = True

    for query_name, enforcing in enforcing_measurements.items():
        baseline = baselines.get(query_name, {})

        if not baseline:
            logger.warning(f"No baseline found for {query_name}, skipping comparison")
            logger.warning(f"  This query has no baseline data - cannot measure RLS overhead")
            logger.warning(f"  Check if baseline was captured with the correct query name")
            results[query_name] = {
                "skipped": True,
                "skip_reason": "no_baseline",
                "passed": False  # No baseline means validation cannot complete
            }
            all_passed = False
            continue

        # Handle skipped measurements
        if enforcing.get("skipped") or baseline.get("skipped"):
            skip_reason = enforcing.get("skip_reason") or baseline.get("skip_reason") or "unknown"
            logger.info(f"\n{query_name}: ⏭️ SKIPPED ({skip_reason})")
            logger.info(f"  This is expected if external dependencies (e.g., OpenAI API) are not configured")
            logger.info(f"  NFR2 validation incomplete for this query - requires baseline measurement")
            results[query_name] = {
                "skipped": True,
                "skip_reason": skip_reason,
                "passed": False  # Skipped means validation incomplete
            }
            all_passed = False
            continue

        baseline_p99 = baseline.get("p99_ms", 0)
        enforcing_p99 = enforcing.get("p99_ms", 0)

        overhead = calculate_overhead(baseline_p99, enforcing_p99)
        passed = overhead <= NFR2_THRESHOLD_MS

        if not passed:
            all_passed = False

        results[query_name] = {
            "baseline_p99_ms": baseline_p99,
            "enforcing_p99_ms": enforcing_p99,
            "overhead_ms": round(overhead, 2),
            "threshold_ms": NFR2_THRESHOLD_MS,
            "passed": passed,
            "enforcing_stats": {
                "p50_ms": enforcing.get("p50_ms", 0),
                "p95_ms": enforcing.get("p95_ms", 0),
                "mean_ms": enforcing.get("mean_ms", 0),
                "min_ms": enforcing.get("min_ms", 0),
                "max_ms": enforcing.get("max_ms", 0),
            }
        }

        # Log result
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"\n{query_name}:")
        logger.info(f"  Baseline p99: {baseline_p99:.2f}ms")
        logger.info(f"  Enforcing p99: {enforcing_p99:.2f}ms")
        logger.info(f"  RLS Overhead: {overhead:.2f}ms")
        logger.info(f"  NFR2 Threshold: <{NFR2_THRESHOLD_MS}ms")
        logger.info(f"  Status: {status}")

    logger.info("=" * 70)

    return {
        "results": results,
        "overall_passed": all_passed,
        "nfr2_threshold_ms": NFR2_THRESHOLD_MS,
        "timestamp": datetime.now(UTC).isoformat()
    }


def generate_comparison_report(
    comparison: dict[str, Any],
    output_file: Path | None = None
) -> None:
    """Generate human-readable comparison report."""
    logger.info("\nENFORCING PHASE COMPARISON REPORT")
    logger.info("=" * 70)

    for query_name, result in comparison["results"].items():
        if result.get("skipped"):
            skip_reason = result.get("skip_reason", "unknown")
            if skip_reason == "no_baseline":
                logger.warning(f"\n{query_name}: ⚠️ NO BASELINE")
                logger.warning(f"  Cannot measure RLS overhead - baseline data missing")
            else:
                logger.info(f"\n{query_name}: ⏭️ SKIPPED ({skip_reason})")
            continue

        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        logger.info(f"\n{query_name}: {status}")
        logger.info(f"  RLS Overhead: {result['overhead_ms']:.2f}ms (threshold: <{result['threshold_ms']}ms)")
        logger.info(f"  Baseline: {result['baseline_p99_ms']:.2f}ms → Enforcing: {result['enforcing_p99_ms']:.2f}ms")

        if "enforcing_stats" in result:
            stats = result["enforcing_stats"]
            logger.info(f"  Enforcing Stats: p50={stats['p50_ms']:.2f}ms, p95={stats['p95_ms']:.2f}ms, mean={stats['mean_ms']:.2f}ms")

    logger.info("\n" + "=" * 70)

    # Check if there are any skipped or missing baselines
    skipped_count = sum(1 for r in comparison["results"].values() if r.get("skipped"))
    missing_baselines = sum(1 for r in comparison["results"].values() if r.get("skipped") and r.get("skip_reason") == "no_baseline")

    if comparison["overall_passed"]:
        logger.info("✅ OVERALL: PASS - RLS overhead within NFR2 threshold")
        if skipped_count > 0:
            logger.warning(f"⚠️  Note: {skipped_count} queries skipped due to missing baselines")
            logger.warning("   NFR2 validation incomplete - configure required dependencies")
        logger.info("=" * 70)
    else:
        logger.error("❌ OVERALL: FAIL - RLS overhead exceeds NFR2 threshold")
        if missing_baselines > 0:
            logger.error(f"⚠️  {missing_baselines} queries have no baseline - cannot validate")
            logger.error("   Check baseline capture in Story 11.1.0")
        logger.error("NFR2: RLS policy evaluation must add <10ms to query latency")
        logger.error("=" * 70)

    # Write JSON output if requested
    if output_file:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(comparison, f, indent=2)
        logger.info(f"\nReport saved to: {output_file}")


# =============================================================================
# Main Entry Point
# =============================================================================

async def main_async(output_file: Path | None = None) -> int:
    """Main async entry point."""
    logger.info("=" * 70)
    logger.info("PERFORMANCE COMPARISON - Story 11.8.3 (NFR2 Validation)")
    logger.info("=" * 70)

    # Initialize connection pool
    try:
        await initialize_pool()
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        return 1

    # Load baseline from Story 11.1.0
    if not BASELINE_FILE.exists():
        logger.error(f"Baseline file not found: {BASELINE_FILE}")
        logger.error("=" * 70)
        logger.error("PERFORMANCE COMPARISON CANNOT RUN")
        logger.error("=" * 70)
        logger.error("Solution 1: Run Story 11.1.0 baseline capture:")
        logger.error("  python tests/performance/capture_baseline.py")
        logger.error("")
        logger.error("Solution 2: Check if baseline file location is correct")
        logger.error(f"  Expected location: {BASELINE_FILE}")
        logger.error("")
        logger.error("Solution 3: Skip performance validation for now")
        logger.error("  (Not recommended - NFR2 validation will be incomplete)")
        logger.error("=" * 70)
        return 1

    with open(BASELINE_FILE) as f:
        baseline_data = json.load(f)

    baseline_metadata = baseline_data.get("metadata", {})
    logger.info(f"Baseline timestamp: {baseline_metadata.get('timestamp')}")
    logger.info(f"Baseline PostgreSQL: {baseline_metadata.get('postgres_version')}")

    # Measure enforcing phase performance
    logger.info("\nMeasuring enforcing phase performance...")
    enforcing_measurements: dict[str, dict[str, Any]] = {}

    try:
        enforcing_measurements["hybrid_search_semantic_top10"] = await measure_enforcing_hybrid_search()
        enforcing_measurements["graph_query_neighbors_1hop"] = await measure_enforcing_graph_query_neighbors()

    except Exception as e:
        logger.error(f"Failed to measure enforcing performance: {e}")
        return 1

    # Compare against baseline
    comparison = compare_against_baseline(baseline_data, enforcing_measurements)

    # Generate report
    generate_comparison_report(comparison, output_file)

    return 0 if comparison["overall_passed"] else 1


def main() -> int:
    """Main entry point for script."""
    output_file = None

    # Simple argument parsing
    if len(sys.argv) > 1:
        if sys.argv[1] in ["-h", "--help"]:
            print("Usage: python performance_comparison.py [--output comparison_report.json]")
            return 0
        elif sys.argv[1] == "--output" and len(sys.argv) > 2:
            output_file = Path(sys.argv[2])
        else:
            output_file = DEFAULT_OUTPUT_FILE

    try:
        return asyncio.run(main_async(output_file))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
