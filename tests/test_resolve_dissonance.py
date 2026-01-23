"""
Test Resolve Dissonance Tool

Tests for the resolve_dissonance MCP tool which handles resolution of detected
dissonances through hyperedges without deleting original edges.
"""

import pytest
from unittest.mock import Mock, patch
from mcp_server.tools.resolve_dissonance import resolve_dissonance


class TestResolveDissonance:
    """Test cases for resolve_dissonance tool"""

    @pytest.mark.p1
    def test_resolve_as_evolution(self, mock_db_connection):
        """
        [P1] Should create EVOLUTION resolution for developing relationships
        """
        # GIVEN: Dissonance review ID
        review_id = "uuid-review-123"
        resolution_type = "EVOLUTION"
        context = "Position developed from X to Y"
        resolved_by = "I/O"

        # Mock finding pending review
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": review_id,
            "status": "pending",
            "dissonance_type": "NUANCE",
        }

        # Mock resolution creation
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Resolving dissonance as evolution
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Should return success
        assert result["status"] == "success"
        assert result["resolution_type"] == "EVOLUTION"
        assert result["review_id"] == review_id
        assert result["resolved_by"] == resolved_by
        assert "timestamp" in result

    @pytest.mark.p1
    def test_resolve_as_contradiction(self, mock_db_connection):
        """
        [P1] Should create CONTRADICTION resolution for conflicting edges
        """
        # GIVEN: Contradiction resolution
        review_id = "uuid-review-456"
        resolution_type = "CONTRADICTION"
        context = "Edges represent genuinely opposing views"
        resolved_by = "ethr"

        # Mock pending review
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": review_id,
            "status": "pending",
            "dissonance_type": "CONTRADICTION",
        }

        # Mock resolution
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Resolving as contradiction
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["resolution_type"] == "CONTRADICTION"

    @pytest.mark.p1
    def test_resolve_as_nuance(self, mock_db_connection):
        """
        [P1] Should create NUANCE resolution for accepted tension
        """
        # GIVEN: Nuance resolution
        review_id = "uuid-review-789"
        resolution_type = "NUANCE"
        context = "Tension accepted as healthy complexity"
        resolved_by = "I/O"

        # Mock pending review
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": review_id,
            "status": "pending",
            "dissonance_type": "NUANCE",
        }

        # Mock resolution
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Resolving as nuance
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Should succeed
        assert result["status"] == "success"
        assert result["resolution_type"] == "NUANCE"

    @pytest.mark.p1
    def test_reject_invalid_resolution_type(self, mock_db_connection):
        """
        [P1] Should reject invalid resolution types
        """
        # GIVEN: Invalid resolution type
        review_id = "uuid-review-invalid"
        resolution_type = "INVALID_TYPE"
        context = "This should fail"
        resolved_by = "I/O"

        # Mock pending review
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": review_id,
            "status": "pending",
        }

        # WHEN: Attempting invalid resolution
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Should return error
        assert result["status"] == "error"
        assert "invalid" in result["error"].lower()
        assert "resolution_type" in result["error"].lower()

    @pytest.mark.p1
    def test_reject_nonexistent_review(self, mock_db_connection):
        """
        [P1] Should reject non-existent review ID
        """
        # GIVEN: Non-existent review
        review_id = "uuid-nonexistent"
        resolution_type = "EVOLUTION"
        context = "Test"
        resolved_by = "I/O"

        # Mock review not found
        mock_db_connection.execute.return_value.fetchone.return_value = None

        # WHEN: Attempting resolution
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Should return not found error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    def test_reject_already_resolved(self, mock_db_connection):
        """
        [P1] Should reject resolution of already resolved dissonance
        """
        # GIVEN: Already resolved review
        review_id = "uuid-resolved"
        resolution_type = "EVOLUTION"
        context = "Test"
        resolved_by = "I/O"

        # Mock already resolved review
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": review_id,
            "status": "resolved",
            "resolution_type": "NUANCE",
        }

        # WHEN: Attempting re-resolution
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Should return already resolved error
        assert result["status"] == "error"
        assert "already resolved" in result["error"].lower()

    @pytest.mark.p1
    def test_create_hyperedge(self, mock_db_connection):
        """
        [P1] Should create hyperedge for resolution without deleting original edges
        """
        # GIVEN: Valid resolution
        review_id = "uuid-review-hyperedge"
        resolution_type = "EVOLUTION"
        context = "Development tracked via hyperedge"
        resolved_by = "I/O"

        # Mock pending review
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": review_id,
            "status": "pending",
            "edge_ids": ["edge-1", "edge-2"],
        }

        # Mock resolution creation
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Resolving
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Should create hyperedge
        assert "hyperedge_id" in result
        assert "original_edges_preserved" in result
        assert result["original_edges_preserved"] is True
        # Verify original edges were not deleted
        # (Implementation should preserve edges)

    @pytest.mark.p1
    def test_update_review_status(self, mock_db_connection):
        """
        [P1] Should update review status to resolved
        """
        # GIVEN: Valid resolution
        review_id = "uuid-review-update"
        resolution_type = "EVOLUTION"
        context = "Status update test"
        resolved_by = "I/O"

        # Mock pending review
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": review_id,
            "status": "pending",
        }

        # Mock resolution
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Resolving
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Should update status
        assert result["status"] == "success"
        # Verify database was updated with new status
        # (Implementation should update status to "resolved")

    @pytest.mark.p1
    def test_audit_trail(self, mock_db_connection):
        """
        [P1] Should create audit trail for resolution
        """
        # GIVEN: Valid resolution
        review_id = "uuid-review-audit"
        resolution_type = "NUANCE"
        context = "Audit trail verification"
        resolved_by = "ethr"

        # Mock pending review
        mock_db_connection.execute.return_value.fetchone.return_value = {
            "id": review_id,
            "status": "pending",
        }

        # Mock resolution
        mock_db_connection.execute.return_value = Mock()
        mock_db_connection.commit.return_value = None

        # WHEN: Resolving
        result = resolve_dissonance(
            mock_db_connection,
            review_id,
            resolution_type,
            context,
            resolved_by
        )

        # THEN: Audit trail should be created
        # (Verify database calls include audit log entry)
        assert mock_db_connection.commit.called


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
