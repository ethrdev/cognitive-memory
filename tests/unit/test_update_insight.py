"""
Unit Tests for update_insight MCP Tool

Tests for Story 26.2: UPDATE Operation.
Covers all acceptance criteria (AC-1 through AC-7).

Author: Epic 26 Implementation
Story: 26.2 - UPDATE Operation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from mcp_server.tools.insights.update import handle_update_insight
from mcp_server.analysis.smf import SMFAction


# =============================================================================
# AC-3: Reason Required Tests
# =============================================================================

@pytest.mark.asyncio
async def test_reason_required():
    """AC-3: reason is mandatory - returns 400 error when missing."""
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "new_content": "Updated content",
        # reason missing!
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "reason required"
    assert result["error"]["field"] == "reason"


@pytest.mark.asyncio
async def test_reason_empty_string():
    """AC-3: reason cannot be empty string."""
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "",  # Empty string
        "new_content": "Updated content",
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "reason required"


# =============================================================================
# AC-4: Changes Required Tests
# =============================================================================

@pytest.mark.asyncio
async def test_changes_required():
    """AC-4: at least one change required - returns 400 when neither new_content nor new_memory_strength provided."""
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test update",
        # Neither new_content nor new_memory_strength!
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "no changes provided"


@pytest.mark.asyncio
async def test_new_content_not_empty():
    """AC-4: new_content cannot be empty string."""
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test update",
        "new_content": "",  # Empty string!
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "new_content cannot be empty"
    assert result["error"]["field"] == "new_content"


@pytest.mark.asyncio
async def test_new_content_whitespace_only():
    """AC-4: new_content with only whitespace is treated as empty."""
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test update",
        "new_content": "   \n\t  ",  # Only whitespace!
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "new_content cannot be empty"


@pytest.mark.asyncio
async def test_memory_strength_out_of_range_low():
    """AC-4: new_memory_strength must be >= 0.0."""
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test update",
        "new_memory_strength": -0.1,  # Below 0.0
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert "between 0.0 and 1.0" in result["error"]["message"]


@pytest.mark.asyncio
async def test_memory_strength_out_of_range_high():
    """AC-4: new_memory_strength must be <= 1.0."""
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test update",
        "new_memory_strength": 1.1,  # Above 1.0
    })

    assert "error" in result
    assert result["error"]["code"] == 400
    assert "between 0.0 and 1.0" in result["error"]["message"]


# =============================================================================
# AC-1: Direct Update (I/O as Actor) Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
async def test_io_direct_update(mock_execute):
    """AC-1: I/O can update directly without SMF proposal."""
    # Mock successful update
    mock_execute.return_value = {
        "success": True,
        "insight_id": 42,
        "history_id": 123,
        "updated_fields": {"content": True, "memory_strength": False}
    }

    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Präzisierung",
        "new_content": "Updated content"
    })

    # Verify direct execution (no SMF)
    assert "error" not in result
    assert result["success"] is True
    assert result["insight_id"] == 42
    assert result["history_id"] == 123
    assert result["updated_fields"]["content"] is True

    # Verify execute_update_with_history was called with correct params
    mock_execute.assert_called_once_with(
        insight_id=42,
        new_content="Updated content",
        new_memory_strength=None,
        actor="I/O",
        reason="Präzisierung"
    )


# =============================================================================
# AC-2: Consent Flow (ethr as Actor) Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.create_smf_proposal')
async def test_ethr_creates_smf_proposal(mock_create_smf):
    """AC-2: ethr creates SMF proposal for consent."""
    # Mock SMF proposal creation
    mock_create_smf.return_value = 456  # proposal_id

    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "ethr",
        "reason": "Vorgeschlagene Änderung",
        "new_content": "Proposed content"
    })

    # Verify SMF proposal flow (no direct update)
    assert "error" not in result
    assert result["status"] == "pending"
    assert result["proposal_id"] == 456
    assert "waiting" in result["message"].lower()

    # Verify create_smf_proposal was called correctly
    mock_create_smf.assert_called_once()
    call_args = mock_create_smf.call_args
    assert call_args[1]["proposed_action"]["action"] == SMFAction.UPDATE_INSIGHT
    assert call_args[1]["proposed_action"]["insight_id"] == 42
    assert call_args[1]["reasoning"] == "Vorgeschlagene Änderung"


# =============================================================================
# AC-6: Not Found Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
async def test_not_found_insight(mock_execute):
    """AC-6: returns 404 for unknown insight ID."""
    # Mock ValueError for "not found"
    mock_execute.side_effect = ValueError("Insight 42 not found")

    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test",
        "new_content": "Content"
    })

    assert "error" in result
    assert result["error"]["code"] == 404
    assert "not found" in result["error"]["message"].lower()


@pytest.mark.asyncio
async def test_insight_id_validation():
    """AC-6: validates insight_id parameter."""
    # Test with None
    result = await handle_update_insight({
        "actor": "I/O",
        "reason": "Test",
        "new_content": "Content"
    })
    assert result["error"]["code"] == 400
    assert result["error"]["field"] == "insight_id"

    # Test with invalid ID (negative)
    result = await handle_update_insight({
        "insight_id": -1,
        "actor": "I/O",
        "reason": "Test",
        "new_content": "Content"
    })
    assert result["error"]["code"] == 400

    # Test with invalid ID (zero)
    result = await handle_update_insight({
        "insight_id": 0,
        "actor": "I/O",
        "reason": "Test",
        "new_content": "Content"
    })
    assert result["error"]["code"] == 400


# =============================================================================
# Actor Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_actor_validation():
    """Test that actor parameter is validated."""
    # Missing actor
    result = await handle_update_insight({
        "insight_id": 42,
        "reason": "Test",
        "new_content": "Content"
    })
    assert result["error"]["code"] == 400
    assert result["error"]["field"] == "actor"

    # Invalid actor
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "invalid",
        "reason": "Test",
        "new_content": "Content"
    })
    assert result["error"]["code"] == 400
    assert "actor must be" in result["error"]["message"]


# =============================================================================
# AC-7: Soft-Deleted Insight Tests (Optional)
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
async def test_soft_deleted_insight_returns_404(mock_execute):
    """AC-7: soft-deleted insights return 404 (same as not found)."""
    # Mock ValueError for "not found" (includes soft-deleted)
    mock_execute.side_effect = ValueError("Insight 42 not found")

    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test",
        "new_content": "Content"
    })

    assert "error" in result
    assert result["error"]["code"] == 404
    assert "not found" in result["error"]["message"].lower()


# =============================================================================
# Memory Strength Update Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
async def test_update_memory_strength_only(mock_execute):
    """Test updating only memory_strength (no content change)."""
    mock_execute.return_value = {
        "success": True,
        "insight_id": 42,
        "history_id": 123,
        "updated_fields": {"content": False, "memory_strength": True}
    }

    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Increase importance",
        "new_memory_strength": 0.9
    })

    assert result["success"] is True
    assert result["updated_fields"]["memory_strength"] is True
    assert result["updated_fields"]["content"] is False


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
async def test_update_both_content_and_strength(mock_execute):
    """Test updating both content and memory_strength."""
    mock_execute.return_value = {
        "success": True,
        "insight_id": 42,
        "history_id": 123,
        "updated_fields": {"content": True, "memory_strength": True}
    }

    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Full update",
        "new_content": "Completely revised content",
        "new_memory_strength": 0.8
    })

    assert result["success"] is True
    assert result["updated_fields"]["content"] is True
    assert result["updated_fields"]["memory_strength"] is True


# =============================================================================
# EP-5: Error Propagation Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
async def test_database_error_returns_500(mock_execute):
    """EP-5: Database errors return structured 500 response."""
    mock_execute.side_effect = Exception("Database connection failed")

    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "Test",
        "new_content": "Content"
    })

    assert "error" in result
    assert result["error"]["code"] == 500
    assert "Internal error" in result["error"]["message"]


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.create_smf_proposal')
async def test_smf_creation_error_returns_500(mock_create_smf):
    """EP-5: SMF creation errors return structured 500 response."""
    mock_create_smf.side_effect = Exception("SMF system down")

    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "ethr",
        "reason": "Test",
        "new_content": "Content"
    })

    assert "error" in result
    assert result["error"]["code"] == 500
    assert "consent proposal" in result["error"]["message"].lower()
