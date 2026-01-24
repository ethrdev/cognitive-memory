"""
Database Connection Pool Module

Provides connection pooling for PostgreSQL database with health checks
and graceful shutdown capabilities.

Story 11.4.2: Adds RLS context integration with get_connection_with_project_context().
Story 11.6.1: Adds pgvector 0.8.0 iterative scan configuration.
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

from mcp_server.exceptions import RLSContextError


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


async def configure_pgvector_iterative_scans(conn: connection) -> None:
    """
    Configure pgvector 0.8.0+ iterative scans for optimal RLS performance.

    Story 11.6.1: Adds iterative scan configuration to handle RLS filtering
    without significant performance degradation.

    When RLS filters rows AFTER the HNSW scan, pgvector may need to scan
    more tuples to return the requested top_k results. The iterative_scan
    mode allows pgvector to continue scanning until enough results pass
    the RLS filter.

    Configuration:
    - hnsw.iterative_scan = 'relaxed_order': Allow approximate ordering
      for better performance when RLS filters are active
    - hnsw.max_scan_tuples = 20000: Maximum tuples to scan before
      stopping (prevents runaway queries)

    Called once per connection at acquisition in get_connection_with_project_context().

    Args:
        conn: PostgreSQL connection object

    Reference:
        https://github.com/pgvector/pgvector#iterative-scan
    """
    try:
        # Enable iterative scan with relaxed ordering
        await conn.execute("SET hnsw.iterative_scan = 'relaxed_order'")
        # Set maximum tuples to scan (prevents runaway queries)
        await conn.execute("SET hnsw.max_scan_tuples = 20000")
        logging.getLogger(__name__).debug(
            "pgvector iterative scans configured: relaxed_order, max_scan_tuples=20000"
        )
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"Failed to configure pgvector iterative scans (pgvector may not be 0.8.0+): {e}"
        )
        # Non-fatal: continue without iterative scan optimization


def configure_pgvector_iterative_scans_sync(conn: connection) -> None:
    """
    Synchronous version of configure_pgvector_iterative_scans.

    Story 11.6.1: Adds iterative scan configuration to handle RLS filtering
    without significant performance degradation.

    Args:
        conn: PostgreSQL connection object

    Reference:
        https://github.com/pgvector/pgvector#iterative-scan
    """
    try:
        cursor = conn.cursor()
        # Enable iterative scan with relaxed ordering
        cursor.execute("SET hnsw.iterative_scan = 'relaxed_order'")
        # Set maximum tuples to scan (prevents runaway queries)
        cursor.execute("SET hnsw.max_scan_tuples = 20000")
        cursor.close()
        logging.getLogger(__name__).debug(
            "pgvector iterative scans configured: relaxed_order, max_scan_tuples=20000 (sync)"
        )
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"Failed to configure pgvector iterative scans (pgvector may not be 0.8.0+): {e}"
        )
        # Non-fatal: continue without iterative scan optimization


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


@asynccontextmanager
async def get_connection_with_project_context(
    read_only: bool = False,
    max_retries: int = 3,
    retry_delay: float = 0.5,
) -> AsyncIterator[connection]:
    """
    Get a database connection with RLS project context automatically set.

    Story 11.4.2: Project Context Validation and RLS Integration
    Story 11.6.1: Added pgvector iterative scan configuration

    This wrapper extends get_connection() to:
    1. Get project_id from the project_context contextvar (set by TenantMiddleware)
    2. Call set_project_context(project_id) with appropriate transaction scoping
    3. Ensure RLS session variables are active for all queries
    4. Maintain backward compatibility with existing connection pool retry logic

    CRITICAL: Transaction scoping depends on read_only parameter:
    - read_only=True: Uses autocommit mode (valid for single SELECT query)
    - read_only=False: Uses explicit transaction (required for writes, valid for transaction duration)

    Args:
        read_only: If True, use autocommit for SELECT-only operations.
                  If False, use explicit transaction for write operations (default: False).
        max_retries: Maximum number of retry attempts for transient errors (default: 3)
        retry_delay: Initial delay between retries in seconds, doubles each attempt (default: 0.5)

    Returns:
        Database connection object with RLS context active

    Raises:
        PoolError: If pool is not initialized or exhausted after all retries
        ConnectionHealthError: If connection health check fails after all retries
        RLSContextError: If project context cannot be set (no project_id in contextvar)

    Example:
        # For read-only operations (SELECT queries):
        async with get_connection_with_project_context(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM nodes WHERE project_id = %s", (project_id,))
            # RLS context active for single query, then autocommit
        # Context is cleared automatically

        # For write operations (INSERT/UPDATE/DELETE):
        async with get_connection_with_project_context(read_only=False) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO nodes ...")
            # RLS context active for entire transaction
        # Transaction commits/rollbacks, context cleared
    """
    global _connection_pool

    if _connection_pool is None:
        raise PoolError(
            "Connection pool not initialized. Call initialize_pool() first."
        )

    # Get project_id from contextvar (set by TenantMiddleware)
    from mcp_server.middleware.context import get_project_id

    project_id = get_project_id()
    if project_id is None:
        raise RLSContextError(
            "No project context available. "
            "TenantMiddleware should have set project_context before database access."
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

            # Story 11.6.1: Configure pgvector iterative scans BEFORE setting RLS context
            await configure_pgvector_iterative_scans(conn)

            # CRITICAL: Set RLS context with appropriate transaction scoping
            # For read-only: SET LOCAL valid for single query with autocommit
            # For write: SET LOCAL valid for entire transaction
            try:
                if read_only:
                    # Read-only mode: autocommit, SET LOCAL valid for single query
                    conn.autocommit = True
                    cursor = conn.cursor()
                    cursor.execute("SELECT set_project_context(%s)", (project_id,))
                    cursor.close()

                    _logger.debug(
                        f"RLS context set for project_id={project_id} "
                        f"(read-only mode, autocommit, context active for single query)"
                    )

                    # Yield connection with RLS context
                    yield conn

                    # Autocommit happens automatically, no explicit transaction
                else:
                    # Write mode: explicit transaction, SET LOCAL valid for transaction
                    with conn.transaction() as tx:
                        cursor = conn.cursor()
                        # Call set_project_context() which sets all session variables
                        # This is defined in migration 034_rls_helper_functions.sql
                        cursor.execute("SELECT set_project_context(%s)", (project_id,))
                        cursor.close()

                        _logger.debug(
                            f"RLS context set for project_id={project_id} "
                            f"(transaction started, context active)"
                        )

                        # Yield connection with active transaction and RLS context
                        # The transaction remains open until the caller exits the context manager
                        yield conn

                        # Transaction commits/rolls back based on exception handling
                        # tx.__exit__ handles this automatically

            except psycopg2.Error as e:
                _logger.error(f"Failed to set RLS context for project {project_id}: {e}")
                raise RLSContextError(f"Failed to set RLS context: {e}") from e

            _logger.debug("Database connection with RLS context returned to pool")
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
def get_connection_with_project_context_sync(
    read_only: bool = False,
    max_retries: int = 3,
    retry_delay: float = 0.5,
) -> Iterator[connection]:
    """
    Synchronous version of get_connection_with_project_context.

    Story 11.4.2: Project Context Validation and RLS Integration
    Story 11.6.1: Added pgvector iterative scan configuration

    Use this for non-async code paths (middleware validation, batch jobs).
    For MCP tools running in async context, use get_connection_with_project_context() instead.

    Args:
        read_only: If True, use autocommit for SELECT-only operations.
                  If False, use explicit transaction for write operations (default: False).
        max_retries: Maximum number of retry attempts for transient errors (default: 3)
        retry_delay: Initial delay between retries in seconds, doubles each attempt (default: 0.5)

    Returns:
        Database connection object with RLS context active

    Raises:
        PoolError: If pool is not initialized or exhausted after all retries
        ConnectionHealthError: If connection health check fails after all retries
        RLSContextError: If project context cannot be set

    Example:
        # In middleware validation (read-only):
        with get_connection_with_project_context_sync(read_only=True) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM nodes")
    """
    global _connection_pool

    if _connection_pool is None:
        raise PoolError(
            "Connection pool not initialized. Call initialize_pool() first."
        )

    # Get project_id from contextvar (set by TenantMiddleware)
    from mcp_server.middleware.context import get_project_id

    project_id = get_project_id()
    if project_id is None:
        raise RLSContextError(
            "No project context available. "
            "TenantMiddleware should have set project_context before database access."
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

            # Story 11.6.1: Configure pgvector iterative scans BEFORE setting RLS context
            # Note: This is the sync version, so we call the sync function
            configure_pgvector_iterative_scans_sync(conn)

            # CRITICAL: Set RLS context with appropriate transaction scoping
            try:
                if read_only:
                    # Read-only mode: autocommit, SET LOCAL valid for single query
                    conn.autocommit = True
                    cursor = conn.cursor()
                    cursor.execute("SELECT set_project_context(%s)", (project_id,))
                    cursor.close()

                    _logger.debug(
                        f"RLS context set for project_id={project_id} "
                        f"(sync read-only mode, autocommit, context active for single query)"
                    )

                    # Yield connection with RLS context
                    yield conn
                else:
                    # Write mode: explicit transaction, SET LOCAL valid for transaction
                    with conn:
                        cursor = conn.cursor()
                        # Call set_project_context() which sets all session variables
                        cursor.execute("SELECT set_project_context(%s)", (project_id,))
                        cursor.close()

                        _logger.debug(
                            f"RLS context set for project_id={project_id} "
                            f"(transaction started, context active)"
                        )

                        # Yield connection with active transaction and RLS context
                        yield conn

            except psycopg2.Error as e:
                _logger.error(f"Failed to set RLS context for project {project_id}: {e}")
                raise RLSContextError(f"Failed to set RLS context: {e}") from e

            _logger.debug("Database connection with RLS context returned to pool (sync)")
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
