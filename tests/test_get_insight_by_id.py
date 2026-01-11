"""
Tests for get_insight_by_id MCP Tool

Tests the get_insight_by_id tool implementation including:
- Successful insight retrieval by ID
- Graceful null return for non-existent IDs
- Parameter validation (missing, invalid type, negative)
- Database error handling
- Response field completeness
- No embedding in response (too large)

Story 6.5: get_insight_by_id MCP Tool
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestGetInsightByIdTool:
    """Test suite for get_insight_by_id MCP tool."""

    @pytest.mark.asyncio
    async def test_get_insight_by_id_success(self):
        """Test successful insight retrieval by ID."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        mock_insight = {
            "id": 123,
            "content": "User bevorzugt direkte Kommunikation",
            "source_ids": [1, 2, 3],
            "metadata": {"topic": "communication"},
            "created_at": "2025-12-06T14:30:00+00:00",
        }

        with patch("mcp_server.tools.get_insight_by_id.get_insight_by_id") as mock_get:
            mock_get.return_value = mock_insight

            result = await handle_get_insight_by_id({"id": 123})

            assert result["status"] == "success"
            assert result["id"] == 123
            assert result["content"] == "User bevorzugt direkte Kommunikation"
            assert result["source_ids"] == [1, 2, 3]
            assert result["metadata"] == {"topic": "communication"}
            assert result["created_at"] == "2025-12-06T14:30:00+00:00"
            mock_get.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_get_insight_by_id_not_found(self):
        """Test graceful null return when insight doesn't exist."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        with patch("mcp_server.tools.get_insight_by_id.get_insight_by_id") as mock_get:
            mock_get.return_value = None

            result = await handle_get_insight_by_id({"id": 99999})

            assert result["status"] == "not_found"
            assert result["insight"] is None
            # Graceful null - NO error field
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_get_insight_by_id_missing_id(self):
        """Test missing id parameter returns validation error."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        result = await handle_get_insight_by_id({})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert "id" in result["details"].lower()
        assert result["tool"] == "get_insight_by_id"

    @pytest.mark.asyncio
    async def test_get_insight_by_id_invalid_type_string(self):
        """Test non-integer id parameter returns validation error."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        result = await handle_get_insight_by_id({"id": "not-an-int"})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert result["tool"] == "get_insight_by_id"

    @pytest.mark.asyncio
    async def test_get_insight_by_id_invalid_negative(self):
        """Test negative id parameter returns validation error."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        result = await handle_get_insight_by_id({"id": -1})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert result["tool"] == "get_insight_by_id"

    @pytest.mark.asyncio
    async def test_get_insight_by_id_invalid_zero(self):
        """Test zero id parameter returns validation error."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        result = await handle_get_insight_by_id({"id": 0})

        assert "error" in result
        assert result["error"] == "Parameter validation failed"
        assert result["tool"] == "get_insight_by_id"

    @pytest.mark.asyncio
    async def test_get_insight_by_id_database_error(self):
        """Test database error returns structured error response."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        with patch("mcp_server.tools.get_insight_by_id.get_insight_by_id") as mock_get:
            mock_get.side_effect = Exception("Connection timeout")

            result = await handle_get_insight_by_id({"id": 123})

            assert "error" in result
            assert result["error"] == "Database operation failed"
            assert "Connection timeout" in result["details"]
            assert result["tool"] == "get_insight_by_id"

    @pytest.mark.asyncio
    async def test_get_insight_by_id_no_embedding_in_response(self):
        """Test that embedding is NOT included in response (too large)."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        mock_insight = {
            "id": 123,
            "content": "Test content",
            "source_ids": [],
            "metadata": {},
            "created_at": "2025-12-06T14:30:00+00:00",
        }

        with patch("mcp_server.tools.get_insight_by_id.get_insight_by_id") as mock_get:
            mock_get.return_value = mock_insight

            result = await handle_get_insight_by_id({"id": 123})

            assert result["status"] == "success"
            assert "embedding" not in result

    @pytest.mark.asyncio
    async def test_get_insight_by_id_response_fields_complete(self):
        """Test response contains all required fields."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        mock_insight = {
            "id": 1,
            "content": "Test",
            "source_ids": [1],
            "metadata": {},
            "created_at": "2025-12-06T00:00:00+00:00",
        }

        with patch("mcp_server.tools.get_insight_by_id.get_insight_by_id") as mock_get:
            mock_get.return_value = mock_insight

            result = await handle_get_insight_by_id({"id": 1})

            # All required fields present
            assert "id" in result
            assert "content" in result
            assert "source_ids" in result
            assert "metadata" in result
            assert "created_at" in result
            assert "status" in result
            # Status is last (dict order preserved in Python 3.7+)
            assert list(result.keys())[-1] == "status"

    @pytest.mark.asyncio
    async def test_get_insight_by_id_metadata_null_handling(self):
        """Test that null metadata returns empty dict."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        mock_insight = {
            "id": 1,
            "content": "Test",
            "source_ids": [],
            "metadata": None,  # NULL from DB
            "created_at": "2025-12-06T00:00:00+00:00",
        }

        with patch("mcp_server.tools.get_insight_by_id.get_insight_by_id") as mock_get:
            mock_get.return_value = mock_insight

            result = await handle_get_insight_by_id({"id": 1})

            assert result["status"] == "success"
            assert result["metadata"] == {}  # Empty dict, not None

    @pytest.mark.asyncio
    async def test_get_insight_by_id_source_ids_is_list(self):
        """Test that source_ids is returned as a list."""
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        mock_insight = {
            "id": 1,
            "content": "Test",
            "source_ids": [10, 20, 30],
            "metadata": {},
            "created_at": "2025-12-06T00:00:00+00:00",
        }

        with patch("mcp_server.tools.get_insight_by_id.get_insight_by_id") as mock_get:
            mock_get.return_value = mock_insight

            result = await handle_get_insight_by_id({"id": 1})

            assert isinstance(result["source_ids"], list)
            assert result["source_ids"] == [10, 20, 30]


class TestGetInsightByIdDBFunction:
    """Test suite for get_insight_by_id DB function."""

    def test_get_insight_by_id_db_function_exists(self):
        """Test that the DB function can be imported."""
        from mcp_server.db.insights import get_insight_by_id

        assert callable(get_insight_by_id)

    def test_get_insight_by_id_db_returns_dict_or_none(self):
        """Test DB function returns expected dict structure or None."""
        from mcp_server.db.insights import get_insight_by_id

        with patch("mcp_server.db.insights.get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {
                "id": 1,
                "content": "Test",
                "source_ids": [],
                "metadata": {},
                "created_at": datetime(2025, 12, 6, tzinfo=timezone.utc),
            }
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

            result = get_insight_by_id(1)

            assert isinstance(result, dict)
            assert "id" in result
            assert "content" in result
            assert "source_ids" in result
            assert "metadata" in result
            assert "created_at" in result

    def test_get_insight_by_id_db_returns_none_for_missing(self):
        """Test DB function returns None when insight not found."""
        from mcp_server.db.insights import get_insight_by_id

        with patch("mcp_server.db.insights.get_connection") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

            result = get_insight_by_id(99999)

            assert result is None


class TestGetInsightByIdIntegration:
    """Integration tests with real database."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_insight_by_id_real_db(self):
        """Test get_insight_by_id with real PostgreSQL database."""
        import json

        from mcp_server.db.connection import get_connection
        from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

        test_content = f"IntegrationTest_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536  # Required: 1536-dim vector
        test_id = None

        try:
            # Insert test insight
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO l2_insights (content, source_ids, metadata, embedding)
                    VALUES (%s, %s, %s::jsonb, %s)
                    RETURNING id
                    """,
                    (test_content, [1, 2, 3], json.dumps({"test": True}), fake_embedding),
                )
                test_id = cursor.fetchone()["id"]
                conn.commit()

            # Test get_insight_by_id
            result = await handle_get_insight_by_id({"id": test_id})

            assert result["status"] == "success"
            assert result["id"] == test_id
            assert result["content"] == test_content
            assert result["source_ids"] == [1, 2, 3]
            assert result["metadata"] == {"test": True}
            assert "created_at" in result
            assert "embedding" not in result  # Should NOT be in response

        finally:
            # Cleanup
            if test_id:
                async with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM l2_insights WHERE id = %s",
                        (test_id,),
                    )
                    conn.commit()
