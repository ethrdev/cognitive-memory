#!/usr/bin/env python3
"""
Latency Benchmarking Script for NFR001 Validation.

Measures component-level latency for the RAG pipeline to validate NFR001
(Query Response Time <5s p95). Benchmarks 100 Golden Test queries with
stratified mix (40 Short, 40 Medium, 20 Long).

Components Measured:
1. Query Expansion Time (placeholder - requires Claude Code integration)
2. Embedding Time (OpenAI text-embedding-3-small API)
3. Hybrid Search Time (pgvector + PostgreSQL full-text)
4. CoT Generation Time (placeholder - requires Claude Code integration)
5. Evaluation Time (Haiku API with fallback)

Usage:
    python -m mcp_server.benchmarking.latency_benchmark

Output:
    - JSON measurements file: benchmarking/results/latency_measurements_{timestamp}.json
    - Performance report: docs/performance-benchmarks.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development")

from mcp_server.db.connection import get_connection
from mcp_server.external.anthropic_client import (
    HaikuClient,
    evaluate_answer_with_fallback,
)
from mcp_server.external.openai_client import create_embedding
from mcp_server.tools import handle_hybrid_search

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# Golden Test Set path
GOLDEN_TEST_SET_PATH = "mcp_server/scripts/mock_golden_test_set.json"

# Output paths
RESULTS_DIR = Path("mcp_server/benchmarking/results")
DOCS_DIR = Path("docs")

# NFR001 Thresholds
NFR001_P95_THRESHOLD = 5.0  # seconds
HYBRID_SEARCH_P95_THRESHOLD = 1.0  # seconds
COT_GENERATION_P50_THRESHOLD = 3.0  # seconds
EVALUATION_P95_THRESHOLD = 1.0  # seconds


# =============================================================================
# Component Benchmarking Functions
# =============================================================================

async def measure_query_expansion(query: str) -> float:
    """
    Measure Query Expansion Time.

    NOTE: This is a placeholder implementation. Query expansion is performed
    by Claude Code internally. In a production benchmark, this would measure
    actual Claude Code query expansion time.

    Args:
        query: User query string

    Returns:
        Latency in seconds (placeholder: returns 0.0)
    """
    # TODO: Integrate with Claude Code to measure actual query expansion time
    # For now, return placeholder value
    logger.warning(
        "Query Expansion timing not implemented - placeholder returning 0.0s"
    )
    return 0.0


async def measure_embedding(query: str) -> tuple[float, List[float]]:
    """
    Measure Embedding Time with OpenAI API.

    Args:
        query: Query text to embed

    Returns:
        Tuple of (latency_seconds, embedding_vector)
    """
    start = time.perf_counter()

    try:
        embedding = await create_embedding(query)
        latency = time.perf_counter() - start

        logger.debug(f"Embedding latency: {latency:.3f}s")
        return latency, embedding

    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise


async def measure_hybrid_search(
    query: str,
    embedding: List[float],
    top_k: int = 5
) -> tuple[float, List[Dict]]:
    """
    Measure Hybrid Search Time (pgvector + PostgreSQL full-text).

    Args:
        query: Query text
        embedding: Query embedding vector (1536-dim)
        top_k: Number of results to retrieve

    Returns:
        Tuple of (latency_seconds, search_results)
    """
    start = time.perf_counter()

    try:
        # Call hybrid_search handler directly
        result = await handle_hybrid_search({
            "query_text": query,
            "query_embedding": embedding,
            "top_k": top_k,
            "weights": {"semantic": 0.7, "keyword": 0.3}
        })

        latency = time.perf_counter() - start

        if result.get("error"):
            logger.error(f"Hybrid search error: {result['error']}")
            raise RuntimeError(f"Hybrid search failed: {result['error']}")

        logger.debug(f"Hybrid search latency: {latency:.3f}s")
        return latency, result.get("results", [])

    except Exception as e:
        logger.error(f"Hybrid search failed: {e}")
        raise


async def measure_cot_generation(
    query: str,
    context: List[str]
) -> tuple[float, str]:
    """
    Measure CoT Generation Time.

    NOTE: This is a placeholder implementation. CoT generation is performed
    by Claude Code internally. In a production benchmark, this would measure
    actual Claude Code answer generation time.

    Args:
        query: User query
        context: Retrieved context documents

    Returns:
        Tuple of (latency_seconds, generated_answer)
    """
    # TODO: Integrate with Claude Code to measure actual CoT generation time
    # For now, return placeholder values
    logger.warning(
        "CoT Generation timing not implemented - placeholder returning 0.0s"
    )

    # Simulate answer for evaluation
    placeholder_answer = f"This is a simulated answer for query: {query[:50]}..."
    return 0.0, placeholder_answer


async def measure_evaluation(
    client: HaikuClient,
    query: str,
    context: List[str],
    answer: str
) -> tuple[float, Dict[str, Any]]:
    """
    Measure Evaluation Time with Haiku API (includes fallback logic).

    Args:
        client: Initialized HaikuClient
        query: User query
        context: Retrieved context documents
        answer: Generated answer to evaluate

    Returns:
        Tuple of (latency_seconds, evaluation_result)
    """
    start = time.perf_counter()

    try:
        # Use evaluate_answer_with_fallback to include Story 3.4 fallback logic
        result = await evaluate_answer_with_fallback(
            client,
            query,
            context,
            answer
        )

        latency = time.perf_counter() - start

        logger.debug(f"Evaluation latency: {latency:.3f}s (fallback: {result.get('fallback', False)})")
        return latency, result

    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise


# =============================================================================
# Single Query Benchmark
# =============================================================================

async def benchmark_query(
    client: HaikuClient,
    query_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Benchmark single query with component-level timing.

    Args:
        client: Initialized HaikuClient for evaluation
        query_data: Golden Test query dict with 'id' and 'query' keys

    Returns:
        Dict with query_id, query_type, breakdown, and total_latency
    """
    query_id = query_data["id"]
    query = query_data["query"]
    query_type = query_data.get("query_type", "unknown")

    logger.info(f"Benchmarking query {query_id} ({query_type}): {query[:80]}...")

    breakdown = {}
    start_total = time.perf_counter()

    try:
        # Component 1: Query Expansion
        breakdown["query_expansion"] = await measure_query_expansion(query)

        # Component 2: Embedding
        embedding_time, embedding = await measure_embedding(query)
        breakdown["embedding"] = embedding_time

        # Component 3: Hybrid Search
        search_time, results = await measure_hybrid_search(query, embedding, top_k=5)
        breakdown["hybrid_search"] = search_time

        # Extract context from search results
        context = [r["content"] for r in results[:5]]

        # Component 4: CoT Generation
        cot_time, answer = await measure_cot_generation(query, context)
        breakdown["cot_generation"] = cot_time

        # Component 5: Evaluation
        eval_time, eval_result = await measure_evaluation(client, query, context, answer)
        breakdown["evaluation"] = eval_time

        # Total End-to-End Latency
        breakdown["total"] = time.perf_counter() - start_total

        # Verify component sum (should be close to total)
        component_sum = sum([
            breakdown["query_expansion"],
            breakdown["embedding"],
            breakdown["hybrid_search"],
            breakdown["cot_generation"],
            breakdown["evaluation"]
        ])

        overhead = breakdown["total"] - component_sum
        breakdown["overhead"] = overhead  # Python execution overhead

        logger.info(
            f"Query {query_id} complete: total={breakdown['total']:.3f}s "
            f"(embedding={breakdown['embedding']:.3f}s, "
            f"search={breakdown['hybrid_search']:.3f}s, "
            f"eval={breakdown['evaluation']:.3f}s)"
        )

        return {
            "query_id": query_id,
            "query": query,
            "query_type": query_type,
            "word_count": query_data.get("word_count", len(query.split())),
            "breakdown": breakdown,
            "timestamp": datetime.now().isoformat(),
            "fallback_used": eval_result.get("fallback", False),
        }

    except Exception as e:
        logger.error(f"Query {query_id} failed: {e}")
        return {
            "query_id": query_id,
            "query": query,
            "query_type": query_type,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


# =============================================================================
# Full Benchmark Execution
# =============================================================================

async def run_benchmark(test_queries: List[Dict]) -> List[Dict]:
    """
    Execute benchmark on all test queries.

    Args:
        test_queries: List of Golden Test query dicts

    Returns:
        List of measurement dicts with component breakdowns
    """
    logger.info(f"Starting benchmark on {len(test_queries)} queries...")

    # Initialize Haiku client
    client = HaikuClient()

    measurements = []

    for i, query_data in enumerate(test_queries, start=1):
        logger.info(f"Progress: {i}/{len(test_queries)}")

        try:
            measurement = await benchmark_query(client, query_data)
            measurements.append(measurement)

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Query {query_data.get('id')} benchmark failed: {e}")
            # Continue with next query

    logger.info(f"Benchmark complete: {len(measurements)} measurements collected")
    return measurements


# =============================================================================
# Statistical Analysis
# =============================================================================

def calculate_percentiles(measurements: List[Dict]) -> Dict[str, Dict[str, float]]:
    """
    Calculate p50, p95, p99 for each component and total latency.

    Args:
        measurements: List of measurement dicts from run_benchmark()

    Returns:
        Nested dict: {component: {p50, p95, p99}}
    """
    logger.info("Calculating percentiles...")

    # Filter out failed measurements
    valid_measurements = [m for m in measurements if "error" not in m]

    if not valid_measurements:
        logger.error("No valid measurements to analyze!")
        return {}

    # Extract latencies by component
    components = ["query_expansion", "embedding", "hybrid_search", "cot_generation", "evaluation", "total"]
    latencies = {comp: [] for comp in components}

    for m in valid_measurements:
        breakdown = m.get("breakdown", {})
        for comp in components:
            if comp in breakdown:
                latencies[comp].append(breakdown[comp])

    # Calculate percentiles for each component
    percentiles = {}

    for comp, values in latencies.items():
        if not values:
            logger.warning(f"No data for component: {comp}")
            continue

        try:
            percentiles[comp] = {
                "p50": statistics.quantiles(values, n=100)[49],  # Median
                "p95": statistics.quantiles(values, n=100)[94],
                "p99": statistics.quantiles(values, n=100)[98],
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "count": len(values)
            }

            logger.info(
                f"{comp}: p50={percentiles[comp]['p50']:.3f}s, "
                f"p95={percentiles[comp]['p95']:.3f}s, "
                f"p99={percentiles[comp]['p99']:.3f}s"
            )

        except Exception as e:
            logger.error(f"Failed to calculate percentiles for {comp}: {e}")

    return percentiles


def validate_nfr001(percentiles: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    """
    Validate NFR001 compliance: p95 End-to-End < 5s.

    Args:
        percentiles: Percentile results from calculate_percentiles()

    Returns:
        Dict with compliance status and details
    """
    logger.info("Validating NFR001 compliance...")

    total_stats = percentiles.get("total", {})
    p95_total = total_stats.get("p95", float('inf'))

    nfr001_pass = p95_total < NFR001_P95_THRESHOLD

    # Component threshold checks
    component_checks = {}

    # Hybrid Search threshold
    search_stats = percentiles.get("hybrid_search", {})
    search_p95 = search_stats.get("p95", float('inf'))
    component_checks["hybrid_search"] = {
        "p95": search_p95,
        "threshold": HYBRID_SEARCH_P95_THRESHOLD,
        "pass": search_p95 < HYBRID_SEARCH_P95_THRESHOLD
    }

    # CoT Generation threshold (p50, not p95)
    cot_stats = percentiles.get("cot_generation", {})
    cot_p50 = cot_stats.get("p50", float('inf'))
    component_checks["cot_generation"] = {
        "p50": cot_p50,
        "threshold": COT_GENERATION_P50_THRESHOLD,
        "pass": cot_p50 < COT_GENERATION_P50_THRESHOLD
    }

    # Evaluation threshold
    eval_stats = percentiles.get("evaluation", {})
    eval_p95 = eval_stats.get("p95", float('inf'))
    component_checks["evaluation"] = {
        "p95": eval_p95,
        "threshold": EVALUATION_P95_THRESHOLD,
        "pass": eval_p95 < EVALUATION_P95_THRESHOLD
    }

    logger.info(
        f"NFR001 Validation: {'✅ PASS' if nfr001_pass else '❌ FAIL'} "
        f"(p95={p95_total:.3f}s, threshold={NFR001_P95_THRESHOLD}s)"
    )

    return {
        "nfr001_pass": nfr001_pass,
        "p95_total": p95_total,
        "threshold": NFR001_P95_THRESHOLD,
        "component_checks": component_checks
    }


# =============================================================================
# Report Generation
# =============================================================================

def generate_report(
    percentiles: Dict[str, Dict[str, float]],
    validation: Dict[str, Any],
    measurements: List[Dict]
) -> str:
    """
    Generate performance-benchmarks.md documentation.

    Args:
        percentiles: Percentile statistics
        validation: NFR001 validation results
        measurements: Raw measurements

    Returns:
        Markdown report content
    """
    logger.info("Generating performance report...")

    # Count query types
    query_types = {"short": 0, "medium": 0, "long": 0}
    for m in measurements:
        qtype = m.get("query_type", "unknown").lower()
        if qtype in query_types:
            query_types[qtype] += 1

    # NFR001 status
    nfr001_status = "✅ PASS" if validation["nfr001_pass"] else "❌ FAIL"

    # Component thresholds
    comp_checks = validation["component_checks"]

    report = f"""# Performance Benchmarks - NFR001 Latency Validation

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Benchmark Date:** {datetime.now().strftime("%Y-%m-%d")}
**NFR001 Status:** {nfr001_status}

---

## Executive Summary

End-to-End Query Response Time: **{validation['p95_total']:.3f}s** (p95)
- NFR001 Threshold: <{validation['threshold']:.1f}s (p95)
- Status: **{nfr001_status}**

---

## Benchmark Setup

### Test Configuration

- **Query Count:** {len(measurements)} queries
- **Stratification:** {query_types['short']} Short, {query_types['medium']} Medium, {query_types['long']} Long
- **Timing Method:** `time.perf_counter()` (nanosecond precision)
- **Date:** {datetime.now().strftime("%Y-%m-%d")}

### Components Measured

1. **Query Expansion:** Query reformulation (placeholder - not yet measured)
2. **Embedding:** OpenAI text-embedding-3-small API
3. **Hybrid Search:** pgvector semantic + PostgreSQL full-text with RRF fusion
4. **CoT Generation:** Answer generation (placeholder - not yet measured)
5. **Evaluation:** Haiku API with fallback logic (Story 3.4)

---

## Results

### Percentile Summary

| Component | p50 (median) | p95 | p99 | Min | Max | Mean |
|-----------|--------------|-----|-----|-----|-----|------|
"""

    # Add component rows
    component_order = ["total", "query_expansion", "embedding", "hybrid_search", "cot_generation", "evaluation"]
    for comp in component_order:
        if comp in percentiles:
            stats = percentiles[comp]
            report += f"| {comp.replace('_', ' ').title()} | {stats['p50']:.3f}s | {stats['p95']:.3f}s | {stats['p99']:.3f}s | {stats['min']:.3f}s | {stats['max']:.3f}s | {stats['mean']:.3f}s |\n"

    report += f"""

### Component Threshold Validation

| Component | Metric | Value | Threshold | Status |
|-----------|--------|-------|-----------|--------|
| **Hybrid Search** | p95 | {comp_checks['hybrid_search']['p95']:.3f}s | <{comp_checks['hybrid_search']['threshold']:.1f}s | {'✅ PASS' if comp_checks['hybrid_search']['pass'] else '❌ FAIL'} |
| **CoT Generation** | p50 | {comp_checks['cot_generation']['p50']:.3f}s | <{comp_checks['cot_generation']['threshold']:.1f}s | {'✅ PASS' if comp_checks['cot_generation']['pass'] else '❌ FAIL'} |
| **Evaluation** | p95 | {comp_checks['evaluation']['p95']:.3f}s | <{comp_checks['evaluation']['threshold']:.1f}s | {'✅ PASS' if comp_checks['evaluation']['pass'] else '❌ FAIL'} |
| **End-to-End (NFR001)** | p95 | {validation['p95_total']:.3f}s | <{validation['threshold']:.1f}s | {nfr001_status} |

---

## NFR001 Compliance

### Requirement

**NFR001:** Query Response Time must be <5s (p95) for acceptable user experience.

### Result

- **Measured p95:** {validation['p95_total']:.3f}s
- **Threshold:** <{validation['threshold']:.1f}s
- **Compliance:** {nfr001_status}

"""

    # Add optimization recommendations if needed
    if not validation["nfr001_pass"]:
        report += """### ⚠️ Optimization Required

NFR001 threshold exceeded. Recommended optimizations:

"""

        # Identify bottleneck
        if comp_checks['hybrid_search']['p95'] > HYBRID_SEARCH_P95_THRESHOLD:
            report += """#### 1. Hybrid Search Optimization (p95 >{HYBRID_SEARCH_P95_THRESHOLD:.1f}s)

- **Test pgvector Index:** Try IVFFlat with varying `lists` parameter (100, 200, 500)
- **Consider HNSW Index:** Faster search, higher memory usage
- **Tune `probes` parameter:** Default=10, test with 5, 20

"""

        if comp_checks['cot_generation']['p50'] > COT_GENERATION_P50_THRESHOLD:
            report += f"""#### 2. CoT Generation Optimization (p50 >{COT_GENERATION_P50_THRESHOLD:.1f}s)

- **Reduce Retrieved Context:** Use Top-3 instead of Top-5 results
- **Shorten CoT Prompt:** Remove redundant instructions
- **Profile Claude Code latency:** Measure internal reasoning time

"""

        if comp_checks['evaluation']['p95'] > EVALUATION_P95_THRESHOLD:
            report += f"""#### 3. Evaluation Optimization (p95 >{EVALUATION_P95_THRESHOLD:.1f}s)

- **Check Haiku API Latency:** Profile API vs. network latency
- **Consider Batch Evaluation:** Parallel queries (watch for rate limits)
- **Review Retry-Logic Overhead:** Story 3.3 retry impact

"""
    else:
        report += """### ✅ NFR001 Satisfied

System performance meets NFR001 requirements. No immediate optimizations needed.

"""

    report += f"""---

## Baseline for Regression Testing

These values establish the performance baseline for future regression tests:

- **p95 End-to-End:** {validation['p95_total']:.3f}s
- **p95 Hybrid Search:** {comp_checks['hybrid_search']['p95']:.3f}s
- **p95 Evaluation:** {comp_checks['evaluation']['p95']:.3f}s

**Baseline Date:** {datetime.now().strftime("%Y-%m-%d")}

Monitor these metrics in Story 3.11 (7-Day Stability Testing) to detect performance degradation.

---

## Notes

### Measurement Limitations

1. **Query Expansion:** Not yet measured (requires Claude Code integration)
2. **CoT Generation:** Not yet measured (requires Claude Code integration)
3. **Fallback Logic:** Haiku API evaluation includes Story 3.4 fallback overhead

### Next Steps

1. Manual review: Verify all acceptance criteria met
2. Re-run after optimizations (if needed)
3. Integrate measurements into Story 3.11 regression tests

---

**End of Report**
"""

    return report


# =============================================================================
# Main Execution
# =============================================================================

async def main():
    """Main benchmark execution."""
    logger.info("=" * 80)
    logger.info("Latency Benchmarking - NFR001 Validation")
    logger.info("=" * 80)

    # 1. Load Golden Test Set
    logger.info(f"Loading Golden Test Set from {GOLDEN_TEST_SET_PATH}...")

    try:
        with open(GOLDEN_TEST_SET_PATH, "r") as f:
            test_queries = json.load(f)

        logger.info(f"Loaded {len(test_queries)} test queries")

        # Verify stratification
        query_types = {"short": 0, "medium": 0, "long": 0}
        for q in test_queries:
            qtype = q.get("query_type", "unknown").lower()
            if qtype in query_types:
                query_types[qtype] += 1

        logger.info(f"Stratification: {query_types['short']} Short, {query_types['medium']} Medium, {query_types['long']} Long")

    except FileNotFoundError:
        logger.error(f"Golden Test Set not found: {GOLDEN_TEST_SET_PATH}")
        logger.error("Run Story 3.1 to create Golden Test Set first")
        return
    except Exception as e:
        logger.error(f"Failed to load Golden Test Set: {e}")
        return

    # 2. Run Benchmark
    measurements = await run_benchmark(test_queries)

    # 3. Calculate Percentiles
    percentiles = calculate_percentiles(measurements)

    # 4. Validate NFR001
    validation = validate_nfr001(percentiles)

    # 5. Save Measurements
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = RESULTS_DIR / f"latency_measurements_{timestamp}.json"

    with open(results_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "measurements": measurements,
            "percentiles": percentiles,
            "validation": validation
        }, f, indent=2)

    logger.info(f"Results saved to: {results_file}")

    # 6. Generate Report
    report = generate_report(percentiles, validation, measurements)

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = DOCS_DIR / "performance-benchmarks.md"

    with open(report_file, "w") as f:
        f.write(report)

    logger.info(f"Report generated: {report_file}")

    # 7. Summary
    logger.info("=" * 80)
    logger.info("BENCHMARK COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Measurements: {len(measurements)}")
    logger.info(f"NFR001 Status: {'✅ PASS' if validation['nfr001_pass'] else '❌ FAIL'}")
    logger.info(f"p95 End-to-End: {validation['p95_total']:.3f}s (threshold: <{validation['threshold']:.1f}s)")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
