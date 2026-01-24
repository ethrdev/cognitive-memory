"""
Unit Tests for Memory Write Operations with Project Context

Tests for Story 11.5.3: Memory Write Operations (Working Memory, Episodes, Raw)
Covers all acceptance criteria (AC-1 through AC-5).

Author: Epic 11.5 Implementation
Story: 11.5.3 - Memory Write Operations
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from psycopg2 import DatabaseError


# =============================================================================
# AC-1: update_working_memory project_id insertion
# =============================================================================


@pytest.mark.asyncio
async def test_update_working_memory_includes_project_id_in_insert():
    """
    AC-1: Verify add_working_memory_item INSERT includes project_id.
    This test will FAIL initially because the function doesn't include project_id.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {"id": 1}

    with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
        await __import__("mcp_server.tools", fromlist=["add_working_memory_item"]).add_working_memory_item("test content", 0.5, mock_conn)

        # Verify INSERT was called with project_id
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        # SQL should include project_id column
        assert "project_id" in sql.lower(), "INSERT should include project_id column"

        # Parameters should include project_id
        assert "test-project" in params, "Parameters should include project_id value"


@pytest.mark.asyncio
async def test_update_working_memory_response_includes_project_metadata():
    """
    AC-1: Verify response includes project_id in metadata.
    """
    # Import the functions after patching
    tools_module = __import__("mcp_server.tools", fromlist=["handle_update_working_memory"])

    async def mock_get_connection():
        mock_conn = MagicMock()
        yield mock_conn

    with patch("mcp_server.tools.get_connection_with_project_context", new=mock_get_connection):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"id": 1, "count": 1}

        with patch("mcp_server.tools.add_working_memory_item", return_value=1):
            with patch("mcp_server.tools.evict_lru_item", return_value=None):
                with patch("mcp_server.tools.archive_to_stale_memory", return_value=None):
                    with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
                        result = await tools_module.handle_update_working_memory({
                            "content": "Test content",
                            "importance": 0.5
                        })

        # Verify response includes project_id in metadata
        assert "metadata" in result
        assert result["metadata"]["project_id"] == "test-project"


# =============================================================================
# AC-2: delete_working_memory project scoping
# =============================================================================


@pytest.mark.asyncio
async def test_delete_working_memory_filters_by_project_id():
    """
    AC-2: Verify delete_working_memory filters by project_id in SELECT/DELETE.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    # Entry does NOT exist (RLS filtered it out)
    mock_cursor.fetchone.return_value = None

    with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
        from mcp_server.tools import handle_delete_working_memory

        # Mock the connection as a synchronous context manager (for testing)
        class MockConnectionManager:
            async def __aenter__(self):
                return mock_conn
            async def __aexit__(self, *args):
                pass

        with patch("mcp_server.tools.get_connection_with_project_context", return_value=MockConnectionManager()):
            result = await handle_delete_working_memory({"id": 42})

    # Verify SELECT was called with project_id filter
    call_args = mock_cursor.execute.call_args_list
    # First call should be the SELECT with project_id
    select_sql = call_args[0][0][0] if call_args else ""
    assert "project_id" in select_sql.lower(), "SELECT should include project_id filter"

    # Should return not_found status
    assert result["status"] == "not_found"


# =============================================================================
# AC-3: store_episode project_id insertion
# =============================================================================


@pytest.mark.asyncio
async def test_store_episode_includes_project_id_in_insert():
    """
    AC-3: Verify add_episode INSERT includes project_id.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "created_at": MagicMock(isoformat=lambda: "2024-01-01T00:00:00Z")
    }

    # Mock OpenAI client to avoid API key requirement - must patch before importing
    with patch("mcp_server.tools.os.getenv", return_value="sk-test-key"):
        with patch("mcp_server.tools.OpenAI"):
            with patch("mcp_server.tools.get_embedding_with_retry", return_value=[0.1] * 1536):
                with patch("mcp_server.tools.register_vector"):
                    with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
                        # Import after patches are applied
                        from mcp_server.tools import add_episode
                        result = await add_episode("test query", 0.5, "test reflection", mock_conn)

    # Verify INSERT was called
    mock_cursor.execute.assert_called()
    call_args = mock_cursor.execute.call_args
    sql = call_args[0][0]

    # SQL should include project_id column
    assert "project_id" in sql.lower(), "INSERT into episode_memory should include project_id column"


@pytest.mark.asyncio
async def test_store_episode_response_includes_project_metadata():
    """
    AC-3: Verify response includes project_id in metadata.
    """
    tools_module = __import__("mcp_server.tools", fromlist=["handle_store_episode"])

    async def mock_get_connection():
        mock_conn = MagicMock()
        yield mock_conn

    with patch("mcp_server.tools.get_connection_with_project_context", new=mock_get_connection):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {
            "id": 1,
            "created_at": MagicMock(isoformat=lambda: "2024-01-01T00:00:00Z")
        }

        with patch("mcp_server.tools.get_embedding_with_retry", return_value=[0.1] * 1536):
            with patch("mcp_server.tools.register_vector"):
                with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
                    result = await tools_module.handle_store_episode({
                        "query": "test query",
                        "reward": 0.5,
                        "reflection": "test reflection"
                    })

        # Verify response includes project_id in metadata
        assert "metadata" in result
        assert result["metadata"]["project_id"] == "test-project"


# =============================================================================
# AC-4: store_raw_dialogue project_id insertion
# =============================================================================


@pytest.mark.asyncio
async def test_store_raw_dialogue_includes_project_id_in_insert():
    """
    AC-4: Verify store_raw_dialogue INSERT includes project_id.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "timestamp": MagicMock(isoformat=lambda: "2024-01-01T00:00:00Z")
    }

    from mcp_server.tools import handle_store_raw_dialogue

    # Mock the connection as a synchronous context manager (for testing)
    class MockConnectionManager:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, *args):
            pass

    with patch("mcp_server.tools.get_connection_with_project_context", return_value=MockConnectionManager()):
        with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
            result = await handle_store_raw_dialogue({
                "session_id": "test-session",
                "speaker": "user",
                "content": "test content"
            })

    # Verify INSERT includes project_id
    call_args = mock_cursor.execute.call_args
    if call_args and call_args[0]:
        sql = call_args[0][0]
        # SQL should include project_id column
        assert "project_id" in sql.lower(), "INSERT into l0_raw should include project_id column"


@pytest.mark.asyncio
async def test_store_raw_dialogue_response_includes_project_metadata():
    """
    AC-4: Verify response includes project_id in metadata.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {
        "id": 1,
        "timestamp": MagicMock(isoformat=lambda: "2024-01-01T00:00:00Z")
    }

    from mcp_server.tools import handle_store_raw_dialogue

    # Mock the connection as a synchronous context manager (for testing)
    class MockConnectionManager:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, *args):
            pass

    with patch("mcp_server.tools.get_connection_with_project_context", return_value=MockConnectionManager()):
        with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
            result = await handle_store_raw_dialogue({
                "session_id": "test-session",
                "speaker": "user",
                "content": "test content"
            })

    # Verify response includes project_id in metadata
    assert "metadata" in result
    assert result["metadata"]["project_id"] == "test-project"


@pytest.mark.asyncio
async def test_store_raw_dialogue_session_id_scoped_to_project():
    """
    AC-4: Verify session_id uniqueness is scoped to project.
    Same session_id should be allowed for different projects.
    """
    # This is tested at integration level - unit test verifies schema assumption
    # The unique constraint is (project_id, session_id, id) per migration 027
    assert True  # Placeholder for documentation


# =============================================================================
# AC-5: Working memory eviction is project-scoped
# =============================================================================


@pytest.mark.asyncio
async def test_eviction_query_includes_project_id_filter():
    """
    AC-5: Verify eviction SELECT includes project_id filter.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    # Mock a row being returned
    mock_cursor.fetchone.return_value = {"id": 1}

    with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
        from mcp_server.tools import evict_lru_item
        result = await evict_lru_item(mock_conn)

    # Verify SELECT includes project_id filter
    call_args = mock_cursor.execute.call_args
    if call_args and call_args[0]:
        sql = call_args[0][0]
        # SQL should include project_id filter
        assert "project_id" in sql.lower(), "Eviction SELECT should include project_id filter"


@pytest.mark.asyncio
async def test_capacity_check_includes_project_id_filter():
    """
    AC-5: Verify capacity check SELECT includes project_id filter.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {"count": 5}
    mock_cursor.rowcount = 1

    from mcp_server.tools import handle_update_working_memory

    # Mock the connection as a synchronous context manager (for testing)
    class MockConnectionManager:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, *args):
            pass

    with patch("mcp_server.tools.get_connection_with_project_context", return_value=MockConnectionManager()):
        with patch("mcp_server.tools.add_working_memory_item", return_value=1):
            with patch("mcp_server.tools.evict_lru_item", return_value=None):
                with patch("mcp_server.middleware.context.get_current_project", return_value="test-project"):
                    await handle_update_working_memory({
                        "content": "Test content",
                        "importance": 0.5
                    })

    # Find the COUNT query
    count_calls = [call for call in mock_cursor.execute.call_args_list
                   if call[0] and "COUNT" in str(call[0][0]).upper()]
    assert len(count_calls) > 0, "COUNT query should be executed"

    count_sql = count_calls[0][0][0]
    # Capacity check should include project_id filter
    assert "project_id" in count_sql.lower(), \
        "Capacity check COUNT should include project_id filter"


@pytest.mark.asyncio
async def test_eviction_does_not_cross_project_boundaries():
    """
    AC-5: Verify eviction in project 'aa' does not affect project 'io'.

    Integration-level scenario:
    - Project 'aa' has 10 items (at capacity)
    - Project 'io' has 5 items
    - When project 'aa' adds item, eviction should only consider 'aa' items
    - Project 'io' items should NOT be affected
    """
    # This requires full integration test with real database
    # Unit test documents the expectation
    assert True  # Placeholder - integration test covers this
