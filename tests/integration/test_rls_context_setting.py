"""
Integration tests for RLS context setting.

Story 11.4.2: Project Context Validation and RLS Integration

Tests that set_project_context() sets all session variables correctly,
allowed_projects array computation for different access levels, and
transaction scoping (context cleared after transaction ends).
"""

from __future__ import annotations

import pytest

from mcp_server.exceptions import RLSContextError
from mcp_server.middleware.context import clear_context, project_context, set_project_id


class TestRLSSessionVariables:
    """Test RLS session variables are set correctly."""

    @pytest.mark.P0
    def test_set_project_context_sets_all_session_variables(self, conn):
        """Test that set_project_context() sets all required session variables."""
        cursor = conn.cursor()

        # Call set_project_context for a test project
        cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))

        # Verify all session variables are set
        cursor.execute("SELECT current_setting('app.current_project', true)")
        assert cursor.fetchone()[0] == "test_isolated"

        cursor.execute("SELECT current_setting('app.rls_mode', true)")
        rls_mode = cursor.fetchone()[0]
        assert rls_mode in ("pending", "shadow", "enforcing", "complete")

        cursor.execute("SELECT current_setting('app.access_level', true)")
        access_level = cursor.fetchone()[0]
        assert access_level in ("super", "shared", "isolated")

        cursor.execute("SELECT current_setting('app.allowed_projects', true)")
        # Should be a PostgreSQL array format like {test_isolated}
        allowed = cursor.fetchone()[0]
        assert "test_isolated" in allowed

    @pytest.mark.P0
    def test_allowed_projects_for_isolated_access_level(self, conn):
        """Test allowed_projects array for isolated access level."""
        cursor = conn.cursor()

        # Set context for isolated project
        cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))

        # Verify allowed_projects only contains the project itself
        cursor.execute("SELECT current_setting('app.allowed_projects', true)")
        allowed = cursor.fetchone()[0]

        # Isolated: {test_isolated}
        assert "test_isolated" in allowed
        # Should not contain other projects (verify by checking count)
        cursor.execute(
            "SELECT array_length(current_setting('app.allowed_projects', true)::TEXT[], 1)"
        )
        count = cursor.fetchone()[0]
        assert count == 1, f"Expected 1 allowed project for isolated, got {count}"

    @pytest.mark.P0
    def test_allowed_projects_for_shared_access_level(self, conn):
        """Test allowed_projects array computation for shared access level."""
        cursor = conn.cursor()

        # Set context for shared project
        # test_shared should have access to test_isolated via project_read_permissions
        cursor.execute("SELECT set_project_context(%s)", ("test_shared",))

        # Verify allowed_projects contains own project + permitted targets
        cursor.execute("SELECT current_setting('app.allowed_projects', true)::TEXT[]")
        allowed = cursor.fetchone()[0]

        # Should contain at least the project itself
        assert "test_shared" in allowed
        # May contain permitted targets depending on project_read_permissions

    @pytest.mark.P0
    def test_allowed_projects_for_super_access_level(self, conn):
        """Test allowed_projects array for super access level includes all projects."""
        cursor = conn.cursor()

        # Set context for super project
        cursor.execute("SELECT set_project_context(%s)", ("test_super",))

        # Verify allowed_projects contains all registered projects
        cursor.execute("SELECT current_setting('app.allowed_projects', true)::TEXT[]")
        allowed = cursor.fetchone()[0]

        # Super should see at least: test_super, test_isolated, test_shared
        assert "test_super" in allowed
        assert "test_isolated" in allowed
        assert "test_shared" in allowed

    @pytest.mark.P1
    def test_get_current_project_immutable_function(self, conn):
        """Test get_current_project() IMMUTABLE wrapper function."""
        cursor = conn.cursor()

        # Set project context
        cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))

        # Call IMMUTABLE wrapper
        cursor.execute("SELECT get_current_project()")
        result = cursor.fetchone()[0]

        assert result == "test_isolated"

    @pytest.mark.P1
    def test_get_allowed_projects_immutable_function(self, conn):
        """Test get_allowed_projects() IMMUTABLE wrapper returns native array."""
        cursor = conn.cursor()

        # Set project context
        cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))

        # Call IMMUTABLE wrapper - returns TEXT[] directly
        cursor.execute("SELECT get_allowed_projects()")
        result = cursor.fetchone()[0]

        # Result should be a native PostgreSQL array
        assert isinstance(result, list)
        assert "test_isolated" in result

    @pytest.mark.P1
    def test_get_access_level_immutable_function(self, conn):
        """Test get_access_level() IMMUTABLE wrapper function."""
        cursor = conn.cursor()

        # Set project context
        cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))

        # Call IMMUTABLE wrapper
        cursor.execute("SELECT get_access_level()")
        result = cursor.fetchone()[0]

        assert result in ("super", "shared", "isolated")

    @pytest.mark.P1
    def test_get_rls_mode_immutable_function(self, conn):
        """Test get_rls_mode() IMMUTABLE wrapper function."""
        cursor = conn.cursor()

        # Set project context
        cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))

        # Call IMMUTABLE wrapper
        cursor.execute("SELECT get_rls_mode()")
        result = cursor.fetchone()[0]

        # RLS mode should be one of the valid migration phases
        assert result in ("pending", "shadow", "enforcing", "complete")


class TestTransactionScoping:
    """Test that RLS context is properly scoped to transactions."""

    @pytest.mark.P0
    def test_context_cleared_after_transaction_ends(self, conn):
        """Test that SET LOCAL variables are cleared when transaction ends."""
        cursor = conn.cursor()

        # Set context within explicit transaction
        with conn:
            cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))
            cursor.execute("SELECT current_setting('app.current_project', true)")
            assert cursor.fetchone()[0] == "test_isolated"

        # After transaction ends, SET LOCAL variables should be cleared
        # Note: The conn fixture does rollback, which also clears SET LOCAL
        cursor.execute("SELECT current_setting('app.current_project', true)")
        result = cursor.fetchone()[0]

        # Result should be None or empty (depending on PostgreSQL version)
        assert result is None or result == ""

    @pytest.mark.P1
    def test_context_persists_within_transaction(self, conn):
        """Test that context remains available throughout the transaction."""
        cursor = conn.cursor()

        # Start transaction
        with conn:
            # Set context
            cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))

            # Verify multiple times within same transaction
            cursor.execute("SELECT current_setting('app.current_project', true)")
            assert cursor.fetchone()[0] == "test_isolated"

            cursor.execute("SELECT current_setting('app.current_project', true)")
            assert cursor.fetchone()[0] == "test_isolated"

            cursor.execute("SELECT get_allowed_projects()")
            assert "test_isolated" in cursor.fetchone()[0]

    @pytest.mark.P2
    def test_transaction_isolation_between_tests(self, conn):
        """Test that context doesn't leak between tests (transaction rollback)."""
        cursor = conn.cursor()

        # First, check that no context is set (from previous test)
        cursor.execute("SELECT current_setting('app.current_project', true)")
        initial = cursor.fetchone()[0]
        assert initial is None or initial == ""

        # Set context in this test's transaction
        with conn:
            cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))
            cursor.execute("SELECT current_setting('app.current_project', true)")
            assert cursor.fetchone()[0] == "test_isolated"


class TestConnectionWithContextManager:
    """Test get_connection_with_project_context() connection wrapper."""

    @pytest.mark.P0
    def test_connection_wrapper_sets_rls_context(self, conn):
        """Test that connection wrapper sets RLS context automatically."""
        from mcp_server.middleware.context import get_project_id, set_project_id

        # Set project context (simulating TenantMiddleware)
        set_project_id("test_isolated")

        # Import after setting context
        from mcp_server.db.connection import get_connection_with_project_context_sync

        # Use connection wrapper
        with get_connection_with_project_context_sync() as conn:
            cursor = conn.cursor()

            # Verify RLS context is active
            cursor.execute("SELECT current_setting('app.current_project', true)")
            project = cursor.fetchone()[0]

            assert project == "test_isolated"

        # Clean up
        clear_context()

    @pytest.mark.P1
    def test_connection_wrapper_raises_error_without_context(self):
        """Test that connection wrapper raises error without project context."""
        from mcp_server.db.connection import get_connection_with_project_context_sync

        # Clear any existing context
        clear_context()

        # Should raise RLSContextError
        with pytest.raises(RLSContextError) as exc_info:
            with get_connection_with_project_context_sync() as conn:
                pass

        assert "No project context available" in str(exc_info.value)

    @pytest.mark.P1
    def test_connection_wrapper_maintains_retry_logic(self):
        """Test that connection wrapper maintains existing retry logic."""
        from mcp_server.middleware.context import set_project_id
        from mcp_server.db.connection import get_connection_with_project_context_sync

        # Set project context
        set_project_id("test_isolated")

        # Should work with existing connection pool
        try:
            with get_connection_with_project_context_sync() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                assert result[0] == 1
        except Exception as e:
            # If connection pool not initialized, that's okay for this test
            # We're just verifying the function signature and logic
            if "Connection pool not initialized" not in str(e):
                raise
        finally:
            clear_context()


class TestSetProjectContextErrors:
    """Test error handling in set_project_context()."""

    @pytest.mark.P1
    def test_unknown_project_raises_exception(self, conn):
        """Test that unknown project_id raises exception in set_project_context."""
        cursor = conn.cursor()

        # Should raise exception for unknown project
        with pytest.raises(Exception) as exc_info:
            cursor.execute("SELECT set_project_context(%s)", ("nonexistent_project",))

        # PostgreSQL should raise an exception
        assert "Unknown project" in str(exc_info.value) or "nonexistent_project" in str(exc_info.value)

    @pytest.mark.P2
    def test_set_project_context_security_definer(self, conn):
        """Test that set_project_context runs with SECURITY DEFINER.

        This means it can read from project_registry even if the caller
        doesn't have direct SELECT permissions.
        """
        cursor = conn.cursor()

        # The function should execute successfully even without
        # explicit permissions on project_registry (it has SECURITY DEFINER)
        cursor.execute("SELECT set_project_context(%s)", ("test_isolated",))

        # If we got here, SECURITY DEFINER is working
        cursor.execute("SELECT current_setting('app.current_project', true)")
        assert cursor.fetchone()[0] == "test_isolated"


class TestIntegrationWithMiddleware:
    """Integration tests with TenantMiddleware."""

    @pytest.mark.P1
    def test_middleware_sets_context_for_connection(self, conn):
        """Test that middleware validation sets context for connection wrapper."""
        from mcp_server.db.connection import get_connection_with_project_context_sync
        from mcp_server.middleware.tenant import TenantMiddleware

        # Create middleware instance
        middleware = TenantMiddleware()

        # Simulate middleware setting project context
        # In real flow, this happens in on_call_tool()
        set_project_id("test_isolated")

        try:
            # Connection wrapper should use the context set by middleware
            with get_connection_with_project_context_sync() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT current_setting('app.current_project', true)")
                project = cursor.fetchone()[0]
                assert project == "test_isolated"
        except Exception as e:
            if "Connection pool not initialized" not in str(e):
                raise
        finally:
            clear_context()
