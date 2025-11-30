"""
Tests for graph_add_node MCP Tool

Tests the graph_add_node tool implementation including:
- Parameter validation
- Idempotent node creation and retrieval
- Optional parameters (properties, vector_id)
- Error handling for invalid inputs
- Database integration

Story 4.2: graph_add_node Tool Implementation
"""

from __future__ import annotations

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.tools.graph_add_node import handle_graph_add_node
from mcp_server.db.graph import add_node, get_node_by_id, get_nodes_by_label


class TestGraphAddNodeTool:
    """Test suite for graph_add_node MCP tool."""

    @pytest.mark.asyncio
    async def test_create_new_node_success(self):
        """Test creating a new node with minimal required parameters."""
        # Mock database function to simulate new node creation
        with patch('mcp_server.tools.graph_add_node.add_node') as mock_add_node:
            mock_add_node.return_value = {
                "node_id": "123e4567-e89b-12d3-a456-426614174000",
                "created": True,
                "label": "Project",
                "name": "TestProject"
            }

            arguments = {
                "label": "Project",
                "name": "TestProject"
            }

            result = await handle_graph_add_node(arguments)

            assert result["status"] == "success"
            assert result["node_id"] == "123e4567-e89b-12d3-a456-426614174000"
            assert result["created"] is True
            assert result["label"] == "Project"
            assert result["name"] == "TestProject"

            # Verify the database function was called correctly
            mock_add_node.assert_called_once_with(
                label="Project",
                name="TestProject",
                properties="{}",
                vector_id=None
            )

    @pytest.mark.asyncio
    async def test_find_existing_node_idempotent(self):
        """Test finding an existing node (idempotent operation)."""
        # Mock database function to simulate existing node retrieval
        with patch('mcp_server.tools.graph_add_node.add_node') as mock_add_node:
            mock_add_node.return_value = {
                "node_id": "existing-node-id",
                "created": False,
                "label": "Technology",
                "name": "Python"
            }

            arguments = {
                "label": "Technology",
                "name": "Python",
                "properties": {"version": "3.9"}
            }

            result = await handle_graph_add_node(arguments)

            assert result["status"] == "success"
            assert result["node_id"] == "existing-node-id"
            assert result["created"] is False
            assert result["label"] == "Technology"
            assert result["name"] == "Python"

    @pytest.mark.asyncio
    async def test_create_node_with_all_parameters(self):
        """Test creating a node with all optional parameters."""
        with patch('mcp_server.tools.graph_add_node.add_node') as mock_add_node:
            mock_add_node.return_value = {
                "node_id": "node-with-all-params",
                "created": True,
                "label": "Client",
                "name": "AcmeCorp",
                "properties": {"industry": "Technology", "size": "Large"},
                "vector_id": 42
            }

            arguments = {
                "label": "Client",
                "name": "AcmeCorp",
                "properties": {"industry": "Technology", "size": "Large"},
                "vector_id": 42
            }

            result = await handle_graph_add_node(arguments)

            assert result["status"] == "success"
            assert result["created"] is True

            # Verify all parameters were passed correctly
            mock_add_node.assert_called_once_with(
                label="Client",
                name="AcmeCorp",
                properties=json.dumps({"industry": "Technology", "size": "Large"}),
                vector_id=42
            )

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_label(self):
        """Test error handling when label parameter is missing."""
        arguments = {
            "name": "TestNode"
            # label is missing
        }

        result = await handle_graph_add_node(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "label" in result["details"]
        assert result["tool"] == "graph_add_node"

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_name(self):
        """Test error handling when name parameter is missing."""
        arguments = {
            "label": "Project"
            # name is missing
        }

        result = await handle_graph_add_node(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "name" in result["details"]
        assert result["tool"] == "graph_add_node"

    @pytest.mark.asyncio
    async def test_parameter_validation_empty_label(self):
        """Test error handling when label is empty string."""
        arguments = {
            "label": "",
            "name": "TestNode"
        }

        result = await handle_graph_add_node(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "label" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_empty_name(self):
        """Test error handling when name is empty string."""
        arguments = {
            "label": "Project",
            "name": ""
        }

        result = await handle_graph_add_node(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_properties_type(self):
        """Test error handling when properties is not a dict."""
        arguments = {
            "label": "Project",
            "name": "TestProject",
            "properties": "invalid-string"  # Should be dict
        }

        result = await handle_graph_add_node(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "properties" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_invalid_vector_id_type(self):
        """Test error handling when vector_id is not an integer."""
        arguments = {
            "label": "Project",
            "name": "TestProject",
            "vector_id": "not-an-integer"  # Should be positive integer
        }

        result = await handle_graph_add_node(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "vector_id" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_negative_vector_id(self):
        """Test error handling when vector_id is negative."""
        arguments = {
            "label": "Project",
            "name": "TestProject",
            "vector_id": -1  # Should be positive integer
        }

        result = await handle_graph_add_node(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "vector_id" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_zero_vector_id(self):
        """Test error handling when vector_id is zero."""
        arguments = {
            "label": "Project",
            "name": "TestProject",
            "vector_id": 0  # Should be positive integer
        }

        result = await handle_graph_add_node(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "vector_id" in result["details"]

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test error handling when database operation fails."""
        with patch('mcp_server.tools.graph_add_node.add_node') as mock_add_node:
            mock_add_node.side_effect = Exception("Database connection failed")

            arguments = {
                "label": "Project",
                "name": "TestProject"
            }

            result = await handle_graph_add_node(arguments)

            assert result["error"] == "Database operation failed"
            assert "Database connection failed" in result["details"]
            assert result["tool"] == "graph_add_node"

    @pytest.mark.asyncio
    async def test_non_standard_label_warning(self):
        """Test that non-standard labels generate warnings but don't block."""
        with patch('mcp_server.tools.graph_add_node.add_node') as mock_add_node, \
             patch('mcp_server.tools.graph_add_node.logger') as mock_logger:

            mock_add_node.return_value = {
                "node_id": "test-id",
                "created": True,
                "label": "CustomLabel",
                "name": "TestNode"
            }

            arguments = {
                "label": "CustomLabel",  # Non-standard label
                "name": "TestNode"
            }

            result = await handle_graph_add_node(arguments)

            assert result["status"] == "success"
            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            warning_call = mock_logger.warning.call_args[0][0]
            assert "CustomLabel" in warning_call
            assert "Standard labels" in warning_call


class TestGraphDatabaseFunctions:
    """Test suite for graph database functions."""

    def test_add_node_with_properties_dict(self):
        """Test add_node function with properties parameter."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            # Mock database connection and cursor
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Mock successful INSERT (new node)
            mock_cursor.fetchone.return_value = {
                "id": "new-node-uuid",
                "label": "TestLabel",
                "name": "TestName",
                "created_at": "2025-11-27T12:00:00Z"
            }

            result = add_node(
                label="TestLabel",
                name="TestName",
                properties='{"key": "value"}',
                vector_id=None
            )

            assert result["created"] is True
            assert result["label"] == "TestLabel"
            assert result["name"] == "TestName"

            # Verify correct SQL was executed
            mock_cursor.execute.assert_called_once()
            execute_args = mock_cursor.execute.call_args[0]
            assert "INSERT INTO nodes" in execute_args[0]
            assert "ON CONFLICT (label, name) DO NOTHING" in execute_args[0]

    def test_add_node_idempotent_conflict(self):
        """Test add_node function when node already exists (conflict)."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            # Mock database connection and cursor
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Mock INSERT conflict (no row returned) then SELECT existing
            mock_cursor.fetchone.side_effect = [
                None,  # INSERT returned no rows (conflict)
                {
                    "id": "existing-node-uuid",
                    "label": "TestLabel",
                    "name": "TestName",
                    "created_at": "2025-11-27T12:00:00Z"
                }  # SELECT found existing node
            ]

            result = add_node(
                label="TestLabel",
                name="TestName",
                properties="{}",
                vector_id=None
            )

            assert result["created"] is False
            assert result["label"] == "TestLabel"
            assert result["name"] == "TestName"

            # Verify both INSERT and SELECT were executed
            assert mock_cursor.execute.call_count == 2

    def test_get_nodes_by_label_success(self):
        """Test get_nodes_by_label function."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            # Mock database connection and cursor
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Mock query results
            mock_cursor.fetchall.return_value = [
                {
                    "id": "node-1-uuid",
                    "label": "Project",
                    "name": "ProjectA",
                    "properties": {"status": "active"},
                    "vector_id": 1,
                    "created_at": "2025-11-27T12:00:00Z"
                },
                {
                    "id": "node-2-uuid",
                    "label": "Project",
                    "name": "ProjectB",
                    "properties": {"status": "planning"},
                    "vector_id": 2,
                    "created_at": "2025-11-27T13:00:00Z"
                }
            ]

            result = get_nodes_by_label("Project")

            assert len(result) == 2
            assert result[0]["label"] == "Project"
            assert result[0]["name"] == "ProjectA"
            assert result[1]["label"] == "Project"
            assert result[1]["name"] == "ProjectB"

            # Verify correct SQL was executed
            mock_cursor.execute.assert_called_once()
            execute_args = mock_cursor.execute.call_args[0]
            assert "SELECT id, label, name, properties, vector_id, created_at" in execute_args[0]
            assert "WHERE label = %s" in execute_args[0]
            assert execute_args[1] == ("Project",)