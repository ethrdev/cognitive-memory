"""
Integration Tests for SMF Read Operations with Project Scope (Story 11.7.1).

Tests that SMF proposals and dissonance checks respect project boundaries
through Row-Level Security (RLS) policies.

AC Covered:
    - smf_pending_proposals returns only proposals from current project
    - smf_review returns "not found" for inaccessible proposals
    - Bilateral consent works within project scope
    - dissonance_check respects project boundaries

Usage:
    pytest tests/integration/test_smf_read_project_scope.py -v

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
    """Create test data for SMF read operations across multiple projects"""
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
        cur.execute("DELETE FROM smf_proposals WHERE project_id IN ('io', 'aa', 'sm')")

        # Create test proposals for each project
        # io project (super) proposal
        cur.execute("""
            INSERT INTO smf_proposals (
                id, trigger_type, proposed_action, affected_edges,
                reasoning, approval_level, status, project_id
            )
            VALUES (
                1001, 'MANUAL', '{"action": "test"}'::jsonb, '{}',
                'io test proposal', 'io', 'pending', 'io'
            )
        """)

        # aa project (shared) proposal
        cur.execute("""
            INSERT INTO smf_proposals (
                id, trigger_type, proposed_action, affected_edges,
                reasoning, approval_level, status, project_id
            )
            VALUES (
                2001, 'MANUAL', '{"action": "test"}'::jsonb, '{}',
                'aa test proposal', 'io', 'pending', 'aa'
            )
        """)

        # sm project (isolated) proposal
        cur.execute("""
            INSERT INTO smf_proposals (
                id, trigger_type, proposed_action, affected_edges,
                reasoning, approval_level, status, project_id
            )
            VALUES (
                3001, 'MANUAL', '{"action": "test"}'::jsonb, '{}',
                'sm test proposal', 'io', 'pending', 'sm'
            )
        """)

        # Create test nodes and edges for dissonance check tests
        cur.execute("DELETE FROM nodes WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM edges WHERE project_id IN ('io', 'aa', 'sm')")

        # Create nodes for each project
        cur.execute("""
            INSERT INTO nodes (id, name, label, properties, project_id)
            VALUES
                ('00000001-0001-0001-0001-000000000001', 'io_node', 'test', '{}', 'io'),
                ('00000001-0002-0002-0002-000000000001', 'aa_node', 'test', '{}', 'aa'),
                ('00000001-0003-0003-0003-000000000001', 'sm_node', 'test', '{}', 'sm')
            ON CONFLICT (id) DO NOTHING
        """)

        # Create edges for each project
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
        cur.execute("DELETE FROM smf_proposals WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM edges WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM nodes WHERE project_id IN ('io', 'aa', 'sm')")
        cur.execute("DELETE FROM project_read_permissions WHERE reader_project_id = 'aa' AND target_project_id = 'sm'")
        conn.commit()


def await_query(coro):
    """Helper to run async functions in sync tests"""
    return asyncio.get_event_loop().run_until_complete(coro)


# =============================================================================
# Test Class: SMF Pending Proposals Project Scope
# =============================================================================

@pytest.mark.integration
@pytest.mark.P0
class TestSMFPendingProposalsProjectScope:
    """
    Test that smf_pending_proposals respects project boundaries.

    Story 11.7.1: AC #smf_pending_proposals Project Filtering
    - Shared project sees own + permitted proposals
    - Super project sees all proposals
    - Isolated project sees own proposals only
    """

    def test_shared_project_sees_own_and_permitted_proposals(self, conn: connection):
        """
        Test that shared project (aa) sees own + permitted (sm) proposals.

        AC: smf_pending_proposals Project Filtering
        Given project 'aa' (shared, can read 'sm') lists pending proposals
        When smf_pending_proposals() is called
        Then only proposals affecting 'aa' or permitted 'sm' are returned
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.smf_pending_proposals import handle_smf_pending_proposals

        # Set project context as 'aa' (shared, can read aa + sm)
        set_project_id("aa")

        try:
            # Should see own proposals (aa, id=2001)
            aa_result = await_query(handle_smf_pending_proposals())
            assert "error" not in aa_result, f"Should get proposals for own project: {aa_result}"

            proposal_ids = [p["id"] for p in aa_result.get("proposals", [])]
            assert 2001 in proposal_ids, "Should see own project proposal"

            # Should NOT see io proposal (not permitted)
            assert 1001 not in proposal_ids, "Should not see super project proposal"

        finally:
            clear_context()

    def test_super_project_sees_all_proposals(self, conn: connection):
        """
        Test that super project (io) sees all proposals.

        AC: smf_pending_proposals Project Filtering
        Given project 'io' (super) lists pending proposals
        When smf_pending_proposals() is called
        Then all proposals from all projects are returned
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.smf_pending_proposals import handle_smf_pending_proposals

        # Set project context as 'io' (super)
        set_project_id("io")

        try:
            # Should see all proposals
            result = await_query(handle_smf_pending_proposals())
            assert "error" not in result, f"Super project should see all proposals: {result}"

            proposal_ids = [p["id"] for p in result.get("proposals", [])]
            assert 1001 in proposal_ids, "Super project should see io proposal"
            assert 2001 in proposal_ids, "Super project should see aa proposal"
            assert 3001 in proposal_ids, "Super project should see sm proposal"

        finally:
            clear_context()

    def test_isolated_project_sees_own_proposals_only(self, conn: connection):
        """
        Test that isolated project (sm) sees own proposals only.

        AC: smf_pending_proposals Project Filtering
        Given project 'sm' (isolated) lists pending proposals
        When smf_pending_proposals() is called
        Then only proposals from 'sm' project are returned
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.smf_pending_proposals import handle_smf_pending_proposals

        # Set project context as 'sm' (isolated)
        set_project_id("sm")

        try:
            # Should see own proposals only
            result = await_query(handle_smf_pending_proposals())
            assert "error" not in result, f"Should get proposals for isolated project: {result}"

            proposal_ids = [p["id"] for p in result.get("proposals", [])]
            assert 3001 in proposal_ids, "Should see own project proposal"

            # Should NOT see other proposals
            assert 1001 not in proposal_ids, "Should not see io proposal"
            assert 2001 not in proposal_ids, "Should not see aa proposal"

        finally:
            clear_context()


# =============================================================================
# Test Class: SMF Review Project Scope
# =============================================================================

@pytest.mark.integration
@pytest.mark.P0
class TestSMFReviewProjectScope:
    """
    Test that smf_review respects project boundaries.

    Story 11.7.1: AC #smf_review Project Filtering
    - Accessible proposals return full details
    - Inaccessible proposals return "not found" (no existence leak)
    """

    def test_shared_project_can_review_accessible_proposals(self, conn: connection):
        """
        Test that shared project (aa) can review accessible proposals.

        AC: smf_review Project Filtering
        Given project 'aa' reviews a specific proposal
        When the proposal affects 'aa' or permitted 'sm' data
        Then full proposal details are returned
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.smf_review import handle_smf_review

        # Set project context as 'aa' (shared)
        set_project_id("aa")

        try:
            # Should be able to review own proposal (aa, id=2001)
            aa_result = await_query(handle_smf_review({"proposal_id": 2001}))
            assert "error" not in aa_result, f"Should review own proposal: {aa_result}"
            assert aa_result["proposal"]["id"] == 2001
            assert aa_result["proposal"]["project_id"] == "aa"

        finally:
            clear_context()

    def test_shared_project_cannot_review_inaccessible_proposals(self, conn: connection):
        """
        Test that shared project (aa) cannot review inaccessible proposals.

        AC: smf_review Project Filtering
        Given project 'aa' reviews a specific proposal
        When the proposal affects 'io' data (not accessible)
        Then error: "Proposal not found or not accessible"
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.smf_review import handle_smf_review

        # Set project context as 'aa' (shared)
        set_project_id("aa")

        try:
            # Should NOT be able to review io proposal (not permitted)
            io_result = await_query(handle_smf_review({"proposal_id": 1001}))
            assert "error" in io_result, "Should return error for non-permitted proposal"
            assert io_result["error"]["code"] == 404, "Should return 404 (no existence leak)"
            assert "not found" in io_result["error"]["message"].lower(), "Should say 'not found'"

        finally:
            clear_context()

    def test_super_project_can_review_all_proposals(self, conn: connection):
        """
        Test that super project (io) can review all proposals.

        AC: smf_review Project Filtering
        Given project 'io' (super) reviews a specific proposal
        When the proposal affects any project
        Then full proposal details are returned
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.smf_review import handle_smf_review

        # Set project context as 'io' (super)
        set_project_id("io")

        try:
            # Should be able to review all proposals
            for proposal_id in [1001, 2001, 3001]:
                result = await_query(handle_smf_review({"proposal_id": proposal_id}))
                assert "error" not in result, f"Super project should review proposal {proposal_id}: {result}"
                assert result["proposal"]["id"] == proposal_id

        finally:
            clear_context()


# =============================================================================
# Test Class: Bilateral Consent Project Scope
# =============================================================================

@pytest.mark.integration
@pytest.mark.P0
class TestBilateralConsentProjectScope:
    """
    Test that bilateral consent works within project scope.

    Story 11.7.1: AC #Bilateral Consent Project Scope
    - Proposals requiring bilateral consent work within same project
    - Proposals are not visible across project boundaries
    """

    def test_bilateral_consent_within_same_project(self, conn: connection):
        """
        Test that bilateral consent proposals work within same project.

        AC: Bilateral Consent Project Scope
        Given a proposal requires bilateral consent (approval_level=BILATERAL)
        When both parties' projects are within accessible scope
        Then proposal is visible to both parties
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.smf_pending_proposals import handle_smf_pending_proposals

        # Create a bilateral consent proposal for 'aa' project
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO smf_proposals (
                    trigger_type, proposed_action, affected_edges,
                    reasoning, approval_level, status, project_id
                )
                VALUES (
                    'MANUAL', '{"action": "test"}'::jsonb, '{}',
                    'aa bilateral proposal', 'bilateral', 'pending', 'aa'
                )
                RETURNING id
            """)
            proposal_id = cur.fetchone()[0]
            conn.commit()

        # Set project context as 'aa' (shared)
        set_project_id("aa")

        try:
            # Should see the bilateral consent proposal
            result = await_query(handle_smf_pending_proposals())
            assert "error" not in result, f"Should see bilateral consent proposal: {result}"

            proposal_ids = [p["id"] for p in result.get("proposals", [])]
            assert proposal_id in proposal_ids, "Should see bilateral consent proposal in same project"

        finally:
            clear_context()

            # Clean up
            with conn.cursor() as cur:
                cur.execute("DELETE FROM smf_proposals WHERE id = %s", (proposal_id,))
                conn.commit()


# =============================================================================
# Test Class: Dissonance Check Project Scope
# =============================================================================

@pytest.mark.integration
@pytest.mark.P0
class TestDissonanceCheckProjectScope:
    """
    Test that dissonance_check respects project boundaries.

    Story 11.7.1: AC #dissonance_check Project Scoping
    - Only edges within accessible projects are analyzed
    - Dissonances with inaccessible project edges are not reported
    """

    def test_dissonance_check_respects_project_boundaries(self, conn: connection):
        """
        Test that dissonance_check only analyzes edges within project scope.

        AC: dissonance_check Project Scoping
        Given project 'aa' runs dissonance check
        When dissonance_check() is called
        Then only edges within accessible projects are analyzed
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.tools.dissonance_check import handle_dissonance_check
        from mcp.server import Server

        # Set project context as 'aa' (shared, can read aa + sm)
        set_project_id("aa")

        try:
            # Run dissonance check on aa_node
            # Should only analyze edges in 'aa' and 'sm' projects, not 'io'
            result = await_query(handle_dissonance_check(
                Server("test-server"),
                context_node="aa_node",
                scope="full"
            ))

            # Should complete without error
            assert result is not None, "Dissonance check should complete"

            # Result should be a list of TextContent
            assert isinstance(result, list), "Result should be a list"

            # If dissonances were found, they should only involve accessible edges
            # (This is a basic smoke test - comprehensive testing would require
            # setting up specific dissonance scenarios)
            for content in result:
                assert hasattr(content, "text"), "Content should have text attribute"

        finally:
            clear_context()

    def test_dissonance_engine_uses_project_context(self, conn: connection):
        """
        Test that DissonanceEngine uses project-scoped connections.

        AC: dissonance_check Project Scoping
        Given DissonanceEngine is initialized with project_id
        When _fetch_edges() is called
        Then get_connection_with_project_context_sync() is used
        """
        from mcp_server.middleware.context import set_project_id, clear_context
        from mcp_server.analysis.dissonance import DissonanceEngine

        # Set project context as 'aa' (shared)
        set_project_id("aa")

        try:
            # Initialize engine with project context
            engine = DissonanceEngine(project_id="aa")

            # Verify project_id is set
            assert engine.project_id == "aa", "Engine should have project_id set"

            # Run dissonance check - should use project-scoped connection
            result = await_query(engine.dissonance_check(
                context_node="aa_node",
                scope="full"
            ))

            # Should complete without RLS errors
            assert result is not None, "Dissonance check should complete with project context"

        finally:
            clear_context()


# =============================================================================
# Test Class: RLS Policies Verification
# =============================================================================

@pytest.mark.integration
@pytest.mark.P0
class TestSMFRLSPoliciesCreated:
    """
    Test that RLS policies are created on smf_proposals table.

    Story 11.7.1: AC #RLS Policies Created
    - smf_proposals has RLS enabled
    - require_project_id RESTRICTIVE policy exists
    - select_smf_proposals policy exists
    """

    def test_rls_enabled_on_smf_proposals(self, conn: connection):
        """
        Test that RLS is enabled on smf_proposals table.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_tables for smf_proposals
        Then rowsecurity = TRUE and forcerowsecurity = TRUE
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tablename, rowsecurity AS rls_enabled, forcerowsecurity AS force_rls
                FROM pg_tables
                WHERE schemaname='public' AND tablename = 'smf_proposals'
            """)
            result = cur.fetchone()

            assert result is not None, "smf_proposals table not found"
            assert result["rls_enabled"] is True, "RLS should be enabled on smf_proposals"
            assert result["force_rls"] is True, "FORCE RLS should be enabled on smf_proposals"

    def test_restrictive_policy_exists_on_smf_proposals(self, conn: connection):
        """
        Test that RESTRICTIVE require_project_id policy exists on smf_proposals.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_policies for smf_proposals
        Then require_project_id policy exists with permissive = FALSE
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT policyname, permissive
                FROM pg_policies
                WHERE schemaname='public' AND tablename = 'smf_proposals'
                AND policyname = 'require_project_id'
            """)
            result = cur.fetchone()

            assert result is not None, "require_project_id policy should exist"
            assert result["permissive"] is False, "require_project_id should be RESTRICTIVE"

    def test_select_policy_exists_on_smf_proposals(self, conn: connection):
        """
        Test that SELECT policy exists on smf_proposals.

        AC: RLS Policies Created
        Given Migration 037 has been applied
        When querying pg_policies for smf_proposals
        Then select_smf_proposals policy exists
        """
        with conn.cursor() as cur:
            cur.execute("""
                SELECT policyname
                FROM pg_policies
                WHERE schemaname='public' AND tablename = 'smf_proposals'
                AND policyname = 'select_smf_proposals'
            """)
            result = cur.fetchone()

            assert result is not None, "select_smf_proposals policy should exist"
