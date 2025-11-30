"""
Tests for MemoryStore Core Class (Story 5.2)

Tests cover all Acceptance Criteria:
- AC-5.2.1: MemoryStore Constructor and DB-Connection
- AC-5.2.2: Context Manager Support
- AC-5.2.3: Manual Lifecycle Management
- AC-5.2.4: Factory Method from_env()
- AC-5.2.5: Sub-Object Accessor Properties

All tests use mocks to avoid requiring a real database connection.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest


class TestFromEnvFactoryMethod:
    """AC-5.2.4: Factory Method from_env()"""

    def test_from_env_reads_database_url(self):
        """
        GIVEN: DATABASE_URL environment variable is set
        WHEN: calling MemoryStore.from_env()
        THEN: MemoryStore is created with that connection string
        """
        from cognitive_memory import MemoryStore

        test_url = "postgresql://user:pass@host:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}):
            store = MemoryStore.from_env()

            assert store is not None
            assert store._connection_manager._connection_string == test_url

    def test_from_env_raises_without_database_url(self):
        """
        GIVEN: DATABASE_URL environment variable is NOT set
        WHEN: calling MemoryStore.from_env()
        THEN: ConnectionError is raised with helpful message
        """
        from cognitive_memory import MemoryStore
        from cognitive_memory.exceptions import ConnectionError

        # Clear DATABASE_URL from environment
        env_without_db_url = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
        with patch.dict(os.environ, env_without_db_url, clear=True):
            with pytest.raises(ConnectionError) as exc_info:
                MemoryStore.from_env()

            assert "DATABASE_URL" in str(exc_info.value)

    def test_from_env_raises_with_empty_database_url(self):
        """
        GIVEN: DATABASE_URL environment variable is empty string
        WHEN: calling MemoryStore.from_env()
        THEN: ConnectionError is raised
        """
        from cognitive_memory import MemoryStore
        from cognitive_memory.exceptions import ConnectionError

        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            with pytest.raises(ConnectionError) as exc_info:
                MemoryStore.from_env()

            assert "DATABASE_URL" in str(exc_info.value)


class TestMemoryStoreInstantiation:
    """AC-5.2.1: MemoryStore Constructor and DB-Connection"""

    def test_memorystore_init_with_connection_string(self):
        """
        GIVEN: A valid connection string
        WHEN: creating MemoryStore with connection_string parameter
        THEN: instance is created with that connection string
        """
        from cognitive_memory import MemoryStore

        conn_string = "postgresql://user:pass@localhost:5432/cognitive_memory"
        store = MemoryStore(connection_string=conn_string)

        assert store is not None
        assert store._connection_manager._connection_string == conn_string

    def test_memorystore_init_without_connection_string(self):
        """
        GIVEN: DATABASE_URL environment variable is set
        WHEN: creating MemoryStore without connection_string parameter
        THEN: instance is created (ConnectionManager reads from env)
        """
        from cognitive_memory import MemoryStore

        # MemoryStore without connection_string delegates to ConnectionManager
        # which reads DATABASE_URL from environment
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test@localhost/test"}):
            store = MemoryStore()

            assert store is not None
            # ConnectionManager reads from env when connection_string is None
            assert store._connection_manager._connection_string is not None

    def test_lazy_connection(self):
        """
        GIVEN: MemoryStore is instantiated
        WHEN: no connect() is called
        THEN: is_connected returns False (lazy connection)
        """
        from cognitive_memory import MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        # Connection is lazy - not connected until connect() is called
        assert store.is_connected is False


class TestConnectionPoolIntegration:
    """AC-5.2.1, AC-5.2.3: Connection Pool Integration"""

    def test_connect_initializes_pool(self):
        """
        GIVEN: MemoryStore instance
        WHEN: calling connect()
        THEN: initialize_pool is called with correct parameters
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool") as mock_init, \
             patch("mcp_server.db.connection.get_pool_status") as mock_status:
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")
            store.connect(min_connections=2, max_connections=20, connection_timeout=10)

            mock_init.assert_called_once_with(
                min_connections=2,
                max_connections=20,
                connection_timeout=10,
            )
            assert store.is_connected is True

    def test_close_closes_pool(self):
        """
        GIVEN: Connected MemoryStore
        WHEN: calling close()
        THEN: close_all_connections is called
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections") as mock_close:
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")
            store.connect()

            # Now close
            store.close()

            mock_close.assert_called_once()
            assert store.is_connected is False

    def test_connect_with_pool_parameters(self):
        """
        GIVEN: MemoryStore instance
        WHEN: calling connect() with custom pool parameters
        THEN: parameters are passed to initialize_pool
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool") as mock_init, \
             patch("mcp_server.db.connection.get_pool_status") as mock_status:
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")
            store.connect(
                min_connections=5,
                max_connections=50,
                connection_timeout=30
            )

            mock_init.assert_called_once_with(
                min_connections=5,
                max_connections=50,
                connection_timeout=30,
            )


class TestContextManagerSupport:
    """AC-5.2.2: Context Manager Support"""

    def test_context_manager_calls_connect_on_enter(self):
        """
        GIVEN: MemoryStore with auto_initialize=True (default)
        WHEN: entering context manager
        THEN: connect() is called
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections"):
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")

            with store as s:
                assert s.is_connected is True

    def test_context_manager_calls_close_on_exit(self):
        """
        GIVEN: MemoryStore used as context manager
        WHEN: exiting context
        THEN: close() is called
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections") as mock_close:
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")

            with store:
                pass

            # close_all_connections should be called after exiting context
            mock_close.assert_called_once()

    def test_context_manager_exception_safe(self):
        """
        GIVEN: Exception raised inside context manager
        WHEN: exception propagates
        THEN: close() is still called for cleanup
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections") as mock_close:
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")

            with pytest.raises(ValueError):
                with store:
                    raise ValueError("Test error")

            # close should still be called even after exception
            mock_close.assert_called_once()

    def test_context_manager_without_auto_initialize(self):
        """
        GIVEN: MemoryStore with auto_initialize=False
        WHEN: entering context manager
        THEN: connect() is NOT automatically called
        """
        from cognitive_memory import MemoryStore

        store = MemoryStore(
            connection_string="postgresql://test@localhost/test",
            auto_initialize=False
        )

        with store as s:
            # Should not be connected since auto_initialize=False
            assert s._is_connected is False


class TestIsConnectedProperty:
    """AC-5.2.3: is_connected Property"""

    def test_is_connected_false_initially(self):
        """
        GIVEN: Newly created MemoryStore
        WHEN: checking is_connected
        THEN: returns False
        """
        from cognitive_memory import MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        assert store.is_connected is False

    def test_is_connected_true_after_connect(self):
        """
        GIVEN: MemoryStore with connect() called
        WHEN: checking is_connected
        THEN: returns True
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status:
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")
            store.connect()

            assert store.is_connected is True

    def test_is_connected_false_after_close(self):
        """
        GIVEN: Connected MemoryStore
        WHEN: close() is called
        THEN: is_connected returns False
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections"):
            mock_status.return_value = {"initialized": False}

            store = MemoryStore(connection_string="postgresql://test@localhost/test")
            store.connect()
            assert store.is_connected is True

            store.close()
            assert store.is_connected is False


class TestSubObjectAccessorProperties:
    """AC-5.2.5: Sub-Object Accessor Properties"""

    def test_working_property_returns_working_memory(self):
        """
        GIVEN: MemoryStore instance
        WHEN: accessing store.working
        THEN: returns WorkingMemory instance
        """
        from cognitive_memory import MemoryStore, WorkingMemory

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        working = store.working

        assert isinstance(working, WorkingMemory)

    def test_episode_property_returns_episode_memory(self):
        """
        GIVEN: MemoryStore instance
        WHEN: accessing store.episode
        THEN: returns EpisodeMemory instance
        """
        from cognitive_memory import EpisodeMemory, MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        episode = store.episode

        assert isinstance(episode, EpisodeMemory)

    def test_graph_property_returns_graph_store(self):
        """
        GIVEN: MemoryStore instance
        WHEN: accessing store.graph
        THEN: returns GraphStore instance
        """
        from cognitive_memory import GraphStore, MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        graph = store.graph

        assert isinstance(graph, GraphStore)

    def test_sub_objects_share_connection_manager(self):
        """
        GIVEN: MemoryStore instance
        WHEN: accessing sub-objects
        THEN: all sub-objects share the same ConnectionManager
        """
        from cognitive_memory import MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        working = store.working
        episode = store.episode
        graph = store.graph

        # All should share the same ConnectionManager instance
        assert working._connection_manager is store._connection_manager
        assert episode._connection_manager is store._connection_manager
        assert graph._connection_manager is store._connection_manager

    def test_sub_objects_lazy_initialized(self):
        """
        GIVEN: MemoryStore instance
        WHEN: accessing sub-objects multiple times
        THEN: same instance is returned (lazy initialization)
        """
        from cognitive_memory import MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        # First access creates instance
        working1 = store.working
        episode1 = store.episode
        graph1 = store.graph

        # Second access returns same instance
        working2 = store.working
        episode2 = store.episode
        graph2 = store.graph

        assert working1 is working2
        assert episode1 is episode2
        assert graph1 is graph2

    def test_sub_objects_not_created_until_accessed(self):
        """
        GIVEN: MemoryStore instance
        WHEN: sub-objects are NOT accessed
        THEN: internal sub-object attributes remain None
        """
        from cognitive_memory import MemoryStore

        store = MemoryStore(connection_string="postgresql://test@localhost/test")

        # Internal attributes should be None before access
        assert store._working is None
        assert store._episode is None
        assert store._graph is None

        # After accessing working, only _working should be set
        _ = store.working
        assert store._working is not None
        assert store._episode is None
        assert store._graph is None


class TestFullLifecycle:
    """Integration tests for complete lifecycle"""

    def test_full_lifecycle_construct_connect_use_close(self):
        """
        GIVEN: MemoryStore instance
        WHEN: going through full lifecycle
        THEN: all steps work correctly
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections"):
            mock_status.return_value = {"initialized": False}

            # 1. Construct
            store = MemoryStore(connection_string="postgresql://test@localhost/test")
            assert store.is_connected is False

            # 2. Connect
            store.connect()
            assert store.is_connected is True

            # 3. Use (access sub-objects)
            working = store.working
            episode = store.episode
            graph = store.graph

            assert working is not None
            assert episode is not None
            assert graph is not None

            # 4. Close
            store.close()
            assert store.is_connected is False

    def test_context_manager_full_lifecycle(self):
        """
        GIVEN: MemoryStore used as context manager
        WHEN: using sub-objects inside context
        THEN: everything works and cleans up properly
        """
        from cognitive_memory import MemoryStore

        with patch("mcp_server.db.connection.initialize_pool"), \
             patch("mcp_server.db.connection.get_pool_status") as mock_status, \
             patch("mcp_server.db.connection.close_all_connections") as mock_close:
            mock_status.return_value = {"initialized": False}

            with MemoryStore(connection_string="postgresql://test@localhost/test") as store:
                assert store.is_connected is True

                # Access sub-objects
                working = store.working
                episode = store.episode
                graph = store.graph

                # All share connection manager
                assert working._connection_manager is store._connection_manager
                assert episode._connection_manager is store._connection_manager
                assert graph._connection_manager is store._connection_manager

            # After exiting, close should have been called
            mock_close.assert_called_once()
