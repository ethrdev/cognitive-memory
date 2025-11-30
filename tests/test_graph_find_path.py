"""
Tests for graph_find_path tool implementation.

Tests BFS-based pathfinding functionality including direct paths, multi-hop paths,
same-node queries, no path scenarios, error handling, and performance requirements.

Story 4.5: graph_find_path Tool Implementation
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from mcp_server.db.graph import find_path, get_node_by_name
from mcp_server.tools.graph_find_path import handle_graph_find_path


@pytest.fixture
def mock_start_node():
    """Mock start node for testing."""
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "label": "Project",
        "name": "TestProject",
        "properties": {"status": "active"},
        "vector_id": None,
        "created_at": "2025-11-30T10:00:00Z",
    }


@pytest.fixture
def mock_end_node():
    """Mock end node for testing."""
    return {
        "id": "22222222-2222-2222-2222-222222222222",
        "label": "Technology",
        "name": "Python",
        "properties": {"type": "language"},
        "vector_id": None,
        "created_at": "2025-11-30T10:00:00Z",
    }


@pytest.fixture
def mock_intermediate_node():
    """Mock intermediate node for testing."""
    return {
        "id": "33333333-3333-3333-3333-333333333333",
        "label": "Problem",
        "name": "Performance",
        "properties": {"severity": "high"},
        "vector_id": None,
        "created_at": "2025-11-30T10:00:00Z",
    }


class TestGraphFindPath:
    """Test suite for graph_find_path tool functionality."""

    @patch("mcp_server.tools.graph_find_path.find_path")
    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_direct_path(self, mock_get_node, mock_find_path, mock_start_node, mock_end_node):
        """Test AC-4.5.1: Direct path (depth=1) between two nodes."""
        # Arrange
        mock_get_node.side_effect = [mock_start_node, mock_end_node]
        mock_find_path.return_value = {
            "path_found": True,
            "path_length": 1,
            "paths": [{
                "nodes": [mock_start_node, mock_end_node],
                "edges": [{
                    "edge_id": "edge-1",
                    "relation": "USES",
                    "weight": 1.0,
                }],
                "total_weight": 1.0,
            }],
        }

        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert result["status"] == "success"
        assert result["path_found"] is True
        assert result["path_length"] == 1
        assert len(result["paths"]) == 1
        assert len(result["paths"][0]["nodes"]) == 2
        assert len(result["paths"][0]["edges"]) == 1
        assert result["paths"][0]["total_weight"] == 1.0

    @patch("mcp_server.tools.graph_find_path.find_path")
    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_multi_hop_path(self, mock_get_node, mock_find_path,
                                                         mock_start_node, mock_end_node, mock_intermediate_node):
        """Test AC-4.5.1: Multi-hop path (depth=2-3) between nodes."""
        # Arrange
        mock_get_node.side_effect = [mock_start_node, mock_end_node]
        mock_find_path.return_value = {
            "path_found": True,
            "path_length": 2,
            "paths": [{
                "nodes": [mock_start_node, mock_intermediate_node, mock_end_node],
                "edges": [
                    {"edge_id": "edge-1", "relation": "HAS", "weight": 1.0},
                    {"edge_id": "edge-2", "relation": "SOLVED_BY", "weight": 0.8},
                ],
                "total_weight": 1.8,
            }],
        }

        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert result["status"] == "success"
        assert result["path_found"] is True
        assert result["path_length"] == 2
        assert len(result["paths"][0]["nodes"]) == 3
        assert len(result["paths"][0]["edges"]) == 2
        assert result["paths"][0]["total_weight"] == 1.8

    @patch("mcp_server.tools.graph_find_path.find_path")
    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_no_path_found(self, mock_get_node, mock_find_path,
                                                       mock_start_node, mock_end_node):
        """Test AC-4.5.1: No path found between disconnected nodes."""
        # Arrange
        mock_get_node.side_effect = [mock_start_node, mock_end_node]
        mock_find_path.return_value = {
            "path_found": False,
            "path_length": 0,
            "paths": [],
        }

        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert result["status"] == "success"
        assert result["path_found"] is False
        assert result["path_length"] == 0
        assert len(result["paths"]) == 0

    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_same_node_query(self, mock_get_node, mock_start_node):
        """Test AC-4.5.5: Same-node query returns special response."""
        # Arrange
        mock_get_node.return_value = mock_start_node

        arguments = {
            "start_node": "TestProject",
            "end_node": "TestProject",  # Same node
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert result["status"] == "success"
        assert result["path_found"] is True
        assert result["path_length"] == 0
        assert len(result["paths"]) == 1
        assert len(result["paths"][0]["nodes"]) == 1  # Only one node
        assert len(result["paths"][0]["edges"]) == 0  # No edges
        assert result["paths"][0]["total_weight"] == 0.0

    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_start_node_not_found(self, mock_get_node):
        """Test AC-4.5.4: Error when start node not found."""
        # Arrange
        mock_get_node.return_value = None  # Node not found

        arguments = {
            "start_node": "NonExistentProject",
            "end_node": "Python",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert "error" in result
        assert result["error_type"] == "start_node_not_found"
        assert "NonExistentProject" in result["details"]

    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_end_node_not_found(self, mock_get_node, mock_start_node):
        """Test AC-4.5.4: Error when end node not found."""
        # Arrange
        mock_get_node.side_effect = [mock_start_node, None]  # End node not found

        arguments = {
            "start_node": "TestProject",
            "end_node": "NonExistentTech",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert "error" in result
        assert result["error_type"] == "end_node_not_found"
        assert "NonExistentTech" in result["details"]

    async def test_handle_graph_find_path_invalid_start_node_parameter(self):
        """Test AC-4.5.4: Error with invalid start_node parameter."""
        # Arrange
        arguments = {
            "start_node": "",  # Empty string
            "end_node": "Python",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert "error" in result
        assert result["error_type"] == "invalid_parameters"
        assert "start_node" in result["details"]

    async def test_handle_graph_find_path_invalid_end_node_parameter(self):
        """Test AC-4.5.4: Error with invalid end_node parameter."""
        # Arrange
        arguments = {
            "start_node": "TestProject",
            "end_node": None,  # None value
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert "error" in result
        assert result["error_type"] == "invalid_parameters"
        assert "end_node" in result["details"]

    async def test_handle_graph_find_path_invalid_depth_too_low(self):
        """Test AC-4.5.4: Error with depth parameter too low."""
        # Arrange
        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            "max_depth": 0,  # Below minimum
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert "error" in result
        assert result["error_type"] == "invalid_parameters"
        assert "max_depth" in result["details"]

    async def test_handle_graph_find_path_invalid_depth_too_high(self):
        """Test AC-4.5.4: Error with depth parameter too high."""
        # Arrange
        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            "max_depth": 15,  # Above maximum
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert "error" in result
        assert result["error_type"] == "invalid_parameters"
        assert "max_depth" in result["details"]

    async def test_handle_graph_find_path_default_depth_parameter(self):
        """Test AC-4.5.3: Default max_depth parameter is 5."""
        # Arrange
        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            # max_depth not provided, should default to 5
        }

        # Mock the database operations
        with patch("mcp_server.tools.graph_find_path.get_node_by_name") as mock_get_node, \
             patch("mcp_server.tools.graph_find_path.find_path") as mock_find_path:

            mock_start_node = {
                "id": "start-uuid", "label": "Project", "name": "TestProject",
                "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"
            }
            mock_end_node = {
                "id": "end-uuid", "label": "Technology", "name": "Python",
                "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"
            }
            mock_get_node.side_effect = [mock_start_node, mock_end_node]
            mock_find_path.return_value = {"path_found": False, "path_length": 0, "paths": []}

            # Act
            result = await handle_graph_find_path(arguments)

            # Assert
            assert result["query_params"]["max_depth"] == 5
            mock_find_path.assert_called_once_with(
                start_node_name="TestProject",
                end_node_name="Python",
                max_depth=5
            )

    @patch("mcp_server.tools.graph_find_path.find_path")
    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_timeout_error(self, mock_get_node, mock_find_path,
                                                      mock_start_node, mock_end_node):
        """Test AC-4.5.4: Timeout error handling."""
        # Arrange
        mock_get_node.side_effect = [mock_start_node, mock_end_node]
        mock_find_path.return_value = {
            "error_type": "timeout",
            "path_found": False,
            "path_length": 0,
            "paths": [],
        }

        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert "error" in result
        assert result["error_type"] == "timeout"
        assert "timeout" in result["details"].lower()

    @patch("mcp_server.tools.graph_find_path.find_path")
    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_multiple_paths(self, mock_get_node, mock_find_path,
                                                       mock_start_node, mock_end_node):
        """Test AC-4.5.3: Multiple paths returned (max 10)."""
        # Arrange
        mock_get_node.side_effect = [mock_start_node, mock_end_node]

        # Create 3 paths of equal length
        paths = []
        for i in range(3):
            paths.append({
                "nodes": [mock_start_node, mock_end_node],
                "edges": [{"edge_id": f"edge-{i}", "relation": "CONNECTS", "weight": 1.0}],
                "total_weight": 1.0,
            })

        mock_find_path.return_value = {
            "path_found": True,
            "path_length": 1,
            "paths": paths,
        }

        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert
        assert result["status"] == "success"
        assert result["path_found"] is True
        assert len(result["paths"]) == 3  # All 3 paths returned
        assert result["path_length"] == 1

    @patch("mcp_server.tools.graph_find_path.find_path")
    @patch("mcp_server.tools.graph_find_path.get_node_by_name")
    async def test_handle_graph_find_path_response_format(self, mock_get_node, mock_find_path,
                                                        mock_start_node, mock_end_node):
        """Test AC-4.5.2: Complete response format validation."""
        # Arrange
        mock_get_node.side_effect = [mock_start_node, mock_end_node]
        mock_find_path.return_value = {
            "path_found": True,
            "path_length": 1,
            "paths": [{
                "nodes": [
                    {
                        "node_id": mock_start_node["id"],
                        "label": mock_start_node["label"],
                        "name": mock_start_node["name"],
                        "properties": mock_start_node["properties"],
                    },
                    {
                        "node_id": mock_end_node["id"],
                        "label": mock_end_node["label"],
                        "name": mock_end_node["name"],
                        "properties": mock_end_node["properties"],
                    }
                ],
                "edges": [{"edge_id": "edge-1", "relation": "USES", "weight": 0.9}],
                "total_weight": 0.9,
            }],
        }

        arguments = {
            "start_node": "TestProject",
            "end_node": "Python",
            "max_depth": 3,
        }

        # Act
        result = await handle_graph_find_path(arguments)

        # Assert - Check complete response structure
        assert "status" in result
        assert "path_found" in result
        assert "path_length" in result
        assert "paths" in result
        assert "execution_time_ms" in result
        assert "query_params" in result

        # Check query parameters
        query_params = result["query_params"]
        assert "start_node" in query_params
        assert "end_node" in query_params
        assert "max_depth" in query_params
        assert query_params["start_node"] == "TestProject"
        assert query_params["end_node"] == "Python"
        assert query_params["max_depth"] == 3

        # Check path structure
        path = result["paths"][0]
        assert "nodes" in path
        assert "edges" in path
        assert "total_weight" in path

        # Check node structure
        node = path["nodes"][0]
        assert "node_id" in node
        assert "label" in node
        assert "name" in node
        assert "properties" in node

        # Check edge structure
        edge = path["edges"][0]
        assert "edge_id" in edge
        assert "relation" in edge
        assert "weight" in edge


class TestFindPathDatabaseFunction:
    """Test suite for find_path database function."""

    def test_find_path_database_function_basic(self):
        """Test find_path database function with basic scenario."""
        # Arrange - mock both get_node_by_name and get_connection
        mock_start_node = {"id": "start-uuid", "name": "Start", "label": "Project", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}
        mock_end_node = {"id": "end-uuid", "name": "End", "label": "Tech", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}

        # Create a proper mock cursor that behaves like DictCursor
        mock_cursor = MagicMock()

        # fetchall returns list of dict-like objects for path results
        path_result = MagicMock()
        path_result.__getitem__ = lambda self, key: {
            "node_path": ["start-uuid", "end-uuid"],
            "edge_path": ["edge-uuid"],
            "path_length": 1,
            "total_weight": 1.0,
        }[key]
        mock_cursor.fetchall.return_value = [path_result]

        # fetchone returns node and edge details - use simple dicts
        mock_node_result_1 = {"id": "start-uuid", "label": "Project", "name": "Start", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}
        mock_node_result_2 = {"id": "end-uuid", "label": "Tech", "name": "End", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}
        mock_edge_result = {"id": "edge-uuid", "source_id": "start-uuid", "target_id": "end-uuid", "relation": "USES", "weight": 1.0, "properties": {}}
        mock_cursor.fetchone.side_effect = [mock_node_result_1, mock_node_result_2, mock_edge_result]

        # Mock connection context manager
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("mcp_server.db.graph.get_node_by_name") as mock_get_node, \
             patch("mcp_server.db.graph.get_connection") as mock_get_conn:
            mock_get_node.side_effect = [mock_start_node, mock_end_node]
            mock_get_conn.return_value = mock_conn

            # Act
            result = find_path("Start", "End", 3)

        # Assert
        assert result["path_found"] is True
        assert result["path_length"] == 1
        assert len(result["paths"]) == 1
        assert len(result["paths"][0]["nodes"]) == 2
        assert len(result["paths"][0]["edges"]) == 1

    def test_find_path_no_results(self):
        """Test find_path when no paths found."""
        # Arrange
        mock_start_node = {"id": "start-uuid", "name": "Start", "label": "Project", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}
        mock_end_node = {"id": "end-uuid", "name": "End", "label": "Tech", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}

        # Create mock cursor that returns empty results
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # No paths found

        # Mock connection context manager
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("mcp_server.db.graph.get_node_by_name") as mock_get_node, \
             patch("mcp_server.db.graph.get_connection") as mock_get_conn:
            mock_get_node.side_effect = [mock_start_node, mock_end_node]
            mock_get_conn.return_value = mock_conn

            # Act
            result = find_path("Start", "End", 3)

        # Assert
        assert result["path_found"] is False
        assert result["path_length"] == 0
        assert len(result["paths"]) == 0

    def test_find_path_node_not_found(self):
        """Test find_path when start or end node not found."""
        with patch("mcp_server.db.graph.get_node_by_name") as mock_get_node:
            # End node not found
            mock_get_node.side_effect = [{"id": "start-uuid", "name": "Start"}, None]

            # Act
            result = find_path("Start", "NonExistent", 3)

        # Assert
        assert result["path_found"] is False
        assert result["path_length"] == 0
        assert len(result["paths"]) == 0

    def test_find_path_timeout_handling(self):
        """Test find_path timeout error handling."""
        # Arrange
        mock_start_node = {"id": "start-uuid", "name": "Start", "label": "Project", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}
        mock_end_node = {"id": "end-uuid", "name": "End", "label": "Tech", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}

        # Create mock cursor that raises timeout on execute
        mock_cursor = MagicMock()
        # First execute is SET LOCAL statement_timeout, then the CTE query fails
        mock_cursor.execute.side_effect = [None, Exception("statement timeout")]

        # Mock connection context manager
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor

        with patch("mcp_server.db.graph.get_node_by_name") as mock_get_node, \
             patch("mcp_server.db.graph.get_connection") as mock_get_conn:
            mock_get_node.side_effect = [mock_start_node, mock_end_node]
            mock_get_conn.return_value = mock_conn

            # Act
            result = find_path("Start", "End", 10)

        # Assert - should catch the exception and return timeout error
        assert result["error_type"] == "timeout"
        assert result["path_found"] is False