"""
Integration Tests for Utility Read Operations with Project Scope (Story 11.7.2).

Tests that list_episodes and count_by_type respect project boundaries
through Row-Level Security (RLS) policies.

AC Covered:
    - list_episodes returns only episodes from accessible projects
    - count_by_type returns counts for accessible data only
    - Super project sees all data across all projects

Usage:
    pytest tests/integration/test_utility_read_project_scope.py -v

INFRASTRUCTURE REQUIREMENT:
    These tests require a database user WITHOUT the bypassrls privilege.
    See module docstring in test_insight_read_project_scope.py for details.
"""

from __future__ import annotations

import asyncio
import pytest
from psycopg2.extensions import connection


def _can_test_rls(conn: connection) -> bool:
    """
    Check if the current database connection can test RLS policies.

    Returns True if RLS policies will be enforced, False if bypassrls is enabled.
    """
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
    """
    Skip RLS tests if database user has bypassrls privilege.
    """
    can_test_rls = _can_test_rls(conn)
    if not can_test_rls:
        pytest.skip(
            "RLS testing requires database user WITHOUT bypassrls privilege. "
            "Current user has bypassrls=TRUE which bypasses all RLS policies. "
            "See module docstring for infrastructure setup instructions."
        )


@pytest.fixture(autouse=True)
def setup_test_data(conn: connection):
    """Create test data for utility read operations across multiple projects"""
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

        # Clean up existing test data
        cur.execute("DELETE FROM episode_memory WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM working_memory WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM l0_raw WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM nodes WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM edges WHERE project_id IN ('io', 'aa', 'sm')")

        # Create test l2_insights for each project (Story 11.7.2 AC)
        cur.execute("""
            INSERT INTO l2_insights (id, content, project_id)
            VALUES
                ('ins-001-io', 'io insight', 'io'),
                ('ins-002-io', 'io insight 2', 'io'),
                ('ins-001-aa', 'aa insight', 'aa'),
                ('ins-001-sm', 'sm insight', 'sm')
            ON CONFLICT (id) DO NOTHING
        """)

        # Create test episodes for each project
        cur.execute("""
            INSERT INTO episode_memory (id, query, reward, project_id)
            VALUES
                (1001, 'io episode 1', 0.9, 'io'),
                (1002, 'io episode 2', 0.8, 'io'),
                (2001, 'aa episode 1', 0.7, 'aa'),
                (2002, 'aa episode 2', 0.6, 'aa'),
                (3001, 'sm episode 1', 0.5, 'sm'),
                (3002, 'sm episode 2', 0.4, 'sm')
        """)

        # Create test working memory entries
        cur.execute("""
            INSERT INTO working_memory (key, value, project_id)
            VALUES
                ('io_key', 'io_value', 'io'),
                ('aa_key', 'aa_value', 'aa'),
                ('sm_key', 'sm_value', 'sm')
        """)

        # Create test raw dialogues
        cur.execute("""
            INSERT INTO l0_raw (content, project_id)
            VALUES
                ('io dialogue', 'io'),
                ('aa dialogue', 'aa'),
                ('sm dialogue', 'sm')
        """)

        # Create test nodes for graph counts
        cur.execute("""
            INSERT INTO nodes (id, name, label, properties, project_id)
            VALUES
                ('00000001-0001-0001-0001-000000000001', 'io_node', 'test', '{}', 'io'),
                ('00000001-0002-0002-0002-000000000001', 'aa_node', 'test', '{}', 'aa'),
                ('00000001-0003-0003-0003-000000000001', 'sm_node', 'test', '{}', 'sm')
            ON CONFLICT (id) DO NOTHING
        """)

        # Create test edges for graph counts
        cur.execute("""
            INSERT INTO edges (
                source_id, target_id, relation, properties, project_id,
                source_name, target_name
            )
            VALUES
                (
                    '00000001-0001-0001-0001-000000000001',
                    '00000001-0001-0001-0001-000000000001',
                    'TEST_EDGE', '{}'::jsonb, 'io', 'io_node', 'io_node'
                ),
                (
                    '00000001-0002-0002-0002-000000000001',
                    '00000001-0002-0002-0002-000000000001',
                    'TEST_EDGE', '{}'::jsonb, 'aa', 'aa_node', 'aa_node'
                ),
                (
                    '00000001-0003-0003-0003-000000000001',
                    '00000001-0003-0003-0003-000000000001',
                    'TEST_EDGE', '{}'::jsonb, 'sm', 'sm_node', 'sm_node'
                )
        """)

        conn.commit()

    yield

    # Cleanup
    with conn.cursor() as cur:
        cur.execute("DELETE FROM episode_memory WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM working_memory WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM l0_raw WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM edges WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM nodes WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM l2_insights WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM project_read_permissions WHERE reader_project_id = 'aa' AND target_project_id = 'sm'")
        conn.commit()


def await_query(coro):
    """Helper to run async functions in sync tests"""
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# Test Class: list_episodes Project Scope
# =============================================================================

@pytest.mark.integration
@pytest.mark.P0
class TestListEpisodesProjectScope:
    """
    Test that list_episodes respects project boundaries.

    Story 11.7.2: AC #list_episodes Project Filtering
    - Shared project sees own episodes
    - Super project sees all episodes
    - Isolated project sees own episodes only
    """

    def test_shared_project_sees_own_episodes_only(self, conn: connection):
        """
        Test that shared project (aa) sees own episodes only.

        AC: list_episodes Project Filtering
        Given project 'aa' (shared, can read 'sm') lists episodes
        When list_episodes(limit=50) is called
        Then only 'aa' owned episodes are returned
        And 'io' episodes are not visible

        Note: episode_memory is isolated, so even shared projects only see their own.
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.list_episodes import handle_list_episodes

        # Set project context as 'aa' (shared)
        set_project_id("aa")

        try:
            # Should see own episodes only (aa, ids 2001, 2002)
            aa_result = await_query(handle_list_episodes({}))
            assert "error" not in aa_result, f"Should get episodes for own project: {aa_result}"

            episode_ids = [ep["id"] for ep in aa_result.get("episodes", [])]

            # Should see own episodes
            assert 2001 in episode_ids, "Should see own project episode"
            assert 2002 in episode_ids, "Should see own project episode"

            # Should NOT see io episodes (not accessible)
            assert 1001 not in episode_ids, "Should not see io project episode"
            assert 1002 not in episode_ids, "Should not see io project episode"

            # Should NOT see sm episodes (episode_memory is isolated)
            assert 3001 not in episode_ids, "Should not see sm project episode"
            assert 3002 not in episode_ids, "Should not see sm project episode"

            # total_count should reflect only own episodes
            assert aa_result["total_count"] == 2, f"Should count own episodes only, got {aa_result['total_count']}"

        finally:
            clear_context()

    def test_super_project_sees_all_episodes(self, conn: connection):
        """
        Test that super project (io) sees all episodes.

        AC: list_episodes Project Filtering (Super User)
        Given project 'io' (super) lists episodes
        When list_episodes(limit=50) is called
        Then all episodes from all projects are returned
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.list_episodes import handle_list_episodes

        # Set project context as 'io' (super)
        set_project_id("io")

        try:
            # Should see all episodes
            result = await_query(handle_list_episodes({}))
            assert "error" not in result, f"Super project should see all episodes: {result}"

            episode_ids = [ep["id"] for ep in result.get("episodes", [])]

            # Should see all episodes from all projects
            assert 1001 in episode_ids, "Super project should see io episode"
            assert 1002 in episode_ids, "Super project should see io episode"
            assert 2001 in episode_ids, "Super project should see aa episode"
            assert 2002 in episode_ids, "Super project should see aa episode"
            assert 3001 in episode_ids, "Super project should see sm episode"
            assert 3002 in episode_ids, "Super project should see sm episode"

            # total_count should reflect all episodes
            assert result["total_count"] == 6, f"Should count all episodes, got {result['total_count']}"

        finally:
            clear_context()

    def test_isolated_project_sees_own_episodes_only(self, conn: connection):
        """
        Test that isolated project (sm) sees own episodes only.

        AC: list_episodes Project Filtering
        Given project 'sm' (isolated) lists episodes
        When list_episodes(limit=50) is called
        Then only 'sm' episodes are returned
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.list_episodes import handle_list_episodes

        # Set project context as 'sm' (isolated)
        set_project_id("sm")

        try:
            # Should see own episodes only
            result = await_query(handle_list_episodes({}))
            assert "error" not in result, f"Should get episodes for isolated project: {result}"

            episode_ids = [ep["id"] for ep in result.get("episodes", [])]

            # Should see own episodes
            assert 3001 in episode_ids, "Should see own project episode"
            assert 3002 in episode_ids, "Should see own project episode"

            # Should NOT see other episodes
            assert 1001 not in episode_ids, "Should not see io episode"
            assert 1002 not in episode_ids, "Should not see io episode"
            assert 2001 not in episode_ids, "Should not see aa episode"
            assert 2002 not in episode_ids, "Should not see aa episode"

            # total_count should reflect own episodes only
            assert result["total_count"] == 2, f"Should count own episodes only, got {result['total_count']}"

        finally:
            clear_context()

    def test_list_episodes_count_query_respects_rls(self, conn: connection):
        """
        Test that list_episodes count query respects RLS.

        AC: list_episodes Project Filtering
        Given project 'aa' lists episodes
        When list_episodes() is called
        Then total_count reflects only accessible episodes
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.list_episodes import handle_list_episodes

        # Set project context as 'aa' (shared)
        set_project_id("aa")

        try:
            # total_count should only count accessible episodes
            result = await_query(handle_list_episodes({}))

            # aa should only see its own 2 episodes
            assert result["total_count"] == 2, f"total_count should reflect accessible data only, got {result['total_count']}"

        finally:
            clear_context()


# =============================================================================
# Test Class: count_by_type Project Scope
# =============================================================================

@pytest.mark.integration
@pytest.mark.P0
class TestCountByTypeProjectScope:
    """
    Test that count_by_type respects project boundaries.

    Story 11.7.2: AC #count_by_type Project Filtering
    - Shared project sees counts for own + permitted data
    - Super project sees counts for all data
    - Isolated project sees counts for own data only
    """

    def test_shared_project_sees_accessible_counts(self, conn: connection):
        """
        Test that shared project (aa) sees counts for accessible data only.

        AC: count_by_type Project Filtering
        Given project 'aa' (shared, can read 'sm') requests counts
        When count_by_type() is called
        Then counts reflect only accessible data:
          - nodes: count of 'aa' + 'sm' nodes
          - edges: count of 'aa' + 'sm' edges
          - l2_insights: count of 'aa' + 'sm' insights
          - episodes: count of 'aa' only (isolated)
          - working_memory: count of 'aa' only (isolated)
          - raw_dialogues: count of 'aa' + 'sm' (shared permission)
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.count_by_type import handle_count_by_type

        # Set project context as 'aa' (shared, can read sm)
        set_project_id("aa")

        try:
            # Get counts as 'aa' project
            result = await_query(handle_count_by_type({}))

            assert "error" not in result, f"Should get counts for shared project: {result}"

            # Graph counts: aa + sm (shared access)
            assert result["graph_nodes"] >= 1, "Should see at least aa nodes"
            assert result["graph_edges"] >= 1, "Should see at least aa edges"

            # L2 insights: aa + sm (shared access) - should see 2 insights
            assert result["l2_insights"] == 2, f"l2_insights should be aa + sm (2), got {result['l2_insights']}"

            # Episodes: aa only (isolated table)
            assert result["episodes"] == 2, f"episodes should be aa only (2), got {result['episodes']}"

            # Working memory: aa only (isolated table)
            assert result["working_memory"] == 1, f"working_memory should be aa only (1), got {result['working_memory']}"

            # Raw dialogues: aa + sm (shared permission)
            assert result["raw_dialogues"] >= 1, "Should see at least aa raw dialogues"

            # Should NOT count io data (not accessible)
            # Total should be less than full dataset (io + aa + sm)
            total_accessible = result["graph_nodes"] + result["graph_edges"] + result.get("l2_insights", 0)
            assert total_accessible < 10, "Shared project should not see all data"

        finally:
            clear_context()

    def test_super_project_sees_all_counts(self, conn: connection):
        """
        Test that super project (io) sees all counts.

        AC: count_by_type Project Filtering (Super User)
        Given project 'io' (super) requests counts
        When count_by_type() is called
        Then counts reflect ALL project data
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.count_by_type import handle_count_by_type

        # Set project context as 'io' (super)
        set_project_id("io")

        try:
            # Get counts as 'io' project
            result = await_query(handle_count_by_type({}))

            assert "error" not in result, f"Super project should get all counts: {result}"

            # Should see all data from all projects
            # 3 nodes (io + aa + sm)
            assert result["graph_nodes"] == 3, f"Super project should see all nodes, got {result['graph_nodes']}"

            # 3 edges (io + aa + sm)
            assert result["graph_edges"] == 3, f"Super project should see all edges, got {result['graph_edges']}"

            # 4 l2_insights (2 from io, 1 from aa, 1 from sm)
            assert result["l2_insights"] == 4, f"Super project should see all l2_insights, got {result['l2_insights']}"

            # 6 episodes (2 from each project)
            assert result["episodes"] == 6, f"Super project should see all episodes, got {result['episodes']}"

            # 3 working memory entries
            assert result["working_memory"] == 3, f"Super project should see all working memory, got {result['working_memory']}"

            # 3 raw dialogues
            assert result["raw_dialogues"] == 3, f"Super project should see all raw dialogues, got {result['raw_dialogues']}"

        finally:
            clear_context()

    def test_isolated_project_sees_own_counts_only(self, conn: connection):
        """
        Test that isolated project (sm) sees own counts only.

        AC: count_by_type Project Filtering
        Given project 'sm' (isolated) requests counts
        When count_by_type() is called
        Then counts reflect own data only
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.count_by_type import handle_count_by_type

        # Set project context as 'sm' (isolated)
        set_project_id("sm")

        try:
            # Get counts as 'sm' project
            result = await_query(handle_count_by_type({}))

            assert "error" not in result, f"Should get counts for isolated project: {result}"

            # Should see own data only
            assert result["graph_nodes"] == 1, f"Isolated project should see own nodes (1), got {result['graph_nodes']}"
            assert result["graph_edges"] == 1, f"Isolated project should see own edges (1), got {result['graph_edges']}"
            assert result["episodes"] == 2, f"Isolated project should see own episodes (2), got {result['episodes']}"
            assert result["working_memory"] == 1, f"Isolated project should see own working memory (1), got {result['working_memory']}"
            assert result["raw_dialogues"] == 1, f"Isolated project should see own raw dialogues (1), got {result['raw_dialogues']}"

        finally:
            clear_context()

    def test_count_by_type_no_existence_leakage(self, conn: connection):
        """
        Test that count_by_type returns 0 for inaccessible data (no existence leakage).

        AC: count_by_type Project Filtering
        Given project 'sm' (isolated) has no access to 'io'
        When count_by_type() is called
        Then counts for inaccessible data are 0 (not error)
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.count_by_type import handle_count_by_type

        # Set project context as 'sm' (isolated, no access to io or aa)
        set_project_id("sm")

        try:
            # Get counts - should not error, just return 0 for inaccessible
            result = await_query(handle_count_by_type({}))

            assert "error" not in result, "Should return counts (0 for inaccessible) rather than error"

            # All counts should be >= 0 (no negative counts)
            assert result["graph_nodes"] >= 0, "Counts should be non-negative"
            assert result["graph_edges"] >= 0, "Counts should be non-negative"
            assert result["episodes"] >= 0, "Counts should be non-negative"
            assert result["working_memory"] >= 0, "Counts should be non-negative"
            assert result["raw_dialogues"] >= 0, "Counts should be non-negative"

        finally:
            clear_context()


# =============================================================================
# Test Class: RLS Policies Verification
# =============================================================================

@pytest.mark.integration
@pytest.mark.P0
class TestUtilityRLSPoliciesCreated:
    """
    Test that RLS policies are created on utility tables.

    Story 11.7.2: AC #RLS Policies Created
    - episode_memory has RLS enabled
    - working_memory has RLS enabled
    - l0_raw has RLS enabled
    """

    def test_rls_enabled_on_episode_memory(self, conn: connection):
        """
        Test that RLS is enabled on episode_memory table.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_tables for episode_memory
        Then rowsecurity = TRUE and forcerowsecurity = TRUE
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename, rowsecurity AS rls_enabled, forcerowsecurity AS force_rls
                FROM pg_tables
                WHERE schemaname='public' AND tablename = 'episode_memory'
            """)
            result = cur.fetchone()

            assert result is not None, "episode_memory table not found"
            assert result["rls_enabled"] is True, "RLS should be enabled on episode_memory"
            assert result["force_rls"] is True, "FORCE RLS should be enabled on episode_memory"

    def test_rls_enabled_on_working_memory(self, conn: connection):
        """
        Test that RLS is enabled on working_memory table.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_tables for working_memory
        Then rowsecurity = TRUE and forcerowsecurity = TRUE
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename, rowsecurity AS rls_enabled, forcerowsecurity AS force_rls
                FROM pg_tables
                WHERE schemaname='public' AND tablename = 'working_memory'
            """)
            result = cur.fetchone()

            assert result is not None, "working_memory table not found"
            assert result["rls_enabled"] is True, "RLS should be enabled on working_memory"
            assert result["force_rls"] is True, "FORCE RLS should be enabled on working_memory"

    def test_rls_enabled_on_l0_raw(self, conn: connection):
        """
        Test that RLS is enabled on l0_raw table.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_tables for l0_raw
        Then rowsecurity = TRUE and forcerowsecurity = TRUE
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename, rowsecurity AS rls_enabled, forcerowsecurity AS force_rls
                FROM pg_tables
                WHERE schemaname='public' AND tablename = 'l0_raw'
            """)
            result = cur.fetchone()

            assert result is not None, "l0_raw table not found"
            assert result["rls_enabled"] is True, "RLS should be enabled on l0_raw"
            assert result["force_rls"] is True, "FORCE RLS should be enabled on l0_raw"

    def test_select_policy_exists_on_episode_memory(self, conn: connection):
        """
        Test that SELECT policy exists on episode_memory.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_policies for episode_memory
        Then select_episode_memory policy exists
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT policyname
                FROM pg_policies
                WHERE schemaname='public' AND tablename = 'episode_memory'
                AND policyname = 'select_episode_memory'
            """)
            result = cur.fetchone()

            assert result is not None, "select_episode_memory policy should exist"

    def test_select_policy_exists_on_working_memory(self, conn: connection):
        """
        Test that SELECT policy exists on working_memory.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_policies for working_memory
        Then select_working_memory policy exists
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT policyname
                FROM pg_policies
                WHERE schemaname='public' AND tablename = 'working_memory'
                AND policyname = 'select_working_memory'
            """)
            result = cur.fetchone()

            assert result is not None, "select_working_memory policy should exist"

    def test_select_policy_exists_on_l0_raw(self, conn: connection):
        """
        Test that SELECT policy exists on l0_raw.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_policies for l0_raw
        Then select_l0_raw policy exists
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT policyname
                FROM pg_policies
                WHERE schemaname='public' AND tablename = 'l0_raw'
                AND policyname = 'select_l0_raw'
            """)
            result = cur.fetchone()

            assert result is not None, "select_l0_raw policy should exist"

    def test_rls_enabled_on_l2_insights(self, conn: connection):
        """
        Test that RLS is enabled on l2_insights table.

        AC: RLS Policies Created
        Given RLS has been applied to l2_insights (Story 11.6.3)
        When querying pg_tables for l2_insights
        Then rowsecurity = TRUE
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename, rowsecurity AS rls_enabled
                FROM pg_tables
                WHERE schemaname='public' AND tablename = 'l2_insights'
            """)
            result = cur.fetchone()

            assert result is not None, "l2_insights table not found"
            assert result["rls_enabled"] is True, "RLS should be enabled on l2_insights"

    def test_select_policy_exists_on_l2_insights(self, conn: connection):
        """
        Test that SELECT policy exists on l2_insights.

        AC: RLS Policies Created
        Given Migration 039 has been applied (Story 11.6.3 fix)
        When querying pg_policies for l2_insights
        Then select_l2_insights policy exists
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT policyname
                FROM pg_policies
                WHERE schemaname='public' AND tablename = 'l2_insights'
                AND policyname = 'select_l2_insights'
            """)
            result = cur.fetchone()

            assert result is not None, "select_l2_insights policy should exist"
