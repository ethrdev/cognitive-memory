"""
ATDD Tests: MemoryStore Core Class (Story 5.2)

These tests verify the core MemoryStore class functionality:
- Instantiation with connection string
- Factory method from_env()
- Context manager support
- Graceful error handling

Status: GREEN Phase (MemoryStore class implemented in Story 5.2)
Priority: P0 - Core functionality required for all other features
"""

import os
from unittest.mock import patch

import pytest


class TestMemoryStoreInstantiation:
    """P0: Verify MemoryStore can be instantiated correctly."""

    def test_instantiate_with_connection_string(self):
        """
        GIVEN: A valid PostgreSQL connection string
        WHEN: creating MemoryStore with connection_string parameter
        THEN: instance is created successfully

        Story: 5.2 - MemoryStore Core Class
        """
        from cognitive_memory import MemoryStore

        # Connection string format
        conn_string = "postgresql://user:pass@localhost:5432/cognitive_memory"

        store = MemoryStore(connection_string=conn_string)

        assert store is not None
        assert hasattr(store, "search")
        assert hasattr(store, "store_insight")
        assert hasattr(store, "working")
        assert hasattr(store, "episode")
        assert hasattr(store, "graph")

    def test_instantiate_with_from_env_factory(self):
        """
        GIVEN: DATABASE_URL environment variable is set
        WHEN: creating MemoryStore with from_env() factory
        THEN: instance is created using environment variable

        Story: 5.2 - MemoryStore Core Class
        """
        from cognitive_memory import MemoryStore

        # Set environment variable for test
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://test:test@localhost/test_db"},
        ):
            store = MemoryStore.from_env()

            assert store is not None

    def test_from_env_raises_error_when_no_database_url(self):
        """
        GIVEN: DATABASE_URL environment variable is NOT set
        WHEN: creating MemoryStore with from_env() factory
        THEN: raises ConnectionError with helpful message

        Risk Mitigation: R-006 (Missing DATABASE_URL)
        """
        from cognitive_memory import MemoryStore
        from cognitive_memory.exceptions import ConnectionError

        # Remove DATABASE_URL from environment
        env_without_db_url = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        with patch.dict(os.environ, env_without_db_url, clear=True):
            with pytest.raises(ConnectionError) as exc_info:
                MemoryStore.from_env()

            # Error message should be helpful
            assert "DATABASE_URL" in str(exc_info.value)


class TestMemoryStoreContextManager:
    """P0: Verify context manager support for automatic cleanup."""

    def test_context_manager_enters_successfully(self):
        """
        GIVEN: A valid MemoryStore instance
        WHEN: using with statement
        THEN: __enter__ returns the store instance

        Story: 5.2 - Context Manager Support
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections"):
            mock_status.return_value = {"initialized": False}

            with MemoryStore(connection_string="postgresql://test@localhost/test") as store:
                assert store is not None
                # Should be able to call methods inside context
                assert hasattr(store, "search")

    def test_context_manager_exits_cleanly(self):
        """
        GIVEN: A MemoryStore used as context manager
        WHEN: exiting the with block
        THEN: __exit__ is called and resources are cleaned up

        Story: 5.2 - Context Manager Support
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections") as mock_close:
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")

            with store:
                pass

            # close_all_connections should have been called
            mock_close.assert_called_once()

    def test_context_manager_handles_exceptions(self):
        """
        GIVEN: An exception occurs inside context manager
        WHEN: the exception propagates
        THEN: __exit__ is still called for cleanup

        Story: 5.2 - Graceful Error Handling
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections") as mock_close:
            mock_status.return_value = {"initialized": False}

            with pytest.raises(ValueError):
                with MemoryStore(connection_string="postgresql://test@localhost/test"):
                    # Simulate error during operation
                    raise ValueError("Test error")

            # Cleanup should still happen
            mock_close.assert_called_once()


class TestMemoryStoreSubModules:
    """P0: Verify sub-module access (working, episode, graph)."""

    def test_working_memory_accessor(self):
        """
        GIVEN: A MemoryStore instance
        WHEN: accessing store.working
        THEN: returns WorkingMemory instance

        Story: 5.5 - Working Memory Library API
        """
        from cognitive_memory import MemoryStore, WorkingMemory

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        assert hasattr(store, "working")
        assert isinstance(store.working, WorkingMemory)
        assert hasattr(store.working, "add")
        assert hasattr(store.working, "get_all")
        assert hasattr(store.working, "clear")

    def test_episode_memory_accessor(self):
        """
        GIVEN: A MemoryStore instance
        WHEN: accessing store.episode
        THEN: returns EpisodeMemory instance

        Story: 5.6 - Episode Memory Library API
        """
        from cognitive_memory import EpisodeMemory, MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        assert hasattr(store, "episode")
        assert isinstance(store.episode, EpisodeMemory)
        assert hasattr(store.episode, "store")
        assert hasattr(store.episode, "get_recent")

    def test_graph_store_accessor(self):
        """
        GIVEN: A MemoryStore instance
        WHEN: accessing store.graph
        THEN: returns GraphStore instance

        Story: 5.7 - Graph Query Neighbors Library API
        """
        from cognitive_memory import GraphStore, MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        assert hasattr(store, "graph")
        assert isinstance(store.graph, GraphStore)
        assert hasattr(store.graph, "add_node")
        assert hasattr(store.graph, "add_edge")
        assert hasattr(store.graph, "get_neighbors")
