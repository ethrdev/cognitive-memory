"""
Integration Tests for Migration 023: Add memory_strength Column

Tests the schema migration for Epic 26, Story 26.1.
Verifies that:
1. Migration adds memory_strength column to l2_insights table
2. All existing insights get default value 0.5
3. Migration is idempotent (safe to run multiple times)
4. Column has correct type and default value

Author: Epic 26 Implementation
Story: 26.1 - Memory Strength Field für I/O's Bedeutungszuweisung
"""

import pytest


def test_023_migration_adds_column(conn):
    """Test that migration 023 adds the memory_strength column to l2_insights table."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'memory_strength'
        """
    )
    row = cursor.fetchone()
    cursor.close()

    assert row is not None, "memory_strength column should exist"
    assert row[1] == "double precision", "Column should be FLOAT (DOUBLE PRECISION) type"
    # Default should be 0.5
    assert "0.5" in str(row[2]), f"Default should be 0.5, got {row[2]}"


def test_023_migration_no_null_values(conn):
    """Test that all insights have memory_strength set (no NULL values after migration)."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM l2_insights WHERE memory_strength IS NULL")
    null_count = cursor.fetchone()[0]
    cursor.close()

    assert null_count == 0, f"All insights should have memory_strength set, found {null_count} NULL values"


def test_023_migration_default_values(conn):
    """Test that insights have valid memory_strength values after migration."""
    cursor = conn.cursor()

    # Verify that all insights have a valid memory_strength value (no NULL)
    # and that values are in the valid range [0.0, 1.0]
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM l2_insights
        WHERE memory_strength IS NULL
           OR memory_strength < 0.0
           OR memory_strength > 1.0
        """
    )
    invalid_count = cursor.fetchone()[0]
    cursor.close()

    # All insights should have valid memory_strength values
    assert invalid_count == 0, f"All insights should have valid memory_strength in [0.0, 1.0], found {invalid_count} with invalid values"


def test_023_migration_column_properties(conn):
    """Test that memory_strength column has correct properties."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            is_nullable,
            data_type,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'memory_strength'
        """
    )
    row = cursor.fetchone()
    cursor.close()

    assert row is not None, "memory_strength column should exist"
    assert row[0] == "YES", "Column should be nullable (for backward compat)"
    assert row[1] == "double precision", "Column should be DOUBLE PRECISION (FLOAT)"
    # FLOAT has high precision (53 bits)
    assert row[2] == 53, f"Precision should be 53 bits, got {row[2]}"


def test_023_migration_insight_data_preserved(conn):
    """Test that original insight data is preserved after migration."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, content, source_ids, metadata, memory_strength
        FROM l2_insights
        LIMIT 5
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    assert len(rows) > 0, "Should have at least some insights for testing"

    for row in rows:
        assert row["id"] is not None, f"Insight {row['id']} should have ID"
        assert row["content"] is not None, f"Insight {row['id']} should have content"
        assert row["source_ids"] is not None, f"Insight {row['id']} should have source_ids"
        assert row["metadata"] is not None, f"Insight {row['id']} should have metadata"
        assert row["memory_strength"] == 0.5, f"Insight {row['id']} should have memory_strength=0.5"


def test_023_migration_idempotent(conn):
    """Test that migration is idempotent - running it twice doesn't cause errors."""
    cursor = conn.cursor()

    # Get current insight count
    cursor.execute("SELECT COUNT(*) FROM l2_insights")
    insight_count_before = cursor.fetchone()[0]

    # Simulate running migration again (UPDATE statement)
    cursor.execute(
        """
        UPDATE l2_insights
        SET memory_strength = 0.5
        WHERE memory_strength IS NULL
        """
    )

    # Verify insight count hasn't changed
    cursor.execute("SELECT COUNT(*) FROM l2_insights")
    insight_count_after = cursor.fetchone()[0]

    assert insight_count_before == insight_count_after, "Insight count should not change"

    # Verify no NULL values exist
    cursor.execute("SELECT COUNT(*) FROM l2_insights WHERE memory_strength IS NULL")
    null_count = cursor.fetchone()[0]

    assert null_count == 0, "No NULL values should exist after re-running migration"
    cursor.close()


def test_023_migration_value_range(conn):
    """Test that all memory_strength values are in valid range [0.0, 1.0]."""
    cursor = conn.cursor()

    # Check for invalid values (outside 0.0-1.0 range)
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM l2_insights
        WHERE memory_strength < 0.0 OR memory_strength > 1.0
        """
    )
    invalid_count = cursor.fetchone()[0]
    cursor.close()

    assert invalid_count == 0, f"All memory_strength values should be in [0.0, 1.0], found {invalid_count} invalid values"


def test_023_migration_statistics(conn):
    """Test that migration created valid memory_strength statistics."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            COUNT(*) as total_insights,
            AVG(memory_strength) as avg_strength,
            MIN(memory_strength) as min_strength,
            MAX(memory_strength) as max_strength
        FROM l2_insights
        """
    )
    row = cursor.fetchone()
    cursor.close()

    assert row["total_insights"] >= 0, "Should have non-negative insight count"
    # Values should be in valid range [0.0, 1.0]
    assert 0.0 <= row["avg_strength"] <= 1.0, f"Average should be in [0.0, 1.0], got {row['avg_strength']}"
    assert 0.0 <= row["min_strength"] <= 1.0, f"Min should be in [0.0, 1.0], got {row['min_strength']}"
    assert 0.0 <= row["max_strength"] <= 1.0, f"Max should be in [0.0, 1.0], got {row['max_strength']}"


def test_023_rollback_safety(conn):
    """Test that migration can be safely rolled back."""
    cursor = conn.cursor()

    # Verify column exists
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'memory_strength'
        """
    )
    assert cursor.fetchone() is not None, "memory_strength column should exist"

    # Simulate ROLLBACK (DROP COLUMN IF EXISTS)
    # This is what the DOWN migration does
    cursor.execute("ALTER TABLE l2_insights DROP COLUMN IF EXISTS memory_strength")

    # Verify column is gone
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'memory_strength'
        """
    )
    assert cursor.fetchone() is None, "memory_strength column should be dropped"

    # Re-apply migration (UP)
    cursor.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'l2_insights' AND column_name = 'memory_strength'
            ) THEN
                ALTER TABLE l2_insights ADD COLUMN memory_strength FLOAT DEFAULT 0.5;
            END IF;
        END $$;
        """
    )

    cursor.execute(
        """
        UPDATE l2_insights
        SET memory_strength = 0.5
        WHERE memory_strength IS NULL
        """
    )

    # Verify column is back
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'memory_strength'
        """
    )
    assert cursor.fetchone() is not None, "memory_strength column should exist after re-migration"

    cursor.close()
