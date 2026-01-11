"""
Tests for get_edge MCP Tool

Tests the get_edge tool implementation including:
- Successful edge retrieval by source_name, target_name, relation
- Graceful not_found response for non-existent edges
- Graceful not_found for non-existent source/target nodes
- Parameter validation
- Database error handling
- Write-then-Verify edge workflow pattern

Story 6.2: get_edge MCP Tool
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from mcp_server.tools.get_edge import handle_get_edge


class TestGetEdgeTool:
    """Test suite for get_edge MCP tool."""

    @pytest.mark.asyncio
    async def test_get_existing_edge_success(self):
        """Test retrieving an existing edge returns full edge data."""
        with patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:
            mock_get_edge.return_value = {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "source_id": "aaa11111-e89b-12d3-a456-426614174000",
                "target_id": "bbb22222-e89b-12d3-a456-426614174000",
                "relation": "USES",
                "weight": 0.85,
                "properties": {"context": "development"},
                "memory_sector": "semantic",  # Story 8-5: FR26
                "created_at": "2025-12-06T14:30:00Z",
            }

            arguments = {
                "source_name": "I/O",
                "target_name": "Python",
                "relation": "USES",
            }

            result = await handle_get_edge(arguments)

            assert result["status"] == "success"
            assert result["edge_id"] == "123e4567-e89b-12d3-a456-426614174000"
            assert result["source_id"] == "aaa11111-e89b-12d3-a456-426614174000"
            assert result["target_id"] == "bbb22222-e89b-12d3-a456-426614174000"
            assert result["relation"] == "USES"
            assert result["weight"] == 0.85
            assert result["properties"] == {"context": "development"}
            assert result["created_at"] == "2025-12-06T14:30:00Z"

            mock_get_edge.assert_called_once_with("I/O", "Python", "USES")

    @pytest.mark.asyncio
    async def test_get_non_existent_edge_graceful_null(self):
        """Test retrieving non-existent edge returns graceful null, not exception."""
        with patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:
            mock_get_edge.return_value = None

            arguments = {
                "source_name": "NodeA",
                "target_name": "NodeB",
                "relation": "CONNECTS",
            }

            result = await handle_get_edge(arguments)

            # Graceful null return - NOT an error
            assert result["status"] == "not_found"
            assert result["edge"] is None
            assert "error" not in result

            mock_get_edge.assert_called_once_with("NodeA", "NodeB", "CONNECTS")

    @pytest.mark.asyncio
    async def test_get_edge_non_existent_source_node_graceful_null(self):
        """Test graceful null when source node doesn't exist."""
        with patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:
            # DB function returns None when source node doesn't exist
            mock_get_edge.return_value = None

            arguments = {
                "source_name": "NonExistentSource",
                "target_name": "ExistingTarget",
                "relation": "USES",
            }

            result = await handle_get_edge(arguments)

            assert result["status"] == "not_found"
            assert result["edge"] is None
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_get_edge_non_existent_target_node_graceful_null(self):
        """Test graceful null when target node doesn't exist."""
        with patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:
            # DB function returns None when target node doesn't exist
            mock_get_edge.return_value = None

            arguments = {
                "source_name": "ExistingSource",
                "target_name": "NonExistentTarget",
                "relation": "USES",
            }

            result = await handle_get_edge(arguments)

            assert result["status"] == "not_found"
            assert result["edge"] is None
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_source_name(self):
        """Test error handling when source_name parameter is missing."""
        arguments = {
            "target_name": "Python",
            "relation": "USES",
        }  # source_name is missing

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "source_name" in result["details"]
        assert result["tool"] == "get_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_empty_source_name(self):
        """Test error handling when source_name is empty string."""
        arguments = {
            "source_name": "",
            "target_name": "Python",
            "relation": "USES",
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "source_name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_target_name(self):
        """Test error handling when target_name parameter is missing."""
        arguments = {
            "source_name": "I/O",
            "relation": "USES",
        }  # target_name is missing

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "target_name" in result["details"]
        assert result["tool"] == "get_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_empty_target_name(self):
        """Test error handling when target_name is empty string."""
        arguments = {
            "source_name": "I/O",
            "target_name": "",
            "relation": "USES",
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "target_name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_missing_relation(self):
        """Test error handling when relation parameter is missing."""
        arguments = {
            "source_name": "I/O",
            "target_name": "Python",
        }  # relation is missing

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "relation" in result["details"]
        assert result["tool"] == "get_edge"

    @pytest.mark.asyncio
    async def test_parameter_validation_empty_relation(self):
        """Test error handling when relation is empty string."""
        arguments = {
            "source_name": "I/O",
            "target_name": "Python",
            "relation": "",
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "relation" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_whitespace_source_name(self):
        """Test error handling when source_name is whitespace-only."""
        arguments = {
            "source_name": "   ",
            "target_name": "Python",
            "relation": "USES",
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "source_name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_whitespace_target_name(self):
        """Test error handling when target_name is whitespace-only."""
        arguments = {
            "source_name": "I/O",
            "target_name": "   ",
            "relation": "USES",
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "target_name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_whitespace_relation(self):
        """Test error handling when relation is whitespace-only."""
        arguments = {
            "source_name": "I/O",
            "target_name": "Python",
            "relation": "   ",
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "relation" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_source_name_not_string(self):
        """Test error handling when source_name is not a string."""
        arguments = {
            "source_name": 12345,  # Should be string
            "target_name": "Python",
            "relation": "USES",
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "source_name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_target_name_not_string(self):
        """Test error handling when target_name is not a string."""
        arguments = {
            "source_name": "I/O",
            "target_name": 12345,  # Should be string
            "relation": "USES",
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "target_name" in result["details"]

    @pytest.mark.asyncio
    async def test_parameter_validation_relation_not_string(self):
        """Test error handling when relation is not a string."""
        arguments = {
            "source_name": "I/O",
            "target_name": "Python",
            "relation": 12345,  # Should be string
        }

        result = await handle_get_edge(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "relation" in result["details"]

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test error handling when database operation fails."""
        with patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:
            mock_get_edge.side_effect = Exception("Database connection failed")

            arguments = {
                "source_name": "I/O",
                "target_name": "Python",
                "relation": "USES",
            }

            result = await handle_get_edge(arguments)

            assert result["error"] == "Database operation failed"
            assert "Database connection failed" in result["details"]
            assert result["tool"] == "get_edge"

    @pytest.mark.asyncio
    async def test_get_edge_with_null_properties(self):
        """Test retrieving edge that has empty properties."""
        with patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:
            mock_get_edge.return_value = {
                "id": "edge-no-props",
                "source_id": "source-uuid",
                "target_id": "target-uuid",
                "relation": "RELATED_TO",
                "weight": 1.0,
                "properties": {},  # Empty properties
                "memory_sector": "semantic",  # Story 8-5: FR26
                "created_at": "2025-12-06T10:00:00Z",
            }

            arguments = {
                "source_name": "NodeA",
                "target_name": "NodeB",
                "relation": "RELATED_TO",
            }

            result = await handle_get_edge(arguments)

            assert result["status"] == "success"
            assert result["properties"] == {}

    @pytest.mark.asyncio
    async def test_get_edge_with_default_weight(self):
        """Test retrieving edge with default weight of 1.0."""
        with patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:
            mock_get_edge.return_value = {
                "id": "edge-default-weight",
                "source_id": "source-uuid",
                "target_id": "target-uuid",
                "relation": "DEPENDS_ON",
                "weight": 1.0,  # Default weight
                "properties": {},
                "memory_sector": "semantic",  # Story 8-5: FR26
                "created_at": "2025-12-06T11:00:00Z",
            }

            arguments = {
                "source_name": "ProjectA",
                "target_name": "LibraryB",
                "relation": "DEPENDS_ON",
            }

            result = await handle_get_edge(arguments)

            assert result["status"] == "success"
            assert result["weight"] == 1.0


class TestGetEdgeIntegration:
    """Integration tests with real database (requires PostgreSQL)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_edge_real_db(self):
        """Test get_edge with real PostgreSQL database."""
        import os
        from dotenv import load_dotenv

        # Skip if no DATABASE_URL configured
        load_dotenv(".env.development")
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not configured - skipping integration test")

        from mcp_server.db.graph import add_node, add_edge, get_edge_by_names

        # Create unique test nodes and edge
        import uuid
        test_source = f"IntegrationTestSource_{uuid.uuid4().hex[:8]}"
        test_target = f"IntegrationTestTarget_{uuid.uuid4().hex[:8]}"
        test_relation = "INTEGRATION_TEST"

        try:
            # Step 1: Create source and target nodes
            source_result = add_node(
                label="TestLabel",
                name=test_source,
                properties="{}",
                vector_id=None
            )
            target_result = add_node(
                label="TestLabel",
                name=test_target,
                properties="{}",
                vector_id=None
            )
            source_id = source_result["node_id"]
            target_id = target_result["node_id"]

            # Step 2: Create edge between nodes
            edge_result = add_edge(
                source_id=source_id,
                target_id=target_id,
                relation=test_relation,
                weight=0.75,
                properties="{}"
            )
            created_edge_id = edge_result["edge_id"]

            # Step 3: Verify via get_edge_by_names DB function
            edge = get_edge_by_names(test_source, test_target, test_relation)
            assert edge is not None
            assert edge["id"] == created_edge_id
            assert edge["relation"] == test_relation
            assert float(edge["weight"]) == 0.75

            # Step 4: Test MCP Tool wrapper
            from mcp_server.tools.get_edge import handle_get_edge

            tool_result = await handle_get_edge({
                "source_name": test_source,
                "target_name": test_target,
                "relation": test_relation,
            })
            assert tool_result["status"] == "success"
            assert tool_result["edge_id"] == created_edge_id

            # Step 5: Test not-found case with non-existent relation
            not_found_result = await handle_get_edge({
                "source_name": test_source,
                "target_name": test_target,
                "relation": "NON_EXISTENT_RELATION",
            })
            assert not_found_result["status"] == "not_found"
            assert not_found_result["edge"] is None

        finally:
            # Cleanup: Delete test edge and nodes
            from mcp_server.db.connection import get_connection
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM edges WHERE relation = %s", (test_relation,))
                    cur.execute("DELETE FROM nodes WHERE name IN (%s, %s)", (test_source, test_target))
                conn.commit()


class TestWriteThenVerifyEdgeWorkflow:
    """Integration-style tests for Write-then-Verify edge pattern."""

    @pytest.mark.asyncio
    async def test_write_then_verify_edge_success(self):
        """Test the Write-then-Verify pattern: create edge, then verify it exists."""
        from mcp_server.tools.graph_add_edge import handle_graph_add_edge

        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_or_create, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge, \
             patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:

            # Step 1: Write (create edge) - setup mocks
            mock_get_or_create.side_effect = [
                {"node_id": "source-uuid", "created": False},
                {"node_id": "target-uuid", "created": False},
            ]
            mock_add_edge.return_value = {
                "edge_id": "new-edge-uuid",
                "created": True,
                "source_id": "source-uuid",
                "target_id": "target-uuid",
                "relation": "USES",
                "weight": 1.0,
                "memory_sector": "semantic",  # Story 8-5: FR26 (Story 8-3 added this to graph_add_edge response)
            }

            write_result = await handle_graph_add_edge({
                "source_name": "I/O",
                "target_name": "Python",
                "relation": "USES",
            })

            assert write_result["status"] == "success"
            assert write_result["created"] is True
            edge_id = write_result["edge_id"]

            # Step 2: Verify (get edge by names)
            mock_get_edge.return_value = {
                "id": edge_id,
                "source_id": "source-uuid",
                "target_id": "target-uuid",
                "relation": "USES",
                "weight": 1.0,
                "properties": {},
                "memory_sector": "semantic",  # Story 8-5: FR26
                "created_at": "2025-12-06T14:30:00Z",
            }

            verify_result = await handle_get_edge({
                "source_name": "I/O",
                "target_name": "Python",
                "relation": "USES",
            })

            assert verify_result["status"] == "success"
            assert verify_result["edge_id"] == edge_id
            assert verify_result["relation"] == "USES"

    @pytest.mark.asyncio
    async def test_verify_non_existent_before_write(self):
        """Test verification before write returns not_found."""
        with patch('mcp_server.tools.get_edge.get_edge_by_names') as mock_get_edge:
            mock_get_edge.return_value = None

            result = await handle_get_edge({
                "source_name": "SourceThatDoesNotExist",
                "target_name": "TargetThatDoesNotExist",
                "relation": "UNKNOWN_RELATION",
            })

            assert result["status"] == "not_found"
            assert result["edge"] is None
