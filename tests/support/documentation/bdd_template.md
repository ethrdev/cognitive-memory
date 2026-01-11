# BDD (Given-When-Then) Template for Tests

**Date**: 2026-01-11
**Purpose**: Standardize BDD structure across all cognitive-memory tests

---

## Why Given-When-Then?

**BDD (Behavior-Driven Development)** structure makes tests:
- **Scannable** - Test intent obvious at a glance
- **Self-documenting** - Tests serve as living documentation
- **Maintainable** - Easy to identify what needs updating when requirements change

---

## Standard Template

### Docstring Format

```python
@pytest.mark.asyncio
@pytest.mark.P0
async def test_26_4_UNIT_001_helpful_feedback():
    """
    Test ID: 26.4-UNIT-001
    AC: AC-3 (Positive Feedback)
    Priority: P0

    Given a valid insight ID (42) with is_deleted=FALSE
    And feedback_type="helpful"
    When submit_insight_feedback is called
    Then the feedback is stored successfully
    And the response includes feedback_id
    And the note indicates "IEF will update on next query"
    """
```

### Body Comment Format

```python
@pytest.mark.asyncio
@pytest.mark.P0
async def test_26_4_UNIT_001_helpful_feedback():
    """Test ID: 26.4-UNIT-001..."""

    # Given: Valid insight exists and is not soft-deleted
    mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
    mock_cursor.fetchone.return_value = {"id": 99}  # feedback_id

    # When: Submit helpful feedback
    result = await handle_submit_insight_feedback({
        "insight_id": 42,
        "feedback_type": "helpful"
    })

    # Then: Verify success response
    assert result["success"] is True
    assert result["feedback_id"] == 99

    # And: Verify IEF note
    assert "IEF will update" in result.get("note", "")
```

---

## Complete Example

```python
"""
Unit Tests for Story 26.4: Context Critic (Insight Feedback)

Tests the submit_insight_feedback tool for collecting user feedback
on L2 insights and applying IEF score adjustments.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestStory26_4_InsightFeedbackUnit:
    """
    Story 26.4: Context Critic (Insight Feedback) - Unit Tests

    Unit tests use mocks - no database connection required.
    """

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_26_4_UNIT_001_helpful_feedback_stored_successfully(self):
        """
        Test ID: 26.4-UNIT-001
        AC: AC-3 (Positive Feedback - IEF +0.1 boost)
        Priority: P0 - Core feedback submission must work

        Given a valid insight ID (42) with is_deleted=FALSE
        And feedback_type="helpful"
        When submit_insight_feedback is called via MCP
        Then the feedback is stored successfully in insight_feedback table
        And the response includes feedback_id (generated)
        And the note indicates "IEF will update on next query"
        And no IEF recalculation happens immediately (EP-4 Lazy Evaluation)
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Insight exists and is not soft-deleted
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value = mock_conn

            # First call: SELECT for insight existence
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            # Second call: INSERT returns new feedback_id
            mock_cursor.fetchone.return_value = {"id": 99}

            # When: Submit helpful feedback
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "helpful"
            })

            # Then: Verify success response structure
            assert result["success"] is True
            assert result["feedback_id"] == 99
            assert "IEF will update" in result.get("note", "")

            # And: Verify INSERT was called (feedback stored)
            assert mock_cursor.execute.call_count >= 2  # SELECT + INSERT
            insert_call = [c for c in mock_cursor.execute.call_args_list
                          if "INSERT INTO insight_feedback" in str(c)][0]
            assert insert_call is not None

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_26_4_UNIT_004_soft_deleted_insight_returns_404(self):
        """
        Test ID: 26.4-UNIT-004
        AC: AC-8 (Insight Existence Check)
        Priority: P1 - Data integrity validation

        Given an insight that was soft-deleted (is_deleted=TRUE)
        And deleted_at is set to a past timestamp
        When submit_insight_feedback is called with that insight_id
        Then the request returns 404 error
        And error message contains "not found"
        And no feedback is stored
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Soft-deleted insight
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {
                "id": 42,
                "is_deleted": True,
                "deleted_at": "2026-01-10T10:00:00Z"
            }
            mock_get_conn.return_value = mock_conn

            # When: Try to submit feedback for soft-deleted insight
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "helpful"
            })

            # Then: Verify 404 response
            assert result["error"]["code"] == 404
            assert "not found" in result["error"]["message"].lower()

            # And: Verify no INSERT was attempted
            insert_calls = [c for c in mock_cursor.execute.call_args_list
                           if "INSERT" in str(c)]
            assert len(insert_calls) == 0

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_26_4_UNIT_003_invalid_feedback_type_returns_400(self):
        """
        Test ID: 26.4-UNIT-003
        AC: AC-7 (Feedback Type Validation)
        Priority: P0 - Input validation must reject invalid values

        Given a valid insight ID (42) with is_deleted=FALSE
        When submit_insight_feedback is called with feedback_type="invalid"
        Then returns 400 error
        And error.field = "feedback_type"
        And error message indicates valid options
        And no feedback is stored
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Valid insight
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            mock_get_conn.return_value = mock_conn

            # When: Submit with invalid feedback type
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "invalid_type"
            })

            # Then: Verify validation error
            assert result["error"]["code"] == 400
            assert result["error"]["field"] == "feedback_type"

    @pytest.mark.asyncio
    @pytest.mark.P2
    async def test_26_4_UNIT_006_context_parameter_accepts_string(self):
        """
        Test ID: 26.4-UNIT-006
        AC: AC-10 (Context Parameter Validation)
        Priority: P2 - Edge case validation (optional context)

        Given a valid insight ID (42)
        And feedback_type="helpful"
        And context="This insight was very useful for my query"
        When submit_insight_feedback is called
        Then the feedback is stored with context included
        And the context is persisted correctly in the database
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Valid insight with context
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            mock_cursor.fetchone.return_value = {"id": 99}
            mock_get_conn.return_value = mock_conn

            # When: Submit feedback with context
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "helpful",
                "context": "This insight was very useful"
            })

            # Then: Verify success
            assert result["success"] is True

            # And: Verify context was passed to INSERT
            insert_call = [c for c in mock_cursor.execute.call_args_list
                          if "INSERT INTO insight_feedback" in str(c)][0]
            assert "This insight was very useful" in str(insert_call)


class TestStory26_4_IEFIntegration:
    """
    Story 26.4: Context Critic - IEF Score Integration

    Integration tests for IEF score adjustment based on feedback.
    Requires DATABASE_URL.
    """

    @pytest.mark.asyncio
    @pytest.mark.P0
    @pytest.mark.integration
    async def test_26_4_INT_001_helpful_increases_ief_score(self, conn):
        """
        Test ID: 26.4-INT-001
        AC: AC-3 (Positive Feedback → +0.1 IEF boost)
        Priority: P0 - Core feedback loop

        Given an existing insight with memory_strength=0.5
        And the insight has no prior feedback
        When helpful feedback is submitted
        Then IEF score should increase by +0.1
        And new memory_strength = 0.6
        And feedback_count increases by 1
        """
        pytest.skip("Requires DATABASE_URL - integration test")

    @pytest.mark.asyncio
    @pytest.mark.P0
    @pytest.mark.integration
    async def test_26_4_INT_004_score_clamping_150(self, conn):
        """
        Test ID: 26.4-INT-004
        AC: AC-12 (Score Clamping [0.0, 1.5])
        Priority: P0 - Edge case prevents invalid scores

        Given an insight with memory_strength=1.45
        And 20x helpful feedback submitted (+2.0 total adjustment)
        When apply_insight_feedback_to_score is called
        Then the score is clamped to 1.5 (upper bound)
        And no exception is raised
        """
        pytest.skip("Requires DATABASE_URL - integration test")


# ============================================================================
# GWT Keywords Quick Reference
# ============================================================================

"""
PRIMARY KEYWORDS:
  Given    - Initial context/setup (preconditions)
  When     - Action/trigger (what is being tested)
  Then     - Expected outcome (assertions)
  And      - Additional context or assertions

SECONDARY KEYWORDS (use sparingly):
  But      - Exception case or alternate condition

ORDERING:
  1. All Given clauses first (setup)
  2. All When clauses next (action)
  3. All Then clauses last (verification)
  4. And clauses extend the previous keyword

TIPS:
  - Start each clause with the keyword
  - Be specific about values (42, "helpful", 0.5)
  - Use present tense ("is stored", not "was stored")
  - One assertion per Then/And clause
  - Keep clauses focused (single responsibility)

EXAMPLES:

GOOD - Clear and specific:
  Given insight ID 42 with is_deleted=FALSE
  And feedback_type="helpful"
  When submit_insight_feedback is called
  Then feedback is stored successfully
  And response includes feedback_id

BAD - Vague and combined:
  Given an insight and feedback
  When the function is called
  Then it should work and return something

GOOD - Single assertion per line:
  Then response.success is TRUE
  And response.feedback_id is an integer
  And response.note is not empty

BAD - Multiple assertions in one line:
  Then response is correct with all fields
"""
