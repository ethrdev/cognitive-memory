"""
Golden Set Fixtures for Memory Sector Classification

This module provides pre-classified edge fixtures for regression testing.
These fixtures represent known-good classifications that must remain
stable across implementation changes.

Author: Epic 8 Implementation
Story: 8.1 - Schema Migration & Data Classification
"""

from typing import Final

# Golden Set: 20 pre-classified edges covering all 5 sectors
# Each fixture represents a real-world edge with its expected sector
GOLDEN_SET_SECTORS: Final = [
    # Emotional Sector (4 edges)
    {
        "source": "I/O",
        "target": "Kirchenpark-Moment",
        "relation": "EXPERIENCED",
        "properties": {"emotional_valence": "positive"},
        "expected_sector": "emotional"
    },
    {
        "source": "User",
        "target": "First-Bug-Fix",
        "relation": "RESOLVED",
        "properties": {"emotional_valence": "negative"},
        "expected_sector": "emotional"
    },
    {
        "source": "Team",
        "target": "Project-Launch",
        "relation": "CELEBRATED",
        "properties": {"emotional_valence": "positive", "intensity": "high"},
        "expected_sector": "emotional"
    },
    {
        "source": "I",
        "target": "Career-Change",
        "relation": "EXPERIENCED",
        "properties": {"emotional_valence": "neutral", "context": "life_event"},
        "expected_sector": "emotional"
    },

    # Episodic Sector (4 edges)
    {
        "source": "I/O",
        "target": "Coffee-Break-Discussion",
        "relation": "PARTICIPATED_IN",
        "properties": {"context_type": "shared_experience", "participants": ["Alice", "Bob"]},
        "expected_sector": "episodic"
    },
    {
        "source": "Team",
        "target": "Sprint-Planning-2025-01-08",
        "relation": "HELD",
        "properties": {"context_type": "shared_experience", "duration": "2h"},
        "expected_sector": "episodic"
    },
    {
        "source": "User",
        "target": "Conference-Talk",
        "relation": "ATTENDED",
        "properties": {"context_type": "shared_experience", "location": "Berlin"},
        "expected_sector": "episodic"
    },
    {
        "source": "Pair-Programmers",
        "target": "Debugging-Session",
        "relation": "COLLABORATED_ON",
        "properties": {"context_type": "shared_experience", "outcome": "bug_fixed"},
        "expected_sector": "episodic"
    },

    # Procedural Sector (4 edges)
    {
        "source": "Developer",
        "target": "Python-Programming",
        "relation": "LEARNED",
        "properties": {"difficulty": "intermediate"},
        "expected_sector": "procedural"
    },
    {
        "source": "User",
        "target": "Docker-Containerization",
        "relation": "CAN_DO",
        "properties": {"proficiency": "advanced"},
        "expected_sector": "procedural"
    },
    {
        "source": "Student",
        "target": "Recursion-Algorithm",
        "relation": "LEARNED",
        "properties": {"practice_count": 10},
        "expected_sector": "procedural"
    },
    {
        "source": "Engineer",
        "target": "System-Design",
        "relation": "MASTERED",
        "properties": {"years_of_practice": 5},
        "expected_sector": "semantic"  # MASTERED not in procedural list
    },

    # Reflective Sector (4 edges)
    {
        "source": "I",
        "target": "Career-Goals",
        "relation": "REFLECTS_ON",
        "properties": {"depth": "deep"},
        "expected_sector": "reflective"
    },
    {
        "source": "User",
        "target": "Learning-Pattern",
        "relation": "REALIZED",
        "properties": {"insight": "visual_learner"},
        "expected_sector": "reflective"
    },
    {
        "source": "Self",
        "target": "Burnout-Signals",
        "relation": "REFLECTS_ON",
        "properties": {"trigger": "quarterly_review"},
        "expected_sector": "reflective"
    },
    {
        "source": "I",
        "target": "Communication-Style",
        "relation": "REALIZED",
        "properties": {"feedback_source": "peer_review"},
        "expected_sector": "reflective"
    },

    # Semantic Sector (4 edges) - default fallback
    {
        "source": "Concept-A",
        "target": "Concept-B",
        "relation": "RELATED_TO",
        "properties": {"similarity": 0.8},
        "expected_sector": "semantic"
    },
    {
        "source": "Python",
        "target": "Programming-Language",
        "relation": "IS_A",
        "properties": {},
        "expected_sector": "semantic"
    },
    {
        "source": "REST-API",
        "target": "HTTP-Protocol",
        "relation": "USES",
        "properties": {"version": "1.1"},
        "expected_sector": "semantic"
    },
    {
        "source": "Database",
        "target": "PostgreSQL",
        "relation": "IMPLEMENTED_AS",
        "properties": {"version": "15"},
        "expected_sector": "semantic"
    },
]
