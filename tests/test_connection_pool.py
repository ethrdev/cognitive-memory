"""
Tests for connection.py database connection functions.

Tests connection pool management, transient error detection,
RLS context integration, and pool status monitoring.

Story 11.4.2: Project Context Validation and RLS Integration
Story 11.6.1: pgvector iterative scan configuration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from mcp_server.db.connection import (
    _is_transient_error,
    get_pool_status,
    close_all_connections,
)
from psycopg2 import OperationalError


class TestIsTransientError:
    """Test suite for _is_transient_error function."""

    def test_transient_ssl_connection_closed(self):
        """Test that SSL connection closed error is detected as transient."""
        # Arrange - _is_transient_error only checks error message string
        error = OperationalError("SSL connection has been closed unexpectedly")

        # Act
        result = _is_transient_error(error)

        # Assert
        assert result is True, "SSL connection closed should be transient"

    def test_transient_connection_reset(self):
        """Test that connection reset error is detected as transient."""
        # Arrange
        error = OperationalError("connection reset by peer")

        # Act
        result = _is_transient_error(error)

        # Assert
        assert result is True, "Connection reset should be transient"

    def test_transient_connection_timeout(self):
        """Test that connection timeout error is detected as transient."""
        # Arrange
        error = OperationalError("connection timed out")

        # Act
        result = _is_transient_error(error)

        # Assert
        assert result is True, "Connection timeout should be transient"

    def test_transient_server_closed_connection(self):
        """Test that server closed connection error is detected as transient."""
        # Arrange
        error = OperationalError("server closed the connection unexpectedly")

        # Act
        result = _is_transient_error(error)

        # Assert
        assert result is True, "Server closed connection should be transient"

    def test_non_transient_syntax_error(self):
        """Test that non-transient errors are not detected as transient."""
        # Arrange
        error = OperationalError("syntax error at or near")

        # Act
        result = _is_transient_error(error)

        # Assert
        assert result is False, "Syntax error should NOT be transient"

    def test_non_transient_relation_not_exist(self):
        """Test that relation does not exist error is not transient."""
        # Arrange
        error = OperationalError("relation does not exist")

        # Act
        result = _is_transient_error(error)

        # Assert
        assert result is False, "Does not exist should NOT be transient"


class TestGetPoolStatus:
    """Test suite for get_pool_status function."""

    @patch("mcp_server.db.connection._connection_pool")
    def test_get_pool_status_when_pool_initialized(self, mock_pool):
        """Test pool status when pool is initialized."""
        # Arrange
        mock_pool.minconn = 1
        mock_pool.maxconn = 10
        mock_pool._used = [MagicMock()]  # 1 connection in use
        mock_pool._pool = [MagicMock(), MagicMock()]  # 2 idle connections

        # Act
        status = get_pool_status()

        # Assert
        assert status["initialized"] is True
        assert status["min_connections"] == 1
        assert status["max_connections"] == 10
        assert status["current_connections"] == 3  # 1 used + 2 idle

    @patch("mcp_server.db.connection._connection_pool", None)
    def test_get_pool_status_when_pool_not_initialized(self):
        """Test pool status when pool is None."""
        # Act
        status = get_pool_status()

        # Assert
        assert status["initialized"] is False
        assert status["min_connections"] == 0
        assert status["max_connections"] == 0
        assert status["current_connections"] == 0


class TestCloseAllConnections:
    """Test suite for close_all_connections function."""

    @patch("mcp_server.db.connection._connection_pool")
    def test_close_all_connections_closes_pool(self, mock_pool):
        """Test that all connections are closed and pool is removed."""
        # Arrange
        mock_pool.closeall.return_value = None

        # Act
        close_all_connections()

        # Assert
        mock_pool.closeall.assert_called_once()

    @patch("mcp_server.db.connection._connection_pool", None)
    def test_close_all_connections_when_pool_not_initialized(self):
        """Test that function handles None pool gracefully."""
        # Act - Should not raise exception
        close_all_connections()


class TestConnectionWithProjectContext:
    """Test suite for connection context managers with RLS."""

    @patch("mcp_server.middleware.context.get_project_id", return_value="test-project")
    @patch("mcp_server.db.connection._connection_pool")
    async def test_async_connection_with_rls_success(self, mock_pool, mock_project):
        """Test successful async connection retrieval with RLS context."""
        # Arrange - Create mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"health_check": 1}
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn

        # Import locally to avoid circular imports in test
        from mcp_server.db.connection import get_connection_with_project_context

        # Act
        async with get_connection_with_project_context() as conn:
            # Connection should be retrieved successfully
            assert conn is not None

        # Assert - connection was returned to pool
        mock_pool.putconn.assert_called_once()

    @patch("mcp_server.middleware.context.get_project_id", return_value="test-project")
    @patch("mcp_server.db.connection._connection_pool")
    def test_sync_connection_with_rls_success(self, mock_pool, mock_project):
        """Test successful sync connection retrieval with RLS context."""
        # Arrange - Create mock connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"health_check": 1}
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn

        # Import locally to avoid circular imports in test
        from mcp_server.db.connection import get_connection_with_project_context_sync

        # Act
        with get_connection_with_project_context_sync() as conn:
            # Connection should be retrieved successfully
            assert conn is not None

        # Assert - connection was returned to pool
        mock_pool.putconn.assert_called_once()


class TestConnectionHealthCheck:
    """Test suite for connection health check functionality."""

    @patch("mcp_server.db.connection._connection_pool")
    async def test_health_check_passes_when_connection_healthy(self, mock_pool):
        """Test that healthy connections pass health check."""
        # Arrange - Create mock connection that returns healthy=1
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"health_check": 1}
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn

        from mcp_server.db.connection import get_connection_with_project_context

        # Act - Should not raise exception
        async with get_connection_with_project_context() as conn:
            assert conn is not None

    @patch("mcp_server.db.connection._connection_pool")
    @patch("mcp_server.middleware.context.get_project_id", return_value="test-project")
    async def test_health_check_fails_when_connection_unhealthy(self, mock_project, mock_pool):
        """Test that unhealthy connections fail health check with retry."""
        # Arrange - Connection fails health check consistently
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"health_check": 0}  # Unhealthy
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn

        from mcp_server.db.connection import get_connection_with_project_context

        # Act & Assert - Should raise ConnectionHealthError after retries
        with pytest.raises(Exception):  # ConnectionHealthError
            async with get_connection_with_project_context() as conn:
                pass

    @patch("mcp_server.db.connection._connection_pool", None)
    async def test_connection_raises_when_pool_not_initialized(self):
        """Test error when connection pool is None."""
        from mcp_server.db.connection import get_connection_with_project_context
        from mcp_server.db.connection import PoolError

        # Act & Assert
        with pytest.raises(PoolError, match="Connection pool not initialized"):
            async with get_connection_with_project_context() as conn:
                pass


class TestRLSContextIntegration:
    """Test suite for RLS (Row-Level Security) context integration."""

    @patch("mcp_server.middleware.context.get_project_id", return_value="test-project")
    @patch("mcp_server.db.connection._connection_pool")
    async def test_rls_context_set_on_connection(self, mock_pool, mock_project):
        """Test that RLS context (set_project_context) and pgvector config are executed."""
        # Arrange
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"health_check": 1}

        execute_calls = []
        def track_execute(query, params=None):
            execute_calls.append(query)
            return None

        mock_cursor.execute.side_effect = track_execute
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn

        from mcp_server.db.connection import get_connection_with_project_context

        # Act
        async with get_connection_with_project_context() as conn:
            pass

        # Assert - Should see set_project_context for RLS and SET for pgvector
        queries_str = " ".join(execute_calls).lower()
        assert "set_project_context" in queries_str
        assert "hnsw.iterative_scan" in queries_str
        assert "hnsw.max_scan_tuples" in queries_str

    @patch("mcp_server.middleware.context.get_project_id", return_value=None)
    async def test_raises_error_when_no_project_context(self, mock_project):
        """Test error when project context is not available."""
        from mcp_server.db.connection import get_connection_with_project_context
        from mcp_server.db.connection import RLSContextError

        # Act & Assert
        with pytest.raises(RLSContextError, match="No project context available"):
            async with get_connection_with_project_context() as conn:
                pass
