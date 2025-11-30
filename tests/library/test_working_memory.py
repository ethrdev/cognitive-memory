"""
Tests for WorkingMemory API implementation.

Tests cover all WorkingMemory operations:
- add() with importance validation, LRU eviction, and stale memory archiving
- list() with correct sorting
- get() with LRU touch functionality
- clear() with stale memory archiving
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from cognitive_memory import MemoryStore
from cognitive_memory.exceptions import ConnectionError, ValidationError
from cognitive_memory.types import WorkingMemoryItem, WorkingMemoryResult


class TestWorkingMemoryAdd:
    """Test WorkingMemory.add() method."""

    def test_add_simple_item(self):
        """Test adding a simple item without eviction."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            # Setup mock connection
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock INSERT returning ID
            mock_cursor.fetchone.side_effect = [
                {"id": 1},  # Insert result
                {"count": 1},  # Count check
                {"count": 1},  # Final count
            ]

            # Create MemoryStore and test
            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.add("Test content", importance=0.5)

            assert isinstance(result, WorkingMemoryResult)
            assert result.added_id == 1
            assert result.evicted_id is None
            assert result.archived_id is None
            assert result.current_count == 1

    def test_add_with_default_importance(self):
        """Test adding item with default importance (0.5)."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            mock_cursor.fetchone.side_effect = [
                {"id": 2},
                {"count": 1},
                {"count": 1},
            ]

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.add("Test content")  # No importance specified

            assert result.added_id == 2
            assert result.current_count == 1

    def test_add_importance_validation_low(self):
        """Test ValidationError for importance < 0.0."""
        store = MemoryStore("postgresql://test")
        store._is_connected = True

        with pytest.raises(ValidationError, match="Importance must be between 0.0 and 1.0"):
            store.working.add("Test content", importance=-0.1)

    def test_add_importance_validation_high(self):
        """Test ValidationError for importance > 1.0."""
        store = MemoryStore("postgresql://test")
        store._is_connected = True

        with pytest.raises(ValidationError, match="Importance must be between 0.0 and 1.0"):
            store.working.add("Test content", importance=1.1)

    def test_add_content_validation_empty(self):
        """Test ValidationError for empty content."""
        store = MemoryStore("postgresql://test")
        store._is_connected = True

        with pytest.raises(ValidationError, match="Content must be a non-empty string"):
            store.working.add("")

    def test_add_content_validation_whitespace_only(self):
        """Test ValidationError for whitespace-only content."""
        store = MemoryStore("postgresql://test")
        store._is_connected = True

        with pytest.raises(ValidationError, match="Content must be a non-empty string"):
            store.working.add("   \t\n   ")

    def test_add_connection_validation(self):
        """Test ConnectionError when not connected."""
        store = MemoryStore("postgresql://test")
        store._is_connected = False

        with pytest.raises(ConnectionError, match="WorkingMemory is not connected"):
            store.working.add("Test content")

    def test_add_lru_eviction_non_critical(self):
        """Test LRU eviction of non-critical item (importance <= 0.8)."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Simulate adding 11th item, triggering eviction
            mock_cursor.fetchone.side_effect = [
                {"id": 11},  # New item insert
                {"count": 11},  # Capacity check (over limit)
                {"id": 1, "importance": 0.5},  # LRU item to evict (non-critical)
                {"count": 10},  # Final count
            ]

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.add("New item", importance=0.7)

            assert result.added_id == 11
            assert result.evicted_id == 1
            assert result.archived_id is None  # Non-critical, not archived
            assert result.current_count == 10

    def test_add_lru_eviction_critical_item(self):
        """Test LRU eviction with archiving of critical item (importance > 0.8)."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Simulate adding 11th item, triggering eviction of critical item
            mock_cursor.fetchone.side_effect = [
                {"id": 11},  # New item insert
                {"count": 11},  # Capacity check (over limit)
                {"id": 1, "importance": 0.9},  # LRU item to evict (critical)
                {"id": 100},  # Archive result
                {"count": 10},  # Final count
            ]

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.add("New item", importance=0.7)

            assert result.added_id == 11
            assert result.evicted_id == 1
            assert result.archived_id == 100  # Critical item archived
            assert result.current_count == 10

    def test_add_lru_eviction_all_critical(self):
        """Test LRU eviction when all items are critical."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # All items critical (no non-critical found), force evict oldest
            mock_cursor.fetchone.side_effect = [
                {"id": 11},  # New item insert
                {"count": 11},  # Capacity check (over limit)
                None,  # No non-critical items found
                {"id": 1, "importance": 0.9},  # Force evict oldest critical
                {"id": 100},  # Archive result
                {"count": 10},  # Final count
            ]

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.add("New item", importance=0.7)

            assert result.added_id == 11
            assert result.evicted_id == 1
            assert result.archived_id == 100
            assert result.current_count == 10


class TestWorkingMemoryList:
    """Test WorkingMemory.list() method."""

    def test_list_empty(self):
        """Test listing when working memory is empty."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Empty result
            mock_cursor.fetchall.return_value = []

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.list()

            assert result == []
            mock_cursor.execute.assert_called_once()

    def test_list_with_items(self):
        """Test listing with multiple items."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Mock database results
            now = datetime.now()
            mock_cursor.fetchall.return_value = [
                {
                    "id": 3,
                    "content": "Item 3",
                    "importance": 0.9,
                    "last_accessed": now,
                    "created_at": now,
                },
                {
                    "id": 2,
                    "content": "Item 2",
                    "importance": 0.7,
                    "last_accessed": now,
                    "created_at": now,
                },
                {
                    "id": 1,
                    "content": "Item 1",
                    "importance": 0.5,
                    "last_accessed": now,
                    "created_at": now,
                },
            ]

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.list()

            assert len(result) == 3
            for item in result:
                assert isinstance(item, WorkingMemoryItem)

            # Check ordering (should be by last_accessed DESC)
            assert result[0].id == 3
            assert result[1].id == 2
            assert result[2].id == 1

    def test_list_connection_validation(self):
        """Test ConnectionError when not connected."""
        store = MemoryStore("postgresql://test")
        store._is_connected = False

        with pytest.raises(ConnectionError, match="WorkingMemory is not connected"):
            store.working.list()


class TestWorkingMemoryGet:
    """Test WorkingMemory.get() method."""

    def test_get_existing_item(self):
        """Test getting an existing item with LRU touch."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            now = datetime.now()
            mock_cursor.fetchone.side_effect = [
                {
                    "id": 1,
                    "content": "Test content",
                    "importance": 0.7,
                    "last_accessed": now,
                    "created_at": now,
                }
            ]

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.get(1)

            assert isinstance(result, WorkingMemoryItem)
            assert result.id == 1
            assert result.content == "Test content"
            assert result.importance == 0.7

            # Verify LRU touch was called
            assert mock_cursor.execute.call_count == 2

    def test_get_nonexistent_item(self):
        """Test getting a non-existent item."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            # Item not found
            mock_cursor.fetchone.return_value = None

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.get(999)

            assert result is None

    def test_get_invalid_id(self):
        """Test ValidationError for invalid item ID."""
        store = MemoryStore("postgresql://test")
        store._is_connected = True

        with pytest.raises(ValidationError, match="Item ID must be a positive integer"):
            store.working.get(0)

        with pytest.raises(ValidationError, match="Item ID must be a positive integer"):
            store.working.get(-1)

        with pytest.raises(ValidationError, match="Item ID must be a positive integer"):
            store.working.get("not_an_int")

    def test_get_connection_validation(self):
        """Test ConnectionError when not connected."""
        store = MemoryStore("postgresql://test")
        store._is_connected = False

        with pytest.raises(ConnectionError, match="WorkingMemory is not connected"):
            store.working.get(1)


class TestWorkingMemoryClear:
    """Test WorkingMemory.clear() method."""

    def test_clear_with_items(self):
        """Test clearing working memory with items."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            mock_cursor.fetchone.side_effect = [
                {"count": 5},  # Count before clear
            ]

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.clear()

            assert result == 5
            assert mock_cursor.execute.call_count == 2  # Archive + Delete

    def test_clear_empty(self):
        """Test clearing empty working memory."""
        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            mock_conn = MagicMock()
            mock_conn_mgr.return_value.get_connection.return_value.__enter__.return_value = mock_conn
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

            mock_cursor.fetchone.side_effect = [
                {"count": 0},  # Empty count
            ]

            store = MemoryStore("postgresql://test")
            store._is_connected = True
            result = store.working.clear()

            assert result == 0

    def test_clear_connection_validation(self):
        """Test ConnectionError when not connected."""
        store = MemoryStore("postgresql://test")
        store._is_connected = False

        with pytest.raises(ConnectionError, match="WorkingMemory is not connected"):
            store.working.clear()


class TestWorkingMemoryIntegration:
    """Integration tests for WorkingMemory operations."""

    def test_lazy_initialization(self):
        """Test that store.working property is lazy-initialized."""
        store = MemoryStore("postgresql://test")

        # WorkingMemory should not be initialized yet
        assert store._working is None

        # Accessing the property should create it
        with patch.object(store.working, '_connection_manager', store._connection_manager):
            working = store.working
            assert working is not None
            assert store._working is working

    def test_connection_pool_sharing(self):
        """Test that WorkingMemory shares connection pool with MemoryStore."""
        store = MemoryStore("postgresql://test")

        with patch('cognitive_memory.store.ConnectionManager') as mock_conn_mgr:
            # Both should use the same connection manager
            working = store.working
            assert working._connection_manager is store._connection_manager