"""
Tests for list_episodes MCP Tool

Tests the list_episodes tool implementation including:
- Successful episode listing with pagination
- Time filtering with since parameter
- Parameter validation (limit, offset, since)
- Empty database handling
- Database error handling

Story 6.4: list_episodes MCP Tool
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestListEpisodesTool:
    """Test suite for list_episodes MCP tool."""

    @pytest.mark.asyncio
    async def test_list_episodes_success(self):
        """Test successful episode listing with default pagination."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        mock_episodes = [
            {"id": 2, "query": "What is GraphRAG?", "reward": 0.6, "created_at": "2025-12-02T14:30:00+00:00"},
            {"id": 1, "query": "How to connect?", "reward": 0.8, "created_at": "2025-12-01T10:00:00+00:00"},
        ]

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": mock_episodes,
                "total_count": 86,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({})

            assert result["status"] == "success"
            assert result["total_count"] == 86
            assert result["limit"] == 50
            assert result["offset"] == 0
            assert len(result["episodes"]) == 2
            mock_list.assert_called_once_with(limit=50, offset=0, since=None)

    @pytest.mark.asyncio
    async def test_list_episodes_with_pagination(self):
        """Test pagination with custom limit and offset."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [{"id": 25, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00"}],
                "total_count": 100,
                "limit": 10,
                "offset": 20,
            }

            result = await handle_list_episodes({"limit": 10, "offset": 20})

            assert result["status"] == "success"
            assert result["limit"] == 10
            assert result["offset"] == 20
            assert result["total_count"] == 100
            mock_list.assert_called_once_with(limit=10, offset=20, since=None)

    @pytest.mark.asyncio
    async def test_list_episodes_with_since_filter(self):
        """Test time filtering with since parameter."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [{"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T12:00:00+00:00"}],
                "total_count": 10,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"since": "2025-12-01T00:00:00Z"})

            assert result["status"] == "success"
            assert result["total_count"] == 10
            # Verify since was parsed and passed
            call_args = mock_list.call_args
            assert call_args.kwargs["since"] is not None

    @pytest.mark.asyncio
    async def test_list_episodes_empty_database(self):
        """Test empty database returns empty list, not error."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [],
                "total_count": 0,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({})

            assert result["status"] == "success"
            assert result["episodes"] == []
            assert result["total_count"] == 0
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_list_episodes_invalid_limit_too_low(self):
        """Test limit < 1 returns validation error."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"limit": 0})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert "limit" in result["details"]
        assert result["tool"] == "list_episodes"

    @pytest.mark.asyncio
    async def test_list_episodes_invalid_limit_too_high(self):
        """Test limit > 100 returns validation error."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"limit": 101})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert "limit" in result["details"]
        assert result["tool"] == "list_episodes"

    @pytest.mark.asyncio
    async def test_list_episodes_invalid_offset_negative(self):
        """Test offset < 0 returns validation error."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"offset": -1})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert "offset" in result["details"]
        assert result["tool"] == "list_episodes"

    @pytest.mark.asyncio
    async def test_list_episodes_invalid_since_format(self):
        """Test invalid since format returns validation error."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"since": "not-a-date"})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert "timestamp" in result["details"].lower() or "since" in result["details"].lower()
        assert result["tool"] == "list_episodes"

    @pytest.mark.asyncio
    async def test_list_episodes_database_error(self):
        """Test database error returns structured error response."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.side_effect = Exception("Connection timeout")

            result = await handle_list_episodes({})

            assert "error" in result
            assert result["error"] == "Database operation failed"
            assert "Connection timeout" in result["details"]
            assert result["tool"] == "list_episodes"

    @pytest.mark.asyncio
    async def test_list_episodes_response_fields_complete(self):
        """Test response contains all required fields."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [],
                "total_count": 0,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({})

            # All required fields present
            assert "episodes" in result
            assert "total_count" in result
            assert "limit" in result
            assert "offset" in result
            assert "status" in result
            # Status is last (dict order preserved in Python 3.7+)
            assert list(result.keys())[-1] == "status"

    @pytest.mark.asyncio
    async def test_list_episodes_total_count_independent_of_limit(self):
        """Test total_count reflects all matching episodes, not just page."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            # Only 5 episodes returned due to limit, but 100 total
            mock_list.return_value = {
                "episodes": [{"id": i, "query": f"Q{i}", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00"} for i in range(5)],
                "total_count": 100,
                "limit": 5,
                "offset": 0,
            }

            result = await handle_list_episodes({"limit": 5})

            assert len(result["episodes"]) == 5
            assert result["total_count"] == 100  # Total, not page size


class TestListEpisodesDBFunction:
    """Test suite for list_episodes DB function."""

    def test_list_episodes_db_function_exists(self):
        """Test that the DB function can be imported."""
        from mcp_server.db.episodes import list_episodes
        assert callable(list_episodes)

    @pytest.mark.asyncio
    async def test_list_episodes_db_returns_dict(self):
        """Test DB function returns expected dict structure."""
        from mcp_server.db.episodes import list_episodes

        with patch("mcp_server.db.episodes.get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {"count": 0}
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

            result = await list_episodes()

            assert isinstance(result, dict)
            assert "episodes" in result
            assert "total_count" in result
            assert "limit" in result
            assert "offset" in result


class TestListEpisodesIntegration:
    """Integration tests with real database."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_episodes_real_db(self):
        """Test list_episodes with real PostgreSQL database."""
        from mcp_server.db.connection import get_connection
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_query = f"IntegrationTest_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536  # Required: 1536-dim vector

        try:
            # Insert test episode
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO episode_memory
                    (query, reward, reflection, embedding, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (test_query, 0.8, "Test reflection for integration", fake_embedding),
                )
                conn.commit()

            # Test list_episodes
            result = await handle_list_episodes({})

            assert result["status"] == "success"
            assert result["total_count"] >= 1
            assert isinstance(result["episodes"], list)

            # Verify our test episode is in the results
            found = any(ep["query"] == test_query for ep in result["episodes"])
            assert found, f"Test episode with query '{test_query}' not found in results"

        finally:
            # Cleanup
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query = %s",
                    (test_query,),
                )
                conn.commit()
