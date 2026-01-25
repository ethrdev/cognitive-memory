"""Integration Tests for Story 11.8.3: Enforcing Phase Activation und Validation

These tests verify the enforcing activation script (activate_enforcing.py) correctly:
- Activates enforcing phase following migration sequence
- Validates exit criteria before activation
- Implements rollback capability (enforcing -> pending)
- Handles batch activation with proper error handling

Story 11.8.3 - Task 1: Create enforcing activation script.
"""

import os
import subprocess
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest


class TestEnforcingActivation:
    """Test enforcing activation for Story 11.8.3."""

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
            print(f"⚠️  WARNING: Integration tests require database connection")
            print(f"   Set TEST_DATABASE_URL environment variable or ensure PostgreSQL is running")
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
        # Insert test projects with different access levels
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES
                ('test-enf-1', 'Test Enf 1', 'isolated'),
                ('test-enf-2', 'Test Enf 2', 'isolated'),
                ('test-enf-3', 'Test Enf 3', 'shared'),
                ('test-enf-4', 'Test Enf 4', 'super')
            ON CONFLICT (project_id) DO NOTHING
        """)

        # Initialize migration status to shadow
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES
                ('test-enf-1', 'shadow'),
                ('test-enf-2', 'shadow'),
                ('test-enf-3', 'shadow'),
                ('test-enf-4', 'shadow')
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
        past_time = datetime.now(UTC) - timedelta(days=days_ago)
        await conn.execute(
            "UPDATE rls_migration_status SET migration_phase = 'shadow', updated_at = $1 WHERE project_id = $2",
            past_time,
            project_id,
        )

    async def _add_audit_log_entries(
        self, conn: asyncpg.Connection, project_id: str, count: int, would_be_denied: bool
    ) -> None:
        """Helper: Add audit log entries for testing."""
        updated_at = await conn.fetchval(
            "SELECT updated_at FROM rls_migration_status WHERE project_id = $1",
            project_id,
        )

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
    # Task 1.1: Create activate_enforcing.py with CLI interface
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_activate_enforcing_cli_interface(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test activate_enforcing.py CLI interface exists and runs

        GIVEN activate_enforcing.py script exists
        WHEN running with --help flag
        THEN usage information is displayed
        """
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"CLI help failed: {result.stderr}"
        assert "activate_enforcing.py" in result.stdout
        assert "--project" in result.stdout or "--batch" in result.stdout

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_activate_single_project_to_enforcing(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test single project activation to enforcing

        GIVEN project in shadow phase with all exit criteria met
        WHEN running activate_enforcing.py --project <id>
        THEN project migration_phase changes to 'enforcing'
        """
        # Setup: 8 days in shadow, 1200 transactions, 0 violations
        await self._set_shadow_phase_start(test_db, "test-enf-1", days_ago=8)
        await self._add_audit_log_entries(test_db, "test-enf-1", count=1200, would_be_denied=False)

        # Run activation
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--project", "test-enf-1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Activation failed: {result.stderr}"

        # Verify phase changed
        phase = await self._get_migration_phase(test_db, "test-enf-1")
        assert phase == "enforcing", f"Expected phase 'enforcing', got '{phase}'"

    # =========================================================================
    # Task 1.2: Implement batch activation following migration sequence
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_activation_follows_sequence(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test batch activation respects migration sequence

        GIVEN multiple projects in shadow phase
        WHEN running activate_enforcing.py --batch with project list
        THEN all projects are activated in provided order
        """
        # Setup: All projects eligible
        for proj in ["test-enf-1", "test-enf-2", "test-enf-3"]:
            await self._set_shadow_phase_start(test_db, proj, days_ago=8)
            await self._add_audit_log_entries(test_db, proj, count=1200, would_be_denied=False)

        # Run batch activation
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--batch", "test-enf-1,test-enf-2,test-enf-3"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Batch activation failed: {result.stderr}"

        # Verify all projects activated
        for proj in ["test-enf-1", "test-enf-2", "test-enf-3"]:
            phase = await self._get_migration_phase(test_db, proj)
            assert phase == "enforcing", f"Project {proj} not activated: {phase}"

    # =========================================================================
    # Task 1.3: Add validation checks before activation
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validation_fails_with_violations(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test activation fails when violations exist

        GIVEN project in shadow phase with violations
        WHEN running activate_enforcing.py --project <id>
        THEN activation is rejected
        AND error message mentions violations
        """
        # Setup: 8 days in shadow but has violations
        await self._set_shadow_phase_start(test_db, "test-enf-1", days_ago=8)
        await self._add_audit_log_entries(test_db, "test-enf-1", count=1200, would_be_denied=False)
        await self._add_audit_log_entries(test_db, "test-enf-1", count=5, would_be_denied=True)

        # Run activation (should fail)
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--project", "test-enf-1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, "Should fail when violations exist"
        assert "violation" in result.stdout.lower() or "violation" in result.stderr.lower()

        # Verify phase did NOT change
        phase = await self._get_migration_phase(test_db, "test-enf-1")
        assert phase == "shadow", f"Phase should remain 'shadow', got '{phase}'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validation_fails_insufficient_duration(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test activation fails with insufficient shadow duration

        GIVEN project in shadow phase for only 3 days (< 7 minimum)
        WHEN running activate_enforcing.py --project <id>
        THEN activation is rejected
        AND error message mentions minimum duration
        """
        # Setup: Only 3 days in shadow
        await self._set_shadow_phase_start(test_db, "test-enf-1", days_ago=3)
        await self._add_audit_log_entries(test_db, "test-enf-1", count=1500, would_be_denied=False)

        # Run activation (should fail)
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--project", "test-enf-1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, "Should fail with insufficient duration"
        assert "day" in result.stdout.lower() or "day" in result.stderr.lower()

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_validation_fails_insufficient_transactions(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test activation fails with insufficient transaction count

        GIVEN project in shadow phase with < 1000 transactions
        WHEN running activate_enforcing.py --project <id>
        THEN activation is rejected
        AND error message mentions transaction count
        """
        # Setup: 8 days but only 500 transactions
        await self._set_shadow_phase_start(test_db, "test-enf-1", days_ago=8)
        await self._add_audit_log_entries(test_db, "test-enf-1", count=500, would_be_denied=False)

        # Run activation (should fail)
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--project", "test-enf-1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, "Should fail with insufficient transactions"
        assert "transaction" in result.stdout.lower() or "transaction" in result.stderr.lower()

    # =========================================================================
    # Task 1.4: Implement rollback capability (enforcing -> pending)
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_from_enforcing_to_pending(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test rollback from enforcing to pending phase

        GIVEN project in enforcing phase
        WHEN running activate_enforcing.py --project <id> --rollback
        THEN project migration_phase changes to 'pending'
        """
        # Setup: Project in enforcing phase
        await test_db.execute(
            "UPDATE rls_migration_status SET migration_phase = 'enforcing' WHERE project_id = $1",
            "test-enf-1"
        )

        # Run rollback
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--project", "test-enf-1", "--rollback"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Rollback failed: {result.stderr}"

        # Verify phase changed to pending
        phase = await self._get_migration_phase(test_db, "test-enf-1")
        assert phase == "pending", f"Expected phase 'pending' after rollback, got '{phase}'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_batch_projects(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test batch rollback of multiple projects

        GIVEN multiple projects in enforcing phase
        WHEN running activate_enforcing.py --batch --rollback
        THEN all projects revert to 'pending' phase
        """
        # Setup: All projects in enforcing
        for proj in ["test-enf-1", "test-enf-2", "test-enf-3"]:
            await test_db.execute(
                "UPDATE rls_migration_status SET migration_phase = 'enforcing' WHERE project_id = $1",
                proj
            )

        # Run batch rollback
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--batch", "test-enf-1,test-enf-2,test-enf-3", "--rollback"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Batch rollback failed: {result.stderr}"

        # Verify all projects rolled back
        for proj in ["test-enf-1", "test-enf-2", "test-enf-3"]:
            phase = await self._get_migration_phase(test_db, proj)
            assert phase == "pending", f"Project {proj} not rolled back: {phase}"

    # =========================================================================
    # Task 1.1: Dry-run mode for testing
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dry_run_mode_does_not_modify_database(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test dry-run mode shows what would happen without changes

        GIVEN project eligible for enforcing activation
        WHEN running activate_enforcing.py --project <id> --dry-run
        THEN eligibility is reported
        BUT phase is NOT changed
        """
        # Setup: Eligible project
        await self._set_shadow_phase_start(test_db, "test-enf-1", days_ago=8)
        await self._add_audit_log_entries(test_db, "test-enf-1", count=1200, would_be_denied=False)

        initial_phase = await self._get_migration_phase(test_db, "test-enf-1")

        # Run dry-run
        result = subprocess.run(
            ["python", "scripts/activate_enforcing.py", "--project", "test-enf-1", "--dry-run"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Dry-run failed: {result.stderr}"
        assert "dry-run" in result.stdout.lower() or "eligible" in result.stdout.lower()

        # Verify phase did NOT change
        final_phase = await self._get_migration_phase(test_db, "test-enf-1")
        assert final_phase == initial_phase, "Phase should not change in dry-run mode"
        assert final_phase == "shadow", "Phase should still be 'shadow'"
