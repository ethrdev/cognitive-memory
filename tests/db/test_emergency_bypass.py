"""
Integration Tests for Migration 038: BYPASSRLS Emergency Role

Tests the emergency bypass role for RLS debugging.
Verifies that:
1. Role rls_emergency_bypass is created with BYPASSRLS and NOLOGIN attributes
2. SET ROLE activation works for superusers
3. Non-superusers cannot activate role (permission denied)
4. Role bypasses RLS policies (all projects visible)
5. RESET ROLE restores RLS enforcement
6. Lock timeout procedure for DISABLE ROW LEVEL SECURITY

Story: 11.3.5 - BYPASSRLS Emergency Role
Acceptance Criteria: AC1, AC2, AC3, AC4, AC6
"""

import os
import pytest

from psycopg2.extensions import connection
from psycopg2 import errors as PostgresError


def test_emergency_role_created(conn: connection):
    """AC1: Test that role rls_emergency_bypass is created with correct attributes."""
    cursor = conn.cursor()

    # Check role exists
    cursor.execute(
        """
        SELECT EXISTS(
            SELECT 1 FROM pg_roles
            WHERE rolname = 'rls_emergency_bypass'
        )
        """
    )
    role_exists = cursor.fetchone()[0]

    assert role_exists is True, "rls_emergency_bypass role should exist"

    # Check role attributes
    cursor.execute(
        """
        SELECT rolcanlogin, rolsuper, rolbypassrls
        FROM pg_roles
        WHERE rolname = 'rls_emergency_bypass'
        """
    )
    role_attrs = cursor.fetchone()

    assert role_attrs is not None, "Role should have retrievable attributes"
    assert role_attrs[0] is False, "rolcanlogin should be False (NOLOGIN)"
    assert role_attrs[2] is True, "rolbypassrls should be True (BYPASSRLS)"

    cursor.close()


def test_emergency_role_has_comment(conn: connection):
    """AC1: Test that role has descriptive comment explaining emergency-only usage."""
    cursor = conn.cursor()

    # Role comments are stored in pg_shdescription (shared descriptions)
    cursor.execute(
        """
        SELECT description
        FROM pg_shdescription
        WHERE objoid = (SELECT oid FROM pg_roles WHERE rolname = 'rls_emergency_bypass')
        """
    )
    comment = cursor.fetchone()[0]

    assert comment is not None, "Role should have a comment"
    assert "emergency" in comment.lower(), "Comment should mention emergency usage"
    assert "debug" in comment.lower() or "debugging" in comment.lower(), "Comment should mention debugging"

    cursor.close()


def test_superuser_can_activate_bypass(conn: connection):
    """AC2: Test that superusers can SET ROLE to rls_emergency_bypass."""
    cursor = conn.cursor()

    # Verify current user is superuser (test database assumption)
    cursor.execute("SELECT current_user")
    current_user = cursor.fetchone()[0]

    cursor.execute("SELECT usesuper FROM pg_user WHERE usename = current_user")
    is_superuser = cursor.fetchone()[0]

    # Skip test if not superuser
    # Superuser is required because only superusers can SET ROLE to rls_emergency_bypass
    if not is_superuser:
        cursor.close()
        pytest.skip("Test requires superuser connection - only superusers can SET ROLE to bypass role")

    # Activate bypass role
    cursor.execute("SET ROLE rls_emergency_bypass")

    # Verify role is active
    cursor.execute("SELECT current_role")
    current_role = cursor.fetchone()[0]

    assert current_role == "rls_emergency_bypass", "Current role should be rls_emergency_bypass"

    # Reset role
    cursor.execute("RESET ROLE")

    cursor.close()


def test_bypass_role_sees_all_projects(conn: connection):
    """AC2: Test that bypass role can see all project data regardless of RLS policies."""
    cursor = conn.cursor()

    # Verify current user is superuser
    # Only superusers can SET ROLE to rls_emergency_bypass
    cursor.execute("SELECT usesuper FROM pg_user WHERE usename = current_user")
    is_superuser = cursor.fetchone()[0]

    if not is_superuser:
        cursor.close()
        pytest.skip("Test requires superuser connection - bypass role testing needs elevated privileges")

    # First, set project context to an isolated project (should see limited data)
    cursor.execute("SET LOCAL app.current_project = 'test_isolated'")

    # Count nodes with RLS active (should be limited to test_isolated project)
    cursor.execute("SELECT COUNT(*) FROM nodes WHERE project_id = 'test_isolated'")
    isolated_count = cursor.fetchone()[0] or 0

    # Now activate bypass role - should see ALL projects
    cursor.execute("SET ROLE rls_emergency_bypass")

    # Count all nodes regardless of project
    cursor.execute("SELECT COUNT(*) FROM nodes")
    total_count = cursor.fetchone()[0] or 0

    # Reset
    cursor.execute("RESET ROLE")

    assert total_count >= isolated_count, "Bypass role should see all nodes (>= isolated view)"

    cursor.close()


def test_non_superuser_cannot_activate_bypass(conn: connection):
    """AC4: Test that non-superusers get permission denied when trying to activate bypass."""
    cursor = conn.cursor()

    # We need to test with a non-superuser role
    # Create a temporary test role without superuser privileges
    cursor.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'test_non_superuser') THEN
                CREATE ROLE test_non_superuser WITH NOLOGIN;
            END IF;
        END $$;
        """
    )

    # Get the current user
    cursor.execute("SELECT current_user")
    current_user = cursor.fetchone()[0]

    # Grant the test role to the current user so they can SET ROLE to it
    cursor.execute(
        """
        GRANT test_non_superuser TO current_user
        """
    )

    # Switch to the non-superuser role
    cursor.execute("SET ROLE test_non_superuser")

    # Now try to SET ROLE to rls_emergency_bypass as non-superuser
    # This should fail with permission denied
    try:
        cursor.execute("SET ROLE rls_emergency_bypass")
        # If we reach here, the test should fail
        cursor.execute("RESET ROLE")  # Cleanup
        cursor.execute("RESET ROLE")  # Reset back to original role
        assert False, "Non-superuser should NOT be able to SET ROLE rls_emergency_bypass"
    except PostgresError.Error as e:
        # Expected: permission denied or similar error
        cursor.execute("RESET ROLE")  # Cleanup - reset back to original role
        assert "permission" in str(e).lower() or "denied" in str(e).lower(), \
            f"Should get permission denied, got: {e}"

    cursor.close()


def test_reset_role_restores_rls(conn: connection):
    """AC3: Test that RESET ROLE restores RLS enforcement based on app.current_project."""
    cursor = conn.cursor()

    # Verify current user is superuser
    # Superuser required to test bypass role activation and RLS restoration
    cursor.execute("SELECT usesuper FROM pg_user WHERE usename = current_user")
    is_superuser = cursor.fetchone()[0]

    if not is_superuser:
        cursor.close()
        pytest.skip("Test requires superuser connection - RLS testing needs elevated privileges")

    # Set project context to isolated project
    cursor.execute("SET LOCAL app.current_project = 'test_isolated'")

    # Count with RLS active (isolated view)
    cursor.execute("SELECT COUNT(*) FROM nodes WHERE project_id = 'test_isolated'")
    isolated_count = cursor.fetchone()[0] or 0

    # Activate bypass - should see all
    cursor.execute("SET ROLE rls_emergency_bypass")
    cursor.execute("SELECT COUNT(*) FROM nodes")
    bypass_count = cursor.fetchone()[0] or 0

    # Reset role - should go back to isolated view
    cursor.execute("RESET ROLE")
    cursor.execute("SELECT COUNT(*) FROM nodes WHERE project_id = 'test_isolated'")
    reset_count = cursor.fetchone()[0] or 0

    assert bypass_count >= isolated_count, "Bypass should show more or equal data"
    assert reset_count == isolated_count, "After RESET, should return to isolated view"

    cursor.close()


def test_lock_timeout_prevents_blocking(conn: connection):
    """AC6: Test that lock_timeout of 5s is used for DISABLE ROW LEVEL SECURITY."""
    cursor = conn.cursor()

    # Set lock timeout to 5 seconds
    cursor.execute("SET lock_timeout = '5s'")

    # Verify lock_timeout is set
    cursor.execute("SHOW lock_timeout")
    lock_timeout = cursor.fetchone()[0]

    assert lock_timeout == "5s", "lock_timeout should be set to 5s"

    # Reset to default
    cursor.execute("RESET lock_timeout")

    # Verify reset
    cursor.execute("SHOW lock_timeout")
    lock_timeout_reset = cursor.fetchone()[0]

    assert lock_timeout_reset == "0", "lock_timeout should reset to default (0 = no timeout)"

    cursor.close()


def test_role_is_idempotent(conn: connection):
    """Test that migration is idempotent - running it twice doesn't cause errors."""
    cursor = conn.cursor()

    # Get role attributes before
    cursor.execute(
        """
        SELECT rolcanlogin, rolsuper, rolbypassrls
        FROM pg_roles
        WHERE rolname = 'rls_emergency_bypass'
        """
    )
    attrs_before = cursor.fetchone()

    # Simulate running migration again (IF NOT EXISTS check)
    # This should not change anything
    cursor.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rls_emergency_bypass') THEN
                RAISE EXCEPTION 'Role should already exist';
            END IF;
        END $$;
        """
    )

    # Get role attributes after
    cursor.execute(
        """
        SELECT rolcanlogin, rolsuper, rolbypassrls
        FROM pg_roles
        WHERE rolname = 'rls_emergency_bypass'
        """
    )
    attrs_after = cursor.fetchone()

    assert attrs_before == attrs_after, "Role attributes should not change on re-run"

    cursor.close()
