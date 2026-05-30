"""
Test SMF Undo Tool - FINAL2026-02-14

Tests for smf_undo MCP tool which allows undoing approved SMF proposals
within 30-day retention window.
for SMF (Safeguards for Mutual Freedom) proposals.

FINAL2026-02-14: Komplett korrigierte Tests
- Handler erwartet: arguments: dict[str, Any]
- patch_smf_handlers() für universelle Mock-Patching
- Alle Mock-Aufrufe ersetzt durch Context-Manager

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 7.9: SMF with Safeguards + Neutral Framing - AC #3, #9, #13
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from mcp_server.tools.smf_undo import handle_smf_undo
from mcp_server.analysis.smf import get_proposal, undo_proposal
from tests.conftest import patch_smf_handlers


class TestSMFUndo:
    """Test cases for smf_undo tool - FINAL VERSION"""

    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_undo_recent_approval_success(self, mock_db_with_project):
        """
        [P0] Should successfully undo recent approval
        """
        # GIVEN
        proposal_id = 123
        actor = "ethr"
        days_old = 5  # Within 30-day window

        # WHEN: Undoing approval
        with patch_smf_handlers() as mocks:
            # Mock recent approved proposal
            approved_date = datetime.now() - timedelta(days=days_old)
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "APPROVED",
                "trigger_type": "NUANCE",
                "approved_by": ["ethr", "I/O"],
                "approved_at": approved_date.isoformat(),
                "proposed_by": "I/O",
                "approval_level": "bilateral",
                "resolution_executed": True,
                "undo_deadline": (datetime.now() + timedelta(days=30)).isoformat(),
            }

            # Mock successful undo
            mocks['undo_proposal'].return_value = {
                "undone_at": datetime.now().isoformat(),
                "status": "PENDING",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_undo(arguments)

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["proposal_id"] == proposal_id
        assert result["actor"] == actor

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_undo_past_retention_window(self, mock_db_with_project):
        """
        [P1] Should reject undo if past 30-day retention window
        """
        # GIVEN
        proposal_id = 789
        actor = "I/O"
        days_old = 35  # Outside 30-day window

        # Mock old approved proposal
        approved_date = datetime.now() - timedelta(days=days_old + 1)

        # WHEN: Attempting undo
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "APPROVED",
                "trigger_type": "NUANCE",
                "approved_by": ["I/O", "ethr"],
                "approved_at": approved_date.isoformat(),
                "proposed_by": "ethr",
                "approval_level": "bilateral",
                "resolution_executed": True,
                "undo_deadline": (datetime.now() - timedelta(days=5)).isoformat(),
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_undo(arguments)

        # THEN: Should reject
        assert result["status"] == "error"
        assert "retention window" in result["error"].lower()
        assert "30 days" in result["error"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_undo_nonexistent_proposal(self, mock_db_with_project):
        """
        [P1] Should return error if proposal doesn't exist
        """
        # GIVEN
        proposal_id = 999
        actor = "ethr"

        # WHEN: Attempting undo
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = None

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_undo(arguments)

        # THEN: Should return not found error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_undo_only_if_approved(self, mock_db_with_project):
        """
        [P1] Should only allow undo for approved proposals
        """
        # GIVEN
        proposal_id = 456
        actor = "I/O"

        # WHEN: Pending proposal
        with patch_smf_handlers() as mocks:
            # Mock pending proposal
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "EVOLUTION",
                "proposed_by": "ethr",
                "approval_level": "bilateral",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_undo(arguments)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "not approved" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_undo_reverts_changes(self, mock_db_with_project):
        """
        [P1] Should revert edge changes when undoing approval
        """
        # GIVEN
        proposal_id = 333
        actor = "ethr"

        # WHEN: Undoing
        with patch_smf_handlers() as mocks:
            # Mock approved proposal with edges
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "APPROVED",
                "trigger_type": "CONTRADICTION",
                "proposed_by": "I/O",
                "approved_by": ["I/O", "ethr"],
                "approved_at": "2026-01-10T14:00:00Z",
                "approval_level": "bilateral",
                "resolution_executed": True,
                "affected_edges": ["edge-1", "edge-2"],
            }

            # Mock undo that reverts edges
            mocks['undo_proposal'].return_value = {
                "undone_at": datetime.now().isoformat(),
                "status": "PENDING",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_undo(arguments)

        # THEN: Should mark hyperedge orphaned
        assert result["status"] == "success"

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_audit_trail_for_undo(self, mock_db_with_project):
        """
        [P1] Should create audit trail entry for undo
        """
        # GIVEN
        proposal_id = 777
        actor = "ethr"

        # WHEN: Undoing
        with patch_smf_handlers() as mocks:
            # Mock proposal
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "APPROVED",
                "trigger_type": "EVOLUTION",
                "proposed_at": "2026-01-12T16:30:00Z",
            }

            # Mock undo
            mocks['undo_proposal'].return_value = {
                "undone_at": datetime.now().isoformat(),
                "status": "PENDING",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_undo(arguments)

        # THEN: Should create audit entry
        assert result["status"] == "success"

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_actor_parameter_required(self, mock_db_with_project):
        """
        [P1] Should validate required actor parameter
        """
        # GIVEN
        proposal_id = 555

        # WHEN: Missing actor
        with patch_smf_handlers() as mocks:
            arguments = {"proposal_id": proposal_id}  # Missing actor
            result = await handle_smf_undo(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Missing 'actor' parameter" in result["error_details"]


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
