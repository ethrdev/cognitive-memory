"""
SSL Timeout Fix Tests

Tests for the SSL connection timeout fix (TECH-DEBT-SSL-CONNECTION.md).

Verifies that:
1. TCP keep-alive settings are properly configured
2. Periodic pool validator thread works correctly
3. Connections stay alive after idle periods (>30 seconds)
4. Graceful shutdown stops the validator thread

Story: Tech-Debt SSL Fix (2026-01-25)
"""

import os
import time
from unittest.mock import MagicMock, patch

import pytest


class TestTCPKeepAliveSettings:
    """Test TCP keep-alive configuration in connection pool."""

    def test_initialize_pool_sync_with_tcp_keepalive_defaults(self):
        """
        GIVEN: Connection pool is initialized
        WHEN: using default TCP keep-alive settings
        THEN: pool should be created with keep-alive enabled
        """
        from mcp_server.db.connection import initialize_pool_sync

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            # Mock the SimpleConnectionPool and async initialization
            with patch("mcp_server.db.connection.pool.SimpleConnectionPool") as mock_pool:
                mock_pool_instance = MagicMock()
                mock_pool_instance.minconn = 1
                mock_pool_instance.maxconn = 10
                mock_pool_instance._pool = []
                mock_pool_instance._used = []
                mock_pool.return_value = mock_pool_instance

                initialize_pool_sync()

                # Verify pool was created with TCP keep-alive settings
                mock_pool.assert_called_once()
                call_kwargs = mock_pool.call_args[1]
                assert "keepalives_idle" in call_kwargs
                assert call_kwargs["keepalives_idle"] == 10
                assert call_kwargs["keepalives_interval"] == 10
                assert call_kwargs["keepalives_count"] == 3

    def test_initialize_pool_sync_with_custom_tcp_keepalive(self):
        """
        GIVEN: Connection pool is initialized
        WHEN: using custom TCP keep-alive settings
        THEN: pool should be created with custom values
        """
        from mcp_server.db.connection import initialize_pool_sync

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            with patch("mcp_server.db.connection.pool.SimpleConnectionPool") as mock_pool:
                mock_pool_instance = MagicMock()
                mock_pool_instance.minconn = 1
                mock_pool_instance.maxconn = 10
                mock_pool_instance._pool = []
                mock_pool_instance._used = []
                mock_pool.return_value = mock_pool_instance

                initialize_pool_sync(
                    tcp_keepalives_idle=20,
                    tcp_keepalives_interval=15,
                    tcp_keepalives_count=5,
                )

                # Verify custom settings were applied
                call_kwargs = mock_pool.call_args[1]
                assert call_kwargs["keepalives_idle"] == 20
                assert call_kwargs["keepalives_interval"] == 15
                assert call_kwargs["keepalives_count"] == 5


class TestPoolValidatorThread:
    """Test periodic pool validator thread functionality."""

    def test_pool_validator_thread_started_on_init_sync(self):
        """
        GIVEN: Connection pool is initialized
        WHEN: initialization completes
        THEN: pool validator thread should be started
        """
        from mcp_server.db.connection import _pool_validator_thread, initialize_pool_sync

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            with patch("mcp_server.db.connection.pool.SimpleConnectionPool") as mock_pool:
                mock_pool_instance = MagicMock()
                mock_pool_instance.minconn = 1
                mock_pool_instance.maxconn = 10
                mock_pool_instance._pool = []
                mock_pool_instance._used = []
                mock_pool.return_value = mock_pool_instance

                with patch("mcp_server.db.connection.threading.Thread") as mock_thread:
                    mock_thread_instance = MagicMock()
                    mock_thread_instance.is_alive.return_value = False
                    mock_thread.return_value = mock_thread_instance

                    initialize_pool_sync()

                    # Verify thread was created and started
                    mock_thread.assert_called_once()
                    assert mock_thread.call_args[1]["target"] is not None
                    assert mock_thread.call_args[1]["daemon"] is True
                    assert "name" in mock_thread.call_args[1]
                    mock_thread_instance.start.assert_called_once()

    def test_pool_validator_loop_executes_periodically(self):
        """
        GIVEN: Pool validator thread is running
        WHEN: interval_seconds elapses
        THEN: validator should check connection health
        """
        from mcp_server.db.connection import _pool_validator_loop

        # Create a mock pool
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"pool_validator": 1}
        mock_pool.getconn.return_value = mock_conn
        mock_pool.putconn = MagicMock()

        # Mock the stop event to trigger quickly
        mock_stop_event = MagicMock()

        # Create a counter for the number of iterations
        iteration_count = [0]

        def wait_side_effect(timeout=None):
            iteration_count[0] += 1
            if iteration_count[0] >= 2:
                return True  # Stop after 2 iterations
            return False  # Continue running

        mock_stop_event.wait.side_effect = wait_side_effect
        mock_stop_event.is_set.return_value = False

        with patch("mcp_server.db.connection._connection_pool", mock_pool):
            with patch("mcp_server.db.connection._pool_validator_stop_event", mock_stop_event):
                # Run the validator loop with short interval
                _pool_validator_loop(interval_seconds=0.01)

                # Verify connections were validated at least once
                assert mock_pool.getconn.call_count >= 1
                assert mock_conn.cursor.call_count >= 1
                assert mock_cursor.execute.call_count >= 1


class TestIdleConnectionHandling:
    """Test that connections stay alive after idle periods."""

    @pytest.mark.integration
    def test_connection_stays_alive_after_idle_period_sync(self, database_url: str):
        """
        GIVEN: Connection is acquired from pool
        WHEN: waiting >30 seconds (idle period)
        THEN: next connection should succeed without SSL error

        This is an integration test that requires a real database.
        """
        from mcp_server.db.connection import (
            close_all_connections,
            get_connection_sync,
            initialize_pool_sync,
        )

        # Initialize pool with TCP keep-alive
        initialize_pool_sync()

        try:
            # First connection
            with get_connection_sync() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                assert result["test"] == 1
                print("First connection successful")

            # Wait for >30 seconds (idle period that would cause SSL timeout)
            print("Waiting 35 seconds to test idle connection handling...")
            time.sleep(35)

            # Second connection after idle - should succeed without retry
            with get_connection_sync() as conn2:
                cursor2 = conn2.cursor()
                cursor2.execute("SELECT 2 as test")
                result2 = cursor2.fetchone()
                assert result2["test"] == 2
                print("✓ Connection survived idle period - SSL timeout fix working!")

        finally:
            close_all_connections()


class TestGracefulShutdown:
    """Test graceful shutdown of pool validator thread."""

    def test_close_all_connections_stops_validator_thread(self):
        """
        GIVEN: Pool with validator thread running
        WHEN: close_all_connections is called
        THEN: validator thread should be stopped gracefully
        """
        from mcp_server.db.connection import (
            _pool_validator_stop_event,
            _pool_validator_thread,
            close_all_connections,
            initialize_pool_sync,
        )

        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test:test@localhost/test"}):
            with patch("mcp_server.db.connection.pool.SimpleConnectionPool") as mock_pool:
                mock_pool_instance = MagicMock()
                mock_pool_instance.minconn = 1
                mock_pool_instance.maxconn = 10
                mock_pool_instance._pool = []
                mock_pool_instance._used = []
                mock_pool.return_value = mock_pool_instance

                with patch("mcp_server.db.connection.threading.Thread") as mock_thread:
                    mock_thread_instance = MagicMock()
                    mock_thread_instance.is_alive.return_value = False
                    mock_thread.return_value = mock_thread_instance

                    # Initialize pool (creates validator thread)
                    initialize_pool_sync()

                    # Verify thread was created
                    assert _pool_validator_thread is not None

                    # Close all connections
                    close_all_connections()

                    # Verify stop event was set
                    _pool_validator_stop_event.set.assert_called()

                    # Verify thread was joined
                    mock_thread_instance.join.assert_called()

    def test_close_all_connections_handles_missing_thread(self):
        """
        GIVEN: Pool without validator thread
        WHEN: close_all_connections is called
        THEN: should not raise error
        """
        from mcp_server.db.connection import close_all_connections

        # Import and set thread to None
        from mcp_server import db

        original_thread = db.connection._pool_validator_thread
        db.connection._pool_validator_thread = None

        try:
            # Should not raise error
            close_all_connections()
        finally:
            # Restore original value
            db.connection._pool_validator_thread = original_thread


class TestRetryLogic:
    """Test that retry logic still works for transient errors."""

    def test_ssl_error_is_transient(self):
        """
        GIVEN: SSL connection error occurs
        WHEN: error is checked for transience
        THEN: should be classified as transient (triggers retry)
        """
        from mcp_server.db.connection import _is_transient_error

        # Test SSL error pattern
        ssl_error = Exception("SSL connection has been closed unexpectedly")
        assert _is_transient_error(ssl_error) is True

    def test_other_transient_errors(self):
        """
        GIVEN: Various transient connection errors occur
        WHEN: errors are checked for transience
        THEN: should be classified as transient
        """
        from mcp_server.db.connection import _is_transient_error

        test_cases = [
            "connection reset by peer",
            "connection timed out",
            "server closed the connection unexpectedly",
            "could not connect to server",
            "the connection is closed",
        ]

        for error_msg in test_cases:
            error = Exception(error_msg)
            assert _is_transient_error(error) is True, f"Failed for: {error_msg}"

    def test_non_transient_errors(self):
        """
        GIVEN: Non-transient database errors occur
        WHEN: errors are checked for transience
        THEN: should NOT be classified as transient
        """
        from mcp_server.db.connection import _is_transient_error

        non_transient_errors = [
            Exception("syntax error at or near"),
            Exception("relation does not exist"),
            Exception("duplicate key value violates unique constraint"),
        ]

        for error in non_transient_errors:
            assert _is_transient_error(error) is False
