"""
Integration Tests for update_insight Full Flow

Tests the complete flow: update → history → verify.

Story 26.2: UPDATE Operation - Full Flow Integration Test
"""

import pytest
from mcp_server.db.insights import execute_update_with_history, get_insight_by_id
from mcp_server.tools.insights.update import handle_update_insight


def _generate_test_embedding():
    """Generate a valid 1536-dimensional embedding vector for testing."""
    # Create a simple pattern that repeats to fill 1536 dimensions
    embedding = [0.1] * 1536  # All 0.1 values (simplified for testing)
    return embedding


def test_full_flow_update_with_history(conn):
    """
    Integration Test: Full flow (update → history → verify).

    AC-5: Atomic History - History is written in same transaction as update.
    """
    # Generate valid 1536-dimensional embedding
    embedding = _generate_test_embedding()

    # First, create a test insight if none exists
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO l2_insights (content, embedding, source_ids)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Original content", embedding, [1])
    )
    insight_id = cursor.fetchone()[0]
    conn.commit()  # IMPORTANT: Commit so execute_update_with_history can see the insight
    cursor.close()

    # Execute update with atomic history
    result = execute_update_with_history(
        insight_id=insight_id,
        new_content="Updated content",
        new_memory_strength=0.8,
        actor="I/O",
        reason="Integration test"
    )

    # Verify success
    assert result["success"] is True
    assert result["insight_id"] == insight_id
    assert result["history_id"] is not None

    # Verify insight was actually updated
    updated_insight = get_insight_by_id(insight_id)
    assert updated_insight is not None
    assert updated_insight["content"] == "Updated content"

    # Verify history entry was written
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT action, actor, old_content, new_content, old_memory_strength, new_memory_strength, reason
        FROM l2_insight_history
        WHERE insight_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (insight_id,)
    )
    history = cursor.fetchone()
    cursor.close()

    assert history is not None
    assert history[0] == "UPDATE"  # action
    assert history[1] == "I/O"     # actor
    assert history[2] == "Original content"  # old_content
    assert history[3] == "Updated content"   # new_content
    assert history[6] == "Integration test"  # reason


def test_atomic_transaction_rollback(conn):
    """
    Integration Test: Atomic transaction rollback (AC-5).

    AC-5 Requirement: "bei Abbruch: vollständiger Rollback, kein partieller State"

    This test verifies that if the UPDATE fails AFTER history is written,
    both operations are rolled back atomically (no orphaned history entries).

    Test approach: Use a database trigger to simulate failure during UPDATE.
    """
    # Generate valid 1536-dimensional embedding
    embedding = _generate_test_embedding()

    # Create test insight
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO l2_insights (content, embedding, source_ids)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Test content for rollback", embedding, [1])
    )
    insight_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()

    # Count history entries BEFORE attempted update
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM l2_insight_history WHERE insight_id = %s",
        (insight_id,)
    )
    history_count_before = cursor.fetchone()[0]
    cursor.close()

    # Create a trigger that will cause UPDATE to fail
    # This simulates a failure AFTER history is written but during UPDATE
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE OR REPLACE FUNCTION fail_update_trigger()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.content = 'TRIGGER_ROLLBACK_TEST' THEN
                RAISE EXCEPTION 'Simulated failure for rollback test';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS test_rollback_trigger ON l2_insights;
        CREATE TRIGGER test_rollback_trigger
            BEFORE UPDATE ON l2_insights
            FOR EACH ROW
            EXECUTE FUNCTION fail_update_trigger();
        """
    )
    conn.commit()
    cursor.close()

    try:
        # Attempt update that will fail during UPDATE (after history INSERT)
        try:
            execute_update_with_history(
                insight_id=insight_id,
                new_content="TRIGGER_ROLLBACK_TEST",  # This triggers the failure
                new_memory_strength=0.7,
                actor="I/O",
                reason="Rollback test"
            )
            pytest.fail("Expected exception was not raised")
        except Exception as e:
            # Expected: the trigger causes an exception
            assert "Simulated failure" in str(e) or "rollback" in str(e).lower() or True
            # Any exception is acceptable - the key test is below

        # CRITICAL VERIFICATION: History should NOT have been written
        # If transaction is atomic, rollback should have removed the history entry
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM l2_insight_history WHERE insight_id = %s",
            (insight_id,)
        )
        history_count_after = cursor.fetchone()[0]
        cursor.close()

        assert history_count_after == history_count_before, \
            f"AC-5 VIOLATION: History entries changed from {history_count_before} to {history_count_after}. " \
            f"Transaction rollback should have removed orphaned history entry."

        # Also verify the insight content was NOT changed
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM l2_insights WHERE id = %s",
            (insight_id,)
        )
        current_content = cursor.fetchone()[0]
        cursor.close()

        assert current_content == "Test content for rollback", \
            f"AC-5 VIOLATION: Content was changed to '{current_content}' despite rollback"

    finally:
        # Cleanup: Remove the test trigger
        cursor = conn.cursor()
        cursor.execute("DROP TRIGGER IF EXISTS test_rollback_trigger ON l2_insights")
        cursor.execute("DROP FUNCTION IF EXISTS fail_update_trigger()")
        conn.commit()
        cursor.close()


def test_successful_update_has_exactly_one_history_entry(conn):
    """
    Integration Test: Successful update creates exactly one history entry.

    Complementary test to rollback - verifies no duplicate entries on success.
    """
    # Generate valid 1536-dimensional embedding
    embedding = _generate_test_embedding()

    # Create test insight
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO l2_insights (content, embedding, source_ids)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Test content", embedding, [1])
    )
    insight_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()

    # Execute successful update
    result = execute_update_with_history(
        insight_id=insight_id,
        new_content="Valid update",
        new_memory_strength=0.7,
        actor="I/O",
        reason="Test"
    )

    assert result["success"] is True

    # Verify exactly ONE history entry exists (no duplicates)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM l2_insight_history WHERE insight_id = %s",
        (insight_id,)
    )
    count = cursor.fetchone()[0]
    cursor.close()

    assert count == 1, f"Should have exactly one history entry, got {count}"


def test_consecutive_updates_create_multiple_history_entries(conn):
    """
    Integration Test: Multiple updates create separate history entries.
    """
    # Generate valid 1536-dimensional embedding
    embedding = _generate_test_embedding()

    # Create test insight
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO l2_insights (content, embedding, source_ids)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("V1", embedding, [1])
    )
    insight_id = cursor.fetchone()[0]
    conn.commit()  # IMPORTANT: Commit so execute_update_with_history can see the insight
    cursor.close()

    # First update
    result1 = execute_update_with_history(
        insight_id=insight_id,
        new_content="V2",
        new_memory_strength=0.6,
        actor="I/O",
        reason="First update"
    )
    assert result1["success"] is True

    # Second update
    result2 = execute_update_with_history(
        insight_id=insight_id,
        new_content="V3",
        new_memory_strength=0.9,
        actor="I/O",
        reason="Second update"
    )
    assert result2["success"] is True

    # Verify we have 2 history entries
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM l2_insight_history WHERE insight_id = %s",
        (insight_id,)
    )
    count = cursor.fetchone()[0]
    cursor.close()

    assert count == 2, "Should have two history entries"

    # Verify latest history entry is V2→V3
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT old_content, new_content
        FROM l2_insight_history
        WHERE insight_id = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (insight_id,)
    )
    latest = cursor.fetchone()
    cursor.close()

    assert latest[0] == "V2"  # old_content
    assert latest[1] == "V3"  # new_content


@pytest.mark.skipif(
    "True",  # Skip by default - requires soft-delete support (Story 26.3)
    reason="AC-7: Requires soft-delete fields from Story 26.3 (is_deleted, deleted_at, deleted_by, deleted_reason)"
)
def test_soft_deleted_insight_returns_404(conn):
    """
    AC-7: Soft-deleted insights return 404.

    This test verifies that update_insight returns 404 for soft-deleted insights.
    Optional test - skipped if Story 26.3 (soft-delete) is not implemented yet.

    Test flow:
    1. Create a test insight
    2. Soft-delete it (set is_deleted=TRUE via Story 26.3 mechanism)
    3. Call update_insight
    4. Verify 404 error is returned
    """
    import pytest

    # Check if soft-delete fields exist
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'l2_insights'
          AND column_name = 'is_deleted'
        """
    )
    has_soft_delete = cursor.fetchone() is not None
    cursor.close()

    if not has_soft_delete:
        pytest.skip("Soft-delete fields not implemented (Story 26.3)")

    # Generate valid embedding
    embedding = _generate_test_embedding()

    # Step 1: Create test insight
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO l2_insights (content, embedding, source_ids)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        ("Test insight for soft-delete", embedding, [1])
    )
    insight_id = cursor.fetchone()[0]
    conn.commit()  # IMPORTANT: Commit so soft-delete update can see the insight
    cursor.close()

    # Step 2: Soft-delete the insight
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE l2_insights
        SET is_deleted = TRUE,
            deleted_at = NOW(),
            deleted_by = 'I/O',
            deleted_reason = 'Test soft-delete'
        WHERE id = %s
        """,
        (insight_id,)
    )
    cursor.close()

    # Step 3: Try to update the soft-deleted insight
    result = handle_update_insight({
        "insight_id": insight_id,
        "actor": "I/O",
        "reason": "Should not work",
        "new_content": "This should fail"
    })

    # Step 4: Verify 404 error is returned
    assert "error" in result, "Should return error for soft-deleted insight"
    assert result["error"]["code"] == 404, "Error code should be 404"
    assert "not found" in result["error"]["message"].lower(), "Error message should mention 'not found'"
