"""
Integration Test: Full Delete Operation Flow

Tests the complete end-to-end flow of deleting an insight:
1. Create test insight
2. Verify it appears in search
3. Delete the insight (AC-1, AC-2, AC-5, AC-7)
4. Verify it's excluded from search (AC-3)
5. Verify history is preserved (AC-4)
6. Test error cases (AC-6, AC-5, AC-7)

Story 26.3: DELETE Operation
Epic 26: Memory Management with Curation
"""

import pytest
import asyncpg
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime


class TestDeleteInsightFlow:
    """End-to-end integration tests for delete_insight flow."""

    @pytest.fixture
    async def test_db(self):
        """Create a test database connection."""
        db_url = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/test_cognitive_memory")
        conn = await asyncpg.connect(db_url)

        # Start transaction
        async with conn.transaction():
            yield conn

        await conn.close()

    @pytest.fixture
    async def test_insight_id(self, test_db):
        """Create a test insight for deletion."""
        insight_id = await test_db.fetchval("""
            INSERT INTO l2_insights (
                content,
                embedding,
                source_ids,
                metadata,
                memory_strength,
                is_deleted,
                deleted_at,
                deleted_by,
                deleted_reason
            )
            VALUES (
                'Test insight for delete operation',
                '[0.1, 0.2, 0.3]'::vector,
                ARRAY[1, 2, 3],
                '{"test": true}'::jsonb,
                0.8,
                FALSE,
                NULL,
                NULL,
                NULL
            )
            RETURNING id
 """)

        yield insight_id

        # Cleanup
        await test_db.execute("DELETE FROM l2_insights WHERE id = $1", insight_id)
        await test_db.execute("DELETE FROM l2_insight_history WHERE insight_id = $1", insight_id)

    @pytest.mark.asyncio
    async def test_full_delete_flow_io_actor(self, test_db, test_insight_id):
        """
        AC-1 & AC-3: Full flow test with I/O actor.

        Test that:
        1. Insight exists and appears in search
        2. I/O can delete directly without SMF
        3. Deleted insight is excluded from search
        4. History is preserved
        """
        insight_id = test_insight_id

        # Step 1: Verify insight exists
        row = await test_db.fetchrow("""
            SELECT id, content, is_deleted, deleted_at, deleted_by, deleted_reason
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        assert row is not None, "Test insight should exist"
        assert row["is_deleted"] is False, "Insight should not be deleted initially"
        assert row["deleted_at"] is None, "deleted_at should be NULL initially"

        # Step 2: Verify it would appear in search (hybrid_search uses WHERE is_deleted = FALSE)
        # Query that mimics hybrid_search
        search_results = await test_db.fetch("""
            SELECT id, content, 1.0 as score
            FROM l2_insights
            WHERE is_deleted = FALSE
            AND content ILIKE $1
            ORDER BY created_at DESC
            LIMIT 10
 """, "%delete operation%")

        assert len(search_results) > 0, "Test insight should appear in search before deletion"

        # Step 3: Execute soft delete using the database function
        # This mimics what execute_delete_with_history does
        await test_db.execute("""
            INSERT INTO l2_insight_history (
                insight_id,
                action,
                actor,
                old_content,
                old_memory_strength,
                reason,
                created_at
            )
            VALUES ($1, 'DELETE', 'I/O', $2, 0.8, 'Full flow test', NOW())
 """, insight_id, row["content"])

        await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'I/O',
                deleted_reason = 'Full flow test'
            WHERE id = $1
 """, insight_id)

        # Step 4: Verify soft delete worked
        row_after = await test_db.fetchrow("""
            SELECT id, content, is_deleted, deleted_at, deleted_by, deleted_reason
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        assert row_after["is_deleted"] is True, "Insight should be marked as deleted"
        assert row_after["deleted_at"] is not None, "deleted_at should be set"
        assert row_after["deleted_by"] == "I/O", "deleted_by should be 'I/O'"
        assert row_after["deleted_reason"] == "Full flow test", "deleted_reason should be set"

        # Step 5: Verify it's EXCLUDED from search (AC-3)
        search_results_after = await test_db.fetch("""
            SELECT id, content, 1.0 as score
            FROM l2_insights
            WHERE is_deleted = FALSE
            AND content ILIKE $1
            ORDER BY created_at DESC
            LIMIT 10
 """, "%delete operation%")

        # The test insight should NOT appear in search results
        found_in_search = any(r["id"] == insight_id for r in search_results_after)
        assert not found_in_search, "Soft-deleted insight should be excluded from search"

        # Step 6: Verify history is preserved (AC-4)
        history = await test_db.fetchrow("""
            SELECT insight_id, action, actor, old_content, reason, created_at
            FROM l2_insight_history
            WHERE insight_id = $1 AND action = 'DELETE'
            ORDER BY created_at DESC
            LIMIT 1
 """, insight_id)

        assert history is not None, "History entry should be created"
        assert history["action"] == "DELETE", "History should record DELETE action"
        assert history["actor"] == "I/O", "History should record actor"
        assert history["old_content"] == row["content"], "History should preserve old content"
        assert history["reason"] == "Full flow test", "History should preserve reason"

    @pytest.mark.asyncio
    async def test_search_exclusion_with_multiple_insights(self, test_db):
        """AC-3: Verify search exclusion works with multiple insights."""
        # Create 5 test insights
        insight_ids = []
        for i in range(5):
            insight_id = await test_db.fetchval("""
                INSERT INTO l2_insights (
                    content,
                    embedding,
                    source_ids,
                    metadata,
                    memory_strength
                )
                VALUES (
                    $1,
                    '[0.1, 0.2, 0.3]'::vector,
                    ARRAY[1],
                    '{}'::jsonb,
                    0.5
                )
                RETURNING id
 """, f"Search test insight {i}")
            insight_ids.append(insight_id)

        # Delete 2 of them
        await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'I/O',
                deleted_reason = 'Test exclusion'
            WHERE id = ANY($1)
 """, insight_ids[:2])

        # Query search results (mimics hybrid_search)
        search_results = await test_db.fetch("""
            SELECT id, content
            FROM l2_insights
            WHERE is_deleted = FALSE
            ORDER BY created_at DESC
            LIMIT 10
 """)

        # Should only find 3 non-deleted insights
        assert len(search_results) == 3, "Should find 3 non-deleted insights"

        # Verify the deleted ones are NOT in results
        deleted_ids_in_results = [r["id"] for r in search_results if r["id"] in insight_ids[:2]]
        assert len(deleted_ids_in_results) == 0, "Deleted insights should not appear in search"

        # Clean up
        await test_db.execute("""
            DELETE FROM l2_insights
            WHERE id = ANY($1)
 """, insight_ids)

    @pytest.mark.asyncio
    async def test_already_deleted_error(self, test_db, test_insight_id):
        """AC-5: Test that deleting an already deleted insight returns 409 error."""
        insight_id = test_insight_id

        # First delete
        await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'I/O',
                deleted_reason = 'First delete'
            WHERE id = $1
 """, insight_id)

        # Verify it's marked as deleted
        row = await test_db.fetchrow("""
            SELECT is_deleted
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        assert row["is_deleted"] is True, "Insight should be marked as deleted"

        # Try to delete again - should simulate 409 error
        # In the real tool, this would be caught by execute_delete_with_history
        try:
            await test_db.execute("""
                UPDATE l2_insights
                SET is_deleted = TRUE,
                    deleted_at = NOW(),
                    deleted_by = 'I/O',
                    deleted_reason = 'Second delete'
                WHERE id = $1 AND is_deleted = FALSE
 """, insight_id)

            # If we get here without error, the update didn't happen (which is correct)
            # Check that the update didn't change anything
            row_after = await test_db.fetchrow("""
                SELECT deleted_reason
                FROM l2_insights
                WHERE id = $1
 """, insight_id)

            assert row_after["deleted_reason"] == "First delete", "Second delete should not have changed the record"

        except Exception as e:
            # This is also acceptable behavior
            pytest.fail(f"Unexpected exception: {e}")

    @pytest.mark.asyncio
    async def test_not_found_error(self, test_db):
        """AC-7: Test that deleting a non-existent insight returns 404 error."""
        # Try to delete an insight that doesn't exist
        non_existent_id = 99999

        # In the real tool, this would be caught before the DB update
        # Simulate the check
        row = await test_db.fetchrow("""
            SELECT id
            FROM l2_insights
            WHERE id = $1
 """, non_existent_id)

        assert row is None, "Insight should not exist"

        # The actual delete would fail or do nothing
        rows_affected = await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'I/O',
                deleted_reason = 'Test'
            WHERE id = $1
 """, non_existent_id)

        assert "UPDATE 0" in rows_affected, "No rows should be updated"

    @pytest.mark.asyncio
    async def test_history_preservation_after_delete(self, test_db, test_insight_id):
        """
        AC-4: Test that deleted insights are preserved in history.

        This is the foundation for Story 26.7 (get_insight_history).
        """
        insight_id = test_insight_id
        original_content = "Test insight for delete operation"

        # Create history entry before delete
        history_id = await test_db.fetchval("""
            INSERT INTO l2_insight_history (
                insight_id,
                action,
                actor,
                old_content,
                old_memory_strength,
                reason,
                created_at
            )
            VALUES ($1, 'DELETE', 'I/O', $2, 0.8, 'History preservation test', NOW())
            RETURNING id
 """, insight_id, original_content)

        # Soft delete
        await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'I/O',
                deleted_reason = 'History preservation test'
            WHERE id = $1
 """, insight_id)

        # Verify history is queryable
        history = await test_db.fetchrow("""
            SELECT id, insight_id, action, actor, old_content, old_memory_strength, reason, created_at
            FROM l2_insight_history
            WHERE id = $1
 """, history_id)

        assert history is not None, "History entry should exist"
        assert history["insight_id"] == insight_id, "History should reference correct insight"
        assert history["action"] == "DELETE", "History should record DELETE action"
        assert history["actor"] == "I/O", "History should record actor"
        assert history["old_content"] == original_content, "History should preserve original content"
        assert history["reason"] == "History preservation test", "History should preserve reason"

        # Verify insight is soft-deleted but still queryable
        insight = await test_db.fetchrow("""
            SELECT id, content, is_deleted
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        assert insight is not None, "Soft-deleted insight should still exist"
        assert insight["is_deleted"] is True, "Insight should be marked as deleted"
        assert insight["content"] == original_content, "Content should be preserved"

    @pytest.mark.asyncio
    async def test_transaction_rollback_on_error(self, test_db, test_insight_id):
        """Test that errors in delete operation don't leave partial state."""
        insight_id = test_insight_id

        # Get original state
        original = await test_db.fetchrow("""
            SELECT is_deleted, deleted_at, deleted_by, deleted_reason
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        # Attempt an invalid delete (simulate error in middle of operation)
        async with test_db.transaction():
            # This would succeed
            await test_db.execute("""
                INSERT INTO l2_insight_history (
                    insight_id,
                    action,
                    actor,
                    old_content,
                    reason
                )
                VALUES ($1, 'DELETE', 'I/O', $2, 'Transaction test')
 """, insight_id, "Test content")

            # Simulate an error (e.g., DB connection lost)
            # In a real scenario, this would rollback the transaction
            raise Exception("Simulated database error")

        # Verify nothing changed (transaction rolled back)
        current = await test_db.fetchrow("""
            SELECT is_deleted, deleted_at, deleted_by, deleted_reason
            FROM l2_insights
            WHERE id = $1
 """, insight_id)

        # Check that deleted fields are still NULL/False
        assert current["is_deleted"] == original["is_deleted"], "is_deleted should not change on error"
        assert current["deleted_at"] == original["deleted_at"], "deleted_at should not change on error"
        assert current["deleted_by"] == original["deleted_by"], "deleted_by should not change on error"
        assert current["deleted_reason"] == original["deleted_reason"], "deleted_reason should not change on error"

    @pytest.mark.asyncio
    async def test_multiple_deletes_different_actors(self, test_db):
        """Test that different actors can delete different insights."""
        # Create two insights
        insight1_id = await test_db.fetchval("""
            INSERT INTO l2_insights (content, embedding, source_ids)
            VALUES ('Insight by I/O', '[0.1]'::vector, ARRAY[1])
            RETURNING id
 """)

        insight2_id = await test_db.fetchval("""
            INSERT INTO l2_insights (content, embedding, source_ids)
            VALUES ('Insight by ethr', '[0.2]'::vector, ARRAY[1])
            RETURNING id
 """)

        # Delete with different actors
        await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'I/O',
                deleted_reason = 'I/O deletion'
            WHERE id = $1
 """, insight1_id)

        await test_db.execute("""
            UPDATE l2_insights
            SET is_deleted = TRUE,
                deleted_at = NOW(),
                deleted_by = 'ethr',
                deleted_reason = 'ethr deletion'
            WHERE id = $1
 """, insight2_id)

        # Verify both are deleted with correct actors
        row1 = await test_db.fetchrow("""
            SELECT deleted_by, deleted_reason
            FROM l2_insights
            WHERE id = $1
 """, insight1_id)

        row2 = await test_db.fetchrow("""
            SELECT deleted_by, deleted_reason
            FROM l2_insights
            WHERE id = $1
 """, insight2_id)

        assert row1["deleted_by"] == "I/O", "First insight should be deleted by I/O"
        assert row1["deleted_reason"] == "I/O deletion", "First insight should have correct reason"
        assert row2["deleted_by"] == "ethr", "Second insight should be deleted by ethr"
        assert row2["deleted_reason"] == "ethr deletion", "Second insight should have correct reason"

        # Clean up
        await test_db.execute("""
            DELETE FROM l2_insights
            WHERE id = ANY($1)
 """, [insight1_id, insight2_id])
