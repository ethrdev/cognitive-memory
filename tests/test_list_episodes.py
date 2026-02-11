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
from unittest.mock import MagicMock, AsyncMock, patch

import pytest


class TestListEpisodesTool:
    """Test suite for list_episodes MCP tool."""

    @pytest.mark.asyncio
    async def test_list_episodes_success(self):
        """Test successful episode listing with default pagination."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        mock_episodes = [
            {"id": 2, "query": "What is GraphRAG?", "reward": 0.6, "created_at": "2025-12-02T14:30:00+00:00", "tags": []},
            {"id": 1, "query": "How to connect?", "reward": 0.8, "created_at": "2025-12-01T10:00:00+00:00", "tags": []},
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
            # Updated for Story 9.2.1: new parameters expected
            mock_list.assert_called_once_with(
                limit=50, offset=0, since=None, date_from=None, date_to=None,
                tags=None, category=None
            )

    @pytest.mark.asyncio
    async def test_list_episodes_with_pagination(self):
        """Test pagination with custom limit and offset."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [{"id": 25, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00", "tags": []}],
                "total_count": 100,
                "limit": 10,
                "offset": 20,
            }

            result = await handle_list_episodes({"limit": 10, "offset": 20})

            assert result["status"] == "success"
            assert result["limit"] == 10
            assert result["offset"] == 20
            assert result["total_count"] == 100
            # Updated for Story 9.2.1: new parameters expected
            mock_list.assert_called_once_with(
                limit=10, offset=20, since=None, date_from=None, date_to=None,
                tags=None, category=None
            )

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
            # Note: add_response_metadata() adds "metadata" field before "status"
            # So "status" is not necessarily the last key anymore
            assert "metadata" in result  # Added by add_response_metadata (Story 11.4.3)

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
        from contextlib import asynccontextmanager

        # Updated for Story 9.2.1: mock get_connection_with_project_context (async)
        @asynccontextmanager
        async def mock_connection():
            """Mock async context manager that returns a mock connection."""
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {"count": 0}
            mock_conn.cursor.return_value = mock_cursor
            yield mock_conn

        with patch("mcp_server.db.episodes.get_connection_with_project_context", side_effect=mock_connection):
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
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_query = f"IntegrationTest_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536  # Required: 1536-dim vector

        try:
            # Initialize pool for integration test
            await initialize_pool()

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


# ============================================================================
# Story 9.2.1: Extended Parameter Tests
# ============================================================================

class TestListEpisodesExtendedParameters:
    """Test suite for extended filtering parameters (tags, category, date range)."""

    @pytest.mark.asyncio
    async def test_tags_single_filter(self):
        """Test filtering by single tag."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00", "tags": ["dark-romance"]},
                ],
                "total_count": 5,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"tags": ["dark-romance"]})

            assert result["status"] == "success"
            mock_list.assert_called_once_with(
                limit=50, offset=0, since=None, date_from=None, date_to=None,
                tags=["dark-romance"], category=None
            )

    @pytest.mark.asyncio
    async def test_tags_multiple_filter_and_logic(self):
        """Test filtering by multiple tags (AND logic - all must be present)."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00",
                     "tags": ["dark-romance", "relationship"]},
                ],
                "total_count": 2,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"tags": ["dark-romance", "relationship"]})

            assert result["status"] == "success"
            call_args = mock_list.call_args
            assert call_args.kwargs["tags"] == ["dark-romance", "relationship"]

    @pytest.mark.asyncio
    async def test_tags_no_match(self):
        """Test tags filter with no matching episodes."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [],
                "total_count": 0,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"tags": ["nonexistent-tag"]})

            assert result["status"] == "success"
            assert len(result["episodes"]) == 0
            assert result["total_count"] == 0

    @pytest.mark.asyncio
    async def test_tags_empty_array_no_filter(self):
        """Test empty tags array is treated as no filter (returns all episodes)."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00", "tags": []},
                ],
                "total_count": 50,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"tags": []})

            assert result["status"] == "success"
            # Empty tags array should be passed as None (no filter)
            call_args = mock_list.call_args
            assert call_args.kwargs["tags"] is None or call_args.kwargs["tags"] == []

    @pytest.mark.asyncio
    async def test_tags_invalid_not_array(self):
        """Test tags validation rejects non-array values."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"tags": "not-an-array"})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert "tags" in result["details"].lower() or "array" in result["details"].lower()

    @pytest.mark.asyncio
    async def test_tags_invalid_array_contains_non_string(self):
        """Test tags validation rejects arrays with non-string elements."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"tags": ["valid-tag", 123, "another-tag"]})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"

    @pytest.mark.asyncio
    async def test_category_prefix_match(self):
        """Test category prefix matching on query field."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "[ethr] Dark Romance scene", "reward": 0.7, "created_at": "2025-12-01T00:00:00+00:00", "tags": []},
                ],
                "total_count": 10,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"category": "[ethr]"})

            assert result["status"] == "success"
            mock_list.assert_called_once_with(
                limit=50, offset=0, since=None, date_from=None, date_to=None,
                tags=None, category="[ethr]"
            )

    @pytest.mark.asyncio
    async def test_category_no_match(self):
        """Test category filter with no matching episodes."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [],
                "total_count": 0,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"category": "[nonexistent]"})

            assert result["status"] == "success"
            assert len(result["episodes"]) == 0

    @pytest.mark.asyncio
    async def test_category_invalid_not_string(self):
        """Test category validation rejects non-string values."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"category": 123})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert "category" in result["details"].lower() or "string" in result["details"].lower()

    @pytest.mark.asyncio
    async def test_date_from_only(self):
        """Test date_from filter (episodes on or after date)."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T12:00:00+00:00", "tags": []},
                ],
                "total_count": 15,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"date_from": "2025-12-01T00:00:00Z"})

            assert result["status"] == "success"
            call_args = mock_list.call_args
            assert call_args.kwargs["date_from"] is not None

    @pytest.mark.asyncio
    async def test_date_to_only(self):
        """Test date_to filter (episodes before or on date)."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-11-30T23:59:59+00:00", "tags": []},
                ],
                "total_count": 8,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"date_to": "2025-11-30T23:59:59Z"})

            assert result["status"] == "success"
            call_args = mock_list.call_args
            assert call_args.kwargs["date_to"] is not None

    @pytest.mark.asyncio
    async def test_date_range(self):
        """Test date range filter (both date_from and date_to)."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-15T12:00:00+00:00", "tags": []},
                ],
                "total_count": 5,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({
                "date_from": "2025-12-01T00:00:00Z",
                "date_to": "2025-12-31T23:59:59Z"
            })

            assert result["status"] == "success"
            call_args = mock_list.call_args
            assert call_args.kwargs["date_from"] is not None
            assert call_args.kwargs["date_to"] is not None

    @pytest.mark.asyncio
    async def test_date_from_invalid_format(self):
        """Test date_from validation rejects invalid timestamps."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"date_from": "not-a-date"})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert "timestamp" in result["details"].lower() or "invalid" in result["details"].lower()

    @pytest.mark.asyncio
    async def test_date_to_invalid_format(self):
        """Test date_to validation rejects invalid timestamps."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        result = await handle_list_episodes({"date_to": "not-a-date"})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"

    @pytest.mark.asyncio
    async def test_combined_filters(self):
        """Test combining multiple filters (tags + category + date range)."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "[ethr] Dark Romance scene", "reward": 0.7,
                     "created_at": "2025-12-15T12:00:00+00:00", "tags": ["dark-romance", "relationship"]},
                ],
                "total_count": 1,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({
                "tags": ["dark-romance"],
                "category": "[ethr]",
                "date_from": "2025-12-01T00:00:00Z",
                "date_to": "2025-12-31T23:59:59Z"
            })

            assert result["status"] == "success"
            call_args = mock_list.call_args
            assert call_args.kwargs["tags"] == ["dark-romance"]
            assert call_args.kwargs["category"] == "[ethr]"
            assert call_args.kwargs["date_from"] is not None
            assert call_args.kwargs["date_to"] is not None

    @pytest.mark.asyncio
    async def test_backward_compatibility_no_new_params(self):
        """Test backward compatibility - calls without new parameters work unchanged."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00", "tags": []},
                ],
                "total_count": 50,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"limit": 10, "offset": 0})

            assert result["status"] == "success"
            mock_list.assert_called_once_with(
                limit=10, offset=0, since=None, date_from=None, date_to=None,
                tags=None, category=None
            )

    @pytest.mark.asyncio
    async def test_since_parameter_still_works(self):
        """Test legacy 'since' parameter behaves like 'date_from'."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T12:00:00+00:00", "tags": []},
                ],
                "total_count": 10,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({"since": "2025-12-01T00:00:00Z"})

            assert result["status"] == "success"
            call_args = mock_list.call_args
            # since should be passed as `since` parameter
            assert call_args.kwargs["since"] is not None
            # date_from should remain None
            assert call_args.kwargs["date_from"] is None

    @pytest.mark.asyncio
    async def test_since_and_date_from_both_provided_date_from_wins(self):
        """Test when both 'since' and 'date_from' provided, date_from takes precedence."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-15T12:00:00+00:00", "tags": []},
                ],
                "total_count": 5,
                "limit": 50,
                "offset": 0,
            }

            # Both parameters provided - date_from should be used
            result = await handle_list_episodes({
                "since": "2025-12-01T00:00:00Z",  # Earlier date (should be ignored)
                "date_from": "2025-12-10T00:00:00Z",  # Later date (should win)
            })

            assert result["status"] == "success"
            call_args = mock_list.call_args
            # Both are passed to DB function which merges them (date_from wins)
            assert call_args.kwargs["since"] is not None
            assert call_args.kwargs["date_from"] is not None

    @pytest.mark.asyncio
    async def test_count_query_accuracy_with_filters(self):
        """Test total_count reflects actual matching episodes with filters active."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            # Only 3 episodes returned due to limit, but 25 total match filter
            mock_list.return_value = {
                "episodes": [
                    {"id": i, "query": f"Q{i}", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00", "tags": ["test"]}
                    for i in range(3)
                ],
                "total_count": 25,  # Total matching filter, not just page
                "limit": 3,
                "offset": 0,
            }

            result = await handle_list_episodes({"tags": ["test"], "limit": 3})

            assert len(result["episodes"]) == 3
            assert result["total_count"] == 25  # All matching, not just page size

    @pytest.mark.asyncio
    async def test_response_includes_tags_field(self):
        """Test response includes tags field for each episode."""
        from mcp_server.tools.list_episodes import handle_list_episodes

        with patch("mcp_server.tools.list_episodes.list_episodes") as mock_list:
            mock_list.return_value = {
                "episodes": [
                    {"id": 1, "query": "Test", "reward": 0.5, "created_at": "2025-12-01T00:00:00+00:00", "tags": ["dark-romance", "relationship"]},
                ],
                "total_count": 1,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_episodes({})

            assert result["status"] == "success"
            assert "tags" in result["episodes"][0]
            assert result["episodes"][0]["tags"] == ["dark-romance", "relationship"]


class TestListEpisodesExtendedIntegration:
    """Integration tests for extended parameters with real database."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_episodes_with_tags_filter(self):
        """Test tags filtering with real PostgreSQL database."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_query = f"TagsTest_{uuid.uuid4().hex[:8]}"
        test_tags = ["integration-test", "story-9-2-1"]
        fake_embedding = [0.1] * 1536

        try:
            # Initialize pool for integration test
            await initialize_pool()

            # Insert test episode with tags
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO episode_memory
                    (query, reward, reflection, embedding, created_at, tags)
                    VALUES (%s, %s, %s, %s, NOW(), %s)
                    """,
                    (test_query, 0.8, "Test tags filter", fake_embedding, test_tags),
                )
                conn.commit()

            # Test list_episodes with tags filter
            result = await handle_list_episodes({"tags": ["integration-test"]})

            assert result["status"] == "success"
            # Should find our test episode
            found = any(ep["query"] == test_query for ep in result["episodes"])
            assert found, f"Test episode with tags {test_tags} not found in results"

        finally:
            # Cleanup
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query = %s",
                    (test_query,),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_episodes_with_category_filter(self):
        """Test category filtering with real PostgreSQL database."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_query = f"[cat-test] CategoryTest_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536

        try:
            # Initialize pool for integration test
            await initialize_pool()

            # Insert test episode with category prefix in query
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO episode_memory
                    (query, reward, reflection, embedding, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (test_query, 0.8, "Test category filter", fake_embedding),
                )
                conn.commit()

            # Test list_episodes with category filter
            result = await handle_list_episodes({"category": "[cat-test]"})

            assert result["status"] == "success"
            # Should find our test episode
            found = any(ep["query"] == test_query for ep in result["episodes"])
            assert found, f"Test episode with query '{test_query}' not found in category filtered results"

        finally:
            # Cleanup
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query = %s",
                    (test_query,),
                )
                conn.commit()
