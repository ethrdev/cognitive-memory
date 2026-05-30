"""
Tests for fuzzy_search_node_by_name database function.

Tests pg_trgm word_similarity search functionality including:
- Fuzzy name matching with various thresholds
- Limit parameter behavior
- Empty result handling
- Error handling

Story 8-5: Added fuzzy_search_node_by_name for node name suggestions.
Fix 2026-02-12: Helps callers find nodes without knowing exact names.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from mcp_server.db.graph import fuzzy_search_node_by_name


def _create_async_connection_mock(fetch_result=None):
    """
    Helper to create a properly mocked async connection.

    psycopg2 connection is SYNC, but context manager is ASYNC.
    The async context manager wraps the sync psycopg2 connection.
    """
    # Sync psycopg2 cursor (DictCursor)
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = fetch_result or []

    # Sync psycopg2 connection
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Async context manager wrapper
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = mock_conn  # Returns sync conn
    async_cm.__aexit__.return_value = None

    return async_cm, mock_cursor


class TestFuzzySearchNodeByName:
    """Test suite for fuzzy_search_node_by_name function."""

    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_fuzzy_search_basic(self, mock_get_conn):
        """Test basic fuzzy search with partial name match."""
        # Arrange
        async_cm, mock_cursor = _create_async_connection_mock([
            {
                "id": "node-1-uuid",
                "label": "Technology",
                "name": "Python",
                "properties": {"type": "language"},
                "vector_id": 1,
                "created_at": datetime(2025, 11, 27, 12, 0, 0, tzinfo=timezone.utc),
                "project_id": "default-project",
                "similarity": 0.8,
            },
            {
                "id": "node-2-uuid",
                "label": "Technology",
                "name": "PyTorch",
                "properties": {"type": "framework"},
                "vector_id": 2,
                "created_at": datetime(2025, 11, 27, 13, 0, 0, tzinfo=timezone.utc),
                "project_id": "default-project",
                "similarity": 0.6,
            },
        ])
        mock_get_conn.return_value = async_cm

        # Act
        result = await fuzzy_search_node_by_name("Pythn", limit=5, threshold=0.3)

        # Assert
        assert len(result) == 2
        assert result[0]["name"] == "Python"
        assert result[0]["similarity"] == 0.8
        assert result[1]["name"] == "PyTorch"
        assert result[1]["similarity"] == 0.6

    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_fuzzy_search_empty_results(self, mock_get_conn):
        """Test fuzzy search when no matches found."""
        # Arrange
        async_cm, _ = _create_async_connection_mock([])
        mock_get_conn.return_value = async_cm

        # Act
        result = await fuzzy_search_node_by_name("NonExistentNode", limit=5)

        # Assert
        assert result == []

    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_fuzzy_search_limit_parameter(self, mock_get_conn):
        """Test fuzzy search with custom limit."""
        # Arrange
        async_cm, _ = _create_async_connection_mock([
            {
                "id": f"node-{i}-uuid",
                "label": "Technology",
                "name": f"Python{i}",
                "properties": {},
                "vector_id": i,
                "created_at": datetime(2025, 11, 27, 12, 0, 0, tzinfo=timezone.utc),
                "project_id": "default-project",
                "similarity": 0.9 - (i * 0.1),
            }
            for i in range(3)
        ])
        mock_get_conn.return_value = async_cm

        # Act
        result = await fuzzy_search_node_by_name("Python", limit=3)

        # Assert
        assert len(result) == 3

    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_fuzzy_search_threshold_parameter(self, mock_get_conn):
        """Test fuzzy search with custom threshold."""
        # Arrange
        async_cm, _ = _create_async_connection_mock([
            {
                "id": "node-1-uuid",
                "label": "Technology",
                "name": "Python",
                "properties": {},
                "vector_id": 1,
                "created_at": datetime(2025, 11, 27, 12, 0, 0, tzinfo=timezone.utc),
                "project_id": "default-project",
                "similarity": 0.7,
            }
        ])
        mock_get_conn.return_value = async_cm

        # Act
        result = await fuzzy_search_node_by_name("Pythn", threshold=0.5)

        # Assert
        assert len(result) == 1

    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_fuzzy_search_sorted_by_similarity(self, mock_get_conn):
        """Test that results are sorted by similarity DESC."""
        # Arrange
        async_cm, _ = _create_async_connection_mock([
            {
                "id": "node-1-uuid",
                "label": "Technology",
                "name": "Python",
                "properties": {},
                "vector_id": 1,
                "created_at": datetime(2025, 11, 27, 12, 0, 0, tzinfo=timezone.utc),
                "project_id": "default-project",
                "similarity": 0.9,
            },
            {
                "id": "node-2-uuid",
                "label": "Technology",
                "name": "Pytho",
                "properties": {},
                "vector_id": 2,
                "created_at": datetime(2025, 11, 27, 12, 0, 0, tzinfo=timezone.utc),
                "project_id": "default-project",
                "similarity": 0.6,
            },
        ])
        mock_get_conn.return_value = async_cm

        # Act
        result = await fuzzy_search_node_by_name("Python", limit=5)

        # Assert
        assert len(result) == 2
        assert result[0]["similarity"] >= result[1]["similarity"]

    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_fuzzy_search_error_handling(self, mock_get_conn):
        """Test fuzzy search error handling returns empty list."""
        # Arrange
        mock_conn = MagicMock()
        mock_conn.cursor.side_effect = Exception("Database error")

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        # Act
        result = await fuzzy_search_node_by_name("Python")

        # Assert
        assert result == []

    @patch("mcp_server.db.graph.get_connection_with_project_context")
    async def test_fuzzy_search_response_structure(self, mock_get_conn):
        """Test complete response structure validation."""
        # Arrange
        async_cm, _ = _create_async_connection_mock([
            {
                "id": "node-1-uuid",
                "label": "Technology",
                "name": "Python",
                "properties": {"type": "language"},
                "vector_id": 1,
                "created_at": datetime(2025, 11, 27, 12, 0, 0, tzinfo=timezone.utc),
                "project_id": "default-project",
                "similarity": 0.8,
            }
        ])
        mock_get_conn.return_value = async_cm

        # Act
        result = await fuzzy_search_node_by_name("Python")

        # Assert
        node = result[0]
        assert "id" in node
        assert "label" in node
        assert "name" in node
        assert "properties" in node
        assert "vector_id" in node
        assert "created_at" in node
        assert "project_id" in node
        assert "similarity" in node
        assert isinstance(node["similarity"], float)
