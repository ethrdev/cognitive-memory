"""
Database Connection Pool Module

Provides connection pooling for PostgreSQL database with health checks
and graceful shutdown capabilities.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extensions import connection
from psycopg2.extras import DictCursor


# Custom exceptions
class PoolError(Exception):
    """Raised when connection pool is exhausted or unavailable."""

    pass


class ConnectionHealthError(Exception):
    """Raised when connection health check fails."""

    pass


# Global connection pool
_connection_pool: pool.SimpleConnectionPool | None = None
_logger = logging.getLogger(__name__)


def initialize_pool(
    min_connections: int = 1,
    max_connections: int = 10,
    connection_timeout: int = 5,
) -> None:
    """
    Initialize the PostgreSQL connection pool.

    Args:
        min_connections: Minimum number of connections to maintain
        max_connections: Maximum number of connections allowed
        connection_timeout: Timeout in seconds for connection attempts

    Raises:
        PoolError: If pool initialization fails
    """
    global _connection_pool

    if _connection_pool is not None:
        _logger.warning("Connection pool already initialized")
        return

    try:
        # Get database configuration from environment
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise PoolError("DATABASE_URL environment variable not set")

        # Initialize connection pool
        _connection_pool = pool.SimpleConnectionPool(
            minconn=min_connections,
            maxconn=max_connections,
            dsn=database_url,
            cursor_factory=DictCursor,
            connect_timeout=connection_timeout,
        )

        _logger.info(
            f"Connection pool initialized: min={min_connections}, max={max_connections}"
        )

        # Test initial connection
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            if result["test"] != 1:
                raise ConnectionHealthError("Initial connection health check failed")

        _logger.info("Connection pool health check passed")

    except psycopg2.Error as e:
        _logger.error(f"Failed to initialize connection pool: {e}")
        raise PoolError(f"Connection pool initialization failed: {e}") from e


@contextmanager
def get_connection() -> Iterator[connection]:
    """
    Get a database connection from the pool.

    Returns:
        Database connection object

    Raises:
        PoolError: If pool is not initialized or exhausted
        ConnectionHealthError: If connection health check fails
    """
    global _connection_pool

    if _connection_pool is None:
        raise PoolError(
            "Connection pool not initialized. Call initialize_pool() first."
        )

    conn = None
    try:
        # Get connection from pool
        conn = _connection_pool.getconn()

        # Health check: verify connection is alive
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as health_check")
            result = cursor.fetchone()
            if result["health_check"] != 1:
                raise ConnectionHealthError("Connection health check failed")
            cursor.close()
        except (psycopg2.Error, Exception) as e:
            _logger.warning(f"Connection health check failed: {e}")
            # Discard bad connection and try to get a new one
            _connection_pool.putconn(conn, close=True)
            raise ConnectionHealthError(f"Connection health check failed: {e}") from e

        _logger.debug("Database connection acquired from pool")
        yield conn

    except pool.PoolError as e:
        _logger.error("Connection pool exhausted")
        raise PoolError("Connection pool exhausted - no available connections") from e
    except psycopg2.Error as e:
        _logger.error(f"Database connection error: {e}")
        raise PoolError(f"Database connection failed: {e}") from e
    finally:
        # Always return connection to pool if it was successfully acquired
        if conn is not None:
            try:
                _connection_pool.putconn(conn)
                _logger.debug("Database connection returned to pool")
            except Exception as e:
                _logger.error(f"Error returning connection to pool: {e}")


def close_all_connections(timeout: int = 10) -> None:
    """
    Close all connections in the pool gracefully.

    Args:
        timeout: Maximum time in seconds to wait for connections to close
    """
    global _connection_pool

    if _connection_pool is None:
        _logger.info("No connection pool to close")
        return

    start_time = time.time()

    try:
        # Close all connections in the pool
        _connection_pool.closeall()
        _logger.info("All database connections closed")

        # Clear global reference
        _connection_pool = None

        elapsed = time.time() - start_time
        if elapsed > timeout:
            _logger.warning(
                f"Connection closing took {elapsed:.2f}s (exceeded timeout of {timeout}s)"
            )
        else:
            _logger.debug(f"Connections closed in {elapsed:.2f}s")

    except Exception as e:
        elapsed = time.time() - start_time
        _logger.error(f"Error closing connections after {elapsed:.2f}s: {e}")


def get_pool_status() -> dict:
    """
    Get current status of the connection pool.

    Returns:
        Dictionary with pool status information
    """
    global _connection_pool

    if _connection_pool is None:
        return {
            "initialized": False,
            "min_connections": 0,
            "max_connections": 0,
            "current_connections": 0,
        }

    return {
        "initialized": True,
        "min_connections": _connection_pool.minconn,
        "max_connections": _connection_pool.maxconn,
        "current_connections": len(_connection_pool._used)
        + len(_connection_pool._pool),
    }


def test_database_connection() -> bool:
    """
    Test database connection with a simple query.

    Returns:
        True if connection is successful, False otherwise
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT version() as version, current_database() as database"
            )
            result = cursor.fetchone()
            _logger.info(
                f"Database test successful: {result['database']} v{result['version'].split()[1]}"
            )
            return True
    except Exception as e:
        _logger.error(f"Database test failed: {e}")
        return False


# Initialize pool when module is imported (if environment is ready)
try:
    if os.getenv("DATABASE_URL"):
        initialize_pool()
    else:
        _logger.warning("DATABASE_URL not set, connection pool not initialized")
except Exception as e:
    _logger.error(f"Failed to auto-initialize connection pool: {e}")
