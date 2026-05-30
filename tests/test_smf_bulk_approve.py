"""
Test SMF Bulk Approve Tool - FINAL2026-02-14

Tests for smf_bulk_approve MCP tool which handles bulk approval
for SMF (Safeguards for Mutual Freedom) proposals.

FINAL2026-02-14: Korrigierte API-Signatur-Tests
- Handler erwartet nun: arguments: dict[str, Any]
- Alle Parameter werden als dict übergeben
- Handler-Name korrigiert: handle_smf_bulk_approve (ohne 'e')

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 7.9: SMF mit Safeguards + Neutral Framing - AC #3, #9, #13
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from mcp_server.tools.smf_bulk_approve import handle_smf_bulk_approve
from mcp_server.analysis.smf import get_pending_proposals, approve_proposal


class TestSMFBulkApprove:
    """Test cases for smf_bulk_approve tool - FINAL VERSION"""

    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_bulk_approve_all_success(self, mock_db_with_project):
        """
        [P0] Should successfully approve multiple proposals
        """
        # GIVEN
        actor = "ethr"

        # Mock pending proposals
        with patch('mcp_server.analysis.smf.get_pending_proposals') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "status": "pending",
                    "trigger_type": "NUANCE",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                },
                {
                    "id": 2,
                    "status": "pending",
                    "trigger_type": "NUANCE",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                },
            ]

        with patch('mcp_server.analysis.smf.approve_proposal') as mock_approve:
            mock_approve.return_value = {
                "approved_by_io": False,
                "approved_by_ethr": True,
                "fully_approved": True,
                "status": "APPROVED"
            }

        # WHEN: Bulk approving
        arguments = {"actor": actor}
        result = await handle_smf_bulk_approve(arguments)

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["succeeded"] == 2

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_bulk_approve_with_trigger_type_filter(self, mock_db_with_project):
        """
        [P1] Should filter by trigger type
        """
        # GIVEN
        actor = "I/O"
        trigger_type = "NUANCE"

        # Mock proposals with different types
        with patch('mcp_server.analysis.smf.get_pending_proposals') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "status": "pending",
                    "trigger_type": "NUANCE",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                    "proposed_action": {"resolution_type": "NUANCE"},
                },
                {
                    "id": 2,
                    "status": "pending",
                    "trigger_type": "EVOLUTION",
                    "proposed_by": "I/O",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                    "proposed_action": {"resolution_type": "EVOLUTION"},
                },
            ]

        with patch('mcp_server.analysis.smf.approve_proposal') as mock_approve:
            mock_approve.return_value = {
                "approved_by_io": True,
                "approved_by_ethr": False,
                "fully_approved": False,
                "status": "PENDING"
            }

        # WHEN: Filtering by trigger type
        arguments = {"actor": actor, "trigger_type": trigger_type}
        result = await handle_smf_bulk_approve(arguments)

        # THEN: Should only approve NUANCE
        assert result["status"] == "success"
        assert result["succeeded"] == 1
        assert result["awaiting_bilateral"] == 1

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_bulk_approve_dry_run(self, mock_db_with_project):
        """
        [P1] Should support dry run mode
        """
        # GIVEN
        actor = "ethr"

        # Mock proposals
        with patch('mcp_server.analysis.smf.get_pending_proposals') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "status": "pending",
                    "trigger_type": "NUANCE",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                    "proposed_action": {"resolution_type": "NUANCE"},
                }
            ]

        # WHEN: Dry run
        arguments = {"actor": actor, "dry_run": True}
        result = await handle_smf_bulk_approve(arguments)

        # THEN: Should report without executing
        assert result["status"] == "dry_run"
        assert "proposals_to_approve" in result
        assert result["proposals_to_approve"] == 1

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_bulk_approve_skip_already_approved(self, mock_db_with_project):
        """
        [P1] Should skip proposals already approved by actor
        """
        # GIVEN
        actor = "I/O"

        # Mock proposals where one is already approved by I/O
        with patch('mcp_server.analysis.smf.get_pending_proposals') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "status": "pending",
                    "trigger_type": "NUANCE",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                },
                {
                    "id": 2,
                    "status": "pending",
                    "trigger_type": "EVOLUTION",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": ["I/O"],  # Already approved by I/O
                },
            ]

        with patch('mcp_server.analysis.smf.approve_proposal') as mock_approve:
            mock_approve.return_value = {
                "approved_by_io": True,
                "approved_by_ethr": False,
                "fully_approved": False,
                "status": "PENDING"
            }

        # WHEN: Bulk approving
        arguments = {"actor": actor}
        result = await handle_smf_bulk_approve(arguments)

        # THEN: Should skip the already approved one
        assert result["status"] == "success"
        assert result["succeeded"] == 1
        assert result["awaiting_bilateral"] == 1

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_parameter_validation_missing_actor(self, mock_db_with_project):
        """
        [P1] Should validate required actor parameter
        """
        # GIVEN - No actor

        # WHEN: Missing actor
        arguments = {}
        result = await handle_smf_bulk_approve(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Missing 'actor' parameter" in result["error_details"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_actor(self, mock_db_with_project):
        """
        [P1] Should reject invalid actor value
        """
        # GIVEN
        actor = "InvalidActor"

        # WHEN: Invalid actor
        arguments = {"actor": actor}
        result = await handle_smf_bulk_approve(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Invalid actor" in result["error_details"]


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
