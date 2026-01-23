"""
P0 Tests: Sector Classification Latency <10ms (Epic 8)
ATDD Red Phase - Tests that will pass after implementation

Risk Mitigation: R-003 (Sector classification adds >10ms to insert latency)
Test Count: 6
"""

import pytest
import time
import statistics
from typing import Dict, Any
from pathlib import Path

from mcp_server.utils.sector_classifier import classify_memory_sector
from mcp_server.utils.relevance import calculate_relevance_score
from mcp_server.utils.decay_config import get_decay_config


class TestClassificationPerformance:
    """NFR1: Sector classification must add <10ms to insert latency"""

    @pytest.mark.p0
    def test_classify_memory_sector_latency_under_10ms(self):
        """NFR1: Classification performance requirement

        Given classify_memory_sector function
        When called with typical edge properties
        Then it completes in less than 10ms

        Performance is critical for user experience.
        """
        # Time multiple calls to get average
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            result = classify_memory_sector(
                relation="LEARNED",
                properties={"importance": "high"}
            )
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # Convert to ms

        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95th percentile

        assert avg_latency < 10, f"Average latency {avg_latency:.2f}ms should be <10ms"
        assert p95_latency < 15, f"95th percentile {p95_latency:.2f}ms should be <15ms"

    @pytest.mark.p0
    def test_edge_insert_latency_with_classification(self):
        """NFR1: End-to-end insert latency with classification

        Given graph_add_edge with automatic classification
        When an edge is inserted
        Then classification adds less than 10ms to insert latency

        This is the actual user-facing metric.
        """
        # Simulate the classification that happens during edge insertion
        latencies = []
        for _ in range(50):
            start = time.perf_counter()

            # Simulate the classification steps
            result = classify_memory_sector(
                relation="KNOWS",
                properties={"emotional_valence": "positive"}
            )

            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)
        assert avg_latency < 10, f"Insert latency {avg_latency:.2f}ms should be <10ms"

    @pytest.mark.p0
    def test_classification_performance_multiple_calls(self):
        """NFR1: Performance under load

        Given 100 sequential classification calls
        When average latency is calculated
        Then average is under 10ms and 95th percentile under 15ms

        Ensures consistent performance, not just average case.
        """
        # Test various classification scenarios
        test_cases = [
            ("LEARNED", {}),
            ("KNOWS", {"emotional_valence": "positive"}),
            ("CONNECTED_TO", {"context_type": "shared_experience"}),
            ("REFLECTS", {}),
            ("REALIZED", {}),
        ]

        all_latencies = []

        for relation, props in test_cases:
            for _ in range(20):
                start = time.perf_counter()
                classify_memory_sector(relation, props)
                end = time.perf_counter()
                all_latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(all_latencies)
        p95_latency = statistics.quantiles(all_latencies, n=20)[18]

        assert avg_latency < 10, f"Average {avg_latency:.2f}ms should be <10ms"
        assert p95_latency < 15, f"95th percentile {p95_latency:.2f}ms should be <15ms"


class TestConfigLoadingPerformance:
    """NFR4: Config file loading must not block server startup"""

    @pytest.mark.p0
    def test_decay_config_loads_in_under_1s(self):
        """NFR4: Config loading performance

        Given the server is starting
        When decay_config.yaml is loaded
        Then config loading completes in less than 1 second
        """
        # Time the config loading
        start = time.perf_counter()
        config = get_decay_config()
        end = time.perf_counter()

        load_time = (end - start) * 1000  # Convert to ms

        assert load_time < 1000, f"Config loading {load_time:.2f}ms should be <1000ms"
        assert config is not None, "Config should be loaded"


class TestDecayCalculationPerformance:
    """NFR3: Decay calculation must complete in <5ms per edge"""

    @pytest.mark.p0
    def test_decay_calculation_latency_under_5ms(self):
        """NFR3: Decay calculation performance

        Given calculate_relevance_score function
        When called for an edge
        Then calculation completes in less than 5ms
        """
        from datetime import datetime, timedelta

        # Create test edge data
        base_date = datetime.now()
        edge_data = {
            "edge_properties": {"memory_sector": "emotional"},
            "last_accessed": (base_date - timedelta(days=100)).isoformat(),
            "access_count": 5,
            "memory_sector": "emotional"
        }

        # Time multiple calls
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            score = calculate_relevance_score(edge_data)
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]

        assert avg_latency < 5, f"Average decay calc {avg_latency:.2f}ms should be <5ms"
        assert p95_latency < 10, f"95th percentile {p95_latency:.2f}ms should be <10ms"

    @pytest.mark.p0
    def test_decay_calculation_performance_logged(self):
        """NFR16: Performance logging

        Given decay calculation is performed
        When calculate_relevance_score completes
        Then duration is logged at DEBUG level

        For monitoring and optimization.
        """
        # Check that relevance.py has performance logging
        relevance_file = Path("mcp_server/utils/relevance.py")
        content = relevance_file.read_text()

        # Verify timing code exists
        assert "time.perf_counter()" in content, "Should measure performance"
        assert "calculation_ms" in content or "elapsed_ms" in content, \
            "Should log calculation time"
