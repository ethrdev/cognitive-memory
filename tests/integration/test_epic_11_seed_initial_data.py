"""Tests for Story 11.2.4: Seed Initial Data

These tests verify the migration seeds the project_registry,
project_read_permissions, and rls_migration_status tables with
the correct initial data for all 8 known projects.

Uses asyncpg with its own fixture (not the global psycopg2 conn fixture).
"""

import os
from pathlib import Path

import asyncpg
import pytest


class TestSeedInitialData:
    """Test Migration 033: Seed Initial Project Data."""

    @pytest.fixture
    async def test_db(self):
        """Create an asyncpg connection for testing.

        Uses TEST_DATABASE_URL or falls back to default test database.
        Each test runs in a transaction that is rolled back.
        Uses context manager pattern for safe transaction handling.
        """
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/test_cognitive_memory"
        )
        try:
            conn = await asyncpg.connect(db_url)
        except Exception as e:
            pytest.skip(f"Could not connect to database: {e}")
            return

        # Use context manager for safe transaction handling
        async with conn.transaction():
            yield conn

        await conn.close()

    @pytest.fixture
    def migration_path(self) -> Path:
        """Path to the migration SQL file."""
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "033_seed_initial_projects.sql"
        assert path.exists(), f"Migration file not found at {path}"
        return path

    @pytest.fixture
    def rollback_path(self) -> Path:
        """Path to the rollback SQL file."""
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "033_seed_initial_projects_rollback.sql"
        assert path.exists(), f"Rollback file not found at {path}"
        return path

    @pytest.fixture
    async def setup_tables(self, test_db):
        """Ensure prerequisite tables exist (from migrations 030, 031, 032).

        This fixture runs migrations 030, 031, and 032 to create the tables
        that migration 033 depends on.
        """
        migrations_dir = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations"

        # Run migration 030 (project_registry)
        migration_030 = migrations_dir / "030_create_project_registry.sql"
        if migration_030.exists():
            await test_db.execute(migration_030.read_text())

        # Run migration 031 (project_read_permissions)
        migration_031 = migrations_dir / "031_create_project_read_permissions.sql"
        if migration_031.exists():
            await test_db.execute(migration_031.read_text())

        # Run migration 032 (rls_migration_status)
        migration_032 = migrations_dir / "032_create_rls_migration_status.sql"
        if migration_032.exists():
            await test_db.execute(migration_032.read_text())

    async def _run_migration(self, conn: asyncpg.Connection, sql_path: Path) -> None:
        """Execute a migration SQL file."""
        sql = sql_path.read_text()
        # Execute as single script (handles SET/RESET statements properly)
        await conn.execute(sql)

    # =========================================================================
    # AC1: Project Registry Seeded
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_project_registry_has_8_projects(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify project_registry contains exactly 8 projects (AC1)

        GIVEN migration 033 has been applied
        WHEN counting projects in project_registry
        THEN exactly 8 projects exist
        """
        await self._run_migration(test_db, migration_path)

        count = await test_db.fetchval("""
            SELECT COUNT(*) FROM project_registry
        """)

        assert count == 8, f"Expected 8 projects, found {count}"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_project_registry_access_levels(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify each project has correct access_level (AC1)

        GIVEN migration 033 has been applied
        WHEN querying project_registry
        THEN each project has the expected access_level
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch("""
            SELECT project_id, name, access_level
            FROM project_registry
            ORDER BY project_id
        """)

        expected = {
            'io': ('I/O System', 'super'),
            'echo': ('Echo', 'super'),
            'ea': ('Echo Assistant', 'super'),
            'ab': ('Application Builder', 'shared'),
            'aa': ('Application Assistant', 'shared'),
            'bap': ('bmad-audit-polish', 'shared'),
            'motoko': ('Motoko', 'isolated'),
            'sm': ('Semantic Memory', 'isolated'),
        }

        actual = {row['project_id']: (row['name'], row['access_level']) for row in result}

        assert actual == expected, f"Project data mismatch. Expected {expected}, got {actual}"

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_super_projects_can_read_all(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify SUPER projects have implicit read-all access

        GIVEN migration 033 has been applied
        WHEN checking access_level
        THEN io, echo, ea have access_level='super'
        """
        await self._run_migration(test_db, migration_path)

        super_projects = await test_db.fetch("""
            SELECT project_id FROM project_registry
            WHERE access_level = 'super'
            ORDER BY project_id
        """)

        project_ids = [row['project_id'] for row in super_projects]
        assert project_ids == ['ea', 'echo', 'io'], f"Expected super projects ['ea', 'echo', 'io'], got {project_ids}"

    # =========================================================================
    # AC2: Project Read Permissions Seeded
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_project_read_permissions_count(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify project_read_permissions has 3 entries (AC2)

        GIVEN migration 033 has been applied
        WHEN counting permissions in project_read_permissions
        THEN exactly 3 permissions exist (ab->sm, aa->sm, bap->sm)
        """
        await self._run_migration(test_db, migration_path)

        count = await test_db.fetchval("""
            SELECT COUNT(*) FROM project_read_permissions
        """)

        assert count == 3, f"Expected 3 permissions, found {count}"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shared_projects_can_read_semantic_memory(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify all SHARED projects can read 'sm' (AC2)

        GIVEN migration 033 has been applied
        WHEN querying project_read_permissions
        THEN ab, aa, and bap can all read sm
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch("""
            SELECT reader_project_id, target_project_id
            FROM project_read_permissions
            ORDER BY reader_project_id
        """)

        permissions = [(row['reader_project_id'], row['target_project_id']) for row in result]

        assert ('ab', 'sm') in permissions, "Application Builder should read Semantic Memory"
        assert ('aa', 'sm') in permissions, "Application Assistant should read Semantic Memory"
        assert ('bap', 'sm') in permissions, "bmad-audit-polish should read Semantic Memory"

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_isolated_projects_have_no_read_permissions(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify ISOLATED projects have no read permissions

        GIVEN migration 033 has been applied
        WHEN querying project_read_permissions
        THEN motoko and sm have no read permissions entries
        AND no project has read access to motoko
        """
        await self._run_migration(test_db, migration_path)

        # Verify motoko and sm are not readers
        readers = await test_db.fetch("""
            SELECT DISTINCT reader_project_id FROM project_read_permissions
            ORDER BY reader_project_id
        """)

        reader_ids = [row['reader_project_id'] for row in readers]
        assert 'motoko' not in reader_ids, "motoko should not be a reader"
        assert 'sm' not in reader_ids, "sm should not be a reader"

        # Verify no one has read access to motoko
        motoko_targets = await test_db.fetchval("""
            SELECT COUNT(*) FROM project_read_permissions
            WHERE target_project_id = 'motoko'
        """)
        assert motoko_targets == 0, "No project should have read access to motoko"

    # =========================================================================
    # AC3: RLS Migration Status Seeded
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_migration_status_initialized(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify all 8 projects have rls_migration_status entries (AC3)

        GIVEN migration 033 has been applied
        WHEN querying rls_migration_status
        THEN all 8 projects have status entries
        AND all have rls_enabled=FALSE and migration_phase='pending'
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch("""
            SELECT project_id, rls_enabled, migration_phase
            FROM rls_migration_status
            ORDER BY project_id
        """)

        assert len(result) == 8, f"Expected 8 status entries, found {len(result)}"

        for row in result:
            assert row['rls_enabled'] is False, f"Project {row['project_id']} should have rls_enabled=FALSE"
            assert row['migration_phase'] == 'pending', f"Project {row['project_id']} should have migration_phase='pending'"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_migration_status_all_projects(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify all 8 project_ids have status entries

        GIVEN migration 033 has been applied
        WHEN querying rls_migration_status
        THEN all 8 project_ids (io, echo, ea, ab, aa, bap, motoko, sm) exist
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch("""
            SELECT project_id FROM rls_migration_status
            ORDER BY project_id
        """)

        project_ids = [row['project_id'] for row in result]
        expected_ids = ['aa', 'ab', 'bap', 'ea', 'echo', 'io', 'motoko', 'sm']

        assert project_ids == expected_ids, f"Expected project_ids {expected_ids}, got {project_ids}"

    # =========================================================================
    # AC4: Idempotency - Critical Requirement
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify running seed twice creates no duplicates (AC4)

        GIVEN migration 033 has been applied
        WHEN running the seed INSERT statements again
        THEN no duplicate entries are created
        AND row counts remain unchanged
        """
        # Run migration first time
        await self._run_migration(test_db, migration_path)

        # Get initial counts
        project_count = await test_db.fetchval("SELECT COUNT(*) FROM project_registry")
        permission_count = await test_db.fetchval("SELECT COUNT(*) FROM project_read_permissions")
        status_count = await test_db.fetchval("SELECT COUNT(*) FROM rls_migration_status")

        # Re-run all INSERT statements from migration 033
        for project_id, name, access_level in [
            ('io', 'I/O System', 'super'),
            ('echo', 'Echo', 'super'),
            ('ea', 'Echo Assistant', 'super'),
            ('ab', 'Application Builder', 'shared'),
            ('aa', 'Application Assistant', 'shared'),
            ('bap', 'bmad-audit-polish', 'shared'),
            ('motoko', 'Motoko', 'isolated'),
            ('sm', 'Semantic Memory', 'isolated'),
        ]:
            await test_db.execute("""
                INSERT INTO project_registry (project_id, name, access_level)
                VALUES ($1, $2, $3)
                ON CONFLICT (project_id) DO NOTHING
            """, project_id, name, access_level)

        for reader, target in [('ab', 'sm'), ('aa', 'sm'), ('bap', 'sm')]:
            await test_db.execute("""
                INSERT INTO project_read_permissions (reader_project_id, target_project_id)
                VALUES ($1, $2)
                ON CONFLICT (reader_project_id, target_project_id) DO NOTHING
            """, reader, target)

        for project_id in ['io', 'echo', 'ea', 'ab', 'aa', 'bap', 'motoko', 'sm']:
            await test_db.execute("""
                INSERT INTO rls_migration_status (project_id, migration_phase)
                VALUES ($1, 'pending')
                ON CONFLICT (project_id) DO NOTHING
            """, project_id)

        # Verify counts unchanged
        new_project_count = await test_db.fetchval("SELECT COUNT(*) FROM project_registry")
        new_permission_count = await test_db.fetchval("SELECT COUNT(*) FROM project_read_permissions")
        new_status_count = await test_db.fetchval("SELECT COUNT(*) FROM rls_migration_status")

        assert new_project_count == project_count, "Project count should not change on re-run"
        assert new_permission_count == permission_count, "Permission count should not change on re-run"
        assert new_status_count == status_count, "Status count should not change on re-run"

    # =========================================================================
    # AC5: Rollback Script Available
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_removes_all_seeded_data(self, test_db, setup_tables, migration_path, rollback_path) -> None:
        """INTEGRATION: Verify rollback removes all seeded data (AC5)

        GIVEN migration 033 has been applied
        WHEN rollback script is executed
        THEN all seeded data is removed
        """
        # Run migration first
        await self._run_migration(test_db, migration_path)

        # Get initial counts
        project_count_before = await test_db.fetchval("SELECT COUNT(*) FROM project_registry")
        permission_count_before = await test_db.fetchval("SELECT COUNT(*) FROM project_read_permissions")
        status_count_before = await test_db.fetchval("SELECT COUNT(*) FROM rls_migration_status")

        # Verify data was seeded
        assert project_count_before >= 8, "At least 8 projects should exist after migration"
        assert permission_count_before >= 3, "At least 3 permissions should exist after migration"
        assert status_count_before >= 8, "At least 8 status entries should exist after migration"

        # Execute rollback
        await self._run_migration(test_db, rollback_path)

        # Verify all seeded data removed
        project_count_after = await test_db.fetchval("SELECT COUNT(*) FROM project_registry")
        permission_count_after = await test_db.fetchval("SELECT COUNT(*) FROM project_read_permissions")
        status_count_after = await test_db.fetchval("SELECT COUNT(*) FROM rls_migration_status")

        assert project_count_after == project_count_before - 8, "8 projects should be removed by rollback"
        assert permission_count_after == permission_count_before - 3, "3 permissions should be removed by rollback"
        assert status_count_after == status_count_before - 8, "8 status entries should be removed by rollback"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_order_preserves_constraints(self, test_db, setup_tables, migration_path, rollback_path) -> None:
        """INTEGRATION: Verify rollback respects foreign key constraints

        GIVEN migration 033 has been applied
        WHEN rollback script is executed
        THEN no foreign key constraint violations occur
        (Rollback must delete in correct order: status -> permissions -> projects)
        """
        # Run migration first
        await self._run_migration(test_db, migration_path)

        # Execute rollback - should not raise any errors
        # If rollback order is wrong, foreign key constraint will fail
        try:
            await self._run_migration(test_db, rollback_path)
        except asyncpg.ForeignKeyViolationError as e:
            pytest.fail(f"Rollback violated foreign key constraints: {e}")

        # Verify rollback completed successfully
        # Check that seeded projects are gone
        seeded_projects = await test_db.fetch("""
            SELECT project_id FROM project_registry
            WHERE project_id IN ('io', 'echo', 'ea', 'ab', 'aa', 'bap', 'motoko', 'sm')
        """)
        assert len(seeded_projects) == 0, "All seeded projects should be removed by rollback"

    # =========================================================================
    # Additional Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_seed_runs_with_clean_database(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify seed works on clean database

        GIVEN migrations 030-032 have been applied (empty tables)
        WHEN migration 033 is applied
        THEN all data is seeded correctly without errors
        """
        # Verify tables are empty
        project_count = await test_db.fetchval("SELECT COUNT(*) FROM project_registry")
        assert project_count == 0, "Tables should be empty before seed"

        # Run migration - should not raise any errors
        try:
            await self._run_migration(test_db, migration_path)
        except Exception as e:
            pytest.fail(f"Seed failed on clean database: {e}")

        # Verify data was seeded
        new_project_count = await test_db.fetchval("SELECT COUNT(*) FROM project_registry")
        assert new_project_count == 8, "All 8 projects should be seeded"

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lock_timeout_set_in_migration(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify lock_timeout is set during migration

        GIVEN migration 033 is executed
        WHEN checking lock_timeout
        THEN it should be set to '5s' during the migration
        """
        # We can't directly test the lock_timeout during the migration execution,
        # but we can verify the SET/RESET statements exist in the file
        sql = migration_path.read_text()

        assert "SET lock_timeout = '5s'" in sql, "Migration should set lock_timeout"
        assert "RESET lock_timeout" in sql, "Migration should reset lock_timeout"
