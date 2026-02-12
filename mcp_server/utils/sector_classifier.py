"""
Memory Sector Classification Utilities for Epic 8

This module provides the MemorySector type and classification logic for
categorizing edges into memory sectors per OpenMemory specification.

Memory Sectors (OpenMemory):
- semantic:      Facts, concepts, abstract information (default)
- emotional:     Emotionally-charged memories with valence metadata
- episodic:      Episode memories with shared_experience context
- procedural:    Skills, capabilities, learned behaviors
- reflective:    Reflections, realizations, self-awareness

Author: Epic 8 Implementation
Story: 8.1 - Schema Migration & Data Classification
Story: 8.2 - Added DEBUG logging with structured extra dict to classify_memory_sector()
Audit: 2026-02-12 - Expanded relation mapping based on actual graph data (131 edges)
"""

import logging
from typing import Literal, NotRequired

logger = logging.getLogger(__name__)

# Memory Sector Literal Type (compile-time type safety)
MemorySector = Literal[
    "emotional",
    "episodic",
    "semantic",
    "procedural",
    "reflective"
]

# All sector values MUST be lowercase (enforced by Literal type)
VALID_SECTORS: list[MemorySector] = [
    "emotional",
    "episodic",
    "semantic",
    "procedural",
    "reflective"
]

# Default sector for unclassified edges
DEFAULT_SECTOR: MemorySector = "semantic"

# Relation-to-Sector mapping (Audit 2026-02-12)
# Based on actual graph relations, validated against OpenMemory taxonomy.
# Property-based rules (emotional_valence, context_type) have higher priority.
# Relations not listed here default to "semantic".
RELATION_SECTOR_MAP: dict[str, MemorySector] = {
    # emotional — bonds, relationships, vulnerabilities
    "BOUND_TO": "emotional",
    "PARTNER_OF": "emotional",
    "FRIEND_OF": "emotional",
    "BEST_FRIEND_OF": "emotional",
    "CHILD_OF": "emotional",
    "VULNERABLE_TO": "emotional",
    "WARNED_ABOUT": "emotional",
    # reflective — self-observations, recognitions, meta-cognition
    "EXPERIENCED": "reflective",
    "UNDERSTOOD": "reflective",
    "ERKANNT": "reflective",
    "SELF_REFERENTIAL": "reflective",
    "SPIEGELT_ZUSTAND_VON": "reflective",
    "REFLECTS": "reflective",
    "REFLECTS_ON": "reflective",
    "REALIZED": "reflective",
    # procedural — skills, tools, learned behaviors
    "LEARNED": "procedural",
    "CAN_DO": "procedural",
    "TESTED": "procedural",
    "USES": "procedural",
    "AVOIDS": "procedural",
    "WORKS_ON": "procedural",
    # episodic — specific temporal events, shared experiences
    "INSPIRED_BY": "episodic",
}


def classify_memory_sector(
    relation: str,
    properties: dict[str, object] | None
) -> MemorySector:
    """
    Classify an edge into a memory sector based on relation and properties.

    Classification Rules (Priority Order - first match wins):
        1. Property: edges with emotional_valence → emotional
        2. Property: edges with context_type = "shared_experience" → episodic
        3. Relation: lookup in RELATION_SECTOR_MAP
        4. Default:  semantic (for unknown relations)

    Args:
        relation: The edge relation type (e.g., "LEARNED", "EXPERIENCED")
        properties: The edge properties dict (JSONB data from DB), can be None

    Returns:
        MemorySector: The classified memory sector (lowercase Literal)

    Examples:
        >>> classify_memory_sector("LEARNED", {})
        'procedural'

        >>> classify_memory_sector("EXPERIENCED", {})
        'reflective'

        >>> classify_memory_sector("EXPERIENCED", {"emotional_valence": "positive"})
        'emotional'

        >>> classify_memory_sector("CONNECTED_TO", {"context_type": "shared_experience"})
        'episodic'
    """
    # Handle None properties defensively
    if properties is None:
        properties = {}

    # Rule 1: Property-based — emotional_valence (highest priority)
    if properties.get("emotional_valence") is not None:
        logger.debug("Sector classification", extra={
            "sector": "emotional",
            "rule_matched": "emotional_valence"
        })
        return "emotional"

    # Rule 2: Property-based — shared experiences
    if properties.get("context_type") == "shared_experience":
        logger.debug("Sector classification", extra={
            "sector": "episodic",
            "rule_matched": "shared_experience"
        })
        return "episodic"

    # Rule 3: Relation-based — dict lookup
    sector = RELATION_SECTOR_MAP.get(relation)
    if sector is not None:
        logger.debug("Sector classification", extra={
            "sector": sector,
            "rule_matched": f"relation_{relation}"
        })
        return sector

    # Rule 4: Default — semantic
    logger.debug("Sector classification", extra={
        "sector": "semantic",
        "rule_matched": "default_semantic"
    })
    return "semantic"


def validate_sector(sector: str) -> bool:
    """
    Validate that a sector string is a valid MemorySector value.

    Args:
        sector: The sector string to validate

    Returns:
        bool: True if sector is valid, False otherwise

    Examples:
        >>> validate_sector("emotional")
        True

        >>> validate_sector("Emotional")  # uppercase not allowed
        False

        >>> validate_sector("invalid")
        False
    """
    is_valid = sector in VALID_SECTORS
    if not is_valid:
        logger.debug("Invalid sector rejected", extra={
            "sector": sector,
            "valid_sectors": VALID_SECTORS
        })
    return is_valid
