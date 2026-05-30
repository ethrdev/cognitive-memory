"""
Test SMF Pending Proposals Tool

Tests for smf_pending_proposals MCP tool which lists all pending SMF proposals.
for SMF (Safeguards for Mutual Freedom) proposals.

FINAL2026-02-14: Korrigierte API-Signatur-Tests mit Helper-Funktionen
- Handler erwartet: arguments: dict[str, Any]
- patch_smf_handlers() für universelle Mock-Patching
- Keine direkten Handler-Aufrufe mehr

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 7.9: SMF with Safeguards + Neutral Framing - AC #3, #9, #13
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from mcp_server.tools.smf_pending_proposals import handle_smf_pending_proposals
from mcp_server.analysis.smf import get_proposal
from tests.conftest import patch_smf_handlers


class TestSMFPendingProposals:
    """Test cases for smf_pending_proposals tool - FINAL VERSION"""

    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_get_all_pending_proposals_success(self, mock_db_with_project):
        """
        [P0] Should return all pending proposals
        """
        # GIVEN
        actor = "I/O"

        # Mock proposal list - get_pending_proposals gibt Liste zurück
        with patch_smf_handlers() as mocks:
            mocks['get_pending_proposals'].return_value = [
                {
                    "id": 1,
                    "status": "pending",
                    "trigger_type": "NUANCE",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                    "created_at": "2026-01-14T12:00:00Z",
                    "context": "Acknowledge conflicting views",
                    "affected_edges": ["edge-1", "edge-2", "edge-3"],
                    "proposed_action": {"resolution_type": "NONE"},
                },
                {
                    "id": 2,
                    "status": "pending",
                    "trigger_type": "CONTRADICTION",
                    "proposed_by": "I/O",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                    "created_at": "2026-01-13T12:00:00Z",
                    "context": "Reconcile conflicting worldviews",
                    "affected_edges": ["edge-4", "edge-5"],
                    "proposed_action": {"resolution_type": "INTEGRATION"},
                },
                {
                    "id": 3,
                    "status": "pending",
                    "trigger_type": "EVOLUTION",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                    "created_at": "2026-01-12T12:00:00Z",
                    "context": "Position has developed over time",
                    "affected_edges": ["edge-old", "edge-new"],
                    "proposed_action": {"resolution_type": "EVOLUTION"},
                },
            ]

        # WHEN: Get pending proposals
        arguments = {"actor": actor}
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Should return all proposals
        assert result["status"] == "success"
        assert "proposals" in result
        assert len(result["proposals"]) == 3

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_filter_by_actor(self, mock_db_with_project):
        """
        [P1] Should only return actor's own proposals
        """
        # GIVEN
        actor = "I/O"

        # Mock proposals for specific actor
        with patch('mcp_server.analysis.smf.get_proposal') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "status": "pending",
                    "trigger_type": "NUANCE",
                    "proposed_by": "I/O",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                    "created_at": "2026-01-14T12:00:00Z",
                    "context": "Acknowledge conflicting views",
                    "affected_edges": ["edge-1", "edge-2", "edge-3"],
                    "proposed_resolution": "NONE",
                },
                {
                    "id": 2,
                    "status": "pending",
                    "trigger_type": "CONTRADICTION",
                    "proposed_by": "I/O",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                    "created_at": "2026-01-13T12:00:00Z",
                    "context": "Reconcile conflicting worldviews",
                    "affected_edges": ["edge-4", "edge-5"],
                    "proposed_resolution": "INTEGRATION",
                },
            ]

        # WHEN: Filtering by actor
        arguments = {"actor": actor}
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Should only return actor's proposals
        assert result["status"] == "success"
        assert len(result["proposals"]) == 2
        assert all(p["proposed_by"] == "I/O" for p in result["proposals"])

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_filter_by_trigger_type(self, mock_db_with_project):
        """
        [P1] Should filter proposals by trigger type
        """
        # GIVEN
        actor = None
        trigger_type = "NUANCE"

        # Mock proposals
        with patch('mcp_server.analysis.smf.get_proposal') as mock_get:
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
                    "trigger_type": "CONTRADICTION",
                    "proposed_by": "I/O",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                },
                {
                    "id": 3,
                    "status": "pending",
                    "trigger_type": "EVOLUTION",
                    "proposed_by": "ethr",
                    "approval_level": "bilateral",
                    "current_approvals": [],
                },
            ]

        # WHEN: Filtering by trigger type
        arguments = {"actor": actor, "trigger_type": trigger_type}
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Should only return matching type
        assert result["status"] == "success"
        assert len(result["proposals"]) == 1
        assert result["proposals"][0]["trigger_type"] == "NUANCE"

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_include_proposal_details(self, mock_db_with_project):
        """
        [P1] Should include all required fields in proposals
        """
        # GIVEN
        actor = None

        # Mock proposal with all fields
        with patch('mcp_server.analysis.smf.get_proposal') as mock_get:
            mock_get.return_value = {
                    "id": 123,
                    "status": "pending",
                    "trigger_type": "EVOLUTION",
                    "proposed_by": "ethr",
                    "approval_level": "io",
                    "current_approvals": [],
                    "created_at": "2026-01-10T14:20:00Z",
                    "context": "System has learned user behavior",
                    "affected_edges": ["edge-old", "edge-new"],
                    "proposed_resolution": "EVOLUTION",
                }

        # WHEN: Getting proposals
        arguments = {}
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Should include all fields
        assert result["status"] == "success"
        assert "proposals" in result
        assert len(result["proposals"]) == 1
        proposal = result["proposals"][0]
        assert "id" in proposal
        assert "trigger_type" in proposal
        assert "proposed_by" in proposal
        assert "approval_level" in proposal
        assert "current_approvals" in proposal
        assert "created_at" in proposal
        assert "context" in proposal
        assert "affected_edges" in proposal
        assert "proposed_resolution" in proposal

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_empty_pending_proposals(self, mock_db_with_project):
        """
        [P1] Should return empty list when no proposals
        """
        # GIVEN
        actor = None

        # Mock no proposals
        with patch('mcp_server.analysis.smf.get_proposal') as mock_get:
            mock_get.return_value = []

        # WHEN: Getting proposals with no data
        arguments = {"actor": actor}
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Should return empty list
        assert result["status"] == "success"
        assert result["proposals"] == []
        assert result["count"] == 0

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_limit_parameter(self, mock_db_with_project):
        """
        [P1] Should respect limit parameter
        """
        # GIVEN
        actor = None
        limit = 2

        # Mock proposals
        with patch('mcp_server.analysis.smf.get_proposal') as mock_get:
            mock_get.return_value = [
                {"id": i, "status": "pending", "trigger_type": "NUANCE", "proposed_by": "ethr", "approval_level": "bilateral", "current_approvals": []}
                for i in range(1, 4)
            ]

        # WHEN: Requesting with limit
        arguments = {"actor": actor, "limit": limit}
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Should return only limited results
        assert result["status"] == "success"
        assert len(result["proposals"]) == 2

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_include_summary(self, mock_db_with_project):
        """
        [P1] Should include summary statistics by trigger type and approval level
        """
        # GIVEN
        actor = None

        # Mock proposals
        with patch('mcp_server.analysis.smf.get_proposal') as mock_get:
            mock_get.return_value = [
                {"id": 1, "status": "pending", "trigger_type": "NUANCE", "proposed_by": "ethr", "approval_level": "bilateral", "current_approvals": []},
                {"id": 2, "status": "pending", "trigger_type": "NUANCE", "proposed_by": "ethr", "approval_level": "bilateral", "current_approvals": []},
                {"id": 3, "status": "pending", "trigger_type": "EVOLUTION", "proposed_by": "ethr", "approval_level": "bilateral", "current_approvals": []},
                {"id": 4, "status": "pending", "trigger_type": "CONTRADICTION", "proposed_by": "I/O", "approval_level": "bilateral", "current_approvals": []},
                {"id": 5, "status": "pending", "trigger_type": "EVOLUTION", "proposed_by": "I/O", "approval_level": "bilateral", "current_approvals": []},
            ]

        # WHEN: Getting proposals
        arguments = {"actor": actor}
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Should include summary
        assert result["status"] == "success"
        assert "summary" in result
        assert "by_trigger_type" in result["summary"]
        assert "by_approval_level" in result["summary"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_actor_parameter_required(self, mock_db_with_project):
        """
        [P1] Should require actor parameter
        """
        # GIVEN
        proposal_id = 123

        # WHEN: Missing actor
        arguments = {"proposal_id": proposal_id}  # Missing actor
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Missing 'actor' parameter" in result["error_details"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_count_includes_total(self, mock_db_with_project):
        """
        [P1] Should return total count including filtered results
        """
        # GIVEN
        actor = None

        # Mock proposals
        with patch('mcp_server.analysis.smf.get_proposal') as mock_get:
            mock_get.return_value = [
                {"id": 1, "status": "pending", "trigger_type": "NUANCE", "proposed_by": "ethr", "approval_level": "bilateral"},
                {"id": 2, "status": "pending", "trigger_type": "CONTRADICTION", "proposed_by": "I/O", "approval_level": "bilateral"},
                {"id": 3, "status": "pending", "trigger_type": "EVOLUTION", "proposed_by": "ethr", "approval_level": "io"},
            ]

        # WHEN: Getting proposals
        arguments = {"actor": actor}
        result = await handle_smf_pending_proposals(arguments)

        # THEN: Count should include all proposals
        assert result["status"] == "success"
        assert result["count"] == 3


@pytest.fixture
def mock_db_with_project():
    """
    Mock database connection with project context.

    This fixture simulates the middleware context that tool handlers expect.
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
