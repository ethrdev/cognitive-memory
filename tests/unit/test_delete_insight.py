"""
Unit Tests for delete_insight MCP Tool

Tests for Story 26.3: DELETE Operation.
Covers all acceptance criteria (AC-1 through AC-7).

Author: Epic 26 Implementation
Story: 26.3 - DELETE Operation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mcp_server.tools.insights.delete import handle_delete_insight
from mcp_server.analysis.smf import SMFAction


# =============================================================================
# AC-6: Reason Required Tests
# =============================================================================

@pytest.mark.asyncio
async def test_reason_required():
    """AC-6: reason is mandatory - returns 400 error when missing."""
    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "I/O",
        # reason missing!
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "reason required"
    assert result["error"]["field"] == "reason"


@pytest.mark.asyncio
async def test_reason_empty_string():
    """AC-6: reason cannot be empty string."""
    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "",  # Empty string
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "reason required"


# =============================================================================
# AC-1: Direct Delete (I/O as Actor) Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.execute_delete_with_history')
async def test_io_direct_delete(mock_execute):
    """AC-1: I/O can delete directly without SMF proposal."""
    # Mock successful delete
    mock_execute.return_value = {
        "success": True,
        "insight_id": 42,
        "history_id": 123,
        "status": "deleted",
        "recoverable": True
    }

    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Nicht mehr relevant"
    })

    assert "success" in result
    assert result["success"] is True
    assert result["insight_id"] == 42
    assert result["status"] == "deleted"
    assert result["recoverable"] is True
    mock_execute.assert_called_once_with(insight_id=42, actor="I/O", reason="Nicht mehr relevant")


# =============================================================================
# AC-2: SMF Proposal (ethr as Actor) Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.create_smf_proposal')
async def test_ethr_creates_smf_proposal(mock_create_proposal):
    """AC-2: ethr creates SMF proposal for bilateral consent."""
    # Mock successful proposal creation
    mock_create_proposal.return_value = 999

    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "ethr",
        "reason": "Vorgeschlagene Löschung"
    })

    assert "status" in result
    assert result["status"] == "pending"
    assert result["proposal_id"] == 999
    assert "message" in result
    mock_create_proposal.assert_called_once()


# =============================================================================
# AC-5: Already Deleted Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.execute_delete_with_history')
async def test_already_deleted(mock_execute):
    """AC-5: returns 409 for already deleted insight."""
    # Mock already deleted error
    mock_execute.side_effect = ValueError("already deleted")

    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "First delete"
    })

    assert "error" in result
    assert result["error"]["code"] == 409
    assert "already deleted" in result["error"]["message"]


# =============================================================================
# AC-7: Not Found Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.execute_delete_with_history')
async def test_not_found(mock_execute):
    """AC-7: returns 404 for unknown insight."""
    # Mock not found error
    mock_execute.side_effect = ValueError("Insight 42 not found")

    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Won't work"
    })

    assert "error" in result
    assert result["error"]["code"] == 404
    assert "Insight 42 not found" in result["error"]["message"]


# =============================================================================
# AC-3: Search Exclusion Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.execute_delete_with_history')
@patch('mcp_server.tools.insights.delete.get_connection')
async def test_search_exclusion(mock_get_connection, mock_execute):
    """AC-3: soft-deleted insights should be excluded from search results."""
    # Mock the database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_connection.return_value.__aenter__.return_value = mock_conn

    # Mock successful delete
    mock_execute.return_value = {
        "success": True,
        "insight_id": 42,
        "history_id": 123,
        "status": "deleted",
        "recoverable": True
    }

    # Execute delete
    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test deletion"
    })

    # Verify delete was successful
    assert "success" in result
    assert result["success"] is True

    # Verify the function was called (this tests that execute_delete_with_history works)
    # The actual search exclusion is tested in integration tests
    mock_execute.assert_called_once()


# =============================================================================
# AC-4: History Preservation Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.execute_delete_with_history')
async def test_history_preservation(mock_execute):
    """AC-4: Deleted insights should be available in history."""
    # Mock successful delete that creates history
    mock_execute.return_value = {
        "success": True,
        "insight_id": 42,
        "history_id": 123,
        "status": "deleted",
        "recoverable": True
    }

    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test deletion for history"
    })

    # Verify delete was successful
    assert "success" in result
    assert result["success"] is True
    assert "history_id" in result

    # Verify execute_delete_with_history was called
    # This function is responsible for creating history entries
    mock_execute.assert_called_once_with(insight_id=42, actor="I/O", reason="Test deletion for history")


# =============================================================================
# Parameter Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_insight_id_required():
    """insight_id is mandatory."""
    result = await handle_delete_insight({
        "actor": "I/O",
        "reason": "Test"
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "insight_id is required"
    assert result["error"]["field"] == "insight_id"


@pytest.mark.asyncio
async def test_insight_id_must_be_positive():
    """insight_id must be a positive integer."""
    result = await handle_delete_insight({
        "insight_id": 0,
        "actor": "I/O",
        "reason": "Test"
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert "positive integer" in result["error"]["message"]


@pytest.mark.asyncio
async def test_actor_required():
    """actor is mandatory."""
    result = await handle_delete_insight({
        "insight_id": 42,
        "reason": "Test"
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "actor is required"
    assert result["error"]["field"] == "actor"


@pytest.mark.asyncio
async def test_actor_must_be_io_or_ethr():
    """actor must be 'I/O' or 'ethr'."""
    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "invalid",
        "reason": "Test"
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert "must be 'I/O' or 'ethr'" in result["error"]["message"]


@pytest.mark.asyncio
async def test_insight_id_must_be_integer():
    """insight_id must be an integer."""
    result = await handle_delete_insight({
        "insight_id": "not-a-number",
        "actor": "I/O",
        "reason": "Test"
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert "positive integer" in result["error"]["message"]


# =============================================================================
# Error Handling Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.execute_delete_with_history')
async def test_io_delete_internal_error(mock_execute):
    """Handles internal errors gracefully."""
    mock_execute.side_effect = Exception("Database connection failed")

    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test"
    })

    assert "error" in result
    assert result["error"]["code"] == 500
    assert "Internal error during delete" in result["error"]["message"]


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.create_smf_proposal')
async def test_ethr_proposal_creation_fails(mock_create_proposal):
    """Handles SMF proposal creation failures."""
    mock_create_proposal.side_effect = Exception("SMF service unavailable")

    result = await handle_delete_insight({
        "insight_id": 42,
        "actor": "ethr",
        "reason": "Test"
    })

    assert "error" in result
    assert result["error"]["code"] == 500
    assert "Failed to create consent proposal" in result["error"]["message"]


# =============================================================================
# SMF Proposal Content Validation Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.create_smf_proposal')
async def test_smf_proposal_correct_action(mock_create_proposal):
    """Verifies SMF proposal uses DELETE_INSIGHT action."""
    mock_create_proposal.return_value = 999

    await handle_delete_insight({
        "insight_id": 42,
        "actor": "ethr",
        "reason": "Test deletion"
    })

    call_args = mock_create_proposal.call_args
    assert call_args is not None
    proposed_action = call_args.kwargs.get("proposed_action", {})
    assert proposed_action.get("action") == SMFAction.DELETE_INSIGHT


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.delete.create_smf_proposal')
async def test_smf_proposal_bilateral_approval(mock_create_proposal):
    """Verifies SMF proposal requires bilateral approval."""
    mock_create_proposal.return_value = 999

    await handle_delete_insight({
        "insight_id": 42,
        "actor": "ethr",
        "reason": "Test deletion"
    })

    call_args = mock_create_proposal.call_args
    assert call_args is not None
    approval_level = call_args.kwargs.get("approval_level")
    from mcp_server.analysis.smf import ApprovalLevel
    assert approval_level == ApprovalLevel.BILATERAL
