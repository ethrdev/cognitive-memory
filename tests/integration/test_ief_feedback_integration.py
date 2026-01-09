"""
Integration Tests for IEF Feedback Integration

Tests for Story 26.4: Context Critic.
Covers AC-3: IEF considers feedback on next query (EP-4 Lazy Evaluation).

Author: Epic 26 Implementation
Story: 26.4 - Context Critic
"""

import json

import pytest
from psycopg2.extensions import connection as conn_type
from typing import Any


# =============================================================================
# AC-3: IEF Score Changes on Next Query
# =============================================================================

@pytest.mark.asyncio
async def test_ief_score_increases_with_helpful_feedback(conn):
    """AC-3: Positive feedback increases IEF score on next query."""
    from mcp_server.analysis.ief import apply_insight_feedback_to_score

    cursor = conn.cursor()

    # Create test insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight for IEF feedback", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]
    conn.commit()

    # Get initial score (without feedback)
    initial_score = 0.6  # Base score
    score_without_feedback = apply_insight_feedback_to_score(initial_score, insight_id)
    assert score_without_feedback == initial_score  # No change without feedback

    # Add helpful feedback
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
        VALUES (%s, %s, NOW());
    """, (insight_id, "helpful"))
    conn.commit()

    # Score should increase by 0.1
    score_with_feedback = apply_insight_feedback_to_score(initial_score, insight_id)
    assert score_with_feedback == initial_score + 0.1


@pytest.mark.asyncio
async def test_ief_score_decreases_with_not_relevant_feedback(conn):
    """AC-4: Negative feedback decreases IEF score on next query."""
    from mcp_server.analysis.ief import apply_insight_feedback_to_score

    cursor = conn.cursor()

    # Create test insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight for negative feedback", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]
    conn.commit()

    # Get initial score
    initial_score = 0.6

    # Add not_relevant feedback
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
        VALUES (%s, %s, NOW());
    """, (insight_id, "not_relevant"))
    conn.commit()

    # Score should decrease by 0.1
    score_with_feedback = apply_insight_feedback_to_score(initial_score, insight_id)
    assert score_with_feedback == initial_score - 0.1


@pytest.mark.asyncio
async def test_ief_score_unchanged_with_not_now_feedback(conn):
    """AC-5: not_now feedback has no effect on IEF score."""
    from mcp_server.analysis.ief import apply_insight_feedback_to_score

    cursor = conn.cursor()

    # Create test insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight for not_now feedback", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]
    conn.commit()

    # Get initial score
    initial_score = 0.6

    # Add not_now feedback
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
        VALUES (%s, %s, NOW());
    """, (insight_id, "not_now"))
    conn.commit()

    # Score should remain unchanged
    score_with_feedback = apply_insight_feedback_to_score(initial_score, insight_id)
    assert score_with_feedback == initial_score


@pytest.mark.asyncio
async def test_multiple_feedback_aggregates_correctly(conn):
    """Multiple feedback entries should aggregate."""
    from mcp_server.analysis.ief import apply_insight_feedback_to_score

    cursor = conn.cursor()

    # Create test insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight for multiple feedback", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]
    conn.commit()

    # Get initial score
    initial_score = 0.5

    # Add multiple feedback: 2 helpful, 1 not_relevant, 1 not_now
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
        VALUES (%s, %s, NOW());
    """, (insight_id, "helpful"))
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
        VALUES (%s, %s, NOW());
    """, (insight_id, "helpful"))
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
        VALUES (%s, %s, NOW());
    """, (insight_id, "not_relevant"))
    cursor.execute("""
        INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
        VALUES (%s, %s, NOW());
    """, (insight_id, "not_now"))
    conn.commit()

    # Expected adjustment: +0.1 + 0.1 - 0.1 + 0 = +0.1
    score_with_feedback = apply_insight_feedback_to_score(initial_score, insight_id)
    assert score_with_feedback == initial_score + 0.1


@pytest.mark.asyncio
async def test_ief_score_clamped_to_valid_range(conn):
    """IEF score should be clamped to [0.0, 1.5] range."""
    from mcp_server.analysis.ief import apply_insight_feedback_to_score

    cursor = conn.cursor()

    # Create test insight
    cursor.execute("""
        INSERT INTO l2_insights (content, source_ids, metadata, embedding, memory_strength)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, ("Test insight for clamping", [1], json.dumps({}), [0.1] * 1536, 0.5))

    insight_id = cursor.fetchone()[0]
    conn.commit()

    # Test upper bound: add lots of positive feedback
    for _ in range(20):
        cursor.execute("""
            INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
            VALUES (%s, %s, NOW());
        """, (insight_id, "helpful"))
    conn.commit()

    # Even with +2.0 adjustment, score should be capped at 1.5
    score_clamped_high = apply_insight_feedback_to_score(1.0, insight_id)
    assert score_clamped_high <= 1.5

    # Test lower bound: add lots of negative feedback
    cursor.execute("DELETE FROM insight_feedback WHERE insight_id = %s", (insight_id,))
    for _ in range(20):
        cursor.execute("""
            INSERT INTO insight_feedback (insight_id, feedback_type, created_at)
            VALUES (%s, %s, NOW());
        """, (insight_id, "not_relevant"))
    conn.commit()

    # Even with -2.0 adjustment, score should be capped at 0.0
    score_clamped_low = apply_insight_feedback_to_score(0.5, insight_id)
    assert score_clamped_low >= 0.0


@pytest.mark.asyncio
async def test_no_feedback_returns_base_score():
    """Insight with no feedback should return base score unchanged."""
    from mcp_server.analysis.ief import apply_insight_feedback_to_score

    # Use a non-existent insight ID (no feedback possible)
    insight_id = 999999
    base_score = 0.6

    score = apply_insight_feedback_to_score(base_score, insight_id)
    assert score == base_score
