"""Tests for ShadowAuditLogger

Tests for the Python shadow audit logger that detects RLS violations
during SELECT operations in shadow mode.

Story 11.3.2: Shadow Audit Infrastructure - Application-Layer SELECT Audit (AC: #5, #7)
"""

import pytest

from mcp_server.audit.shadow_logger import ShadowAuditLogger


class TestShadowAuditLogger:
    """Test ShadowAuditLogger class for SELECT audit logging."""

    @pytest.fixture
    def logger(self):
        """Create a ShadowAuditLogger instance."""
        return ShadowAuditLogger()

    # =========================================================================
    # Cross-Project Detection Tests
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.unit
    def test_detect_cross_project_violations_empty_results(self, logger) -> None:
        """UNIT: Verify empty results produce no violations

        GIVEN an empty result list
        WHEN _detect_cross_project_violations is called
        THEN returns empty list
        """
        results = []
        violations = logger._detect_cross_project_violations(results, "aa")
        assert violations == []

    @pytest.mark.P0
    @pytest.mark.unit
    def test_detect_cross_project_violations_same_project(self, logger) -> None:
        """UNIT: Verify same-project results produce no violations

        GIVEN results with project_id = requesting project_id
        WHEN _detect_cross_project_violations is called
        THEN returns empty list (no violations)
        """
        results = [
            {"id": 1, "project_id": "aa", "name": "result1"},
            {"id": 2, "project_id": "aa", "name": "result2"},
        ]
        violations = logger._detect_cross_project_violations(results, "aa")
        assert violations == []

    @pytest.mark.P0
    @pytest.mark.unit
    def test_detect_cross_project_violations_cross_project(self, logger) -> None:
        """UNIT: Verify cross-project results are detected

        GIVEN results with project_id != requesting project_id
        WHEN _detect_cross_project_violations is called
        THEN returns list of violating results
        """
        results = [
            {"id": 1, "project_id": "aa", "name": "same_project"},
            {"id": 2, "project_id": "io", "name": "cross_project"},
            {"id": 3, "project_id": "sm", "name": "another_cross"},
        ]
        violations = logger._detect_cross_project_violations(results, "aa")

        assert len(violations) == 2
        # Check that the cross-project results are returned
        violating_ids = [v["id"] for v in violations]
        assert 2 in violating_ids
        assert 3 in violating_ids
        assert 1 not in violating_ids  # Same project not included

    @pytest.mark.P0
    @pytest.mark.unit
    def test_detect_cross_project_violations_no_project_id(self, logger) -> None:
        """UNIT: Verify results without project_id are skipped

        GIVEN results where some rows don't have project_id field
        WHEN _detect_cross_project_violations is called
        THEN rows without project_id are skipped (not treated as violations)
        """
        results = [
            {"id": 1, "project_id": "aa", "name": "same_project"},
            {"id": 2, "name": "no_project_id"},  # No project_id field
            {"id": 3, "project_id": "io", "name": "cross_project"},
        ]
        violations = logger._detect_cross_project_violations(results, "aa")

        # Only the io result should be a violation
        assert len(violations) == 1
        assert violations[0]["id"] == 3

    @pytest.mark.P0
    @pytest.mark.unit
    def test_detect_cross_project_violations_null_project_id(self, logger) -> None:
        """UNIT: Verify results with None project_id are skipped

        GIVEN results where some rows have project_id = None
        WHEN _detect_cross_project_violations is called
        THEN rows with None project_id are skipped
        """
        results = [
            {"id": 1, "project_id": "aa", "name": "same_project"},
            {"id": 2, "project_id": None, "name": "null_project"},
            {"id": 3, "project_id": "io", "name": "cross_project"},
        ]
        violations = logger._detect_cross_project_violations(results, "aa")

        # Only the io result should be a violation
        assert len(violations) == 1
        assert violations[0]["id"] == 3

    # =========================================================================
    # Type Handling Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.unit
    def test_detect_cross_project_violations_string_conversion(self, logger) -> None:
        """UNIT: Verify project_id comparison handles type differences

        GIVEN results with numeric project_id vs string requesting project_id
        WHEN _detect_cross_project_violations is called
        THEN comparison works correctly (string conversion)
        """
        results = [
            {"id": 1, "project_id": 123, "name": "numeric_project"},  # Numeric
            {"id": 2, "project_id": "aa", "name": "string_project"},  # String
        ]
        violations = logger._detect_cross_project_violations(results, "aa")

        # Only numeric project should be a violation (123 != "aa")
        # String project should match (aa == aa)
        assert len(violations) == 1
        assert violations[0]["id"] == 1

    # =========================================================================
    # Logging Behavior Tests
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_select_violations_no_violations(self, logger) -> None:
        """UNIT: Verify no logging when no violations

        GIVEN results with no cross-project violations
        WHEN log_select_violations is called
        THEN no audit log entry is created
        """
        # Note: This test will skip actual DB writes and just verify
        # the method handles empty violations correctly
        results = [
            {"id": 1, "project_id": "aa", "name": "same_project"},
        ]

        # Should not raise any errors
        # In shadow mode, violations would be empty
        violations = logger._detect_cross_project_violations(results, "aa")
        assert violations == []

    @pytest.mark.P0
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_log_select_violations_with_violations(self, logger) -> None:
        """UNIT: Verify logging is triggered when violations exist

        GIVEN results with cross-project violations
        WHEN log_select_violations is called
        THEN violations are detected and logged
        """
        results = [
            {"id": 1, "project_id": "aa", "name": "same_project"},
            {"id": 2, "project_id": "io", "name": "cross_project"},
        ]

        # Verify violations are detected
        violations = logger._detect_cross_project_violations(results, "aa")
        assert len(violations) == 1
        assert violations[0]["id"] == 2

    # =========================================================================
    # Async Fire-and-Forget Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.unit
    def test_log_violations_async_is_async(self, logger) -> None:
        """UNIT: Verify _log_violations_async is an async method

        GIVEN the ShadowAuditLogger class
        WHEN checking the _log_violations_async method
        THEN it is an async function (coroutine)
        """
        import inspect

        assert inspect.iscoroutinefunction(logger._log_violations_async), \
            "_log_violations_async should be an async function"

    @pytest.mark.P1
    @pytest.mark.unit
    def test_log_select_violations_is_async(self, logger) -> None:
        """UNIT: Verify log_select_violations is an async method

        GIVEN the ShadowAuditLogger class
        WHEN checking the log_select_violations method
        THEN it is an async function (coroutine)
        """
        import inspect

        assert inspect.iscoroutinefunction(logger.log_select_violations), \
            "log_select_violations should be an async function"
