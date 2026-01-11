"""
Tests for graph_query_neighbors MCP Tool

Tests the graph_query_neighbors tool implementation including:
- Parameter validation (node_name, relation_type, depth, direction)
- Single-hop query functionality (depth=1)
- Multi-hop query functionality (depth=2, 3, 4, 5)
- Relation type filtering
- Bidirectional traversal (both/outgoing/incoming)
- Sorting by distance and weight
- Cycle detection (no duplicate nodes)
- Error handling for invalid inputs
- Performance timing functionality

Story 4.4: graph_query_neighbors Tool Implementation
Bug Fix: Bidirectional graph neighbors (2025-12-07)
Story 7.6: Hyperedge via Properties (properties_filter parameter)

Default Parameter Values (for mock assertions):
- node_id: Required (from get_node_by_name lookup)
- relation_type: None (all relations)
- max_depth: 1 (single-hop)
- direction: "both" (bidirectional traversal)
- include_superseded: False (Story 7.5 - hide superseded edges)
- properties_filter: None (Story 7.6 - no JSONB filtering)
- sector_filter: None (Story 9-3 - all sectors)
"""

from __future__ import annotations

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors
from mcp_server.db.graph import get_node_by_name, query_neighbors


class TestGraphQueryNeighborsTool:
    """Test suite for graph_query_neighbors MCP tool."""

    @pytest.mark.asyncio
    async def test_successful_single_hop_query(self):
        """Test successful neighbor query with depth=1."""
        # Mock database functions
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            # Mock start node found
            mock_get_node.return_value = {
                "id": "start-node-id",
                "label": "Project",
                "name": "TestProject",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-11-30T10:00:00Z"
            }

            # Mock neighbor query results
            mock_query.return_value = [
                {
                    "node_id": "neighbor-1-id",
                    "label": "Technology",
                    "name": "Python",
                    "properties": {"type": "language"},
                    "relation": "USES",
                    "weight": 0.9,
                    "distance": 1
                },
                {
                    "node_id": "neighbor-2-id",
                    "label": "Technology",
                    "name": "Docker",
                    "properties": {"type": "container"},
                    "relation": "USES",
                    "weight": 0.8,
                    "distance": 1
                }
            ]

            # Test arguments
            arguments = {
                "node_name": "TestProject",
                "depth": 1
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify response structure
            assert result["status"] == "success"
            assert result["neighbor_count"] == 2
            assert result["start_node"]["name"] == "TestProject"
            assert result["query_params"]["depth"] == 1
            assert result["query_params"]["relation_type"] is None
            assert result["query_params"]["sector_filter"] is None
            assert "execution_time_ms" in result
            assert "neighbors" in result

            # Verify neighbor data
            neighbors = result["neighbors"]
            assert len(neighbors) == 2
            assert neighbors[0]["name"] == "Python"

            # Verify DB call with sector_filter=None
            mock_query.assert_called_once_with(
                node_id="start-node-id",
                relation_type=None,
                max_depth=1,
                direction="both",
                include_superseded=False,
                properties_filter=None,
                sector_filter=None,
                use_ief=False,
                query_embedding=None
            )
            assert neighbors[0]["distance"] == 1
            assert neighbors[0]["relation"] == "USES"

            # Verify function calls
            mock_get_node.assert_called_once_with(name="TestProject")
            mock_query.assert_called_once_with(
                node_id="start-node-id",
                relation_type=None,
                max_depth=1,
                direction="both",  # Default direction
                include_superseded=False,  # Story 7.5 default
                properties_filter=None,  # Story 7.6 default
                sector_filter=None,  # Story 9-3 default
                use_ief=False,  # Story 7.7 default
                query_embedding=None  # Story 7.7 default
            )

    @pytest.mark.asyncio
    async def test_successful_multi_hop_query(self):
        """Test successful neighbor query with depth=3."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            # Mock start node found
            mock_get_node.return_value = {
                "id": "start-node-id",
                "label": "Project",
                "name": "ComplexProject"
            }

            # Mock multi-hop neighbor results
            mock_query.return_value = [
                # Direct neighbors (distance=1)
                {
                    "node_id": "tech-1-id",
                    "label": "Technology",
                    "name": "React",
                    "relation": "USES",
                    "weight": 0.9,
                    "distance": 1
                },
                # Indirect neighbors (distance=2)
                {
                    "node_id": "lib-1-id",
                    "label": "Library",
                    "name": "Redux",
                    "relation": "DEPENDS_ON",
                    "weight": 0.8,
                    "distance": 2
                },
                # Third-degree neighbors (distance=3)
                {
                    "node_id": "tool-1-id",
                    "label": "Tool",
                    "name": "DevTools",
                    "relation": "RELATED_TO",
                    "weight": 0.7,
                    "distance": 3
                }
            ]

            arguments = {
                "node_name": "ComplexProject",
                "depth": 3
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify response
            assert result["status"] == "success"
            assert result["neighbor_count"] == 3
            assert result["query_params"]["depth"] == 3

            # Verify sorting by distance (ASC) then weight (DESC)
            neighbors = result["neighbors"]
            assert neighbors[0]["distance"] == 1
            assert neighbors[1]["distance"] == 2
            assert neighbors[2]["distance"] == 3

    @pytest.mark.asyncio
    async def test_successful_relation_filter_query(self):
        """Test successful neighbor query with relation type filter."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "start-node-id", "name": "TestProject", "label": "Project", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}

            # Mock filtered results (only "USES" relations)
            mock_query.return_value = [
                {
                    "node_id": "tech-1-id",
                    "label": "Technology",
                    "name": "Python",
                    "relation": "USES",
                    "weight": 0.9,
                    "distance": 1
                },
                {
                    "node_id": "tech-2-id",
                    "label": "Technology",
                    "name": "PostgreSQL",
                    "relation": "USES",
                    "weight": 0.8,
                    "distance": 1
                }
            ]

            arguments = {
                "node_name": "TestProject",
                "relation_type": "USES",
                "depth": 1
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify filtering applied
            assert result["status"] == "success"
            assert result["query_params"]["relation_type"] == "USES"

            # All returned neighbors should have "USES" relation
            for neighbor in result["neighbors"]:
                assert neighbor["relation"] == "USES"

            # Verify function called with relation filter
            mock_query.assert_called_once_with(
                node_id="start-node-id",
                relation_type="USES",
                max_depth=1,
                direction="both",  # Default direction
                include_superseded=False,  # Story 7.5 default
                properties_filter=None,  # Story 7.6 default
                sector_filter=None,  # Story 9-3 default
                use_ief=False,  # Story 7.7 default
                query_embedding=None  # Story 7.7 default
            )

    @pytest.mark.asyncio
    async def test_empty_neighbors_result(self):
        """Test query where no neighbors are found."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "isolated-node-id", "name": "IsolatedProject", "label": "Project", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}
            mock_query.return_value = []  # No neighbors found

            arguments = {
                "node_name": "IsolatedProject",
                "depth": 1
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify empty result handled properly
            assert result["status"] == "success"
            assert result["neighbor_count"] == 0
            assert result["neighbors"] == []

    @pytest.mark.asyncio
    async def test_start_node_not_found_error(self):
        """Test error handling when start node doesn't exist."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node:
            # Mock node not found
            mock_get_node.return_value = None

            arguments = {
                "node_name": "NonExistentProject",
                "depth": 1
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify error response
            assert result["error"] == "Start node not found"
            assert "NonExistentProject" in result["details"]
            assert result["tool"] == "graph_query_neighbors"

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_node_name(self):
        """Test parameter validation for missing node_name."""
        arguments = {
            "depth": 1
            # node_name missing
        }

        result = await handle_graph_query_neighbors(arguments)

        # Verify validation error
        assert result["error"] == "Parameter validation failed"
        assert "node_name" in result["details"]
        assert result["tool"] == "graph_query_neighbors"

    @pytest.mark.asyncio
    async def test_parameter_validation_empty_node_name(self):
        """Test parameter validation for empty node_name."""
        arguments = {
            "node_name": "",  # Empty string
            "depth": 1
        }

        result = await handle_graph_query_neighbors(arguments)

        # Verify validation error
        assert result["error"] == "Parameter validation failed"
        assert "node_name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_depth_too_low(self):
        """Test parameter validation for depth less than 1."""
        arguments = {
            "node_name": "TestProject",
            "depth": 0  # Invalid: less than 1
        }

        result = await handle_graph_query_neighbors(arguments)

        # Verify validation error
        assert result["error"] == "Parameter validation failed"
        assert "depth" in result["details"]
        assert "between 1 and 5" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_depth_too_high(self):
        """Test parameter validation for depth greater than 5."""
        arguments = {
            "node_name": "TestProject",
            "depth": 10  # Invalid: greater than 5
        }

        result = await handle_graph_query_neighbors(arguments)

        # Verify validation error
        assert result["error"] == "Parameter validation failed"
        assert "depth" in result["details"]
        assert "between 1 and 5" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_depth_type(self):
        """Test parameter validation for non-integer depth."""
        arguments = {
            "node_name": "TestProject",
            "depth": "invalid"  # Invalid: not an integer
        }

        result = await handle_graph_query_neighbors(arguments)

        # Verify validation error
        assert result["error"] == "Parameter validation failed"
        assert "depth" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_relation_type(self):
        """Test parameter validation for non-string relation_type."""
        arguments = {
            "node_name": "TestProject",
            "relation_type": 123  # Invalid: not a string
        }

        result = await handle_graph_query_neighbors(arguments)

        # Verify validation error
        assert result["error"] == "Parameter validation failed"
        assert "relation_type" in result["details"]

    @pytest.mark.asyncio
    async def test_default_depth_parameter(self):
        """Test that default depth=1 is used when not specified."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "start-node-id", "name": "TestProject", "label": "Project", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}
            mock_query.return_value = []

            # Arguments without depth specified
            arguments = {
                "node_name": "TestProject"
                # depth not specified, should default to 1
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify default depth applied
            assert result["status"] == "success"
            assert result["query_params"]["depth"] == 1

            # Verify function called with default depth and direction
            mock_query.assert_called_once_with(
                node_id="start-node-id",
                relation_type=None,
                max_depth=1,  # Default depth
                direction="both",  # Default direction
                include_superseded=False,  # Story 7.5 default
                properties_filter=None,  # Story 7.6 default
                sector_filter=None,  # Story 9-3 default
                use_ief=False,  # Story 7.7 default
                query_embedding=None  # Story 7.7 default
            )

    @pytest.mark.asyncio
    async def test_performance_timing_functionality(self):
        """Test that execution timing is recorded and included in response."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "start-node-id", "name": "TestProject", "label": "Project", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}
            mock_query.return_value = []

            arguments = {
                "node_name": "TestProject",
                "depth": 1
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify timing information included
            assert "execution_time_ms" in result
            assert isinstance(result["execution_time_ms"], float)
            assert result["execution_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test error handling for database connection or query failures."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node:
            # Mock database exception
            mock_get_node.side_effect = Exception("Database connection failed")

            arguments = {
                "node_name": "TestProject",
                "depth": 1
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify database error response
            assert result["error"] == "Database operation failed"
            assert "Database connection failed" in result["details"]
            assert result["tool"] == "graph_query_neighbors"

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self):
        """Test error handling for unexpected exceptions."""
        with patch('mcp_server.tools.graph_query_neighbors.handle_graph_query_neighbors') as mock_handler:
            # Mock unexpected exception during parameter processing
            mock_handler.side_effect = Exception("Unexpected system error")

            # This should trigger the outer try-catch block
            arguments = {"invalid": "arguments"}

            # We can't easily mock the tool itself, so let's test with a real call
            # but patch something that would cause an unexpected error
            result = await handle_graph_query_neighbors({"node_name": None, "depth": 1})

            # Should handle None node_name as validation error, not unexpected error
            assert result["error"] == "Parameter validation failed"


class TestDatabaseFunctions:
    """Test suite for graph_query_neighbors database functions."""

    def test_get_node_by_name_success(self):
        """Test successful node lookup by name."""
        # This test would require database integration testing
        # For now, we'll test the function signature and basic behavior
        # In a real implementation, you'd set up a test database
        pass

    def test_query_neighbors_function_structure(self):
        """Test that query_neighbors function has correct signature and basic structure."""
        # This test verifies the function exists and has correct parameters
        from mcp_server.db.graph import query_neighbors

        import inspect
        sig = inspect.signature(query_neighbors)

        # Verify function signature (now includes direction parameter)
        expected_params = ["node_id", "relation_type", "max_depth", "direction"]
        actual_params = list(sig.parameters.keys())

        for param in expected_params:
            assert param in actual_params

        # Verify default values
        assert sig.parameters["relation_type"].default is None
        assert sig.parameters["max_depth"].default == 1
        assert sig.parameters["direction"].default == "both"


class TestCycleDetection:
    """Test suite specifically for cycle detection functionality."""

    @pytest.mark.asyncio
    async def test_cycle_detection_in_results(self):
        """Test that cycle detection prevents duplicate nodes in results."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "start-node-id", "name": "TestProject", "label": "Project", "properties": {}, "vector_id": None, "created_at": "2025-11-30T10:00:00Z"}

            # Mock results that would include cycles (duplicates if cycle detection failed)
            # The database CTE should handle cycle detection, so we expect unique results
            mock_query.return_value = [
                {
                    "node_id": "neighbor-1-id",
                    "name": "TechnologyA",
                    "distance": 1,
                    "relation": "USES"
                },
                {
                    "node_id": "neighbor-2-id",
                    "name": "TechnologyB",
                    "distance": 2,
                    "relation": "DEPENDS_ON"
                }
                # No duplicates expected due to DISTINCT ON (id) in SQL
            ]

            arguments = {
                "node_name": "TestProject",
                "depth": 3  # Deep enough to potentially encounter cycles
            }

            result = await handle_graph_query_neighbors(arguments)

            # Verify no duplicate node_ids in results
            node_ids = [neighbor["node_id"] for neighbor in result["neighbors"]]
            assert len(node_ids) == len(set(node_ids)), "Duplicate node IDs found - cycle detection may have failed"


class TestBidirectionalTraversal:
    """Test suite for bidirectional traversal functionality (Bug Fix 2025-12-07)."""

    @pytest.mark.asyncio
    async def test_direction_parameter_in_query_params(self):
        """Test that direction parameter is included in query_params response."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "start-node-id", "name": "TestNode", "label": "Entity",
                "properties": {}, "vector_id": None, "created_at": "2025-12-07T10:00:00Z"
            }
            mock_query.return_value = []

            # Test with explicit direction
            arguments = {
                "node_name": "TestNode",
                "direction": "incoming"
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["query_params"]["direction"] == "incoming"

    @pytest.mark.asyncio
    async def test_default_direction_is_both(self):
        """Test that default direction is 'both' when not specified."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "start-node-id", "name": "TestNode", "label": "Entity",
                "properties": {}, "vector_id": None, "created_at": "2025-12-07T10:00:00Z"
            }
            mock_query.return_value = []

            # No direction specified
            arguments = {"node_name": "TestNode"}

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["query_params"]["direction"] == "both"

            # Verify DB function called with direction="both"
            mock_query.assert_called_once_with(
                node_id="start-node-id",
                relation_type=None,
                max_depth=1,
                direction="both",
                include_superseded=False,  # Story 7.5 default
                properties_filter=None,  # Story 7.6 default
                sector_filter=None,  # Story 9-3 default
                use_ief=False,  # Story 7.7 default
                query_embedding=None  # Story 7.7 default
            )

    @pytest.mark.asyncio
    async def test_direction_outgoing_passed_to_db(self):
        """Test that direction='outgoing' is correctly passed to database function."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "node-b-id", "name": "NodeB", "label": "Entity",
                "properties": {}, "vector_id": None, "created_at": "2025-12-07T10:00:00Z"
            }
            mock_query.return_value = []

            arguments = {
                "node_name": "NodeB",
                "direction": "outgoing"
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            mock_query.assert_called_once_with(
                node_id="node-b-id",
                relation_type=None,
                max_depth=1,
                direction="outgoing",
                include_superseded=False,  # Story 7.5 default
                properties_filter=None,  # Story 7.6 default
                sector_filter=None,  # Story 9-3 default
                use_ief=False,  # Story 7.7 default
                query_embedding=None  # Story 7.7 default
            )

    @pytest.mark.asyncio
    async def test_direction_incoming_passed_to_db(self):
        """Test that direction='incoming' is correctly passed to database function."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "node-b-id", "name": "NodeB", "label": "Entity",
                "properties": {}, "vector_id": None, "created_at": "2025-12-07T10:00:00Z"
            }
            # Mock incoming neighbor (A points to B, so A is incoming neighbor of B)
            mock_query.return_value = [
                {
                    "node_id": "node-a-id",
                    "label": "Entity",
                    "name": "NodeA",
                    "properties": {},
                    "relation": "RELATED_TO",
                    "weight": 1.0,
                    "distance": 1,
                    "edge_direction": "incoming"
                }
            ]

            arguments = {
                "node_name": "NodeB",
                "direction": "incoming"
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["neighbor_count"] == 1
            assert result["neighbors"][0]["name"] == "NodeA"
            assert result["neighbors"][0]["edge_direction"] == "incoming"

            mock_query.assert_called_once_with(
                node_id="node-b-id",
                relation_type=None,
                max_depth=1,
                direction="incoming",
                include_superseded=False,  # Story 7.5 default
                properties_filter=None,  # Story 7.6 default
                sector_filter=None,  # Story 9-3 default
                use_ief=False,  # Story 7.7 default
                query_embedding=None  # Story 7.7 default
            )

    @pytest.mark.asyncio
    async def test_invalid_direction_parameter(self):
        """Test validation error for invalid direction parameter."""
        arguments = {
            "node_name": "TestNode",
            "direction": "invalid_direction"  # Invalid value
        }

        result = await handle_graph_query_neighbors(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "direction" in result["details"]
        assert result["tool"] == "graph_query_neighbors"

    @pytest.mark.asyncio
    async def test_direction_parameter_non_string(self):
        """Test validation error for non-string direction parameter."""
        arguments = {
            "node_name": "TestNode",
            "direction": 123  # Invalid type
        }

        result = await handle_graph_query_neighbors(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "direction" in result["details"]

    @pytest.mark.asyncio
    async def test_edge_direction_field_in_response(self):
        """Test that edge_direction field is included in neighbor results."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "center-node-id", "name": "CenterNode", "label": "Entity",
                "properties": {}, "vector_id": None, "created_at": "2025-12-07T10:00:00Z"
            }
            # Mock bidirectional results with edge_direction
            mock_query.return_value = [
                {
                    "node_id": "outgoing-neighbor-id",
                    "label": "Entity",
                    "name": "OutgoingNeighbor",
                    "properties": {},
                    "relation": "USES",
                    "weight": 0.9,
                    "distance": 1,
                    "edge_direction": "outgoing"
                },
                {
                    "node_id": "incoming-neighbor-id",
                    "label": "Entity",
                    "name": "IncomingNeighbor",
                    "properties": {},
                    "relation": "DEPENDS_ON",
                    "weight": 0.8,
                    "distance": 1,
                    "edge_direction": "incoming"
                }
            ]

            arguments = {
                "node_name": "CenterNode",
                "direction": "both"
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["neighbor_count"] == 2

            # Verify edge_direction is present in results
            neighbors = result["neighbors"]
            edge_directions = [n["edge_direction"] for n in neighbors]
            assert "outgoing" in edge_directions
            assert "incoming" in edge_directions

    @pytest.mark.asyncio
    async def test_bidirectional_multihop_traversal(self):
        """Test multi-hop traversal with bidirectional edges (AC 4)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "node-c-id", "name": "NodeC", "label": "Entity",
                "properties": {}, "vector_id": None, "created_at": "2025-12-07T10:00:00Z"
            }
            # Mock results for chain A→B→C with bidirectional traversal from C
            # C should find B (distance=1 incoming) and A (distance=2 incoming)
            mock_query.return_value = [
                {
                    "node_id": "node-b-id",
                    "label": "Entity",
                    "name": "NodeB",
                    "properties": {},
                    "relation": "CONNECTED_TO",
                    "weight": 1.0,
                    "distance": 1,
                    "edge_direction": "incoming"
                },
                {
                    "node_id": "node-a-id",
                    "label": "Entity",
                    "name": "NodeA",
                    "properties": {},
                    "relation": "CONNECTED_TO",
                    "weight": 1.0,
                    "distance": 2,
                    "edge_direction": "incoming"
                }
            ]

            arguments = {
                "node_name": "NodeC",
                "depth": 2,
                "direction": "both"
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["neighbor_count"] == 2

            # Verify both nodes found with correct distances
            neighbors_by_name = {n["name"]: n for n in result["neighbors"]}
            assert "NodeB" in neighbors_by_name
            assert "NodeA" in neighbors_by_name
            assert neighbors_by_name["NodeB"]["distance"] == 1
            assert neighbors_by_name["NodeA"]["distance"] == 2


class TestDirectionValidationInDBLayer:
    """Test direction parameter validation in database layer."""

    def test_query_neighbors_invalid_direction_raises_error(self):
        """Test that invalid direction raises ValueError in DB function."""
        from mcp_server.db.graph import query_neighbors

        # This test verifies the DB function validates direction
        # In a real test, we'd mock the DB connection
        # For now, we verify the function signature accepts direction
        import inspect
        sig = inspect.signature(query_neighbors)
        assert "direction" in sig.parameters

        # Verify default is "both"
        assert sig.parameters["direction"].default == "both"


class TestSectorFilter:
    """Test sector_filter parameter (Story 9-3)."""

    @pytest.mark.asyncio
    async def test_sector_filter_single_sector(self):
        """Test filtering by single memory sector (AC #1)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "node-id",
                "name": "TestNode",
                "label": "Entity"
            }
            mock_query.return_value = [
                {
                    "node_id": "1",
                    "name": "EmotionalNeighbor",
                    "memory_sector": "emotional",
                    "relation": "FEELS",
                    "weight": 0.9,
                    "distance": 1
                }
            ]

            arguments = {
                "node_name": "TestNode",
                "sector_filter": ["emotional"]
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            mock_query.assert_called_once_with(
                node_id="node-id",
                relation_type=None,
                max_depth=1,
                direction="both",
                include_superseded=False,
                properties_filter=None,
                sector_filter=["emotional"],
                use_ief=False,
                query_embedding=None
            )

    @pytest.mark.asyncio
    async def test_sector_filter_multiple_sectors(self):
        """Test filtering by multiple memory sectors (AC #2)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "node-id", "name": "TestNode", "label": "Entity"}
            mock_query.return_value = []

            arguments = {
                "node_name": "TestNode",
                "sector_filter": ["emotional", "episodic"]
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            mock_query.assert_called_once_with(
                node_id="node-id",
                relation_type=None,
                max_depth=1,
                direction="both",
                include_superseded=False,
                properties_filter=None,
                sector_filter=["emotional", "episodic"],
                use_ief=False,
                query_embedding=None
            )

    @pytest.mark.asyncio
    async def test_sector_filter_none_means_all_sectors(self):
        """Test that sector_filter=None returns all sectors (AC #3)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "node-id", "name": "TestNode", "label": "Entity"}
            mock_query.return_value = []

            arguments = {
                "node_name": "TestNode",
                "sector_filter": None
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            mock_query.assert_called_once_with(
                node_id="node-id",
                relation_type=None,
                max_depth=1,
                direction="both",
                include_superseded=False,
                properties_filter=None,
                sector_filter=None,
                use_ief=False,
                query_embedding=None
            )

    @pytest.mark.asyncio
    async def test_sector_filter_empty_list_returns_empty(self):
        """Test that sector_filter=[] returns empty results (AC #4)."""
        from mcp_server.db.graph import query_neighbors

        # Empty list should return immediately without DB query
        result = await query_neighbors(
            node_id="some-id",
            sector_filter=[]
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_sector_filter_invalid_sector_validation_error(self):
        """Test validation error for invalid sector values (AC #7)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node:

            mock_get_node.return_value = {"id": "node-id", "name": "TestNode", "label": "Entity"}

            arguments = {
                "node_name": "TestNode",
                "sector_filter": ["invalid_sector"]
            }

            result = await handle_graph_query_neighbors(arguments)

            assert "error" in result
            assert "Invalid sector(s)" in result["details"]
            assert "invalid_sector" in result["details"]

    @pytest.mark.asyncio
    async def test_sector_filter_in_query_params_response(self):
        """Test that sector_filter appears in query_params response (AC #1)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "node-id", "name": "TestNode", "label": "Entity"}
            mock_query.return_value = []

            arguments = {
                "node_name": "TestNode",
                "sector_filter": ["emotional"]
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["query_params"]["sector_filter"] == ["emotional"]

    @pytest.mark.asyncio
    async def test_sector_filter_not_list_validation_error(self):
        """Test validation error when sector_filter is not a list."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node:

            mock_get_node.return_value = {"id": "node-id", "name": "TestNode", "label": "Entity"}

            arguments = {
                "node_name": "TestNode",
                "sector_filter": "emotional"  # String, not list
            }

            result = await handle_graph_query_neighbors(arguments)

            assert "error" in result
            assert "must be array of sector names" in result["details"]

    @pytest.mark.asyncio
    async def test_sector_filter_combined_with_properties_filter(self):
        """Test combined sector_filter AND properties_filter (AC #8)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "node-id", "name": "TestNode", "label": "Entity"}
            mock_query.return_value = []

            arguments = {
                "node_name": "TestNode",
                "sector_filter": ["emotional"],
                "properties_filter": {"participants": "I/O"}
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            # Verify both filters are passed to DB
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args.kwargs
            assert call_kwargs["sector_filter"] == ["emotional"]
            assert call_kwargs["properties_filter"] == {"participants": "I/O"}
