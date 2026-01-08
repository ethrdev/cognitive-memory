"""
Integration Tests for Migration 022: Add Memory Sector Column

Tests the schema migration and data classification for Epic 8.
Verifies that:
1. Migration is idempotent (safe to run multiple times)
2. All edges have memory_sector set (no NULL values)
3. Original edge properties are preserved
4. Classification rules work correctly

Author: Epic 8 Implementation
Story: 8.1 - Schema Migration & Data Classification
"""

import pytest

from mcp_server.db.connection import get_connection


def test_022_migration_adds_column(conn):
    """Test that migration 022 adds the memory_sector column to edges table."""
    # Check that memory_sector column exists
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT column_name, data_type, column_default
        FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'memory_sector'
        """
    )
    row = cursor.fetchone()

    assert row is not None, "memory_sector column should exist"
    assert row[1] == "character varying", "Column should be VARCHAR type"
    assert row[2] == "'semantic'::character varying", "Default should be 'semantic'"
    cursor.close()


def test_022_migration_no_null_values(conn):
    """Test that all edges have memory_sector set (no NULL values after migration)."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM edges WHERE memory_sector IS NULL")
    null_count = cursor.fetchone()[0]
    cursor.close()

    assert null_count == 0, f"All edges should have memory_sector set, found {null_count} NULL values"


def test_022_migration_properties_preserved(conn):
    """Test that original edge properties are preserved after migration."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, relation, properties, memory_sector
        FROM edges
        WHERE properties != '{}'
        LIMIT 5
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    assert len(rows) > 0, "Should have at least some edges with properties"

    for row in rows:
        assert row[2] is not None, f"Edge {row['id']} should have properties"
        assert isinstance(row[2], dict), f"Properties should be a dict for edge {row['id']}"
        assert row[3] is not None, f"Edge {row['id']} should have memory_sector"


def test_022_migration_classification_emotional(conn):
    """Test that edges with emotional_valence are classified as emotional."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, relation, properties, memory_sector
        FROM edges
        WHERE properties->>'emotional_valence' IS NOT NULL
        LIMIT 10
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    for row in rows:
        assert row[3] == "emotional", (
            f"Edge {row[0]} with emotional_valence should be 'emotional', "
            f"got '{row[3]}'"
        )


def test_022_migration_classification_episodic(conn):
    """Test that edges with shared_experience context are classified as episodic."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, relation, properties, memory_sector
        FROM edges
        WHERE properties->>'context_type' = 'shared_experience'
        LIMIT 10
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    for row in rows:
        # Should be episodic unless emotional_valence takes priority (classification order)
        if row[2].get("emotional_valence") is None:
            assert row[3] == "episodic", (
                f"Edge {row[0]} with shared_experience should be 'episodic', "
                f"got '{row[3]}'"
            )
        else:
            # emotional takes priority over episodic
            assert row[3] == "emotional", (
                f"Edge {row[0]} with both emotional_valence and shared_experience "
                f"should be 'emotional' (priority), got '{row[3]}'"
            )


def test_022_migration_classification_procedural(conn):
    """Test that LEARNED and CAN_DO relations are classified as procedural."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, relation, properties, memory_sector
        FROM edges
        WHERE relation IN ('LEARNED', 'CAN_DO')
        LIMIT 10
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    for row in rows:
        # Should be procedural unless emotional_valence or shared_experience takes priority
        if row[2].get("emotional_valence") is None and \
           row[2].get("context_type") != "shared_experience":
            assert row[3] == "procedural", (
                f"Edge {row[0]} with relation {row[1]} should be 'procedural', "
                f"got '{row[3]}'"
            )


def test_022_migration_classification_reflective(conn):
    """Test that REFLECTS, REFLECTS_ON, and REALIZED relations are classified as reflective."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, relation, properties, memory_sector
        FROM edges
        WHERE relation IN ('REFLECTS', 'REFLECTS_ON', 'REALIZED')
        LIMIT 10
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    for row in rows:
        # Should be reflective unless emotional_valence or shared_experience takes priority
        if row[2].get("emotional_valence") is None and \
           row[2].get("context_type") != "shared_experience":
            assert row[3] == "reflective", (
                f"Edge {row[0]} with relation {row[1]} should be 'reflective', "
                f"got '{row[3]}'"
            )


def test_022_migration_sector_distribution(conn):
    """Test that migration created a reasonable sector distribution."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT memory_sector, COUNT(*) as count
        FROM edges
        GROUP BY memory_sector
        ORDER BY count DESC
        """
    )
    rows = cursor.fetchall()
    cursor.close()

    assert len(rows) > 0, "Should have at least one sector"

    # All sectors should be valid MemorySector values
    valid_sectors = {"emotional", "episodic", "semantic", "procedural", "reflective"}
    for row in rows:
        assert row[0] in valid_sectors, f"Invalid sector '{row[0]}' found"

    # At minimum, we should have semantic edges (default)
    sectors_found = {row[0] for row in rows}
    assert "semantic" in sectors_found, "Should have at least some semantic edges"


def test_022_migration_idempotent(conn):
    """Test that migration is idempotent - running it twice doesn't cause errors."""
    cursor = conn.cursor()

    # Get current edge count
    cursor.execute("SELECT COUNT(*) FROM edges")
    edge_count_before = cursor.fetchone()[0]

    # Get current sector distribution
    cursor.execute("SELECT memory_sector, COUNT(*) FROM edges GROUP BY memory_sector")
    dist_before = cursor.fetchall()
    dist_before_dict = {row[0]: row[1] for row in dist_before}

    # Run migration again (simulate by running the UPDATE statements)
    # Note: In a real test, we'd execute the migration file, but for now we verify
    # that running the UPDATEs again doesn't change anything
    cursor.execute(
        """
        UPDATE edges
        SET memory_sector = 'emotional'
        WHERE properties->>'emotional_valence' IS NOT NULL
          AND memory_sector = 'semantic'
        """
    )

    cursor.execute(
        """
        UPDATE edges
        SET memory_sector = 'episodic'
        WHERE properties->>'context_type' = 'shared_experience'
          AND memory_sector = 'semantic'
        """
    )

    cursor.execute(
        """
        UPDATE edges
        SET memory_sector = 'procedural'
        WHERE relation IN ('LEARNED', 'CAN_DO')
          AND memory_sector = 'semantic'
        """
    )

    cursor.execute(
        """
        UPDATE edges
        SET memory_sector = 'reflective'
        WHERE relation IN ('REFLECTS', 'REFLECTS_ON', 'REALIZED')
          AND memory_sector = 'semantic'
        """
    )

    # Verify edge count hasn't changed
    cursor.execute("SELECT COUNT(*) FROM edges")
    edge_count_after = cursor.fetchone()[0]
    assert edge_count_before == edge_count_after, "Edge count should not change"

    # Verify distribution hasn't changed
    cursor.execute("SELECT memory_sector, COUNT(*) FROM edges GROUP BY memory_sector")
    dist_after = cursor.fetchall()
    dist_after_dict = {row[0]: row[1] for row in dist_after}

    assert dist_before_dict == dist_after_dict, "Sector distribution should not change on re-run"
    cursor.close()

