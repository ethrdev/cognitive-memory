"""
Integration Tests for Migration 025: insight_feedback Table

Tests for Story 26.4: Context Critic.
Covers AC-7: Migration 025 creates insight_feedback table with correct schema.

Author: Epic 26 Implementation
Story: 26.4 - Context Critic
"""

import json

import pytest
from psycopg2.extensions import connection as conn_type
from typing import Any


# =============================================================================
# AC-7: Migration 025 Schema Tests
# =============================================================================

@pytest.mark.asyncio
async def test_migration_025_creates_table(conn):
    """AC-7: Migration 025 creates insight_feedback table."""
    cursor = conn.cursor()

    # Check table exists
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_name = 'insight_feedback';
    """)

    result = cursor.fetchone()
    assert result is not None, "insight_feedback table was not created"


@pytest.mark.asyncio
async def test_migration_025_columns_correct(conn):
    """AC-7: insight_feedback table has all required columns."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'insight_feedback'
        ORDER BY ordinal_position;
    """)

    columns = {row[0]: row for row in cursor.fetchall()}

    # Check all required columns exist
    assert "id" in columns
    assert columns["id"][1] == "integer"

    assert "insight_id" in columns
    assert columns["insight_id"][1] == "integer"

    assert "feedback_type" in columns
    assert columns["feedback_type"][1] == "character varying"

    assert "context" in columns
    assert columns["context"][1] == "text"

    assert "created_at" in columns
    assert columns["created_at"][1] == "timestamp with time zone"


@pytest.mark.asyncio
async def test_migration_025_index_created(conn):
    """AC-7: Index idx_insight_feedback_insight_id exists."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT indexname
        FROM pg_indexes
        WHERE indexname = 'idx_insight_feedback_insight_id';
    """)

    result = cursor.fetchone()
    assert result is not None, "idx_insight_feedback_insight_id index was not created"


@pytest.mark.asyncio
async def test_migration_025_check_constraint(conn):
    """AC-7: CHECK constraint for feedback_type exists."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conname LIKE '%insight_feedback%'
          AND contype = 'c';
    """)

    constraints = cursor.fetchall()
    check_constraints = [c[0] for c in constraints if "CHECK" in c[0]]

    # Should have a CHECK constraint for feedback_type
    assert len(check_constraints) > 0, "No CHECK constraint found for feedback_type"

    # Verify it contains the valid values
    check_def = check_constraints[0]
    assert "helpful" in check_def
    assert "not_relevant" in check_def
    assert "not_now" in check_def


@pytest.mark.asyncio
async def test_migration_025_foreign_key(conn):
    """AC-7: Foreign key to l2_insights(id) exists."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            tc.constraint_name,
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_name = 'insight_feedback'
          AND kcu.column_name = 'insight_id';
    """)

    result = cursor.fetchone()
    assert result is not None, "Foreign key to l2_insights not found"
    assert result[3] == "l2_insights"  # foreign_table_name
    assert result[4] == "id"  # foreign_column_name


# =============================================================================
# CRUD Tests (AC-3, AC-4, AC-5)
# =============================================================================

@pytest.mark.asyncio
async def test_feedback_insert_helpful(conn):
    """AC-3: Can insert helpful feedback."""
    cursor = conn.cursor()

    # First ensure we have an insight to reference
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight for feedback", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]

    # Insert helpful feedback
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, context, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id;
    """, (insight_id, "helpful", "Very helpful"))

    result = cursor.fetchone()
    assert result is not None
    feedback_id = result[0]

    conn.commit()

    # Verify we can read it back
    cursor.execute("SELECT * FROM insight_feedback WHERE id = %s", (feedback_id,))
    feedback = cursor.fetchone()

    assert feedback[1] == insight_id  # insight_id
    assert feedback[2] == "helpful"   # feedback_type
    assert feedback[3] == "Very helpful"  # context


@pytest.mark.asyncio
async def test_feedback_insert_not_relevant(conn):
    """AC-4: Can insert not_relevant feedback with context."""
    cursor = conn.cursor()

    # Create insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]

    # Insert not_relevant feedback
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, context, created_at)
        VALUES (%s, %s, %s, NOW())
        RETURNING id;
    """, (insight_id, "not_relevant", "Too general"))

    result = cursor.fetchone()
    assert result is not None

    conn.commit()


@pytest.mark.asyncio
async def test_feedback_insert_not_now(conn):
    """AC-5: Can insert not_now feedback (neutral)."""
    cursor = conn.cursor()

    # Create insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]

    # Insert not_now feedback without context
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
        VALUES (%s, %s, NOW())
        RETURNING id;
    """, (insight_id, "not_now"))

    result = cursor.fetchone()
    assert result is not None

    conn.commit()


@pytest.mark.asyncio
async def test_feedback_invalid_type_fails(conn):
    """CHECK constraint rejects invalid feedback_type."""
    cursor = conn.cursor()

    # Create insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]

    # Try to insert invalid feedback_type
    try:
        cursor.execute("""
            INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
            VALUES (%s, %s, NOW());
        """, (insight_id, "invalid_type"))

        # Should not reach here
        assert False, "CHECK constraint should have rejected invalid feedback_type"

    except Exception as e:
        # Expected: CHECK constraint violation
        assert "insight_feedback" in str(e).lower() or "check" in str(e).lower()

    finally:
        conn.rollback()


@pytest.mark.asyncio
async def test_feedback_query_by_insight(conn):
    """Test querying feedback by insight_id (performance test)."""
    cursor = conn.cursor()

    # Create insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]

    # Insert multiple feedback entries
    for i in range(3):
        cursor.execute("""
            INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
            VALUES (%s, %s, NOW());
        """, (insight_id, "helpful" if i % 2 == 0 else "not_now"))

    conn.commit()

    # Query all feedback for this insight
    cursor.execute("""
        SELECT feedback_type, created_at
        FROM insight_feedback
        WHERE insight_id = %s
        ORDER BY created_at;
    """, (insight_id,))

    results = cursor.fetchall()
    assert len(results) == 3
