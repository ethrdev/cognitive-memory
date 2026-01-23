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
async def test_reason_required(with_project_context):
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
async def test_reason_empty_string(with_project_context):
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
async def test_changes_required(with_project_context):
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
async def test_new_content_not_empty(with_project_context):
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
async def test_new_content_whitespace_only(with_project_context):
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
async def test_memory_strength_out_of_range_low(with_project_context):
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
async def test_memory_strength_out_of_range_high(with_project_context):
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
async def test_io_direct_update(mock_execute, with_project_context):
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

    # Verify metadata includes project_id
    assert "metadata" in result
    assert result["metadata"]["project_id"] == "test-project"


# =============================================================================
# AC-2: Consent Flow (ethr as Actor) Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.create_smf_proposal')
async def test_ethr_creates_smf_proposal(mock_create_smf, with_project_context):
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

    # Verify metadata includes project_id
    assert "metadata" in result
    assert result["metadata"]["project_id"] == "test-project"


# =============================================================================
# Task 5.9: SMF Consent State Tests (4 states × UPDATE_INSIGHT)
# =============================================================================

# State 1: pending - tested above in test_ethr_creates_smf_proposal
# State 2: direct - tested above in test_io_direct_update

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
@patch('mcp_server.tools.insights.update.create_smf_proposal')
async def test_smf_state_approved_executes_update(mock_create_smf, mock_execute, with_project_context):
    """
    SMF State 3: APPROVED - After I/O approves ethr's proposal, update executes.

    This tests the scenario where:
    1. ethr creates a proposal (pending state)
    2. I/O approves the proposal
    3. The update is executed

    Note: The actual approval execution happens in smf_approve tool,
    which calls execute_update_with_history. This test verifies the
    update function can be called by the approval flow.
    """
    # Mock successful update execution (called by SMF approval)
    mock_execute.return_value = {
        "success": True,
        "insight_id": 42,
        "history_id": 789,
        "updated_fields": {"content": True, "memory_strength": False}
    }

    # Simulate the approval flow calling update with I/O as actor
    # (SMF approval switches actor context to I/O for execution)
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",  # SMF approval executes as I/O
        "reason": "Approved by I/O via SMF proposal #456",
        "new_content": "Content approved by I/O"
    })

    # Verify the update executed successfully
    assert "error" not in result
    assert result["success"] is True
    assert result["insight_id"] == 42
    assert result["history_id"] == 789

    # Verify execute_update_with_history was called (not create_smf_proposal)
    mock_execute.assert_called_once()
    mock_create_smf.assert_not_called()


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.create_smf_proposal')
async def test_smf_state_rejected_no_update(mock_create_smf, with_project_context):
    """
    SMF State 4: REJECTED - After I/O rejects ethr's proposal, no update happens.

    This tests the scenario where:
    1. ethr creates a proposal (pending state)
    2. I/O rejects the proposal
    3. No update is executed - proposal just stays rejected

    Note: Rejection is handled by smf_reject tool which marks the proposal
    as rejected without calling update_insight. This test verifies that
    ethr cannot bypass SMF by calling update directly.
    """
    # Mock SMF proposal creation
    mock_create_smf.return_value = 456  # proposal_id

    # ethr tries to update - should create proposal, not execute
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "ethr",
        "reason": "This will be rejected",
        "new_content": "Content that I/O will reject"
    })

    # Verify only proposal created (no direct execution)
    assert result["status"] == "pending"
    assert result["proposal_id"] == 456

    # The rejection happens via smf_reject tool, not here
    # This test confirms ethr CANNOT bypass SMF consent


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
@patch('mcp_server.tools.insights.update.create_smf_proposal')
async def test_smf_consent_matrix_io_always_direct(mock_create_smf, mock_execute, with_project_context):
    """
    SMF Consent Matrix: I/O ALWAYS executes directly, never creates proposals.

    Verifies EP-1 pattern: I/O as actor = direct execution.
    """
    mock_execute.return_value = {
        "success": True,
        "insight_id": 42,
        "history_id": 123,
        "updated_fields": {"content": True, "memory_strength": True}
    }

    # I/O updates - should NEVER create SMF proposal
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "I/O",
        "reason": "I/O's direct update",
        "new_content": "New content",
        "new_memory_strength": 0.9
    })

    # Verify direct execution
    assert result["success"] is True
    mock_execute.assert_called_once()
    mock_create_smf.assert_not_called()  # CRITICAL: No SMF for I/O


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
@patch('mcp_server.tools.insights.update.create_smf_proposal')
async def test_smf_consent_matrix_ethr_always_proposal(mock_create_smf, mock_execute, with_project_context):
    """
    SMF Consent Matrix: ethr ALWAYS creates proposals, never executes directly.

    Verifies EP-1 pattern: ethr as actor = SMF proposal required.
    """
    mock_create_smf.return_value = 999

    # ethr updates - should ALWAYS create SMF proposal
    result = await handle_update_insight({
        "insight_id": 42,
        "actor": "ethr",
        "reason": "ethr's proposal",
        "new_content": "Proposed content",
        "new_memory_strength": 0.7
    })

    # Verify proposal flow
    assert result["status"] == "pending"
    assert result["proposal_id"] == 999
    mock_create_smf.assert_called_once()
    mock_execute.assert_not_called()  # CRITICAL: No direct execution for ethr


# =============================================================================
# AC-6: Not Found Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.update.execute_update_with_history')
async def test_not_found_insight(mock_execute, with_project_context):
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
async def test_insight_id_validation(with_project_context):
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
async def test_actor_validation(with_project_context):
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
async def test_soft_deleted_insight_returns_404(mock_execute, with_project_context):
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
async def test_update_memory_strength_only(mock_execute, with_project_context):
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
async def test_update_both_content_and_strength(mock_execute, with_project_context):
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
async def test_database_error_returns_500(mock_execute, with_project_context):
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
async def test_smf_creation_error_returns_500(mock_create_smf, with_project_context):
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
