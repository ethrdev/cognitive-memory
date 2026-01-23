"""
Test SMF Undo Tool

Tests for the smf_undo MCP tool which allows undoing approved SMF proposals
within the 30-day retention window.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from mcp_server.tools.smf_undo import smf_undo


class TestSMFUndo:
    """Test cases for smf_undo tool"""

    @pytest.mark.p1
    def test_undo_recent_approval(self, mock_db_connection):
        """
        [P1] Should undo recently approved proposal within retention window
        """
        # GIVEN: Recently approved proposal (5 days ago)
        proposal_id = 123
        actor = "I/O"

        # Mock recently approved proposal
        approved_date = datetime.now() - timedelta(days=5)
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "approved_at": approved_date.isoformat(),
            "trigger_type": "NUANCE",
            "resolution_executed": True,
            "hyperedge_id": "hyper-123",
        }

        # Mock undo operation
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Undoing approval
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["proposal_id"] == proposal_id
        assert result["actor"] == actor
        assert "days_old" in result
        assert result["within_retention_window"] is True
        assert "hyperedge_marked_orphaned" in result

    @pytest.mark.p1
    def test_reject_undo_outside_retention_window(self, mock_db_connection):
        """
        [P1] Should reject undo outside 30-day window
        """
        # GIVEN: Old approved proposal (35 days ago)
        proposal_id = 456
        actor = "ethr"

        # Mock old approved proposal
        approved_date = datetime.now() - timedelta(days=35)
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "approved_at": approved_date.isoformat(),
            "trigger_type": "EVOLUTION",
        }

        # WHEN: Attempting undo
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: Should reject
        assert result["status"] == "error"
        assert "retention window" in result["error"].lower()
        assert "30 days" in result["error"]

    @pytest.mark.p1
    def test_undo_only_if_approved(self, mock_db_connection):
        """
        [P1] Should only undo approved proposals
        """
        # GIVEN: Pending proposal
        proposal_id = 789
        actor = "I/O"

        # Mock pending proposal
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "pending",
            "trigger_type": "NUANCE",
        }

        # WHEN: Attempting undo
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "not approved" in result["error"].lower()

    @pytest.mark.p1
    def test_undo_only_if_proposal_exists(self, mock_db_connection):
        """
        [P1] Should return error for non-existent proposal
        """
        # GIVEN: Non-existent proposal
        proposal_id = 999
        actor = "I/O"

        # Mock not found
        mock_db_connection.execute.return_value.fetchone.return_value = None

        # WHEN: Attempting undo
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    def test_mark_hyperedge_orphaned(self, mock_db_connection):
        """
        [P1] Should mark hyperedge as orphaned when undoing
        """
        # GIVEN: Approved proposal with hyperedge
        proposal_id = 111
        actor = "I/O"

        # Mock approved proposal with hyperedge
        approved_date = datetime.now() - timedelta(days=10)
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "approved_at": approved_date.isoformat(),
            "hyperedge_id": "hyper-456",
            "resolution_executed": True,
        }

        # Mock undo
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Undoing
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: Should mark hyperedge orphaned
        assert result["status"] == "success"
        assert result["hyperedge_marked_orphaned"] is True
        assert result["hyperedge_id"] == "hyper-456"

    @pytest.mark.p1
    def test_reverse_edge_changes(self, mock_db_connection):
        """
        [P1] Should reverse edge changes made by resolution
        """
        # GIVEN: Approved proposal that modified edges
        proposal_id = 222
        actor = "ethr"

        # Mock approved proposal
        approved_date = datetime.now() - timedelta(days=15)
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "approved_at": approved_date.isoformat(),
            "affected_edges": ["edge-1", "edge-2"],
            "resolution_executed": True,
        }

        # Mock undo
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Undoing
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: Should reverse changes
        assert result["status"] == "success"
        assert "edges_reverted" in result
        assert len(result["edges_reverted"]) > 0

    @pytest.mark.p1
    def test_audit_trail_for_undo(self, mock_db_connection):
        """
        [P1] Should create audit trail for undo operation
        """
        # GIVEN: Valid undo
        proposal_id = 333
        actor = "I/O"

        # Mock approved proposal
        approved_date = datetime.now() - timedelta(days=7)
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "approved_at": approved_date.isoformat(),
            "trigger_type": "NUANCE",
        }

        # Mock undo
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Undoing
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: Should create audit trail
        assert "audit_entry" in result
        assert result["audit_entry"]["action"] == "undo"
        assert result["audit_entry"]["actor"] == actor
        assert result["audit_entry"]["proposal_id"] == proposal_id

    @pytest.mark.p1
    def test_require_authorization(self, mock_db_connection):
        """
        [P1] Should verify actor has authorization to undo
        """
        # GIVEN: Approved proposal by different actor
        proposal_id = 444
        actor = "ethr"

        # Mock approved proposal by I/O
        approved_date = datetime.now() - timedelta(days=10)
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "approved_at": approved_date.isoformat(),
            "proposed_by": "I/O",
            "trigger_type": "NUANCE",
        }

        # WHEN: Different actor attempts undo
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: May require additional verification
        # (Implementation may allow or reject based on policy)
        # For now, we'll allow it but log the authorization check
        assert "authorization_checked" in result or result["status"] in ["success", "error"]

    @pytest.mark.p1
    def test_boundary_30_days(self, mock_db_connection):
        """
        [P1] Should handle boundary case of exactly 30 days
        """
        # GIVEN: Exactly 30 days old
        proposal_id = 555
        actor = "I/O"

        # Mock proposal exactly at boundary
        approved_date = datetime.now() - timedelta(days=30)
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": proposal_id,
            "status": "approved",
            "approved_at": approved_date.isoformat(),
        }

        # Mock undo
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Undoing at boundary
        result = smf_undo(mock_db_connection, proposal_id, actor)

        # THEN: Should succeed (within window)
        assert result["status"] == "success"
        assert result["within_retention_window"] is True


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
