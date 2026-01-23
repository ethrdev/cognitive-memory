"""
Unit tests for project validation logic.

Story 11.4.2: Project Context Validation and RLS Integration

Tests project validation against project_registry, per-request caching,
and error handling for unknown projects.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mcp_server.exceptions import ProjectNotFoundError
from mcp_server.middleware.context import clear_context, set_project_id
from mcp_server.middleware.tenant import ProjectMetadata, TenantMiddleware


class TestLogging:
    """Test structured logging output."""

    @pytest.mark.asyncio
    async def test_validation_logs_success_message(self, caplog):
        """Test that successful validation logs a debug message."""
        middleware = TenantMiddleware()
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = {
            "project_id": "test-project",
            "access_level": "isolated",
            "name": "Test Project"
        }

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn

            with caplog.at_level("DEBUG"):
                metadata = await middleware._validate_project("test-project")

                # Verify debug log was written
                assert any(
                    "Project validated: test-project" in record.message
                    and "access_level=isolated" in record.message
                    for record in caplog.records
                )

    @pytest.mark.asyncio
    async def test_unknown_project_logs_warning(self, caplog):
        """Test that unknown project validation logs a warning."""
        middleware = TenantMiddleware()
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = None  # Project not found

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn

            with caplog.at_level("WARNING"):
                with pytest.raises(ProjectNotFoundError):
                    await middleware._validate_project("unknown-project")

                # Verify warning log was written
                assert any(
                    "Project not found in registry: unknown-project" in record.message
                    for record in caplog.records
                )

    @pytest.mark.asyncio
    async def test_validation_cache_hit_logs_debug(self, caplog):
        """Test that cache hits are logged as debug messages."""
        middleware = TenantMiddleware()
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        cursor.fetchone.return_value = {
            "project_id": "test-project",
            "access_level": "shared",
            "name": "Test Shared Project"
        }

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn

            # First call
            await middleware._validate_project("test-project")

            # Second call (should hit cache)
            with caplog.at_level("DEBUG"):
                await middleware._validate_project("test-project")

                # Verify cache hit was logged
                assert any(
                    "Project validation cache hit for test-project" in record.message
                    for record in caplog.records
                )


class TestProjectMetadata:
    """Test ProjectMetadata dataclass."""

    def test_project_metadata_creation(self):
        """Test creating ProjectMetadata with all fields."""
        metadata = ProjectMetadata(
            project_id="test-project",
            access_level="isolated",
            name="Test Project"
        )
        assert metadata.project_id == "test-project"
        assert metadata.access_level == "isolated"
        assert metadata.name == "Test Project"


class TestTenantMiddlewareValidation:
    """Test TenantMiddleware project validation logic."""

    @pytest.fixture
    def middleware(self):
        """Create a TenantMiddleware instance for testing."""
        return TenantMiddleware()

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        return conn, cursor

    @pytest.mark.asyncio
    async def test_validate_known_project(self, middleware, mock_connection):
        """Test validation returns ProjectMetadata for known project."""
        conn, cursor = mock_connection

        # Mock database query returning a known project
        cursor.fetchone.return_value = {
            "project_id": "test-project",
            "access_level": "isolated",
            "name": "Test Project"
        }

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn

            metadata = await middleware._validate_project("test-project")

            assert metadata.project_id == "test-project"
            assert metadata.access_level == "isolated"
            assert metadata.name == "Test Project"

            # Verify SQL was executed correctly
            cursor.execute.assert_called_once()
            call_args = cursor.execute.call_args
            assert "SELECT project_id, access_level, name" in call_args[0][0]
            assert "FROM project_registry" in call_args[0][0]
            assert call_args[0][1] == ("test-project",)

    @pytest.mark.asyncio
    async def test_validate_unknown_project_raises_error(self, middleware, mock_connection):
        """Test validation raises ProjectNotFoundError for unknown project."""
        conn, cursor = mock_connection

        # Mock database query returning None (project not found)
        cursor.fetchone.return_value = None

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn

            with pytest.raises(ProjectNotFoundError) as exc_info:
                await middleware._validate_project("unknown-project")

            assert exc_info.value.project_id == "unknown-project"
            assert "Unknown project: unknown-project" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validation_cache_hit(self, middleware, mock_connection):
        """Test that second validation uses cache instead of database query."""
        conn, cursor = mock_connection

        # Mock database query
        cursor.fetchone.return_value = {
            "project_id": "test-project",
            "access_level": "shared",
            "name": "Test Shared Project"
        }

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn

            # First call - should hit database
            metadata1 = await middleware._validate_project("test-project")
            assert cursor.execute.call_count == 1

            # Second call - should use cache
            metadata2 = await middleware._validate_project("test-project")
            assert cursor.execute.call_count == 1  # No additional query

            # Verify same metadata returned
            assert metadata1.project_id == metadata2.project_id
            assert metadata1.access_level == metadata2.access_level

    @pytest.mark.asyncio
    async def test_validation_cache_cleared_per_request(self, middleware, mock_connection):
        """Test that cache is cleared at start of each request."""
        conn, cursor = mock_connection

        cursor.fetchone.return_value = {
            "project_id": "test-project",
            "access_level": "isolated",
            "name": "Test Project"
        }

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn

            # First request
            middleware._validation_cache.clear()  # Simulate on_call_tool cache clear
            await middleware._validate_project("test-project")
            first_call_count = cursor.execute.call_count

            # Simulate new request - cache cleared
            middleware._validation_cache.clear()
            await middleware._validate_project("test-project")

            # Should have made another database call
            assert cursor.execute.call_count == first_call_count + 1

    @pytest.mark.asyncio
    async def test_validate_project_database_error_treated_as_not_found(
        self, middleware, mock_connection
    ):
        """Test that database errors are treated as project not found (security)."""
        conn, cursor = mock_connection

        # Mock database error
        cursor.execute.side_effect = Exception("Database connection lost")

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.return_value = conn

            with pytest.raises(ProjectNotFoundError) as exc_info:
                await middleware._validate_project("test-project")

            # Should raise ProjectNotFoundError, not the original database error
            assert exc_info.value.project_id == "test-project"
            assert isinstance(exc_info.value, ProjectNotFoundError)

    @pytest.mark.asyncio
    async def test_multiple_projects_cached_separately(self, middleware):
        """Test that different projects are cached separately."""
        # Create separate mocks for each project
        conn_a = MagicMock()
        cursor_a = MagicMock()
        conn_a.cursor.return_value = cursor_a
        cursor_a.fetchone.return_value = {
            "project_id": "project-a",
            "access_level": "super",
            "name": "Project A"
        }

        conn_b = MagicMock()
        cursor_b = MagicMock()
        conn_b.cursor.return_value = cursor_b
        cursor_b.fetchone.return_value = {
            "project_id": "project-b",
            "access_level": "isolated",
            "name": "Project B"
        }

        call_count = [0]

        def mock_get_connection():
            call_count[0] += 1
            if call_count[0] == 1:
                return conn_a
            return conn_b

        with patch("mcp_server.db.connection.get_connection_sync") as mock_get_conn:
            mock_get_conn.return_value.__enter__.side_effect = mock_get_connection

            # Validate first project
            metadata_a = await middleware._validate_project("project-a")
            assert metadata_a.access_level == "super"

            # Validate second project
            metadata_b = await middleware._validate_project("project-b")
            assert metadata_b.access_level == "isolated"

            # Both should have made queries
            assert call_count[0] == 2

            # Verify cache hits work (no new connections)
            metadata_a_cached = await middleware._validate_project("project-a")
            metadata_b_cached = await middleware._validate_project("project-b")

            # No additional queries
            assert call_count[0] == 2

            # Verify metadata matches
            assert metadata_a_cached.access_level == "super"
            assert metadata_b_cached.access_level == "isolated"


class TestProjectNotFoundError:
    """Test ProjectNotFoundError exception."""

    def test_exception_message_format(self):
        """Test that exception message follows expected format."""
        exc = ProjectNotFoundError("my-project")
        assert str(exc) == "Unknown project: my-project"
        assert exc.project_id == "my-project"

    def test_exception_is_value_error(self):
        """Test that ProjectNotFoundError inherits from ValueError."""
        exc = ProjectNotFoundError("test-project")
        assert isinstance(exc, ValueError)

    def test_exception_can_be_caught_as_value_error(self):
        """Test that exception can be caught as ValueError."""
        with pytest.raises(ValueError):
            raise ProjectNotFoundError("test")


class TestValidationIntegration:
    """Integration tests for validation with context."""

    @pytest.mark.asyncio
    async def test_validation_sets_context_after_extraction(self):
        """Test that on_call_tool validates and sets project context."""
        middleware = TenantMiddleware()

        # Mock the _extract_project_id to return a project_id
        with patch.object(
            middleware, "_extract_project_id", return_value="test-project"
        ):
            # Mock the _validate_project to return metadata
            metadata = ProjectMetadata(
                project_id="test-project",
                access_level="isolated",
                name="Test Project"
            )
            with patch.object(middleware, "_validate_project", return_value=metadata):
                # Mock call_next to return a result
                async def mock_call_next(context):
                    # Verify context was set
                    from mcp_server.middleware.context import get_project_id
                    assert get_project_id() == "test-project"
                    return {"result": "success"}

                # Create mock middleware context
                mock_context = MagicMock()

                result = await middleware.on_call_tool(mock_context, mock_call_next)
                assert result == {"result": "success"}

                # Clean up context
                clear_context()
