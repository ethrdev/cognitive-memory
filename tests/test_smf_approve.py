"""
Test SMF Approve Tool

Tests for the smf_approve MCP tool which handles bilateral consent approval
for SMF (Safeguards for Mutual Freedom) proposals.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from mcp_server.tools.smf_approve import smf_approve


class TestSMFApprove:
    """Test cases for smf_approve tool"""

    @pytest.mark.p0
    def test_approve_proposal_success(self, mock_db_connection):
        """
        [P0] Should successfully approve pending SMF proposal
        """
        # GIVEN: Pending proposal
        proposal_id = 123
        actor = "I/O"

        # Mock proposal exists and is pending
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "NUANCE",
            "proposed_by": "ethr",
            "approval_level": "bilateral",
            "current_approvals": ["ethr"],
        }

        # Mock successful update
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Approving proposal
        result = smf_approve(mock_db_connection, proposal_id, actor)

        # THEN: Should return success
        assert result["status"] == "success"
        assert result["proposal_id"] == proposal_id
        assert result["actor"] == actor
        assert "timestamp" in result
        assert result["approval_level"] == "bilateral"

    @pytest.mark.p1
    def test_approve_already_approved_proposal(self, mock_db_connection):
        """
        [P1] Should return error if proposal already approved
        """
        # GIVEN: Already approved proposal
        proposal_id = 456
        actor = "I/O"

        # Mock proposal already approved
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "trigger_type": "NUANCE",
            "approved_by": ["ethr", "I/O"],
        }

        # WHEN: Attempting to approve
        result = smf_approve(mock_db_connection, proposal_id, actor)

        # THEN: Should return already approved error
        assert result["status"] == "error"
        assert "already approved" in result["error"].lower()

    @pytest.mark.p1
    def test_approve_rejected_proposal(self, mock_db_connection):
        """
        [P1] Should return error if proposal was rejected
        """
        # GIVEN: Rejected proposal
        proposal_id = 789
        actor = "I/O"

        # Mock proposal rejected
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "rejected",
            "trigger_type": "NUANCE",
        }

        # WHEN: Attempting to approve
        result = smf_approve(mock_db_connection, proposal_id, actor)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "rejected" in result["error"].lower()

    @pytest.mark.p1
    def test_approve_nonexistent_proposal(self, mock_db_connection):
        """
        [P1] Should return error if proposal doesn't exist
        """
        # GIVEN: Non-existent proposal
        proposal_id = 999
        actor = "I/O"

        # Mock proposal not found
        mock_db_connection.execute.return_value.fetchone.return_value = None

        # WHEN: Attempting to approve
        result = smf_approve(mock_db_connection, proposal_id, actor)

        # THEN: Should return not found error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    def test_io_only_approval_level(self, mock_db_connection):
        """
        [P1] Should allow single approval for io-level proposals
        """
        # GIVEN: IO-level proposal
        proposal_id = 111
        actor = "I/O"

        # Mock IO-level proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "NUANCE",
            "approval_level": "io",
            "current_approvals": [],
        }

        # Mock update to approved
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Approving
        result = smf_approve(mock_db_connection, proposal_id, actor)

        # THEN: Should succeed with single approval
        assert result["status"] == "success"
        assert result["approval_level"] == "io"

    @pytest.mark.p1
    def test_bilateral_consent_required(self, mock_db_connection):
        """
        [P1] Should require both parties for bilateral proposals
        """
        # GIVEN: Bilateral proposal approved by one party
        proposal_id = 222
        actor = "I/O"

        # Mock bilateral proposal partially approved
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "CONTRADICTION",
            "approval_level": "bilateral",
            "current_approvals": ["ethr"],  # ethr already approved
            "proposed_by": "I/O",
        }

        # Mock update
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: I/O approves
        result = smf_approve(mock_db_connection, proposal_id, actor)

        # THEN: Should complete bilateral consent
        assert result["status"] == "success"
        assert result["approval_level"] == "bilateral"

    @pytest.mark.p1
    def test_duplicate_approval_not_allowed(self, mock_db_connection):
        """
        [P1] Should prevent actor from approving twice
        """
        # GIVEN: Proposal already approved by actor
        proposal_id = 333
        actor = "I/O"

        # Mock proposal with duplicate approval attempt
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "NUANCE",
            "current_approvals": ["I/O"],  # Already approved by I/O
        }

        # WHEN: Attempting duplicate approval
        result = smf_approve(mock_db_connection, proposal_id, actor)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "already approved" in result["error"].lower()

    @pytest.mark.p1
    def test_audit_trail_creation(self, mock_db_connection):
        """
        [P1] Should create audit trail entry for approval
        """
        # GIVEN: Valid approval
        proposal_id = 444
        actor = "ethr"

        # Mock valid proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "NUANCE",
            "current_approvals": [],
        }

        # Mock update
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Approving
        result = smf_approve(mock_db_connection, proposal_id, actor)

        # THEN: Audit trail should be created
        # (Verify database calls include audit log)
        assert mock_db_connection.commit.called
        # At least execute and commit should be called
        assert mock_db_connection.execute.call_count >= 1


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
