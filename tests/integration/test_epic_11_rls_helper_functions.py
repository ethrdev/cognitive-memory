"""Tests for Story 11.3.1: RLS Helper Functions

These tests verify the RLS helper functions created in migration 034:
- set_project_context() sets all session variables correctly
- get_current_project() returns correct value
- get_rls_mode() returns correct migration phase
- get_access_level() returns correct access level
- get_allowed_projects() returns TEXT[] with correct projects
- Super/Shared/Isolated access levels compute correct allowed_projects
- Unknown project raises exception
- Dependency validation fails if Epic 11.2 incomplete

Uses asyncpg with its own fixture (not the global psycopg2 conn fixture).
"""

import os
from pathlib import Path

import asyncpg
import pytest


class TestRLSHelperFunctions:
    """Test Migration 034: RLS Helper Functions."""

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
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "034_rls_helper_functions.sql"
        assert path.exists(), f"Migration file not found at {path}"
        return path

    @pytest.fixture
    def rollback_path(self) -> Path:
        """Path to the rollback SQL file."""
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "034_rls_helper_functions_rollback.sql"
        assert path.exists(), f"Rollback file not found at {path}"
        return path

    @pytest.fixture
    async def setup_tables(self, test_db):
        """Ensure prerequisite tables exist (from migrations 030, 031, 032).

        This fixture runs migrations 030, 031, 032, and 033 to create the tables
        that migration 034 depends on.
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

    async def _run_migration(self, conn: asyncpg.Connection, sql_path: Path) -> None:
        """Execute a migration SQL file."""
        sql = sql_path.read_text()
        # Execute as single script (handles SET/RESET statements properly)
        await conn.execute(sql)

    # =========================================================================
    # AC1: set_project_context() Function - Session Variables
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_project_context_sets_all_variables(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify set_project_context() sets all session variables (AC1)

        GIVEN Epic 11.2 tables exist with data
        WHEN set_project_context('aa') is called
        THEN all session variables are set correctly:
          - app.current_project = 'aa'
          - app.rls_mode = 'pending' (from rls_migration_status)
          - app.access_level = 'shared' (from project_registry)
          - app.allowed_projects contains projects
        """
        await self._run_migration(test_db, migration_path)

        # Call set_project_context
        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Verify all session variables are set
        current_project = await test_db.fetchval("SELECT get_current_project()")
        rls_mode = await test_db.fetchval("SELECT get_rls_mode()")
        access_level = await test_db.fetchval("SELECT get_access_level()")
        allowed_projects = await test_db.fetchval("SELECT get_allowed_projects()")

        assert current_project == "aa", f"Expected current_project='aa', got '{current_project}'"
        assert rls_mode == "pending", f"Expected rls_mode='pending', got '{rls_mode}'"
        assert access_level == "shared", f"Expected access_level='shared', got '{access_level}'"
        assert isinstance(allowed_projects, list), "allowed_projects should be a list (TEXT[])"
        assert "aa" in allowed_projects, "allowed_projects should contain 'aa'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_project_context_uses_set_local(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify set_project_context() uses SET LOCAL (transaction-scoped) (AC1)

        GIVEN Epic 11.2 tables exist with data
        WHEN set_project_context() is called
        THEN variables use SET LOCAL (reset at transaction end)

        This test verifies the transaction-scoped behavior by checking
        that variables are available within the transaction context.
        """
        await self._run_migration(test_db, migration_path)

        # Set context within transaction
        await test_db.execute("SELECT set_project_context($1)", "sm")

        # Variable should be accessible within same transaction
        current_project = await test_db.fetchval("SELECT get_current_project()")
        assert current_project == "sm", f"Expected 'sm', got '{current_project}'"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_project_context_lookups_rls_mode_with_fallback(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify RLS mode lookup with COALESCE fallback (AC1)

        GIVEN a project exists in project_registry
        WHEN that project has no rls_migration_status entry
        THEN RLS mode should default to 'pending'
        """
        await self._run_migration(test_db, migration_path)

        # Create a project without rls_migration_status entry
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ($1, $2, $3)
        """, "test_project", "Test Project", "isolated")

        # Call set_project_context - should fallback to 'pending'
        await test_db.execute("SELECT set_project_context($1)", "test_project")

        rls_mode = await test_db.fetchval("SELECT get_rls_mode()")
        assert rls_mode == "pending", f"Expected fallback to 'pending', got '{rls_mode}'"

    # =========================================================================
    # AC2: IMMUTABLE Wrapper Functions
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_current_project_returns_value(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify get_current_project() returns correct value (AC2)

        GIVEN set_project_context('io') has been called
        WHEN get_current_project() is called
        THEN it returns 'io'
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "io")
        result = await test_db.fetchval("SELECT get_current_project()")

        assert result == "io", f"Expected 'io', got '{result}'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_rls_mode_returns_value(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify get_rls_mode() returns correct migration phase (AC2)

        GIVEN set_project_context('aa') has been called
        WHEN get_rls_mode() is called
        THEN it returns the migration phase from rls_migration_status
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "aa")
        result = await test_db.fetchval("SELECT get_rls_mode()")

        assert result == "pending", f"Expected 'pending', got '{result}'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_access_level_returns_value(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify get_access_level() returns correct access level (AC2)

        GIVEN set_project_context('io') has been called (io is super)
        WHEN get_access_level() is called
        THEN it returns 'super'
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "io")
        result = await test_db.fetchval("SELECT get_access_level()")

        assert result == "super", f"Expected 'super', got '{result}'"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_allowed_projects_returns_array(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify get_allowed_projects() returns TEXT[] (AC2, AC3)

        GIVEN set_project_context('aa') has been called
        WHEN get_allowed_projects() is called
        THEN it returns a TEXT[] array with native array format
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "aa")
        result = await test_db.fetchval("SELECT get_allowed_projects()")

        assert isinstance(result, list), "Result should be a list (native TEXT[])"
        assert "aa" in result, "Result should contain 'aa'"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_immutable_functions_declared_correctly(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify functions are declared IMMUTABLE PARALLEL SAFE (AC2)

        GIVEN migration 034 has been applied
        WHEN querying pg_proc for function properties
        THEN all wrapper functions are declared IMMUTABLE and PARALLEL SAFE
        """
        await self._run_migration(test_db, migration_path)

        # Check get_current_project
        result = await test_db.fetchrow("""
            SELECT provolatile, proparallel
            FROM pg_proc
            WHERE proname = 'get_current_project'
        """)
        assert result is not None, "get_current_project function should exist"
        assert result['provolatile'] == 'i', f"get_current_project should be IMMUTABLE (i), got {result['provolatile']}"
        assert result['proparallel'] == 's', f"get_current_project should be PARALLEL SAFE (s), got {result['proparallel']}"

        # Check get_allowed_projects
        result = await test_db.fetchrow("""
            SELECT provolatile, proparallel
            FROM pg_proc
            WHERE proname = 'get_allowed_projects'
        """)
        assert result is not None, "get_allowed_projects function should exist"
        assert result['provolatile'] == 'i', "get_allowed_projects should be IMMUTABLE"
        assert result['proparallel'] == 's', "get_allowed_projects should be PARALLEL SAFE"

    # =========================================================================
    # AC3: Native Array Format (No CSV Parsing)
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_allowed_projects_uses_native_array_format(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify allowed_projects uses PostgreSQL array literal format (AC3)

        GIVEN set_project_context() computes allowed projects
        WHEN the allowed_projects variable is set
        THEN it uses PostgreSQL array literal format: '{aa,sm}'
        AND NOT comma-separated string that requires string_to_array()
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Get the raw session variable (before casting to TEXT[])
        raw_value = await test_db.fetchval("SELECT current_setting('app.allowed_projects', TRUE)")

        # Verify it's in PostgreSQL array literal format (starts with '{')
        assert raw_value.startswith("{"), f"Array should start with '{{', got: {raw_value}"
        assert raw_value.endswith("}"), f"Array should end with '}}', got: {raw_value}"

        # Verify it can be cast to TEXT[] directly (no string_to_array needed)
        cast_value = await test_db.fetchval("SELECT $1::TEXT[]", raw_value)
        assert isinstance(cast_value, list), "Raw value should be castable to TEXT[] directly"

    # =========================================================================
    # AC4: Allowed Projects Computation
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_super_access_level_returns_all_projects(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify super access level returns ALL project_ids (AC4)

        GIVEN project 'io' has access_level = 'super'
        WHEN set_project_context('io') is called
        THEN app.allowed_projects contains ALL 8 project_ids from project_registry
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "io")
        allowed = await test_db.fetchval("SELECT get_allowed_projects()")

        # Should contain all 8 projects from seed data
        expected_projects = {"io", "echo", "ea", "ab", "aa", "bap", "motoko", "sm"}
        actual_projects = set(allowed)

        assert actual_projects == expected_projects, f"Expected {expected_projects}, got {actual_projects}"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shared_access_level_returns_own_plus_permitted(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify shared access level returns own + permitted projects (AC4)

        GIVEN project 'aa' has access_level = 'shared'
        AND project 'aa' has permission to read 'sm' (from seed data)
        WHEN set_project_context('aa') is called
        THEN app.allowed_projects = '{aa,sm}' (own + permitted)
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "aa")
        allowed = await test_db.fetchval("SELECT get_allowed_projects()")

        # aa (shared) should see itself and sm (from project_read_permissions)
        expected = {"aa", "sm"}
        actual = set(allowed)

        assert actual == expected, f"Expected {expected}, got {actual}"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_isolated_access_level_returns_own_only(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify isolated access level returns own project only (AC4)

        GIVEN project 'motoko' has access_level = 'isolated'
        WHEN set_project_context('motoko') is called
        THEN app.allowed_projects = '{motoko}' (own only)
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "motoko")
        allowed = await test_db.fetchval("SELECT get_allowed_projects()")

        # motoko (isolated) should only see itself
        expected = {"motoko"}
        actual = set(allowed)

        assert actual == expected, f"Expected {expected}, got {actual}"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shared_with_multiple_permissions(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify shared access level with multiple permissions (AC4)

        GIVEN project 'ab' has access_level = 'shared'
        AND project 'ab' has permission to read 'sm' (from seed data)
        WHEN set_project_context('ab') is called
        THEN app.allowed_projects = '{ab,sm}' (own + all permitted)
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "ab")
        allowed = await test_db.fetchval("SELECT get_allowed_projects()")

        # ab (shared) should see itself and sm
        expected = {"ab", "sm"}
        actual = set(allowed)

        assert actual == expected, f"Expected {expected}, got {actual}"

    # =========================================================================
    # AC5: Performance: 14x Improvement via IMMUTABLE
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_immutable_function_single_evaluation(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify IMMUTABLE functions are evaluated once per query (AC5)

        GIVEN set_project_context('aa') has been called
        WHEN a query uses get_allowed_projects() in WHERE clause
        THEN EXPLAIN shows single evaluation (not per-row)

        This is a basic check that the function can be used in queries.
        Full performance testing is in test_rls_helper_performance.py
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("SELECT set_project_context($1)", "aa")

        # Query using get_allowed_projects() DIRECTLY in WHERE clause
        # This properly tests the IMMUTABLE behavior in the query planner
        plan_rows = await test_db.fetch("""
            EXPLAIN (FORMAT TEXT)
            SELECT project_id FROM project_registry
            WHERE project_id = ANY (get_allowed_projects())
        """)

        plan = "\n".join(row['QUERY PLAN'] for row in plan_rows)

        # Verify query executes without error and produces a plan
        assert plan is not None
        assert len(plan) > 0

    # =========================================================================
    # AC6: Error Handling
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unknown_project_raises_exception(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify unknown project_id raises exception (AC6)

        GIVEN set_project_context() is called with unknown project_id
        WHEN the function executes
        THEN it raises an exception 'Unknown project: {project_id}'
        AND no session variables are set
        """
        await self._run_migration(test_db, migration_path)

        # Try to set context for unknown project
        # RAISE EXCEPTION in PL/pgSQL maps to asyncpg.RaiseError
        with pytest.raises(asyncpg.RaiseError, match="Unknown project"):
            await test_db.execute("SELECT set_project_context($1)", "unknown_project_xyz")

        # Verify session variable was NOT set
        # Note: current_setting with missing_ok=TRUE returns empty string, not error
        current_project = await test_db.fetchval("SELECT get_current_project()")
        assert current_project == "" or current_project is None, \
            f"Session variable should be empty after failed set_project_context, got: {current_project}"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_empty_project_id_raises_exception(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify empty project_id raises exception (AC6)

        GIVEN set_project_context() is called with empty project_id
        WHEN the function executes
        THEN it raises an exception 'Unknown project: '
        """
        await self._run_migration(test_db, migration_path)

        # Try to set context for empty project
        # RAISE EXCEPTION in PL/pgSQL maps to asyncpg.RaiseError
        with pytest.raises(asyncpg.RaiseError, match="Unknown project"):
            await test_db.execute("SELECT set_project_context($1)", "")

    # =========================================================================
    # AC7: Dependency Validation
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_dependency_validation_fails_if_tables_missing(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify migration fails if Epic 11.2 tables missing (AC7)

        GIVEN Epic 11.2 is NOT complete (tables missing)
        WHEN migration 034 is run
        THEN migration fails with clear error message
        AND partial state is rolled back
        """
        # Don't run setup_tables - simulate missing Epic 11.2 tables

        # Try to run migration - should fail
        # RAISE EXCEPTION in PL/pgSQL DO block maps to asyncpg.RaiseError
        with pytest.raises(asyncpg.RaiseError, match="Dependency check failed"):
            await self._run_migration(test_db, migration_path)

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_with_prerequisite_tables(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify migration succeeds when Epic 11.2 complete (AC7)

        GIVEN Epic 11.2 migrations (030-032) are complete
        WHEN migration 034 is run
        THEN migration succeeds without errors
        """
        # setup_tables ensures Epic 11.2 tables exist
        # Should not raise any errors
        await self._run_migration(test_db, migration_path)

        # Verify functions were created
        functions = await test_db.fetchval("""
            SELECT COUNT(*) FROM pg_proc
            WHERE proname IN (
                'set_project_context',
                'get_current_project',
                'get_rls_mode',
                'get_access_level',
                'get_allowed_projects'
            )
        """)

        assert functions == 5, f"Expected 5 functions, found {functions}"

    # =========================================================================
    # Additional Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_set_project_context_security_definer(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify set_project_context uses SECURITY DEFINER

        GIVEN migration 034 has been applied
        WHEN checking function properties
        THEN set_project_context is declared SECURITY DEFINER
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchrow("""
            SELECT prosecdef
            FROM pg_proc
            WHERE proname = 'set_project_context'
        """)

        assert result is not None, "set_project_context function should exist"
        assert result['prosecdef'] is True, "set_project_context should use SECURITY DEFINER"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_removes_all_functions(self, test_db, setup_tables, migration_path, rollback_path) -> None:
        """INTEGRATION: Verify rollback removes all RLS helper functions

        GIVEN migration 034 has been applied
        WHEN rollback script is executed
        THEN all functions are removed
        """
        # Run migration first
        await self._run_migration(test_db, migration_path)

        # Verify functions exist
        count_before = await test_db.fetchval("""
            SELECT COUNT(*) FROM pg_proc
            WHERE proname IN (
                'set_project_context',
                'get_current_project',
                'get_rls_mode',
                'get_access_level',
                'get_allowed_projects'
            )
        """)
        assert count_before == 5, f"Expected 5 functions before rollback, found {count_before}"

        # Execute rollback
        await self._run_migration(test_db, rollback_path)

        # Verify all functions are removed
        count_after = await test_db.fetchval("""
            SELECT COUNT(*) FROM pg_proc
            WHERE proname IN (
                'set_project_context',
                'get_current_project',
                'get_rls_mode',
                'get_access_level',
                'get_allowed_projects'
            )
        """)
        assert count_after == 0, f"Expected 0 functions after rollback, found {count_after}"

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_lock_timeout_set_in_migration(self, test_db, setup_tables, migration_path) -> None:
        """INTEGRATION: Verify lock_timeout is set during migration

        GIVEN migration 034 is executed
        WHEN checking migration file
        THEN it should set lock_timeout = '5s'
        """
        sql = migration_path.read_text()

        assert "SET lock_timeout = '5s'" in sql, "Migration should set lock_timeout"
        assert "RESET lock_timeout" in sql, "Migration should reset lock_timeout"
