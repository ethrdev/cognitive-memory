"""
Test SMF Review Tool - FINAL2026-02-14

Tests for smf_review MCP tool which retrieves detailed information
about specific SMF proposals.

FINAL2026-02-14: Komplett korrigierte Tests
- Handler erwartet: arguments: dict[str, Any]
- patch_smf_handlers() für universelle Mock-Patching
- Alle Mock-Aufrufe ersetzt durch Context-Manager

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 7.9: SMF mit Safeguards + Neutral Framing - AC #3, #9, #13
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from mcp_server.tools.smf_review import handle_smf_review
from mcp_server.analysis.smf import get_proposal
from mcp_server.db.graph import get_edge_by_id
from tests.conftest import patch_smf_handlers


class TestSMFReview:
    """Test cases for smf_review tool - FINAL VERSION"""

    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_review_proposal_success(self, mock_db_with_project):
        """
        [P0] Should retrieve proposal details successfully
        """
        # GIVEN
        proposal_id = 123
        actor = "ethr"

        # WHEN: Getting proposal details
        with patch_smf_handlers() as mocks:
            # Mock proposal exists
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "EVOLUTION",
                "proposed_by": "I/O",
                "approval_level": "io",
                "created_at": "2026-01-10T14:20:00Z",
                "context": "Position has developed",
                "affected_edges": ["edge-old", "edge-new"],
                "proposed_action": {"resolution_type": "EVOLUTION"},
            }

            # Mock edge details
            mocks['get_edge_by_id'].return_value = {
                "id": "edge-1",
                "relation": "related_to",
                "source_name": "concept_A",
                "target_name": "concept_B",
                "properties": {"weight": 0.8},
                "created_at": "2026-01-05T10:00:00Z",
            }

            arguments = {"proposal_id": proposal_id}
            result = await handle_smf_review(arguments)

        # THEN: Should return proposal with all fields
        assert result["status"] == "success"
        assert "proposal" in result
        assert result["proposal"]["id"] == proposal_id
        assert result["proposal"]["trigger_type"] == "EVOLUTION"

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_review_nonexistent_proposal(self, mock_db_with_project):
        """
        [P1] Should return error if proposal doesn't exist
        """
        # GIVEN
        proposal_id = 999

        # WHEN: Requesting review
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = None

            arguments = {"proposal_id": proposal_id}
            result = await handle_smf_review(arguments)

        # THEN: Should return not found error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_include_approval_history(self, mock_db_with_project):
        """
        [P1] Should include approval history in response
        """
        # GIVEN
        proposal_id = 456

        # WHEN: Getting proposal details
        with patch_smf_handlers() as mocks:
            # Mock proposal with history
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "NUANCE",
                "proposed_by": "ethr",
                "approval_level": "bilateral",
                "created_at": "2026-01-14T12:00:00Z",
                "approval_history": [
                    {"actor": "I/O", "action": "approved", "timestamp": "2026-01-14T11:00:00Z"},
                ],
            }

            arguments = {"proposal_id": proposal_id}
            result = await handle_smf_review(arguments)

        # THEN: Should include history
        assert result["status"] == "success"
        assert "approval_history" in result["proposal"]
        assert len(result["proposal"]["approval_history"]) == 1

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_include_consequences(self, mock_db_with_project):
        """
        [P1] Should include consequences of approval and rejection
        """
        # GIVEN
        proposal_id = 789

        # WHEN: Getting proposal details
        with patch_smf_handlers() as mocks:
            # Mock proposal
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "CONTRADICTION",
                "proposed_by": "I/O",
                "approval_level": "bilateral",
                "created_at": "2026-01-15T09:30:00Z",
                "context": "Conflicting positions",
                "affected_edges": ["edge-1", "edge-2"],
                "proposed_action": {"resolution_type": "MERGE"},
            }

            arguments = {"proposal_id": proposal_id}
            result = await handle_smf_review(arguments)

        # THEN: Should include consequences
        assert result["status"] == "success"
        assert "consequences" in result["proposal"]
        assert "if_approved" in result["proposal"]["consequences"]
        assert "if_rejected" in result["proposal"]["consequences"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_indicate_required_approvers(self, mock_db_with_project):
        """
        [P1] Should show which approvals are still required
        """
        # GIVEN
        proposal_id = 111

        # WHEN: Getting proposal details
        with patch_smf_handlers() as mocks:
            # Mock bilateral proposal
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "EVOLUTION",
                "proposed_by": "ethr",
                "approval_level": "bilateral",
            }

            arguments = {"proposal_id": proposal_id}
            result = await handle_smf_review(arguments)

        # THEN: Should show required approvers
        assert result["status"] == "success"
        assert "approval_status" in result["proposal"]
        assert "required_approvers" in result["proposal"]["approval_status"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_proposal_id_parameter_required(self, mock_db_with_project):
        """
        [P1] Should validate required proposal_id parameter
        """
        # GIVEN
        actor = "ethr"

        # WHEN: Missing proposal_id
        with patch_smf_handlers() as mocks:
            arguments = {"actor": actor}  # Missing proposal_id
            result = await handle_smf_review(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Missing 'proposal_id' parameter" in result["error_details"]


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
