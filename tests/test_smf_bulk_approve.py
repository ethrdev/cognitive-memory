"""
Test SMF Bulk Approve Tool

Tests for the smf_bulk_approve MCP tool which handles batch approval
of multiple SMF proposals.
"""

import pytest
from unittest.mock import Mock, patch
from mcp_server.tools.smf_bulk_approve import smf_bulk_approve


class TestSMFBulkApprove:
    """Test cases for smf_bulk_approve tool"""

    @pytest.mark.p1
    def test_bulk_approve_multiple_proposals(self, mock_db_connection):
        """
        [P1] Should approve multiple proposals at once
        """
        # GIVEN: List of proposal IDs
        proposal_ids = [1, 2, 3]
        actor = "I/O"

        # Mock finding proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"id": 1, "status": "pending", "trigger_type": "NUANCE"},
            {"id": 2, "status": "pending", "trigger_type": "EVOLUTION"},
            {"id": 3, "status": "pending", "trigger_type": "NUANCE"},
        ]

        # Mock successful updates
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Bulk approving
        result = smf_bulk_approve(mock_db_connection, proposal_ids, actor)

        # THEN: Should return success for all
        assert result["status"] == "success"
        assert result["approved_count"] == 3
        assert result["failed_count"] == 0
        assert len(result["approved_proposals"]) == 3

    @pytest.mark.p1
    def test_bulk_approve_with_failures(self, mock_db_connection):
        """
        [P1] Should handle partial failures in bulk approval
        """
        # GIVEN: Mixed proposal states
        proposal_ids = [1, 2, 3, 4]
        actor = "I/O"

        # Mock mixed states
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"id": 1, "status": "pending", "trigger_type": "NUANCE"},
            {"id": 2, "status": "approved", "trigger_type": "EVOLUTION"},  # Already approved
            {"id": 3, "status": "pending", "trigger_type": "NUANCE"},
            {"id": 4, "status": "rejected", "trigger_type": "EVOLUTION"},  # Rejected
        ]

        # Mock updates for valid proposals
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Bulk approving
        result = smf_bulk_approve(mock_db_connection, proposal_ids, actor)

        # THEN: Should report partial success
        assert result["status"] == "partial_success"
        assert result["approved_count"] == 2  # Only pending ones
        assert result["failed_count"] == 2
        assert len(result["approved_proposals"]) == 2
        assert len(result["failed_proposals"]) == 2

    @pytest.mark.p1
    def test_bulk_approve_by_trigger_type(self, mock_db_connection):
        """
        [P1] Should filter proposals by trigger type
        """
        # GIVEN: Filter by trigger type
        trigger_type = "NUANCE"
        actor = "I/O"

        # Mock proposals with different types
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"id": 1, "status": "pending", "trigger_type": "NUANCE"},
            {"id": 2, "status": "pending", "trigger_type": "EVOLUTION"},  # Different type
            {"id": 3, "status": "pending", "trigger_type": "NUANCE"},
        ]

        # Mock updates
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Bulk approving by type
        result = smf_bulk_approve(
            mock_db_connection,
            proposal_ids=None,
            actor=actor,
            trigger_type=trigger_type
        )

        # THEN: Should approve only matching type
        assert result["approved_count"] == 2
        assert all(p["trigger_type"] == "NUANCE" for p in result["approved_proposals"])

    @pytest.mark.p1
    def test_bulk_approve_by_approval_level(self, mock_db_connection):
        """
        [P1] Should filter proposals by approval level
        """
        # GIVEN: Filter by approval level
        approval_level = "io"
        actor = "I/O"

        # Mock proposals with different levels
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"id": 1, "status": "pending", "approval_level": "io"},
            {"id": 2, "status": "pending", "approval_level": "bilateral"},
            {"id": 3, "status": "pending", "approval_level": "io"},
        ]

        # Mock updates
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Bulk approving by level
        result = smf_bulk_approve(
            mock_db_connection,
            proposal_ids=None,
            actor=actor,
            approval_level=approval_level
        )

        # THEN: Should approve only matching level
        assert result["approved_count"] == 2
        assert all(p["approval_level"] == "io" for p in result["approved_proposals"])

    @pytest.mark.p1
    def test_bulk_approve_dry_run(self, mock_db_connection):
        """
        [P1] Should support dry run mode to preview approvals
        """
        # GIVEN: Dry run request
        proposal_ids = [1, 2, 3]
        actor = "I/O"
        dry_run = True

        # Mock proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"id": 1, "status": "pending", "trigger_type": "NUANCE"},
            {"id": 2, "status": "pending", "trigger_type": "EVOLUTION"},
            {"id": 3, "status": "pending", "trigger_type": "NUANCE"},
        ]

        # WHEN: Dry run
        result = smf_bulk_approve(
            mock_db_connection,
            proposal_ids,
            actor,
            dry_run=dry_run
        )

        # THEN: Should preview without updating
        assert result["dry_run"] is True
        assert result["would_approve_count"] == 3
        assert result["status"] == "preview"
        # Verify no database updates were made
        # (Implementation should not commit in dry run)

    @pytest.mark.p1
    def test_bulk_approve_empty_list(self, mock_db_connection):
        """
        [P1] Should handle empty proposal list
        """
        # GIVEN: Empty list
        proposal_ids = []
        actor = "I/O"

        # WHEN: Bulk approving empty list
        result = smf_bulk_approve(mock_db_connection, proposal_ids, actor)

        # THEN: Should return empty result
        assert result["status"] == "success"
        assert result["approved_count"] == 0
        assert result["failed_count"] == 0

    @pytest.mark.p1
    def test_bulk_approve_nonexistent_ids(self, mock_db_connection):
        """
        [P1] Should handle non-existent proposal IDs gracefully
        """
        # GIVEN: Mix of existent and non-existent IDs
        proposal_ids = [1, 999, 2]
        actor = "I/O"

        # Mock finding only some proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"id": 1, "status": "pending"},
            {"id": 2, "status": "pending"},
        ]

        # Mock updates
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Bulk approving
        result = smf_bulk_approve(mock_db_connection, proposal_ids, actor)

        # THEN: Should report skipped IDs
        assert result["approved_count"] == 2
        assert 999 in result["skipped_ids"]
        assert len(result["skipped_ids"]) > 0


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
