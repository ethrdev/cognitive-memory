"""Tests for Story 11.2.3: Create rls_migration_status Table

These tests verify the migration creates the rls_migration_status table
with the correct schema, enum type, indexes, and updated_at trigger.

Uses asyncpg with its own fixture (not the global psycopg2 conn fixture).
"""

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest


class TestRLSMigrationStatusMigration:
    """Test Migration 032: Create rls_migration_status table."""

    @pytest.fixture
    async def test_db(self):
        """Create an asyncpg connection for testing.

        Uses TEST_DATABASE_URL or falls back to default test database.
        Each test runs in a transaction that is ALWAYS rolled back,
        ensuring test isolation and no leftover data.
        """
        db_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/test_cognitive_memory",
        )
        try:
            conn = await asyncpg.connect(db_url)
        except Exception as e:
            pytest.skip(f"Could not connect to database: {e}")
            return

        # Manually manage transaction to ensure rollback (not commit)
        tr = conn.transaction()
        await tr.start()
        try:
            yield conn
        finally:
            # Always rollback - ensures test isolation
            await tr.rollback()
            await conn.close()

    @pytest.fixture
    def migration_path(self) -> Path:
        """Path to the migration SQL file."""
        path = (
            Path(__file__).parent.parent.parent
            / "mcp_server"
            / "db"
            / "migrations"
            / "032_create_rls_migration_status.sql"
        )
        assert path.exists(), f"Migration file not found at {path}"
        return path

    @pytest.fixture
    def rollback_path(self) -> Path:
        """Path to the rollback SQL file."""
        path = (
            Path(__file__).parent.parent.parent
            / "mcp_server"
            / "db"
            / "migrations"
            / "032_create_rls_migration_status_rollback.sql"
        )
        assert path.exists(), f"Rollback file not found at {path}"
        return path

    async def _run_migration(self, conn: asyncpg.Connection, sql_path: Path) -> None:
        """Execute a migration SQL file."""
        sql = sql_path.read_text()
        # Execute as single script (handles SET/RESET statements properly)
        await conn.execute(sql)

    async def _ensure_project_registry_exists(self, conn: asyncpg.Connection) -> None:
        """Ensure project_registry table exists for foreign key tests."""
        # Check if migration 030 has been applied
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'project_registry'
            )
        """
        )

        if not table_exists:
            # Apply migration 030 first
            migration_030_path = (
                Path(__file__).parent.parent.parent
                / "mcp_server"
                / "db"
                / "migrations"
                / "030_create_project_registry.sql"
            )
            if migration_030_path.exists():
                await self._run_migration(conn, migration_030_path)

    # =========================================================================
    # AC1: Table Schema Created
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_migration_status_table_exists(
        self, test_db, migration_path
    ) -> None:
        """INTEGRATION: Verify rls_migration_status table is created (AC1)

        GIVEN migration 032 has been applied
        WHEN checking information_schema
        THEN rls_migration_status table exists
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'rls_migration_status'
            )
        """
        )

        assert result is True, "rls_migration_status table should exist after migration"

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rls_migration_status_columns(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify all columns exist with correct types (AC1)

        GIVEN migration 032 has been applied
        WHEN checking column definitions
        THEN all columns exist with correct data types
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'rls_migration_status'
            ORDER BY ordinal_position
        """
        )

        columns = {row["column_name"]: dict(row) for row in result}

        # Verify id column (SERIAL = integer with sequence)
        assert "id" in columns, "id column should exist"
        assert columns["id"]["data_type"] == "integer", "id should be integer (SERIAL)"

        # Verify project_id column (VARCHAR(50) UNIQUE NOT NULL)
        assert "project_id" in columns, "project_id column should exist"
        assert (
            columns["project_id"]["data_type"] == "character varying"
        ), "project_id should be VARCHAR"
        assert (
            columns["project_id"]["is_nullable"] == "NO"
        ), "project_id should be NOT NULL"

        # Verify rls_enabled column (BOOLEAN NOT NULL DEFAULT FALSE)
        assert "rls_enabled" in columns, "rls_enabled column should exist"
        assert (
            columns["rls_enabled"]["data_type"] == "boolean"
        ), "rls_enabled should be boolean"
        assert (
            columns["rls_enabled"]["is_nullable"] == "NO"
        ), "rls_enabled should be NOT NULL"
        assert (
            "false" in str(columns["rls_enabled"]["column_default"]).lower()
        ), "rls_enabled should default to FALSE"

        # Verify migration_phase column (migration_phase_enum NOT NULL DEFAULT 'pending')
        assert "migration_phase" in columns, "migration_phase column should exist"
        assert (
            columns["migration_phase"]["data_type"] == "USER-DEFINED"
        ), "migration_phase should be USER-DEFINED (enum)"
        assert "'pending'::migration_phase_enum" in str(
            columns["migration_phase"]["column_default"]
        ), "migration_phase should default to 'pending'"

        # Verify migrated_at is nullable
        assert "migrated_at" in columns, "migrated_at column should exist"
        assert (
            columns["migrated_at"]["is_nullable"] == "YES"
        ), "migrated_at should be nullable"

        # Verify timestamp columns
        assert "created_at" in columns, "created_at column should exist"
        assert "updated_at" in columns, "updated_at column should exist"

    # =========================================================================
    # AC2: Migration Phase Enum Created
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_phase_enum_exists(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify migration_phase_enum type exists (AC2)

        GIVEN migration 032 has been applied
        WHEN checking pg_enum
        THEN migration_phase_enum exists with correct values ('pending', 'shadow', 'enforcing', 'complete')
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetch(
            """
            SELECT enumlabel
            FROM pg_enum
            WHERE enumtypid = 'migration_phase_enum'::regtype
            ORDER BY enumsortorder
        """
        )

        values = [row["enumlabel"] for row in result]
        assert values == [
            "pending",
            "shadow",
            "enforcing",
            "complete",
        ], f"migration_phase_enum should have values ['pending', 'shadow', 'enforcing', 'complete'], got {values}"

    # =========================================================================
    # AC3: UNIQUE Constraint on project_id
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unique_constraint_on_project_id(
        self, test_db, migration_path
    ) -> None:
        """INTEGRATION: Verify UNIQUE constraint on project_id (AC3)

        GIVEN migration 032 has been applied AND project exists
        WHEN inserting duplicate status for same project
        THEN unique constraint violation occurs
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        # Insert test project
        await test_db.execute(
            """
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-unique-rls', 'Test Unique RLS', 'shared')
            ON CONFLICT (project_id) DO NOTHING
        """
        )

        # First insert should succeed
        await test_db.execute(
            """
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ('test-unique-rls', 'pending')
        """
        )

        # Second insert should fail (UNIQUE constraint)
        with pytest.raises(asyncpg.UniqueViolationError):
            await test_db.execute(
                """
                INSERT INTO rls_migration_status (project_id, migration_phase)
                VALUES ('test-unique-rls', 'shadow')
            """
            )

        # Cleanup
        await test_db.execute(
            "DELETE FROM project_registry WHERE project_id = 'test-unique-rls'"
        )

    # =========================================================================
    # AC4: Index on project_id
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_index_on_project_id_exists(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify index on project_id exists (AC4)

        GIVEN migration 032 has been applied
        WHEN checking pg_indexes
        THEN idx_rls_status_project_id index exists
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'rls_migration_status'
                  AND indexname = 'idx_rls_status_project_id'
            )
        """
        )

        assert result is True, "idx_rls_status_project_id index should exist"

    # =========================================================================
    # AC5: Index on migration_phase
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_index_on_migration_phase_exists(
        self, test_db, migration_path
    ) -> None:
        """INTEGRATION: Verify index on migration_phase exists (AC5)

        GIVEN migration 032 has been applied
        WHEN checking pg_indexes
        THEN idx_rls_status_migration_phase index exists
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'rls_migration_status'
                  AND indexname = 'idx_rls_status_migration_phase'
            )
        """
        )

        assert result is True, "idx_rls_status_migration_phase index should exist"

    # =========================================================================
    # AC6: Rollback Script Available
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_rollback_drops_table_and_enum(
        self, test_db, migration_path, rollback_path
    ) -> None:
        """INTEGRATION: Verify rollback cleans up table and enum (AC6)

        GIVEN migration 032 is applied
        WHEN rollback script is executed
        THEN rls_migration_status table is dropped
        AND migration_phase_enum type is dropped
        AND trigger is dropped
        """
        await self._ensure_project_registry_exists(test_db)
        # First apply migration
        await self._run_migration(test_db, migration_path)

        # Verify table and enum exist
        table_exists = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'rls_migration_status'
            )
        """
        )
        assert table_exists is True, "Table should exist before rollback"

        enum_exists = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'migration_phase_enum'
            )
        """
        )
        assert enum_exists is True, "Enum should exist before rollback"

        trigger_exists = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'update_rls_migration_status_updated_at'
            )
        """
        )
        assert trigger_exists is True, "Trigger should exist before rollback"

        # Execute rollback
        await self._run_migration(test_db, rollback_path)

        # Verify table is dropped
        table_exists_after = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'rls_migration_status'
            )
        """
        )
        assert table_exists_after is False, "Table should be dropped after rollback"

        # Verify enum is dropped
        enum_exists_after = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'migration_phase_enum'
            )
        """
        )
        assert enum_exists_after is False, "Enum should be dropped after rollback"

        # Verify trigger is dropped
        trigger_exists_after = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'update_rls_migration_status_updated_at'
            )
        """
        )
        assert trigger_exists_after is False, "Trigger should be dropped after rollback"

    # =========================================================================
    # Foreign Key Constraint Tests
    # =========================================================================

    @pytest.mark.P0
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_foreign_key_constraint(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify foreign key constraint with CASCADE delete

        GIVEN migration 032 has been applied AND project_registry has test data
        WHEN inserting status with invalid project_id
        THEN foreign key violation occurs

        GIVEN a status exists AND project is deleted
        THEN status is automatically deleted (CASCADE)
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        # Test FK violation: Insert with non-existent project_id should fail
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await test_db.execute(
                """
                INSERT INTO rls_migration_status (project_id, migration_phase)
                VALUES ('non-existent-project', 'pending')
            """
            )

        # Insert test project for valid insert test
        await test_db.execute(
            """
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-rls-project', 'Test RLS Project', 'isolated')
            ON CONFLICT (project_id) DO NOTHING
        """
        )

        # Test valid insert
        await test_db.execute(
            """
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ('test-rls-project', 'pending')
        """
        )

        # Verify insert succeeded
        count = await test_db.fetchval(
            """
            SELECT COUNT(*) FROM rls_migration_status
            WHERE project_id = 'test-rls-project'
        """
        )
        assert count == 1, "Status should be inserted for valid project_id"

        # Test CASCADE delete
        await test_db.execute(
            "DELETE FROM project_registry WHERE project_id = 'test-rls-project'"
        )

        # Verify status was deleted
        count = await test_db.fetchval(
            """
            SELECT COUNT(*) FROM rls_migration_status
            WHERE project_id = 'test-rls-project'
        """
        )
        assert count == 0, "Status should be CASCADE deleted when project is deleted"

    # =========================================================================
    # Trigger Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_updated_at_trigger_exists(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify updated_at trigger exists

        GIVEN migration 032 has been applied
        WHEN checking pg_trigger
        THEN update_rls_migration_status_updated_at trigger exists
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        result = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'update_rls_migration_status_updated_at'
                  AND tgrelid = 'rls_migration_status'::regclass
            )
        """
        )

        assert result is True, "updated_at trigger should exist"

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_updated_at_auto_updates(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify updated_at auto-updates on row modification

        GIVEN migration 032 has been applied AND status exists
        WHEN updating the status
        THEN updated_at is automatically set to current timestamp
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        # Insert test project and status
        await test_db.execute(
            """
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-trigger-rls', 'Test Trigger RLS', 'isolated')
            ON CONFLICT (project_id) DO NOTHING
        """
        )

        await test_db.execute(
            """
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ('test-trigger-rls', 'pending')
        """
        )

        # Get initial updated_at
        initial = await test_db.fetchrow(
            """
            SELECT updated_at FROM rls_migration_status WHERE project_id = 'test-trigger-rls'
        """
        )

        # Wait a bit and update
        await asyncio.sleep(0.01)

        await test_db.execute(
            """
            UPDATE rls_migration_status SET rls_enabled = TRUE WHERE project_id = 'test-trigger-rls'
        """
        )

        # Get updated updated_at
        updated = await test_db.fetchrow(
            """
            SELECT updated_at FROM rls_migration_status WHERE project_id = 'test-trigger-rls'
        """
        )

        assert (
            updated["updated_at"] > initial["updated_at"]
        ), "updated_at should be updated by trigger"

        # Cleanup
        await test_db.execute(
            "DELETE FROM project_registry WHERE project_id = 'test-trigger-rls'"
        )

    # =========================================================================
    # Default Values Tests
    # =========================================================================

    @pytest.mark.P1
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_default_values(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify default values are applied correctly

        GIVEN migration 032 has been applied AND project exists
        WHEN inserting status without explicit values
        THEN rls_enabled defaults to FALSE and migration_phase defaults to 'pending'
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        # Insert test project
        await test_db.execute(
            """
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-defaults-rls', 'Test Defaults RLS', 'shared')
            ON CONFLICT (project_id) DO NOTHING
        """
        )

        # Insert without explicit values
        await test_db.execute(
            """
            INSERT INTO rls_migration_status (project_id)
            VALUES ('test-defaults-rls')
        """
        )

        # Verify defaults
        result = await test_db.fetchrow(
            """
            SELECT rls_enabled, migration_phase
            FROM rls_migration_status
            WHERE project_id = 'test-defaults-rls'
        """
        )

        assert result["rls_enabled"] is False, "rls_enabled should default to FALSE"
        assert (
            result["migration_phase"] == "pending"
        ), "migration_phase should default to 'pending'"

        # Cleanup
        await test_db.execute(
            "DELETE FROM project_registry WHERE project_id = 'test-defaults-rls'"
        )

    # =========================================================================
    # Idempotency & Additional Tests
    # =========================================================================

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_idempotent(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify migration can be run multiple times safely

        GIVEN migration 032 has been applied
        WHEN running migration again
        THEN no errors occur (IF NOT EXISTS handles it)
        """
        await self._ensure_project_registry_exists(test_db)
        # Run migration first time
        await self._run_migration(test_db, migration_path)

        # Verify table exists
        result1 = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'rls_migration_status'
            )
        """
        )
        assert result1 is True, "Table should exist after first migration"

        # Run migration second time - should NOT error due to IF NOT EXISTS guards
        await self._run_migration(test_db, migration_path)

        # Verify table still exists
        result2 = await test_db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'rls_migration_status'
            )
        """
        )
        assert result2 is True, "Table should still exist after second migration"

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_table_comments_exist(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify table and column comments exist for documentation

        GIVEN migration 032 has been applied
        WHEN checking pg_description
        THEN comments exist for table and key columns
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        # Check table comment
        table_comment = await test_db.fetchval(
            """
            SELECT obj_description('rls_migration_status'::regclass, 'pg_class')
        """
        )

        assert (
            table_comment is not None
        ), "rls_migration_status table should have a comment"
        assert (
            "migration" in table_comment.lower() or "rls" in table_comment.lower()
        ), "Table comment should mention migration or RLS"

        # Check key column comments
        rls_enabled_comment = await test_db.fetchval(
            """
            SELECT col_description('rls_migration_status'::regclass, ordinal_position)
            FROM information_schema.columns
            WHERE table_name = 'rls_migration_status' AND column_name = 'rls_enabled'
        """
        )

        assert (
            rls_enabled_comment is not None
        ), "rls_enabled column should have a comment"

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migration_phase_enum_all_values_valid(
        self, test_db, migration_path
    ) -> None:
        """INTEGRATION: Verify all enum values can be used

        GIVEN migration 032 has been applied AND project exists
        WHEN inserting status with each enum value
        THEN all values ('pending', 'shadow', 'enforcing', 'complete') are valid
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        enum_values = ["pending", "shadow", "enforcing", "complete"]

        for phase in enum_values:
            # Insert test project for each phase
            project_id = f"test-enum-{phase}"
            await test_db.execute(
                """
                INSERT INTO project_registry (project_id, name, access_level)
                VALUES ($1, 'Test Enum Project', 'isolated')
                ON CONFLICT (project_id) DO NOTHING
            """,
                project_id,
            )

            # Insert status with this phase
            await test_db.execute(
                """
                INSERT INTO rls_migration_status (project_id, migration_phase)
                VALUES ($1, $2)
            """,
                project_id,
                phase,
            )

            # Verify it was inserted
            result = await test_db.fetchval(
                """
                SELECT migration_phase FROM rls_migration_status WHERE project_id = $1
            """,
                project_id,
            )

            assert result == phase, f"Phase '{phase}' should be valid"

            # Cleanup
            await test_db.execute(
                "DELETE FROM project_registry WHERE project_id = $1", project_id
            )

    @pytest.mark.P2
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_migrated_at_nullable(self, test_db, migration_path) -> None:
        """INTEGRATION: Verify migrated_at is nullable and can be set

        GIVEN migration 032 has been applied AND project exists
        WHEN inserting status without migrated_at
        THEN migrated_at is NULL

        WHEN updating status to set migrated_at
        THEN migrated_at can be set to a timestamp
        """
        await self._ensure_project_registry_exists(test_db)
        await self._run_migration(test_db, migration_path)

        # Insert test project
        await test_db.execute(
            """
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES ('test-migrated-at', 'Test Migrated At', 'isolated')
            ON CONFLICT (project_id) DO NOTHING
        """
        )

        # Insert without migrated_at
        await test_db.execute(
            """
            INSERT INTO rls_migration_status (project_id, migration_phase)
            VALUES ('test-migrated-at', 'shadow')
        """
        )

        # Verify migrated_at is NULL
        result = await test_db.fetchrow(
            """
            SELECT migrated_at FROM rls_migration_status WHERE project_id = 'test-migrated-at'
        """
        )
        assert result["migrated_at"] is None, "migrated_at should be NULL initially"

        # Update to set migrated_at
        await test_db.execute(
            """
            UPDATE rls_migration_status
            SET migrated_at = NOW(), migration_phase = 'enforcing'
            WHERE project_id = 'test-migrated-at'
        """
        )

        # Verify migrated_at is set
        result = await test_db.fetchrow(
            """
            SELECT migrated_at FROM rls_migration_status WHERE project_id = 'test-migrated-at'
        """
        )
        assert (
            result["migrated_at"] is not None
        ), "migrated_at should be set after update"

        # Cleanup
        await test_db.execute(
            "DELETE FROM project_registry WHERE project_id = 'test-migrated-at'"
        )
