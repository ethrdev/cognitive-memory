"""
Tests for count_by_type MCP Tool

Tests the count_by_type tool implementation including:
- Successful count retrieval for all memory types
- Zero counts for empty tables
- Parameterless invocation
- Database error handling
- Response format validation

Story 6.3: count_by_type MCP Tool
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


class TestCountByTypeTool:
    """Test suite for count_by_type MCP tool."""

    @pytest.mark.asyncio
    async def test_get_all_counts_success(self):
        """Test retrieving all counts returns complete response with all 6 fields."""
        from mcp_server.tools.count_by_type import handle_count_by_type

        with patch('mcp_server.tools.count_by_type.get_all_counts') as mock_get_counts:
            mock_get_counts.return_value = {
                "graph_nodes": 47,
                "graph_edges": 89,
                "l2_insights": 234,
                "episodes": 86,
                "working_memory": 5,
                "raw_dialogues": 1203,
            }

            arguments = {}  # Parameterless

            result = await handle_count_by_type(arguments)

            assert result["status"] == "success"
            assert result["graph_nodes"] == 47
            assert result["graph_edges"] == 89
            assert result["l2_insights"] == 234
            assert result["episodes"] == 86
            assert result["working_memory"] == 5
            assert result["raw_dialogues"] == 1203

            mock_get_counts.assert_called_once()

    @pytest.mark.asyncio
    async def test_zero_counts_empty_database(self):
        """Test that empty tables return zero counts, not errors."""
        from mcp_server.tools.count_by_type import handle_count_by_type

        with patch('mcp_server.tools.count_by_type.get_all_counts') as mock_get_counts:
            mock_get_counts.return_value = {
                "graph_nodes": 0,
                "graph_edges": 0,
                "l2_insights": 0,
                "episodes": 0,
                "working_memory": 0,
                "raw_dialogues": 0,
            }

            arguments = {}

            result = await handle_count_by_type(arguments)

            assert result["status"] == "success"
            assert result["graph_nodes"] == 0
            assert result["graph_edges"] == 0
            assert result["l2_insights"] == 0
            assert result["episodes"] == 0
            assert result["working_memory"] == 0
            assert result["raw_dialogues"] == 0
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_parameterless_invocation(self):
        """Test that tool works without any parameters (empty arguments dict)."""
        from mcp_server.tools.count_by_type import handle_count_by_type

        with patch('mcp_server.tools.count_by_type.get_all_counts') as mock_get_counts:
            mock_get_counts.return_value = {
                "graph_nodes": 10,
                "graph_edges": 20,
                "l2_insights": 30,
                "episodes": 40,
                "working_memory": 50,
                "raw_dialogues": 60,
            }

            # Empty arguments - parameterless call
            result = await handle_count_by_type({})

            assert result["status"] == "success"
            mock_get_counts.assert_called_once()

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test error handling when database operation fails."""
        from mcp_server.tools.count_by_type import handle_count_by_type

        with patch('mcp_server.tools.count_by_type.get_all_counts') as mock_get_counts:
            mock_get_counts.side_effect = Exception("Connection timeout")

            arguments = {}

            result = await handle_count_by_type(arguments)

            assert result["error"] == "Database operation failed"
            assert "Connection timeout" in result["details"]
            assert result["tool"] == "count_by_type"

    @pytest.mark.asyncio
    async def test_response_contains_all_required_fields(self):
        """Test that response contains exactly the 6 count fields plus status."""
        from mcp_server.tools.count_by_type import handle_count_by_type

        with patch('mcp_server.tools.count_by_type.get_all_counts') as mock_get_counts:
            mock_get_counts.return_value = {
                "graph_nodes": 1,
                "graph_edges": 2,
                "l2_insights": 3,
                "episodes": 4,
                "working_memory": 5,
                "raw_dialogues": 6,
            }

            result = await handle_count_by_type({})

            expected_fields = {
                "graph_nodes", "graph_edges", "l2_insights",
                "episodes", "working_memory", "raw_dialogues", "status"
            }
            assert set(result.keys()) == expected_fields

    @pytest.mark.asyncio
    async def test_count_values_are_integers(self):
        """Test that all count values are integers (not strings or floats)."""
        from mcp_server.tools.count_by_type import handle_count_by_type

        with patch('mcp_server.tools.count_by_type.get_all_counts') as mock_get_counts:
            mock_get_counts.return_value = {
                "graph_nodes": 100,
                "graph_edges": 200,
                "l2_insights": 300,
                "episodes": 400,
                "working_memory": 500,
                "raw_dialogues": 600,
            }

            result = await handle_count_by_type({})

            assert isinstance(result["graph_nodes"], int)
            assert isinstance(result["graph_edges"], int)
            assert isinstance(result["l2_insights"], int)
            assert isinstance(result["episodes"], int)
            assert isinstance(result["working_memory"], int)
            assert isinstance(result["raw_dialogues"], int)

    @pytest.mark.asyncio
    async def test_response_structure_status_last(self):
        """Test that status is included in the response (order in dict is insertion order in Python 3.7+)."""
        from mcp_server.tools.count_by_type import handle_count_by_type

        with patch('mcp_server.tools.count_by_type.get_all_counts') as mock_get_counts:
            mock_get_counts.return_value = {
                "graph_nodes": 1,
                "graph_edges": 2,
                "l2_insights": 3,
                "episodes": 4,
                "working_memory": 5,
                "raw_dialogues": 6,
            }

            result = await handle_count_by_type({})

            # In Python 3.7+, dict maintains insertion order
            # Verify status is present and last
            keys_list = list(result.keys())
            assert keys_list[-1] == "status"


class TestGetAllCountsDBFunction:
    """Test suite for get_all_counts database function."""

    def test_get_all_counts_returns_dict(self):
        """Test that get_all_counts returns a dictionary with all counts."""
        from mcp_server.db.stats import get_all_counts

        with patch('mcp_server.db.stats.get_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {"type": "graph_nodes", "count": 10},
                {"type": "graph_edges", "count": 20},
                {"type": "l2_insights", "count": 30},
                {"type": "episodes", "count": 40},
                {"type": "working_memory", "count": 50},
                {"type": "raw_dialogues", "count": 60},
            ]
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

            result = await get_all_counts()

            assert result["graph_nodes"] == 10
            assert result["graph_edges"] == 20
            assert result["l2_insights"] == 30
            assert result["episodes"] == 40
            assert result["working_memory"] == 50
            assert result["raw_dialogues"] == 60

    def test_get_all_counts_empty_tables(self):
        """Test that empty tables return 0 counts."""
        from mcp_server.db.stats import get_all_counts

        with patch('mcp_server.db.stats.get_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {"type": "graph_nodes", "count": 0},
                {"type": "graph_edges", "count": 0},
                {"type": "l2_insights", "count": 0},
                {"type": "episodes", "count": 0},
                {"type": "working_memory", "count": 0},
                {"type": "raw_dialogues", "count": 0},
            ]
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

            result = await get_all_counts()

            assert all(v == 0 for v in result.values())


class TestCountByTypeIntegration:
    """Integration tests with real database (requires PostgreSQL)."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_count_by_type_real_db(self):
        """Test count_by_type with real PostgreSQL database."""
        import os
        from dotenv import load_dotenv

        # Skip if no DATABASE_URL configured
        load_dotenv(".env.development")
        if not os.getenv("DATABASE_URL"):
            pytest.skip("DATABASE_URL not configured - skipping integration test")

        from mcp_server.tools.count_by_type import handle_count_by_type
        from mcp_server.db.graph import add_node
        from mcp_server.db.connection import get_connection
        import uuid

        test_node_name = f"IntegrationTestNode_{uuid.uuid4().hex[:8]}"

        try:
            # Step 1: Get initial counts
            initial_result = await handle_count_by_type({})
            assert initial_result["status"] == "success"
            initial_node_count = initial_result["graph_nodes"]

            # Step 2: Add a test node
            add_node(
                label="TestLabel",
                name=test_node_name,
                properties="{}",
                vector_id=None
            )

            # Step 3: Verify count increased
            after_result = await handle_count_by_type({})
            assert after_result["status"] == "success"
            assert after_result["graph_nodes"] == initial_node_count + 1

        finally:
            # Cleanup: Delete test node
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM nodes WHERE name = %s", (test_node_name,))
                conn.commit()
