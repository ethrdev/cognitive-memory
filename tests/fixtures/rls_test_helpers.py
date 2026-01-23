"""
RLS Test Data Fixtures for Epic 11.3.0

Story 11.3.0: pgTAP + Test Infrastructure

This module provides test data fixtures for RLS policy testing.
Creates ephemeral test projects (test_super, test_shared, test_isolated)
with sample data within test transactions.

AC8: Test Data Fixtures
AC9: Test Project Isolation from Production
"""

import pytest
from psycopg2.extensions import connection


@pytest.fixture
def rls_test_data(conn: connection):
    """
    Create ephemeral test projects and data for RLS testing.

    AC8: Test Data Fixtures

    Creates 3 test projects (super, shared, isolated) with sample data.
    All data is created within test transaction and rolled back after.

    Test Projects:
        - test_super: Access level 'super' (can read all projects)
        - test_shared: Access level 'shared' (can read own + test_isolated)
        - test_isolated: Access level 'isolated' (can read own only)

    Each project gets:
        - 2 nodes (e.g., test_super_node_1, test_super_node_2)
        - 2 edges
        - 2 l2_insights

    Usage:
        def test_rls_isolation(conn, rls_test_data):
            cur = conn.cursor()
            # Test data is already set up
            cur.execute("SELECT * FROM nodes WHERE project_id = 'test_super'")
            nodes = cur.fetchall()
            assert len(nodes) == 2

    AC9: Test projects are isolated from production - never use io, aa, ab, etc.
    """
    cur = conn.cursor()

    try:
        # Register test projects (ephemeral - rolled back after test)
        cur.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES
                ('test_super', 'Test Super Project', 'super'),
                ('test_shared', 'Test Shared Project', 'shared'),
                ('test_isolated', 'Test Isolated Project', 'isolated')
            ON CONFLICT (project_id) DO NOTHING
        """)

        # Grant read permission: test_shared -> test_isolated (simulates sm pattern)
        # This tests the cross-project permission feature
        cur.execute("""
            INSERT INTO project_read_permissions (reader, target)
            VALUES ('test_shared', 'test_isolated')
            ON CONFLICT (reader, target) DO NOTHING
        """)

        # Initialize RLS status for test projects (enforcing mode)
        cur.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
            VALUES
                ('test_super', 'enforcing', TRUE),
                ('test_shared', 'enforcing', TRUE),
                ('test_isolated', 'enforcing', TRUE)
            ON CONFLICT (project_id) DO NOTHING
        """)

        # Create test data for each project
        for project_id in ['test_super', 'test_shared', 'test_isolated']:
            # 2 nodes per project
            cur.execute("""
                INSERT INTO nodes (name, label, properties, project_id)
                VALUES
                    (%s || '_node_1', 'test', '{}', %s),
                    (%s || '_node_2', 'test', '{}', %s)
            """, (project_id, project_id, project_id, project_id))

            # 2 edges per project (node_1 -> node_2, node_2 -> node_1)
            cur.execute("""
                INSERT INTO edges (source_name, target_name, relation, properties, project_id)
                VALUES
                    (%s || '_node_1', %s || '_node_2', 'TEST_EDGE', '{}', %s),
                    (%s || '_node_2', %s || '_node_1', 'TEST_REVERSE', '{}', %s)
            """, (project_id, project_id, project_id, project_id, project_id, project_id))

            # 2 l2_insights per project
            # Note: Using array syntax for vector to avoid dimension issues
            cur.execute("""
                INSERT INTO l2_insights (content, embedding, properties, project_id)
                VALUES
                    ('Test content 1 for ' || %s, %s::vector, '{}', %s),
                    ('Test content 2 for ' || %s, %s::vector, '{}', %s)
            """, (project_id, [0.1] * 1536, project_id, project_id, [0.2] * 1536, project_id))

        # DO NOT commit - let the conn fixture handle rollback for test isolation
        # This ensures test data is automatically cleaned up (AC9)

        yield conn

    finally:
        # Transaction rollback happens in the conn fixture
        # This automatically cleans up all test data (AC9)
        pass


@pytest.fixture
def rls_test_data_with_permissions(conn: connection):
    """
    Create test data with explicit cross-project permissions.

    Extended version of rls_test_data that includes additional
    permission scenarios for testing SHARED access level.

    Permissions created:
        - test_shared can read test_isolated (semantic-memory pattern)
        - test_shared CANNOT read test_super (no permission)

    Usage:
        def test_shared_permissions(conn, rls_test_data_with_permissions):
            with ProjectContext(conn, 'test_shared'):
                # Can see test_shared and test_isolated data
                # Cannot see test_super data
    """
    cur = conn.cursor()

    try:
        # First create base test data
        # Use the rls_test_data fixture logic inline
        cur.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES
                ('test_super', 'Test Super Project', 'super'),
                ('test_shared', 'Test Shared Project', 'shared'),
                ('test_isolated', 'Test Isolated Project', 'isolated')
            ON CONFLICT (project_id) DO NOTHING
        """)

        # Cross-project permissions: test_shared -> test_isolated
        cur.execute("""
            INSERT INTO project_read_permissions (reader, target)
            VALUES ('test_shared', 'test_isolated')
            ON CONFLICT (reader, target) DO NOTHING
        """)

        cur.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
            VALUES
                ('test_super', 'enforcing', TRUE),
                ('test_shared', 'enforcing', TRUE),
                ('test_isolated', 'enforcing', TRUE)
            ON CONFLICT (project_id) DO NOTHING
        """)

        for project_id in ['test_super', 'test_shared', 'test_isolated']:
            # Create test nodes
            cur.execute("""
                INSERT INTO nodes (name, label, properties, project_id)
                VALUES
                    (%s || '_node_1', 'test', '{}', %s),
                    (%s || '_node_2', 'test', '{}', %s)
            """, (project_id, project_id, project_id, project_id))

        # DO NOT commit - let the conn fixture handle rollback for test isolation
        yield conn

    finally:
        # Transaction rollback happens in the conn fixture
        pass


@pytest.fixture
def rls_test_projects_only(conn: connection):
    """
    Create only test project registry entries (no data).

    Useful for tests that need to create their own specific test data
    but want the test projects registered.

    AC9: Ensures test projects are separate from production.
    """
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO project_registry (project_id, name, access_level)
            VALUES
                ('test_super', 'Test Super Project', 'super'),
                ('test_shared', 'Test Shared Project', 'shared'),
                ('test_isolated', 'Test Isolated Project', 'isolated')
            ON CONFLICT (project_id) DO NOTHING
        """)

        cur.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
            VALUES
                ('test_super', 'enforcing', TRUE),
                ('test_shared', 'enforcing', TRUE),
                ('test_isolated', 'enforcing', TRUE)
            ON CONFLICT (project_id) DO NOTHING
        """)

        # DO NOT commit - let the conn fixture handle rollback for test isolation
        yield conn

    finally:
        # Transaction rollback happens in the conn fixture
        pass
