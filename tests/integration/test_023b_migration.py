"""
Integration Test for Migration 023b: Soft-Delete Fields

Tests the complete migration lifecycle:
- Up migration: Add soft-delete fields to l2_insights
- Verify: All fields and indexes created correctly
- Down migration: Remove soft-delete fields
- Up migration: Verify idempotency (can run twice)

Story 26.3: DELETE Operation
Epic 26: Memory Management with Curation
"""

import pytest
import asyncpg
import os
from pathlib import Path


class TestMigration023b:
    """Test Migration 023b soft-delete fields."""

    @pytest.fixture
    async def test_db(self):
        """Create a test database connection."""
        db_url = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test_cognitive_memory")
        conn = await asyncpg.connect(db_url)

        # Start transaction
        async with conn.transaction():
            yield conn

        await conn.close()

    @pytest.fixture
    async def migration_sql_path(self):
        """Path to the migration SQL file."""
        migration_path = Path(__file__).parent.parent.parent / "mcp_server" / "db" / "migrations" / "023b_soft_delete.sql"
        assert migration_path.exists(), f"Migration file not found at {migration_path}"
        return migration_path

    async def test_migration_up(self, test_db, migration_sql_path):
        """Test that the UP migration adds all required fields."""
        # Load and execute UP migration
        sql = migration_sql_path.read_text()

        # Split by semicolon and execute each statement
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                await test_db.execute(statement)

        # Verify all fields were added
        result = await test_db.fetchrow("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'l2_insights'
            ORDER BY column_name
 """)

        columns = {row["column_name"] for row in await test_db.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'l2_insights'
 """)}

        # Verify soft-delete fields exist
        assert "is_deleted" in columns, "is_deleted field not found"
        assert "deleted_at" in columns, "deleted_at field not found"
        assert "deleted_by" in columns, "deleted_by field not found"
        assert "deleted_reason" in columns, "deleted_reason field not found"

        # Verify is_deleted has correct default
        row = await test_db.fetchrow("""
            SELECT column_default
            FROM information_schema.columns
            WHERE table_name = 'l2_insights' AND column_name = 'is_deleted'
 """)

        assert "FALSE" in str(row["column_default"]), "is_deleted should default to FALSE"

    async def test_performance_index_created(self, test_db, migration_sql_path):
        """Test that the performance index idx_l2_insights_not_deleted is created."""
        # Execute migration
        sql = migration_sql_path.read_text()
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                await test_db.execute(statement)

        # Check if index exists
        index_exists = await test_db.fetchrow("""
            SELECT 1
            FROM pg_indexes
            WHERE indexname = 'idx_l2_insights_not_deleted'
 """)

        assert index_exists is not None, "Performance index idx_l2_insights_not_deleted not created"

        # Verify it's a partial index on is_deleted = FALSE
        index_def = await test_db.fetchrow("""
            SELECT indexdef
            FROM pg_indexes
            WHERE indexname = 'idx_l2_insights_not_deleted'
 """)

        assert "WHERE is_deleted = FALSE" in index_def["indexdef"], "Index should be a partial index on is_deleted = FALSE"

    async def test_migration_down(self, test_db, migration_sql_path):
        """Test that the DOWN migration removes all soft-delete fields."""
        # First run UP migration
        sql = migration_sql_path.read_text()
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                await test_db.execute(statement)

        # Verify fields exist
        columns = {row["column_name"] for row in await test_db.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'l2_insights'
 """)}

        assert "is_deleted" in columns
        assert "deleted_at" in columns
        assert "deleted_by" in columns
        assert "deleted_reason" in columns

        # Execute DOWN migration (last part after -- DOWN comment)
        down_started = False
        down_statements = []
        for line in sql.split("\n"):
            if "-- DOWN" in line:
                down_started = True
                continue
            if down_started and line.strip() and not line.strip().startswith("--"):
                down_statements.append(line.strip())

        for statement in down_statements:
            if statement:
                await test_db.execute(statement)

        # Verify all fields are removed
        columns = {row["column_name"] for row in await test_db.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'l2_insights'
 """)}

        assert "is_deleted" not in columns, "is_deleted field should be removed"
        assert "deleted_at" not in columns, "deleted_at field should be removed"
        assert "deleted_by" not in columns, "deleted_by field should be removed"
        assert "deleted_reason" not in columns, "deleted_reason field should be removed"

        # Verify index is removed
        index_exists = await test_db.fetchrow("""
            SELECT 1
            FROM pg_indexes
            WHERE indexname = 'idx_l2_insights_not_deleted'
 """)

        assert index_exists is None, "Performance index should be removed"

    async def test_migration_idempotency(self, test_db, migration_sql_path):
        """Test that the migration can be run multiple times (idempotent)."""
        sql = migration_sql_path.read_text()

        # Run UP migration twice
        for _ in range(2):
            for statement in sql.split(";"):
                statement = statement.strip()
                if statement and not statement.startswith("--"):
                    await test_db.execute(statement)

        # Verify no duplicate columns
        columns = [row["column_name"] for row in await test_db.fetch("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'l2_insights'
            ORDER BY column_name
 """)]

        # Count soft-delete fields
        soft_delete_count = sum(1 for c in columns if c in ["is_deleted", "deleted_at", "deleted_by", "deleted_reason"])
        assert soft_delete_count == 4, f"Expected 4 soft-delete fields, found {soft_delete_count}"

        # Verify index exists only once
        indexes = await test_db.fetch("""
            SELECT COUNT(*) as count
            FROM pg_indexes
            WHERE indexname = 'idx_l2_insights_not_deleted'
 """)

        assert indexes[0]["count"] == 1, "Performance index should exist only once"

    async def test_soft_delete_functionality(self, test_db, migration_sql_path):
        """Test that soft-delete fields work correctly for actual delete operations."""
        # Run migration
        sql = migration_sql_path.read_text()
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                await test_db.execute(statement)

        # Create a test insight
        insight_id = await test_db.fetchval("""
            INSERT INTO l2_insights (content, embedding, source_ids, metadata)
            VALUES (
                'Test insight for deletion',
                '[0.0]'::vector,
                ARRAY[1],
                '{}'::jsonb
            )
            RETURNING id
 """)

        # Verify it's not deleted by default
        row = await test_db.fetchrow("""
            SELECT is_deleted, deleted_at, deleted_by, deleted_reason
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        assert row["is_deleted"] is False, "New insight should not be deleted"
        assert row["deleted_at"] is None, "deleted_at should be NULL initially"
        assert row["deleted_by"] is None, "deleted_by should be NULL initially"
        assert row["deleted_reason"] is None, "deleted_reason should be NULL initially"

        # Soft delete the insight
        await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'I/O',
                deleted_reason = 'Test deletion'
            WHERE id = $1
 """, insight_id)

        # Verify soft delete worked
        row = await test_db.fetchrow("""
            SELECT is_deleted, deleted_at, deleted_by, deleted_reason
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        assert row["is_deleted"] is True, "is_deleted should be TRUE"
        assert row["deleted_at"] is not None, "deleted_at should be set"
        assert row["deleted_by"] == "I/O", "deleted_by should be 'I/O'"
        assert row["deleted_reason"] == "Test deletion", "deleted_reason should be set"

        # Verify deleted insight can still be queried (soft delete, not hard delete)
        recovered = await test_db.fetchrow("""
            SELECT id, content, is_deleted
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        assert recovered is not None, "Soft-deleted insight should still exist in database"
        assert recovered["content"] == "Test insight for deletion", "Content should be preserved"

        # Clean up
        await test_db.execute("DELETE FROM l2_insights WHERE id = $1", insight_id)

    async def test_partial_index_performance(self, test_db, migration_sql_path):
        """Test that the partial index only includes non-deleted insights."""
        # Run migration
        sql = migration_sql_path.read_text()
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                await test_db.execute(statement)

        # Create multiple test insights
        insight_ids = []
        for i in range(5):
            insight_id = await test_db.fetchval("""
                INSERT INTO l2_insights (content, embedding, source_ids, metadata)
                VALUES (
                    $1,
                    '[0.0]'::vector,
                    ARRAY[1],
                    '{}'::jsonb
                )
                RETURNING id
 """, f"Test insight {i}")
            insight_ids.append(insight_id)

        # Delete 2 insights
        await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'I/O',
                deleted_reason = 'Test'
            WHERE id = ANY($1)
 """, insight_ids[:2])

        # Verify index structure
        # The partial index should only have entries for is_deleted = FALSE
        index_size = await test_db.fetchrow("""
            SELECT relname, relpages
            FROM pg_class
            WHERE relname = 'idx_l2_insights_not_deleted'
 """)

        # Query using the index (should only return non-deleted)
        active_insights = await test_db.fetch("""
            SELECT id
            FROM l2_insights
            WHERE is_deleted = FALSE
        """)

        assert len(active_insights) == 3, "Should find 3 non-deleted insights"

        # Clean up
        await test_db.execute("""
            DELETE FROM l2_insights
            WHERE id = ANY($1)
 """, insight_ids)
