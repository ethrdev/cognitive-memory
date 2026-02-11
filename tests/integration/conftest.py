"""
Pytest configuration and fixtures for integration tests.

Story 9.2.2: list_insights Integration Tests
"""

import pytest
import os
from mcp_server.db.connection import initialize_pool, get_connection, get_connection_with_project_context
from mcp_server.middleware.context import project_context


@pytest.fixture(scope="session")
def db_url():
    """
    Get database URL for integration tests.

    Uses TEST_DATABASE_URL if set, otherwise falls back to DATABASE_URL.
    """
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("No DATABASE_URL or TEST_DATABASE_URL set - skipping integration tests")
    return url


@pytest.fixture
async def conn(db_url, monkeypatch):
    """
    Get a database connection for a single test.

    Each test gets a fresh connection, pool is initialized per test.
    Clean up test data BEFORE each test to ensure isolation.
    """
    # Set DATABASE_URL environment variable for this test
    monkeypatch.setenv("DATABASE_URL", db_url)

    # Initialize pool for this test
    await initialize_pool()

    # First, clean up ALL test data (including development leftovers)
    # Use simple connection without RLS to ensure all data is removed
    async with get_connection() as cleanup_conn:
        cur = cleanup_conn.cursor()
        # Delete test-project data
        cur.execute("DELETE FROM l2_insights WHERE project_id = 'test-project'")
        # Also delete any other test-looking project_ids
        cur.execute("DELETE FROM l2_insights WHERE project_id IN ('io', 'mo', 'ea')")
        cleanup_conn.commit()
        cur.close()

    # Set project context for this test (required by get_connection_with_project_context)
    token = project_context.set('test-project')

    # Get a fresh connection for the test (with RLS context)
    async with get_connection_with_project_context() as connection:
        yield connection

    # Clean up context (no close_all_connections to avoid teardown errors)
    project_context.reset(token)
