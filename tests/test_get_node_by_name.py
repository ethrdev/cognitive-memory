"""
Tests for get_node_by_name MCP Tool

Tests the get_node_by_name tool implementation including:
- Successful node retrieval by name
- Graceful not_found response for non-existent nodes
- Parameter validation
- Database error handling

Story 6.1: get_node_by_name MCP Tool
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from mcp_server.tools.get_node_by_name import handle_get_node_by_name


class TestGetNodeByNameTool:
    """Test suite for get_node_by_name MCP tool."""

    @pytest.mark.asyncio
    async def test_get_existing_node_success(self):
        """Test retrieving an existing node by name returns full node data."""
        with patch('mcp_server.tools.get_node_by_name.get_node_by_name') as mock_get_node:
            mock_get_node.return_value = {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "label": "Agent",
                "name": "I/O",
                "properties": {"type": "autonomous"},
                "vector_id": 42,
                "created_at": "2025-12-06T14:30:00Z",
            }

            arguments = {"name": "I/O"}

            result = await handle_get_node_by_name(arguments)

            assert result["status"] == "success"
            assert result["node_id"] == "123e4567-e89b-12d3-a456-426614174000"
            assert result["label"] == "Agent"
            assert result["name"] == "I/O"
            assert result["properties"] == {"type": "autonomous"}
            assert result["vector_id"] == 42
            assert result["created_at"] == "2025-12-06T14:30:00Z"

            mock_get_node.assert_called_once_with("I/O")

    @pytest.mark.asyncio
    async def test_get_non_existent_node_graceful_null(self):
        """Test retrieving non-existent node returns graceful null, not exception."""
        with patch('mcp_server.tools.get_node_by_name.get_node_by_name') as mock_get_node:
            mock_get_node.return_value = None

            arguments = {"name": "NonExistentNode"}

            result = await handle_get_node_by_name(arguments)

            # Graceful null return - NOT an error
            assert result["status"] == "not_found"
            assert result["node"] is None
            assert "error" not in result

            mock_get_node.assert_called_once_with("NonExistentNode")

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_name(self):
        """Test error handling when name parameter is missing."""
        arguments = {}  # name is missing

        result = await handle_get_node_by_name(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "name" in result["details"]
        assert result["tool"] == "get_node_by_name"

    @pytest.mark.asyncio
    async def test_parameter_validation_empty_name(self):
        """Test error handling when name is empty string."""
        arguments = {"name": ""}

        result = await handle_get_node_by_name(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_name_not_string(self):
        """Test error handling when name is not a string."""
        arguments = {"name": 12345}  # Should be string

        result = await handle_get_node_by_name(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "name" in result["details"]

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test error handling when database operation fails."""
        with patch('mcp_server.tools.get_node_by_name.get_node_by_name') as mock_get_node:
            mock_get_node.side_effect = Exception("Database connection failed")

            arguments = {"name": "TestNode"}

            result = await handle_get_node_by_name(arguments)

            assert result["error"] == "Database operation failed"
            assert "Database connection failed" in result["details"]
            assert result["tool"] == "get_node_by_name"

    @pytest.mark.asyncio
    async def test_get_node_with_null_vector_id(self):
        """Test retrieving node that has no vector_id linked."""
        with patch('mcp_server.tools.get_node_by_name.get_node_by_name') as mock_get_node:
            mock_get_node.return_value = {
                "id": "node-no-vector",
                "label": "Technology",
                "name": "Python",
                "properties": {"version": "3.12"},
                "vector_id": None,  # No linked L2 insight
                "created_at": "2025-12-06T10:00:00Z",
            }

            arguments = {"name": "Python"}

            result = await handle_get_node_by_name(arguments)

            assert result["status"] == "success"
            assert result["vector_id"] is None
            assert result["name"] == "Python"

    @pytest.mark.asyncio
    async def test_get_node_with_empty_properties(self):
        """Test retrieving node with empty properties dict."""
        with patch('mcp_server.tools.get_node_by_name.get_node_by_name') as mock_get_node:
            mock_get_node.return_value = {
                "id": "node-empty-props",
                "label": "Project",
                "name": "SimpleProject",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-12-06T11:00:00Z",
            }

            arguments = {"name": "SimpleProject"}

            result = await handle_get_node_by_name(arguments)

            assert result["status"] == "success"
            assert result["properties"] == {}


class TestGetNodeByNameIntegration:
    """Integration tests with real database (requires PostgreSQL)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_node_by_name_real_db(self):
        """Test get_node_by_name with real PostgreSQL database."""
        import os
        from dotenv import load_dotenv

        # Skip if no DATABASE_URL configured
        load_dotenv(".env.development")
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not configured - skipping integration test")

        from mcp_server.db.graph import add_node, get_node_by_name as db_get_node

        # Create a unique test node
        import uuid
        test_name = f"IntegrationTestNode_{uuid.uuid4().hex[:8]}"

        try:
            # Step 1: Create node via DB function
            result = add_node(
                label="TestLabel",
                name=test_name,
                properties="{}",
                vector_id=None
            )
            assert result["created"] is True
            created_node_id = result["node_id"]

            # Step 2: Verify via get_node_by_name DB function
            node = db_get_node(test_name)
            assert node is not None
            assert node["id"] == created_node_id
            assert node["label"] == "TestLabel"
            assert node["name"] == test_name

            # Step 3: Test MCP Tool wrapper
            from mcp_server.tools.get_node_by_name import handle_get_node_by_name

            tool_result = await handle_get_node_by_name({"name": test_name})
            assert tool_result["status"] == "success"
            assert tool_result["node_id"] == created_node_id
            assert tool_result["name"] == test_name

            # Step 4: Test not-found case
            not_found_result = await handle_get_node_by_name({"name": "NonExistent_" + uuid.uuid4().hex})
            assert not_found_result["status"] == "not_found"
            assert not_found_result["node"] is None

        finally:
            # Cleanup: Delete test node
            from mcp_server.db.connection import get_connection
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM nodes WHERE name = %s", (test_name,))
                conn.commit()


class TestWriteThenVerifyWorkflow:
    """Integration-style tests for Write-then-Verify pattern."""

    @pytest.mark.asyncio
    async def test_write_then_verify_node_success(self):
        """Test the Write-then-Verify pattern: create node, then verify it exists."""
        from mcp_server.tools.graph_add_node import handle_graph_add_node

        with patch('mcp_server.tools.graph_add_node.add_node') as mock_add_node, \
             patch('mcp_server.tools.get_node_by_name.get_node_by_name') as mock_get_node:

            # Step 1: Write (create node)
            mock_add_node.return_value = {
                "node_id": "new-node-uuid",
                "created": True,
                "label": "Agent",
                "name": "I/O",
            }

            write_result = await handle_graph_add_node({
                "label": "Agent",
                "name": "I/O",
            })

            assert write_result["status"] == "success"
            assert write_result["created"] is True
            node_id = write_result["node_id"]

            # Step 2: Verify (get node by name)
            mock_get_node.return_value = {
                "id": node_id,
                "label": "Agent",
                "name": "I/O",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-12-06T14:30:00Z",
            }

            verify_result = await handle_get_node_by_name({"name": "I/O"})

            assert verify_result["status"] == "success"
            assert verify_result["node_id"] == node_id
            assert verify_result["name"] == "I/O"

    @pytest.mark.asyncio
    async def test_verify_non_existent_before_write(self):
        """Test verification before write returns not_found."""
        with patch('mcp_server.tools.get_node_by_name.get_node_by_name') as mock_get_node:
            mock_get_node.return_value = None

            result = await handle_get_node_by_name({"name": "NodeThatDoesNotExist"})

            assert result["status"] == "not_found"
            assert result["node"] is None
