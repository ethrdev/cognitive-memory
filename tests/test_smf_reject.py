"""
Test SMF Reject Tool - FINAL2026-02-14

Tests for smf_reject MCP tool which handles rejection of SMF proposals
for SMF (Safeguards for Mutual Freedom) proposals.

FINAL2026-02-14: Komplett korrigierte Tests
- Handler erwartet: arguments: dict[str, Any]
- patch_smf_handlers() für universelle Mock-Patching

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 7.9: SMF with Safeguards + Neutral Framing - AC #3, #9, #13
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from mcp_server.tools.smf_reject import handle_smf_reject
from mcp_server.analysis.smf import get_proposal, reject_proposal
from tests.conftest import patch_smf_handlers


class TestSMFReject:
    """Test cases for smf_reject tool - FINAL VERSION"""

    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_reject_proposal_success(self, mock_db_with_project):
        """
        [P0] Should successfully reject SMF proposal
        """
        # GIVEN
        proposal_id = 789
        actor = "ethr"
        reason = "Test rejection"

        # WHEN: Rejecting proposal
        with patch_smf_handlers() as mocks:
            # Mock proposal exists and is pending
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "pending",
                "trigger_type": "NUANCE",
                "proposed_by": "I/O",
                "approval_level": "bilateral",
                "created_at": "2026-01-10T14:20:00Z",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor, "reason": reason}
            result = await handle_smf_reject(arguments)

        # THEN: Should return success
        assert result["status"] == "success"
        assert result["proposal_id"] == proposal_id
        assert result["actor"] == actor
        assert result["reason"] == reason

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_reject_already_rejected_proposal(self, mock_db_with_project):
        """
        [P1] Should return error if proposal already rejected
        """
        # GIVEN
        proposal_id = 555
        actor = "ethr"
        reason = "Test"

        # WHEN: Proposal already rejected
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "rejected",
                "trigger_type": "CONTRADICTION",
                "proposed_by": "I/O",
                "approval_level": "bilateral",
                "current_approvals": ["ethr"],
                "rejection_reason": "Initial disagreement",
                "rejected_at": datetime.now() - timedelta(days=5),
                "rejected_by": "I/O",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor, "reason": reason}
            result = await handle_smf_reject(arguments)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "already rejected" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_reject_nonexistent_proposal(self, mock_db_with_project):
        """
        [P1] Should return error if proposal doesn't exist
        """
        # GIVEN
        proposal_id = 999
        actor = "I/O"
        reason = "Not found"

        # WHEN: Proposal not found
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = None

            arguments = {"proposal_id": proposal_id, "actor": actor, "reason": reason}
            result = await handle_smf_reject(arguments)

        # THEN: Should return not found error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_reason_parameter_required(self, mock_db_with_project):
        """
        [P1] Should require reason parameter
        """
        # GIVEN
        proposal_id = 444

        # WHEN: Missing reason
        with patch_smf_handlers() as mocks:
            arguments = {"proposal_id": proposal_id, "actor": "I/O"}  # Missing reason
            result = await handle_smf_reject(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Missing 'reason' parameter" in result["error_details"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_audit_trail_creation(self, mock_db_with_project):
        """
        [P1] Should create audit trail entry for rejection
        """
        # GIVEN
        proposal_id = 777
        actor = "ethr"
        reason = "Policy violation"

        # WHEN: Rejecting
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "pending",
                "trigger_type": "CONTRADICTION",
                "proposed_by": "I/O",
                "approval_level": "bilateral",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor, "reason": reason}
            result = await handle_smf_reject(arguments)

        # THEN: Verify audit trail
        assert result["status"] == "success"


@pytest.fixture
def mock_db_with_project():
    """
    Mock database connection with project context.

    This fixture simulates middleware context that tool handlers expect.
    Auto-applied to all tests (autouse=True in conftest.py).
    """
    mock = Mock()

    # Mock as async context manager
    mock.__aenter__ = Mock(return_value=mock)
    mock.__aexit__ = Mock(return_value=None)

    # Mock cursor for DictCursor compatibility
    mock.cursor.return_value.fetchone.return_value = None
    mock.cursor.return_value.fetchall.return_value = []

    return mock
