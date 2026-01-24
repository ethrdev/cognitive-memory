"""
Integration tests for L2 Insight write operations with project scoping.

Story 11.5.2: L2 Insight Write Operations
Tests that compress_to_l2_insight, update_insight, and delete_insight
respect project boundaries and RLS policies.
"""

import pytest
from mcp_server.db.connection import get_connection_with_project_context


@pytest.mark.asyncio
async def test_compress_to_l2_insight_creates_with_project_id(conn):
    """Test that compress_to_l2_insight creates insights with correct project_id."""
    cursor = conn.cursor()

    # Set project context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Create insight using compress_to_l2_insight logic
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, project_id
        """,
        ("test-project", "Test content", [1, 2], 0.8, {}, [0.1] * 1536),
    )

    result = cursor.fetchone()
    assert result is not None
    assert result["project_id"] == "test-project"

    # Cleanup
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (result["id"],))
    conn.commit()


@pytest.mark.asyncio
async def test_update_insight_own_project_succeeds(conn):
    """Test that update_insight succeeds for own project's insights."""
    cursor = conn.cursor()

    # Set project context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Create insight
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("test-project", "Original content", [1], 0.5, {}, [0.1] * 1536),
    )
    result = cursor.fetchone()
    insight_id = result["id"]

    # Update should succeed
    cursor.execute(
        """
        UPDATE l2_insights
        SET content = %s
        WHERE id = %s
        RETURNING content
        """,
        ("Updated content", insight_id),
    )

    updated = cursor.fetchone()
    assert updated["content"] == "Updated content"

    # Cleanup
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
    conn.commit()


@pytest.mark.asyncio
async def test_update_insight_cross_project_fails(conn):
    """Test that update_insight fails for other project's insights due to RLS."""
    cursor = conn.cursor()

    # Create insight as 'io' project
    await cursor.execute("SELECT set_project_context(%s)", ("io",))
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("io", "IO content", [1], 0.5, {}, [0.1] * 1536),
    )
    result = cursor.fetchone()
    insight_id = result["id"]

    # Switch to 'test-project' context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Update should fail or affect 0 rows due to RLS
    cursor.execute(
        """
        UPDATE l2_insights
        SET content = %s
        WHERE id = %s
        """,
        ("Hacked content", insight_id),
    )

    # Verify content unchanged (RLS blocked the update)
    await cursor.execute("SELECT set_project_context(%s)", ("io",))
    cursor.execute(
        "SELECT content FROM l2_insights WHERE id = %s",
        (insight_id,)
    )
    unchanged = cursor.fetchone()
    assert unchanged["content"] == "IO content"

    # Cleanup
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
    conn.commit()


@pytest.mark.asyncio
async def test_delete_insight_own_project_succeeds(conn):
    """Test that delete_insight succeeds for own project's insights."""
    cursor = conn.cursor()

    # Set project context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Create insight
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("test-project", "To be deleted", [1], 0.5, {}, [0.1] * 1536),
    )
    result = cursor.fetchone()
    insight_id = result["id"]

    # Soft-delete should succeed
    cursor.execute(
        """
        UPDATE l2_insights
        SET is_deleted = TRUE, deleted_at = NOW(), deleted_by = %s, deleted_reason = %s
        WHERE id = %s
        RETURNING is_deleted
        """,
        ("test-user", "Test deletion", insight_id),
    )

    deleted = cursor.fetchone()
    assert deleted["is_deleted"] is True

    # Cleanup (hard delete for test)
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
    conn.commit()


@pytest.mark.asyncio
async def test_delete_insight_cross_project_fails(conn):
    """Test that delete_insight fails for other project's insights due to RLS."""
    cursor = conn.cursor()

    # Create insight as 'io' project
    await cursor.execute("SELECT set_project_context(%s)", ("io",))
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("io", "IO content", [1], 0.5, {}, [0.1] * 1536),
    )
    result = cursor.fetchone()
    insight_id = result["id"]

    # Switch to 'test-project' context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Delete should fail or affect 0 rows due to RLS
    cursor.execute(
        """
        UPDATE l2_insights
        SET is_deleted = TRUE
        WHERE id = %s
        """,
        (insight_id,),
    )

    # Verify not deleted (RLS blocked the delete)
    await cursor.execute("SELECT set_project_context(%s)", ("io",))
    cursor.execute(
        "SELECT is_deleted FROM l2_insights WHERE id = %s",
        (insight_id,)
    )
    unchanged = cursor.fetchone()
    assert unchanged["is_deleted"] is False

    # Cleanup
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
    conn.commit()


@pytest.mark.asyncio
async def test_insight_history_includes_project_id(conn):
    """Test that insight history entries include project_id (Story 11.5.2)."""
    cursor = conn.cursor()

    # Set project context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Create insight
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("test-project", "History test content", [1], 0.5, {}, [0.1] * 1536),
    )
    result = cursor.fetchone()
    insight_id = result["id"]

    # Update insight to create history entry
    cursor.execute(
        """
        UPDATE l2_insights
        SET content = %s
        WHERE id = %s
        """,
        ("Updated content", insight_id),
    )

    # Verify history entry has project_id
    cursor.execute(
        """
        SELECT project_id FROM l2_insight_history
        WHERE insight_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (insight_id,),
    )

    history_entry = cursor.fetchone()
    assert history_entry is not None
    assert history_entry["project_id"] == "test-project"

    # Cleanup
    cursor.execute("DELETE FROM l2_insight_history WHERE insight_id = %s", (insight_id,))
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
    conn.commit()


@pytest.mark.asyncio
async def test_compress_to_l2_insight_rls_blocks_wrong_project(conn):
    """Test that RLS blocks INSERT with wrong project_id."""
    cursor = conn.cursor()

    # Set project context to 'test-project'
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Try to INSERT with 'io' project_id (should be blocked by RLS WITH CHECK)
    with pytest.raises(Exception) as exc_info:
        cursor.execute(
            """
            INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("io", "This should fail", [1], 0.5, {}, [0.1] * 1536),
        )
        conn.commit()

    # RLS should reject this because project_id != current project
    assert "new row violates row-level security policy" in str(exc_info.value).lower() or \
           "violates check constraint" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_insight_write_operations_preserve_project_id(conn):
    """Test that all insight write operations preserve project_id correctly."""
    cursor = conn.cursor()

    # Set project context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Create insight
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id, project_id
        """,
        ("test-project", "Original", [1], 0.5, {}, [0.1] * 1536),
    )
    result = cursor.fetchone()
    insight_id = result["id"]
    original_project_id = result["project_id"]

    # Update insight
    cursor.execute(
        """
        UPDATE l2_insights
        SET content = %s, memory_strength = %s
        WHERE id = %s
        RETURNING project_id
        """,
        ("Updated", 0.7, insight_id),
    )
    updated = cursor.fetchone()
    assert updated["project_id"] == original_project_id

    # Soft-delete insight
    cursor.execute(
        """
        UPDATE l2_insights
        SET is_deleted = TRUE, deleted_at = NOW(), deleted_by = %s, deleted_reason = %s
        WHERE id = %s
        RETURNING project_id
        """,
        ("test-user", "Test", insight_id),
    )
    deleted = cursor.fetchone()
    assert deleted["project_id"] == original_project_id

    # Verify history entries have correct project_id
    cursor.execute(
        """
        SELECT project_id FROM l2_insight_history
        WHERE insight_id = %s
        """,
        (insight_id,),
    )
    history_entries = cursor.fetchall()
    for entry in history_entries:
        assert entry["project_id"] == original_project_id

    # Cleanup
    cursor.execute("DELETE FROM l2_insight_history WHERE insight_id = %s", (insight_id,))
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
    conn.commit()


@pytest.mark.asyncio
async def test_update_insight_tool_cross_project_error_message(conn):
    """Test that update_insight tool returns proper error message for cross-project updates."""
    from mcp_server.tools.insights.update import handle_update_insight

    cursor = conn.cursor()

    # Create insight as 'io' project
    await cursor.execute("SELECT set_project_context(%s)", ("io",))
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("io", "IO content", [1], 0.5, {}, [0.1] * 1536),
    )
    result = cursor.fetchone()
    insight_id = result["id"]

    # Switch to 'test-project' context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Call update_insight tool directly
    response = await handle_update_insight({
        "insight_id": insight_id,
        "actor": "I/O",
        "reason": "Test update",
        "new_content": "Attempted hack"
    })

    # Verify error response
    assert "error" in response
    assert response["error"]["code"] == 403
    assert "Cannot modify insight from another project" in response["error"]["message"]

    # Cleanup
    await cursor.execute("SELECT set_project_context(%s)", ("io",))
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
    conn.commit()


@pytest.mark.asyncio
async def test_delete_insight_tool_cross_project_error_message(conn):
    """Test that delete_insight tool returns proper error message for cross-project deletes."""
    from mcp_server.tools.insights.delete import handle_delete_insight

    cursor = conn.cursor()

    # Create insight as 'io' project
    await cursor.execute("SELECT set_project_context(%s)", ("io",))
    cursor.execute(
        """
        INSERT INTO l2_insights (project_id, content, source_ids, memory_strength, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        ("io", "IO content", [1], 0.5, {}, [0.1] * 1536),
    )
    result = cursor.fetchone()
    insight_id = result["id"]

    # Switch to 'test-project' context
    await cursor.execute("SELECT set_project_context(%s)", ("test-project",))

    # Call delete_insight tool directly
    response = await handle_delete_insight({
        "insight_id": insight_id,
        "actor": "I/O",
        "reason": "Test delete"
    })

    # Verify error response
    assert "error" in response
    assert response["error"]["code"] == 403
    assert "Cannot delete insight from another project" in response["error"]["message"]

    # Cleanup
    await cursor.execute("SELECT set_project_context(%s)", ("io",))
    cursor.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
    conn.commit()
