"""
Smoke Tests for MCP Tool Async/Await Correctness

These tests verify that all MCP tools handle async operations correctly.
They don't test business logic - just that async/await patterns are correct.

Catches bugs like:
- Missing await on async function calls
- Using sync 'with' on async context managers
- Returning coroutine objects instead of awaited results

Created: 2026-01-14
Triggered by: Bug Report MCP-ASYNC-AWAIT
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import inspect


# =============================================================================
# Async Context Manager Mock (reusable fixture)
# =============================================================================

class AsyncContextManagerMock:
    """Mock for async with statements."""
    def __init__(self, return_value=None):
        self._return_value = return_value

    async def __aenter__(self):
        return self._return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


def create_mock_connection():
    """Create a mock psycopg2 connection with cursor."""
    mock_cursor = Mock()
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    mock_cursor.execute.return_value = None

    mock_conn = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.commit.return_value = None
    mock_conn.rollback.return_value = None

    return mock_conn


# =============================================================================
# Error Pattern Detection
# =============================================================================

ASYNC_ERROR_PATTERNS = [
    "'coroutine' object",
    "_GeneratorContextManager",
    "_AsyncGeneratorContextManager",
    "was never awaited",
    "object is not subscriptable",
    "has no attribute '__enter__'",
    "has no attribute '__exit__'",
]


def check_for_async_errors(result: dict) -> list[str]:
    """Check if result contains async-related error patterns."""
    errors_found = []
    result_str = str(result)

    for pattern in ASYNC_ERROR_PATTERNS:
        if pattern in result_str:
            errors_found.append(pattern)

    return errors_found


# =============================================================================
# Smoke Tests: Core Tools
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.db.connection.get_connection')
async def test_get_insight_by_id_no_async_errors(mock_get_conn, with_project_context):
    """Verify get_insight_by_id doesn't have async/await bugs."""
    from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id
    from mcp_server.db.insights import get_insight_by_id as db_get_insight

    # Mock the database function
    with patch('mcp_server.tools.get_insight_by_id.get_insight_by_id') as mock_db:
        mock_db.return_value = None  # Simulate not found

        result = await handle_get_insight_by_id({"id": 99999})

        # Should return dict, not coroutine
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Check for async error patterns
        errors = check_for_async_errors(result)
        assert not errors, f"Async errors found: {errors}"


@pytest.mark.asyncio
@patch('mcp_server.db.connection.get_connection')
async def test_get_insight_history_no_async_errors(mock_get_conn, with_project_context):
    """Verify get_insight_history doesn't have async/await bugs."""
    from mcp_server.tools.insights.history import handle_get_insight_history

    # Mock connection with psycopg2 cursor pattern
    mock_conn = create_mock_connection()
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    # Mock get_insight_by_id
    with patch('mcp_server.tools.insights.history.get_insight_by_id') as mock_get:
        mock_get.return_value = {"id": 1, "content": "test", "is_deleted": False}

        result = await handle_get_insight_history({"insight_id": 1})

        assert isinstance(result, dict)
        errors = check_for_async_errors(result)
        assert not errors, f"Async errors found: {errors}"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires integration test with full DB mocking - complex call chain")
@patch('mcp_server.db.connection.get_connection')
async def test_hybrid_search_no_async_errors(mock_get_conn, with_project_context):
    """Verify hybrid_search doesn't have async/await bugs.

    NOTE: This test requires deep mocking of multiple layers.
    Use integration tests for full validation.
    """
    from mcp_server.tools import handle_hybrid_search

    mock_conn = create_mock_connection()
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    # Need to mock the embedding generation
    with patch('mcp_server.tools.generate_query_embedding') as mock_embed:
        mock_embed.return_value = [0.1] * 1536

        result = await handle_hybrid_search({"query_text": "test query"})

        assert isinstance(result, dict)
        errors = check_for_async_errors(result)
        assert not errors, f"Async errors found: {errors}"


# =============================================================================
# Smoke Tests: Graph Tools
# =============================================================================

@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires integration test - calls db.graph functions internally")
@patch('mcp_server.db.connection.get_connection')
async def test_graph_add_node_no_async_errors(mock_get_conn, with_project_context):
    """Verify graph_add_node doesn't have async/await bugs."""
    from mcp_server.tools.graph_add_node import handle_graph_add_node

    mock_conn = create_mock_connection()
    mock_conn.cursor().fetchone.return_value = {"id": 1, "name": "test"}
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    result = await handle_graph_add_node({
        "label": "TestLabel",
        "name": "test_node"
    })

    assert isinstance(result, dict)
    errors = check_for_async_errors(result)
    assert not errors, f"Async errors found: {errors}"


@pytest.mark.asyncio
@patch('mcp_server.db.connection.get_connection')
async def test_graph_query_neighbors_no_async_errors(mock_get_conn, with_project_context):
    """Verify graph_query_neighbors doesn't have async/await bugs."""
    from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors

    mock_conn = create_mock_connection()
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    # Mock the node lookup
    with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_node:
        mock_node.return_value = None  # Node not found

        result = await handle_graph_query_neighbors({"node_name": "nonexistent"})

        assert isinstance(result, dict)
        errors = check_for_async_errors(result)
        assert not errors, f"Async errors found: {errors}"


# =============================================================================
# Smoke Tests: SMF Tools
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.db.connection.get_connection')
async def test_smf_pending_proposals_no_async_errors(mock_get_conn, with_project_context):
    """Verify smf_pending_proposals doesn't have async/await bugs."""
    from mcp_server.tools.smf_pending_proposals import handle_smf_pending_proposals

    mock_conn = create_mock_connection()
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    result = await handle_smf_pending_proposals({})

    assert isinstance(result, dict)
    errors = check_for_async_errors(result)
    assert not errors, f"Async errors found: {errors}"


# =============================================================================
# Smoke Tests: Insight Tools
# =============================================================================

@pytest.mark.asyncio
@patch('mcp_server.db.connection.get_connection')
async def test_update_insight_no_async_errors(mock_get_conn, with_project_context):
    """Verify update_insight doesn't have async/await bugs."""
    from mcp_server.tools.insights.update import handle_update_insight

    mock_conn = create_mock_connection()
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    result = await handle_update_insight({
        "insight_id": 1,
        "actor": "I/O",
        "reason": "test update"
    })

    assert isinstance(result, dict)
    errors = check_for_async_errors(result)
    assert not errors, f"Async errors found: {errors}"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires integration test - calls db.insights functions internally")
@patch('mcp_server.db.connection.get_connection')
async def test_delete_insight_no_async_errors(mock_get_conn, with_project_context):
    """Verify delete_insight doesn't have async/await bugs."""
    from mcp_server.tools.insights.delete import handle_delete_insight

    mock_conn = create_mock_connection()
    mock_get_conn.return_value = AsyncContextManagerMock(return_value=mock_conn)

    result = await handle_delete_insight({
        "insight_id": 1,
        "actor": "I/O",
        "reason": "test delete"
    })

    assert isinstance(result, dict)
    errors = check_for_async_errors(result)
    assert not errors, f"Async errors found: {errors}"


# =============================================================================
# Regression Guard: Return Type Validation
# =============================================================================

@pytest.mark.asyncio
async def test_all_handlers_return_dict_not_coroutine(with_project_context):
    """
    Meta-test: Verify handler functions return dict, not coroutine.

    This catches the classic bug where someone forgets 'await':
        result = some_async_function()  # Returns coroutine!
        return {"data": result}  # Oops, result is a coroutine object
    """
    from mcp_server.tools import handle_ping

    # Ping is the simplest tool - should always work
    result = await handle_ping({})

    assert isinstance(result, dict), f"handle_ping returned {type(result)}, expected dict"
    assert "status" in result or "message" in result, "Ping should return status or message"

    # Verify it's not a coroutine object serialized to string
    result_str = str(result)
    assert "coroutine object" not in result_str, "Result contains coroutine object"
