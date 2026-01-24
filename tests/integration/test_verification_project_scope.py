"""
Integration tests for Verification Operations with Project Scope (Story 11.7.3).

Tests that get_golden_test_results, get_node_by_name, and get_edge respect
project boundaries through Row-Level Security (RLS) policies.

AC Covered:
    - get_golden_test_results uses project-scoped golden test data
    - get_node_by_name returns only nodes from accessible projects
    - get_edge returns only edges from accessible projects
    - Super project sees all verification data across all projects

Usage:
    pytest tests/integration/test_verification_project_scope.py -v

INFRASTRUCTURE REQUIREMENT:
    These tests require a database user WITHOUT the bypassrls privilege.
    See module docstring in test_insight_read_project_scope.py for details.
"""

from __future__ import annotations

import pytest
from datetime import date
from psycopg2.extensions import connection


def _can_test_rls(conn: connection) -> bool:
    """Check if RLS policies will be enforced."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT rolbypassrls
            FROM pg_roles
            WHERE rolname = session_user
        """)
        result = cur.fetchone()
        return result is not None and not result[0] if result else False


@pytest.fixture(autouse=True)
def check_rls_testing_capability(conn: connection):
    """Skip RLS tests if database user has bypassrls privilege."""
    can_test_rls = _can_test_rls(conn)
    if not can_test_rls:
        pytest.skip(
            "RLS testing requires database user WITHOUT bypassrls privilege. "
            "Current user has bypassrls=TRUE which bypasses all RLS policies."
        )


@pytest.fixture(autouse=True)
def setup_test_data(conn: connection):
    """Create test data for verification operations across multiple projects"""
    with conn.cursor() as cur:
        # Set RLS to enforcing mode for all projects
        cur.execute("""
            INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
            VALUES ('io', 'enforcing', TRUE), ('aa', 'enforcing', TRUE), ('sm', 'enforcing', TRUE)
            ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
        """)

        # Set up project_read_permissions for shared project 'aa' to read 'sm'
        cur.execute("""
            INSERT INTO project_read_permissions (reader_project_id, target_project_id)
            VALUES ('aa', 'sm')
            ON CONFLICT (reader_project_id, target_project_id) DO NOTHING
        """)

        # Create test nodes for each project
        cur.execute("DELETE FROM nodes WHERE name IN ('SharedNode', 'TestNode') AND project_id IN ('io', 'aa', 'sm')")
        cur.execute("""
            INSERT INTO nodes (id, name, label, properties, project_id)
            VALUES
                (1001, 'SharedNode', 'test', '{}'::jsonb, 'io'),
                (2001, 'SharedNode', 'test', '{}'::jsonb, 'aa'),
                (3001, 'SharedNode', 'test', '{}'::jsonb, 'sm'),
                (1002, 'TestNode', 'test', '{}'::jsonb, 'io'),
                (2002, 'TestNode', 'test', '{}'::jsonb, 'aa')
        """)

        # Create test edges for each project
        cur.execute("""
            INSERT INTO edges (source_id, target_id, relation, weight, properties, memory_sector, project_id)
            VALUES
                (1001, 1001, 'TEST_EDGE', 1.0, '{}'::jsonb, 'semantic', 'io'),
                (2001, 2001, 'TEST_EDGE', 1.0, '{}'::jsonb, 'semantic', 'aa'),
                (3001, 3001, 'TEST_EDGE', 1.0, '{}'::jsonb, 'semantic', 'sm')
        """)

        # Create test golden test set entries for each project
        cur.execute("DELETE FROM golden_test_set WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("""
            INSERT INTO golden_test_set (query, query_type, expected_docs, project_id)
            VALUES
                ('io test query', 'short', ARRAY[]::INTEGER[], 'io'),
                ('aa test query', 'short', ARRAY[]::INTEGER[], 'aa'),
                ('sm test query', 'short', ARRAY[]::INTEGER[], 'sm')
            ON CONFLICT DO NOTHING
        """)

        # Create test model drift log entries for each project
        cur.execute("DELETE FROM model_drift_log WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("""
            INSERT INTO model_drift_log (date, precision_at_5, num_queries, drift_detected, baseline_p5, project_id)
            VALUES
                (CURRENT_DATE, 0.85, 10, FALSE, 0.84, 'io'),
                (CURRENT_DATE, 0.90, 5, FALSE, 0.89, 'aa'),
                (CURRENT_DATE, 0.88, 8, FALSE, 0.87, 'sm')
            ON CONFLICT (date, project_id) DO NOTHING
        """)

        conn.commit()

    yield

    # Cleanup
    with conn.cursor() as cur:
        cur.execute("DELETE FROM model_drift_log WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM golden_test_set WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM edges WHERE project_id IN ('io', 'aa', 'sm') AND relation = 'TEST_EDGE'")
        cur.execute("DELETE FROM nodes WHERE name IN ('SharedNode', 'TestNode') AND project_id IN ('io', 'aa', 'sm')")
        conn.commit()


# =============================================================================
# Test: RLS Policies Exist on Verification Tables
# =============================================================================


def test_rls_policies_exist_on_golden_test_set(conn: connection):
    """AC: get_golden_test_results Project Scoping - Verify RLS enabled on golden_test_set"""
    with conn.cursor() as cur:
        # Check RLS is enabled on golden_test_set
        cur.execute("""
            SELECT rowsecurity, forcerowsecurity
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'golden_test_set'
        """)
        result = cur.fetchone()
        assert result is not None, "golden_test_set table not found"
        assert result[0] is True, "RLS not enabled on golden_test_set"


def test_rls_policies_exist_on_model_drift_log(conn: connection):
    """AC: get_golden_test_results Project Scoping - Verify RLS enabled on model_drift_log"""
    with conn.cursor() as cur:
        # Check RLS is enabled on model_drift_log
        cur.execute("""
            SELECT rowsecurity, forcerowsecurity
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = 'model_drift_log'
        """)
        result = cur.fetchone()
        assert result is not None, "model_drift_log table not found"
        assert result[0] is True, "RLS not enabled on model_drift_log"


def test_project_id_column_exists_on_golden_test_set(conn: connection):
    """AC: get_golden_test_results Project Scoping - Verify project_id column exists"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'golden_test_set' AND column_name = 'project_id'
        """)
        result = cur.fetchone()
        assert result is not None, "project_id column not found on golden_test_set"
        assert result[1] == 'character varying', f"Unexpected data type: {result[1]}"
        assert result[2] == 'NO', "project_id should be NOT NULL"


def test_project_id_column_exists_on_model_drift_log(conn: connection):
    """AC: get_golden_test_results Project Scoping - Verify project_id column exists"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'model_drift_log' AND column_name = 'project_id'
        """)
        result = cur.fetchone()
        assert result is not None, "project_id column not found on model_drift_log"
        assert result[1] == 'character varying', f"Unexpected data type: {result[1]}"
        assert result[2] == 'NO', "project_id should be NOT NULL"


# =============================================================================
# Test: get_golden_test_results Project Scoping
# =============================================================================


@pytest.mark.asyncio
async def test_golden_test_set_filters_by_project():
    """AC: get_golden_test_results Project Scoping - Project sees only own golden test data"""
    from mcp_server.db.connection import get_connection_with_project_context
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # Set project context to 'aa'
    set_project_context('aa')

    try:
        async with get_connection_with_project_context(read_only=True) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM golden_test_set")
            count = cur.fetchone()[0]

            # Should only see 'aa' golden test entries (1 entry)
            assert count == 1, f"Expected 1 golden test entry for project 'aa', got {count}"

            cur.execute("SELECT query, project_id FROM golden_test_set")
            result = cur.fetchone()
            assert result[0] == 'aa test query', "Should see aa's query"
            assert result[1] == 'aa', "Should have project_id='aa'"
    finally:
        reset_project_context()


@pytest.mark.asyncio
async def test_model_drift_log_filters_by_project():
    """AC: get_golden_test_results Project Scoping - Project sees only own drift data"""
    from mcp_server.db.connection import get_connection_with_project_context
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # Set project context to 'aa'
    set_project_context('aa')

    try:
        async with get_connection_with_project_context(read_only=True) as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM model_drift_log")
            count = cur.fetchone()[0]

            # Should only see 'aa' drift log entries (1 entry)
            assert count == 1, f"Expected 1 drift log entry for project 'aa', got {count}"

            cur.execute("SELECT precision_at_5, project_id FROM model_drift_log")
            result = cur.fetchone()
            assert result[0] == 0.90, "Should see aa's precision score"
            assert result[1] == 'aa', "Should have project_id='aa'"
    finally:
        reset_project_context()


# =============================================================================
# Test: get_node_by_name Project Filtering
# =============================================================================


@pytest.mark.asyncio
async def test_get_node_by_name_respects_project_rls():
    """AC: get_node_by_name Project Filtering - Returns only project's own node"""
    from mcp_server.db.graph import get_node_by_name
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # Set project context to 'aa'
    set_project_context('aa')

    try:
        # Get node as 'aa' project
        node = await get_node_by_name('SharedNode')

        # Should see 'aa' node (id 2001), not 'io' or 'sm'
        assert node is not None, "Should find node"
        assert node['name'] == 'SharedNode', "Should find SharedNode"
        assert node['project_id'] == 'aa', f"Should get aa's node, got project_id={node.get('project_id')}"
        assert node['id'] == 2001, f"Should get aa's node (id=2001), got id={node['id']}"
    finally:
        reset_project_context()


@pytest.mark.asyncio
async def test_get_node_by_name_no_cross_project_leakage():
    """AC: get_node_by_name Project Filtering - Does not return other project's node with same name"""
    from mcp_server.db.graph import get_node_by_name
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # Test with 'aa' project (should NOT see 'io' or 'sm' nodes)
    set_project_context('aa')

    try:
        node = await get_node_by_name('SharedNode')
        assert node is not None, "Should find node for project 'aa'"
        assert node['project_id'] == 'aa', "Should only see aa's node, not io or sm"

        # Verify we cannot see 'io' or 'sm' nodes
        assert node['id'] != 1001, "Should not see io's node (id=1001)"
        assert node['id'] != 3001, "Should not see sm's node (id=3001)"
    finally:
        reset_project_context()


@pytest.mark.asyncio
async def test_get_node_by_name_shared_project_can_read_permitted():
    """AC: get_node_by_name Project Filtering - Shared project can read permitted project data"""
    from mcp_server.db.graph import get_node_by_name
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # 'aa' has read permission on 'sm' (set in setup_test_data)
    # But 'TestNode' only exists in 'io' and 'aa', not 'sm'
    set_project_context('aa')

    try:
        # Get a node that exists in 'aa'
        node = await get_node_by_name('TestNode')
        assert node is not None, "Should find TestNode for project 'aa'"
        assert node['project_id'] == 'aa', "Should get aa's TestNode"
    finally:
        reset_project_context()


# =============================================================================
# Test: get_edge Project Filtering
# =============================================================================


@pytest.mark.asyncio
async def test_get_edge_respects_project_rls():
    """AC: get_edge Project Filtering - Returns only project's own edge"""
    from mcp_server.db.graph import get_edge_by_names
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # Set project context to 'aa'
    set_project_context('aa')

    try:
        # Get edge as 'aa' project
        edge = await get_edge_by_names('SharedNode', 'SharedNode', 'TEST_EDGE')

        # Should see 'aa' edge, not 'io' or 'sm'
        assert edge is not None, "Should find edge"
        assert edge['relation'] == 'TEST_EDGE', "Should find TEST_EDGE"
        assert edge['project_id'] == 'aa', f"Should get aa's edge, got project_id={edge.get('project_id')}"
        assert edge['source_id'] == 2001, f"Should get aa's edge (source_id=2001), got source_id={edge['source_id']}"
    finally:
        reset_project_context()


@pytest.mark.asyncio
async def test_get_edge_no_cross_project_leakage():
    """AC: get_edge Project Filtering - Does not return edge from other projects"""
    from mcp_server.db.graph import get_edge_by_names
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # Test with 'aa' project (should NOT see 'io' or 'sm' edges)
    set_project_context('aa')

    try:
        edge = await get_edge_by_names('SharedNode', 'SharedNode', 'TEST_EDGE')
        assert edge is not None, "Should find edge for project 'aa'"
        assert edge['project_id'] == 'aa', "Should only see aa's edge, not io or sm"

        # Verify we cannot see 'io' or 'sm' edges
        assert edge['source_id'] != 1001, "Should not see io's edge (source_id=1001)"
        assert edge['source_id'] != 3001, "Should not see sm's edge (source_id=3001)"
    finally:
        reset_project_context()


# =============================================================================
# Test: Super Project Access
# =============================================================================


@pytest.mark.asyncio
async def test_super_project_sees_all_golden_test_data():
    """AC: All - Super project sees all verification data across all projects"""
    from mcp_server.db.connection import get_connection_with_project_context
    from mcp_server.middleware.context import set_project_context, reset_project_context

    # 'io' is a super project, should see all data
    set_project_context('io')

    try:
        async with get_connection_with_project_context(read_only=True) as conn:
            cur = conn.cursor()

            # Should see all golden test entries (io, aa, sm = 3 entries)
            cur.execute("SELECT COUNT(*) FROM golden_test_set")
            count = cur.fetchone()[0]
            assert count == 3, f"Super project 'io' should see all 3 golden test entries, got {count}"

            # Should see all drift log entries
            cur.execute("SELECT COUNT(*) FROM model_drift_log")
            count = cur.fetchone()[0]
            assert count == 3, f"Super project 'io' should see all 3 drift log entries, got {count}"
    finally:
        reset_project_context()


# =============================================================================
# Test: Composite Primary Key on model_drift_log
# =============================================================================


def test_model_drift_log_has_composite_primary_key(conn: connection):
    """AC: get_golden_test_results Project Scoping - Verify (date, project_id) is composite primary key"""
    with conn.cursor() as cur:
        # Check primary key constraint
        cur.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = 'model_drift_log'::regclass
              AND i.indisprimary
            ORDER BY a.attnum
        """)
        pk_columns = [row[0] for row in cur.fetchall()]

        assert 'date' in pk_columns, "date should be part of primary key"
        assert 'project_id' in pk_columns, "project_id should be part of primary key"
        assert len(pk_columns) == 2, f"Expected 2 PK columns (date, project_id), got {len(pk_columns)}"
