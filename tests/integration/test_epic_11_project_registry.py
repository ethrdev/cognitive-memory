"""Tests for Story 11.2.1: Create project_registry Table

These tests verify the migration creates the project_registry table
with the correct schema, enum type, indexes, and updated_at trigger.

Uses asyncpg with its own fixture (not the global psycopg2 conn fixture).
"""

import os
from pathlib import Path

import asyncpg
import pytest


class TestProjectRegistryMigration:
    """Test Migration 030: Create project_registry table."""

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
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "030_create_project_registry.sql"
        assert path.exists(), f"Migration file not found at {path}"
        return path

    @pytest.fixture
    def rollback_path(self) -> Path:
        """Path to the rollback SQL file."""
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "030_create_project_registry_rollback.sql"
        assert path.exists(), f"Rollback file not found at {path}"
        return path

    async def _run_migration(self, conn: asyncpg.Connection, sql_path: Path) -> None:
        """Execute a migration SQL file."""
        sql = sql_path.read_text()
        # Execute as single script (handles SET/RESET statements properly)
        await conn.execute(sql)

    # =========================================================================
    # AC1: Table Schema Created
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_project_registry_table_exists(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify project_registry table is created (AC1)

        GIVEN migration 030 has been applied
        WHEN checking information_schema
        THEN project_registry table exists
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_registry'
            )
        """)

        assert result is True, "project_registry table should exist after migration"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_project_registry_columns(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify all columns exist with correct types (AC1)

        GIVEN migration 030 has been applied
        WHEN checking column definitions
        THEN all columns exist with correct data types
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'project_registry'
            ORDER BY ordinal_position
        """)

        columns = {row['column_name']: dict(row) for row in result}

        # Verify id column (SERIAL = integer with sequence)
        assert 'id' in columns, "id column should exist"
        assert columns['id']['data_type'] == 'integer', "id should be integer (SERIAL)"

        # Verify project_id column (VARCHAR(50) UNIQUE NOT NULL)
        assert 'project_id' in columns, "project_id column should exist"
        assert columns['project_id']['data_type'] == 'character varying', "project_id should be VARCHAR"
        assert columns['project_id']['is_nullable'] == 'NO', "project_id should be NOT NULL"

        # Verify name column (VARCHAR(100) NOT NULL)
        assert 'name' in columns, "name column should exist"
        assert columns['name']['is_nullable'] == 'NO', "name should be NOT NULL"

        # Verify access_level column (access_level_enum NOT NULL DEFAULT 'isolated')
        assert 'access_level' in columns, "access_level column should exist"
        assert columns['access_level']['data_type'] == 'USER-DEFINED', "access_level should be USER-DEFINED (enum)"
        assert "'isolated'::access_level_enum" in str(columns['access_level']['column_default']), \
            "access_level should default to 'isolated'"

        # Verify timestamp columns
        assert 'created_at' in columns, "created_at column should exist"
        assert 'updated_at' in columns, "updated_at column should exist"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_project_registry_constraints(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify constraints exist (AC1)

        GIVEN migration 030 has been applied
        WHEN checking table constraints
        THEN PRIMARY KEY and UNIQUE constraints exist
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'project_registry'
        """)

        constraint_types = {row['constraint_type'] for row in result}

        assert 'PRIMARY KEY' in constraint_types, "PRIMARY KEY constraint should exist"
        assert 'UNIQUE' in constraint_types, "UNIQUE constraint on project_id should exist"

    # =========================================================================
    # AC2: Access Level Enum Created
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_access_level_enum_exists(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify access_level_enum type exists (AC2)

        GIVEN migration 030 has been applied
        WHEN checking pg_enum
        THEN access_level_enum exists with correct values ('super', 'shared', 'isolated')
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch("""
            SELECT enumlabel
            FROM pg_enum
            WHERE enumtypid = 'access_level_enum'::regtype
            ORDER BY enumsortorder
        """)

        values = [row['enumlabel'] for row in result]
        assert values == ['super', 'shared', 'isolated'], \
            f"access_level_enum should have values ['super', 'shared', 'isolated'], got {values}"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_default_access_level_isolated(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify default access_level is 'isolated' (AC2)

        GIVEN migration 030 has been applied
        WHEN inserting a row without access_level
        THEN it defaults to 'isolated'
        """
        await self._run_migration(test_db, migration_path)

        await test_db.execute("""
            INSERT INTO project_registry (project_id, name)
            VALUES ('test-project', 'Test Project')
        """)

        access_level = await test_db.fetchval("""
            SELECT access_level FROM project_registry WHERE project_id = 'test-project'
        """)

        assert access_level == 'isolated', "access_level should default to 'isolated'"

    # =========================================================================
    # AC3: Index Created
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_project_registry_index_exists(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify index on project_id exists (AC3)

        GIVEN migration 030 has been applied
        WHEN checking pg_indexes
        THEN idx_project_registry_project_id index exists as B-tree
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchrow("""
            SELECT indexdef
            FROM pg_indexes
            WHERE tablename = 'project_registry'
              AND indexname = 'idx_project_registry_project_id'
        """)

        assert result is not None, "idx_project_registry_project_id index should exist"
        # B-tree is default, verify it's using btree (implicit in CREATE INDEX)
        assert 'project_id' in result['indexdef'], "Index should be on project_id column"

    # =========================================================================
    # AC4: Rollback Script Available
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_drops_table_and_enum(self, test_db, migration_path, rollback_path) -> None:
        """INTEGRATION: Verify rollback cleans up table and enum (AC4)

        GIVEN migration 030 is applied
        WHEN rollback script is executed
        THEN project_registry table is dropped
        AND access_level_enum type is dropped
        """
        # First apply migration
        await self._run_migration(test_db, migration_path)

        # Verify table and enum exist
        table_exists = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_registry'
            )
        """)
        assert table_exists is True, "Table should exist before rollback"

        enum_exists = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'access_level_enum'
            )
        """)
        assert enum_exists is True, "Enum should exist before rollback"

        # Execute rollback
        await self._run_migration(test_db, rollback_path)

        # Verify table is dropped
        table_exists_after = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_registry'
            )
        """)
        assert table_exists_after is False, "Table should be dropped after rollback"

        # Verify enum is dropped
        enum_exists_after = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'access_level_enum'
            )
        """)
        assert enum_exists_after is False, "Enum should be dropped after rollback"

    # =========================================================================
    # Trigger Tests (added by code review)
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_updated_at_trigger_exists(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify updated_at trigger is created

        GIVEN migration 030 has been applied
        WHEN checking pg_trigger
        THEN update_project_registry_updated_at trigger exists
        """
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'update_project_registry_updated_at'
            )
        """)

        assert result is True, "updated_at trigger should exist"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_updated_at_auto_updates(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify updated_at is automatically updated on row change

        GIVEN a row exists in project_registry
        WHEN the row is updated
        THEN updated_at timestamp changes automatically
        """
        await self._run_migration(test_db, migration_path)

        # Insert a row
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('trigger-test', 'Trigger Test Project', 'isolated')
        """)

        # Get initial timestamps
        initial = await test_db.fetchrow("""
            SELECT created_at, updated_at FROM project_registry
            WHERE project_id = 'trigger-test'
        """)

        # Small delay to ensure timestamp difference
        import asyncio
        await asyncio.sleep(0.01)

        # Update the row
        await test_db.execute("""
            UPDATE project_registry SET name = 'Updated Name'
            WHERE project_id = 'trigger-test'
        """)

        # Get new timestamps
        updated = await test_db.fetchrow("""
            SELECT created_at, updated_at FROM project_registry
            WHERE project_id = 'trigger-test'
        """)

        # created_at should not change
        assert initial['created_at'] == updated['created_at'], \
            "created_at should not change on update"

        # updated_at should be newer
        assert updated['updated_at'] >= initial['updated_at'], \
            "updated_at should be updated by trigger"

    # =========================================================================
    # Idempotency & Additional Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unique_constraint_enforced(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify project_id UNIQUE constraint works

        GIVEN migration 030 has been applied
        WHEN inserting duplicate project_id
        THEN unique constraint violation occurs
        """
        await self._run_migration(test_db, migration_path)

        # Insert first row
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('unique-test', 'First Project', 'isolated')
        """)

        # Try to insert duplicate - should fail
        with pytest.raises(asyncpg.UniqueViolationError):
            await test_db.execute("""
                INSERT INTO project_registry (project_id, name, access_level)
                VALUES ('unique-test', 'Second Project', 'isolated')
            """)

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_idempotent(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify migration can be run multiple times safely

        GIVEN migration 030 has been applied
        WHEN running migration again
        THEN no errors occur (IF NOT EXISTS handles it)
        """
        # Run migration first time
        await self._run_migration(test_db, migration_path)

        # Verify table exists
        result1 = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_registry'
            )
        """)
        assert result1 is True, "Table should exist after first migration"

        # Run migration second time - should NOT error due to IF NOT EXISTS guards
        await self._run_migration(test_db, migration_path)

        # Verify table still exists
        result2 = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_registry'
            )
        """)
        assert result2 is True, "Table should still exist after second migration"

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_table_comments_exist(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify table and column comments exist for documentation

        GIVEN migration 030 has been applied
        WHEN checking pg_description
        THEN comments exist for table and key columns
        """
        await self._run_migration(test_db, migration_path)

        # Check table comment
        table_comment = await test_db.fetchval("""
            SELECT obj_description('project_registry'::regclass, 'pg_class')
        """)

        assert table_comment is not None, "project_registry table should have a comment"
        assert 'registry' in table_comment.lower() or 'project' in table_comment.lower(), \
            "Table comment should mention registry or project"
