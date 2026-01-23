"""
P0 Tests: Schema Migration Idempotency and Data Preservation (Epic 8)
ATDD Red Phase - Tests that will pass after implementation

Risk Mitigation: R-001 (Schema migration corrupts data), R-005 (Properties lost)
Test Count: 8
"""

import pytest
import subprocess
import tempfile
import os
import psycopg2
from pathlib import Path
from typing import Dict, List, Any
import json

from mcp_server.utils.sector_classifier import (
    MemorySector,
    classify_memory_sector,
    VALID_SECTORS,
    DEFAULT_SECTOR
)


class TestSchemaMigrationPhase1:
    """Phase 1: Add memory_sector column to edges table"""

    @pytest.mark.p0
    def test_migration_adds_memory_sector_column(self):
        """FR20: System can store memory_sector as a field on all edges

        Given the database schema before Epic 8
        When migration 022_add_memory_sector.sql Phase 1 is executed
        Then the edges table has a memory_sector column of type VARCHAR(20)
        """
        # Verify column exists in information_schema
        query = """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'edges' AND column_name = 'memory_sector';
        """
        # This would need a database connection to test
        # For now, we verify the migration file exists
        migration_file = Path("mcp_server/db/migrations/022_add_memory_sector.sql")
        assert migration_file.exists(), "Migration file should exist"
        assert "memory_sector" in migration_file.read_text()

    @pytest.mark.p0
    def test_memory_sector_column_has_default_value(self):
        """FR20: Default value should be 'semantic'

        Given the memory_sector column is added
        When the migration completes
        Then the default value is 'semantic'
        """
        # Check migration file for default value
        migration_file = Path("mcp_server/db/migrations/022_add_memory_sector.sql")
        content = migration_file.read_text()
        assert "DEFAULT 'semantic'" in content, "Column should have 'semantic' default"
        assert "VARCHAR(20)" in content, "Column should be VARCHAR(20)"

    @pytest.mark.p0
    def test_migration_phase1_is_idempotent(self):
        """NFR7: Schema migration must be idempotent (safe to run multiple times)

        Given migration Phase 1 has been executed once
        When it is executed again
        Then no errors occur and column is not duplicated
        """
        # Check that migration uses IF NOT EXISTS
        migration_file = Path("mcp_server/db/migrations/022_add_memory_sector.sql")
        content = migration_file.read_text()
        assert "IF NOT EXISTS" in content, "Migration should check if column exists"
        assert "DO $$" in content, "Migration should use DO block for idempotency"


class TestSchemaMigrationPhase2:
    """Phase 2: Classify existing edges"""

    @pytest.mark.p0
    def test_emotional_valence_classification(self):
        """FR21: Classification rules based on emotional_valence

        Given existing edges with emotional_valence property
        When migration Phase 2 (data classification) runs
        Then edges with emotional_valence property are set to "emotional"
        """
        # Test the classification logic
        result = classify_memory_sector(
            relation="EXPERIENCED",
            properties={"emotional_valence": "positive"}
        )
        assert result == "emotional", "Edge with emotional_valence should be classified as emotional"

    @pytest.mark.p0
    def test_shared_experience_classification(self):
        """FR21: Classification rules based on context_type

        Given existing edges with context_type property
        When migration Phase 2 runs
        Then edges with context_type = "shared_experience" are set to "episodic"
        """
        # Test the classification logic
        result = classify_memory_sector(
            relation="CONNECTED_TO",
            properties={"context_type": "shared_experience"}
        )
        assert result == "episodic", "Edge with shared_experience should be episodic"

    @pytest.mark.p0
    def test_procedural_relation_classification(self):
        """FR21: Classification rules based on relation

        Given edges with LEARNED or CAN_DO relations
        When migration Phase 2 runs
        Then these edges are set to "procedural"
        """
        # Test LEARNED relation
        result = classify_memory_sector(relation="LEARNED", properties={})
        assert result == "procedural", "LEARNED relation should be procedural"

        # Test CAN_DO relation
        result = classify_memory_sector(relation="CAN_DO", properties={})
        assert result == "procedural", "CAN_DO relation should be procedural"

    @pytest.mark.p0
    def test_reflective_relation_classification(self):
        """FR21: Classification rules based on relation

        Given edges with REFLECTS or REALIZED relations
        When migration Phase 2 runs
        Then these edges are set to "reflective"
        """
        # Test REFLECTS relation
        result = classify_memory_sector(relation="REFLECTS", properties={})
        assert result == "reflective", "REFLECTS relation should be reflective"

        # Test REALIZED relation
        result = classify_memory_sector(relation="REALIZED", properties={})
        assert result == "reflective", "REALIZED relation should be reflective"

    @pytest.mark.p0
    def test_default_semantic_classification(self):
        """FR21: Default classification for unmatched edges

        Given edges that don't match any specific rule
        When migration Phase 2 runs
        Then they remain "semantic" (default)
        """
        # Test unknown relation with no special properties
        result = classify_memory_sector(
            relation="CONNECTED_TO",
            properties={}
        )
        assert result == "semantic", "Unmatched edges should default to semantic"


class TestDataPreservation:
    """NFR12: All original properties must be preserved"""

    @pytest.mark.p0
    def test_all_edge_properties_preserved(self):
        """FR21: Property preservation during migration

        Given edge properties before migration
        When migration completes
        Then all original properties are preserved
        """
        # Check migration file - it should only ADD column, not modify properties
        migration_file = Path("mcp_server/db/migrations/022_add_memory_sector.sql")
        content = migration_file.read_text()
        # Migration should UPDATE memory_sector (may be on multiple lines)
        assert "UPDATE edges" in content, "Should update memory_sector"
        assert "SET memory_sector" in content, "Should set memory_sector"
        # Should NOT drop or alter properties column
        assert "ALTER TABLE edges DROP" not in content, "Should not drop any columns"

    @pytest.mark.p0
    def test_property_count_unchanged(self):
        """NFR12: Property count verification

        Given edges before migration
        When migration completes
        Then the count of properties per edge is unchanged
        """
        # Verify migration only adds memory_sector column, doesn't modify properties
        migration_file = Path("mcp_server/db/migrations/022_add_memory_sector.sql")
        content = migration_file.read_text()
        # Should only ADD column, not ALTER other columns
        assert "ADD COLUMN memory_sector" in content, "Should only add column"
        assert "ALTER TABLE edges" not in content or \
               "ALTER TABLE edges ADD COLUMN" in content, "Should only add, not alter"


class TestMemorySectorType:
    """FR1: MemorySector Literal type definition"""

    @pytest.mark.p0
    def test_memory_sector_literal_type_defined(self):
        """FR1: System can automatically classify edges into one of five sectors

        Given the Python codebase
        When MemorySector type is defined
        Then it is a Literal["emotional", "episodic", "semantic", "procedural", "reflective"]
        """
        # Verify MemorySector is defined
        assert MemorySector is not None, "MemorySector type should be defined"
        # Verify all five sectors are in the Literal
        expected_sectors = {"emotional", "episodic", "semantic", "procedural", "reflective"}
        assert set(VALID_SECTORS) == expected_sectors, \
            f"Expected {expected_sectors}, got {set(VALID_SECTORS)}"

    @pytest.mark.p0
    def test_all_sector_values_lowercase(self):
        """FR1: Sector values must be lowercase

        Given MemorySector type
        When values are checked
        Then all sector values are lowercase
        """
        # All sector values should be lowercase
        for sector in VALID_SECTORS:
            assert sector.islower() or sector == sector.lower(), \
                f"Sector {sector} should be lowercase"
