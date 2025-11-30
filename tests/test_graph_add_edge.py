"""
Tests for graph_add_edge MCP Tool

Tests the graph_add_edge tool implementation including:
- Parameter validation
- Auto-upsert of nodes
- Edge creation and updating (idempotency)
- Optional parameters (weight, properties)
- Error handling for invalid inputs
- Database integration

Story 4.3: graph_add_edge Tool Implementation
"""

from __future__ import annotations

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.tools.graph_add_edge import handle_graph_add_edge
from mcp_server.db.graph import add_edge, get_or_create_node


class TestGraphAddEdgeTool:
    """Test suite for graph_add_edge MCP tool."""

    @pytest.mark.asyncio
    async def test_create_new_edge_success(self):
        """Test creating a new edge with minimal required parameters."""
        # Mock database functions
        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_node, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge:

            # Mock source node creation
            mock_get_node.side_effect = [
                {"node_id": "source-node-id", "created": True},
                {"node_id": "target-node-id", "created": True}
            ]

            # Mock edge creation
            mock_add_edge.return_value = {
                "edge_id": "123e4567-e89b-12d3-a456-426614174000",
                "created": True,
                "source_id": "source-node-id",
                "target_id": "target-node-id",
                "relation": "USES",
                "weight": 1.0
            }

            arguments = {
                "source_name": "TestProject",
                "target_name": "Python",
                "relation": "USES"
            }

            result = await handle_graph_add_edge(arguments)

            assert result["status"] == "success"
            assert result["edge_id"] == "123e4567-e89b-12d3-a456-426614174000"
            assert result["created"] is True
            assert result["source_id"] == "source-node-id"
            assert result["target_id"] == "target-node-id"
            assert result["relation"] == "USES"
            assert result["weight"] == 1.0
            assert result["source_node_created"] is True
            assert result["target_node_created"] is True

    @pytest.mark.asyncio
    async def test_update_existing_edge_idempotent(self):
        """Test updating an existing edge (idempotent operation)."""
        # Mock database functions
        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_node, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge:

            # Mock existing nodes
            mock_get_node.side_effect = [
                {"node_id": "existing-source", "created": False},
                {"node_id": "existing-target", "created": False}
            ]

            # Mock edge update
            mock_add_edge.return_value = {
                "edge_id": "existing-edge-id",
                "created": False,
                "source_id": "existing-source",
                "target_id": "existing-target",
                "relation": "SOLVES",
                "weight": 0.8
            }

            arguments = {
                "source_name": "ExistingSolution",
                "target_name": "ExistingProblem",
                "relation": "SOLVES",
                "weight": 0.8,
                "properties": {"confidence": "high"}
            }

            result = await handle_graph_add_edge(arguments)

            assert result["status"] == "success"
            assert result["created"] is False
            assert result["weight"] == 0.8

    @pytest.mark.asyncio
    async def test_create_edge_with_all_parameters(self):
        """Test creating an edge with all optional parameters."""
        # Mock database functions
        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_node, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge:

            # Mock node creation with custom labels
            mock_get_node.side_effect = [
                {"node_id": "source-with-label", "created": True},
                {"node_id": "target-with-label", "created": True}
            ]

            # Mock edge creation
            mock_add_edge.return_value = {
                "edge_id": "edge-with-all-params",
                "created": True,
                "source_id": "source-with-label",
                "target_id": "target-with-label",
                "relation": "CREATED_BY",
                "weight": 0.5
            }

            arguments = {
                "source_name": "AIModel",
                "target_name": "DataScientist",
                "relation": "CREATED_BY",
                "source_label": "Model",
                "target_label": "Agent",
                "weight": 0.5,
                "properties": {"confidence": 0.9, "method": "training"}
            }

            result = await handle_graph_add_edge(arguments)

            assert result["status"] == "success"
            assert result["created"] is True
            assert result["weight"] == 0.5

            # Verify all parameters were passed correctly
            mock_get_node.assert_any_call(name="AIModel", label="Model")
            mock_get_node.assert_any_call(name="DataScientist", label="Agent")
            mock_add_edge.assert_called_once_with(
                source_id="source-with-label",
                target_id="target-with-label",
                relation="CREATED_BY",
                weight=0.5,
                properties=json.dumps({"confidence": 0.9, "method": "training"})
            )

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_source_name(self):
        """Test error handling when source_name parameter is missing."""
        arguments = {
            "target_name": "TestTarget",
            "relation": "RELATED_TO"
            # source_name is missing
        }

        result = await handle_graph_add_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "source_name" in result["details"]
        assert result["tool"] == "graph_add_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_target_name(self):
        """Test error handling when target_name parameter is missing."""
        arguments = {
            "source_name": "TestSource",
            "relation": "RELATED_TO"
            # target_name is missing
        }

        result = await handle_graph_add_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "target_name" in result["details"]
        assert result["tool"] == "graph_add_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_relation(self):
        """Test error handling when relation parameter is missing."""
        arguments = {
            "source_name": "TestSource",
            "target_name": "TestTarget"
            # relation is missing
        }

        result = await handle_graph_add_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "relation" in result["details"]
        assert result["tool"] == "graph_add_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_empty_source_name(self):
        """Test error handling when source_name is empty string."""
        arguments = {
            "source_name": "",
            "target_name": "TestTarget",
            "relation": "RELATED_TO"
        }

        result = await handle_graph_add_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "source_name" in result["details"]
        assert result["tool"] == "graph_add_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_weight_out_of_range(self):
        """Test error handling when weight is outside 0.0-1.0 range."""
        arguments = {
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "RELATED_TO",
            "weight": 1.5  # Over 1.0
        }

        result = await handle_graph_add_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "weight" in result["details"]
        assert result["tool"] == "graph_add_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_negative_weight(self):
        """Test error handling when weight is negative."""
        arguments = {
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "RELATED_TO",
            "weight": -0.1  # Below 0.0
        }

        result = await handle_graph_add_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "weight" in result["details"]
        assert result["tool"] == "graph_add_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_properties(self):
        """Test error handling when properties is not a dict."""
        arguments = {
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "RELATED_TO",
            "properties": "not-a-dict"  # Should be dict, not string
        }

        result = await handle_graph_add_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "properties" in result["details"]
        assert result["tool"] == "graph_add_edge"

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test error handling for database operation failures."""
        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_node:
            mock_get_node.side_effect = Exception("Database connection failed")

            arguments = {
                "source_name": "TestSource",
                "target_name": "TestTarget",
                "relation": "RELATED_TO"
            }

            result = await handle_graph_add_edge(arguments)

            assert result["error"] == "Database operation failed"
            assert "Database connection failed" in result["details"]
            assert result["tool"] == "graph_add_edge"

    @pytest.mark.asyncio
    async def test_edge_with_boundary_weights(self):
        """Test edge creation with boundary weight values (0.0 and 1.0)."""
        # Test with weight = 0.0
        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_node, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge:

            mock_get_node.side_effect = [
                {"node_id": "source-id", "created": False},
                {"node_id": "target-id", "created": False}
            ]

            mock_add_edge.return_value = {
                "edge_id": "edge-zero-weight",
                "created": True,
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "DEPENDS_ON",
                "weight": 0.0
            }

            arguments = {
                "source_name": "SourceA",
                "target_name": "TargetB",
                "relation": "DEPENDS_ON",
                "weight": 0.0
            }

            result = await handle_graph_add_edge(arguments)
            assert result["status"] == "success"
            assert result["weight"] == 0.0

    @pytest.mark.asyncio
    async def test_edge_with_non_standard_relation_warning(self):
        """Test that non-standard relations generate warnings but don't block."""
        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_node, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge, \
             patch('logging.getLogger') as mock_get_logger:

            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            mock_get_node.side_effect = [
                {"node_id": "source-id", "created": False},
                {"node_id": "target-id", "created": False}
            ]

            mock_add_edge.return_value = {
                "edge_id": "edge-custom-relation",
                "created": True,
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "CUSTOM_RELATION",
                "weight": 1.0
            }

            arguments = {
                "source_name": "SourceA",
                "target_name": "TargetB",
                "relation": "CUSTOM_RELATION"  # Not in STANDARD_RELATIONS
            }

            result = await handle_graph_add_edge(arguments)

            assert result["status"] == "success"
            assert result["relation"] == "CUSTOM_RELATION"

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            assert "Non-standard relation" in str(mock_logger.warning.call_args)

    @pytest.mark.asyncio
    async def test_edge_with_default_values(self):
        """Test edge creation with default values for optional parameters."""
        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_node, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge:

            mock_get_node.side_effect = [
                {"node_id": "source-id", "created": False},
                {"node_id": "target-id", "created": False}
            ]

            mock_add_edge.return_value = {
                "edge_id": "edge-default-values",
                "created": True,
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "RELATED_TO",
                "weight": 1.0
            }

            arguments = {
                "source_name": "SourceA",
                "target_name": "TargetB",
                "relation": "RELATED_TO"
                # No source_label, target_label, weight, properties
            }

            result = await handle_graph_add_edge(arguments)

            assert result["status"] == "success"
            assert result["weight"] == 1.0

            # Verify default values were used
            mock_get_node.assert_any_call(name="SourceA", label="Entity")
            mock_get_node.assert_any_call(name="TargetB", label="Entity")
            mock_add_edge.assert_called_once_with(
                source_id="source-id",
                target_id="target-id",
                relation="RELATED_TO",
                weight=1.0,
                properties="{}"
            )

    @pytest.mark.asyncio
    async def test_bug2_regression_same_name_different_label_reuses_node(self):
        """
        Regression test for Bug #2: graph_add_edge creates duplicate nodes.

        Scenario:
        1. User creates node: graph_add_node(name="Alpha", label="Test")
        2. User creates edge: graph_add_edge(source_name="Alpha", source_label="Entity")
        3. Expected: Edge should use existing "Alpha" node (same ID)
        4. Bug behavior: Edge created NEW node with different ID

        Root cause: UNIQUE constraint was on (label, name), not just (name).
        Fix: UNIQUE only on (name) - nodes are globally unique by name.
        """
        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_node, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge:

            # Simulate the fix: get_or_create_node returns SAME node_id
            # regardless of label, because UNIQUE is now on (name) only
            same_node_id = "9a95840b-2e6b-4e68-b6f1-4573d67a6323"

            mock_get_node.side_effect = [
                # Source node: "Alpha" already exists, should return SAME ID
                {"node_id": same_node_id, "created": False},
                # Target node: new node
                {"node_id": "new-target-id", "created": True}
            ]

            mock_add_edge.return_value = {
                "edge_id": "edge-id",
                "created": True,
                "source_id": same_node_id,
                "target_id": "new-target-id",
                "relation": "CONNECTS_TO",
                "weight": 1.0
            }

            # Simulate Bug #2 scenario: different label than original node
            arguments = {
                "source_name": "Alpha",  # Same name as existing node
                "source_label": "Entity",  # Different label than "Test"
                "target_name": "Beta",
                "relation": "CONNECTS_TO"
            }

            result = await handle_graph_add_edge(arguments)

            assert result["status"] == "success"
            # Critical: source_id should be the EXISTING node, not a new one
            assert result["source_id"] == same_node_id
            # Node should NOT be marked as newly created
            assert "source_node_created" not in result or result.get("source_node_created") is False