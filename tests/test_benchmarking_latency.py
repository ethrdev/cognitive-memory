"""
[P1] Latency Benchmarking Tests

Tests for latency benchmarking functionality including performance measurement,
threshold checking, and performance reporting.

Priority: P1 (High) - Performance monitoring is important for system reliability
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import asyncio
import time

from mcp_server.benchmarking.latency_benchmark import LatencyBenchmark


@pytest.mark.P1
class TestLatencyBenchmark:
    """P1 tests for latency benchmarking functionality."""

    @pytest.fixture
    def latency_benchmark(self):
        """Create latency benchmark instance."""
        return LatencyBenchmark(
            operation_timeout=5.0,
            performance_threshold=100.0,  # milliseconds
            warning_threshold=200.0,      # milliseconds
        )

    @pytest.mark.asyncio
    async def test_measure_operation_latency(self, latency_benchmark):
        """[P1] Measure operation latency should return timing information."""
        # GIVEN: Latency benchmark initialized

        # WHEN: Operation is measured
        async def sample_operation():
            await asyncio.sleep(0.01)  # 10ms operation
            return "success"

        result = await latency_benchmark.measure_operation(
            operation_name="test_operation",
            operation=sample_operation()
        )

        # THEN: Result should include timing
        assert result["operation"] == "test_operation"
        assert result["status"] == "success"
        assert result["latency_ms"] > 0
        assert result["latency_ms"] < 50  # Should be fast

    @pytest.mark.asyncio
    async def test_measure_operation_with_timeout(self, latency_benchmark):
        """[P1] Measure operation should handle timeout correctly."""
        # GIVEN: Latency benchmark with short timeout

        # WHEN: Operation exceeds timeout
        async def slow_operation():
            await asyncio.sleep(0.1)  # 100ms
            return "slow_result"

        result = await latency_benchmark.measure_operation(
            operation_name="slow_operation",
            operation=slow_operation()
        )

        # THEN: Should handle timeout gracefully
        assert result["operation"] == "slow_operation"
        assert result["status"] == "timeout"
        assert result["latency_ms"] >= 5000.0  # Timeout reached

    @pytest.mark.asyncio
    async def test_check_performance_threshold_normal(self, latency_benchmark):
        """[P1] Check performance should pass when under threshold."""
        # GIVEN: Latency benchmark configured

        # WHEN: Measuring fast operation
        fast_operation = LatencyBenchmark()
        result = await fast_operation.measure_operation(
            operation_name="fast",
            operation=asyncio.sleep(0.001, result="done")
        )

        # THEN: Should be within threshold
        performance_check = fast_operation.check_threshold(result["latency_ms"])
        assert performance_check["status"] == "pass"
        assert performance_check["threshold"] == 100.0
        assert performance_check["actual"] < 100.0

    @pytest.mark.asyncio
    async def test_check_performance_threshold_warning(self, latency_benchmark):
        """[P1] Check performance should warn when over warning threshold."""
        # GIVEN: Latency benchmark configured

        # WHEN: Measuring slow operation
        slow_operation = LatencyBenchmark(
            performance_threshold=100.0,
            warning_threshold=200.0,
        )
        result = await slow_operation.measure_operation(
            operation_name="slow",
            operation=asyncio.sleep(0.15, result="slow")  # 150ms
        )

        # THEN: Should warn
        performance_check = slow_operation.check_threshold(result["latency_ms"])
        assert performance_check["status"] == "warning"
        assert performance_check["actual"] > 100.0
        assert performance_check["actual"] < 200.0

    @pytest.mark.asyncio
    async def test_check_performance_threshold_fail(self, latency_benchmark):
        """[P1] Check performance should fail when over performance threshold."""
        # GIVEN: Latency benchmark configured

        # WHEN: Measuring very slow operation
        very_slow_operation = LatencyBenchmark(
            performance_threshold=100.0,
            warning_threshold=200.0,
        )
        result = await very_slow_operation.measure_operation(
            operation_name="very_slow",
            operation=asyncio.sleep(0.25, result="very_slow")  # 250ms
        )

        # THEN: Should fail
        performance_check = very_slow_operation.check_threshold(result["latency_ms"])
        assert performance_check["status"] == "fail"
        assert performance_check["actual"] >= 200.0

    @pytest.mark.asyncio
    async def test_record_benchmark_result(self, latency_benchmark):
        """[P2] Record benchmark result should store metrics."""
        # GIVEN: Latency benchmark initialized

        # WHEN: Result is recorded
        latency_benchmark.record_result(
            operation="test_op",
            latency_ms=50.0,
            status="success",
            metadata={"test": True}
        )

        # THEN: Result should be stored
        assert len(latency_benchmark.results) == 1
        assert latency_benchmark.results[0]["operation"] == "test_op"
        assert latency_benchmark.results[0]["latency_ms"] == 50.0

    @pytest.mark.asyncio
    async def test_get_performance_summary(self, latency_benchmark):
        """[P2] Get performance summary should calculate statistics."""
        # GIVEN: Benchmark with multiple results
        latency_benchmark.record_result("op1", 50.0, "success")
        latency_benchmark.record_result("op2", 100.0, "success")
        latency_benchmark.record_result("op3", 75.0, "success")

        # WHEN: Summary is generated
        summary = latency_benchmark.get_performance_summary()

        # THEN: Should calculate statistics
        assert summary["total_operations"] == 3
        assert summary["average_latency"] == 75.0
        assert summary["min_latency"] == 50.0
        assert summary["max_latency"] == 100.0
        assert summary["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_benchmark_with_custom_thresholds(self):
        """[P2] Benchmark should work with custom thresholds."""
        # GIVEN: Custom threshold configuration
        benchmark = LatencyBenchmark(
            performance_threshold=50.0,
            warning_threshold=75.0,
        )

        # WHEN: Measuring operation
        result = await benchmark.measure_operation(
            operation_name="custom_test",
            operation=asyncio.sleep(0.03, result="done")  # 30ms
        )

        # THEN: Should respect custom thresholds
        assert result["latency_ms"] < 50.0
        check = benchmark.check_threshold(result["latency_ms"])
        assert check["status"] == "pass"

    @pytest.mark.asyncio
    async def test_concurrent_benchmarking(self, latency_benchmark):
        """[P3] Benchmark should handle concurrent operations."""
        # GIVEN: Latency benchmark

        # WHEN: Multiple operations run concurrently
        async def op1():
            await asyncio.sleep(0.01)
            return "op1"

        async def op2():
            await asyncio.sleep(0.02)
            return "op2"

        async def op3():
            await asyncio.sleep(0.015)
            return "op3"

        results = await asyncio.gather(
            latency_benchmark.measure_operation("op1", op1()),
            latency_benchmark.measure_operation("op2", op2()),
            latency_benchmark.measure_operation("op3", op3()),
        )

        # THEN: All operations should be measured
        assert len(results) == 3
        for result in results:
            assert result["status"] == "success"
            assert result["latency_ms"] > 0


@pytest.mark.P2
class TestLatencyBenchmarkIntegration:
    """P2 integration tests for latency benchmarking."""

    @pytest.mark.asyncio
    async def test_end_to_end_benchmark_flow(self):
        """[P2] End-to-end benchmark flow from measurement to reporting."""
        # GIVEN: Benchmark configured
        benchmark = LatencyBenchmark(
            performance_threshold=100.0,
            warning_threshold=150.0,
        )

        # WHEN: Running complete benchmark cycle
        await benchmark.measure_operation(
            "db_query",
            asyncio.sleep(0.05, result="query_result")
        )
        await benchmark.measure_operation(
            "api_call",
            asyncio.sleep(0.03, result="api_result")
        )

        # THEN: Should generate complete report
        summary = benchmark.get_performance_summary()
        assert summary["total_operations"] == 2
        assert "average_latency" in summary
        assert "percentile_95" in summary

    @pytest.mark.asyncio
    async def test_benchmark_with_retries(self, latency_benchmark):
        """[P2] Benchmark should support retry logic for flaky operations."""
        attempt_count = 0

        async def flaky_operation():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Flaky failure")
            await asyncio.sleep(0.01)
            return "success"

        # GIVEN: Benchmark configured with retry
        # WHEN: Flaky operation runs with retries
        result = await latency_benchmark.measure_with_retry(
            operation_name="flaky",
            operation=flaky_operation(),
            max_retries=3,
            retry_delay=0.01
        )

        # THEN: Should eventually succeed
        assert result["status"] == "success"
        assert result["attempts"] == 3
        assert result["latency_ms"] > 0
