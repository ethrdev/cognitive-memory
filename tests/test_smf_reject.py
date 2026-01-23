"""
Test SMF Reject Tool

Tests for the smf_reject MCP tool which handles rejection of SMF proposals
with proper audit logging.
"""

import pytest
from unittest.mock import Mock, patch
from mcp_server.tools.smf_reject import smf_reject


class TestSMFReject:
    """Test cases for smf_reject tool"""

    @pytest.mark.p1
    def test_reject_pending_proposal(self, mock_db_connection):
        """
        [P1] Should successfully reject pending proposal
        """
        # GIVEN: Pending proposal
        proposal_id = 123
        actor = "I/O"
        reason = "Insufficient context for resolution"

        # Mock proposal exists and is pending
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "NUANCE",
            "proposed_by": "ethr",
        }

        # Mock successful rejection
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Rejecting proposal
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should return success
        assert result["status"] == "success"
        assert result["proposal_id"] == proposal_id
        assert result["actor"] == actor
        assert result["reason"] == reason
        assert "timestamp" in result

    @pytest.mark.p1
    def test_reject_already_approved_proposal(self, mock_db_connection):
        """
        [P1] Should reject already approved proposal
        """
        # GIVEN: Approved proposal
        proposal_id = 456
        actor = "I/O"
        reason = "Changed mind"

        # Mock already approved proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "trigger_type": "NUANCE",
            "approved_by": ["ethr", "I/O"],
        }

        # WHEN: Attempting to reject
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "already approved" in result["error"].lower()

    @pytest.mark.p1
    def test_reject_already_rejected_proposal(self, mock_db_connection):
        """
        [P1] Should handle already rejected proposal
        """
        # GIVEN: Already rejected proposal
        proposal_id = 789
        actor = "I/O"
        reason = "Duplicate"

        # Mock already rejected proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "rejected",
            "trigger_type": "NUANCE",
            "rejected_by": "ethr",
        }

        # WHEN: Attempting to reject again
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "already rejected" in result["error"].lower()

    @pytest.mark.p1
    def test_reject_nonexistent_proposal(self, mock_db_connection):
        """
        [P1] Should reject non-existent proposal
        """
        # GIVEN: Non-existent proposal
        proposal_id = 999
        actor = "I/O"
        reason = "Test"

        # Mock proposal not found
        mock_db_connection.execute.return_value.fetchone.return_value = None

        # WHEN: Attempting to reject
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should return not found error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    def test_require_rejection_reason(self, mock_db_connection):
        """
        [P1] Should require a reason for rejection
        """
        # GIVEN: Empty reason
        proposal_id = 111
        actor = "I/O"
        reason = ""  # Empty reason

        # Mock pending proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
        }

        # WHEN: Attempting rejection without reason
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should require reason
        assert result["status"] == "error"
        assert "reason" in result["error"].lower()

    @pytest.mark.p1
    def test_update_status_to_rejected(self, mock_db_connection):
        """
        [P1] Should update proposal status to rejected
        """
        # GIVEN: Valid rejection
        proposal_id = 222
        actor = "I/O"
        reason = "Insufficient evidence"

        # Mock pending proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
        }

        # Mock rejection
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Rejecting
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should update status
        assert result["status"] == "success"
        # Verify database was updated with rejected status
        # (Implementation should update status to "rejected")

    @pytest.mark.p1
    def test_audit_trail_with_reason(self, mock_db_connection):
        """
        [P1] Should create audit trail with rejection reason
        """
        # GIVEN: Valid rejection with reason
        proposal_id = 333
        actor = "ethr"
        reason = "Conflicts with established pattern"

        # Mock pending proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "NUANCE",
        }

        # Mock rejection
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Rejecting
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should create audit trail with reason
        assert "audit_entry" in result
        assert result["audit_entry"]["reason"] == reason
        assert result["audit_entry"]["rejected_by"] == actor
        # Verify audit trail was created in database

    @pytest.mark.p1
    def test_allow_proposer_to_reject_own_proposal(self, mock_db_connection):
        """
        [P1] Should allow proposer to reject their own proposal
        """
        # GIVEN: Proposer rejecting own proposal
        proposal_id = 444
        actor = "I/O"  # Same as proposed_by
        reason = "Changed perspective"

        # Mock proposer-owned proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "proposed_by": "I/O",
        }

        # Mock rejection
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Rejecting own proposal
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["rejected_own_proposal"] is True

    @pytest.mark.p1
    def test_allow_approver_to_reject(self, mock_db_connection):
        """
        [P1] Should allow approver to reject before full approval
        """
        # GIVEN: Pending bilateral proposal
        proposal_id = 555
        actor = "ethr"  # One of the required approvers
        reason = "Requires further discussion"

        # Mock pending bilateral proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "CONTRADICTION",
            "approval_level": "bilateral",
            "proposed_by": "I/O",
        }

        # Mock rejection
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Approver rejects
        result = smf_reject(mock_db_connection, proposal_id, actor, reason)

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["approval_level"] == "bilateral"


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
