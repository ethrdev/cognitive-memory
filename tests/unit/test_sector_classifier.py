"""
Unit Tests for Memory Sector Classification

Tests the MemorySector type and classify_memory_sector() function.
Uses golden set fixtures for regression testing.

Author: Epic 8 Implementation
Story: 8.1 - Schema Migration & Data Classification
Story: 8.2 - Sector Classification Logic (added logging tests)
"""

import logging
import pytest

from mcp_server.utils.sector_classifier import (
    DEFAULT_SECTOR,
    VALID_SECTORS,
    MemorySector,
    classify_memory_sector,
    validate_sector,
)
from tests.fixtures.golden_set_sectors import GOLDEN_SET_SECTORS


class TestMemorySectorType:
    """Test MemorySector Literal type definition and imports."""

    def test_memory_sector_type_exists(self):
        """Test that MemorySector type can be imported."""
        assert MemorySector is not None
        assert callable(MemorySector) or isinstance(MemorySector, type)

    def test_valid_sectors_list(self):
        """Test that VALID_SECTORS contains all 5 expected sectors."""
        expected_sectors = {"emotional", "episodic", "semantic", "procedural", "reflective"}
        assert set(VALID_SECTORS) == expected_sectors
        assert len(VALID_SECTORS) == 5

    def test_all_sectors_lowercase(self):
        """Test that all sector values are lowercase (critical requirement)."""
        for sector in VALID_SECTORS:
            assert sector == sector.lower(), f"Sector {sector} must be lowercase"

    def test_default_sector_is_semantic(self):
        """Test that DEFAULT_SECTOR is 'semantic'."""
        assert DEFAULT_SECTOR == "semantic"


class TestSectorClassification:
    """Test classify_memory_sector() function with golden set fixtures."""

    @pytest.mark.parametrize("edge", GOLDEN_SET_SECTORS)
    def test_classify_with_golden_set(self, edge):
        """Test classification against 20 pre-classified golden set edges."""
        result = classify_memory_sector(edge["relation"], edge["properties"])
        assert result == edge["expected_sector"], (
            f"Edge {edge['source']} -> {edge['target']} "
            f"({edge['relation']}) classified as {result}, "
            f"expected {edge['expected_sector']}"
        )

    def test_classify_emotional_sector(self):
        """Test emotional sector classification with valence property."""
        result = classify_memory_sector("EXPERIENCED", {"emotional_valence": "positive"})
        assert result == "emotional"

    def test_classify_episodic_sector(self):
        """Test episodic sector classification with shared_experience context."""
        result = classify_memory_sector(
            "PARTICIPATED_IN",
            {"context_type": "shared_experience"}
        )
        assert result == "episodic"

    def test_classify_procedural_sector_learned(self):
        """Test procedural sector classification for LEARNED relation."""
        result = classify_memory_sector("LEARNED", {"difficulty": "intermediate"})
        assert result == "procedural"

    def test_classify_procedural_sector_can_do(self):
        """Test procedural sector classification for CAN_DO relation."""
        result = classify_memory_sector("CAN_DO", {"proficiency": "advanced"})
        assert result == "procedural"

    def test_classify_reflective_sector_reflects(self):
        """Test reflective sector classification for REFLECTS_ON relation."""
        result = classify_memory_sector("REFLECTS_ON", {"depth": "deep"})
        assert result == "reflective"

    def test_classify_reflective_sector_realized(self):
        """Test reflective sector classification for REALIZED relation."""
        result = classify_memory_sector("REALIZED", {"insight": "visual_learner"})
        assert result == "reflective"

    def test_classify_semantic_sector_default(self):
        """Test semantic sector as default for unclassified edges."""
        result = classify_memory_sector("RELATED_TO", {"similarity": 0.8})
        assert result == "semantic"

    def test_classification_priority_emotional_over_relation(self):
        """Test that emotional property takes priority over relation type."""
        # This edge has REFLECTS_ON relation (reflective) but emotional_valence (emotional)
        # Priority: emotional wins
        result = classify_memory_sector(
            "REFLECTS_ON",
            {"emotional_valence": "positive", "depth": "deep"}
        )
        assert result == "emotional"

    def test_classification_priority_episodic_over_relation(self):
        """Test that shared_experience context takes priority over relation type."""
        # This edge has LEARNED relation (procedural) but shared_experience (episodic)
        # Priority: episodic wins
        result = classify_memory_sector(
            "LEARNED",
            {"context_type": "shared_experience"}
        )
        assert result == "episodic"

    def test_classification_with_empty_properties(self):
        """Test classification with empty properties dict."""
        result = classify_memory_sector("CONNECTED_TO", {})
        assert result == "semantic"

    def test_classification_with_missing_properties(self):
        """Test classification when properties is None or missing."""
        # Handle None properties gracefully
        result = classify_memory_sector("CONNECTED_TO", None)
        assert result == "semantic"


class TestValidateSector:
    """Test validate_sector() helper function."""

    def test_validate_valid_sectors(self):
        """Test validation of all valid sector values."""
        for sector in VALID_SECTORS:
            assert validate_sector(sector), f"Sector {sector} should be valid"

    def test_validate_uppercase_rejected(self):
        """Test that uppercase sector values are rejected."""
        assert not validate_sector("Emotional")
        assert not validate_sector("EMOTIONAL")
        assert not validate_sector("Episodic")

    def test_validate_invalid_sectors(self):
        """Test validation rejects invalid sector strings."""
        assert not validate_sector("invalid")
        assert not validate_sector("")
        assert not validate_sector("memory")
        assert not validate_sector(" feelings")

    def test_validate_case_sensitive(self):
        """Test that validation is case-sensitive."""
        assert validate_sector("emotional")
        assert not validate_sector("Emotional")
        assert not validate_sector("EMOTIONAL")


class TestSectorDistribution:
    """Test golden set covers all sectors adequately."""

    def test_golden_set_covers_all_sectors(self):
        """Test that golden set contains at least one edge per sector."""
        sectors_in_set = {edge["expected_sector"] for edge in GOLDEN_SET_SECTORS}
        expected_sectors = set(VALID_SECTORS)
        assert sectors_in_set == expected_sectors, (
            f"Golden set missing sectors: {expected_sectors - sectors_in_set}"
        )

    def test_golden_set_minimum_edges_per_sector(self):
        """Test that each sector has at least 3 representative edges."""
        sector_counts = {}
        for edge in GOLDEN_SET_SECTORS:
            sector = edge["expected_sector"]
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        for sector in VALID_SECTORS:
            assert sector_counts.get(sector, 0) >= 3, (
                f"Sector {sector} has insufficient coverage in golden set "
                f"(found {sector_counts.get(sector, 0)}, need at least 3)"
            )

    def test_golden_set_size(self):
        """Test that golden set contains exactly 20 edges."""
        assert len(GOLDEN_SET_SECTORS) == 20


class TestSectorClassificationLogging:
    """Test DEBUG logging for sector classification decisions (Story 8.2, AC #7)."""

    def test_classify_emotional_logs_at_debug_level(self, caplog):
        """Verify emotional classification logs decision at DEBUG level with rule_matched."""
        with caplog.at_level(logging.DEBUG):
            result = classify_memory_sector("EXPERIENCED", {"emotional_valence": "positive"})

        assert result == "emotional"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG
        assert caplog.records[0].sector == "emotional"
        assert caplog.records[0].rule_matched == "emotional_valence"

    def test_classify_episodic_logs_at_debug_level(self, caplog):
        """Verify episodic classification logs decision at DEBUG level with rule_matched."""
        with caplog.at_level(logging.DEBUG):
            result = classify_memory_sector(
                "PARTICIPATED_IN",
                {"context_type": "shared_experience"}
            )

        assert result == "episodic"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG
        assert caplog.records[0].sector == "episodic"
        assert caplog.records[0].rule_matched == "shared_experience"

    def test_classify_procedural_logs_at_debug_level(self, caplog):
        """Verify procedural classification logs decision at DEBUG level with rule_matched."""
        with caplog.at_level(logging.DEBUG):
            result = classify_memory_sector("LEARNED", {"difficulty": "intermediate"})

        assert result == "procedural"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG
        assert caplog.records[0].sector == "procedural"
        assert caplog.records[0].rule_matched == "procedural_relation"

    def test_classify_reflective_logs_at_debug_level(self, caplog):
        """Verify reflective classification logs decision at DEBUG level with rule_matched."""
        with caplog.at_level(logging.DEBUG):
            result = classify_memory_sector("REFLECTS_ON", {"depth": "deep"})

        assert result == "reflective"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG
        assert caplog.records[0].sector == "reflective"
        assert caplog.records[0].rule_matched == "reflective_relation"

    def test_classify_semantic_default_logs_at_debug_level(self, caplog):
        """Verify semantic default classification logs decision at DEBUG level with rule_matched."""
        with caplog.at_level(logging.DEBUG):
            result = classify_memory_sector("CONNECTED_TO", {"similarity": 0.8})

        assert result == "semantic"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG
        assert caplog.records[0].sector == "semantic"
        assert caplog.records[0].rule_matched == "default_semantic"

    def test_classification_with_none_properties_logs(self, caplog):
        """Verify classification with None properties logs default semantic."""
        with caplog.at_level(logging.DEBUG):
            result = classify_memory_sector("RELATED_TO", None)

        assert result == "semantic"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG
        assert caplog.records[0].sector == "semantic"
        assert caplog.records[0].rule_matched == "default_semantic"

    def test_classification_priority_emotional_over_relation_logs(self, caplog):
        """Verify that emotional priority logs correctly even when relation suggests different sector."""
        with caplog.at_level(logging.DEBUG):
            result = classify_memory_sector(
                "REFLECTS_ON",
                {"emotional_valence": "positive", "depth": "deep"}
            )

        assert result == "emotional"
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG
        assert caplog.records[0].sector == "emotional"
        assert caplog.records[0].rule_matched == "emotional_valence"

    def test_logging_does_not_affect_classification_result(self, caplog):
        """Verify logging is pure side effect and doesn't change classification behavior."""
        with caplog.at_level(logging.DEBUG):
            result = classify_memory_sector("LEARNED", {"difficulty": "intermediate"})

        # Result should be procedural regardless of logging
        assert result == "procedural"
        # But logging should have occurred
        assert len(caplog.records) == 1
        assert caplog.records[0].sector == "procedural"

    def test_validate_sector_logs_invalid_rejection(self, caplog):
        """Integration test: verify validate_sector logs rejection of invalid sectors."""
        with caplog.at_level(logging.DEBUG):
            result = validate_sector("InvalidSector")

        # Should reject invalid sector
        assert result is False
        # Should log the rejection
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG
        assert caplog.records[0].sector == "InvalidSector"
        assert caplog.records[0].valid_sectors == VALID_SECTORS
