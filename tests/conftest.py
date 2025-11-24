"""
Pytest configuration and fixtures for Cognitive Memory System tests.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg2
import pytest
from dotenv import load_dotenv

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
from psycopg2.extensions import connection


# Load environment at module level
load_dotenv(".env.development")


@pytest.fixture(scope="session")
def database_url() -> str:
    """Get database URL from environment."""
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set - skipping database tests")
    return url


@pytest.fixture(scope="function")
def conn(database_url: str) -> connection:
    """
    Create a PostgreSQL connection for testing.

    Uses DATABASE_URL from environment. Each test gets a fresh connection
    that is rolled back after the test to avoid side effects.
    """
    try:
        connection = psycopg2.connect(database_url)
        connection.autocommit = False
        yield connection
        connection.rollback()
        connection.close()
    except psycopg2.Error as e:
        pytest.skip(f"Could not connect to database: {e}")


@pytest.fixture
def mock_conn():
    """Mock database connection for unit tests that don't need real DB."""
    mock = MagicMock(spec=connection)
    mock.cursor.return_value = MagicMock()
    mock.cursor.return_value.fetchone.return_value = (1,)
    mock.cursor.return_value.fetchall.return_value = []
    return mock


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embedding tests."""
    mock = MagicMock()
    mock.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 1536)]
    )
    return mock


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for Haiku tests."""
    mock = MagicMock()
    mock.messages.create = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(text='{"score": 0.8, "reasoning": "Test"}')]
        )
    )
    return mock


@pytest.fixture
def sample_embedding():
    """Generate a sample 1536-dimensional embedding vector."""
    return [0.01 * i for i in range(1536)]


@pytest.fixture
def sample_document():
    """Sample document for testing."""
    return {
        "id": 1,
        "content": "This is a test document for cognitive memory system.",
        "metadata": {"source": "test", "timestamp": "2024-01-01T00:00:00Z"},
    }


@pytest.fixture
def sample_query():
    """Sample query for search tests."""
    return "test document cognitive memory"


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    with patch("mcp_server.db.connection.get_connection") as mock:
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            return_value=MagicMock()
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock.return_value.__exit__ = MagicMock(return_value=False)
        yield mock


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment state between tests."""
    yield
    # Cleanup after test if needed
