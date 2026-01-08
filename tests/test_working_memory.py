"""
Unit tests for update_working_memory and delete_working_memory tools.

Tests cover:
- Valid item insertion
- Capacity enforcement with LRU eviction
- Importance override protection
- Stale memory archival
- Edge cases and error handling
- Idempotent deletion of working memory entries
"""

import asyncio
import os
import sys
import time

import pytest

# Add the mcp_server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.db.connection import (
    close_all_connections,
    get_connection,
    initialize_pool,
)
from mcp_server.tools import (
    add_working_memory_item,
    archive_to_stale_memory,
    evict_lru_item,
    force_evict_oldest_critical,
    handle_update_working_memory,
    handle_delete_working_memory,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initialize database connection pool for tests."""
    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv(".env.development")

    # Initialize connection pool
    initialize_pool()

    yield

    # Clean up
    close_all_connections()


class TestWorkingMemoryInsertion:
    """Test Working Memory Insertion Logic."""

    def test_valid_item_insertion(self):
        """Test 1: Valid item insertion - verify item added to DB with correct importance and timestamp."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Add item
            added_id = asyncio.run(add_working_memory_item("Test content", 0.7, conn))
            assert isinstance(added_id, int)
            assert added_id > 0

            # Verify item was added correctly
            cursor.execute(
                "SELECT content, importance, last_accessed FROM working_memory WHERE id=%s;",
                (added_id,),
            )
            result = cursor.fetchone()
            assert result["content"] == "Test content"
            assert result["importance"] == 0.7
            assert result["last_accessed"] is not None  # last_accessed timestamp

            conn.commit()

    def test_invalid_importance(self):
        """Test 7: Invalid importance - importance=1.5, verify error returned."""
        with get_connection() as conn:
            with pytest.raises(ValueError) as exc_info:
                asyncio.run(add_working_memory_item("Test", 1.5, conn))

            assert "Importance must be between 0.0 and 1.0" in str(exc_info.value)

    def test_importance_boundary_values(self):
        """Test importance boundary values (0.0 and 1.0)."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Test lower boundary
            added_id_1 = asyncio.run(
                add_working_memory_item("Low importance", 0.0, conn)
            )
            assert isinstance(added_id_1, int)

            # Test upper boundary
            added_id_2 = asyncio.run(
                add_working_memory_item("High importance", 1.0, conn)
            )
            assert isinstance(added_id_2, int)

            # Verify both items exist
            cursor.execute("SELECT COUNT(*) as count FROM working_memory;")
            count = cursor.fetchone()["count"]
            assert count == 2

            conn.commit()


class TestLRUEviction:
    """Test LRU Eviction Logic with Importance Override."""

    def test_importance_override(self):
        """Test 3: Importance override - add 10 items (all importance >0.8), verify all 10 remain in working_memory (no eviction)."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Add 10 critical items (importance >0.8)
            for i in range(10):
                asyncio.run(add_working_memory_item(f"Critical item {i}", 0.9, conn))

            conn.commit()

            # Check eviction - should return None (no evictable items)
            evicted_id = asyncio.run(evict_lru_item(conn))
            assert evicted_id is None

            # Verify all 10 items remain
            cursor.execute("SELECT COUNT(*) as count FROM working_memory;")
            count = cursor.fetchone()["count"]
            assert count == 10

    def test_mixed_importance(self):
        """Test 4: Mixed importance - add 5 critical (>0.8) + 10 normal items, verify only normal items evicted, 5 critical + 5 normal remain."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Add 5 critical items first
            for i in range(5):
                asyncio.run(add_working_memory_item(f"Critical item {i}", 0.9, conn))

            # Add 10 normal items
            for i in range(10):
                asyncio.run(add_working_memory_item(f"Normal item {i}", 0.6, conn))

            conn.commit()

            # Should evict oldest normal item
            evicted_id = asyncio.run(evict_lru_item(conn))
            assert evicted_id is not None

            # Verify evicted item is a normal item (importance <= 0.8)
            cursor.execute(
                "SELECT importance FROM working_memory WHERE id=%s;", (evicted_id,)
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["importance"] <= 0.8

    def test_all_critical_force_eviction(self):
        """Test 10: Edge case - all 10 items critical (importance >0.8), verify force eviction."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Add 10 critical items
            for i in range(10):
                asyncio.run(add_working_memory_item(f"Critical item {i}", 0.9, conn))

            conn.commit()

            # Force eviction should return oldest item ID
            force_evicted_id = asyncio.run(force_evict_oldest_critical(conn))
            assert isinstance(force_evicted_id, int)
            assert force_evicted_id > 0

            # Verify the item exists
            cursor.execute(
                "SELECT content FROM working_memory WHERE id=%s;", (force_evicted_id,)
            )
            result = cursor.fetchone()
            assert result is not None
            assert "Critical item" in result["content"]

    def test_empty_working_memory_force_eviction(self):
        """Test force eviction on empty working memory."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Should raise RuntimeError
            with pytest.raises(RuntimeError) as exc_info:
                asyncio.run(force_evict_oldest_critical(conn))

            assert "Working Memory is empty" in str(exc_info.value)


class TestStaleMemoryArchival:
    """Test Stale Memory Archival."""

    def test_stale_memory_archival(self):
        """Test 5: Stale Memory archival - verify evicted items in stale_memory table with reason "LRU_EVICTION"."""
        with get_connection() as conn:
            # Clean up both tables
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            cursor.execute("DELETE FROM stale_memory;")
            conn.commit()

            # Add item to working memory
            working_id = asyncio.run(
                add_working_memory_item("To be archived", 0.7, conn)
            )
            conn.commit()

            # Archive it
            archive_id = asyncio.run(
                archive_to_stale_memory(working_id, "LRU_EVICTION", conn)
            )
            assert isinstance(archive_id, int)
            assert archive_id > 0

            # Verify item in stale_memory
            cursor.execute(
                "SELECT original_content, importance, reason FROM stale_memory WHERE id=%s;",
                (archive_id,),
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["original_content"] == "To be archived"
            assert result["importance"] == 0.7
            assert result["reason"] == "LRU_EVICTION"

            conn.commit()

    def test_manual_archive(self):
        """Test 9: Manual archive - test manual archival with reason "MANUAL_ARCHIVE"."""
        with get_connection() as conn:
            # Clean up both tables
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            cursor.execute("DELETE FROM stale_memory;")
            conn.commit()

            # Add item to working memory
            working_id = asyncio.run(
                add_working_memory_item("Manual archive test", 0.5, conn)
            )
            conn.commit()

            # Archive it manually
            archive_id = asyncio.run(
                archive_to_stale_memory(working_id, "MANUAL_ARCHIVE", conn)
            )
            assert isinstance(archive_id, int)

            # Verify reason
            cursor.execute(
                "SELECT reason FROM stale_memory WHERE id=%s;", (archive_id,)
            )
            result = cursor.fetchone()
            assert result["reason"] == "MANUAL_ARCHIVE"

            conn.commit()

    def test_archive_nonexistent_item(self):
        """Test archiving non-existent working memory item."""
        with get_connection() as conn:
            with pytest.raises(ValueError) as exc_info:
                asyncio.run(archive_to_stale_memory(99999, "LRU_EVICTION", conn))

            assert "Working Memory item 99999 not found" in str(exc_info.value)


class TestCapacityEnforcement:
    """Test capacity enforcement and automatic eviction."""

    def test_capacity_enforcement(self):
        """Test 2: Capacity enforcement - add 15 items, verify 5 evicted, maintain ≤10 items total."""
        with get_connection() as conn:
            # Clean up both tables
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            cursor.execute("DELETE FROM stale_memory;")
            conn.commit()

            # Add 15 items via the main tool (triggers automatic eviction)
            for i in range(15):
                result = asyncio.run(
                    handle_update_working_memory(
                        {"content": f"Item {i}", "importance": 0.6}
                    )
                )
                assert result["status"] == "success"

            conn.commit()

            # Verify working memory has exactly 10 items
            cursor.execute("SELECT COUNT(*) as count FROM working_memory;")
            count = cursor.fetchone()["count"]
            assert count == 10

            # Verify stale memory has 5 archived items
            cursor.execute("SELECT COUNT(*) as count FROM stale_memory;")
            stale_count = cursor.fetchone()["count"]
            assert stale_count == 5

            # Verify all archived items have reason "LRU_EVICTION"
            cursor.execute(
                "SELECT COUNT(*) as count FROM stale_memory WHERE reason='LRU_EVICTION';"
            )
            eviction_count = cursor.fetchone()["count"]
            assert eviction_count == 5

    def test_insertion_order_eviction(self):
        """Test 6: Insertion order eviction - add 10 items at T0, T1, T2..., add 11th item at T10, verify item from T0 evicted (oldest by last_accessed)."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            cursor.execute("DELETE FROM stale_memory;")
            conn.commit()

            # Add 10 items with slight delays to ensure different timestamps
            first_items = []
            for i in range(10):
                result = asyncio.run(
                    handle_update_working_memory(
                        {"content": f"Time-based item {i}", "importance": 0.6}
                    )
                )
                first_items.append(result["added_id"])
                # Small delay to ensure different timestamps
                time.sleep(0.01)

            conn.commit()

            # Add 11th item (should trigger eviction of oldest)
            result = asyncio.run(
                handle_update_working_memory(
                    {"content": "Eviction trigger item", "importance": 0.6}
                )
            )

            assert result["status"] == "success"
            assert result["evicted_id"] is not None
            assert result["archived_id"] is not None

            # Verify the evicted item was the first one added
            assert result["evicted_id"] == first_items[0]

            # Verify archived item details
            cursor.execute(
                "SELECT original_content, reason FROM stale_memory WHERE id=%s;",
                (result["archived_id"],),
            )
            archived = cursor.fetchone()
            assert archived["original_content"] == "Time-based item 0"
            assert archived["reason"] == "LRU_EVICTION"

            conn.commit()


class TestUpdateWorkingMemoryTool:
    """Test the main update_working_memory tool."""

    def test_mcp_tool_call_end_to_end(self):
        """Test: MCP Tool Call End-to-End - call update_working_memory and verify response structure."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Test basic call
            result = asyncio.run(
                handle_update_working_memory(
                    {"content": "Test content", "importance": 0.6}
                )
            )

            assert result["status"] == "success"
            assert "added_id" in result
            assert isinstance(result["added_id"], int)
            assert result["added_id"] > 0
            assert result["evicted_id"] is None  # No eviction on first item
            assert result["archived_id"] is None  # No archival on first item

    def test_default_importance(self):
        """Test tool with default importance value."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Call without importance parameter
            result = asyncio.run(
                handle_update_working_memory({"content": "Default importance test"})
            )

            assert result["status"] == "success"

            # Verify default importance was applied
            cursor.execute(
                "SELECT importance FROM working_memory WHERE id=%s;",
                (result["added_id"],),
            )
            db_result = cursor.fetchone()
            assert db_result["importance"] == 0.5

            conn.commit()

    def test_empty_content(self):
        """Test 8: Empty content - content="", verify error returned."""
        result = asyncio.run(
            handle_update_working_memory({"content": "", "importance": 0.6})
        )

        assert "error" in result
        assert "Content is required" in result["error"]
        assert result["tool"] == "update_working_memory"

    def test_missing_content(self):
        """Test missing content parameter."""
        result = asyncio.run(handle_update_working_memory({"importance": 0.6}))

        assert "error" in result
        assert "Content is required" in result["error"]
        assert result["tool"] == "update_working_memory"

    def test_invalid_importance_response(self):
        """Test invalid importance in tool response."""
        result = asyncio.run(
            handle_update_working_memory({"content": "Test", "importance": 1.5})
        )

        assert "error" in result
        assert "Importance must be between 0.0 and 1.0" in result["error"]
        assert result["tool"] == "update_working_memory"

    def test_non_numeric_importance(self):
        """Test non-numeric importance value."""
        result = asyncio.run(
            handle_update_working_memory({"content": "Test", "importance": "high"})
        )

        assert "error" in result
        assert "Importance must be a number" in result["error"]
        assert result["tool"] == "update_working_memory"

    def test_critical_items_protection(self):
        """Test: Critical items protected - add 10 critical + 5 normal, verify only normal evicted."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            cursor.execute("DELETE FROM stale_memory;")
            conn.commit()

            # Add 10 critical items
            critical_ids = []
            for i in range(10):
                result = asyncio.run(
                    handle_update_working_memory(
                        {"content": f"Critical item {i}", "importance": 0.9}
                    )
                )
                critical_ids.append(result["added_id"])

            # Add 5 normal items (should trigger eviction of normal items only)
            normal_results = []
            for i in range(5):
                result = asyncio.run(
                    handle_update_working_memory(
                        {"content": f"Normal item {i}", "importance": 0.6}
                    )
                )
                normal_results.append(result)

            conn.commit()

            # All normal additions should have evicted something
            for result in normal_results:
                assert result["evicted_id"] is not None
                assert result["archived_id"] is not None

            # Verify all critical items still exist
            for critical_id in critical_ids:
                cursor.execute(
                    "SELECT id FROM working_memory WHERE id=%s;", (critical_id,)
                )
                assert cursor.fetchone() is not None

            # Verify working memory still has 10 items (5 critical + 5 normal)
            cursor.execute("SELECT COUNT(*) as count FROM working_memory;")
            count = cursor.fetchone()["count"]
            assert count == 10

            conn.commit()

    def test_force_eviction_all_critical(self):
        """Test: Force eviction - add 10 critical items, add 11th item → verify oldest critical item evicted."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            cursor.execute("DELETE FROM stale_memory;")
            conn.commit()

            # Add 10 critical items
            critical_results = []
            for i in range(10):
                result = asyncio.run(
                    handle_update_working_memory(
                        {"content": f"Critical item {i}", "importance": 0.9}
                    )
                )
                critical_results.append(result)

            # Add 11th critical item (should force evict oldest critical)
            result = asyncio.run(
                handle_update_working_memory(
                    {"content": "Forced eviction trigger", "importance": 0.9}
                )
            )

            assert result["status"] == "success"
            assert result["evicted_id"] is not None
            assert result["archived_id"] is not None

            # Verify the evicted item was the first critical item
            assert result["evicted_id"] == critical_results[0]["added_id"]

            # Verify working memory still has 10 items
            cursor.execute("SELECT COUNT(*) as count FROM working_memory;")
            count = cursor.fetchone()["count"]
            assert count == 10

            # Verify archived item was critical
            cursor.execute(
                "SELECT original_content, importance FROM stale_memory WHERE id=%s;",
                (result["archived_id"],),
            )
            archived = cursor.fetchone()
            assert archived["original_content"] == "Critical item 0"
            assert archived["importance"] == 0.9

            conn.commit()


class TestDeleteWorkingMemory:
    """Test delete_working_memory tool (idempotent deletion)."""

    def test_delete_existing_entry(self):
        """Test: Delete existing entry - returns {deleted_id: int, status: 'success'}."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Add an item
            add_result = asyncio.run(
                handle_update_working_memory(
                    {"content": "To be deleted", "importance": 0.6}
                )
            )
            item_id = add_result["added_id"]

            # Delete the item
            delete_result = asyncio.run(
                handle_delete_working_memory({"id": item_id})
            )

            assert delete_result["status"] == "success"
            assert delete_result["deleted_id"] == item_id

            # Verify item is actually deleted
            cursor.execute(
                "SELECT id FROM working_memory WHERE id = %s;", (item_id,)
            )
            assert cursor.fetchone() is None

    def test_delete_nonexistent_entry(self):
        """Test: Delete non-existent entry - returns {deleted_id: null, status: 'not_found'} (idempotent)."""
        # Use a very high ID that won't exist
        delete_result = asyncio.run(
            handle_delete_working_memory({"id": 999999})
        )

        assert delete_result["status"] == "not_found"
        assert delete_result["deleted_id"] is None

    def test_delete_idempotent_double_delete(self):
        """Test: Double delete - second delete returns not_found (idempotent behavior)."""
        with get_connection() as conn:
            # Clean up
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            conn.commit()

            # Add an item
            add_result = asyncio.run(
                handle_update_working_memory(
                    {"content": "Double delete test", "importance": 0.5}
                )
            )
            item_id = add_result["added_id"]

            # First delete - should succeed
            first_delete = asyncio.run(
                handle_delete_working_memory({"id": item_id})
            )
            assert first_delete["status"] == "success"
            assert first_delete["deleted_id"] == item_id

            # Second delete - should return not_found (idempotent)
            second_delete = asyncio.run(
                handle_delete_working_memory({"id": item_id})
            )
            assert second_delete["status"] == "not_found"
            assert second_delete["deleted_id"] is None

    def test_delete_missing_id_parameter(self):
        """Test: Missing id parameter - returns error."""
        delete_result = asyncio.run(
            handle_delete_working_memory({})
        )

        assert "error" in delete_result
        assert "Missing required 'id' parameter" in delete_result["details"]
        assert delete_result["tool"] == "delete_working_memory"

    def test_delete_invalid_id_type(self):
        """Test: Invalid id type (string) - returns error."""
        delete_result = asyncio.run(
            handle_delete_working_memory({"id": "not-an-int"})
        )

        assert "error" in delete_result
        assert "'id' must be an integer" in delete_result["details"]
        assert delete_result["tool"] == "delete_working_memory"

    def test_delete_invalid_id_negative(self):
        """Test: Invalid id (negative) - returns error."""
        delete_result = asyncio.run(
            handle_delete_working_memory({"id": -5})
        )

        assert "error" in delete_result
        assert "'id' must be >= 1" in delete_result["details"]
        assert delete_result["tool"] == "delete_working_memory"

    def test_delete_invalid_id_zero(self):
        """Test: Invalid id (zero) - returns error."""
        delete_result = asyncio.run(
            handle_delete_working_memory({"id": 0})
        )

        assert "error" in delete_result
        assert "'id' must be >= 1" in delete_result["details"]
        assert delete_result["tool"] == "delete_working_memory"

    def test_delete_no_archival(self):
        """Test: Deleted items are NOT archived (hard delete, no stale_memory entry)."""
        with get_connection() as conn:
            # Clean up both tables
            cursor = conn.cursor()
            cursor.execute("DELETE FROM working_memory;")
            cursor.execute("DELETE FROM stale_memory;")
            conn.commit()

            # Get initial stale_memory count
            cursor.execute("SELECT COUNT(*) as count FROM stale_memory;")
            initial_stale_count = cursor.fetchone()["count"]

            # Add an item
            add_result = asyncio.run(
                handle_update_working_memory(
                    {"content": "No archive test", "importance": 0.7}
                )
            )
            item_id = add_result["added_id"]

            # Delete the item (should NOT archive)
            delete_result = asyncio.run(
                handle_delete_working_memory({"id": item_id})
            )
            assert delete_result["status"] == "success"

            # Verify stale_memory count is unchanged (no archival)
            cursor.execute("SELECT COUNT(*) as count FROM stale_memory;")
            final_stale_count = cursor.fetchone()["count"]
            assert final_stale_count == initial_stale_count
