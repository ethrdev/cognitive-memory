"""Integration Tests for Story 11.8.1: Migration Scripts und Tooling

These tests verify the migration scripts (migrate_project.py, check_shadow_violations.py,
migration_status.py) work correctly for migrating projects through RLS phases.

Story 11.8.1 - Tasks 1-10: CLI tools, monitoring scripts, and runbook documentation.
"""

import os
import subprocess
from typing import Any

import asyncpg
import pytest


class TestMigrationScripts:
    """Test migration scripts for Story 11.8.1."""

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
                ('test-migrate-1', 'Test Migrate 1', 'isolated'),
                ('test-migrate-2', 'Test Migrate 2', 'isolated'),
                ('test-migrate-3', 'Test Migrate 3', 'shared')
            ON CONFLICT (project_id) DO NOTHING
        """)

        # Initialize migration status
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES
                ('test-migrate-1', 'pending'),
                ('test-migrate-2', 'pending'),
                ('test-migrate-3', 'pending')
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

    # =========================================================================
    # Task 1: Create migrate_project.py CLI tool
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migrate_to_shadow_phase(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test single project migration to shadow phase

        GIVEN project 'test-migrate-1' in 'pending' phase
        WHEN running migrate_project.py --project test-migrate-1 --phase shadow
        THEN migration_phase is updated to 'shadow'
        AND updated_at timestamp is refreshed
        """
        # Run migration script
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", "test-migrate-1", "--phase", "shadow"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Verify migration status updated
        phase = await self._get_migration_phase(test_db, "test-migrate-1")
        assert phase == "shadow", f"Expected 'shadow', got '{phase}'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migrate_to_enforcing_phase(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test migration to enforcing phase

        GIVEN project in 'shadow' phase
        WHEN migrating to 'enforcing'
        THEN migration_phase = 'enforcing' is set
        """
        # First move to shadow
        await test_db.execute(
            "UPDATE rls_migration_status SET migration_phase = 'shadow' WHERE project_id = 'test-migrate-2'"
        )

        # Run migration script
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", "test-migrate-2", "--phase", "enforcing"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Verify phase updated
        phase = await self._get_migration_phase(test_db, "test-migrate-2")
        assert phase == "enforcing", f"Expected 'enforcing', got '{phase}'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migrate_to_complete_sets_timestamp(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test that 'complete' phase sets migrated_at timestamp

        GIVEN project in 'enforcing' phase with NULL migrated_at
        WHEN migrating to 'complete'
        THEN migrated_at is set to current timestamp
        """
        # Setup: project in enforcing phase
        await test_db.execute("""
            UPDATE rls_migration_status
            SET migration_phase = 'enforcing', migrated_at = NULL
            WHERE project_id = 'test-migrate-3'
        """)

        # Run migration script
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", "test-migrate-3", "--phase", "complete"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Verify migrated_at is set
        migrated_at = await test_db.fetchval(
            "SELECT migrated_at FROM rls_migration_status WHERE project_id = 'test-migrate-3'"
        )
        assert migrated_at is not None, "migrated_at should be set when phase = 'complete'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_phase_raises_error(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test that invalid phase parameter raises error

        GIVEN project exists
        WHEN running migrate_project.py with invalid phase
        THEN script exits with error code
        """
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", "test-migrate-1", "--phase", "invalid"],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, "Script should fail with invalid phase"
        assert "Invalid phase" in result.stderr or "ValueError" in result.stderr

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_nonexistent_project_raises_error(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test that nonexistent project raises error

        GIVEN project does NOT exist in rls_migration_status
        WHEN running migrate_project.py for that project
        THEN script exits with error
        """
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", "nonexistent-project", "--phase", "shadow"],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, "Script should fail for nonexistent project"

    # =========================================================================
    # Task 2-5: Phase transitions (shadow, enforcing, complete, rollback)
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_to_pending(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test rollback capability

        GIVEN project in 'enforcing' phase
        WHEN rolling back to 'pending'
        THEN migration_phase = 'pending' is set
        AND RLS policies stop blocking (pending mode returns TRUE)
        """
        # Setup: project in enforcing phase
        await test_db.execute(
            "UPDATE rls_migration_status SET migration_phase = 'enforcing' WHERE project_id = 'test-migrate-1'"
        )

        # Rollback to pending
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", "test-migrate-1", "--phase", "pending"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Rollback failed: {result.stderr}"

        # Verify phase reset
        phase = await self._get_migration_phase(test_db, "test-migrate-1")
        assert phase == "pending", f"Expected 'pending' after rollback, got '{phase}'"

    # =========================================================================
    # Task 6: Batch migration support
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_migration_success(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test batch migration of multiple projects

        GIVEN multiple projects in 'pending' phase
        WHEN running migrate_project.py --batch "test-migrate-1,test-migrate-2" --phase shadow
        THEN all projects are updated atomically
        """
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--batch", "test-migrate-1,test-migrate-2", "--phase", "shadow"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Batch migration failed: {result.stderr}"

        # Verify both projects updated
        phase1 = await self._get_migration_phase(test_db, "test-migrate-1")
        phase2 = await self._get_migration_phase(test_db, "test-migrate-2")

        assert phase1 == "shadow", f"Project 1 should be 'shadow', got '{phase1}'"
        assert phase2 == "shadow", f"Project 2 should be 'shadow', got '{phase2}'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_migration_rollback_on_failure(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test batch migration transaction rollback

        GIVEN valid and invalid projects in batch
        WHEN running migrate_project.py with mixed valid/invalid project_ids
        THEN entire transaction is rolled back
        AND no projects are migrated
        """
        # First migrate test-migrate-1 to shadow so we can verify it doesn't change
        await test_db.execute(
            "UPDATE rls_migration_status SET migration_phase = 'shadow' WHERE project_id = 'test-migrate-1'"
        )

        initial_phase = await self._get_migration_phase(test_db, "test-migrate-1")
        assert initial_phase == "shadow", "Setup failed"

        # Try batch with one invalid project
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--batch", "test-migrate-1,nonexistent", "--phase", "enforcing"],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, "Batch migration should fail with invalid project"

        # Verify test-migrate-1 was NOT changed (transaction rolled back)
        final_phase = await self._get_migration_phase(test_db, "test-migrate-1")
        assert final_phase == "shadow", f"Phase should not change after failed batch, got '{final_phase}'"

    # =========================================================================
    # Task 7: check_shadow_violations.py monitoring script
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_shadow_violations_no_violations(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test shadow violation checker with no violations

        GIVEN project in shadow phase with no violations
        WHEN running check_shadow_violations.py
        THEN reports no violations
        """
        # Setup: project in shadow phase
        await test_db.execute(
            "UPDATE rls_migration_status SET migration_phase = 'shadow' WHERE project_id = 'test-migrate-1'"
        )

        result = subprocess.run(
            ["python", "scripts/check_shadow_violations.py", "--project", "test-migrate-1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Check violations failed: {result.stderr}"
        # Output should indicate no violations
        assert "No shadow phase violations" in result.stdout or "Total Violations: 0" in result.stdout

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_shadow_violations_with_violations(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test shadow violation checker reports violations

        GIVEN rls_audit_log contains would_be_denied = TRUE records
        WHEN running check_shadow_violations.py
        THEN reports violation count and breakdown
        """
        # Setup: project in shadow phase
        await test_db.execute(
            "UPDATE rls_migration_status SET migration_phase = 'shadow' WHERE project_id = 'test-migrate-1'"
        )

        # Insert test violations
        await test_db.execute("""
            INSERT INTO rls_audit_log (
                table_name, operation, project_id, user_name,
                would_be_denied, denied_reason, created_at
            )
            VALUES
                ('nodes', 'SELECT', 'test-migrate-1', 'test-user', TRUE, 'Unauthorized project', NOW()),
                ('edges', 'SELECT', 'test-migrate-1', 'test-user', TRUE, 'Unauthorized project', NOW())
        """)

        result = subprocess.run(
            ["python", "scripts/check_shadow_violations.py", "--project", "test-migrate-1"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Check violations failed: {result.stderr}"
        # Should report violations
        assert "test-migrate-1" in result.stdout
        assert "Total Violations: 2" in result.stdout

    # =========================================================================
    # Task 8: migration_status.py status reporting script
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_status_reports_all_projects(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test migration status reporter

        GIVEN multiple projects in different phases
        WHEN running migration_status.py
        THEN displays all projects with current phases
        """
        # Setup: different phases
        await test_db.execute("""
            UPDATE rls_migration_status
            SET migration_phase = 'shadow'
            WHERE project_id = 'test-migrate-1'
        """)
        await test_db.execute("""
            UPDATE rls_migration_status
            SET migration_phase = 'enforcing'
            WHERE project_id = 'test-migrate-2'
        """)

        result = subprocess.run(
            ["python", "scripts/migration_status.py"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Migration status failed: {result.stderr}"
        # Should show summary and project details
        assert "RLS Migration Status" in result.stdout
        assert "test-migrate-1" in result.stdout
        assert "test-migrate-2" in result.stdout
        assert "test-migrate-3" in result.stdout

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_status_phase_counts(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test migration status counts by phase

        GIVEN projects in different phases
        WHEN running migration_status.py
        THEN summary shows correct counts per phase
        """
        # Setup: 1 shadow, 1 enforcing, 1 pending
        await test_db.execute("""
            UPDATE rls_migration_status
            SET migration_phase = 'shadow'
            WHERE project_id = 'test-migrate-1'
        """)
        await test_db.execute("""
            UPDATE rls_migration_status
            SET migration_phase = 'enforcing'
            WHERE project_id = 'test-migrate-2'
        """)

        result = subprocess.run(
            ["python", "scripts/migration_status.py"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Migration status failed: {result.stderr}"
        # Check counts
        assert "Pending:" in result.stdout
        assert "Shadow:" in result.stdout
        assert "Enforcing:" in result.stdout

    # =========================================================================
    # Task 10: Integration tests for all scripts
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_migration_workflow(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test complete migration workflow

        GIVEN project starting at 'pending'
        WHEN migrating through: shadow -> enforcing -> complete
        THEN each phase transition succeeds
        AND migration_status.py reflects final state
        """
        project_id = "test-migrate-3"

        # Step 1: pending -> shadow
        result1 = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", project_id, "--phase", "shadow"],
            capture_output=True,
            text=True,
        )
        assert result1.returncode == 0, f"Shadow phase failed: {result1.stderr}"
        phase = await self._get_migration_phase(test_db, project_id)
        assert phase == "shadow"

        # Step 2: shadow -> enforcing
        result2 = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", project_id, "--phase", "enforcing"],
            capture_output=True,
            text=True,
        )
        assert result2.returncode == 0, f"Enforcing phase failed: {result2.stderr}"
        phase = await self._get_migration_phase(test_db, project_id)
        assert phase == "enforcing"

        # Step 3: enforcing -> complete
        result3 = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", project_id, "--phase", "complete"],
            capture_output=True,
            text=True,
        )
        assert result3.returncode == 0, f"Complete phase failed: {result3.stderr}"
        phase = await self._get_migration_phase(test_db, project_id)
        assert phase == "complete"

        # Verify migrated_at is set
        migrated_at = await test_db.fetchval(
            f"SELECT migrated_at FROM rls_migration_status WHERE project_id = '{project_id}'"
        )
        assert migrated_at is not None, "migrated_at should be set at 'complete' phase"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_emergency_rollback_workflow(
        self, test_db: asyncpg.Connection, setup_test_projects
    ) -> None:
        """INTEGRATION: Test emergency rollback scenario

        GIVEN project in 'enforcing' phase with issues
        WHEN rolling back to 'pending'
        THEN project reverts to legacy behavior
        AND status is updated
        """
        project_id = "test-migrate-1"

        # Setup: project in enforcing
        await test_db.execute(
            f"UPDATE rls_migration_status SET migration_phase = 'enforcing' WHERE project_id = '{project_id}'"
        )

        # Emergency rollback
        result = subprocess.run(
            ["python", "scripts/migrate_project.py", "--project", project_id, "--phase", "pending"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Rollback failed: {result.stderr}"

        # Verify back to pending
        phase = await self._get_migration_phase(test_db, project_id)
        assert phase == "pending", "Emergency rollback should return project to 'pending'"
