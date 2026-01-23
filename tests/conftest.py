"""
Pytest configuration and fixtures for Cognitive Memory System tests.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import psycopg2
from psycopg2.extras import DictCursor
import pytest
from dotenv import load_dotenv

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)
from psycopg2.extensions import connection


# Load environment at module level
load_dotenv(".env.development")


def pytest_configure(config):
    """
    Register custom pytest markers.

    This prevents PytestUnknownMarkWarning when using custom markers.
    """
    # Standard markers
    config.addinivalue_line("markers", "asyncio: marks tests as async")
    config.addinivalue_line("markers", "integration: marks tests as integration tests requiring real database")

    # Priority markers - direct markers for selective execution
    # Usage: @pytest.mark.P0, @pytest.mark.P1, etc.
    # Run: pytest -m P0 (runs only P0 tests)
    config.addinivalue_line("markers", "P0: Critical path - must pass for merge")
    config.addinivalue_line("markers", "P1: High priority - feature validation")
    config.addinivalue_line("markers", "P2: Medium priority - edge cases")
    config.addinivalue_line("markers", "P3: Low priority - nice to have")

    # Test ID marker - for requirements traceability
    # Usage: @pytest.mark.id("26.3-UNIT-001")
    config.addinivalue_line("markers", "id: Test ID for requirements traceability")


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

    IMPORTANT: Uses DictCursor to match production behavior where
    cursor results are accessed as dictionaries (e.g., result["id"]).
    """
    try:
        connection = psycopg2.connect(database_url, cursor_factory=DictCursor)
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
    from mcp_server.middleware.context import clear_context
    clear_context()
    yield
    # Cleanup after test if needed
    from mcp_server.middleware.context import clear_context
    clear_context()


@pytest.fixture(autouse=True)
def with_project_context():
    """
    Fixture to set project context for tool handler tests (auto-applied to all tests).

    Story 11.4.3: Tool Handler Refactoring
    This fixture sets up the project context that tool handlers expect
    when called via middleware. Unit tests that directly call handlers
    should use this fixture to simulate middleware context setup.

    This is autouse=True so it automatically applies to all tests without
    needing to be explicitly requested as a parameter.
    """
    from mcp_server.middleware.context import set_project_id, clear_context

    set_project_id("test-project")
    yield
    clear_context()


# ============================================================================
# RLS Policy Testing Fixtures (Story 11.3.0: pgTAP + Test Infrastructure)
# ============================================================================

class ProjectContext:
    """
    Context manager for switching project context mid-test.

    Usage:
        async with project_context(conn, "test_isolated"):
            # Queries here run with app.current_project = 'test_isolated'
            result = conn.fetch("SELECT * FROM nodes")

    This is transaction-scoped via SET LOCAL, so it clears automatically
    when the transaction ends.
    """

    def __init__(self, conn, project_id: str):
        """
        Initialize the project context manager.

        Args:
            conn: Database connection (psycopg2 connection)
            project_id: Project ID to set as current context
        """
        self.conn = conn
        self.project_id = project_id
        self._previous_context = None

    def __enter__(self):
        """Set the project context using parameterized query."""
        cur = self.conn.cursor()
        # Save previous context for restoration
        # Use current_setting with missing_ok=true to avoid error if not set
        cur.execute("SELECT current_setting('app.current_project', true)")
        result = cur.fetchone()
        self._previous_context = result[0] if result and result[0] else None

        # Set new context using parameterized query (SQL injection safe)
        cur.execute(
            "SET LOCAL app.current_project = %s",
            (self.project_id,)
        )
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore previous context (or leave SET LOCAL to clear at transaction end)."""
        if self._previous_context:
            cur = self.conn.cursor()
            cur.execute(
                "SET LOCAL app.current_project = %s",
                (self._previous_context,)
            )
        # Context will be fully cleared when transaction ends


@pytest.fixture
def project_context():
    """
    Factory for creating project context managers.

    AC6: Pytest Fixtures - project_context (Context Manager)

    Usage:
        def test_my_feature(conn, project_context):
            with project_context(conn, "test_isolated") as conn:
                # Queries here use test_isolated context
                result = conn.fetch("SELECT * FROM nodes")

            with project_context(conn, "test_super") as conn:
                # Queries here use test_super context
                result = conn.fetch("SELECT * FROM nodes")
    """
    return ProjectContext


@pytest.fixture(scope="function")
def isolated_conn(conn, request):
    """
    Create a connection with project-isolated RLS context.

    AC5: Pytest Fixtures - isolated_conn

    This fixture uses SET LOCAL app.current_project within a transaction
    to simulate RLS-isolated access. The transaction is rolled back after
    the test, ensuring no data pollution.

    The project_id can be specified via pytest mark:
        @pytest.mark.parametrize("project_id", ["test_super", "test_isolated"])
        def test_with_isolated_conn(conn, isolated_conn, project_id):
            ...

    Or via direct use in test (though this is less common):
        # In a parameterized test, use the project_id from the fixture
    """
    # Get project_id from pytest mark if available
    project_id = getattr(request, "param", "test_isolated")

    cur = conn.cursor()
    try:
        # Set project context using parameterized query
        cur.execute(
            "SET LOCAL app.current_project = %s",
            (project_id,)
        )
        yield conn
    finally:
        # Transaction rollback happens in the conn fixture
        # SET LOCAL is automatically cleared at transaction end
        pass


@pytest.fixture(scope="function")
def bypass_conn():
    """
    Create a connection that bypasses RLS (for test setup/verification).

    AC7: Pytest Fixtures - bypass_conn

    This fixture creates a separate connection using test_bypass_role
    which has BYPASSRLS attribute. This allows:
        - Setting up test data across multiple projects
        - Verifying data state regardless of RLS policies
        - Cleaning up test data

    ONLY available when TESTING=true environment variable is set.

    Requires:
        - TEST_BYPASS_DSN environment variable set

    Usage:
        def test_setup_with_bypass(bypass_conn):
            cur = bypass_conn.cursor()
            # Can see ALL data regardless of RLS
            cur.execute("SELECT * FROM nodes")
            all_nodes = cur.fetchall()
    """
    # Guard: Only available in test environment
    if not os.getenv("TESTING"):
        pytest.skip("bypass_conn only available when TESTING=true")

    bypass_dsn = os.getenv("TEST_BYPASS_DSN")
    if not bypass_dsn:
        pytest.skip("TEST_BYPASS_DSN not set - bypass_conn unavailable")

    try:
        # Create separate connection for bypass access
        connection = psycopg2.connect(bypass_dsn, cursor_factory=DictCursor)
        connection.autocommit = False
        yield connection
        connection.rollback()
        connection.close()
    except psycopg2.Error as e:
        pytest.skip(f"Could not create bypass connection: {e}")
