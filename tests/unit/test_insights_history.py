"""
Unit Tests for get_insight_history MCP Tool

Tests for Story 26.7: Revision History (Stretch Goal).
Covers parameter validation and error handling (unit-testable logic).

Database-dependent tests are in integration tests.

Author: Epic 26 Implementation
Story: 26.7 - Revision History
Date: 2026-01-10
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock


# =============================================================================
# Import
# =============================================================================

from mcp_server.tools.insights.history import handle_get_insight_history


# =============================================================================
# Helper: Async Context Manager Mock
# =============================================================================

class AsyncContextManagerMock:
    """Helper for mocking async with statements."""
    def __init__(self, return_value=None):
        self._return_value = return_value
        self._exit_value = None

    async def __aenter__(self):
        return self._return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self._exit_value


# =============================================================================
# Parameter Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_insight_id_required():
    """Test that insight_id parameter is required."""
    result = await handle_get_insight_history({})

    assert "error" in result
    assert result["error"]["code"] == 400
    assert result["error"]["message"] == "insight_id is required"
    assert result["error"]["field"] == "insight_id"


@pytest.mark.asyncio
async def test_insight_id_must_be_positive_integer():
    """Test that insight_id must be a positive integer."""
    result = await handle_get_insight_history({"insight_id": 0})

    assert "error" in result
    assert result["error"]["code"] == 400
    assert "positive integer" in result["error"]["message"]


@pytest.mark.asyncio
async def test_insight_id_must_be_integer():
    """Test that insight_id must be an integer type."""
    result = await handle_get_insight_history({"insight_id": "not-an-int"})

    assert "error" in result
    assert result["error"]["code"] == 400


@pytest.mark.asyncio
async def test_insight_id_must_be_positive():
    """Test that insight_id must be > 0."""
    result = await handle_get_insight_history({"insight_id": -1})

    assert "error" in result
    assert result["error"]["code"] == 400
    assert "positive integer" in result["error"]["message"]


# =============================================================================
# NotFound Error Tests (EP-5)
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.history.get_insight_by_id')
async def test_insight_not_found_error(mock_get_insight):
    """Test that 404 error is returned for non-existent insight."""
    mock_get_insight.return_value = None

    result = await handle_get_insight_history({"insight_id": 999})

    assert "error" in result
    assert result["error"]["code"] == 404
    assert "not found" in result["error"]["message"].lower()


# =============================================================================
# Database Error Handling Tests
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.history.get_insight_by_id')
async def test_database_connection_error(mock_get_insight):
    """Test graceful handling of database connection errors."""
    mock_get_insight.side_effect = Exception("Connection failed")

    result = await handle_get_insight_history({"insight_id": 42})

    assert "error" in result
    assert result["error"]["code"] == 500


# =============================================================================
# Tool Metadata Tests
# =============================================================================

def test_tool_metadata_exists():
    """Test that tool metadata is properly defined."""
    from mcp_server.tools.insights.history import (
        TOOL_NAME,
        TOOL_DESCRIPTION,
        TOOL_INPUT_SCHEMA
    )

    assert TOOL_NAME == "get_insight_history"
    assert isinstance(TOOL_DESCRIPTION, str)
    assert len(TOOL_DESCRIPTION) > 0
    assert TOOL_INPUT_SCHEMA is not None
    assert TOOL_INPUT_SCHEMA["type"] == "object"
    assert "insight_id" in TOOL_INPUT_SCHEMA["properties"]
    assert "insight_id" in TOOL_INPUT_SCHEMA["required"]


def test_tool_schema_matches_specification():
    """Test that tool schema matches Story 26.7 specification."""
    from mcp_server.tools.insights.history import TOOL_INPUT_SCHEMA

    # Verify schema structure
    assert "properties" in TOOL_INPUT_SCHEMA
    properties = TOOL_INPUT_SCHEMA["properties"]

    # Verify insight_id property
    assert "insight_id" in properties
    insight_id_schema = properties["insight_id"]
    assert insight_id_schema["type"] == "integer"
    assert insight_id_schema["description"] is not None
    assert insight_id_schema["minimum"] == 1

    # Verify required fields
    assert "insight_id" in TOOL_INPUT_SCHEMA["required"]


# =============================================================================
# Response Structure Tests (with mocked data)
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.tools.insights.history.get_insight_by_id')
@patch('mcp_server.db.connection.get_connection')
async def test_response_format_matches_specification(mock_get_conn, mock_get_insight):
    """Test that response format matches Story 26.7 specification."""
    # Mock insight
    mock_get_insight.return_value = {
        "id": 42,
        "content": "Current content",
        "is_deleted": False
    }

    # Mock database connection with psycopg2 cursor pattern
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    result = await handle_get_insight_history({"insight_id": 42})

    # Verify top-level response structure
    assert isinstance(result, dict)
    assert set(result.keys()) == {"insight_id", "current_content", "is_deleted", "history", "total_revisions"}

    # Verify types
    assert isinstance(result["insight_id"], int)
    assert isinstance(result["current_content"], (str, type(None)))
    assert isinstance(result["is_deleted"], bool)
    assert isinstance(result["history"], list)
    assert isinstance(result["total_revisions"], int)


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.history.get_insight_by_id')
@patch('mcp_server.db.connection.get_connection')
async def test_empty_history_returns_empty_array(mock_get_conn, mock_get_insight):
    """Test that insights without history return empty array (not error)."""
    mock_get_insight.return_value = {
        "id": 42,
        "content": "Untouched content",
        "is_deleted": False
    }

    # No history entries - psycopg2 cursor pattern
    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = []
    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    result = await handle_get_insight_history({"insight_id": 42})

    # Should return success, not error
    assert "error" not in result
    assert result["history"] == []
    assert result["total_revisions"] == 0
    assert result["current_content"] == "Untouched content"


@pytest.mark.asyncio
@patch('mcp_server.tools.insights.history.get_insight_by_id')
@patch('mcp_server.db.connection.get_connection')
async def test_deleted_insight_preserves_history_accessibility(mock_get_conn, mock_get_insight):
    """Test that deleted insights still return history (Archäologie-Prinzip)."""
    # Mock deleted insight
    mock_get_insight.return_value = {
        "id": 42,
        "content": "Deleted content",
        "is_deleted": True
    }

    # History exists - psycopg2 cursor pattern
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    mock_cursor = Mock()
    mock_cursor.fetchall.return_value = [
        {
            "version_id": 1,
            "previous_content": "Before deletion",
            "previous_memory_strength": 0.7,
            "changed_at": now,
            "changed_by": "I/O",
            "change_reason": "Before delete"
        }
    ]
    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    result = await handle_get_insight_history({"insight_id": 42})

    # Verify Archäologie-Prinzip: History preserved even though deleted
    assert result["is_deleted"] is True
    assert result["current_content"] is None  # No current content for deleted
    assert len(result["history"]) == 1  # History still available
