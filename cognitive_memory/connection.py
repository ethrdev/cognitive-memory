"""
Connection management for cognitive_memory library.

Wraps mcp_server.db.connection functions with library-friendly interface.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from cognitive_memory.exceptions import ConnectionError

if TYPE_CHECKING:
    from psycopg2.extensions import connection

_logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages database connections for cognitive memory operations.

    Wraps the mcp_server connection pool with a library-friendly interface.
    Can be used standalone or integrated with MemoryStore.

    Example:
        manager = ConnectionManager()
        manager.initialize()

        with manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")

        manager.close()

    Attributes:
        connection_string: PostgreSQL connection string (from DATABASE_URL if not provided)
        is_initialized: Whether the connection pool is initialized
    """

    def __init__(self, connection_string: str | None = None) -> None:
        """
        Initialize ConnectionManager.

        Args:
            connection_string: PostgreSQL connection string.
                             If None, reads from DATABASE_URL env var.
        """
        self._connection_string = connection_string or os.getenv("DATABASE_URL")
        self._is_initialized = False
        self._owns_pool = False  # Track if we created the pool

    @property
    def is_initialized(self) -> bool:
        """Check if connection pool is initialized."""
        return self._is_initialized

    def initialize(
        self,
        min_connections: int = 1,
        max_connections: int = 10,
        connection_timeout: int = 5,
    ) -> None:
        """
        Initialize the connection pool.

        Args:
            min_connections: Minimum pool connections
            max_connections: Maximum pool connections
            connection_timeout: Connection timeout in seconds

        Raises:
            ConnectionError: If initialization fails
        """
        if self._is_initialized:
            _logger.debug("Connection pool already initialized")
            return

        try:
            # Import here to avoid import cycle
            from mcp_server.db.connection import get_pool_status, initialize_pool

            # Check if pool is already initialized by another component
            status = get_pool_status()
            if status.get("initialized", False):
                _logger.debug("Using existing connection pool")
                self._is_initialized = True
                self._owns_pool = False
                return

            # Initialize new pool
            if self._connection_string:
                # Set DATABASE_URL if provided
                original_url = os.environ.get("DATABASE_URL")
                os.environ["DATABASE_URL"] = self._connection_string

            try:
                initialize_pool(
                    min_connections=min_connections,
                    max_connections=max_connections,
                    connection_timeout=connection_timeout,
                )
                self._is_initialized = True
                self._owns_pool = True
                _logger.info("Connection pool initialized")
            finally:
                # Restore original DATABASE_URL if we modified it
                if self._connection_string and original_url is not None:
                    os.environ["DATABASE_URL"] = original_url

        except Exception as e:
            raise ConnectionError(f"Failed to initialize connection pool: {e}") from e

    @contextmanager
    def get_connection(self) -> Iterator[connection]:
        """
        Get a database connection from the pool.

        Returns:
            Context manager yielding database connection

        Raises:
            ConnectionError: If pool not initialized or connection fails

        Example:
            with manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
        """
        if not self._is_initialized:
            raise ConnectionError(
                "Connection pool not initialized. Call initialize() first."
            )

        try:
            from mcp_server.db.connection import get_connection

            with get_connection() as conn:
                yield conn
        except Exception as e:
            raise ConnectionError(f"Failed to get connection: {e}") from e

    def close(self, timeout: int = 10) -> None:
        """
        Close all connections in the pool.

        Only closes the pool if this manager created it.

        Args:
            timeout: Maximum time to wait for connections to close
        """
        if not self._is_initialized:
            return

        if not self._owns_pool:
            _logger.debug("Not closing pool - owned by another component")
            self._is_initialized = False
            return

        try:
            from mcp_server.db.connection import close_all_connections

            close_all_connections(timeout=timeout)
            self._is_initialized = False
            self._owns_pool = False
            _logger.info("Connection pool closed")
        except Exception as e:
            _logger.error(f"Error closing connection pool: {e}")

    def get_pool_status(self) -> dict[str, Any]:
        """
        Get current connection pool status.

        Returns:
            Dictionary with pool status information
        """
        if not self._is_initialized:
            return {
                "initialized": False,
                "min_connections": 0,
                "max_connections": 0,
                "current_connections": 0,
            }

        try:
            from mcp_server.db.connection import get_pool_status

            return get_pool_status()
        except Exception:
            return {"initialized": False, "error": "Failed to get pool status"}

    def __enter__(self) -> ConnectionManager:
        """Enter context manager - initialize pool."""
        self.initialize()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager - close pool if we own it."""
        self.close()


# Re-export mcp_server connection functions for advanced users
def get_mcp_connection_pool_status() -> dict[str, Any]:
    """
    Get status of the underlying MCP server connection pool.

    Returns:
        Dictionary with pool status information
    """
    try:
        from mcp_server.db.connection import get_pool_status

        return get_pool_status()
    except ImportError:
        return {"error": "mcp_server not available"}
