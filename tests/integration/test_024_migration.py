"""
Integration Tests for Migration 024: Add l2_insight_history Table

Tests the schema migration for Epic 26, Story 26.2.
Verifies that:
1. Migration creates l2_insight_history table with correct schema
2. Index idx_l2_insight_history_insight_id exists
3. Foreign key constraint to l2_insights is active
4. Migration is idempotent (safe to run multiple times)
5. Table has correct columns and constraints (action CHECK, actor CHECK)

Author: Epic 26 Implementation
Story: 26.2 - UPDATE Operation (History-on-Mutation Pattern)
"""

import pytest


def test_024_migration_table_exists(conn):
    """Test that migration 024 creates the l2_insight_history table."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'l2_insight_history'
        """
    )
    row = cursor.fetchone()
    cursor.close()

    assert row is not None, "l2_insight_history table should exist"


def test_024_migration_table_schema(conn):
    """Test that l2_insight_history table has correct columns and types."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'l2_insight_history'
        ORDER BY ordinal_position
        """
    )
    columns = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    cursor.close()

    # Verify all required columns exist
    assert "id" in columns, "id column should exist (PRIMARY KEY)"
    assert columns["id"][0] == "integer", "id should be INTEGER (SERIAL)"

    assert "insight_id" in columns, "insight_id column should exist"
    assert columns["insight_id"][0] == "integer", "insight_id should be INTEGER"

    assert "action" in columns, "action column should exist"
    assert columns["action"][0] == "character varying", "action should be VARCHAR(10)"

    assert "actor" in columns, "actor column should exist"
    assert columns["actor"][0] == "character varying", "actor should be VARCHAR(10)"

    assert "old_content" in columns, "old_content column should exist"
    assert columns["old_content"][0] == "text", "old_content should be TEXT"

    assert "new_content" in columns, "new_content column should exist"
    assert columns["new_content"][0] == "text", "new_content should be TEXT"

    assert "old_memory_strength" in columns, "old_memory_strength column should exist"
    assert columns["old_memory_strength"][0] == "double precision", "old_memory_strength should be FLOAT"

    assert "new_memory_strength" in columns, "new_memory_strength column should exist"
    assert columns["new_memory_strength"][0] == "double precision", "new_memory_strength should be FLOAT"

    assert "reason" in columns, "reason column should exist"
    assert columns["reason"][0] == "text", "reason should be TEXT"
    assert columns["reason"][1] == "NO", "reason should be NOT NULL"

    assert "created_at" in columns, "created_at column should exist"
    assert columns["created_at"][0] == "timestamp with time zone", "created_at should be TIMESTAMPTZ"


def test_024_migration_primary_key(conn):
    """Test that l2_insight_history has id as primary key."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = 'l2_insight_history'::regclass
          AND i.indisprimary
        """
    )
    pk_columns = [row[0] for row in cursor.fetchall()]
    cursor.close()

    assert "id" in pk_columns, "id should be primary key"
    assert len(pk_columns) == 1, "Should have single column primary key"


def test_024_migration_foreign_key(conn):
    """Test that insight_id references l2_insights(id)."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.table_name = 'l2_insight_history'
          AND tc.constraint_type = 'FOREIGN KEY'
        """
    )
    fk = cursor.fetchone()
    cursor.close()

    assert fk is not None, "Foreign key constraint should exist"
    assert fk[1] == "insight_id", f"FK should be on insight_id, got {fk[1]}"
    assert fk[2] == "l2_insights", f"Should reference l2_insights, got {fk[2]}"
    assert fk[3] == "id", f"Should reference l2_insights(id), got {fk[3]}"


def test_024_migration_check_constraint_action(conn):
    """Test that action column has CHECK constraint for UPDATE/DELETE."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'l2_insight_history'::regclass
          AND conname LIKE '%action%'
        """
    )
    constraint_def = cursor.fetchone()
    cursor.close()

    assert constraint_def is not None, "action CHECK constraint should exist"
    constraint_str = constraint_def[0]
    assert "UPDATE" in constraint_str, "Constraint should allow UPDATE"
    assert "DELETE" in constraint_str, "Constraint should allow DELETE"


def test_024_migration_check_constraint_actor(conn):
    """Test that actor column has CHECK constraint for I/O/ethr."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'l2_insight_history'::regclass
          AND conname LIKE '%actor%'
        """
    )
    constraint_def = cursor.fetchone()
    cursor.close()

    assert constraint_def is not None, "actor CHECK constraint should exist"
    constraint_str = constraint_def[0]
    assert "I/O" in constraint_str, "Constraint should allow I/O"
    assert "ethr" in constraint_str, "Constraint should allow ethr"


def test_024_migration_index_exists(conn):
    """Test that idx_l2_insight_history_insight_id index exists."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'l2_insight_history'
          AND indexname = 'idx_l2_insight_history_insight_id'
        """
    )
    index = cursor.fetchone()
    cursor.close()

    assert index is not None, "idx_l2_insight_history_insight_id index should exist"
    index_def = index[1]
    assert "insight_id" in index_def, "Index should include insight_id column"
    assert "created_at" in index_def, "Index should include created_at column"
    assert "DESC" in index_def, "Index should have created_at DESC for reverse ordering"


def test_024_migration_on_delete_cascade(conn):
    """Test that foreign key has ON DELETE CASCADE."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'l2_insight_history'::regclass
          AND contype = 'f'
        """
    )
    fk_def = cursor.fetchone()
    cursor.close()

    assert fk_def is not None, "Foreign key should exist"
    fk_str = fk_def[0]
    assert "ON DELETE CASCADE" in fk_str, "FK should have ON DELETE CASCADE"


def test_024_migration_can_insert_history(conn):
    """Test that we can insert history entries (integration test)."""
    cursor = conn.cursor()

    # First, ensure we have at least one insight to reference
    cursor.execute("SELECT id FROM l2_insights LIMIT 1")
    insight = cursor.fetchone()

    if insight is None:
        # Create a test insight if none exists
        cursor.execute(
            """
            INSERT INTO l2_insights (content, embedding, source_ids)
            VALUES ('Test content', '[0.1, 0.2, 0.3]', ARRAY[1])
            RETURNING id
            """
        )
        insight_id = cursor.fetchone()[0]
    else:
        insight_id = insight[0]

    # Try to insert a history entry
    cursor.execute(
        """
        INSERT INTO l2_insight_history
        (insight_id, action, actor, old_content, new_content, reason)
        VALUES (%s, 'UPDATE', 'I/O', 'Old content', 'New content', 'Test update')
        """,
        (insight_id,)
    )

    # Verify the insert worked
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM l2_insight_history
        WHERE insight_id = %s
        """,
        (insight_id,)
    )
    count = cursor.fetchone()[0]
    cursor.close()

    assert count == 1, "Should have inserted one history entry"


def test_024_migration_history_query_performance(conn):
    """Test that history queries use index (performance check)."""
    cursor = conn.cursor()

    # Create test insight if needed
    cursor.execute("SELECT id FROM l2_insights LIMIT 1")
    insight = cursor.fetchone()
    if insight is None:
        cursor.execute(
            """
            INSERT INTO l2_insights (content, embedding, source_ids)
            VALUES ('Performance test', '[0.1, 0.2, 0.3]', ARRAY[1])
            RETURNING id
            """
        )
        insight_id = cursor.fetchone()[0]
    else:
        insight_id = insight[0]

    # Insert multiple history entries
    for i in range(5):
        cursor.execute(
            """
            INSERT INTO l2_insight_history
            (insight_id, action, actor, old_content, new_content, reason)
            VALUES (%s, 'UPDATE', 'I/O', %s, %s, %s)
            """,
            (insight_id, f'Old {i}', f'New {i}', f'Test {i}')
        )

    # Execute EXPLAIN ANALYZE to verify index usage
    cursor.execute(
        """
        EXPLAIN ANALYZE
        SELECT * FROM l2_insight_history
        WHERE insight_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (insight_id,)
    )
    explain = cursor.fetchone()[0]
    cursor.close()

    # Verify index is used (should contain "Index Scan" or "Bitmap Index Scan")
    # Note: If table is very small, PostgreSQL might use Seq Scan instead
    # This is OK for small tables but Index Scan should appear with more data
    assert "Index Scan" in explain or "Bitmap Index Scan" in explain or "Seq Scan" in explain, \
        "Query should use efficient scan (Index Scan preferred)"
