"""
Performance Tests for Memory Sector Classification

Tests that sector classification meets NFR1: <10ms overhead per edge insert.

Author: Epic 8 Implementation
Story: 8.3 - Auto-Classification on Edge Insert
NFR: NFR1 - Classification must add less than 10ms to insert latency
"""

import time
import pytest

from mcp_server.db.graph import add_edge, get_or_create_node
from mcp_server.utils.sector_classifier import classify_memory_sector


class TestClassificationLatency:
    """Test AC #7: Classification overhead is less than 10ms per NFR1."""

    @pytest.mark.performance
    def test_classification_latency_under_10ms_emotional(self):
        """Classification of emotional edge should take <10ms."""
        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            classify_memory_sector("EXPERIENCED", {"emotional_valence": "positive"})

        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        per_call = elapsed / iterations

        assert per_call < 10, f"Emotional classification took {per_call:.3f}ms per call (NFR1: <10ms)"

    @pytest.mark.performance
    def test_classification_latency_under_10ms_episodic(self):
        """Classification of episodic edge should take <10ms."""
        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            classify_memory_sector("PARTICIPATED_IN", {"context_type": "shared_experience"})

        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        per_call = elapsed / iterations

        assert per_call < 10, f"Episodic classification took {per_call:.3f}ms per call (NFR1: <10ms)"

    @pytest.mark.performance
    def test_classification_latency_under_10ms_procedural(self):
        """Classification of procedural edge should take <10ms."""
        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            classify_memory_sector("LEARNED", {})

        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        per_call = elapsed / iterations

        assert per_call < 10, f"Procedural classification took {per_call:.3f}ms per call (NFR1: <10ms)"

    @pytest.mark.performance
    def test_classification_latency_under_10ms_reflective(self):
        """Classification of reflective edge should take <10ms."""
        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            classify_memory_sector("REFLECTS", {})

        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        per_call = elapsed / iterations

        assert per_call < 10, f"Reflective classification took {per_call:.3f}ms per call (NFR1: <10ms)"

    @pytest.mark.performance
    def test_classification_latency_under_10ms_semantic_default(self):
        """Classification of semantic (default) edge should take <10ms."""
        iterations = 1000
        start = time.perf_counter()

        for _ in range(iterations):
            classify_memory_sector("KNOWS", {})

        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        per_call = elapsed / iterations

        assert per_call < 10, f"Semantic (default) classification took {per_call:.3f}ms per call (NFR1: <10ms)"

    @pytest.mark.performance
    def test_classification_latency_under_10ms_complex_properties(self):
        """Classification with complex properties should take <10ms."""
        iterations = 1000
        complex_properties = {
            "emotional_valence": "positive",
            "context_type": "conversation",
            "participants": ["Alice", "Bob"],
            "timestamp": "2026-01-08T12:00:00Z",
            "confidence": 0.95
        }

        start = time.perf_counter()

        for _ in range(iterations):
            classify_memory_sector("EXPERIENCED", complex_properties)

        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
        per_call = elapsed / iterations

        assert per_call < 10, f"Complex classification took {per_call:.3f}ms per call (NFR1: <10ms)"

    @pytest.mark.performance
    def test_classification_latency_p99_under_10ms(self):
        """P99 latency should be under 10ms (99th percentile)."""
        iterations = 1000
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            classify_memory_sector("EXPERIENCED", {"emotional_valence": "positive"})
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms

        # Sort to find P99
        latencies.sort()
        p99_latency = latencies[int(iterations * 0.99)]  # 99th percentile

        assert p99_latency < 10, f"P99 latency is {p99_latency:.3f}ms (NFR1: <10ms)"

    @pytest.mark.performance
    def test_classification_baseline_comparison(self):
        """Classification should not add significant latency vs. no classification."""
        iterations = 1000

        # Measure with classification
        start = time.perf_counter()
        for _ in range(iterations):
            classify_memory_sector("EXPERIENCED", {"emotional_valence": "positive"})
        with_classification = (time.perf_counter() - start) * 1000

        # Baseline: minimal dict operation (similar cost without classification logic)
        start = time.perf_counter()
        for _ in range(iterations):
            _ = {"emotional_valence": "positive"}.get("emotional_valence")
        baseline = (time.perf_counter() - start) * 1000

        # Classification overhead should be minimal
        overhead = with_classification - baseline
        per_call_overhead = overhead / iterations

        assert per_call_overhead < 10, f"Classification overhead is {per_call_overhead:.3f}ms per call (NFR1: <10ms)"


class TestFullEdgeInsertLatency:
    """Test AC #7: Full edge insert with classification meets NFR1."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_full_edge_insert_latency_under_10ms(self):
        """Full edge insert operation including classification should have <10ms overhead.

        This test measures the actual edge insert operation end-to-end, not just
        the classification function in isolation. This is the correct interpretation
        of NFR1: "classification adds less than 10ms to insert latency".
        """
        # Create test nodes
        source_result = get_or_create_node(name="PerfTestSource", label="Entity")
        source_id = source_result["node_id"]
        target_result = get_or_create_node(name="PerfTestTarget", label="Entity")
        target_id = target_result["node_id"]

        iterations = 100

        # Measure baseline: edge insert WITHOUT classification (default semantic)
        # We pass "semantic" directly to skip classification overhead
        start = time.perf_counter()
        for i in range(iterations):
            add_edge(
                source_id=source_id,
                target_id=target_id,
                relation=f"BASELINE_{i}",
                weight=1.0,
                properties="{}",
                memory_sector="semantic"  # Direct pass, no classification call
            )
        baseline_elapsed = (time.perf_counter() - start) * 1000  # ms
        baseline_per_call = baseline_elapsed / iterations

        # Measure WITH classification: emotional sector (requires classification logic)
        start = time.perf_counter()
        for i in range(iterations):
            # Simulate what handle_graph_add_edge does
            from mcp_server.utils.sector_classifier import classify_memory_sector
            memory_sector = classify_memory_sector("EXPERIENCED", {"emotional_valence": "positive"})

            add_edge(
                source_id=source_id,
                target_id=target_id,
                relation=f"CLASSIFIED_{i}",
                weight=1.0,
                properties='{"emotional_valence": "positive"}',
                memory_sector=memory_sector
            )
        with_classification_elapsed = (time.perf_counter() - start) * 1000  # ms
        with_classification_per_call = with_classification_elapsed / iterations

        # Calculate overhead
        overhead_per_call = with_classification_per_call - baseline_per_call

        assert overhead_per_call < 10, f"Classification adds {overhead_per_call:.3f}ms per edge insert (NFR1: <10ms)"
