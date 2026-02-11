"""
Pytest configuration and fixtures for unit tests.

Story 9.2.2: list_insights Unit Tests
"""

import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def with_project_context(monkeypatch):
    """
    Mock fixture that provides project context for unit tests.

    This fixture mocks:
    - project_context context variable to return 'test-project'
    - get_connection_with_project_context() to return a mock connection
    """
    # Import the context variable
    from mcp_server.middleware.context import project_context

    # Set the project context directly
    token = project_context.set('test-project')

    @asynccontextmanager
    async def mock_connection():
        """Mock async context manager that returns a mock connection."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Configure cursor methods
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_cursor.close.return_value = None

        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit.return_value = None

        yield mock_conn

    with patch('mcp_server.db.connection.get_connection_with_project_context', mock_connection):
        yield

    # Clean up context
    project_context.reset(token)
