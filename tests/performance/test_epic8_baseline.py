"""
Epic 8 Baseline Performance Tests

Measures current performance BEFORE Epic 8 implementation to establish baselines for:
- NFR1: Sector classification during edge insert must add <10ms to existing insert latency
- NFR2: Sector-filtered queries must perform within 20% of unfiltered query latency
- NFR3: Decay calculation must complete in <5ms per edge

Run with: pytest tests/performance/test_epic8_baseline.py -v -s
"""

from __future__ import annotations

import asyncio
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytest

# Integration tests require real database
pytestmark = pytest.mark.integration


@dataclass
class PerformanceResult:
    """Container for performance measurement results."""
    operation: str
    samples: list[float]
    unit: str = "ms"

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0

    @property
    def p95(self) -> float:
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    @property
    def min(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def max(self) -> float:
        return max(self.samples) if self.samples else 0.0


class TestEpic8Baseline:
    """
    Baseline performance measurements for Epic 8.

    These tests measure current performance before Epic 8 changes
    to establish baselines for NFR validation.
    """

    @pytest.fixture
    def unique_prefix(self) -> str:
        """Generate unique prefix for test nodes to avoid conflicts."""
        return f"perf_test_{int(time.time() * 1000)}"

    @pytest.mark.asyncio
    async def test_graph_add_edge_baseline_latency(self, conn, unique_prefix: str):
        """
        Measure baseline insert latency for graph_add_edge.

        NFR1 Target: Epic 8 classification must add <10ms to this baseline.
        """
        from mcp_server.tools.graph_add_edge import handle_graph_add_edge

        samples: list[float] = []
        num_samples = 20

        # Create source and target nodes first
        source_name = f"{unique_prefix}_source"
        target_name = f"{unique_prefix}_target"

        from mcp_server.tools.graph_add_node import handle_graph_add_node
        await handle_graph_add_node({
            "name": source_name,
            "label": "PerfTest",
            "properties": {"test": True}
        })
        await handle_graph_add_node({
            "name": target_name,
            "label": "PerfTest",
            "properties": {"test": True}
        })

        # Warm-up run
        await handle_graph_add_edge({
            "source_name": source_name,
            "target_name": target_name,
            "relation": "WARMUP",
            "properties": {"warmup": True}
        })

        # Measure edge insert latency
        for i in range(num_samples):
            relation = f"TEST_RELATION_{i}"
            properties = {
                "sample": i,
                "timestamp": datetime.now().isoformat(),
                "emotional_valence": "positive" if i % 3 == 0 else None,
                "context_type": "shared_experience" if i % 5 == 0 else "standard",
            }
            # Remove None values
            properties = {k: v for k, v in properties.items() if v is not None}

            start = time.perf_counter()
            result = await handle_graph_add_edge({
                "source_name": source_name,
                "target_name": target_name,
                "relation": relation,
                "properties": properties
            })
            elapsed_ms = (time.perf_counter() - start) * 1000

            assert result["status"] == "success", f"Edge insert failed: {result}"
            samples.append(elapsed_ms)

        perf = PerformanceResult("graph_add_edge", samples)

        # Report results
        print("\n" + "=" * 70)
        print("EPIC 8 BASELINE: graph_add_edge Insert Latency")
        print("=" * 70)
        print(f"  Samples:     {len(samples)}")
        print(f"  Mean:        {perf.mean:.2f} ms")
        print(f"  Median:      {perf.median:.2f} ms")
        print(f"  Std Dev:     {perf.stdev:.2f} ms")
        print(f"  Min:         {perf.min:.2f} ms")
        print(f"  Max:         {perf.max:.2f} ms")
        print(f"  P95:         {perf.p95:.2f} ms")
        print("-" * 70)
        print(f"  NFR1 Budget: <10ms additional latency after Epic 8")
        print(f"  Target:      Epic 8 insert latency should be < {perf.p95 + 10:.2f} ms (P95)")
        print("=" * 70)

        # Store baseline for comparison
        assert perf.mean < 500, f"Baseline insert too slow: {perf.mean:.2f}ms"

    @pytest.mark.asyncio
    async def test_query_neighbors_baseline_latency(self, conn, unique_prefix: str):
        """
        Measure baseline latency for query_neighbors.

        NFR2 Target: Sector-filtered queries must be within 20% of this baseline.
        """
        from mcp_server.tools.graph_add_node import handle_graph_add_node
        from mcp_server.tools.graph_add_edge import handle_graph_add_edge
        from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors

        # Create a small graph for testing
        center_name = f"{unique_prefix}_center"
        await handle_graph_add_node({
            "name": center_name,
            "label": "PerfTestCenter",
            "properties": {"test": True}
        })

        # Create 10 connected nodes
        for i in range(10):
            neighbor_name = f"{unique_prefix}_neighbor_{i}"
            await handle_graph_add_node({
                "name": neighbor_name,
                "label": "PerfTestNeighbor",
                "properties": {"index": i}
            })
            await handle_graph_add_edge({
                "source_name": center_name,
                "target_name": neighbor_name,
                "relation": "CONNECTS_TO",
                "properties": {"weight": 0.9}
            })

        samples: list[float] = []
        num_samples = 20

        # Warm-up
        await handle_graph_query_neighbors({"node_name": center_name, "depth": 1})

        # Measure query latency
        for _ in range(num_samples):
            start = time.perf_counter()
            result = await handle_graph_query_neighbors({
                "node_name": center_name,
                "depth": 1
            })
            elapsed_ms = (time.perf_counter() - start) * 1000

            assert result["status"] == "success", f"Query failed: {result}"
            samples.append(elapsed_ms)

        perf = PerformanceResult("query_neighbors", samples)

        # Report results
        print("\n" + "=" * 70)
        print("EPIC 8 BASELINE: query_neighbors Latency")
        print("=" * 70)
        print(f"  Samples:     {len(samples)}")
        print(f"  Mean:        {perf.mean:.2f} ms")
        print(f"  Median:      {perf.median:.2f} ms")
        print(f"  Std Dev:     {perf.stdev:.2f} ms")
        print(f"  Min:         {perf.min:.2f} ms")
        print(f"  Max:         {perf.max:.2f} ms")
        print(f"  P95:         {perf.p95:.2f} ms")
        print("-" * 70)
        print(f"  NFR2 Budget: Filtered queries within 20% of baseline")
        print(f"  Target:      Epic 8 filtered query should be < {perf.p95 * 1.2:.2f} ms (P95 + 20%)")
        print("=" * 70)

        assert perf.mean < 200, f"Baseline query too slow: {perf.mean:.2f}ms"

    @pytest.mark.asyncio
    async def test_hybrid_search_baseline_latency(self, conn, unique_prefix: str):
        """
        Measure baseline latency for hybrid_search.

        NFR2 Target: Sector-filtered search must be within 20% of this baseline.
        """
        from mcp_server.tools import handle_hybrid_search

        samples: list[float] = []
        num_samples = 10  # Fewer samples as this is more expensive

        test_queries = [
            "Was ist PostgreSQL?",
            "Emotional memory system",
            "Graph database performance",
            "Decay calculation formula",
            "Memory sector classification",
        ]

        # Warm-up
        await handle_hybrid_search({"query_text": "warmup query", "top_k": 5})

        # Measure search latency
        for i in range(num_samples):
            query = test_queries[i % len(test_queries)]

            start = time.perf_counter()
            result = await handle_hybrid_search({
                "query_text": query,
                "top_k": 10
            })
            elapsed_ms = (time.perf_counter() - start) * 1000

            assert result["status"] == "success", f"Search failed: {result}"
            samples.append(elapsed_ms)

        perf = PerformanceResult("hybrid_search", samples)

        # Report results
        print("\n" + "=" * 70)
        print("EPIC 8 BASELINE: hybrid_search Latency")
        print("=" * 70)
        print(f"  Samples:     {len(samples)}")
        print(f"  Mean:        {perf.mean:.2f} ms")
        print(f"  Median:      {perf.median:.2f} ms")
        print(f"  Std Dev:     {perf.stdev:.2f} ms")
        print(f"  Min:         {perf.min:.2f} ms")
        print(f"  Max:         {perf.max:.2f} ms")
        print(f"  P95:         {perf.p95:.2f} ms")
        print("-" * 70)
        print(f"  NFR2 Budget: Filtered search within 20% of baseline")
        print(f"  Target:      Epic 8 filtered search should be < {perf.p95 * 1.2:.2f} ms (P95 + 20%)")
        print("=" * 70)

        assert perf.mean < 2000, f"Baseline search too slow: {perf.mean:.2f}ms"


class TestDecayCalculationBaseline:
    """Baseline for decay calculation performance (NFR3)."""

    def test_current_decay_calculation_speed(self):
        """
        Measure current IEF calculation speed.

        NFR3 Target: Decay calculation must complete in <5ms per edge.

        Note: Currently IEF is embedded in graph_query_neighbors.
        This test measures the pure calculation time.
        """
        import math

        # Simulate current IEF calculation
        def calculate_relevance_score(
            access_count: int,
            days_since_last_access: float,
            S_base: float = 100
        ) -> float:
            S = S_base * (1 + math.log(1 + access_count))
            return math.exp(-days_since_last_access / S)

        samples: list[float] = []
        num_samples = 1000  # Fast calculation, many samples

        # Test with various inputs
        test_cases = [
            (0, 0),      # New edge, just accessed
            (0, 100),    # New edge, 100 days old
            (10, 50),    # Accessed 10 times, 50 days
            (100, 200),  # Heavy access, old
            (5, 30),     # Medium access, medium age
        ]

        for i in range(num_samples):
            access_count, days = test_cases[i % len(test_cases)]

            start = time.perf_counter()
            score = calculate_relevance_score(access_count, days)
            elapsed_ms = (time.perf_counter() - start) * 1000

            assert 0 <= score <= 1, f"Invalid score: {score}"
            samples.append(elapsed_ms)

        perf = PerformanceResult("decay_calculation", samples)

        # Report results
        print("\n" + "=" * 70)
        print("EPIC 8 BASELINE: Decay Calculation Speed")
        print("=" * 70)
        print(f"  Samples:     {len(samples)}")
        print(f"  Mean:        {perf.mean:.4f} ms")
        print(f"  Median:      {perf.median:.4f} ms")
        print(f"  Max:         {perf.max:.4f} ms")
        print(f"  P95:         {perf.p95:.4f} ms")
        print("-" * 70)
        print(f"  NFR3 Target: <5ms per edge")
        print(f"  Status:      {'PASS' if perf.p95 < 5 else 'FAIL'}")
        print("=" * 70)

        # Pure calculation should be sub-millisecond
        assert perf.p95 < 1, f"Decay calculation too slow: {perf.p95:.4f}ms"


class TestBaselineSummary:
    """Generate comprehensive baseline summary."""

    def test_generate_baseline_report(self):
        """Generate baseline report for Epic 8 NFR validation."""
        print("\n")
        print("=" * 70)
        print("EPIC 8 PERFORMANCE BASELINE REPORT")
        print(f"Generated: {datetime.now().isoformat()}")
        print("=" * 70)
        print("""
NFR Targets for Epic 8:

  NFR1: Sector classification during edge insert
        Budget: <10ms additional latency
        Validation: Compare post-Epic 8 insert latency to baseline

  NFR2: Sector-filtered queries
        Budget: Within 20% of unfiltered query latency
        Validation: Compare filtered vs unfiltered query times

  NFR3: Decay calculation with sector-specific parameters
        Budget: <5ms per edge
        Validation: Measure calculate_relevance_score() time

How to Use This Baseline:

  1. Run this test BEFORE Epic 8 implementation:
     pytest tests/performance/test_epic8_baseline.py -v -s

  2. Record the P95 values for each operation

  3. After Epic 8 implementation, run again and compare:
     - graph_add_edge: New P95 should be < (Baseline P95 + 10ms)
     - query_neighbors: Filtered P95 should be < (Baseline P95 * 1.2)
     - hybrid_search: Filtered P95 should be < (Baseline P95 * 1.2)
     - decay_calculation: P95 should be < 5ms
""")
        print("=" * 70)
