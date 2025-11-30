"""
Tests for GraphStore class functionality.

Story 5.7: Graph Query Neighbors Library API
Tests cover all GraphStore methods with comprehensive validation and error handling.
"""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock
import pytest

from cognitive_memory.store import GraphStore
from cognitive_memory.exceptions import ConnectionError, ValidationError, StorageError


class TestGraphStore:
    """Test suite for GraphStore class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.graph_store = GraphStore()
        # Mock connection manager for testing
        self.graph_store._is_connected = True

    # =========================================================================
    # Test _ensure_connected() helper method
    # =========================================================================

    def test_ensure_connected_raises_error_when_not_connected(self):
        """Test that _ensure_connected raises ConnectionError when not connected."""
        self.graph_store._is_connected = False

        with pytest.raises(ConnectionError, match="GraphStore is not connected"):
            self.graph_store._ensure_connected()

    def test_ensure_connected_passes_when_connected(self):
        """Test that _ensure_connected passes when connected."""
        self.graph_store._is_connected = True

        # Should not raise any exception
        self.graph_store._ensure_connected()

    # =========================================================================
    # Test add_node() method
    # =========================================================================

    @patch('cognitive_memory.store.db_add_node')
    def test_add_node_creates_new_node_successfully(self, mock_db_add_node):
        """Test successful node creation."""
        # Setup mock
        mock_db_add_node.return_value = {
            "node_id": "test-uuid-123",
            "created": True,
            "label": "Technology",
            "name": "Python"
        }

        # Execute
        result = self.graph_store.add_node("Python", "Technology", {"version": "3.11"})

        # Verify
        assert result == "test-uuid-123"
        mock_db_add_node.assert_called_once_with(
            label="Technology",
            name="Python",
            properties='{"version": "3.11"}'
        )

    @patch('cognitive_memory.store.db_add_node')
    def test_add_node_with_none_properties(self, mock_db_add_node):
        """Test node creation with None properties."""
        mock_db_add_node.return_value = {"node_id": "test-uuid-456"}

        result = self.graph_store.add_node("Django", "Framework", None)

        assert result == "test-uuid-456"
        mock_db_add_node.assert_called_once_with(
            label="Framework",
            name="Django",
            properties="{}"
        )

    @patch('cognitive_memory.store.db_add_node')
    def test_add_node_idempotent_operation(self, mock_db_add_node):
        """Test that add_node is idempotent for existing nodes."""
        mock_db_add_node.return_value = {
            "node_id": "existing-uuid",
            "created": False,
            "label": "Technology",
            "name": "Python"
        }

        result = self.graph_store.add_node("Python", "Technology")

        assert result == int("existing-uuid")
        mock_db_add_node.assert_called_once()

    def test_add_node_validation_empty_name(self):
        """Test ValidationError for empty name."""
        with pytest.raises(ValidationError, match="name cannot be empty"):
            self.graph_store.add_node("", "Technology")

    def test_add_node_validation_whitespace_only_name(self):
        """Test ValidationError for whitespace-only name."""
        with pytest.raises(ValidationError, match="name cannot be empty"):
            self.graph_store.add_node("   ", "Technology")

    def test_add_node_validation_empty_label(self):
        """Test ValidationError for empty label."""
        with pytest.raises(ValidationError, match="label cannot be empty"):
            self.graph_store.add_node("Python", "")

    def test_add_node_validation_whitespace_only_label(self):
        """Test ValidationError for whitespace-only label."""
        with pytest.raises(ValidationError, match="label cannot be empty"):
            self.graph_store.add_node("Python", "   ")

    @patch('cognitive_memory.store.db_add_node')
    def test_add_node_storage_error_wrapping(self, mock_db_add_node):
        """Test that database exceptions are wrapped as StorageError."""
        mock_db_add_node.side_effect = Exception("Database connection failed")

        with pytest.raises(StorageError, match="Failed to add node"):
            self.graph_store.add_node("Python", "Technology")

    # =========================================================================
    # Test add_edge() method
    # =========================================================================

    @patch('cognitive_memory.store.db_add_edge')
    def test_add_edge_creates_new_edge_successfully(self, mock_db_add_edge):
        """Test successful edge creation."""
        mock_db_add_edge.return_value = {"edge_id": "edge-uuid-123"}

        result = self.graph_store.add_edge("Python", "Django", "USES", 0.8)

        assert result == int("edge-uuid-123")
        mock_db_add_edge.assert_called_once_with(
            source_name="Python",
            target_name="Django",
            relation="USES",
            weight=0.8
        )

    @patch('cognitive_memory.store.db_add_edge')
    def test_add_edge_with_default_weight(self, mock_db_add_edge):
        """Test edge creation with default weight."""
        mock_db_add_edge.return_value = {"edge_id": "edge-uuid-456"}

        result = self.graph_store.add_edge("Python", "FastAPI", "USES")

        assert result == int("edge-uuid-456")
        mock_db_add_edge.assert_called_once_with(
            source_name="Python",
            target_name="FastAPI",
            relation="USES",
            weight=1.0
        )

    def test_add_edge_validation_empty_source_name(self):
        """Test ValidationError for empty source name."""
        with pytest.raises(ValidationError, match="source_name cannot be empty"):
            self.graph_store.add_edge("", "Django", "USES")

    def test_add_edge_validation_empty_target_name(self):
        """Test ValidationError for empty target name."""
        with pytest.raises(ValidationError, match="target_name cannot be empty"):
            self.graph_store.add_edge("Python", "", "USES")

    def test_add_edge_validation_empty_relation(self):
        """Test ValidationError for empty relation."""
        with pytest.raises(ValidationError, match="relation cannot be empty"):
            self.graph_store.add_edge("Python", "Django", "")

    def test_add_edge_validation_weight_too_high(self):
        """Test ValidationError for weight > 1.0."""
        with pytest.raises(ValidationError, match="weight must be between 0.0 and 1.0"):
            self.graph_store.add_edge("Python", "Django", "USES", 1.5)

    def test_add_edge_validation_weight_too_low(self):
        """Test ValidationError for weight < 0.0."""
        with pytest.raises(ValidationError, match="weight must be between 0.0 and 1.0"):
            self.graph_store.add_edge("Python", "Django", "USES", -0.1)

    @patch('cognitive_memory.store.db_add_edge')
    def test_add_edge_storage_error_wrapping(self, mock_db_add_edge):
        """Test that database exceptions are wrapped as StorageError."""
        mock_db_add_edge.side_effect = Exception("Constraint violation")

        with pytest.raises(StorageError, match="Failed to add edge"):
            self.graph_store.add_edge("Python", "Django", "USES")

    # =========================================================================
    # Test query_neighbors() method
    # =========================================================================

    @patch('cognitive_memory.store.get_node_by_name')
    @patch('cognitive_memory.store.db_query_neighbors')
    def test_query_neighbors_single_hop_returns_direct_neighbors(self, mock_query, mock_get_node):
        """Test single-hop query returns direct neighbors."""
        # Setup mocks
        mock_get_node.return_value = {"id": "node-uuid-123", "name": "Python"}
        mock_query.return_value = [
            {
                "node_id": "neighbor-uuid-1",
                "name": "Django",
                "label": "Framework",
                "relation": "USES",
                "distance": 1,
                "weight": 0.8
            },
            {
                "node_id": "neighbor-uuid-2",
                "name": "FastAPI",
                "label": "Framework",
                "relation": "USES",
                "distance": 1,
                "weight": 0.9
            }
        ]

        # Execute
        result = self.graph_store.query_neighbors("Python", depth=1)

        # Verify
        assert len(result) == 2
        assert result[0]["name"] == "Django"
        assert result[0]["distance"] == 1
        assert result[1]["name"] == "FastAPI"
        mock_get_node.assert_called_once_with("Python")
        mock_query.assert_called_once_with(
            node_id="node-uuid-123",
            relation_type=None,
            max_depth=1
        )

    @patch('cognitive_memory.store.get_node_by_name')
    @patch('cognitive_memory.store.db_query_neighbors')
    def test_query_neighbors_multi_hop_returns_transitive_neighbors(self, mock_query, mock_get_node):
        """Test multi-hop query returns transitive neighbors."""
        mock_get_node.return_value = {"id": "node-uuid-123"}
        mock_query.return_value = [
            {"node_id": "neighbor-1", "name": "Django", "distance": 1},
            {"node_id": "neighbor-2", "name": "PostgreSQL", "distance": 2},
            {"node_id": "neighbor-3", "name": "SQL", "distance": 3}
        ]

        result = self.graph_store.query_neighbors("Python", depth=3)

        assert len(result) == 3
        # Verify distance values up to depth 3
        distances = [neighbor["distance"] for neighbor in result]
        assert max(distances) == 3
        mock_query.assert_called_once_with(
            node_id="node-uuid-123",
            relation_type=None,
            max_depth=3
        )

    @patch('cognitive_memory.store.get_node_by_name')
    @patch('cognitive_memory.store.db_query_neighbors')
    def test_query_neighbors_with_relation_filter(self, mock_query, mock_get_node):
        """Test query with relation type filter."""
        mock_get_node.return_value = {"id": "node-uuid-123"}
        mock_query.return_value = [
            {"node_id": "neighbor-1", "name": "Django", "relation": "USES"}
        ]

        result = self.graph_store.query_neighbors("Python", relation_type="USES")

        assert len(result) == 1
        assert result[0]["relation"] == "USES"
        mock_query.assert_called_once_with(
            node_id="node-uuid-123",
            relation_type="USES",
            max_depth=1
        )

    @patch('cognitive_memory.store.get_node_by_name')
    def test_query_neighbors_node_not_found_returns_empty_list(self, mock_get_node):
        """Test empty list when starting node doesn't exist."""
        mock_get_node.return_value = None

        result = self.graph_store.query_neighbors("NonExistentNode")

        assert result == []
        mock_get_node.assert_called_once_with("NonExistentNode")

    def test_query_neighbors_validation_empty_node_name(self):
        """Test ValidationError for empty node name."""
        with pytest.raises(ValidationError, match="node_name cannot be empty"):
            self.graph_store.query_neighbors("")

    def test_query_neighbors_validation_depth_too_high(self):
        """Test ValidationError for depth > 5."""
        with pytest.raises(ValidationError, match="depth must be between 1 and 5"):
            self.graph_store.query_neighbors("Python", depth=6)

    def test_query_neighbors_validation_depth_too_low(self):
        """Test ValidationError for depth < 1."""
        with pytest.raises(ValidationError, match="depth must be between 1 and 5"):
            self.graph_store.query_neighbors("Python", depth=0)

    @patch('cognitive_memory.store.get_node_by_name')
    @patch('cognitive_memory.store.db_query_neighbors')
    def test_query_neighbors_storage_error_wrapping(self, mock_query, mock_get_node):
        """Test that database exceptions are wrapped as StorageError."""
        mock_get_node.return_value = {"id": "node-uuid-123"}
        mock_query.side_effect = Exception("Query timeout")

        with pytest.raises(StorageError, match="Failed to query neighbors"):
            self.graph_store.query_neighbors("Python")

    # =========================================================================
    # Test find_path() method
    # =========================================================================

    @patch('cognitive_memory.store.db_find_path')
    def test_find_path_success_returns_path_data(self, mock_find_path):
        """Test successful path finding."""
        mock_find_path.return_value = {
            "path_found": True,
            "path_length": 3,
            "paths": [
                {"node_id": "node-1", "name": "Python"},
                {"node_id": "node-2", "name": "Django"},
                {"node_id": "node-3", "name": "PostgreSQL"}
            ]
        }

        result = self.graph_store.find_path("Python", "PostgreSQL", max_depth=5)

        assert result["path_found"] is True
        assert result["path_length"] == 3
        assert len(result["paths"]) == 3
        mock_find_path.assert_called_once_with(
            start_node="Python",
            end_node="PostgreSQL",
            max_depth=5
        )

    @patch('cognitive_memory.store.db_find_path')
    def test_find_path_no_path_available(self, mock_find_path):
        """Test case when no path exists."""
        mock_find_path.return_value = {
            "path_found": False,
            "path_length": 0,
            "paths": []
        }

        result = self.graph_store.find_path("Python", "QuantumPhysics")

        assert result["path_found"] is False
        assert result["path_length"] == 0
        assert len(result["paths"]) == 0

    def test_find_path_validation_empty_start_node(self):
        """Test ValidationError for empty start node."""
        with pytest.raises(ValidationError, match="start_node cannot be empty"):
            self.graph_store.find_path("", "Django")

    def test_find_path_validation_empty_end_node(self):
        """Test ValidationError for empty end node."""
        with pytest.raises(ValidationError, match="end_node cannot be empty"):
            self.graph_store.find_path("Python", "")

    def test_find_path_validation_max_depth_too_high(self):
        """Test ValidationError for max_depth > 10."""
        with pytest.raises(ValidationError, match="max_depth must be between 1 and 10"):
            self.graph_store.find_path("Python", "Django", max_depth=11)

    def test_find_path_validation_max_depth_too_low(self):
        """Test ValidationError for max_depth < 1."""
        with pytest.raises(ValidationError, match="max_depth must be between 1 and 10"):
            self.graph_store.find_path("Python", "Django", max_depth=0)

    @patch('cognitive_memory.store.db_find_path')
    def test_find_path_storage_error_wrapping(self, mock_find_path):
        """Test that database exceptions are wrapped as StorageError."""
        mock_find_path.side_effect = Exception("Pathfinding timeout")

        with pytest.raises(StorageError, match="Failed to find path"):
            self.graph_store.find_path("Python", "Django")

    # =========================================================================
    # Test get_neighbors() legacy method
    # =========================================================================

    @patch('cognitive_memory.store.db_query_neighbors')
    @patch('cognitive_memory.store.get_node_by_name')
    def test_get_neighbors_legacy_method_calls_query_neighbors(self, mock_query, mock_get_node):
        """Test that legacy get_neighbors method calls query_neighbors."""
        mock_get_node.return_value = {"id": "node-uuid-123"}
        mock_query.return_value = [{"node_id": "neighbor-1", "name": "Django"}]

        # Call legacy method
        result = self.graph_store.get_neighbors("Python", depth=2, relation_type="USES")

        # Verify it works the same as query_neighbors
        assert len(result) == 1
        assert result[0]["name"] == "Django"
        mock_query.assert_called_once_with(
            node_id="node-uuid-123",
            relation_type="USES",
            max_depth=2
        )

    # =========================================================================
    # Test connection management
    # =========================================================================

    def test_context_manager_connection_setup(self):
        """Test that context manager properly sets up connection."""
        with patch.object(self.graph_store._connection_manager, 'initialize') as mock_init:
            with self.graph_store as gs:
                assert gs._is_connected is True
                mock_init.assert_called_once()

    def test_context_manager_cleanup(self):
        """Test that context manager properly cleans up connection."""
        with patch.object(self.graph_store._connection_manager, 'close') as mock_close:
            with self.graph_store as gs:
                pass
            mock_close.assert_called_once()
            assert self.graph_store._is_connected is False

    # =========================================================================
    # Integration-style tests
    # =========================================================================

    @patch('cognitive_memory.store.db_add_node')
    @patch('cognitive_memory.store.db_add_edge')
    def test_graph_workflow_create_node_and_edge(self, mock_add_edge, mock_add_node):
        """Test creating a node and then an edge (workflow integration)."""
        # Setup mocks
        mock_add_node.return_value = {"node_id": "python-uuid"}
        mock_add_edge.return_value = {"edge_id": "edge-uuid"}

        # Execute workflow
        node_id = self.graph_store.add_node("Python", "Technology")
        edge_id = self.graph_store.add_edge("Python", "Django", "USES", 0.9)

        # Verify
        assert node_id == int("python-uuid")
        assert edge_id == int("edge-uuid")
        mock_add_node.assert_called_once()
        mock_add_edge.assert_called_once()

    @patch('cognitive_memory.store.db_add_node')
    @patch('cognitive_memory.store.db_add_edge')
    @patch('cognitive_memory.store.get_node_by_name')
    @patch('cognitive_memory.store.db_query_neighbors')
    def test_full_graph_workflow(self, mock_query, mock_get_node, mock_add_edge, mock_add_node):
        """Test complete workflow: create nodes, create edges, query neighbors."""
        # Setup mocks
        mock_add_node.side_effect = [
            {"node_id": "python-uuid"},
            {"node_id": "django-uuid"}
        ]
        mock_add_edge.return_value = {"edge_id": "edge-uuid"}
        mock_get_node.return_value = {"id": "python-uuid", "name": "Python"}
        mock_query.return_value = [
            {"node_id": "django-uuid", "name": "Django", "distance": 1}
        ]

        # Execute workflow
        python_id = self.graph_store.add_node("Python", "Technology")
        django_id = self.graph_store.add_node("Django", "Framework")
        edge_id = self.graph_store.add_edge("Python", "Django", "USES", 0.8)
        neighbors = self.graph_store.query_neighbors("Python", depth=1)

        # Verify workflow
        assert python_id == int("python-uuid")
        assert django_id == int("django-uuid")
        assert edge_id == int("edge-uuid")
        assert len(neighbors) == 1
        assert neighbors[0]["name"] == "Django"