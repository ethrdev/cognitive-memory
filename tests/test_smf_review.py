"""
Test SMF Review Tool

Tests for the smf_review MCP tool which retrieves detailed information
about specific SMF proposals.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from mcp_server.tools.smf_review import smf_review


class TestSMFReview:
    """Test cases for smf_review tool"""

    @pytest.mark.p1
    def test_get_proposal_details(self, mock_db_connection):
        """
        [P1] Should return full details of proposal
        """
        # GIVEN: Proposal ID
        proposal_id = 123

        # Mock proposal details
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "trigger_type": "NUANCE",
            "proposed_by": "I/O",
            "created_at": "2026-01-14T10:00:00Z",
            "approval_level": "bilateral",
            "context": "Accepting tension as healthy complexity",
            "affected_edges": ["edge-1", "edge-2", "edge-3"],
            "proposed_resolution": "NUANCE",
            "status": "pending",
            "current_approvals": ["ethr"],
            "consequences": "Preserves both perspectives",
        }

        # WHEN: Reviewing proposal
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should return full details
        assert "proposal" in result
        assert result["proposal"]["id"] == proposal_id
        assert result["proposal"]["trigger_type"] == "NUANCE"
        assert result["proposal"]["proposed_by"] == "I/O"
        assert "created_at" in result["proposal"]
        assert "context" in result["proposal"]
        assert "affected_edges" in result["proposal"]

    @pytest.mark.p1
    def test_include_consequences_of_approval(self, mock_db_connection):
        """
        [P1] Should include consequences of approval
        """
        # GIVEN: Proposal ID
        proposal_id = 456

        # Mock proposal with consequences
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "trigger_type": "EVOLUTION",
            "status": "pending",
            "consequences": {
                "if_approved": "Will mark position as evolved",
                "edges_affected": 2,
                "hyperedge_created": True,
                "audit_trail": "Will be created"
            },
        }

        # WHEN: Reviewing
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should include consequences
        assert "consequences_of_approval" in result
        assert "consequences_of_rejection" in result
        assert result["consequences_of_approval"] is not None

    @pytest.mark.p1
    def test_include_consequences_of_rejection(self, mock_db_connection):
        """
        [P1] Should include consequences of rejection
        """
        # GIVEN: Proposal ID
        proposal_id = 789

        # Mock proposal with rejection consequences
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "trigger_type": "NUANCE",
            "status": "pending",
            "consequences": {
                "if_rejected": "Dissonance remains unresolved",
                "future_review": "Can be resubmitted with more context",
            },
        }

        # WHEN: Reviewing
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should include rejection consequences
        assert "consequences_of_rejection" in result
        assert result["consequences_of_rejection"] is not None

    @pytest.mark.p1
    def test_include_approval_history(self, mock_db_connection):
        """
        [P1] Should include approval history if any
        """
        # GIVEN: Proposal with partial approvals
        proposal_id = 111

        # Mock proposal with history
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "trigger_type": "CONTRADICTION",
            "status": "pending",
            "approval_level": "bilateral",
            "current_approvals": ["ethr"],
            "approval_history": [
                {"actor": "ethr", "action": "approved", "timestamp": "2026-01-14T11:00:00Z"},
            ],
        }

        # WHEN: Reviewing
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should include history
        assert "approval_history" in result
        assert len(result["approval_history"]) > 0
        assert result["approval_history"][0]["actor"] == "ethr"

    @pytest.mark.p1
    def test_nonexistent_proposal(self, mock_db_connection):
        """
        [P1] Should return error for non-existent proposal
        """
        # GIVEN: Non-existent ID
        proposal_id = 999

        # Mock not found
        mock_db_connection.execute.return_value.fetchone.return_value = None

        # WHEN: Reviewing
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    def test_include_proposed_resolution_details(self, mock_db_connection):
        """
        [P1] Should include details of proposed resolution
        """
        # GIVEN: Proposal with resolution
        proposal_id = 222

        # Mock proposal with resolution
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "trigger_type": "EVOLUTION",
            "status": "pending",
            "proposed_resolution": {
                "type": "EVOLUTION",
                "context": "Position has developed over time",
                "hyperedge_required": True,
                "edges_to_link": ["edge-old", "edge-new"],
            },
        }

        # WHEN: Reviewing
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should include resolution details
        assert "proposed_resolution" in result
        assert result["proposed_resolution"]["type"] == "EVOLUTION"
        assert "context" in result["proposed_resolution"]

    @pytest.mark.p1
    def test_indicate_required_approvers(self, mock_db_connection):
        """
        [P1] Should indicate who needs to approve
        """
        # GIVEN: Bilateral proposal
        proposal_id = 333

        # Mock bilateral proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "trigger_type": "CONTRADICTION",
            "status": "pending",
            "approval_level": "bilateral",
            "proposed_by": "I/O",
            "current_approvals": ["ethr"],  # ethr approved
            "required_approvers": ["I/O", "ethr"],
            "pending_approvals": ["I/O"],  # Still waiting for I/O
        }

        # WHEN: Reviewing
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should show approval status
        assert "approval_status" in result
        assert "required_approvers" in result["approval_status"]
        assert "pending_approvals" in result["approval_status"]
        assert "I/O" in result["approval_status"]["pending_approvals"]

    @pytest.mark.p1
    def test_io_level_proposal(self, mock_db_connection):
        """
        [P1] Should handle IO-level proposals differently
        """
        # GIVEN: IO-level proposal
        proposal_id = 444

        # Mock IO-level proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "trigger_type": "NUANCE",
            "status": "pending",
            "approval_level": "io",
            "proposed_by": "ethr",
            "current_approvals": [],
            "required_approvers": ["I/O"],
            "pending_approvals": ["I/O"],
        }

        # WHEN: Reviewing
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should indicate single approver needed
        assert result["approval_status"]["approval_level"] == "io"
        assert len(result["approval_status"]["required_approvers"]) == 1
        assert "I/O" in result["approval_status"]["required_approvers"]

    @pytest.mark.p2
    def test_include_related_proposals(self, mock_db_connection):
        """
        [P2] Should include related proposals if any
        """
        # GIVEN: Proposal with relations
        proposal_id = 555

        # Mock proposal with relations
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "trigger_type": "NUANCE",
            "status": "pending",
            "related_proposals": [444, 666],
        }

        # WHEN: Reviewing
        result = smf_review(mock_db_connection, proposal_id)

        # THEN: Should include related proposals
        assert "related_proposals" in result
        assert len(result["related_proposals"]) > 0


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
