"""
Integration Tests for Memory Write Operations with Project Scope

Tests for Story 11.5.3: Memory Write Operations (Working Memory, Episodes, Raw)
Covers all acceptance criteria (AC-1 through AC-5).

These tests require a real database connection to verify that:
1. Memory write operations include project_id in INSERT statements
2. Eviction logic is scoped to individual projects
3. Cross-project operations are properly isolated

Author: Epic 11.5 Implementation
Story: 11.5.3 - Memory Write Operations
"""

import pytest
from psycopg2 import DatabaseError


# =============================================================================
# AC-1: update_working_memory project_id insertion
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_working_memory_includes_project_id(conn):
    """
    AC-1: Verify update_working_memory creates entries with project_id.
    """
    from mcp_server.middleware.context import set_project_id, clear_context
    from mcp_server.tools import handle_update_working_memory

    # Set project context
    set_project_id("test-project-aa")

    try:
        result = await handle_update_working_memory({
            "content": "Test content for project aa",
            "importance": 0.5
        })

        assert result["status"] == "success"
        assert "added_id" in result

        # Verify the entry was created with correct project_id
        cursor = conn.cursor()
        cursor.execute(
            "SELECT project_id FROM working_memory WHERE id = %s",
            (result["added_id"],)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["project_id"] == "test-project-aa"

    finally:
        clear_context()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_working_memory_eviction_scoped_to_project(conn):
    """
    AC-1 + AC-5: Verify eviction only considers items from the same project.

    Scenario:
    - Project 'aa' has 10 items (at capacity)
    - Project 'io' has 5 items
    - When project 'aa' adds an 11th item, eviction should only consider 'aa' items
    - Project 'io' items should NOT be affected
    """
    from mcp_server.middleware.context import set_project_id, clear_context
    from mcp_server.tools import handle_update_working_memory

    try:
        # Clear existing working memory for clean test
        cursor = conn.cursor()
        cursor.execute("DELETE FROM working_memory WHERE project_id IN ('test-aa', 'test-io');")
        conn.commit()

        # Set up project 'io' with 5 items
        set_project_id("test-io")
        for i in range(5):
            await handle_update_working_memory({
                "content": f"IO project item {i}",
                "importance": 0.5
            })

        # Verify project 'io' has 5 items
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id = 'test-io';")
        assert cursor.fetchone()["count"] == 5

        # Set up project 'aa' with 10 items (at capacity)
        set_project_id("test-aa")
        for i in range(10):
            await handle_update_working_memory({
                "content": f"AA project item {i}",
                "importance": 0.5
            })

        # Verify project 'aa' has 10 items
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id = 'test-aa';")
        assert cursor.fetchone()["count"] == 10

        # Verify project 'io' still has 5 items
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id = 'test-io';")
        assert cursor.fetchone()["count"] == 5

        # Add 11th item to project 'aa' - should trigger eviction within 'aa' only
        result = await handle_update_working_memory({
            "content": "AA project item 10 (triggering eviction)",
            "importance": 0.9  # High importance to test eviction logic
        })

        assert result["status"] == "success"
        assert "added_id" in result
        assert result["evicted_id"] is not None  # Eviction should have occurred

        # Verify project 'aa' still has 10 items (1 added, 1 evicted)
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id = 'test-aa';")
        assert cursor.fetchone()["count"] == 10

        # CRITICAL: Verify project 'io' still has 5 items (unaffected by 'aa' eviction)
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id = 'test-io';")
        assert cursor.fetchone()["count"] == 5, "Eviction in project 'aa' should not affect project 'io' items"

        # Verify the evicted item was from project 'aa'
        cursor.execute(
            "SELECT project_id FROM working_memory WHERE id = %s",
            (result["evicted_id"],)
        )
        # The evicted item should no longer exist in working_memory
        assert cursor.fetchone() is None

    finally:
        clear_context()
        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM working_memory WHERE project_id IN ('test-aa', 'test-io');")
        conn.commit()


# =============================================================================
# AC-2: delete_working_memory project scoping
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_working_memory_scoped_to_project(conn):
    """
    AC-2: Verify delete_working_memory only deletes from the current project.

    Scenario:
    - Project 'aa' has an item with id=1
    - Project 'io' tries to delete id=1
    - The delete should only work if the item belongs to 'io'
    """
    from mcp_server.middleware.context import set_project_id, clear_context
    from mcp_server.tools import handle_update_working_memory, handle_delete_working_memory

    try:
        # Clear existing data
        cursor = conn.cursor()
        cursor.execute("DELETE FROM working_memory WHERE project_id IN ('test-aa', 'test-io');")
        conn.commit()

        # Create item in project 'aa'
        set_project_id("test-aa")
        result_aa = await handle_update_working_memory({
            "content": "AA project item",
            "importance": 0.5
        })
        aa_id = result_aa["added_id"]

        # Create item in project 'io'
        set_project_id("test-io")
        result_io = await handle_update_working_memory({
            "content": "IO project item",
            "importance": 0.5
        })
        io_id = result_io["added_id"]

        # Verify both items exist
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id IN ('test-aa', 'test-io');")
        assert cursor.fetchone()["count"] == 2

        # Try to delete the 'aa' item while in 'io' context
        # Should return not_found because RLS filters out 'aa' items
        delete_result = await handle_delete_working_memory({"id": aa_id})
        assert delete_result["status"] == "not_found"
        assert delete_result["deleted_id"] is None

        # Verify both items still exist
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id IN ('test-aa', 'test-io');")
        assert cursor.fetchone()["count"] == 2

        # Switch to 'aa' context and delete the item successfully
        set_project_id("test-aa")
        delete_result = await handle_delete_working_memory({"id": aa_id})
        assert delete_result["status"] == "success"
        assert delete_result["deleted_id"] == aa_id

        # Verify only 'io' item remains
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id IN ('test-aa', 'test-io');")
        assert cursor.fetchone()["count"] == 1

    finally:
        clear_context()
        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM working_memory WHERE project_id IN ('test-aa', 'test-io');")
        conn.commit()


# =============================================================================
# AC-3: store_episode project_id insertion
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_episode_includes_project_id(conn):
    """
    AC-3: Verify store_episode creates entries with project_id.
    """
    from mcp_server.middleware.context import set_project_id, clear_context
    from mcp_server.tools import handle_store_episode

    # Mock OpenAI embedding to avoid API call
    import pytest
    from unittest.mock import patch, MagicMock

    set_project_id("test-project-episode")

    try:
        with patch("mcp_server.tools.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.embeddings.create.return_value = MagicMock(
                data=[MagicMock(embedding=[0.1] * 1536)]
            )
            mock_openai.return_value = mock_client

            result = await handle_store_episode({
                "query": "test query",
                "reward": 0.5,
                "reflection": "test reflection"
            })

            assert result["status"] == "success"
            assert "id" in result

            # Verify the entry was created with correct project_id
            cursor = conn.cursor()
            cursor.execute(
                "SELECT project_id FROM episode_memory WHERE id = %s",
                (result["id"],)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["project_id"] == "test-project-episode"

    finally:
        clear_context()
        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM episode_memory WHERE project_id = 'test-project-episode';")
        conn.commit()


# =============================================================================
# AC-4: store_raw_dialogue project_id insertion
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_raw_dialogue_includes_project_id(conn):
    """
    AC-4: Verify store_raw_dialogue creates entries with project_id.
    """
    from mcp_server.middleware.context import set_project_id, clear_context
    from mcp_server.tools import handle_store_raw_dialogue

    set_project_id("test-project-dialogue")

    try:
        result = await handle_store_raw_dialogue({
            "session_id": "test-session",
            "speaker": "user",
            "content": "Test content"
        })

        assert result["status"] == "success"
        assert "id" in result

        # Verify the entry was created with correct project_id
        cursor = conn.cursor()
        cursor.execute(
            "SELECT project_id FROM l0_raw WHERE id = %s",
            (result["id"],)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["project_id"] == "test-project-dialogue"

    finally:
        clear_context()
        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM l0_raw WHERE project_id = 'test-project-dialogue';")
        conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_store_raw_dialogue_session_id_scoped_to_project(conn):
    """
    AC-4: Verify session_id uniqueness is scoped to project.

    Same session_id should be allowed for different projects.
    This tests the unique constraint (project_id, session_id, id).
    """
    from mcp_server.middleware.context import set_project_id, clear_context
    from mcp_server.tools import handle_store_raw_dialogue

    try:
        # Create entry in project 'aa' with session_id 'shared-session'
        set_project_id("test-aa-dialogue")
        result_aa = await handle_store_raw_dialogue({
            "session_id": "shared-session",
            "speaker": "user",
            "content": "AA project content"
        })

        assert result_aa["status"] == "success"

        # Create entry in project 'io' with SAME session_id
        set_project_id("test-io-dialogue")
        result_io = await handle_store_raw_dialogue({
            "session_id": "shared-session",
            "speaker": "user",
            "content": "IO project content"
        })

        assert result_io["status"] == "success"

        # Verify both entries exist with same session_id but different projects
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, project_id FROM l0_raw WHERE session_id = 'shared-session' ORDER BY project_id;"
        )
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert rows[0]["project_id"] == "test-aa-dialogue"
        assert rows[1]["project_id"] == "test-io-dialogue"

    finally:
        clear_context()
        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM l0_raw WHERE session_id = 'shared-session';")
        conn.commit()


# =============================================================================
# AC-5: Working memory eviction is project-scoped
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_eviction_with_high_importance_items(conn):
    """
    AC-5: Verify eviction behavior with high importance items.

    When all items in a project have high importance (>0.8),
    the force_evict_oldest_critical function should be called.
    This should only evict from the current project.
    """
    from mcp_server.middleware.context import set_project_id, clear_context
    from mcp_server.tools import handle_update_working_memory

    try:
        # Clear existing working memory for clean test
        cursor = conn.cursor()
        cursor.execute("DELETE FROM working_memory WHERE project_id IN ('test-critical-aa', 'test-critical-io');")
        conn.commit()

        # Set up project 'io' with 5 high importance items
        set_project_id("test-critical-io")
        for i in range(5):
            await handle_update_working_memory({
                "content": f"IO critical item {i}",
                "importance": 0.9  # All critical
            })

        # Set up project 'aa' with 10 high importance items (at capacity)
        set_project_id("test-critical-aa")
        for i in range(10):
            await handle_update_working_memory({
                "content": f"AA critical item {i}",
                "importance": 0.9  # All critical
            })

        # Verify project 'aa' has 10 items
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id = 'test-critical-aa';")
        assert cursor.fetchone()["count"] == 10

        # Add 11th item to project 'aa' - should force evict oldest critical item
        result = await handle_update_working_memory({
            "content": "AA critical item 10 (triggering force eviction)",
            "importance": 0.9
        })

        assert result["status"] == "success"
        assert "added_id" in result
        assert result["evicted_id"] is not None

        # Verify project 'aa' still has 10 items
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id = 'test-critical-aa';")
        assert cursor.fetchone()["count"] == 10

        # CRITICAL: Verify project 'io' still has 5 items (unaffected)
        cursor.execute("SELECT COUNT(*) as count FROM working_memory WHERE project_id = 'test-critical-io';")
        assert cursor.fetchone()["count"] == 5

    finally:
        clear_context()
        # Cleanup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM working_memory WHERE project_id IN ('test-critical-aa', 'test-critical-io');")
        conn.commit()
