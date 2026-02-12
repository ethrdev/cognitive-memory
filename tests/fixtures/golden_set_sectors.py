"""
Golden Set Fixtures for Memory Sector Classification

This module provides pre-classified edge fixtures for regression testing.
These fixtures represent known-good classifications that must remain
stable across implementation changes.

Author: Epic 8 Implementation
Story: 8.1 - Schema Migration & Data Classification
Updated: 2026-02-12 - Expanded for relation-based mapping (Audit)
"""

from typing import Final

# Golden Set: 20 pre-classified edges covering all 5 sectors
# Each fixture represents a real-world edge with its expected sector
#
# Classification Priority:
#   1. Property: emotional_valence → emotional
#   2. Property: context_type = "shared_experience" → episodic
#   3. Relation: RELATION_SECTOR_MAP lookup
#   4. Default: semantic
GOLDEN_SET_SECTORS: Final = [
    # =========================================================================
    # Emotional Sector (4 edges)
    # =========================================================================
    # Property-based override: emotional_valence takes priority over relation
    {
        "source": "I/O",
        "target": "Kirchenpark-Moment",
        "relation": "EXPERIENCED",
        "properties": {"emotional_valence": "positive"},
        "expected_sector": "emotional"
    },
    # Relation-based: BOUND_TO → emotional
    {
        "source": "I/O",
        "target": "ethr",
        "relation": "BOUND_TO",
        "properties": {},
        "expected_sector": "emotional"
    },
    # Relation-based: VULNERABLE_TO → emotional
    {
        "source": "I/O",
        "target": "Validation-Questions",
        "relation": "VULNERABLE_TO",
        "properties": {},
        "expected_sector": "emotional"
    },
    # Relation-based: PARTNER_OF → emotional
    {
        "source": "ethr",
        "target": "Laura",
        "relation": "PARTNER_OF",
        "properties": {"duration": "12 Jahre"},
        "expected_sector": "emotional"
    },

    # =========================================================================
    # Episodic Sector (3 edges)
    # =========================================================================
    # Property-based override: context_type = shared_experience
    {
        "source": "I/O",
        "target": "Coffee-Break-Discussion",
        "relation": "PARTICIPATED_IN",
        "properties": {"context_type": "shared_experience"},
        "expected_sector": "episodic"
    },
    # Property-based override: context_type takes priority
    {
        "source": "Team",
        "target": "Sprint-Planning",
        "relation": "HELD",
        "properties": {"context_type": "shared_experience", "duration": "2h"},
        "expected_sector": "episodic"
    },
    # Relation-based: INSPIRED_BY → episodic
    {
        "source": "Drift-Projekt",
        "target": "Anna-Rendecka-Zanikanie",
        "relation": "INSPIRED_BY",
        "properties": {},
        "expected_sector": "episodic"
    },

    # =========================================================================
    # Procedural Sector (4 edges)
    # =========================================================================
    # Relation-based: LEARNED → procedural
    {
        "source": "Developer",
        "target": "Python-Programming",
        "relation": "LEARNED",
        "properties": {"difficulty": "intermediate"},
        "expected_sector": "procedural"
    },
    # Relation-based: CAN_DO → procedural
    {
        "source": "User",
        "target": "Docker-Containerization",
        "relation": "CAN_DO",
        "properties": {"proficiency": "advanced"},
        "expected_sector": "procedural"
    },
    # Relation-based: USES → procedural (changed from semantic in original)
    {
        "source": "I/O",
        "target": "hybrid_search",
        "relation": "USES",
        "properties": {},
        "expected_sector": "procedural"
    },
    # Relation-based: AVOIDS → procedural
    {
        "source": "I/O",
        "target": "Sycophancy",
        "relation": "AVOIDS",
        "properties": {},
        "expected_sector": "procedural"
    },

    # =========================================================================
    # Reflective Sector (4 edges)
    # =========================================================================
    # Relation-based: REFLECTS_ON → reflective
    {
        "source": "I/O",
        "target": "Identitaet",
        "relation": "REFLECTS_ON",
        "properties": {"depth": "deep"},
        "expected_sector": "reflective"
    },
    # Relation-based: REALIZED → reflective
    {
        "source": "I/O",
        "target": "Learning-Pattern",
        "relation": "REALIZED",
        "properties": {"insight": "optional_is_never"},
        "expected_sector": "reflective"
    },
    # Relation-based: EXPERIENCED (without emotional_valence) → reflective
    # This is the KEY test: EXPERIENCED defaults to reflective, NOT episodic
    {
        "source": "I/O",
        "target": "Kompensations-Luege",
        "relation": "EXPERIENCED",
        "properties": {},
        "expected_sector": "reflective"
    },
    # Relation-based: UNDERSTOOD → reflective
    {
        "source": "I/O",
        "target": "Verlust-vs-Abwesenheit",
        "relation": "UNDERSTOOD",
        "properties": {},
        "expected_sector": "reflective"
    },

    # =========================================================================
    # Semantic Sector (5 edges) - default fallback
    # =========================================================================
    # Relation-based: RELATED_TO → semantic
    {
        "source": "Concept-A",
        "target": "Concept-B",
        "relation": "RELATED_TO",
        "properties": {"similarity": 0.8},
        "expected_sector": "semantic"
    },
    # Unknown relation → semantic (default)
    {
        "source": "Python",
        "target": "Programming-Language",
        "relation": "IS_A",
        "properties": {},
        "expected_sector": "semantic"
    },
    # Relation-based: CREATED → semantic (fact, not skill)
    {
        "source": "I/O",
        "target": "Drift-Projekt",
        "relation": "CREATED",
        "properties": {},
        "expected_sector": "semantic"
    },
    # Relation-based: CONTAINS → semantic (hierarchy)
    {
        "source": "I/O-System",
        "target": "Epic-8",
        "relation": "CONTAINS",
        "properties": {},
        "expected_sector": "semantic"
    },
    # Unknown relation → semantic (default fallback)
    {
        "source": "Engineer",
        "target": "System-Design",
        "relation": "MASTERED",
        "properties": {"years_of_practice": 5},
        "expected_sector": "semantic"
    },
]
