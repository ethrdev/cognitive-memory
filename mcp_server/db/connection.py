"""
Database Connection Pool Module

Provides connection pooling for PostgreSQL database with health checks
and graceful shutdown capabilities.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

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


async def initialize_pool(
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
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            if result["test"] != 1:
                raise ConnectionHealthError("Initial connection health check failed")

        _logger.info("Connection pool health check passed")

    except psycopg2.Error as e:
        _logger.error(f"Failed to initialize connection pool: {e}")
        raise PoolError(f"Connection pool initialization failed: {e}") from e


# Transient error patterns that warrant a retry
_TRANSIENT_ERROR_PATTERNS = [
    "SSL connection has been closed unexpectedly",
    "connection reset by peer",
    "connection timed out",
    "server closed the connection unexpectedly",
    "could not connect to server",
    "the connection is closed",
]


def _is_transient_error(error: Exception) -> bool:
    """Check if an error is transient and should be retried."""
    error_str = str(error).lower()
    return any(pattern.lower() in error_str for pattern in _TRANSIENT_ERROR_PATTERNS)


@asynccontextmanager
async def get_connection(max_retries: int = 3, retry_delay: float = 0.5) -> AsyncIterator[connection]:
    """
    Get a database connection from the pool with retry logic for transient errors.

    Args:
        max_retries: Maximum number of retry attempts for transient errors (default: 3)
        retry_delay: Initial delay between retries in seconds, doubles each attempt (default: 0.5)

    Returns:
        Database connection object

    Raises:
        PoolError: If pool is not initialized or exhausted after all retries
        ConnectionHealthError: If connection health check fails after all retries
    """
    global _connection_pool

    if _connection_pool is None:
        raise PoolError(
            "Connection pool not initialized. Call initialize_pool() first."
        )

    last_error: Exception | None = None
    current_delay = retry_delay
    conn = None

    for attempt in range(max_retries + 1):
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
                _logger.warning(f"Connection health check failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                # Discard bad connection
                try:
                    _connection_pool.putconn(conn, close=True)
                except Exception:
                    pass
                conn = None

                # Check if error is transient and we should retry
                if _is_transient_error(e) and attempt < max_retries:
                    _logger.info(f"Transient error detected, retrying in {current_delay:.1f}s...")
                    await asyncio.sleep(current_delay)
                    current_delay *= 2  # Exponential backoff
                    last_error = e
                    continue

                raise ConnectionHealthError(f"Connection health check failed: {e}") from e

            _logger.debug("Database connection acquired from pool")
            yield conn
            return  # Success - exit the retry loop

        except psycopg2.Error as e:
            # Check if the error during operation is transient
            if _is_transient_error(e) and attempt < max_retries:
                _logger.warning(f"Transient database error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                _logger.info(f"Retrying in {current_delay:.1f}s...")
                time.sleep(current_delay)
                current_delay *= 2
                last_error = e
                continue
            raise
        except pool.PoolError as e:
            if attempt < max_retries:
                _logger.warning(f"Pool error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                time.sleep(current_delay)
                current_delay *= 2
                last_error = e
                continue
            _logger.error("Connection pool exhausted after all retries")
            raise PoolError("Connection pool exhausted - no available connections") from e
        finally:
            # Always return connection to pool if it was successfully acquired
            if conn is not None:
                try:
                    _connection_pool.putconn(conn)
                    _logger.debug("Database connection returned to pool")
                except Exception as e:
                    _logger.error(f"Error returning connection to pool: {e}")
                conn = None

    # All retries exhausted
    if last_error:
        _logger.error(f"All {max_retries + 1} connection attempts failed. Last error: {last_error}")
        raise PoolError(f"Connection failed after {max_retries + 1} attempts: {last_error}") from last_error


@contextmanager
def get_connection_sync(max_retries: int = 3, retry_delay: float = 0.5) -> Iterator[connection]:
    """
    Synchronous version of get_connection for batch jobs and scripts.

    Use this for non-async code paths (analysis/, budget/, scripts/).
    For MCP tools running in async context, use get_connection() instead.

    Args:
        max_retries: Maximum number of retry attempts for transient errors (default: 3)
        retry_delay: Initial delay between retries in seconds, doubles each attempt (default: 0.5)

    Returns:
        Database connection object

    Raises:
        PoolError: If pool is not initialized or exhausted after all retries
        ConnectionHealthError: If connection health check fails after all retries
    """
    global _connection_pool

    if _connection_pool is None:
        raise PoolError(
            "Connection pool not initialized. Call initialize_pool() first."
        )

    last_error: Exception | None = None
    current_delay = retry_delay
    conn = None

    for attempt in range(max_retries + 1):
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
                _logger.warning(f"Connection health check failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                # Discard bad connection
                try:
                    _connection_pool.putconn(conn, close=True)
                except Exception:
                    pass
                conn = None

                # Check if error is transient and we should retry
                if _is_transient_error(e) and attempt < max_retries:
                    _logger.info(f"Transient error detected, retrying in {current_delay:.1f}s...")
                    time.sleep(current_delay)  # sync sleep
                    current_delay *= 2  # Exponential backoff
                    last_error = e
                    continue

                raise ConnectionHealthError(f"Connection health check failed: {e}") from e

            _logger.debug("Database connection acquired from pool (sync)")
            yield conn
            return  # Success - exit the retry loop

        except psycopg2.Error as e:
            # Check if the error during operation is transient
            if _is_transient_error(e) and attempt < max_retries:
                _logger.warning(f"Transient database error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                _logger.info(f"Retrying in {current_delay:.1f}s...")
                time.sleep(current_delay)
                current_delay *= 2
                last_error = e
                continue
            raise
        except pool.PoolError as e:
            if attempt < max_retries:
                _logger.warning(f"Pool error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                time.sleep(current_delay)
                current_delay *= 2
                last_error = e
                continue
            _logger.error("Connection pool exhausted after all retries")
            raise PoolError("Connection pool exhausted - no available connections") from e
        finally:
            # Always return connection to pool if it was successfully acquired
            if conn is not None:
                try:
                    _connection_pool.putconn(conn)
                    _logger.debug("Database connection returned to pool (sync)")
                except Exception as e:
                    _logger.error(f"Error returning connection to pool: {e}")
                conn = None

    # All retries exhausted
    if last_error:
        _logger.error(f"All {max_retries + 1} connection attempts failed. Last error: {last_error}")
        raise PoolError(f"Connection failed after {max_retries + 1} attempts: {last_error}") from last_error


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


async def _test_database_connection_async() -> bool:
    """
    Async version of database connection test.
    """
    try:
        async with get_connection() as conn:
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


def test_database_connection() -> bool:
    """
    Test database connection with a simple query.

    Note: This is a sync wrapper. Use _test_database_connection_async() for async code.

    Returns:
        True if connection is successful, False otherwise
    """
    import asyncio
    try:
        return asyncio.run(_test_database_connection_async())
    except Exception as e:
        _logger.error(f"Database test failed: {e}")
        return False


# Note: Connection pool initialization is now async.
# Use initialize_pool_sync() for sync code or await initialize_pool() for async code.


def initialize_pool_sync(
    min_connections: int = 1,
    max_connections: int = 10,
    connection_timeout: int = 5,
) -> None:
    """
    Sync wrapper for initialize_pool().

    For async code, use: await initialize_pool()

    Args:
        min_connections: Minimum number of connections to maintain
        max_connections: Maximum number of connections allowed
        connection_timeout: Timeout in seconds for connection attempts

    Raises:
        PoolError: If pool initialization fails
    """
    import asyncio
    try:
        asyncio.run(
            initialize_pool(
                min_connections=min_connections,
                max_connections=max_connections,
                connection_timeout=connection_timeout,
            )
        )
    except Exception as e:
        _logger.error(f"Failed to initialize connection pool: {e}")
        raise
