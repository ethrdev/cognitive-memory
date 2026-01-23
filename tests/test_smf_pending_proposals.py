"""
Test SMF Pending Proposals Tool

Tests for the smf_pending_proposals MCP tool which lists all pending
SMF proposals requiring approval.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from mcp_server.tools.smf_pending_proposals import smf_pending_proposals


class TestSMFPendingProposals:
    """Test cases for smf_pending_proposals tool"""

    @pytest.mark.p1
    def test_list_all_pending_proposals(self, mock_db_connection):
        """
        [P1] Should return all pending proposals
        """
        # GIVEN: Multiple pending proposals
        actor = None  # All actors

        # Mock pending proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "trigger_type": "NUANCE",
                "proposed_by": "I/O",
                "created_at": "2026-01-14T10:00:00Z",
                "approval_level": "bilateral",
                "context": "Accept tension as complexity"
            },
            {
                "id": 2,
                "trigger_type": "EVOLUTION",
                "proposed_by": "ethr",
                "created_at": "2026-01-14T11:00:00Z",
                "approval_level": "io",
                "context": "Position developed over time"
            },
            {
                "id": 3,
                "trigger_type": "CONTRADICTION",
                "proposed_by": "I/O",
                "created_at": "2026-01-14T12:00:00Z",
                "approval_level": "bilateral",
                "context": "Acknowledge conflicting views"
            },
        ]

        # WHEN: Listing pending proposals
        result = smf_pending_proposals(mock_db_connection, actor)

        # THEN: Should return all proposals
        assert "proposals" in result
        assert len(result["proposals"]) == 3
        assert all(p["status"] == "pending" for p in result["proposals"])

    @pytest.mark.p1
    def test_filter_by_actor(self, mock_db_connection):
        """
        [P1] Should filter proposals by specific actor
        """
        # GIVEN: Filter by actor
        actor = "I/O"

        # Mock all proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "trigger_type": "NUANCE",
                "proposed_by": "I/O",
                "approval_level": "bilateral",
            },
            {
                "id": 2,
                "trigger_type": "EVOLUTION",
                "proposed_by": "ethr",
                "approval_level": "io",
            },
            {
                "id": 3,
                "trigger_type": "NUANCE",
                "proposed_by": "I/O",
                "approval_level": "bilateral",
            },
        ]

        # WHEN: Listing for specific actor
        result = smf_pending_proposals(mock_db_connection, actor)

        # THEN: Should only return actor's proposals
        assert len(result["proposals"]) == 2
        assert all(p["proposed_by"] == "I/O" for p in result["proposals"])

    @pytest.mark.p1
    def test_filter_by_trigger_type(self, mock_db_connection):
        """
        [P1] Should filter proposals by trigger type
        """
        # GIVEN: Filter by trigger type
        trigger_type = "NUANCE"

        # Mock all proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "trigger_type": "NUANCE",
                "proposed_by": "I/O",
            },
            {
                "id": 2,
                "trigger_type": "EVOLUTION",
                "proposed_by": "ethr",
            },
            {
                "id": 3,
                "trigger_type": "NUANCE",
                "proposed_by": "I/O",
            },
        ]

        # WHEN: Listing by type
        result = smf_pending_proposals(mock_db_connection, actor=None, trigger_type=trigger_type)

        # THEN: Should only return matching type
        assert len(result["proposals"]) == 2
        assert all(p["trigger_type"] == "NUANCE" for p in result["proposals"])

    @pytest.mark.p1
    def test_include_proposal_details(self, mock_db_connection):
        """
        [P1] Should include all proposal details
        """
        # GIVEN: Standard query
        actor = None

        # Mock detailed proposal
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "trigger_type": "NUANCE",
                "proposed_by": "I/O",
                "created_at": "2026-01-14T10:00:00Z",
                "approval_level": "bilateral",
                "context": "Detailed context",
                "affected_edges": ["edge-1", "edge-2"],
                "resolution_type": "NUANCE",
            },
        ]

        # WHEN: Getting proposals
        result = smf_pending_proposals(mock_db_connection, actor)

        # THEN: Should include all fields
        proposal = result["proposals"][0]
        assert "id" in proposal
        assert "trigger_type" in proposal
        assert "proposed_by" in proposal
        assert "created_at" in proposal
        assert "approval_level" in proposal
        assert "context" in proposal
        assert "affected_edges" in proposal
        assert "resolution_type" in proposal

    @pytest.mark.p1
    def test_sort_by_created_date(self, mock_db_connection):
        """
        [P1] Should sort proposals by creation date (newest first)
        """
        # GIVEN: Mixed creation dates
        actor = None

        # Mock unsorted proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {
                "id": 3,
                "trigger_type": "NUANCE",
                "created_at": "2026-01-14T12:00:00Z",
            },
            {
                "id": 1,
                "trigger_type": "EVOLUTION",
                "created_at": "2026-01-14T10:00:00Z",
            },
            {
                "id": 2,
                "trigger_type": "CONTRADICTION",
                "created_at": "2026-01-14T11:00:00Z",
            },
        ]

        # WHEN: Getting proposals
        result = smf_pending_proposals(mock_db_connection, actor)

        # THEN: Should be sorted by date (newest first)
        dates = [p["created_at"] for p in result["proposals"]]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.p1
    def test_empty_pending_proposals(self, mock_db_connection):
        """
        [P1] Should return empty list when no pending proposals
        """
        # GIVEN: No pending proposals
        actor = None

        # Mock empty result
        mock_db_connection.execute.return_value.fetchall.return_value = []

        # WHEN: Listing proposals
        result = smf_pending_proposals(mock_db_connection, actor)

        # THEN: Should return empty list
        assert "proposals" in result
        assert len(result["proposals"]) == 0
        assert result["count"] == 0

    @pytest.mark.p1
    def test_count_summary(self, mock_db_connection):
        """
        [P1] Should include count summary by type and level
        """
        # GIVEN: Various proposal types
        actor = None

        # Mock diverse proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {
                "id": 1,
                "trigger_type": "NUANCE",
                "approval_level": "bilateral",
            },
            {
                "id": 2,
                "trigger_type": "EVOLUTION",
                "approval_level": "io",
            },
            {
                "id": 3,
                "trigger_type": "NUANCE",
                "approval_level": "bilateral",
            },
            {
                "id": 4,
                "trigger_type": "CONTRADICTION",
                "approval_level": "bilateral",
            },
        ]

        # WHEN: Getting proposals
        result = smf_pending_proposals(mock_db_connection, actor)

        # THEN: Should include summary
        assert "summary" in result
        assert "by_trigger_type" in result["summary"]
        assert "by_approval_level" in result["summary"]
        assert result["summary"]["by_trigger_type"]["NUANCE"] == 2
        assert result["summary"]["by_approval_level"]["bilateral"] == 3

    @pytest.mark.p2
    def test_limit_results(self, mock_db_connection):
        """
        [P2] Should support limiting number of results
        """
        # GIVEN: Limit parameter
        actor = None
        limit = 2

        # Mock many proposals
        mock_db_connection.execute.return_value.fetchall.return_value = [
            {"id": i, "trigger_type": "NUANCE"}
            for i in range(1, 11)
        ]

        # WHEN: Listing with limit
        result = smf_pending_proposals(mock_db_connection, actor, limit=limit)

        # THEN: Should respect limit
        assert len(result["proposals"]) <= limit


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
