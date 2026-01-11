"""
Example Test File with Test IDs and Priority Markers

This file demonstrates the new testing standards for cognitive-memory:
- Test IDs: {Story}.{TestLevel}-{Number} format
- Priority Markers: @pytest.mark.priority("P0/P1/P2/P3")
- BDD Format: Given-When-Then structure in docstrings

Run examples:
    pytest -m P0                    # Run only P0 (critical) tests
    pytest -m "P0 or P1"            # Run P0 and P1 tests
    pytest -k "26.4-UNIT"           # Run all Story 26.4 unit tests
    pytest --collect-only --quiet  # List all tests with markers
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestStory26_4_Unit_InsightFeedback:
    """
    Story 26.4: Context Critic (Insight Feedback)

    Unit tests for the submit_insight_feedback tool.
    Tests use mocks - no database required.
    """

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_26_4_UNIT_001_helpful_feedback_stored_successfully(self):
        """
        Test ID: 26.4-UNIT-001
        AC: AC-3 (Positive Feedback)
        Priority: P0 - Core feedback submission must work

        Given a valid insight ID (42) and feedback_type="helpful"
        When submit_insight_feedback is called
        Then the feedback is stored successfully
        And the response includes feedback_id
        And the note indicates IEF will update on next query
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Insight exists and is not soft-deleted
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            mock_cursor.fetchone.return_value = {"id": 99}  # feedback_id
            mock_get_conn.return_value = mock_conn

            # When: Submit helpful feedback
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "helpful"
            })

            # Then: Verify success
            assert result["success"] is True
            assert result["feedback_id"] == 99
            assert "IEF will update" in result.get("note", "")

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_26_4_UNIT_002_not_relevant_feedback_applied(self):
        """
        Test ID: 26.4-UNIT-002
        AC: AC-4 (Negative Feedback)
        Priority: P0 - Core feedback submission must work

        Given a valid insight with feedback_type="not_relevant"
        When submit_insight_feedback is called
        Then negative feedback is stored successfully
        And the response includes feedback_id
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Valid insight
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            mock_cursor.fetchone.return_value = {"id": 100}
            mock_get_conn.return_value = mock_conn

            # When: Submit not_relevant feedback
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "not_relevant",
                "context": "Not relevant to current query"
            })

            # Then: Verify success
            assert result["success"] is True
            assert result["feedback_id"] == 100

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_26_4_UNIT_003_invalid_feedback_type_returns_400(self):
        """
        Test ID: 26.4-UNIT-003
        AC: AC-7 (Feedback Type Validation)
        Priority: P0 - Input validation must work

        Given a valid insight ID
        When submit_insight_feedback is called with invalid feedback_type
        Then returns 400 error with field="feedback_type"
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Valid insight exists
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            mock_get_conn.return_value = mock_conn

            # When: Submit invalid feedback type
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "invalid_type"
            })

            # Then: Verify error response
            assert result["error"]["code"] == 400
            assert result["error"]["field"] == "feedback_type"

    @pytest.mark.asyncio
    @pytest.mark.P1
    async def test_26_4_UNIT_004_soft_deleted_insight_returns_404(self):
        """
        Test ID: 26.4-UNIT-004
        AC: AC-8 (Insight Existence Check)
        Priority: P1 - Data integrity validation

        Given a soft-deleted insight (is_deleted=TRUE)
        When submit_insight_feedback is called
        Then returns 404 error "Insight not found"
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Soft-deleted insight
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": True}
            mock_get_conn.return_value = mock_conn

            # When: Try to submit feedback for soft-deleted insight
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "helpful"
            })

            # Then: Verify 404 error
            assert result["error"]["code"] == 404
            assert "not found" in result["error"]["message"].lower()

    @pytest.mark.asyncio
    @pytest.mark.P1
    async def test_26_4_UNIT_005_missing_insight_id_returns_400(self):
        """
        Test ID: 26.4-UNIT-005
        AC: AC-9 (Parameter Validation)
        Priority: P1 - Input validation

        Given feedback submission request
        When insight_id parameter is missing
        Then returns 400 error "insight_id is required"
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        # When: Submit without insight_id
        result = await handle_submit_insight_feedback({
            "feedback_type": "helpful"
            # missing insight_id
        })

        # Then: Verify error
        assert result["error"]["code"] == 400
        assert "insight_id is required" in result["error"]["message"]

    @pytest.mark.asyncio
    @pytest.mark.P2
    async def test_26_4_UNIT_006_context_parameter_validation(self):
        """
        Test ID: 26.4-UNIT-006
        AC: AC-10 (Context Parameter Validation)
        Priority: P2 - Edge case validation

        Given valid insight and feedback_type
        When context parameter is not a string
        Then returns 400 error "context must be a string if provided"
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Valid insight
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            mock_cursor.fetchone.return_value = {"id": 99}
            mock_get_conn.return_value = mock_conn

            # When: Submit with invalid context type
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "helpful",
                "context": {"not": "a string"}  # Invalid: dict instead of str
            })

            # Then: Verify error
            assert result["error"]["code"] == 400
            assert "must be a string" in result["error"]["message"]

    @pytest.mark.asyncio
    @pytest.mark.P3
    async def test_26_4_UNIT_007_unicode_in_context(self):
        """
        Test ID: 26.4-UNIT-007
        Priority: P3 - Nice to have (internationalization)

        Given valid insight and feedback_type
        When context contains unicode characters (emoji, non-ASCII)
        Then feedback is stored successfully
        """
        from mcp_server.tools.insights.feedback import handle_submit_insight_feedback

        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Given: Valid insight
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            mock_cursor.fetchone.return_value = {"id": 99}
            mock_get_conn.return_value = mock_conn

            # When: Submit with unicode context
            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": "helpful",
                "context": "Great insight! 🎉 Très utile. 日本語"
            })

            # Then: Verify success
            assert result["success"] is True


class TestStory26_4_Integration_IEFScoreAdjustment:
    """
    Story 26.4: Context Critic (Insight Feedback)

    Integration tests for IEF score adjustment based on feedback.
    Tests use real database connection (requires DATABASE_URL).
    """

    @pytest.mark.asyncio
    @pytest.mark.P0
    @pytest.mark.integration
    async def test_26_4_INT_001_helpful_feedback_increases_ief_score(self):
        """
        Test ID: 26.4-INT-001
        AC: AC-3 (Positive Feedback → +0.1 IEF boost)
        Priority: P0 - Core feedback loop must work

        Given an insight with memory_strength=0.5
        When helpful feedback is submitted
        Then IEF score increases by +0.1
        And new score is 0.6
        """
        # This requires database connection
        pytest.skip("Requires DATABASE_URL for integration test")

    @pytest.mark.asyncio
    @pytest.mark.P1
    @pytest.mark.integration
    async def test_26_4_INT_002_not_relevant_feedback_decreases_ief_score(self):
        """
        Test ID: 26.4-INT-002
        AC: AC-4 (Negative Feedback → -0.1 IEF reduction)
        Priority: P1 - Feature validation

        Given an insight with memory_strength=0.5
        When not_relevant feedback is submitted
        Then IEF score decreases by -0.1
        And new score is 0.4
        """
        pytest.skip("Requires DATABASE_URL for integration test")


# ============================================================================
# Migration Guide: Applying Test IDs and Priority Markers
# ============================================================================

"""
# Step 1: Rename test function to include Test ID
# Before:
async def test_helpful_feedback():
    ...

# After:
async def test_26_4_UNIT_001_helpful_feedback():
    ...

# Step 2: Add priority marker decorator
# Before:
@pytest.mark.asyncio
async def test_26_4_UNIT_001_helpful_feedback():
    ...

# After:
@pytest.mark.asyncio
@pytest.mark.P0
async def test_26_4_UNIT_001_helpful_feedback():
    ...

# Step 3: Add BDD docstring with Test ID, AC, and Given-When-Then
async def test_26_4_UNIT_001_helpful_feedback():
    '''
    Test ID: 26.4-UNIT-001
    AC: AC-3 (Positive Feedback)
    Priority: P0

    Given a valid insight ID (42) and feedback_type="helpful"
    When submit_insight_feedback is called
    Then the feedback is stored successfully
    '''
    ...

# Step 4: (Optional) Add body comments matching BDD structure
async def test_26_4_UNIT_001_helpful_feedback():
    '''Test ID: 26.4-UNIT-001...'''
    # Given: Valid insight
    mock_insight = create_insight(id=42)

    # When: Submit helpful feedback
    result = submit_feedback(insight_id=42, feedback_type="helpful")

    # Then: Verify success
    assert result.success is True
"""
