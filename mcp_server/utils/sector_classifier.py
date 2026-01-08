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


def classify_memory_sector(
    relation: str,
    properties: dict[str, object] | None
) -> MemorySector:
    """
    Classify an edge into a memory sector based on relation and properties.

    Classification Rules (Priority Order - first match wins):
        1. Emotional: edges with emotional_valence property
        2. Episodic:  edges with context_type = "shared_experience"
        3. Procedural: edges with relation IN (LEARNED, CAN_DO)
        4. Reflective: edges with relation IN (REFLECTS, REFLECTS_ON, REALIZED)
        5. Semantic:   all other edges (default)

    Args:
        relation: The edge relation type (e.g., "LEARNED", "EXPERIENCED")
        properties: The edge properties dict (JSONB data from DB), can be None

    Returns:
        MemorySector: The classified memory sector (lowercase Literal)

    Examples:
        >>> classify_memory_sector("LEARNED", {})
        'procedural'

        >>> classify_memory_sector("EXPERIENCED", {"emotional_valence": "positive"})
        'emotional'

        >>> classify_memory_sector("CONNECTED_TO", {"context_type": "shared_experience"})
        'episodic'
    """
    # Handle None properties defensively
    if properties is None:
        properties = {}

    # Rule 1: Emotional - edges with emotional_valence property
    if properties.get("emotional_valence") is not None:
        logger.debug("Sector classification", extra={
            "sector": "emotional",
            "rule_matched": "emotional_valence"
        })
        return "emotional"

    # Rule 2: Episodic - shared experiences
    if properties.get("context_type") == "shared_experience":
        logger.debug("Sector classification", extra={
            "sector": "episodic",
            "rule_matched": "shared_experience"
        })
        return "episodic"

    # Rule 3: Procedural - learning-related relations
    if relation in ("LEARNED", "CAN_DO"):
        logger.debug("Sector classification", extra={
            "sector": "procedural",
            "rule_matched": "procedural_relation"
        })
        return "procedural"

    # Rule 4: Reflective - reflection-related relations
    # Support both REFLECTS and REFLECTS_ON (common variant)
    if relation in ("REFLECTS", "REFLECTS_ON", "REALIZED"):
        logger.debug("Sector classification", extra={
            "sector": "reflective",
            "rule_matched": "reflective_relation"
        })
        return "reflective"

    # Rule 5: Semantic - all other edges (default)
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
