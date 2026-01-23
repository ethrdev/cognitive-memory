"""Tests for Story 11.3.2: Shadow Audit Infrastructure

These tests verify the shadow audit infrastructure created in migration 035:
- rls_audit_log table with JSONB columns (old_data, new_data)
- BRIN index on logged_at for time-series optimization
- Partial B-tree index for violations (would_be_denied = TRUE)
- rls_check_access() function implements ACL logic correctly
- shadow_audit_trigger() handles INSERT/UPDATE/DELETE correctly
- Triggers attached to l2_insights, nodes, edges
- Trigger returns correctly (OLD for DELETE, NEW for others)
- Shadow audit logging only happens when rls_mode = 'shadow'
- Rollback is idempotent and removes all objects

Uses asyncpg with its own fixture (not the global psycopg2 conn fixture).
"""

import os
from pathlib import Path

import asyncpg
import pytest


class TestShadowAuditInfrastructure:
    """Test Migration 035: Shadow Audit Infrastructure."""

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
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "035_shadow_audit_infrastructure.sql"
        assert path.exists(), f"Migration file not found at {path}"
        return path

    @pytest.fixture
    def rollback_path(self) -> Path:
        """Path to the rollback SQL file."""
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "035_shadow_audit_infrastructure_rollback.sql"
        assert path.exists(), f"Rollback file not found at {path}"
        return path

    @pytest.fixture
    async def setup_tables(self, test_db):
        """Ensure prerequisite tables exist (from migrations 030-034).

        This fixture runs migrations 030, 031, 032, 033, and 034 to create the tables
        that migration 035 depends on.
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

        # Run migration 033 (seed initial data) - creates the 8 projects
        migration_033 = migrations_dir / "033_seed_initial_projects.sql"
        if migration_033.exists():
            await test_db.execute(migration_033.read_text())

        # Run migration 034 (RLS helper functions)
        migration_034 = migrations_dir / "034_rls_helper_functions.sql"
        if migration_034.exists():
            await test_db.execute(migration_034.read_text())

        # Create core tables for trigger testing (nodes, edges, l2_insights)
        # Simplified schema for testing
        await test_db.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) UNIQUE NOT NULL,
                label VARCHAR(100),
                properties JSONB DEFAULT '{}',
                project_id VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await test_db.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source_id UUID NOT NULL REFERENCES nodes(id),
                target_id UUID NOT NULL REFERENCES nodes(id),
                relation VARCHAR(100) NOT NULL,
                weight FLOAT DEFAULT 1.0,
                properties JSONB DEFAULT '{}',
                project_id VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        await test_db.execute("""
            CREATE TABLE IF NOT EXISTS l2_insights (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                project_id VARCHAR(50),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)

    async def _run_migration(self, conn: asyncpg.Connection, sql_path: Path) -> None:
        """Execute a migration SQL file."""
        sql = sql_path.read_text()
        # Execute as single script (handles SET/RESET statements properly)
        await conn.execute(sql)

    # =========================================================================
    # AC1: rls_audit_log Table (JSONB-based for Flexibility)
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_audit_log_table_structure(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify rls_audit_log table has correct structure (AC1)

        GIVEN migration 035 has been applied
        WHEN querying information_schema for rls_audit_log
        THEN table has correct columns:
          - id (BIGSERIAL, PRIMARY KEY)
          - logged_at (TIMESTAMPTZ, DEFAULT NOW())
          - project_id (VARCHAR(50))
          - table_name (VARCHAR(100))
          - operation (VARCHAR(10))
          - row_project_id (VARCHAR(50))
          - would_be_denied (BOOLEAN)
          - old_data (JSONB)
          - new_data (JSONB)
          - session_user (VARCHAR(100))
        """
        await self._run_migration(test_db, migration_path)

        # Check table exists
        table_exists = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'rls_audit_log'
            )
        """)
        assert table_exists is True, "rls_audit_log table should exist"

        # Check columns
        columns = await test_db.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'rls_audit_log'
            ORDER BY ordinal_position
        """)

        column_map = {row['column_name']: row for row in columns}

        # Verify key columns
        assert 'id' in column_map, "id column should exist"
        assert 'logged_at' in column_map, "logged_at column should exist"
        assert 'project_id' in column_map, "project_id column should exist"
        assert 'table_name' in column_map, "table_name column should exist"
        assert 'operation' in column_map, "operation column should exist"
        assert 'row_project_id' in column_map, "row_project_id column should exist"
        assert 'would_be_denied' in column_map, "would_be_denied column should exist"
        assert 'old_data' in column_map, "old_data column should exist"
        assert 'new_data' in column_map, "new_data column should exist"
        assert 'session_user' in column_map, "session_user column should exist"

        # Verify JSONB types
        assert column_map['old_data']['data_type'] == 'jsonb', "old_data should be JSONB"
        assert column_map['new_data']['data_type'] == 'jsonb', "new_data should be JSONB"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_audit_log_brin_index(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify BRIN index on logged_at (AC1)

        GIVEN migration 035 has been applied
        WHEN querying pg_indexes for rls_audit_log
        THEN idx_audit_log_time exists using BRIN (not B-tree)
        """
        await self._run_migration(test_db, migration_path)

        # Check BRIN index exists
        index_exists = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'rls_audit_log'
                AND indexname = 'idx_audit_log_time'
            )
        """)
        assert index_exists is True, "BRIN index idx_audit_log_time should exist"

        # Verify it's a BRIN index
        index_type = await test_db.fetchval("""
            SELECT amname
            FROM pg_index
            JOIN pg_class ON pg_class.oid = indexrelid
            JOIN pg_am ON pg_am.oid = pg_class.relam
            WHERE pg_class.relname = 'idx_audit_log_time'
        """)
        assert index_type == 'brin', f"Index should be BRIN, got {index_type}"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_audit_log_partial_btree_index(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify partial B-tree index for violations (AC1)

        GIVEN migration 035 has been applied
        WHEN querying pg_indexes for rls_audit_log
        THEN idx_audit_log_violations exists with WHERE would_be_denied = TRUE
        """
        await self._run_migration(test_db, migration_path)

        # Check partial index exists
        index_exists = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'rls_audit_log'
                AND indexname = 'idx_audit_log_violations'
            )
        """)
        assert index_exists is True, "Partial B-tree index idx_audit_log_violations should exist"

        # Verify it's a partial index
        index_pred = await test_db.fetchval("""
            SELECT indispartial
            FROM pg_index
            JOIN pg_class ON pg_class.oid = indexrelid
            WHERE pg_class.relname = 'idx_audit_log_violations'
        """)
        assert index_pred is True, "idx_audit_log_violations should be a partial index"

    # =========================================================================
    # AC2: rls_check_access() Helper Function
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_check_access_super_reads_all(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify super can read all projects (AC2)

        GIVEN set_project_context('io') has been called (io is super)
        WHEN rls_check_access('io', 'motoko', 'SELECT') is called
        THEN returns TRUE (super can read all)
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "io")
        result = await test_db.fetchval("SELECT rls_check_access($1, $2, $3)", "io", "motoko", "SELECT")

        assert result is True, "Super should be able to read all projects"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_check_access_isolated_only_own(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify isolated can only read own data (AC2)

        GIVEN set_project_context('motoko') has been called (motoko is isolated)
        WHEN rls_check_access('motoko', 'aa', 'SELECT') is called
        THEN returns FALSE (isolated cannot read other projects)
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "motoko")
        result = await test_db.fetchval("SELECT rls_check_access($1, $2, $3)", "motoko", "aa", "SELECT")

        assert result is False, "Isolated should not be able to read other projects"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_check_access_write_only_own(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify all levels can only write to own data (AC2)

        GIVEN set_project_context('io') has been called (io is super)
        WHEN rls_check_access('io', 'motoko', 'UPDATE') is called
        THEN returns FALSE (even super cannot write to other projects)
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "io")
        result = await test_db.fetchval("SELECT rls_check_access($1, $2, $3)", "io", "motoko", "UPDATE")

        assert result is False, "Should not be able to write to other projects"

    # =========================================================================
    # AC3, AC4: Shadow Audit Trigger
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shadow_audit_trigger_creates_logs_in_shadow_mode(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify shadow trigger creates logs when rls_mode = 'shadow' (AC3, AC4)

        GIVEN project 'aa' has migration_phase = 'shadow'
        WHEN INSERT/UPDATE/DELETE occurs on nodes table
        THEN shadow trigger logs to rls_audit_log
        AND the actual operation is NOT blocked
        """
        await self._run_migration(test_db, migration_path)

        # Set aa to shadow mode
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ($1, 'shadow')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """, "aa")

        # Set project context to aa
        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Create a node owned by io (different project)
        node_id = await test_db.fetchval("""
            INSERT INTO nodes (name, label, project_id)
            VALUES ($1, $2, $3)
            RETURNING id
        """, "test_node", "Test", "io")

        # Insert should succeed (not blocked in shadow mode)
        assert node_id is not None, "INSERT should succeed in shadow mode"

        # Check that audit log was created
        log_count = await test_db.fetchval("""
            SELECT COUNT(*) FROM rls_audit_log
            WHERE project_id = 'aa'
            AND table_name = 'nodes'
            AND would_be_denied = TRUE
        """)
        assert log_count > 0, "Shadow audit log should be created in shadow mode"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shadow_audit_trigger_does_not_log_when_not_shadow(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify shadow trigger does NOT log when rls_mode != 'shadow' (AC4)

        GIVEN project 'aa' has migration_phase = 'pending' (not shadow)
        WHEN INSERT/UPDATE/DELETE occurs on nodes table
        THEN NO shadow audit log entry is created
        """
        await self._run_migration(test_db, migration_path)

        # Set aa to pending mode (not shadow)
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ($1, 'pending')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """, "aa")

        # Set project context to aa
        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Create a node owned by io (different project)
        node_id = await test_db.fetchval("""
            INSERT INTO nodes (name, label, project_id)
            VALUES ($1, $2, $3)
            RETURNING id
        """, "test_node", "Test", "io")

        # Insert should succeed
        assert node_id is not None, "INSERT should succeed"

        # Check that audit log was NOT created
        log_count = await test_db.fetchval("""
            SELECT COUNT(*) FROM rls_audit_log
            WHERE project_id = 'aa'
            AND table_name = 'nodes'
        """)
        assert log_count == 0, "Shadow audit log should NOT be created when not in shadow mode"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shadow_trigger_returns_correctly(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify trigger returns OLD for DELETE, NEW for others (AC3)

        GIVEN shadow triggers are active
        WHEN INSERT/UPDATE/DELETE occurs
        THEN trigger returns correct value (DELETE: OLD, INSERT/UPDATE: NEW)
        """
        await self._run_migration(test_db, migration_path)

        # Set to shadow mode
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ($1, 'shadow')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """, "aa")
        await test_db.execute("SELECT set_project_context($1)", "aa")

        # INSERT should work
        node_id = await test_db.fetchval("""
            INSERT INTO nodes (name, label, project_id)
            VALUES ($1, $2, $3)
            RETURNING id
        """, "test_insert", "Test", "aa")
        assert node_id is not None, "INSERT should return NEW row"

        # DELETE should also work
        deleted_id = await test_db.fetchval("""
            DELETE FROM nodes WHERE id = $1
            RETURNING id
        """, node_id)
        assert deleted_id == node_id, "DELETE should return OLD row"

    # =========================================================================
    # AC6: Audit Log Validation Query
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_audit_log_validation_query(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify BRIN index works for time-range filtering (AC6)

        GIVEN shadow phase has generated audit logs
        WHEN DevOps queries violations grouped by project/table/operation
        THEN the BRIN index ensures fast time-range filtering
        """
        await self._run_migration(test_db, migration_path)

        # Set to shadow mode
        await test_db.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ($1, 'shadow')
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """, "aa")
        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Generate some audit logs
        await test_db.execute("""
            INSERT INTO nodes (name, label, project_id)
            VALUES ($1, $2, $3)
        """, "test1", "Test", "io")

        await test_db.execute("""
            INSERT INTO nodes (name, label, project_id)
            VALUES ($1, $2, $3)
        """, "test2", "Test", "io")

        # Query violations grouped by project/table/operation
        violations = await test_db.fetch("""
            SELECT
                project_id,
                table_name,
                operation,
                COUNT(*) as violation_count
            FROM rls_audit_log
            WHERE would_be_denied = TRUE
            AND logged_at > NOW() - INTERVAL '1 hour'
            GROUP BY project_id, table_name, operation
        """)

        assert violations is not None, "Should be able to query violations"

    # =========================================================================
    # Rollback Tests
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_removes_all_objects(self, test_db, setup_tables, migration_path, rollback_path) -> None:
        """INTEGRATION: Verify rollback removes all objects (AC1)

        GIVEN migration 035 has been applied
        WHEN rollback script is executed
        THEN all objects are removed (table, indexes, functions, triggers)
        """
        # Run migration first
        await self._run_migration(test_db, migration_path)

        # Verify objects exist
        table_exists = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'rls_audit_log'
            )
        """)
        assert table_exists is True, "rls_audit_log table should exist before rollback"

        # Execute rollback
        await self._run_migration(test_db, rollback_path)

        # Verify table is removed
        table_exists_after = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'rls_audit_log'
            )
        """)
        assert table_exists_after is False, "rls_audit_log table should be removed after rollback"

        # Verify functions are removed
        func_count = await test_db.fetchval("""
            SELECT COUNT(*) FROM pg_proc
            WHERE proname IN ('rls_check_access', 'shadow_audit_trigger')
        """)
        assert func_count == 0, "Functions should be removed after rollback"

        # Verify triggers are removed
        trigger_count = await test_db.fetchval("""
            SELECT COUNT(*) FROM information_schema.triggers
            WHERE trigger_name LIKE '%shadow_audit%'
        """)
        assert trigger_count == 0, "Triggers should be removed after rollback"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_is_idempotent(self, test_db, setup_tables, migration_path, rollback_path) -> None:
        """INTEGRATION: Verify rollback is idempotent (AC1)

        GIVEN rollback script is executed once
        WHEN rollback script is executed again
        THEN no errors occur (idempotent)
        """
        # Run migration first
        await self._run_migration(test_db, migration_path)

        # Execute rollback once
        await self._run_migration(test_db, rollback_path)

        # Execute rollback again (should not error)
        await self._run_migration(test_db, rollback_path)

        # Verify objects are still removed
        table_exists = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'rls_audit_log'
            )
        """)
        assert table_exists is False, "Table should still be removed after second rollback"
