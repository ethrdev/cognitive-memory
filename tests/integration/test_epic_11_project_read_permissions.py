"""Tests for Story 11.2.2: Create project_read_permissions Table

These tests verify the migration creates the project_read_permissions table
with the correct schema, foreign key constraints, unique constraint, check constraint,
and indexes.

Uses asyncpg with its own fixture (not the global psycopg2 conn fixture).
"""

import os
from pathlib import Path

import asyncpg
import pytest


class TestProjectReadPermissionsMigration:
    """Test Migration 031: Create project_read_permissions table."""

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

        # Use explicit transaction with rollback for test isolation
        tx = conn.transaction()
        await tx.start()
        try:
            yield conn
        finally:
            await tx.rollback()
            await conn.close()

    @pytest.fixture
    def migration_path(self) -> Path:
        """Path to the migration SQL file."""
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "031_create_project_read_permissions.sql"
        assert path.exists(), f"Migration file not found at {path}"
        return path

    @pytest.fixture
    def rollback_path(self) -> Path:
        """Path to the rollback SQL file."""
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "031_create_project_read_permissions_rollback.sql"
        assert path.exists(), f"Rollback file not found at {path}"
        return path

    @pytest.fixture
    def project_registry_path(self) -> Path:
        """Path to the project_registry migration (dependency)."""
        path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "030_create_project_registry.sql"
        assert path.exists(), f"Project registry migration not found at {path}"
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
    async def test_project_read_permissions_table_exists(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify project_read_permissions table is created (AC1)

        GIVEN migration 030 (project_registry) and 031 have been applied
        WHEN checking information_schema
        THEN project_read_permissions table exists
        """
        # Apply dependency first
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_read_permissions'
            )
        """)

        assert result is True, "project_read_permissions table should exist after migration"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_project_read_permissions_columns(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify all columns exist with correct types (AC1)

        GIVEN migration 031 has been applied
        WHEN checking column definitions
        THEN all columns exist with correct data types
        """
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch("""
            SELECT column_name, data_type, is_nullable, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'project_read_permissions'
            ORDER BY ordinal_position
        """)

        columns = {row['column_name']: dict(row) for row in result}

        # Verify id column (SERIAL = integer)
        assert 'id' in columns, "id column should exist"
        assert columns['id']['data_type'] == 'integer', "id should be integer (SERIAL)"

        # Verify reader_project_id column (VARCHAR(50) NOT NULL)
        assert 'reader_project_id' in columns, "reader_project_id column should exist"
        assert columns['reader_project_id']['data_type'] == 'character varying', "reader_project_id should be VARCHAR"
        assert columns['reader_project_id']['is_nullable'] == 'NO', "reader_project_id should be NOT NULL"
        assert columns['reader_project_id']['character_maximum_length'] == 50, "reader_project_id should be VARCHAR(50)"

        # Verify target_project_id column (VARCHAR(50) NOT NULL)
        assert 'target_project_id' in columns, "target_project_id column should exist"
        assert columns['target_project_id']['data_type'] == 'character varying', "target_project_id should be VARCHAR"
        assert columns['target_project_id']['is_nullable'] == 'NO', "target_project_id should be NOT NULL"
        assert columns['target_project_id']['character_maximum_length'] == 50, "target_project_id should be VARCHAR(50)"

        # Verify created_at column (TIMESTAMPTZ DEFAULT NOW())
        assert 'created_at' in columns, "created_at column should exist"

    # =========================================================================
    # AC2: UNIQUE Constraint on (reader_project_id, target_project_id)
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unique_constraint_on_reader_target(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify UNIQUE constraint on (reader, target) pair (AC2)

        GIVEN migration 031 has been applied AND projects exist
        WHEN inserting duplicate permission
        THEN unique constraint violation occurs
        """
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        # Insert test projects
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-reader-2', 'Test Reader 2', 'shared'),
                   ('test-target-2', 'Test Target 2', 'isolated')
        """)

        # First insert should succeed
        await test_db.execute("""
            INSERT INTO project_read_permissions (reader_project_id, target_project_id)
            VALUES ('test-reader-2', 'test-target-2')
        """)

        # Second insert should fail (UNIQUE constraint)
        with pytest.raises(asyncpg.UniqueViolationError):
            await test_db.execute("""
                INSERT INTO project_read_permissions (reader_project_id, target_project_id)
                VALUES ('test-reader-2', 'test-target-2')
            """)

    # =========================================================================
    # AC3: CHECK Constraint Prevents Self-Reference
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_check_constraint_prevents_self_reference(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify CHECK constraint prevents self-reference (AC3)

        GIVEN migration 031 has been applied AND project exists
        WHEN inserting permission with reader = target
        THEN check constraint violation occurs
        """
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        # Insert test project
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-self', 'Test Self', 'shared')
        """)

        # Self-reference should fail (CHECK constraint)
        with pytest.raises(asyncpg.CheckViolationError):
            await test_db.execute("""
                INSERT INTO project_read_permissions (reader_project_id, target_project_id)
                VALUES ('test-self', 'test-self')
            """)

    # =========================================================================
    # AC4: Index on reader_project_id
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_index_on_reader_project_id(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify index on reader_project_id exists (AC4)

        GIVEN migration 031 has been applied
        WHEN checking pg_indexes
        THEN idx_permissions_reader index exists
        """
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'project_read_permissions'
                  AND indexname = 'idx_permissions_reader'
            )
        """)

        assert result is True, "idx_permissions_reader index should exist"

    # =========================================================================
    # AC5: Rollback Script Available
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_drops_table(self, test_db, migration_path, rollback_path, project_registry_path) -> None:
        """INTEGRATION: Verify rollback script drops table (AC5)

        GIVEN migration 031 is applied
        WHEN rollback script is executed
        THEN project_read_permissions table is dropped
        """
        # Apply dependency and migration
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        # Verify table exists
        table_exists = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_read_permissions'
            )
        """)
        assert table_exists is True, "Table should exist before rollback"

        # Execute rollback
        await self._run_migration(test_db, rollback_path)

        # Verify table is dropped
        table_exists_after = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_read_permissions'
            )
        """)
        assert table_exists_after is False, "Table should be dropped after rollback"

    # =========================================================================
    # Foreign Key Constraints Tests
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_foreign_key_constraints(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify foreign key constraints with CASCADE delete

        GIVEN migration 031 has been applied AND project_registry has test data
        WHEN inserting permission with invalid project_id
        THEN foreign key violation occurs

        GIVEN a permission exists AND project is deleted
        THEN permission is automatically deleted (CASCADE)
        """
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        # Insert test projects
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-reader', 'Test Reader', 'shared'),
                   ('test-target', 'Test Target', 'isolated')
        """)

        # Test valid insert
        await test_db.execute("""
            INSERT INTO project_read_permissions (reader_project_id, target_project_id)
            VALUES ('test-reader', 'test-target')
        """)

        # Verify insert succeeded
        count = await test_db.fetchval("""
            SELECT COUNT(*) FROM project_read_permissions
            WHERE reader_project_id = 'test-reader'
        """)
        assert count == 1, "Permission should be inserted successfully"

        # Test CASCADE delete - delete reader project
        await test_db.execute("DELETE FROM project_registry WHERE project_id = 'test-reader'")

        # Verify permission was deleted (cascade from reader)
        count = await test_db.fetchval("""
            SELECT COUNT(*) FROM project_read_permissions
            WHERE reader_project_id = 'test-reader'
        """)
        assert count == 0, "Permission should be cascade deleted when reader project is deleted"

        # Also test CASCADE from target - insert new projects and permission
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-target-2', 'Test Target 2', 'isolated')
        """)
        await test_db.execute("""
            INSERT INTO project_read_permissions (reader_project_id, target_project_id)
            VALUES ('test-target', 'test-target-2')
        """)

        # Delete target project
        await test_db.execute("DELETE FROM project_registry WHERE project_id = 'test-target-2'")

        # Verify permission was cascade deleted from target
        count = await test_db.fetchval("""
            SELECT COUNT(*) FROM project_read_permissions
            WHERE target_project_id = 'test-target-2'
        """)
        assert count == 0, "Permission should be cascade deleted when target project is deleted"

        # Cleanup
        await test_db.execute("DELETE FROM project_registry WHERE project_id = 'test-target'")

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_foreign_key_violation_on_invalid_project(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify foreign key rejects invalid project_id

        GIVEN migration 031 has been applied
        WHEN inserting permission with non-existent project_id
        THEN foreign key violation occurs
        """
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        # Try to insert permission for non-existent project
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await test_db.execute("""
                INSERT INTO project_read_permissions (reader_project_id, target_project_id)
                VALUES ('nonexistent-project', 'another-nonexistent')
            """)

    # =========================================================================
    # Default Values Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_default_created_at_timestamp(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify created_at defaults to NOW()

        GIVEN migration 031 has been applied AND projects exist
        WHEN inserting permission without created_at
        THEN created_at is set to current timestamp
        """
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        # Insert test projects
        await test_db.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-reader-3', 'Test Reader 3', 'shared'),
                   ('test-target-3', 'Test Target 3', 'isolated')
        """)

        # Insert without created_at
        await test_db.execute("""
            INSERT INTO project_read_permissions (reader_project_id, target_project_id)
            VALUES ('test-reader-3', 'test-target-3')
        """)

        # Verify created_at was set
        created_at = await test_db.fetchval("""
            SELECT created_at FROM project_read_permissions
            WHERE reader_project_id = 'test-reader-3'
        """)

        assert created_at is not None, "created_at should be set automatically"

    # =========================================================================
    # Idempotency Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_idempotent(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify migration can be run multiple times safely

        GIVEN migration 031 has been applied
        WHEN running migration again
        THEN no errors occur (IF NOT EXISTS handles it)
        """
        # Apply dependency
        await self._run_migration(test_db, project_registry_path)

        # Run migration first time
        await self._run_migration(test_db, migration_path)

        # Verify table exists
        result1 = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_read_permissions'
            )
        """)
        assert result1 is True, "Table should exist after first migration"

        # Run migration second time - should NOT error due to IF NOT EXISTS guards
        await self._run_migration(test_db, migration_path)

        # Verify table still exists
        result2 = await test_db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_read_permissions'
            )
        """)
        assert result2 is True, "Table should still exist after second migration"

    # =========================================================================
    # Documentation Tests
    # =========================================================================

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_table_comments_exist(self, test_db, migration_path, project_registry_path) -> None:
        """INTEGRATION: Verify table and column comments exist for documentation

        GIVEN migration 031 has been applied
        WHEN checking pg_description
        THEN comments exist for table and key columns
        """
        await self._run_migration(test_db, project_registry_path)
        await self._run_migration(test_db, migration_path)

        # Check table comment
        table_comment = await test_db.fetchval("""
            SELECT obj_description('project_read_permissions'::regclass, 'pg_class')
        """)

        assert table_comment is not None, "project_read_permissions table should have a comment"
        assert 'permission' in table_comment.lower(), "Table comment should mention permissions"

        # Check column comments
        reader_comment = await test_db.fetchval("""
            SELECT col_description('project_read_permissions'::regclass, 2)
        """)
        assert reader_comment is not None, "reader_project_id should have a comment"
