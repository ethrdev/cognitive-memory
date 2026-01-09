"""
Unit Tests for submit_insight_feedback MCP Tool

Tests for Story 26.4: Context Critic.
Covers all acceptance criteria (AC-3, AC-4, AC-5, AC-7, AC-8).

Author: Epic 26 Implementation
Story: 26.4 - Context Critic
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mcp_server.tools.insights.feedback import handle_submit_insight_feedback


# =============================================================================
# AC-3: Positive Feedback Tests
# =============================================================================

@pytest.mark.asyncio
async def test_helpful_feedback():
    """AC-3: Positive feedback stored correctly."""
    with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        # Insight exists and not deleted
        mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
        mock_cursor.fetchone.return_value = {"id": 99}  # feedback_id

        result = await handle_submit_insight_feedback({
            "insight_id": 42,
            "feedback_type": "helpful"
        })

        assert result["success"] is True
        assert "feedback_id" in result
        assert result["note"] == "IEF will update on next query"

        # Verify INSERT was called
        mock_cursor.execute.assert_called()
        insert_call = mock_cursor.execute.call_args_list[1]  # Second call (first is SELECT)
        assert "INSERT INTO insight_feedback" in insert_call[0][0]


@pytest.mark.asyncio
async def test_helpful_feedback_with_context():
    """AC-3: Optional context parameter is stored."""
    with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
        mock_cursor.fetchone.return_value = {"id": 99}

        result = await handle_submit_insight_feedback({
            "insight_id": 42,
            "feedback_type": "helpful",
            "context": "Sehr hilfreich für meine Frage"
        })

        assert result["success"] is True


# =============================================================================
# AC-4: Negative Feedback Tests
# =============================================================================

@pytest.mark.asyncio
async def test_not_relevant_feedback():
    """AC-4: Negative feedback stored with optional context."""
    with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
        mock_cursor.fetchone.return_value = {"id": 99}

        result = await handle_submit_insight_feedback({
            "insight_id": 42,
            "feedback_type": "not_relevant",
            "context": "War zu allgemein"
        })

        assert result["success"] is True
        assert "feedback_id" in result


@pytest.mark.asyncio
async def test_not_relevant_without_context():
    """AC-4: Context is optional for not_relevant feedback."""
    with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
        mock_cursor.fetchone.return_value = {"id": 99}

        result = await handle_submit_insight_feedback({
            "insight_id": 42,
            "feedback_type": "not_relevant"
            # No context
        })

        assert result["success"] is True


# =============================================================================
# AC-5: Not Now Tests
# =============================================================================

@pytest.mark.asyncio
async def test_not_now_feedback():
    """AC-5: Not now feedback logged but no score effect."""
    with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
        mock_cursor.fetchone.return_value = {"id": 99}

        result = await handle_submit_insight_feedback({
            "insight_id": 42,
            "feedback_type": "not_now"
        })

        assert result["success"] is True
        assert result.get("note") == "IEF will update on next query"


# =============================================================================
# AC-7: Feedback Type Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_invalid_feedback_type():
    """Invalid feedback_type returns 400."""
    result = await handle_submit_insight_feedback({
        "insight_id": 42,
        "feedback_type": "invalid_type"
    })

    assert result["error"]["code"] == 400
    assert "feedback_type" in result["error"]["message"]
    assert result["error"]["field"] == "feedback_type"


@pytest.mark.asyncio
async def test_missing_feedback_type():
    """Missing feedback_type returns 400."""
    result = await handle_submit_insight_feedback({
        "insight_id": 42,
        # feedback_type missing
    })

    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "feedback_type is required"
    assert result["error"]["field"] == "feedback_type"


@pytest.mark.asyncio
async def test_feedback_type_enum_validation():
    """Only valid enum values accepted."""
    valid_types = ["helpful", "not_relevant", "not_now"]

    for feedback_type in valid_types:
        with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
            # Setup mock
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=False)
            mock_get_conn.return_value = mock_conn

            mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
            mock_cursor.fetchone.return_value = {"id": 99}

            result = await handle_submit_insight_feedback({
                "insight_id": 42,
                "feedback_type": feedback_type
            })

            # Should not return validation error
            assert result.get("error", {}).get("code") != 400


# =============================================================================
# AC-8: Insight Existence Tests
# =============================================================================

@pytest.mark.asyncio
async def test_insight_not_found():
    """AC-8: Returns 404 for unknown insight."""
    with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        # Insight not found
        mock_cursor.fetchone.return_value = None

        result = await handle_submit_insight_feedback({
            "insight_id": 99999,
            "feedback_type": "helpful"
        })

        assert result["error"]["code"] == 404
        assert "not found" in result["error"]["message"].lower()


@pytest.mark.asyncio
async def test_soft_deleted_insight():
    """AC-8: Soft-deleted insights return 404 (like update/delete)."""
    with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        # Insight is soft-deleted
        mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": True}

        result = await handle_submit_insight_feedback({
            "insight_id": 42,
            "feedback_type": "helpful"
        })

        assert result["error"]["code"] == 404
        assert "not found" in result["error"]["message"].lower()


# =============================================================================
# Parameter Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_missing_insight_id():
    """Missing insight_id returns 400."""
    result = await handle_submit_insight_feedback({
        "feedback_type": "helpful"
        # insight_id missing
    })

    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "insight_id is required"
    assert result["error"]["field"] == "insight_id"


@pytest.mark.asyncio
async def test_invalid_insight_id_type():
    """Non-integer insight_id returns 400."""
    result = await handle_submit_insight_feedback({
        "insight_id": "not_an_int",
        "feedback_type": "helpful"
    })

    assert result["error"]["code"] == 400
    assert "positive integer" in result["error"]["message"]


@pytest.mark.asyncio
async def test_invalid_insight_id_negative():
    """Negative insight_id returns 400."""
    result = await handle_submit_insight_feedback({
        "insight_id": -1,
        "feedback_type": "helpful"
    })

    assert result["error"]["code"] == 400
    assert "positive integer" in result["error"]["message"]


@pytest.mark.asyncio
async def test_invalid_context_type():
    """Non-string context returns 400."""
    result = await handle_submit_insight_feedback({
        "insight_id": 42,
        "feedback_type": "helpful",
        "context": 123  # Not a string
    })

    assert result["error"]["code"] == 400
    assert "context must be a string" in result["error"]["message"]


# =============================================================================
# EP-4: Lazy Evaluation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_no_ief_recalculate_on_submit():
    """EP-4: Feedback submission does NOT trigger IEF recalculate."""
    with patch('mcp_server.db.connection.get_connection') as mock_get_conn:
        # Setup mock
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value = mock_conn

        mock_cursor.fetchone.return_value = {"id": 42, "is_deleted": False}
        mock_cursor.fetchone.return_value = {"id": 99}

        result = await handle_submit_insight_feedback({
            "insight_id": 42,
            "feedback_type": "helpful"
        })

        # Verify only INSERT was called, no UPDATE to l2_insights
        assert result["success"] is True
        assert result["note"] == "IEF will update on next query"

        # Check that INSERT was called
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if "INSERT" in str(call)]
        assert len(insert_calls) > 0
        # Verify it's the correct table
        assert "insight_feedback" in str(insert_calls[0])

        # Check that no UPDATE to l2_insights was called
        update_calls = [call for call in mock_cursor.execute.call_args_list
                       if "UPDATE l2_insights" in str(call)]
        assert len(update_calls) == 0
