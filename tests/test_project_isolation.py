"""
Tests for Cross-Project Isolation (Defense-in-Depth).

Story 11.7: Verifies that all read-path database functions include explicit
project_id filters via get_allowed_projects(), independent of RLS enforcement.

Root Cause: RLS migration_phase was 'pending' for all projects, meaning
RLS policies returned TRUE (no filtering). These explicit filters provide
defense-in-depth protection regardless of RLS mode.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_async_conn_mock(fetchone_result=None, fetchall_result=None):
    """Create async connection context manager mock."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_cursor.fetchall.return_value = fetchall_result or []

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = mock_conn
    async_cm.__aexit__.return_value = None

    return async_cm, mock_cursor


def _assert_project_filter_in_sql(mock_cursor, filter_text="get_allowed_projects"):
    """Assert that at least one executed SQL query contains the project filter."""
    calls = mock_cursor.execute.call_args_list
    assert len(calls) > 0, "No SQL queries were executed"

    for call in calls:
        sql = call[0][0] if call[0] else ""
        if filter_text in sql:
            return  # Found it

    all_sql = "\n---\n".join(
        call[0][0] if call[0] else "(no sql)" for call in calls
    )
    pytest.fail(
        f"No SQL query contained '{filter_text}'.\n"
        f"Executed queries:\n{all_sql}"
    )


class TestInsightsProjectIsolation:
    """Verify project_id filters in insights.py read functions."""

    @pytest.mark.asyncio
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_get_insight_by_id_has_project_filter(self, mock_get_conn):
        from mcp_server.db.insights import get_insight_by_id

        async_cm, mock_cursor = _make_async_conn_mock(
            fetchone_result={
                "id": 1, "content": "test", "source_ids": [1],
                "metadata": {}, "created_at": datetime.now(timezone.utc),
                "memory_strength": 0.5,
            }
        )
        mock_get_conn.return_value = async_cm

        await get_insight_by_id(1)
        _assert_project_filter_in_sql(mock_cursor)

    @pytest.mark.asyncio
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_has_project_filter(self, mock_get_conn):
        from mcp_server.db.insights import list_insights

        mock_cursor = MagicMock()
        # First call: COUNT, second call: SELECT
        mock_cursor.fetchone.return_value = {"count": 0}
        mock_cursor.fetchall.return_value = []
        # fetchone returns [0] for count query
        mock_cursor.fetchone.return_value = [0]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        await list_insights(limit=10)

        # Both COUNT and SELECT queries should have the filter
        calls = mock_cursor.execute.call_args_list
        filter_count = sum(
            1 for call in calls
            if call[0] and "get_allowed_projects" in call[0][0]
        )
        assert filter_count >= 2, (
            f"Expected project filter in both COUNT and SELECT queries, "
            f"found in {filter_count} queries"
        )

    @pytest.mark.asyncio
    @patch("mcp_server.middleware.context.get_current_project", return_value="test")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_execute_update_with_history_has_project_filter(
        self, mock_get_conn, mock_project
    ):
        from mcp_server.db.insights import execute_update_with_history

        mock_cursor = MagicMock()
        call_count = 0

        def fetchone_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": "old", "memory_strength": 0.5,
                    "project_id": "test",
                }
            return [42]  # history_id

        mock_cursor.fetchone.side_effect = fetchone_side_effect

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        await execute_update_with_history(1, new_content="new", reason="test")
        _assert_project_filter_in_sql(mock_cursor)

    @pytest.mark.asyncio
    @patch("mcp_server.middleware.context.get_current_project", return_value="test")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_execute_delete_with_history_has_project_filter(
        self, mock_get_conn, mock_project
    ):
        from mcp_server.db.insights import execute_delete_with_history

        mock_cursor = MagicMock()
        call_count = 0

        def fetchone_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": "to delete", "memory_strength": 0.5,
                    "is_deleted": False, "project_id": "test",
                }
            return [42]  # history_id

        mock_cursor.fetchone.side_effect = fetchone_side_effect

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        await execute_delete_with_history(1, reason="cleanup")
        _assert_project_filter_in_sql(mock_cursor)


class TestEpisodesProjectIsolation:
    """Verify project_id filters in episodes.py read functions."""

    @pytest.mark.asyncio
    @patch("mcp_server.db.episodes.get_connection_with_project_context")
    async def test_list_episodes_has_project_filter(self, mock_get_conn):
        from mcp_server.db.episodes import list_episodes

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = {"count": 0}

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        await list_episodes(limit=10)

        # Both data and count queries should have the filter
        calls = mock_cursor.execute.call_args_list
        filter_count = sum(
            1 for call in calls
            if call[0] and "get_allowed_projects" in call[0][0]
        )
        assert filter_count >= 2, (
            f"Expected project filter in both data and count queries, "
            f"found in {filter_count} queries"
        )


class TestStatsProjectIsolation:
    """Verify project_id filters in stats.py."""

    @pytest.mark.asyncio
    @patch("mcp_server.db.stats.get_connection_with_project_context")
    async def test_get_all_counts_has_project_filter(self, mock_get_conn):
        from mcp_server.db.stats import get_all_counts

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"type": "graph_nodes", "count": 5},
            {"type": "graph_edges", "count": 3},
            {"type": "l2_insights", "count": 10},
            {"type": "episodes", "count": 2},
            {"type": "working_memory", "count": 1},
            {"type": "raw_dialogues", "count": 0},
        ]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        result = await get_all_counts()

        # The UNION ALL query should have project filter on EACH sub-query
        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 1, "Expected single UNION ALL query"
        sql = calls[0][0][0]
        # Count occurrences of the filter - should appear 6 times (once per table)
        filter_count = sql.count("get_allowed_projects")
        assert filter_count == 6, (
            f"Expected get_allowed_projects filter 6 times (once per table), "
            f"found {filter_count} times"
        )


class TestGraphProjectIsolation:
    """Verify project_id filters in graph.py read functions."""

    @pytest.mark.asyncio
    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_get_node_by_name_has_project_filter(self, mock_get_conn):
        from mcp_server.db.graph import get_node_by_name

        async_cm, mock_cursor = _make_async_conn_mock(fetchone_result=None)
        mock_get_conn.return_value = async_cm

        await get_node_by_name("TestNode")
        _assert_project_filter_in_sql(mock_cursor)

    @pytest.mark.asyncio
    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_get_node_by_id_has_project_filter(self, mock_get_conn):
        from mcp_server.db.graph import get_node_by_id

        async_cm, mock_cursor = _make_async_conn_mock(fetchone_result=None)
        mock_get_conn.return_value = async_cm

        await get_node_by_id("00000000-0000-0000-0000-000000000001")
        _assert_project_filter_in_sql(mock_cursor)

    @pytest.mark.asyncio
    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_get_nodes_by_label_has_project_filter(self, mock_get_conn):
        from mcp_server.db.graph import get_nodes_by_label

        async_cm, mock_cursor = _make_async_conn_mock(fetchall_result=[])
        mock_get_conn.return_value = async_cm

        await get_nodes_by_label("Entity")
        _assert_project_filter_in_sql(mock_cursor)

    @pytest.mark.asyncio
    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_fuzzy_search_has_project_filter(self, mock_get_conn):
        from mcp_server.db.graph import fuzzy_search_node_by_name

        async_cm, mock_cursor = _make_async_conn_mock(fetchall_result=[])
        mock_get_conn.return_value = async_cm

        await fuzzy_search_node_by_name("Test")
        _assert_project_filter_in_sql(mock_cursor)

    @pytest.mark.asyncio
    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_get_edge_by_id_has_project_filter(self, mock_get_conn):
        from mcp_server.db.graph import get_edge_by_id

        async_cm, mock_cursor = _make_async_conn_mock(fetchone_result=None)
        mock_get_conn.return_value = async_cm

        await get_edge_by_id("00000000-0000-0000-0000-000000000001")
        _assert_project_filter_in_sql(mock_cursor)

    @pytest.mark.asyncio
    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_get_edge_by_names_has_project_filter(self, mock_get_conn):
        from mcp_server.db.graph import get_edge_by_names

        async_cm, mock_cursor = _make_async_conn_mock(fetchone_result=None)
        mock_get_conn.return_value = async_cm

        await get_edge_by_names("NodeA", "NodeB", "RELATES_TO")
        _assert_project_filter_in_sql(mock_cursor)

    @pytest.mark.asyncio
    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_query_neighbors_has_project_filter(self, mock_get_conn):
        from mcp_server.db.graph import query_neighbors

        async_cm, mock_cursor = _make_async_conn_mock(fetchall_result=[])
        mock_get_conn.return_value = async_cm

        await query_neighbors("00000000-0000-0000-0000-000000000001")

        # CTE query should have project filter in each edge query block
        calls = mock_cursor.execute.call_args_list
        assert len(calls) >= 1
        sql = calls[0][0][0]
        # Should appear at least 4 times (outgoing base, outgoing rec, incoming base, incoming rec)
        filter_count = sql.count("get_allowed_projects")
        assert filter_count >= 4, (
            f"Expected get_allowed_projects filter at least 4 times in CTE, "
            f"found {filter_count} times"
        )
