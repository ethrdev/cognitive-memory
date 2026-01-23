"""
Test Get Golden Test Results Tool

Tests for the get_golden_test_results MCP tool which provides daily precision
tracking and model drift detection.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from mcp_server.tools.get_golden_test_results import get_golden_test_results


class TestGetGoldenTestResults:
    """Test cases for get_golden_test_results tool"""

    @pytest.mark.p1
    def test_get_daily_metrics(self, mock_db_connection):
        """
        [P1] Should return daily precision metrics
        """
        # GIVEN: Golden test results for past week
        date = None  # Current date

        # Mock daily metrics
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("2026-01-14", 0.85, 95, 100),
            ("2026-01-13", 0.82, 90, 100),
            ("2026-01-12", 0.88, 88, 100),
            ("2026-01-11", 0.80, 80, 100),
            ("2026-01-10", 0.83, 83, 100),
        ]

        # WHEN: Getting golden test results
        result = get_golden_test_results(mock_db_connection, date)

        # THEN: Should return metrics
        assert "daily_metrics" in result
        assert len(result["daily_metrics"]) == 5
        assert all("date" in m for m in result["daily_metrics"])
        assert all("precision" in m for m in result["daily_metrics"])
        assert all("correct" in m for m in result["daily_metrics"])
        assert all("total" in m for m in result["daily_metrics"])

    @pytest.mark.p1
    def test_detect_model_drift(self, mock_db_connection):
        """
        [P1] Should detect model drift when precision drops significantly
        """
        # GIVEN: Precision metrics showing drift
        date = None

        # Mock metrics with significant drop
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("2026-01-14", 0.45, 45, 100),  # Significant drop
            ("2026-01-13", 0.85, 85, 100),   # Normal
            ("2026-01-12", 0.83, 83, 100),   # Normal
        ]

        # WHEN: Getting results
        result = get_golden_test_results(mock_db_connection, date)

        # THEN: Should detect drift
        assert "drift_detected" in result
        assert result["drift_detected"] is True
        assert "drift_severity" in result
        assert result["drift_severity"] in ["low", "medium", "high", "critical"]
        assert "baseline_precision" in result
        assert "current_precision" in result

    @pytest.mark.p1
    def test_no_drift_when_precision_stable(self, mock_db_connection):
        """
        [P1] Should not detect drift when precision is stable
        """
        # GIVEN: Stable precision metrics
        date = None

        # Mock stable metrics
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("2026-01-14", 0.85, 85, 100),
            ("2026-01-13", 0.84, 84, 100),
            ("2026-01-12", 0.86, 86, 100),
            ("2026-01-11", 0.85, 85, 100),
        ]

        # WHEN: Getting results
        result = get_golden_test_results(mock_db_connection, date)

        # THEN: Should not detect drift
        assert result["drift_detected"] is False
        assert "drift_severity" in result
        assert result["drift_severity"] == "none"

    @pytest.mark.p1
    def test_precision_threshold_validation(self, mock_db_connection):
        """
        [P1] Should validate against minimum precision threshold
        """
        # GIVEN: Golden test threshold (e.g., 0.75)
        date = None
        threshold = 0.75

        # Mock metrics with some below threshold
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("2026-01-14", 0.85, 85, 100),
            ("2026-01-13", 0.72, 72, 100),  # Below threshold
            ("2026-01-12", 0.88, 88, 100),
        ]

        # WHEN: Getting results
        result = get_golden_test_results(mock_db_connection, date)

        # THEN: Should report threshold violations
        assert "threshold_violations" in result
        assert len(result["threshold_violations"]) > 0
        assert all(v["precision"] < threshold for v in result["threshold_violations"])

    @pytest.mark.p1
    def test_calculate_trend(self, mock_db_connection):
        """
        [P1] Should calculate precision trend over time
        """
        # GIVEN: Precision data showing trend
        date = None

        # Mock improving trend
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("2026-01-14", 0.90, 90, 100),
            ("2026-01-13", 0.85, 85, 100),
            ("2026-01-12", 0.80, 80, 100),
            ("2026-01-11", 0.75, 75, 100),
            ("2026-01-10", 0.70, 70, 100),
        ]

        # WHEN: Getting results
        result = get_golden_test_results(mock_db_connection, date)

        # THEN: Should calculate trend
        assert "trend" in result
        assert "direction" in result["trend"]
        assert result["trend"]["direction"] in ["improving", "declining", "stable"]
        assert "slope" in result["trend"]
        assert "correlation" in result["trend"]

    @pytest.mark.p1
    def test_specific_date_query(self, mock_db_connection):
        """
        [P1] Should return results for specific date
        """
        # GIVEN: Specific date query
        date = "2026-01-14"

        # Mock specific date results
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("2026-01-14", 0.85, 85, 100),
        ]

        # WHEN: Getting results for specific date
        result = get_golden_test_results(mock_db_connection, date)

        # THEN: Should return that date's results
        assert "daily_metrics" in result
        assert len(result["daily_metrics"]) == 1
        assert result["daily_metrics"][0]["date"] == "2026-01-14"

    @pytest.mark.p2
    def test_statistics_summary(self, mock_db_connection):
        """
        [P2] Should return statistical summary
        """
        # GIVEN: Historical data
        date = None

        # Mock historical metrics
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("2026-01-14", 0.85, 85, 100),
            ("2026-01-13", 0.82, 82, 100),
            ("2026-01-12", 0.88, 88, 100),
            ("2026-01-11", 0.80, 80, 100),
            ("2026-01-10", 0.83, 83, 100),
        ]

        # WHEN: Getting results
        result = get_golden_test_results(mock_db_connection, date)

        # THEN: Should include statistics
        assert "statistics" in result
        assert "mean_precision" in result["statistics"]
        assert "std_precision" in result["statistics"]
        assert "min_precision" in result["statistics"]
        assert "max_precision" in result["statistics"]
        assert "median_precision" in result["statistics"]


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
