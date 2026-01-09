"""
SMF Fixtures for DELETE_INSIGHT Action

Provides fixtures for testing SMF consent states with DELETE_INSIGHT action.

Story 26.3: DELETE Operation
Epic 26: Memory Management with Curation

This module provides fixtures for the 4 consent states:
1. pending - ethr initiates, waiting for I/O approval
2. approved - I/O approves, delete executes
3. rejected - I/O rejects, no delete happens
4. direct - I/O deletes directly (no SMF needed)
"""

import pytest
from datetime import datetime
from typing import Dict, Any


@pytest.fixture
def smf_proposal_pending():
    """
    Fixture for pending SMF proposal (ethr initiates deletion).

    This represents the state after ethr calls delete_insight with actor="ethr"
    and before I/O has approved or rejected.
    """
    return {
        "id": 1001,
        "trigger_type": "MANUAL",
        "proposed_action": {
            "action": "DELETE_INSIGHT",
            "insight_id": 42,
        },
        "affected_edges": [],
        "reasoning": "ethr proposes deletion of insight 42",
        "approval_level": "bilateral",
        "original_state": {
            "insight_id": 42,
            "actor": "ethr",
        },
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        "reviewed_at": None,
        "reviewer": None,
        "decision": None,
    }


@pytest.fixture
def smf_proposal_approved():
    """
    Fixture for approved SMF proposal (I/O approves deletion).

    This represents the state after I/O approves the deletion proposal.
    The delete should execute when this state is reached.
    """
    return {
        "id": 1002,
        "trigger_type": "MANUAL",
        "proposed_action": {
            "action": "DELETE_INSIGHT",
            "insight_id": 43,
        },
        "affected_edges": [],
        "reasoning": "ethr proposes deletion of insight 43",
        "approval_level": "bilateral",
        "original_state": {
            "insight_id": 43,
            "actor": "ethr",
        },
        "status": "approved",
        "created_at": datetime.now().isoformat(),
        "reviewed_at": datetime.now().isoformat(),
        "reviewer": "I/O",
        "decision": "approved",
        "review_notes": "Approve deletion - insight no longer relevant",
    }


@pytest.fixture
def smf_proposal_rejected():
    """
    Fixture for rejected SMF proposal (I/O rejects deletion).

    This represents the state after I/O rejects the deletion proposal.
    The delete should NOT execute when this state is reached.
    """
    return {
        "id": 1003,
        "trigger_type": "MANUAL",
        "proposed_action": {
            "action": "DELETE_INSIGHT",
            "insight_id": 44,
        },
        "affected_edges": [],
        "reasoning": "ethr proposes deletion of insight 44",
        "approval_level": "bilateral",
        "original_state": {
            "insight_id": 44,
            "actor": "ethr",
        },
        "status": "rejected",
        "created_at": datetime.now().isoformat(),
        "reviewed_at": datetime.now().isoformat(),
        "reviewer": "I/O",
        "decision": "rejected",
        "review_notes": "Reject deletion - insight still valuable for future reference",
    }


@pytest.fixture
def smf_proposal_direct():
    """
    Fixture for direct delete (I/O deletes own content).

    This represents the state when I/O deletes directly without SMF.
    No proposal is created in this case - it's immediate execution.
    """
    return None  # Direct delete doesn't create a proposal


@pytest.fixture
def delete_insight_test_data():
    """
    Fixture providing test data for DELETE_INSIGHT tests.

    Includes:
    - Valid insight IDs
    - Valid actors
    - Valid reasons
    - Invalid test cases
    """
    return {
        "valid_insight_id": 42,
        "valid_actor_io": "I/O",
        "valid_actor_ethr": "ethr",
        "valid_reason": "Test deletion for validation",
        "empty_reason": "",
        "missing_reason": None,
        "invalid_actor": "invalid",
        "invalid_actor_case": "io",  # Should be "I/O" not "io"
        "negative_insight_id": -1,
        "zero_insight_id": 0,
        "string_insight_id": "not-a-number",
    }


@pytest.fixture
def mock_execute_delete_with_history():
    """
    Mock for execute_delete_with_history function.

    Returns a successful delete result.
    """
    def _mock_function(insight_id: int, actor: str, reason: str) -> Dict[str, Any]:
        return {
            "success": True,
            "insight_id": insight_id,
            "history_id": 999,
            "status": "deleted",
            "recoverable": True
        }

    return _mock_function


@pytest.fixture
def mock_execute_delete_not_found():
    """
    Mock for execute_delete_with_history when insight not found.

    Raises ValueError for non-existent insight.
    """
    def _mock_function(insight_id: int, actor: str, reason: str) -> Dict[str, Any]:
        raise ValueError(f"Insight {insight_id} not found")

    return _mock_function


@pytest.fixture
def mock_execute_delete_already_deleted():
    """
    Mock for execute_delete_with_history when already deleted.

    Raises ValueError for already deleted insight.
    """
    def _mock_function(insight_id: int, actor: str, reason: str) -> Dict[str, Any]:
        raise ValueError("already deleted")

    return _mock_function


@pytest.fixture
def mock_create_smf_proposal():
    """
    Mock for create_smf_proposal function.

    Returns a proposal ID.
    """
    def _mock_function(
        trigger_type: str,
        proposed_action: Dict[str, Any],
        affected_edges: list,
        reasoning: str,
        approval_level: str,
        original_state: Dict[str, Any]
    ) -> int:
        # Verify the action is DELETE_INSIGHT
        assert proposed_action["action"] == "DELETE_INSIGHT"
        assert "insight_id" in proposed_action

        # Return a mock proposal ID
        return 1001

    return _mock_function


@pytest.fixture
def smf_consent_state_matrix():
    """
    Matrix of all 4 SMF consent states for DELETE_INSIGHT.

    Used to verify all states are handled correctly.
    """
    return {
        "pending": {
            "description": "ethr initiates, waiting for I/O approval",
            "actor": "ethr",
            "expected_status": "pending",
            "creates_proposal": True,
            "executes_delete": False,
            "requires_approval": True,
        },
        "approved": {
            "description": "I/O approves deletion",
            "actor": "ethr",
            "expected_status": "approved",
            "creates_proposal": True,
            "executes_delete": True,
            "requires_approval": True,
        },
        "rejected": {
            "description": "I/O rejects deletion",
            "actor": "ethr",
            "expected_status": "rejected",
            "creates_proposal": True,
            "executes_delete": False,
            "requires_approval": True,
        },
        "direct": {
            "description": "I/O deletes directly",
            "actor": "I/O",
            "expected_status": "deleted",
            "creates_proposal": False,
            "executes_delete": True,
            "requires_approval": False,
        }
    }


@pytest.fixture
def expected_delete_response_io():
    """
    Expected response when I/O deletes directly.
    """
    return {
        "success": True,
        "insight_id": 42,
        "history_id": 999,
        "status": "deleted",
        "recoverable": True
    }


@pytest.fixture
def expected_delete_response_ethr_pending():
    """
    Expected response when ethr initiates deletion (pending approval).
    """
    return {
        "status": "pending",
        "proposal_id": 1001,
        "message": "Waiting for I/O approval"
    }


@pytest.fixture
def expected_error_response_not_found():
    """
    Expected error response when insight not found (AC-7).
    """
    return {
        "error": {
            "code": 404,
            "message": "Insight 42 not found"
        }
    }


@pytest.fixture
def expected_error_response_already_deleted():
    """
    Expected error response when insight already deleted (AC-5).
    """
    return {
        "error": {
            "code": 409,
            "message": "already deleted"
        }
    }


@pytest.fixture
def expected_error_response_reason_required():
    """
    Expected error response when reason is missing (AC-6).
    """
    return {
        "error": {
            "code": 400,
            "message": "reason required",
            "field": "reason"
        }
    }


@pytest.fixture
def expected_error_response_invalid_actor():
    """
    Expected error response when actor is invalid.
    """
    return {
        "error": {
            "code": 400,
            "message": "actor must be 'I/O' or 'ethr'",
            "field": "actor"
        }
    }


@pytest.fixture
def expected_error_response_invalid_insight_id():
    """
    Expected error response when insight_id is invalid.
    """
    return {
        "error": {
            "code": 400,
            "message": "insight_id must be a positive integer",
            "field": "insight_id"
        }
    }
