"""
Unit tests for hybrid-search-fix implementations.

Tests for:
- Fix 1: date_from/date_to string parsing in handle_hybrid_search
- Fix 2: tags_filter + sector_filter for episode searches
- Fix 3: graph_update_node tool handler + update_node_properties
- Empty list semantics (tags_filter=[], sector_filter=[])

Created: 2026-02-11 (hybrid-search-fix code review)
"""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest


# =============================================================================
# Fix 1: Date String Parsing Tests
# =============================================================================


class TestDateStringParsing:
    """Tests for ISO date string → datetime parsing in handle_hybrid_search."""

    @pytest.mark.asyncio
    async def test_date_from_iso_string_parsed(self):
        """date_from as ISO string should be parsed to datetime."""
        from mcp_server.tools import handle_hybrid_search

        with patch(
            "mcp_server.tools.generate_query_embedding",
            return_value=[0.1] * 1536,
        ), patch(
            "mcp_server.tools.get_connection_with_project_context",
        ) as mock_conn_ctx:
            # Make the connection context raise early so we can check parsing
            mock_conn_ctx.side_effect = RuntimeError("Stop after parsing")

            result = await handle_hybrid_search({
                "query_text": "test",
                "date_from": "2026-02-01",
            })

            # If date was parsed correctly, it should NOT return a validation error
            # It will fail at the connection step — not at date parsing
            if "error" in result:
                assert "Invalid date_from format" not in result.get("details", "")

    @pytest.mark.asyncio
    async def test_date_from_invalid_string_returns_error(self):
        """Invalid date_from string should return clear error."""
        from mcp_server.tools import handle_hybrid_search

        result = await handle_hybrid_search({
            "query_text": "test",
            "date_from": "not-a-date",
        })

        assert "error" in result
        assert "Invalid date_from format" in result["details"]
        assert "not-a-date" in result["details"]

    @pytest.mark.asyncio
    async def test_date_to_invalid_string_returns_error(self):
        """Invalid date_to string should return clear error."""
        from mcp_server.tools import handle_hybrid_search

        result = await handle_hybrid_search({
            "query_text": "test",
            "date_to": "2026-13-99",
        })

        assert "error" in result
        assert "Invalid date_to format" in result["details"]

    @pytest.mark.asyncio
    async def test_date_from_datetime_passthrough(self):
        """datetime objects should pass through unchanged."""
        from mcp_server.tools import handle_hybrid_search

        dt = datetime(2026, 2, 1)
        with patch(
            "mcp_server.tools.generate_query_embedding",
            return_value=[0.1] * 1536,
        ), patch(
            "mcp_server.tools.get_connection_with_project_context",
        ) as mock_conn_ctx:
            mock_conn_ctx.side_effect = RuntimeError("Stop after parsing")

            result = await handle_hybrid_search({
                "query_text": "test",
                "date_from": dt,
            })

            if "error" in result:
                assert "Invalid date_from format" not in result.get("details", "")

    @pytest.mark.asyncio
    async def test_date_from_iso_with_time_parsed(self):
        """ISO datetime with time component should parse correctly."""
        from mcp_server.tools import handle_hybrid_search

        with patch(
            "mcp_server.tools.generate_query_embedding",
            return_value=[0.1] * 1536,
        ), patch(
            "mcp_server.tools.get_connection_with_project_context",
        ) as mock_conn_ctx:
            mock_conn_ctx.side_effect = RuntimeError("Stop after parsing")

            result = await handle_hybrid_search({
                "query_text": "test",
                "date_from": "2026-02-01T14:30:00",
            })

            if "error" in result:
                assert "Invalid date_from format" not in result.get("details", "")


# =============================================================================
# Fix 2: Episode Search Filter Tests (unit-level, no DB)
# =============================================================================


class TestEpisodeSearchFilters:
    """Tests for tags_filter and sector_filter in episode search functions."""

    def _make_mock_conn(self, results: list[dict] | None = None):
        """Create mock connection returning given results."""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = results or []
        mock_cursor.execute.return_value = None

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn, mock_cursor

    def test_episode_semantic_no_filters(self):
        """episode_semantic_search without filters generates clean SQL."""
        from mcp_server.tools import episode_semantic_search

        conn, cursor = self._make_mock_conn()

        with patch("mcp_server.tools.register_vector"):
            episode_semantic_search(
                query_embedding=[0.1] * 1536,
                top_k=5,
                conn=conn,
            )

        sql = cursor.execute.call_args[0][0]
        assert "tags @>" not in sql
        assert "memory_sector" not in sql
        assert "AND FALSE" not in sql

    def test_episode_semantic_with_tags_filter(self):
        """tags_filter should add GIN containment clause."""
        from mcp_server.tools import episode_semantic_search

        conn, cursor = self._make_mock_conn()

        with patch("mcp_server.tools.register_vector"):
            episode_semantic_search(
                query_embedding=[0.1] * 1536,
                top_k=5,
                conn=conn,
                tags_filter=["dark-romance"],
            )

        sql = cursor.execute.call_args[0][0]
        assert "tags @> %s::text[]" in sql
        params = cursor.execute.call_args[0][1]
        assert ["dark-romance"] in params

    def test_episode_semantic_empty_tags_returns_nothing(self):
        """tags_filter=[] should add AND FALSE clause."""
        from mcp_server.tools import episode_semantic_search

        conn, cursor = self._make_mock_conn()

        with patch("mcp_server.tools.register_vector"):
            episode_semantic_search(
                query_embedding=[0.1] * 1536,
                top_k=5,
                conn=conn,
                tags_filter=[],
            )

        sql = cursor.execute.call_args[0][0]
        assert "AND FALSE" in sql

    def test_episode_semantic_with_sector_filter(self):
        """sector_filter should add NULL-safe metadata check."""
        from mcp_server.tools import episode_semantic_search

        conn, cursor = self._make_mock_conn()

        with patch("mcp_server.tools.register_vector"):
            episode_semantic_search(
                query_embedding=[0.1] * 1536,
                top_k=5,
                conn=conn,
                sector_filter=["emotional"],
            )

        sql = cursor.execute.call_args[0][0]
        assert "metadata->>'memory_sector'" in sql
        assert "IS NULL" in sql

    def test_episode_semantic_empty_sector_returns_nothing(self):
        """sector_filter=[] should add AND FALSE clause."""
        from mcp_server.tools import episode_semantic_search

        conn, cursor = self._make_mock_conn()

        with patch("mcp_server.tools.register_vector"):
            episode_semantic_search(
                query_embedding=[0.1] * 1536,
                top_k=5,
                conn=conn,
                sector_filter=[],
            )

        sql = cursor.execute.call_args[0][0]
        assert "AND FALSE" in sql

    def test_episode_keyword_with_tags_filter(self):
        """tags_filter should work in keyword search too."""
        from mcp_server.tools import episode_keyword_search

        conn, cursor = self._make_mock_conn()

        episode_keyword_search(
            query_text="test query",
            top_k=5,
            conn=conn,
            tags_filter=["cognitive-memory"],
        )

        sql = cursor.execute.call_args[0][0]
        assert "tags @> %s::text[]" in sql

    def test_episode_keyword_empty_tags_returns_nothing(self):
        """tags_filter=[] in keyword search should add AND FALSE."""
        from mcp_server.tools import episode_keyword_search

        conn, cursor = self._make_mock_conn()

        episode_keyword_search(
            query_text="test query",
            top_k=5,
            conn=conn,
            tags_filter=[],
        )

        sql = cursor.execute.call_args[0][0]
        assert "AND FALSE" in sql

    def test_episode_keyword_none_tags_no_filter(self):
        """tags_filter=None should not add any filter clause."""
        from mcp_server.tools import episode_keyword_search

        conn, cursor = self._make_mock_conn()

        episode_keyword_search(
            query_text="test query",
            top_k=5,
            conn=conn,
            tags_filter=None,
        )

        sql = cursor.execute.call_args[0][0]
        assert "tags @>" not in sql
        assert "AND FALSE" not in sql


# =============================================================================
# Fix 3: graph_update_node Handler Tests
# =============================================================================


class TestGraphUpdateNodeValidation:
    """Tests for graph_update_node parameter validation."""

    @pytest.mark.asyncio
    async def test_missing_name_returns_error(self):
        """Missing name parameter should return validation error."""
        from mcp_server.tools.graph_update_node import handle_graph_update_node

        with patch("mcp_server.tools.graph_update_node.get_current_project", return_value="test"):
            result = await handle_graph_update_node({"vector_id": 5})

        assert "error" in result
        assert "name" in result["details"]

    @pytest.mark.asyncio
    async def test_empty_name_returns_error(self):
        """Empty string name should return validation error."""
        from mcp_server.tools.graph_update_node import handle_graph_update_node

        with patch("mcp_server.tools.graph_update_node.get_current_project", return_value="test"):
            result = await handle_graph_update_node({"name": "", "vector_id": 5})

        assert "error" in result

    @pytest.mark.asyncio
    async def test_no_update_params_returns_error(self):
        """Neither properties nor vector_id should return error."""
        from mcp_server.tools.graph_update_node import handle_graph_update_node

        with patch("mcp_server.tools.graph_update_node.get_current_project", return_value="test"):
            result = await handle_graph_update_node({"name": "TestNode"})

        assert "error" in result
        assert "At least one" in result["details"]

    @pytest.mark.asyncio
    async def test_invalid_vector_id_returns_error(self):
        """Negative vector_id should return validation error."""
        from mcp_server.tools.graph_update_node import handle_graph_update_node

        with patch("mcp_server.tools.graph_update_node.get_current_project", return_value="test"):
            result = await handle_graph_update_node({
                "name": "TestNode",
                "vector_id": -1,
            })

        assert "error" in result
        assert "vector_id" in result["details"]

    @pytest.mark.asyncio
    async def test_zero_vector_id_returns_error(self):
        """vector_id=0 should return validation error (must be positive)."""
        from mcp_server.tools.graph_update_node import handle_graph_update_node

        with patch("mcp_server.tools.graph_update_node.get_current_project", return_value="test"):
            result = await handle_graph_update_node({
                "name": "TestNode",
                "vector_id": 0,
            })

        assert "error" in result

    @pytest.mark.asyncio
    async def test_invalid_properties_type_returns_error(self):
        """Non-dict properties should return validation error."""
        from mcp_server.tools.graph_update_node import handle_graph_update_node

        with patch("mcp_server.tools.graph_update_node.get_current_project", return_value="test"):
            result = await handle_graph_update_node({
                "name": "TestNode",
                "properties": "not-a-dict",
            })

        assert "error" in result
        assert "properties" in result["details"]

    @pytest.mark.asyncio
    async def test_node_not_found_returns_error(self):
        """Non-existent node should return not-found error."""
        from mcp_server.tools.graph_update_node import handle_graph_update_node

        with patch("mcp_server.tools.graph_update_node.get_current_project", return_value="test"), \
             patch("mcp_server.tools.graph_update_node.get_node_by_name", new_callable=AsyncMock, return_value=None):
            result = await handle_graph_update_node({
                "name": "NonExistent",
                "vector_id": 5,
            })

        assert "error" in result
        assert "no node" in result["details"].lower()

    @pytest.mark.asyncio
    async def test_successful_update_returns_success(self):
        """Successful update should return status=success."""
        from mcp_server.tools.graph_update_node import handle_graph_update_node

        mock_node = {"id": "abc-123", "name": "TestNode", "label": "Entity"}
        mock_result = {
            "id": "abc-123",
            "name": "TestNode",
            "label": "Entity",
            "properties": {"key": "value"},
            "vector_id": 5,
            "created_at": "2026-02-11T00:00:00",
        }

        with patch("mcp_server.tools.graph_update_node.get_current_project", return_value="test"), \
             patch("mcp_server.tools.graph_update_node.get_node_by_name", new_callable=AsyncMock, return_value=mock_node), \
             patch("mcp_server.tools.graph_update_node.update_node_properties", new_callable=AsyncMock, return_value=mock_result):
            result = await handle_graph_update_node({
                "name": "TestNode",
                "vector_id": 5,
            })

        assert result["status"] == "success"
        assert result["vector_id"] == 5
        assert result["name"] == "TestNode"


# =============================================================================
# Fix 3: update_node_properties DB Function Tests
# =============================================================================


class TestUpdateNodePropertiesSignature:
    """Tests for the extended update_node_properties function signature."""

    @pytest.mark.asyncio
    async def test_raises_on_no_params(self):
        """Should raise ValueError if neither properties nor vector_id given."""
        from mcp_server.db.graph import update_node_properties

        with pytest.raises(ValueError, match="At least one"):
            await update_node_properties("some-uuid")

    @pytest.mark.asyncio
    async def test_raises_on_explicit_none_params(self):
        """Should raise ValueError with explicit None for both."""
        from mcp_server.db.graph import update_node_properties

        with pytest.raises(ValueError, match="At least one"):
            await update_node_properties("some-uuid", new_properties=None, vector_id=None)
