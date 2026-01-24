"""Integration Tests for Story 11.8.2: Shadow Phase Execution und Monitoring

These tests verify the shadow phase monitoring tools (enhanced check_shadow_violations.py,
shadow_phase_report.py, check_shadow_duration.py) work correctly for monitoring and
determining eligibility for enforcing phase.

Story 11.8.2 - Tasks 1-6: Enhanced monitoring, reporting, and documentation.
"""

import os
import subprocess
from datetime import datetime, timezone, timedelta

import asyncpg
import pytest


class TestShadowPhaseMonitoring:
    """Test shadow phase monitoring for Story 11.8.2."""

    @pytest.fixture
    async def test_db(self):
        """Create an asyncpg connection for testing."""
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/test_cognitive_memory",
        )
        try:
            conn = await asyncpg.connect(db_url)
        except Exception as e:
            pytest.skip(f"Could not connect to database: {e}")
            return

        # Manually manage transaction to ensure rollback
        tr = conn.transaction()
        await tr.start()
        try:
            yield conn
        finally:
            # Always rollback - ensures test isolation
            await tr.rollback()
            await conn.close()

    @pytest.fixture
    async def setup_test_projects(self, test_db: asyncpg.Connection):
        """Setup test projects in project_registry and rls_migration_status."""
        # Insert test projects
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES
                ('test-shadow-1', 'Test Shadow 1', 'isolated'),
                ('test-shadow-2', 'Test Shadow 2', 'isolated'),
                ('test-shadow-3', 'Test Shadow 3', 'shared')
            ON CONFLICT (project_id) DO NOTHING
        """)

        # Initialize migration status
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES
                ('test-shadow-1', 'pending'),
                ('test-shadow-2', 'pending'),
                ('test-shadow-3', 'pending')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """)

    async def _get_migration_phase(
        self, conn: asyncpg.Connection, project_id: str
    ) -> str:
        """Helper: Get current migration phase for a project."""
        return await conn.fetchval(
            "SELECT migration_phase FROM rls_migration_status WHERE project_id = $1",
            project_id,
        )

    async def _set_shadow_phase_start(
        self, conn: asyncpg.Connection, project_id: str, days_ago: int
    ) -> None:
        """Helper: Set shadow phase start time to N days ago."""
        past_time = datetime.now(timezone.utc) - timedelta(days=days_ago)
        await conn.execute(
            "UPDATE rls_migration_status SET migration_phase = 'shadow', updated_at = $1 WHERE project_id = $2",
            past_time,
            project_id,
        )

    async def _add_audit_log_entries(
        self, conn: asyncpg.Connection, project_id: str, count: int, would_be_denied: bool
    ) -> None:
        """Helper: Add audit log entries for testing."""
        # Get the shadow start time to use for logged_at
        updated_at = await conn.fetchval(
            "SELECT updated_at FROM rls_migration_status WHERE project_id = $1",
            project_id,
        )

        # Insert audit log entries
        values = [
            f"('nodes', 'SELECT', '{project_id}', 'test-project', ${'TRUE' if would_be_denied else 'FALSE'}, '{updated_at}')"
            for _ in range(count)
        ]

        query = f"""
            INSERT INTO rls_audit_log (
                table_name, operation, project_id, row_project_id,
                would_be_denied, logged_at
            )
            SELECT * FROM (VALUES {', '.join(values)}) AS v(
                table_name, operation, project_id, row_project_id,
                would_be_denied, logged_at
            )
        """
        await conn.execute(query)

    # =========================================================================
    # Task 1: Enhance check_shadow_violations.py with exit criteria validation
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_eligibility_check_with_all_criteria_met(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test eligibility calculation when all exit criteria are met

        GIVEN project in shadow phase for 8 days
        AND 1200 transactions recorded
        AND 0 violations
        WHEN running check_shadow_violations.py --check-eligibility
        THEN project is marked ELIGIBLE for enforcing phase
        """
        # Setup: 8 days in shadow, 1200 transactions, 0 violations
        await self._set_shadow_phase_start(test_db, "test-shadow-1", days_ago=8)
        await self._add_audit_log_entries(test_db, "test-shadow-1", count=1200, would_be_denied=False)

        # Run eligibility check
        result = subprocess.run(
            ["python", "scripts/check_shadow_violations.py", "--project", "test-shadow-1", "--check-eligibility"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Eligibility check failed: {result.stderr}"
        assert "test-shadow-1" in result.stdout
        assert "ELIGIBLE" in result.stdout
        assert "Shadow duration: 8 days" in result.stdout
        assert "Transactions: 1200" in result.stdout
        assert "Violations: 0" in result.stdout

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_eligibility_check_with_violations(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test eligibility calculation with violations

        GIVEN project in shadow phase for 10 days
        AND violations detected in rls_audit_log
        WHEN running check_shadow_violations.py --check-eligibility
        THEN project is marked NOT ELIGIBLE
        AND recommendation is INVESTIGATE violations
        """
        # Setup: 10 days in shadow with violations
        await self._set_shadow_phase_start(test_db, "test-shadow-2", days_ago=10)
        await self._add_audit_log_entries(test_db, "test-shadow-2", count=500, would_be_denied=False)
        await self._add_audit_log_entries(test_db, "test-shadow-2", count=5, would_be_denied=True)

        # Run eligibility check
        result = subprocess.run(
            ["python", "scripts/check_shadow_violations.py", "--project", "test-shadow-2", "--check-eligibility"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Eligibility check failed: {result.stderr}"
        assert "NOT ELIGIBLE" in result.stdout
        assert "INVESTIGATE" in result.stdout
        assert "Violations: 5 detected" in result.stdout

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_eligibility_check_insufficient_duration(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test eligibility calculation with insufficient shadow duration

        GIVEN project in shadow phase for only 3 days
        AND no violations
        WHEN running check_shadow_violations.py --check-eligibility
        THEN project is marked NOT ELIGIBLE due to minimum duration not met
        """
        # Setup: 3 days in shadow (below 7 day minimum)
        await self._set_shadow_phase_start(test_db, "test-shadow-3", days_ago=3)
        await self._add_audit_log_entries(test_db, "test-shadow-3", count=1500, would_be_denied=False)

        # Run eligibility check
        result = subprocess.run(
            ["python", "scripts/check_shadow_violations.py", "--project", "test-shadow-3", "--check-eligibility"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Eligibility check failed: {result.stderr}"
        assert "NOT ELIGIBLE" in result.stdout
        assert "Shadow duration: 3 days (minimum: 7)" in result.stdout

    # =========================================================================
    # Task 2: Create shadow_phase_report.py dashboard script
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shadow_phase_report_multiple_projects(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test shadow phase report with multiple projects

        GIVEN multiple projects in shadow phase
        WHEN running shadow_phase_report.py
        THEN report includes all projects with individual metrics
        AND summary shows eligible count
        """
        # Setup: Different scenarios
        await self._set_shadow_phase_start(test_db, "test-shadow-1", days_ago=8)
        await self._add_audit_log_entries(test_db, "test-shadow-1", count=1200, would_be_denied=False)

        await self._set_shadow_phase_start(test_db, "test-shadow-2", days_ago=5)
        await self._add_audit_log_entries(test_db, "test-shadow-2", count=800, would_be_denied=False)

        # Run report
        result = subprocess.run(
            ["python", "scripts/shadow_phase_report.py"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Report generation failed: {result.stderr}"
        assert "SHADOW PHASE REPORT" in result.stdout
        assert "Total Projects in Shadow: 2" in result.stdout
        assert "test-shadow-1" in result.stdout
        assert "test-shadow-2" in result.stdout

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shadow_phase_report_single_project(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test shadow phase report for single project

        GIVEN project in shadow phase
        WHEN running shadow_phase_report.py --project <id>
        THEN report shows only that project
        """
        await self._set_shadow_phase_start(test_db, "test-shadow-1", days_ago=10)
        await self._add_audit_log_entries(test_db, "test-shadow-1", count=1500, would_be_denied=False)

        result = subprocess.run(
            ["python", "scripts/shadow_phase_report.py", "--project", "test-shadow-1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Report generation failed: {result.stderr}"
        assert "test-shadow-1" in result.stdout
        assert "(isolated)" in result.stdout

    # =========================================================================
    # Task 5: Automated monitoring checks (check_shadow_duration.py)
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shadow_duration_threshold_alert(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test shadow duration threshold alert

        GIVEN project in shadow phase for 15 days (> 14 day max)
        WHEN running check_shadow_duration.py
        THEN alert is generated for exceeding maximum duration
        AND script exits with non-zero status
        """
        # Setup: 15 days in shadow (exceeds 14 day threshold)
        await self._set_shadow_phase_start(test_db, "test-shadow-1", days_ago=15)
        await self._add_audit_log_entries(test_db, "test-shadow-1", count=2000, would_be_denied=False)

        result = subprocess.run(
            ["python", "scripts/check_shadow_duration.py"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, "Should exit with non-zero when alert detected"
        assert "ALERT" in result.stdout
        assert "test-shadow-1" in result.stdout
        assert "Days in Shadow: 15" in result.stdout
        assert "Move to enforcing within 3 business days" in result.stdout

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shadow_duration_no_alert_when_within_threshold(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test no alert when shadow duration within threshold

        GIVEN project in shadow phase for 10 days (< 14 day max)
        WHEN running check_shadow_duration.py
        THEN no alert is generated
        AND script exits with zero status
        """
        # Setup: 10 days in shadow (within threshold)
        await self._set_shadow_phase_start(test_db, "test-shadow-1", days_ago=10)

        result = subprocess.run(
            ["python", "scripts/check_shadow_duration.py"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Should exit with zero when no alerts: {result.stderr}"
        assert "No projects exceeding maximum shadow duration" in result.stdout

    # =========================================================================
    # Task 6: Integration tests for multi-project reporting
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_multi_project_eligibility_calculation(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test eligibility calculation across multiple projects

        GIVEN multiple projects with different eligibility statuses
        WHEN running shadow_phase_report.py
        THEN each project has correct eligibility determination
        """
        # test-shadow-1: ELIGIBLE (8 days, 1200 tx, 0 violations)
        await self._set_shadow_phase_start(test_db, "test-shadow-1", days_ago=8)
        await self._add_audit_log_entries(test_db, "test-shadow-1", count=1200, would_be_denied=False)

        # test-shadow-2: NOT ELIGIBLE (violations)
        await self._set_shadow_phase_start(test_db, "test-shadow-2", days_ago=10)
        await self._add_audit_log_entries(test_db, "test-shadow-2", count=1000, would_be_denied=False)
        await self._add_audit_log_entries(test_db, "test-shadow-2", count=10, would_be_denied=True)

        # test-shadow-3: NOT ELIGIBLE (insufficient duration)
        await self._set_shadow_phase_start(test_db, "test-shadow-3", days_ago=3)
        await self._add_audit_log_entries(test_db, "test-shadow-3", count=2000, would_be_denied=False)

        result = subprocess.run(
            ["python", "scripts/shadow_phase_report.py"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Report failed: {result.stderr}"

        output = result.stdout
        # Check test-shadow-1 is eligible
        assert "test-shadow-1" in output
        assert "ELIGIBLE" in output or "\u2713" in output  # Checkmark or ELIGIBLE

        # Check test-shadow-2 shows violations
        assert "test-shadow-2" in output
        assert "INVESTIGATE" in output

        # Check test-shadow-3 shows insufficient duration
        assert "test-shadow-3" in output
        assert "minimum: 7" in output

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_violation_report_with_correct_columns(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test violation report uses correct schema columns

        GIVEN rls_audit_log has entries with correct column names
        WHEN running check_shadow_violations.py
        THEN report displays violations with correct field names
        """
        await self._set_shadow_phase_start(test_db, "test-shadow-1", days_ago=5)

        # Insert violation with correct column names (session_user, logged_at, row_project_id)
        await test_db.execute("""
            INSERT INTO rls_audit_log (
                table_name, operation, project_id, row_project_id,
                would_be_denied, session_user, logged_at
            )
            VALUES ('nodes', 'SELECT', 'test-shadow-1', 'other-project',
                    TRUE, 'test-user', NOW())
        """)

        result = subprocess.run(
            ["python", "scripts/check_shadow_violations.py", "--project", "test-shadow-1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Violation check failed: {result.stderr}"
        assert "test-shadow-1" in result.stdout
        assert "Total Violations: 1" in result.stdout

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_transaction_count_estimation(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test transaction count estimation from audit log

        GIVEN project in shadow phase with audit log entries
        WHEN running eligibility check
        THEN transaction count matches audit log volume
        """
        await self._set_shadow_phase_start(test_db, "test-shadow-1", days_ago=8)
        await self._add_audit_log_entries(test_db, "test-shadow-1", count=1234, would_be_denied=False)

        result = subprocess.run(
            ["python", "scripts/check_shadow_violations.py", "--project", "test-shadow-1", "--check-eligibility"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Eligibility check failed: {result.stderr}"
        assert "Transactions: 1234" in result.stdout
