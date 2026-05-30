"""
Pytest configuration and fixtures for Cognitive Memory System tests.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import asyncio
from datetime import datetime
from typing import Any, Optional

import psycopg2
# from psycopg2.extras import register_vector  # TODO: pgvector extension nicht verfügbar
try:
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor as DictCursor
except (ImportError, AttributeError):
    try:
        from psycopg2.extras import DictCursor
    except ImportError:
        DictCursor = None  # Fallback für psycopg2 ohne DictCursor

from dotenv import load_dotenv

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)

# Load environment at module level
load_dotenv(".env.development")

# ============================================================================
# FIXTURE: UTILITY FUNCTIONS
# ============================================================================

def pytest_configure(config):
    """
    Register custom pytest markers.

    This prevents PytestUnknownMarkWarning when using custom markers.
    """
    # Standard markers
    config.addinivalue_line("markers", "asyncio: marks tests as async")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")

    # Priority markers - direct markers for selective execution
    # Usage: @pytest.mark.P0, @pytest.mark.P1, etc.
    # Run: pytest -m P0 (runs only P0 tests)
    config.addinivalue_line("markers", "P0: Critical path - must pass for merge")
    config.addinivalue_line("markers", "P1: High priority - feature validation")
    config.addinivalue_line("markers", "P2: Medium priority - edge cases")
    config.addinivalue_line("markers", "P3: Low priority - nice to have")

    # Test ID marker - for requirements traceability
    # Usage: @pytest.mark.id("26.3.UNIT-001")
    config.addinivalue_line("markers", "id: Test ID for requirements traceability")


@pytest.fixture(scope="session")
def database_url() -> str:
    """Get database URL from environment."""
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set - skipping database tests")
    return url


@pytest.fixture(scope="function")
def conn(database_url: str) -> psycopg2.extensions.connection:
    """
    Create a PostgreSQL connection for testing.

    Uses DATABASE_URL from environment. Each test gets a fresh connection
    that is rolled back after the test to avoid side effects.

    IMPORTANT: Uses DictCursor to match production behavior where
    cursor results are accessed as dictionaries (e.g., result["id"]).

    Args:
        database_url: Connection string from database_url fixture.

    Returns:
        Connection object with autocommit disabled.
    """
    try:
        cursor_factory = DictCursor if DictCursor is not None else None
        connection = psycopg2.connect(database_url, cursor_factory=cursor_factory)
        connection.autocommit = False
        yield connection
        connection.rollback()
        connection.close()
    except psycopg2.Error as e:
        pytest.skip(f"Could not connect to database: {e}")


@pytest.fixture
def mock_conn():
    """Mock database connection for unit tests that don't need real DB."""
    mock = MagicMock(spec=psycopg2.extensions.connection)
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
    return mock


@pytest.fixture(autouse=True)
def reset_environment():
    """Reset environment state between tests."""
    from mcp_server.middleware.context import clear_context
    clear_context()
    yield
    # Cleanup after test if needed
    from mcp_server.middleware.context import clear_context
    clear_context()


@pytest.fixture(autouse=True, scope="session")
def init_connection_pool():
    """
    Initialize connection pool for all tests (session-scoped).

    This fixture runs once per test session to initialize the asyncpg
    connection pool that handlers expect. Must run before any tests
    that call MCP handlers.

    IMPORTANT: This is a legacy fixture. New code should use
    the connection pool from mcp_server.db.connection which is initialized
    automatically at module import time.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        try:
            from mcp_server.db.connection import initialize_pool_sync
            initialize_pool_sync(min_connections=1, max_connections=5)
        except Exception as e:
            # Log but don't fail - some tests may not need the pool
            import warnings
            warnings.warn(f"Failed to initialize connection pool: {e}")
    yield
    # Cleanup pool after all tests complete
    try:
        from mcp_server.db.connection import close_pool
        try:
            asyncio.run(close_pool())
        except:
            pass
    except:
        pass


@pytest.fixture(autouse=True, scope="function")
async def with_project_context():
    """
    Fixture to set project context for tool handler tests (auto-applied to all tests).

    This fixture simulates the middleware context that tool handlers expect
    when called via middleware.

    IMPORTANT: This fixture MUST be applied to all tool handler tests.
    Unit tests that directly call handlers (bypassing middleware)
    should use mock_db_with_project fixture which provides
    the mock database connection WITHOUT project context.

    Story 11.4.3: Tool Handler Refactoring
    NOTE: Changed to function-scope for contextvars to work with async tests
    """
    from mcp_server.middleware.context import set_project_id, clear_context

    # Set project context for this test (must be async for contextvars to work)
    set_project_id("test-project")
    yield
    clear_context()


@pytest.fixture(autouse=True, scope="session")
def event_loop():
    """
    Create an event loop for async tests (session-scoped).

    This fixture ensures that async tests share an event loop across
    the entire test session, which is more efficient than creating
    a new loop for each test.

    Required for pytest-asyncio with async fixtures.
    """
    import asyncio
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def async_conn(database_url: str):
    """
    Create an asyncpg connection for testing.

    This is the async equivalent of the sync `conn` fixture.
    Use this fixture when migrating tests from psycopg2 to asyncpg.
    """
    import asyncpg

    try:
        connection = await asyncpg.connect(database_url)
        # Start transaction for rollback
        async with connection.transaction():
            yield connection
            # Transaction will be rolled back automatically
    except Exception as e:
        pytest.skip(f"Could not create async connection: {e}")
    finally:
        await connection.close()


@pytest.fixture(scope="function")
def mock_async_conn():
    """
    Mock asyncpg connection for unit tests that don't need real DB.

    This is the async equivalent of the sync `mock_conn` fixture.
    Use for unit tests where you want to mock async DB calls.
    """
    from unittest.mock import AsyncMock, MagicMock

    mock = AsyncMock(spec=asyncpg.connection)
    mock.fetchrow.return_value = {"id": 1, "name": "test"}
    mock.fetch.return_value = []
    mock.execute.return_value = None
    mock.executemany.return_value = None

    mock.transaction = _transaction()
    mock.transaction.return_value.__aenter__.return_value = mock
    mock.transaction.return_value.__aenter__.return_value = mock
    mock.transaction.return_value.__exit__.return_value = None
    mock.transaction.return_value.__exit__.return_value = None

    return mock


@pytest.fixture
def mock_async_conn_with_data():
    """
    Mock asyncpg connection with pre-configured test data.

    Use this fixture when you need specific mock data returned from DB calls.
    Configure the mock return values in your test as needed.

    Example:
        async def test_with_mock_data(mock_async_conn_with_data):
            mock_async_conn_with_data.fetchrow.return_value = {"id": 123, "status": "active"}
            result = await mock_async_conn_with_data.fetchrow("SELECT * FROM nodes WHERE id = $1", 1)
            assert result["id"] == 123
            assert result["status"] == "active"
    """
    from unittest.mock import AsyncMock, MagicMock

    mock = AsyncMock(spec=asyncpg.connection)
    mock.cursor.return_value.fetchone.return_value = None
    mock.cursor.return_value.fetchall.return_value = []

    # Configure fetchrow to return your test data
    mock.fetchrow.return_value = AsyncMock(return_value=None)

    return mock


class _transaction:
    """Mock asyncpg transaction for use in mock_async_conn_with_data."""
    def __enter__(self):
        return mock
    def __exit__(self, *args):
        return False


@pytest.fixture(scope="session")
async def async_pool(database_url: str):
    """
    Create an asyncpg connection pool for testing.

    Use this fixture when testing connection pool behavior or
    when you need multiple connections in a test.

    IMPORTANT: This fixture is obsolete. Tests should use the connection pool
    from mcp_server.db.connection which is initialized automatically at
    module import time.
    """
    import asyncpg

    pool = None
    try:
        pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=5,
            command_timeout=60
        )
        yield pool
    except Exception as e:
        pytest.skip(f"Could not create async pool: {e}")
    finally:
        if pool:
            await pool.close()


@pytest.fixture
def get_connection_mock():
    """
    Mock the get_connection() async context manager.

    Use this fixture when you want to mock the entire get_connection()
    call without actually connecting to a database.

    Usage:
        def test_handler_with_mock(get_connection_mock):
            get_connection_mock.return_value.__aenter__.return_value = mock_conn
            result = handle_store_episode({"query": "test"})
            assert result["query"] == "test"
    """
    from unittest.mock import patch

    with patch("mcp_server.db.connection.get_connection") as mock:
        yield mock


@pytest.fixture
def isolate_conn(conn, request):
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
    """
    import asyncpg

    # Check for test parameters
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
        pass


@pytest.fixture
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
    """
    import asyncpg

    # Guard: Only available in test environment
    if not os.getenv("TESTING"):
        pytest.skip("bypass_conn only available when TESTING=true")
        return

    bypass_dsn = os.getenv("TEST_BYPASS_DSN")
    if not bypass_dsn:
        pytest.skip("TEST_BYPASS_DSN not set - bypass_conn unavailable")
        return

    try:
        # Create separate connection for bypass access
        # Note: asyncpg doesn't support cursor_factory, using record_factory instead if needed
        cursor_factory = DictCursor if DictCursor is not None else None
        connection = asyncpg.connect(bypass_dsn)
        connection.autocommit = False
        yield connection
        connection.rollback()
        connection.close()
    except asyncpg.Error as e:
        pytest.skip(f"Could not create bypass connection: {e}")


@pytest.fixture
def get_connection_mock():
    """
    Mock get_connection() async context manager.

    Use this fixture when you want to mock the entire get_connection()
    call without actually connecting to a database.

    IMPORTANT: This fixture is deprecated. Use connection pool from
    mcp_server.db.connection which is initialized automatically at
    module import time.
    """
    from unittest.mock import patch

    mock = AsyncMock(spec=dict)

    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)

    yield mock


# ============================================================================
# MCP Handler Testing Fixtures (Story: Test Infrastructure Repair)
# ============================================================================

@pytest.fixture
def mock_add_response_metadata():
    """
    Mock add_response_metadata für SMF-Handler-Tests.

    Gibt ein Mock zurück, das add_response_metadata() simuliert und
    korrekte Rückgabewerte mit status-Key liefert.

    FINAL2026-02-14: Für SMF-Test-Korrektur
    """
    from unittest.mock import MagicMock

    def _add_metadata(response: dict[str, Any], project_id: str = "test-project") -> dict[str, Any]:
        """Simuliert add_response_metadata mit korrekter Rückgabe."""
        return {**response, "_project_id": project_id}

    mock = MagicMock(side_effect=_add_metadata)
    return mock


def patch_smf_handlers():
    """
    Patch alle SMF-internen Funktionen mit korrekten Mock-Rückgaben.

    FINAL-2026-02-14: Universelle Helper für SMF-Handler-Patching

    Hinweis: Dies ist KEINE pytest.fixture sondern eine Helper-Funktion,
    die als Context-Manager genutzt wird:
        with patch_smf_handlers() as mocks:
            # mocks['add_response_metadata'] -> Mock für add_response_metadata
            # mocks['get_proposal'] -> Mock für get_proposal
            # mocks['approve_proposal'] -> Mock für approve_proposal
            # mocks['reject_proposal'] -> Mock für reject_proposal
            # mocks['undo_proposal'] -> Mock für undo_proposal
            # mocks['get_pending_proposals'] -> Mock für get_pending_proposals
            # etc.

    WICHTIGKEIT: Diese Helper-Funktion patcht Module-Funktionen, nicht Klassen!
    """
    from unittest.mock import patch, MagicMock

    class SMFMocks:
        """Container für alle SMF-Mocks."""
        def __init__(self):
            # Mock für add_response_metadata - gibt korrekte Rückgaben zurück
            self.add_response_metadata = MagicMock(side_effect=self._add_metadata)

            # Mock für get_proposal - gibt Test-Daten zurück
            self.get_proposal = MagicMock()

            # Mock für approve_proposal - gibt Approval-Ergebnis zurück
            self.approve_proposal = MagicMock(return_value={
                "approved_by_io": False,
                "approved_by_ethr": True,
                "fully_approved": True,
                "status": "APPROVED"
            })

            # Mock für reject_proposal - gibt Reject-Ergebnis zurück
            self.reject_proposal = MagicMock(return_value={
                "resolved_at": "2026-02-14T12:00:00Z"
            })

            # Mock für undo_proposal - gibt Undo-Ergebnis zurück
            self.undo_proposal = MagicMock(return_value={
                "undone_at": "2026-02-14T12:00:00Z",
                "status": "PENDING"
            })

            # Mock für get_pending_proposals - gibt Liste zurück
            self.get_pending_proposals = MagicMock(return_value=[])

            # Mock für get_current_project - gibt Test-Project-ID zurück
            # WICHTIG: MUSS vor anderen Patches aktiviert werden!
            self.get_current_project = MagicMock(return_value="test-project")

        def _add_metadata(self, response: dict[str, Any], project_id: str = "test-project") -> dict[str, Any]:
            """Interne Methode für add_response_metadata Mock."""
            return {**response, "_project_id": project_id}

        def __getitem__(self, key: str) -> MagicMock:
            """Erlaubt Dictionary-Style Zugriff: mocks['get_proposal']."""
            return getattr(self, key)

        def __enter__(self):
            """Context-Manager Entry - aktiviert alle Patches."""
            self.patches = []

            # Mapping von Funktionsname zu korrektem Modulpfad
            module_map = {
                'add_response_metadata': 'mcp_server.utils.response',
                'get_proposal': 'mcp_server.analysis.smf',
                'approve_proposal': 'mcp_server.analysis.smf',
                'reject_proposal': 'mcp_server.analysis.smf',
                'undo_proposal': 'mcp_server.analysis.smf',
                'get_pending_proposals': 'mcp_server.analysis.smf',
                'get_current_project': 'mcp_server.middleware.context',
            }

            # Patch alle relevanten Module-Funktionen mit korrekten Modulpfaden
            for func_name, module_path in module_map.items():
                patcher = patch(f'{module_path}.{func_name}', getattr(self, func_name))
                self.patches.append(patcher)
                patcher.start()

            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            """Context-Manager Exit - entfernt alle Patches."""
            for p in self.patches:
                if hasattr(p, 'stop'):
                    p.stop()
            return False

    return SMFMocks()
