"""
Tests for Dissonance Resolution functionality.

Tests for resolve_dissonance() function, _find_review_by_id() helper,
include_superseded filtering in query_neighbors(), and MCP tool integration.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from mcp_server.analysis.dissonance import (
    resolve_dissonance,
    _find_review_by_id,
    _nuance_reviews,
    DissonanceResult,
    DissonanceType,
    get_resolutions_for_node
)
from mcp_server.db.graph import _filter_superseded_edges, _is_edge_superseded


class TestFindReviewById:
    """Test _find_review_by_id helper function."""

    def test_find_existing_review(self):
        """Test finding an existing review by ID."""
        # Setup test data
        test_review = {
            "id": "test-review-123",
            "dissonance": {"edge_a_id": "edge-a", "edge_b_id": "edge-b"},
            "status": "PENDING_IO_REVIEW"
        }
        _nuance_reviews.append(test_review)

        # Test
        result = _find_review_by_id("test-review-123")

        # Assert
        assert result == test_review

        # Cleanup
        _nuance_reviews.clear()

    def test_find_nonexistent_review(self):
        """Test finding a non-existent review returns None."""
        # Setup test data
        test_review = {
            "id": "test-review-123",
            "dissonance": {"edge_a_id": "edge-a", "edge_b_id": "edge-b"},
            "status": "PENDING_IO_REVIEW"
        }
        _nuance_reviews.append(test_review)

        # Test
        result = _find_review_by_id("nonexistent-id")

        # Assert
        assert result is None

        # Cleanup
        _nuance_reviews.clear()

    def test_empty_reviews_list(self):
        """Test finding review when list is empty."""
        # Ensure list is empty
        _nuance_reviews.clear()

        # Test
        result = _find_review_by_id("any-id")

        # Assert
        assert result is None


class TestResolveDissonance:
    """Test resolve_dissonance function."""

    def setup_method(self):
        """Setup test data before each test."""
        # Clear reviews list
        _nuance_reviews.clear()

        # Create test dissonance and review
        self.test_dissonance = DissonanceResult(
            edge_a_id="edge-a-123",
            edge_b_id="edge-b-456",
            dissonance_type=DissonanceType.EVOLUTION,
            confidence_score=0.8,
            description="Position evolved from X to Y",
            context={"reasoning": "Clear progression over time"},
            requires_review=False
        )

        self.test_review = {
            "id": "review-abc-123",
            "dissonance": {
                "edge_a_id": "edge-a-123",
                "edge_b_id": "edge-b-456",
                "dissonance_type": "EVOLUTION",  # Store as string instead of enum
                "confidence_score": 0.8,
                "description": "Position evolved from X to Y",
                "context": {"reasoning": "Clear progression over time"},
                "requires_review": False
            },
            "status": "PENDING_IO_REVIEW",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        _nuance_reviews.append(self.test_review)

    def teardown_method(self):
        """Cleanup after each test."""
        _nuance_reviews.clear()

    @patch('mcp_server.analysis.dissonance.get_or_create_node')
    @patch('mcp_server.analysis.dissonance.add_edge')
    def test_resolve_evolution_dissonance(self, mock_add_edge, mock_get_node):
        """Test resolving an EVOLUTION type dissonance."""
        # Setup mocks
        mock_resolution_node = {"node_id": "resolution-node-123"}
        mock_get_node.return_value = mock_resolution_node
        mock_resolution_edge = {"edge_id": "resolution-edge-456"}
        mock_add_edge.side_effect = [mock_resolution_edge, {"edge_id": "second-edge"}]

        # Test
        result = resolve_dissonance(
            review_id="review-abc-123",
            resolution_type="EVOLUTION",
            context="Position developed from initial concept to refined understanding",
            resolved_by="I/O"
        )

        # Assert
        assert result["resolution_type"] == "EVOLUTION"
        assert result["edge_a_id"] == "edge-a-123"
        assert result["edge_b_id"] == "edge-b-456"
        assert result["resolved_by"] == "I/O"
        assert "resolved_at" in result

        # Check that get_or_create_node was called with correct name
        mock_get_node.assert_called_once_with(
            name="Resolution-review-a",
            label="Resolution"
        )

        # Check that add_edge was called twice (hyperedge needs 2 edges)
        assert mock_add_edge.call_count == 2

        # Check the properties contain EVOLUTION-specific fields
        first_call_args = mock_add_edge.call_args_list[0]
        properties = json.loads(first_call_args[1]["properties"])
        assert properties["edge_type"] == "resolution"
        assert properties["resolution_type"] == "EVOLUTION"
        assert properties["supersedes"] == ["edge-a-123"]
        assert properties["superseded_by"] == ["edge-b-456"]

        # Check review status was updated
        assert self.test_review["status"] == "CONFIRMED"
        assert self.test_review["reviewed_at"] is not None
        assert self.test_review["review_reason"] == "Position developed from initial concept to refined understanding"

    @patch('mcp_server.analysis.dissonance.get_or_create_node')
    @patch('mcp_server.analysis.dissonance.add_edge')
    def test_resolve_contradiction_dissonance(self, mock_add_edge, mock_get_node):
        """Test resolving a CONTRADICTION type dissonance."""
        # Setup mocks
        mock_resolution_node = {"node_id": "resolution-node-123"}
        mock_get_node.return_value = mock_resolution_node
        mock_resolution_edge = {"edge_id": "resolution-edge-456"}
        mock_add_edge.side_effect = [mock_resolution_edge, {"edge_id": "second-edge"}]

        # Test
        result = resolve_dissonance(
            review_id="review-abc-123",
            resolution_type="CONTRADICTION",
            context="Fundamental disagreement between core principles",
            resolved_by="I/O"
        )

        # Assert
        assert result["resolution_type"] == "CONTRADICTION"

        # Check the properties contain CONTRADICTION-specific fields
        first_call_args = mock_add_edge.call_args_list[0]
        properties = json.loads(first_call_args[1]["properties"])
        assert properties["edge_type"] == "resolution"
        assert properties["resolution_type"] == "CONTRADICTION"
        assert "supersedes" not in properties
        assert "superseded_by" not in properties
        assert properties["affected_edges"] == ["edge-a-123", "edge-b-456"]

    @patch('mcp_server.analysis.dissonance.get_or_create_node')
    @patch('mcp_server.analysis.dissonance.add_edge')
    def test_resolve_nuance_dissonance(self, mock_add_edge, mock_get_node):
        """Test resolving a NUANCE type dissonance."""
        # Setup mocks
        mock_resolution_node = {"node_id": "resolution-node-123"}
        mock_get_node.return_value = mock_resolution_node
        mock_resolution_edge = {"edge_id": "resolution-edge-456"}
        mock_add_edge.side_effect = [mock_resolution_edge, {"edge_id": "second-edge"}]

        # Test
        result = resolve_dissonance(
            review_id="review-abc-123",
            resolution_type="NUANCE",
            context="Dialectical tension between complementary values",
            resolved_by="I/O"
        )

        # Assert
        assert result["resolution_type"] == "NUANCE"

        # Check the properties contain NUANCE-specific fields
        first_call_args = mock_add_edge.call_args_list[0]
        properties = json.loads(first_call_args[1]["properties"])
        assert properties["edge_type"] == "resolution"
        assert properties["resolution_type"] == "NUANCE"
        assert "supersedes" not in properties
        assert "superseded_by" not in properties
        assert properties["affected_edges"] == ["edge-a-123", "edge-b-456"]

    def test_resolve_dissonance_invalid_review_id(self):
        """Test error handling for invalid review ID."""
        with pytest.raises(ValueError, match="Review invalid-id not found"):
            resolve_dissonance(
                review_id="invalid-id",
                resolution_type="EVOLUTION",
                context="Test context"
            )

    def test_resolve_dissonance_invalid_resolution_type(self):
        """Test error handling for invalid resolution type."""
        with pytest.raises(ValueError, match="Invalid resolution_type: INVALID"):
            resolve_dissonance(
                review_id="review-abc-123",
                resolution_type="INVALID",
                context="Test context"
            )

    def test_resolve_dissonance_missing_edge_ids(self):
        """Test error handling when review missing edge IDs."""
        # Create review with missing edge IDs
        bad_review = {
            "id": "bad-review",
            "dissonance": {"edge_a_id": None, "edge_b_id": ""},
            "status": "PENDING_IO_REVIEW"
        }
        _nuance_reviews.append(bad_review)

        with pytest.raises(ValueError, match="has invalid dissonance data"):
            resolve_dissonance(
                review_id="bad-review",
                resolution_type="EVOLUTION",
                context="Test context"
            )

        # Cleanup
        _nuance_reviews.remove(bad_review)


class TestIsEdgeSuperseded:
    """Test _is_edge_superseded helper function."""

    def test_edge_with_explicit_superseded_flag(self):
        """Test edge with explicit superseded=True property."""
        properties = {"superseded": True}
        assert _is_edge_superseded("edge-123", properties) is True

    def test_edge_without_superseded_flag(self):
        """Test edge without superseded property."""
        properties = {"edge_type": "relation"}
        assert _is_edge_superseded("edge-123", properties) is False

    def test_edge_with_superseded_false(self):
        """Test edge with explicit superseded=False property."""
        properties = {"superseded": False}
        assert _is_edge_superseded("edge-123", properties) is False

    def test_edge_with_superseded_in_status(self):
        """Test edge with 'superseded' in status field."""
        properties = {"status": "completed-superseded-2024"}
        assert _is_edge_superseded("edge-123", properties) is True

    def test_resolution_edge_not_superseded(self):
        """Test that resolution edges are not considered superseded."""
        properties = {"edge_type": "resolution", "supersedes": ["edge-123"]}
        assert _is_edge_superseded("edge-123", properties) is False


class TestFilterSupersededEdges:
    """Test _filter_superseded_edges function."""

    def test_filter_mixed_edges(self):
        """Test filtering a mixed list of edges."""
        neighbors = [
            {
                "edge_id": "normal-edge-1",
                "edge_properties": {"edge_type": "relation"}
            },
            {
                "edge_id": "superseded-edge-1",
                "edge_properties": {"superseded": True}
            },
            {
                "edge_id": "resolution-edge-1",
                "edge_properties": {"edge_type": "resolution"}
            },
            {
                "edge_id": "normal-edge-2",
                "edge_properties": {"edge_type": "relation"}
            }
        ]

        result = _filter_superseded_edges(neighbors)

        # Should have 3 edges (normal-1, normal-2, resolution)
        assert len(result) == 3
        edge_ids = [n["edge_id"] for n in result]
        assert "normal-edge-1" in edge_ids
        assert "normal-edge-2" in edge_ids
        assert "resolution-edge-1" in edge_ids
        assert "superseded-edge-1" not in edge_ids

    def test_filter_no_edges(self):
        """Test filtering empty list."""
        result = _filter_superseded_edges([])
        assert result == []

    def test_filter_all_normal_edges(self):
        """Test filtering list with no superseded edges."""
        neighbors = [
            {"edge_id": "edge-1", "edge_properties": {"edge_type": "relation"}},
            {"edge_id": "edge-2", "edge_properties": {"edge_type": "relation"}}
        ]

        result = _filter_superseded_edges(neighbors)
        assert len(result) == 2
        assert result == neighbors

    def test_filter_all_superseded_edges(self):
        """Test filtering list with all superseded edges."""
        neighbors = [
            {"edge_id": "edge-1", "edge_properties": {"superseded": True}},
            {"edge_id": "edge-2", "edge_properties": {"status": "superseded-old"}}
        ]

        result = _filter_superseded_edges(neighbors)
        assert len(result) == 0


class TestGetResolutionsForNode:
    """Test get_resolutions_for_node function."""

    @patch('mcp_server.db.graph.query_neighbors')
    @patch('mcp_server.db.graph.get_node_by_name')
    def test_get_resolutions_for_existing_node(self, mock_get_node, mock_query_neighbors):
        """Test getting resolutions for a node with resolutions."""
        # Setup mocks - MEDIUM-3 FIX: get_node_by_name() returns "id", not "node_id"
        mock_get_node.return_value = {"id": "node-123"}
        mock_query_neighbors.return_value = [
            {
                "name": "Resolution-abc",
                "edge_properties": {
                    "edge_type": "resolution",
                    "resolution_type": "EVOLUTION",
                    "context": "Position evolved",
                    "supersedes": ["old-edge"],
                    "superseded_by": ["new-edge"],
                    "resolved_at": "2024-01-01T12:00:00Z",
                    "resolved_by": "I/O"
                }
            },
            {
                "name": "Resolution-def",
                "edge_properties": {
                    "edge_type": "resolution",
                    "resolution_type": "CONTRADICTION",
                    "context": "Fundamental conflict",
                    "affected_edges": ["edge-a", "edge-b"],
                    "resolved_at": "2024-01-02T13:00:00Z",
                    "resolved_by": "I/O"
                }
            }
        ]

        # Test
        result = get_resolutions_for_node("Test Node")

        # Assert
        assert len(result) == 2

        # Check first resolution (EVOLUTION)
        evolution = result[0]
        assert evolution["resolution_type"] == "EVOLUTION"
        assert evolution["context"] == "Position evolved"
        assert evolution["supersedes"] == ["old-edge"]
        assert evolution["superseded_by"] == ["new-edge"]
        assert evolution["resolved_by"] == "I/O"

        # Check second resolution (CONTRADICTION)
        contradiction = result[1]
        assert contradiction["resolution_type"] == "CONTRADICTION"
        assert contradiction["context"] == "Fundamental conflict"
        assert contradiction["affected_edges"] == ["edge-a", "edge-b"]
        assert contradiction["resolved_by"] == "I/O"

    @patch('mcp_server.db.graph.get_node_by_name')
    def test_get_resolutions_for_nonexistent_node(self, mock_get_node):
        """Test getting resolutions for a node that doesn't exist."""
        mock_get_node.return_value = None

        result = get_resolutions_for_node("Nonexistent Node")

        assert result == []

    @patch('mcp_server.db.graph.query_neighbors')
    @patch('mcp_server.db.graph.get_node_by_name')
    def test_get_resolutions_no_resolution_edges(self, mock_get_node, mock_query_neighbors):
        """Test getting resolutions when node has no resolution edges."""
        # MEDIUM-3 FIX: get_node_by_name() returns "id", not "node_id"
        mock_get_node.return_value = {"id": "node-123"}
        mock_query_neighbors.return_value = [
            {
                "name": "Related Node",
                "edge_properties": {"edge_type": "relation"}
            }
        ]

        result = get_resolutions_for_node("Test Node")

        assert result == []

    @patch('mcp_server.db.graph.query_neighbors')
    @patch('mcp_server.db.graph.get_node_by_name')
    def test_get_resolutions_mixed_edge_types(self, mock_get_node, mock_query_neighbors):
        """Test getting resolutions when mixed edge types exist."""
        # MEDIUM-3 FIX: get_node_by_name() returns "id", not "node_id"
        mock_get_node.return_value = {"id": "node-123"}
        mock_query_neighbors.return_value = [
            {
                "name": "Related Node",
                "edge_properties": {"edge_type": "relation"}
            },
            {
                "name": "Resolution-abc",
                "edge_properties": {
                    "edge_type": "resolution",
                    "resolution_type": "NUANCE",
                    "context": "Dialectical tension"
                }
            },
            {
                "name": "Another Related",
                "edge_properties": {"edge_type": "uses"}
            }
        ]

        result = get_resolutions_for_node("Test Node")

        # Should only return the resolution edge
        assert len(result) == 1
        assert result[0]["resolution_type"] == "NUANCE"
        assert result[0]["context"] == "Dialectical tension"


class TestResolveDissonanceMCPTool:
    """Test resolve_dissonance MCP tool."""

    @patch('mcp_server.tools.resolve_dissonance.resolve_dissonance')
    async def test_handle_resolve_dissonance_success(self, mock_resolve):
        """Test successful MCP tool invocation."""
        # Setup mock
        mock_resolve.return_value = {
            "resolution_id": "res-123",
            "resolution_type": "EVOLUTION",
            "edge_a_id": "edge-a",
            "edge_b_id": "edge-b",
            "resolved_at": "2024-01-01T12:00:00Z",
            "resolved_by": "I/O"
        }

        # Import handler
        from mcp_server.tools.resolve_dissonance import handle_resolve_dissonance

        # Test
        arguments = {
            "review_id": "review-123",
            "resolution_type": "EVOLUTION",
            "context": "Test evolution resolution"
        }

        result = await handle_resolve_dissonance(arguments)

        # Assert
        assert result["status"] == "success"
        assert "resolution" in result
        assert result["resolution"]["resolution_type"] == "EVOLUTION"
        assert "execution_time_ms" in result
        assert result["input_params"]["review_id"] == "review-123"

    @patch('mcp_server.tools.resolve_dissonance.resolve_dissonance')
    async def test_handle_resolve_dissonance_validation_error(self, mock_resolve):
        """Test MCP tool with validation error."""
        # Setup mock to raise ValueError
        mock_resolve.side_effect = ValueError("Invalid review ID")

        from mcp_server.tools.resolve_dissonance import handle_resolve_dissonance

        # Test
        arguments = {
            "review_id": "invalid-id",
            "resolution_type": "EVOLUTION",
            "context": "Test"
        }

        result = await handle_resolve_dissonance(arguments)

        # Assert
        assert result["error"] == "Resolution failed"
        assert "Invalid review ID" in result["details"]
        assert result["error_type"] == "validation_error"

    async def test_handle_resolve_dissonance_missing_parameters(self):
        """Test MCP tool with missing required parameters."""
        from mcp_server.tools.resolve_dissonance import handle_resolve_dissonance

        # Test missing review_id
        arguments = {
            "resolution_type": "EVOLUTION",
            "context": "Test"
        }

        result = await handle_resolve_dissonance(arguments)

        # Assert
        assert result["error"] == "Parameter validation failed"
        assert "review_id" in result["details"]

    async def test_handle_resolve_dissonance_invalid_resolution_type(self):
        """Test MCP tool with invalid resolution_type."""
        from mcp_server.tools.resolve_dissonance import handle_resolve_dissonance

        # Test
        arguments = {
            "review_id": "review-123",
            "resolution_type": "INVALID_TYPE",
            "context": "Test"
        }

        result = await handle_resolve_dissonance(arguments)

        # Assert
        assert result["error"] == "Parameter validation failed"
        assert "resolution_type" in result["details"]


class TestMarkEdgeAsSuperseded:
    """Test _mark_edge_as_superseded helper function (KRITISCH-1 fix)."""

    @patch('mcp_server.analysis.dissonance.get_connection')
    def test_mark_edge_as_superseded_success(self, mock_get_connection):
        """Test successfully marking an edge as superseded."""
        from mcp_server.analysis.dissonance import _mark_edge_as_superseded

        # Setup mock cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"properties": {"existing_key": "value"}}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=None)
        mock_get_connection.return_value = mock_conn

        # Test
        result = _mark_edge_as_superseded(
            edge_id="edge-123",
            superseded_at="2024-01-01T12:00:00Z",
            superseded_by="I/O"
        )

        # Assert
        assert result is True

        # Verify UPDATE was called with merged properties
        update_call = mock_cursor.execute.call_args_list[-1]
        update_sql = update_call[0][0]
        update_params = update_call[0][1]

        assert "UPDATE edges" in update_sql
        assert "properties" in update_sql

        # Check that properties were merged correctly
        import json
        props = json.loads(update_params[0])
        assert props["superseded"] is True
        assert props["superseded_at"] == "2024-01-01T12:00:00Z"
        assert props["superseded_by"] == "I/O"
        assert props["existing_key"] == "value"  # Original property preserved

    @patch('mcp_server.analysis.dissonance.get_connection')
    def test_mark_edge_as_superseded_not_found(self, mock_get_connection):
        """Test marking a non-existent edge returns False."""
        from mcp_server.analysis.dissonance import _mark_edge_as_superseded

        # Setup mock cursor to return None (edge not found)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=None)
        mock_get_connection.return_value = mock_conn

        # Test
        result = _mark_edge_as_superseded(
            edge_id="nonexistent-edge",
            superseded_at="2024-01-01T12:00:00Z",
            superseded_by="I/O"
        )

        # Assert
        assert result is False

    @patch('mcp_server.analysis.dissonance.get_connection')
    def test_mark_edge_as_superseded_handles_string_properties(self, mock_get_connection):
        """Test handling edge with string properties (JSON string)."""
        from mcp_server.analysis.dissonance import _mark_edge_as_superseded

        # Setup mock cursor with JSON string properties
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"properties": '{"key": "value"}'}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=None)
        mock_get_connection.return_value = mock_conn

        # Test
        result = _mark_edge_as_superseded(
            edge_id="edge-with-string-props",
            superseded_at="2024-01-01T12:00:00Z",
            superseded_by="I/O"
        )

        # Assert
        assert result is True


class TestResolveDissonanceEvolutionIntegration:
    """Integration test verifying EVOLUTION resolution marks edge as superseded."""

    def setup_method(self):
        """Setup test data before each test."""
        _nuance_reviews.clear()

        self.test_review = {
            "id": "integration-review-123",
            "dissonance": {
                "edge_a_id": "edge-a-integration",
                "edge_b_id": "edge-b-integration",
                "dissonance_type": "EVOLUTION",
            },
            "status": "PENDING_IO_REVIEW",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        _nuance_reviews.append(self.test_review)

    def teardown_method(self):
        """Cleanup after each test."""
        _nuance_reviews.clear()

    @patch('mcp_server.analysis.dissonance._mark_edge_as_superseded')
    @patch('mcp_server.analysis.dissonance.get_or_create_node')
    @patch('mcp_server.analysis.dissonance.add_edge')
    def test_evolution_resolution_calls_mark_superseded(
        self, mock_add_edge, mock_get_node, mock_mark_superseded
    ):
        """Verify that EVOLUTION resolution calls _mark_edge_as_superseded for edge_a."""
        # Setup mocks
        mock_get_node.return_value = {"node_id": "resolution-node-123"}
        mock_add_edge.return_value = {"edge_id": "resolution-edge-456"}
        mock_mark_superseded.return_value = True

        # Test
        result = resolve_dissonance(
            review_id="integration-review-123",
            resolution_type="EVOLUTION",
            context="Position evolved from old to new",
            resolved_by="I/O"
        )

        # Assert - _mark_edge_as_superseded was called with edge_a_id
        mock_mark_superseded.assert_called_once()
        call_args = mock_mark_superseded.call_args
        assert call_args[0][0] == "edge-a-integration"  # edge_id
        assert call_args[0][2] == "I/O"  # resolved_by

        # Assert result is correct
        assert result["resolution_type"] == "EVOLUTION"
        assert result["edge_a_id"] == "edge-a-integration"

    @patch('mcp_server.analysis.dissonance._mark_edge_as_superseded')
    @patch('mcp_server.analysis.dissonance.get_or_create_node')
    @patch('mcp_server.analysis.dissonance.add_edge')
    def test_contradiction_resolution_does_not_mark_superseded(
        self, mock_add_edge, mock_get_node, mock_mark_superseded
    ):
        """Verify that CONTRADICTION resolution does NOT call _mark_edge_as_superseded."""
        # Setup mocks
        mock_get_node.return_value = {"node_id": "resolution-node-123"}
        mock_add_edge.return_value = {"edge_id": "resolution-edge-456"}

        # Test
        result = resolve_dissonance(
            review_id="integration-review-123",
            resolution_type="CONTRADICTION",
            context="Fundamental disagreement remains",
            resolved_by="I/O"
        )

        # Assert - _mark_edge_as_superseded was NOT called
        mock_mark_superseded.assert_not_called()

        # Assert result is correct
        assert result["resolution_type"] == "CONTRADICTION"

    @patch('mcp_server.analysis.dissonance._mark_edge_as_superseded')
    @patch('mcp_server.analysis.dissonance.get_or_create_node')
    @patch('mcp_server.analysis.dissonance.add_edge')
    def test_nuance_resolution_does_not_mark_superseded(
        self, mock_add_edge, mock_get_node, mock_mark_superseded
    ):
        """Verify that NUANCE resolution does NOT call _mark_edge_as_superseded."""
        # Setup mocks
        mock_get_node.return_value = {"node_id": "resolution-node-123"}
        mock_add_edge.return_value = {"edge_id": "resolution-edge-456"}

        # Test
        result = resolve_dissonance(
            review_id="integration-review-123",
            resolution_type="NUANCE",
            context="Dialectical tension accepted",
            resolved_by="I/O"
        )

        # Assert - _mark_edge_as_superseded was NOT called
        mock_mark_superseded.assert_not_called()

        # Assert result is correct
        assert result["resolution_type"] == "NUANCE"