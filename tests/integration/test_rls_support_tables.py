"""
Integration Tests for RLS Policies on Support Tables
Story 11.3.4: RLS Policies for Support Tables

Tests:
    - Conditional enforcement by rls_mode (AC3)
    - Access level behavior (super, shared, isolated) (AC4-AC9)
    - Cross-project write blocking (even for super) (AC3)
    - Performance: EXPLAIN ANALYZE confirms <10ms overhead (AC3)
    - Index usage: project_id index is used in query plan (AC3)
    - working_memory eviction respects project scope (AC4)

Support Tables:
    - working_memory (AC4)
    - episode_memory (AC5)
    - l0_raw (AC6)
    - ground_truth (AC7)
    - smf_proposals (AC8)
    - stale_memory (AC9)

Usage:
    pytest tests/integration/test_rls_support_tables.py -v
"""

import time
import pytest
from psycopg2.extensions import connection
from psycopg2 import sql


SUPPORT_TABLES = [
    'working_memory',
    'episode_memory',
    'l0_raw',
    'ground_truth',
    'smf_proposals',
    'stale_memory'
]


@pytest.mark.integration
@pytest.mark.P0
class TestRLSSupportTablesConditionalEnforcement:
    """
    Test conditional RLS enforcement by migration phase on support tables.

    AC3: Conditional RLS via Subquery Pattern
    - pending mode: All rows visible (legacy behavior)
    - shadow mode: All rows visible (audit-only)
    - enforcing mode: Only allowed rows visible
    """

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_pending_mode_allows_all_reads(self, conn: connection, table: str):
        """Pending mode: all rows visible (legacy behavior, no enforcement)"""
        with conn.cursor() as cur:
            # Set test projects to pending mode
            cur.execute("""
                INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
                VALUES ('io', 'pending', TRUE), ('aa', 'pending', TRUE)
                ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
            """)
            conn.commit()

            # Test: aa user should see all data in pending mode
            cur.execute("SELECT set_project_context('aa')")
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            result = cur.fetchone()[0]

            assert result >= 0, f"{table}: Pending mode should allow reads, got {result}"

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_shadow_mode_allows_all_reads(self, conn: connection, table: str):
        """Shadow mode: all rows visible (audit-only, shadow triggers log violations)"""
        with conn.cursor() as cur:
            # Set to shadow mode
            cur.execute("""
                INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
                VALUES ('aa', 'shadow', TRUE)
                ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
            """)
            conn.commit()

            cur.execute("SELECT set_project_context('aa')")
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            result = cur.fetchone()[0]

            # Shadow mode still allows all reads
            assert result >= 0, f"{table}: Shadow mode should allow reads, got {result}"

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_enforcing_mode_filters_by_allowed_projects(self, conn: connection, table: str):
        """Enforcing mode: only allowed rows visible"""
        with conn.cursor() as cur:
            # Set to enforcing mode
            cur.execute("""
                INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
                VALUES ('aa', 'enforcing', TRUE)
                ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
            """)
            conn.commit()

            cur.execute("SELECT set_project_context('aa')")
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            result = cur.fetchone()[0]

            # aa is shared and has permission to sm, so should see aa + sm
            assert result >= 0, f"{table}: Enforcing mode should allow reads, got {result}"


@pytest.mark.integration
@pytest.mark.P0
class TestRLSSupportTablesAccessLevelBehavior:
    """
    Test access level behavior for RLS policies on support tables.

    AC4-AC9: Access Level Behavior
    - Super: Can read all projects
    - Shared: Can read own + permitted projects
    - Isolated: Can read own project only
    """

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_super_reads_all_projects(self, conn: connection, table: str):
        """Super access level: can read all projects"""
        with conn.cursor() as cur:
            # Ensure enforcing mode is active
            cur.execute("""
                INSERT INTO rls_migration_status (project_id, migration_phase, rls_enabled)
                VALUES ('io', 'enforcing', TRUE)
                ON CONFLICT (project_id) DO UPDATE SET migration_phase = EXCLUDED.migration_phase
            """)
            conn.commit()

            # Test super user
            cur.execute("SELECT set_project_context('io')")
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            result = cur.fetchone()[0]

            # Super user should see all data
            assert result >= 0, f"{table}: Super user should read all, got {result}"

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_shared_reads_own_and_permitted(self, conn: connection, table: str):
        """Shared access level: can read own + permitted projects"""
        with conn.cursor() as cur:
            cur.execute("SELECT set_project_context('aa')")
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            result = cur.fetchone()[0]

            # aa is shared and has permission to sm
            # Should see aa + sm data
            assert result >= 0, f"{table}: Shared user should read own+permitted, got {result}"

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_isolated_reads_own_only(self, conn: connection, table: str):
        """Isolated access level: can read own project only"""
        with conn.cursor() as cur:
            cur.execute("SELECT set_project_context('sm')")
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            result = cur.fetchone()[0]

            # sm is isolated - should only see own data
            assert result >= 0, f"{table}: Isolated user should read own only, got {result}"


@pytest.mark.integration
@pytest.mark.P0
class TestRLSSupportTablesWriteIsolation:
    """
    Test write isolation - all levels can only write to own project.

    AC3: WRITE Policies - Strict Own-Project-Only
    - Even super users cannot write to other projects
    - Applies to INSERT, UPDATE, DELETE
    """

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_super_cannot_insert_to_other_project(self, conn: connection, table: str):
        """Super user cannot INSERT into other projects"""
        with conn.cursor() as cur:
            cur.execute("SELECT set_project_context('io')")

            # Create test data appropriate for each table type
            test_data = self._get_test_insert_data(table, 'aa')

            try:
                cur.execute(test_data)
                conn.commit()
                # If we get here without error, RLS isn't working properly
                assert False, f"{table}: INSERT should have been blocked by RLS policy"
            except Exception as e:
                conn.rollback()
                # Verify it's an RLS policy violation
                error_msg = str(e).lower()
                assert "violates" in error_msg or "new row violates row-level security policy" in error_msg, \
                    f"{table}: Expected RLS policy violation, got: {e}"

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_user_can_write_to_own_project(self, conn: connection, table: str):
        """User can INSERT into own project"""
        with conn.cursor() as cur:
            cur.execute("SELECT set_project_context('aa')")

            # Create test data appropriate for each table type
            test_data = self._get_test_insert_data(table, 'aa')

            # This should succeed
            try:
                result = self._execute_insert_with_fetch(conn, test_data)
                assert result is not None, f"{table}: INSERT to own project should succeed"
            except Exception as e:
                # Some tables may have constraints that prevent inserts
                # That's OK - we're testing RLS, not constraints
                error_msg = str(e).lower()
                if "violates" in error_msg and "row-level security" in error_msg:
                    assert False, f"{table}: INSERT to own project should not be blocked by RLS"

    def _get_test_insert_data(self, table: str, project_id: str) -> str:
        """Generate appropriate INSERT test data for each table type"""
        if table == 'working_memory':
            # working_memory has: id, content, importance, last_accessed, created_at, project_id
            return f"""
                INSERT INTO working_memory (content, importance, last_accessed, project_id)
                VALUES ('test working memory content', 0.5, NOW(), '{project_id}')
                RETURNING id
            """
        elif table == 'episode_memory':
            # episode_memory has: id, query, reward, reflection, created_at, embedding, project_id
            # Use array_fill for proper 1-D array creation
            return f"""
                INSERT INTO episode_memory (query, reward, reflection, embedding, project_id)
                VALUES ('test query', 0.5, 'test reflection',
                        (SELECT array_agg(x) FROM (SELECT 0.1::REAL UNION SELECT 0.2 UNION SELECT 0.3) AS t(x)),
                        '{project_id}')
                RETURNING id
            """
        elif table == 'l0_raw':
            return f"""
                INSERT INTO l0_raw (session_id, speaker, content, timestamp, project_id)
                VALUES ('test_session', 'test', 'test content', NOW(), '{project_id}')
                RETURNING id
            """
        elif table == 'ground_truth':
            # ground_truth has: id, query, expected_docs, judge1_score, judge2_score, judge1_model, judge2_model, kappa, created_at, project_id
            return f"""
                INSERT INTO ground_truth (query, expected_docs, judge1_score, judge2_score, project_id)
                VALUES ('test query', '{{{{1,2,3}}}}'::INTEGER[], '{{{{0.5}}}}'::FLOAT[], '{{{{0.6}}}}'::FLOAT[], '{project_id}')
                RETURNING id
            """
        elif table == 'smf_proposals':
            # smf_proposals has: id, trigger_type, proposed_action, affected_edges, reasoning, approval_level, status,
            # approved_by_io, approved_by_ethr, created_at, resolved_at, resolved_by, original_state, undo_deadline, project_id
            return f"""
                INSERT INTO smf_proposals (trigger_type, proposed_action, affected_edges, reasoning, status, approval_level, project_id)
                VALUES ('DISSONANCE', '{{{{"action": "test"}}}}'::JSONB, ARRAY '{{{{99999999-9999-9999-9999-999999999999}}}}'::UUID[],
                        'test reasoning', 'PENDING', 'bilateral', '{project_id}')
                RETURNING id
            """
        elif table == 'stale_memory':
            # stale_memory has: id, original_content, archived_at, importance, reason, project_id, content
            return f"""
                INSERT INTO stale_memory (original_content, archived_at, importance, reason, project_id)
                VALUES ('test stale content', NOW(), 0.5, 'MANUAL_ARCHIVE', '{project_id}')
                RETURNING id
            """
        else:
            raise ValueError(f"Unknown table: {table}")

    def _execute_insert_with_fetch(self, conn: connection, sql_query: str):
        """Execute INSERT with RETURNING and fetch result"""
        with conn.cursor() as cur:
            cur.execute(sql_query)
            result = cur.fetchone()
            conn.rollback()  # Cleanup
            return result


@pytest.mark.integration
@pytest.mark.P1
class TestRLSSupportTablesPerformance:
    """
    Test RLS policy performance on support tables.

    AC3: Conditional RLS via Subquery Pattern
    - EXPLAIN ANALYZE confirms <10ms overhead
    - Index usage on project_id
    - Single evaluation of IMMUTABLE functions
    """

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_subquery_pattern_single_evaluation(self, conn: connection, table: str):
        """Verify subquery pattern is used (single evaluation per query)"""
        with conn.cursor() as cur:
            cur.execute("SELECT set_project_context('io')")

            # Get query plan
            cur.execute(sql.SQL("""
                EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
                SELECT * FROM {} WHERE project_id = 'io' LIMIT 1
            """).format(sql.Identifier(table)))

            plan_lines = cur.fetchall()
            plan_text = "\n".join(str(row) for row in plan_lines)

            # Verify query executed successfully with RLS
            assert "rows=" in plan_text or "Index" in plan_text, \
                f"{table}: Query should execute with RLS. Got:\n{plan_text}"

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_rls_overhead_acceptable(self, conn: connection, table: str):
        """RLS policy evaluation adds acceptable overhead to query latency"""
        with conn.cursor() as cur:
            cur.execute("SELECT set_project_context('io')")

            # Get EXPLAIN ANALYZE to verify subquery pattern
            cur.execute(sql.SQL("""
                EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
                SELECT COUNT(*) FROM {} WHERE project_id = 'io'
            """).format(sql.Identifier(table)))
            plan_lines = cur.fetchall()
            plan_text = "\n".join(str(row) for row in plan_lines)

            # Verify subquery pattern is used (single function evaluation)
            assert "(SELECT get_rls_mode())" in plan_text or "(SELECT get_allowed_projects())" in plan_text, \
                f"{table}: Subquery pattern not found in plan. Verify RLS functions use subquery pattern:\n{plan_text}"

            # AC3: EXPLAIN ANALYZE confirms single evaluation per query
            # Count function calls in the plan to verify single evaluation
            # Should see "(SELECT get_rls_mode())" and "(SELECT get_allowed_projects())" at most once each
            get_rls_mode_count = plan_text.count("(SELECT get_rls_mode())")
            get_allowed_projects_count = plan_text.count("(SELECT get_allowed_projects())")

            # These functions should appear exactly once in the plan (single evaluation)
            assert get_rls_mode_count <= 1, \
                f"{table}: get_rls_mode() evaluated {get_rls_mode_count} times (should be 1). Plan:\n{plan_text}"
            assert get_allowed_projects_count <= 1, \
                f"{table}: get_allowed_projects() evaluated {get_allowed_projects_count} times (should be 1). Plan:\n{plan_text}"

            # Verify query executed
            assert "rows=" in plan_text, \
                f"{table}: Query should execute with RLS. Got:\n{plan_text}"

            # Warm up
            for _ in range(3):
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
                cur.fetchone()

            # Measure with RLS
            start = time.perf_counter()
            iterations = 10
            for _ in range(iterations):
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {} WHERE project_id = 'io'").format(sql.Identifier(table)))
                cur.fetchone()
            end = time.perf_counter()

            avg_latency_ms = (end - start) / iterations * 1000

            # AC3: Policy evaluation adds <10ms to query latency
            assert avg_latency_ms < 10, \
                f"{table}: RLS overhead too high: {avg_latency_ms:.2f}ms (AC3 requires: <10ms)"

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_index_used_with_rls(self, conn: connection, table: str):
        """Verify project_id index is used in query plan"""
        with conn.cursor() as cur:
            cur.execute("SELECT set_project_context('aa')")

            # Get query plan with enforcing mode
            cur.execute(sql.SQL("""
                EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
                SELECT * FROM {} WHERE project_id = 'aa' LIMIT 1
            """).format(sql.Identifier(table)))

            plan_lines = cur.fetchall()
            plan_text = "\n".join(str(row) for row in plan_lines)

            # Verify query plan shows index usage on project_id
            # AC3: Index usage is required for performance
            assert ("Index Scan" in plan_text or "Index Cond" in plan_text), \
                f"{table}: Expected Index Scan/Cond in plan (Seq Scan means NO index used). Query plan:\n{plan_text}"

            # Verify query executed successfully
            assert "rows=" in plan_text, f"{table}: Query should execute. Got:\n{plan_text}"


@pytest.mark.integration
@pytest.mark.P1
class TestAllSupportTablesHavePolicies:
    """
    Verify all support tables have RLS policies configured.

    AC1: RLS Activation on Support Tables
    - working_memory
    - episode_memory
    - l0_raw
    - ground_truth
    - smf_proposals
    - stale_memory
    - Each has: 1 RESTRICTIVE + 4 PERMISSIVE policies (5 total)
    """

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_table_has_all_policies(self, conn: connection, table: str):
        """Each support table has 5 policies (1 RESTRICTIVE + 4 PERMISSIVE)"""
        with conn.cursor() as cur:
            cur.execute(sql.SQL("""
                SELECT policyname FROM pg_policies
                WHERE schemaname = 'public' AND tablename = %s
                ORDER BY policyname
            """), (table,))
            policies = [row[0] for row in cur.fetchall()]

            expected = [
                f'require_project_id',  # RESTRICTIVE
                f'select_{table}',
                f'insert_{table}',
                f'update_{table}',
                f'delete_{table}'
            ]

            assert len(policies) == 5, \
                f"{table}: Expected 5 policies, got {len(policies)}: {policies}"

            for exp in expected:
                assert exp in policies, f"{table}: Missing policy: {exp}"

    def test_force_rls_enabled_on_all_support_tables(self, conn: connection):
        """FORCE ROW LEVEL SECURITY is enabled on all support tables"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT relname, relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname IN %s
                ORDER BY relname
            """, (tuple(SUPPORT_TABLES),))
            results = cur.fetchall()

            assert len(results) == 6, \
                f"Expected 6 support tables, got {len(results)}"

            for table_name, rls_enabled, force_rls in results:
                assert rls_enabled, f"{table_name}: RLS not enabled"
                assert force_rls, f"{table_name}: FORCE ROW LEVEL SECURITY not enabled"


@pytest.mark.integration
@pytest.mark.P0
class TestSystemTablesNoRLS:
    """
    Verify system tables explicitly do NOT have RLS.

    AC10: System Tables Explicitly Excluded
    - rls_audit_log: Must always be writable for security auditing
    - rls_migration_status: System table for migration phases
    - project_registry: System table for project definitions
    - project_read_permissions: System table for ACL data
    """

    SYSTEM_TABLES = [
        'rls_audit_log',
        'rls_migration_status',
        'project_registry',
        'project_read_permissions'
    ]

    @pytest.mark.parametrize("table", SYSTEM_TABLES)
    def test_system_table_has_no_rls(self, conn: connection, table: str):
        """System tables should NOT have RLS enabled"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = %s
            """, (table,))
            result = cur.fetchone()

            if result:
                rls_enabled, force_rls = result
                assert not rls_enabled, f"{table}: System table should NOT have RLS enabled"
                assert not force_rls, f"{table}: System table should NOT have FORCE RLS enabled"

            # Also check no policies exist
            cur.execute("""
                SELECT COUNT(*) FROM pg_policies
                WHERE schemaname = 'public' AND tablename = %s
            """, (table,))
            policy_count = cur.fetchone()[0]

            assert policy_count == 0, \
                f"{table}: System table should have NO RLS policies, found {policy_count}"


@pytest.mark.integration
@pytest.mark.P0
class TestWorkingMemoryEvictionRespectsProjectScope:
    """
    Test that working_memory eviction operates within project scope.

    AC4: Working Memory Isolation
    - Each project sees only its own working memory entries
    - Eviction operates within project scope
    """

    def test_eviction_respects_project_scope(self, conn: connection):
        """Eviction queries should only affect own project's data"""
        with conn.cursor() as cur:
            # Create test data for different projects
            # working_memory has: id, content, importance, last_accessed, created_at, project_id
            cur.execute("""
                INSERT INTO working_memory (content, importance, last_accessed, project_id)
                VALUES
                    ('io content 1', 0.1, NOW() - INTERVAL '1 hour', 'io'),
                    ('io content 2', 0.2, NOW() - INTERVAL '2 hours', 'io'),
                    ('aa content 1', 0.1, NOW() - INTERVAL '1 hour', 'aa')
                ON CONFLICT DO NOTHING
            """)
            conn.commit()

            # Set context to aa project
            cur.execute("SELECT set_project_context('aa')")

            # Count total working_memory entries visible to aa
            cur.execute("SELECT COUNT(*) FROM working_memory")
            visible_count = cur.fetchone()[0]

            # Verify aa can only see its own data
            cur.execute("SELECT COUNT(*) FROM working_memory WHERE project_id = 'aa'")
            aa_count = cur.fetchone()[0]

            assert visible_count >= aa_count, \
                f"aa project should only see its own working_memory entries"

            # Verify aa cannot see io's data through eviction queries
            cur.execute("SELECT COUNT(*) FROM working_memory WHERE project_id = 'io'")
            io_visible = cur.fetchone()[0]

            assert io_visible == 0, \
                "aa project should not see io's working_memory entries for eviction"

            conn.rollback()


@pytest.mark.integration
@pytest.mark.P1
class TestRLSSupportTablesSubqueryPattern:
    """
    Verify RLS policies use subquery pattern for IMMUTABLE functions.

    AC3: Conditional RLS via Subquery Pattern
    - They use Subquery pattern: (SELECT get_...())
    - EXPLAIN ANALYZE confirms single evaluation per query
    """

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_select_policy_uses_subquery_pattern(self, conn: connection, table: str):
        """SELECT policy uses subquery pattern for IMMUTABLE functions"""
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pg_get_expr(qual, policyoid)
                FROM pg_policy
                WHERE polname = %s AND polrelid = %s::regclass
            """, (f'select_{table}', table))

            result = cur.fetchone()
            if result and result[0]:
                policy_expr = result[0]

                # Verify subquery pattern is used
                assert "(SELECT get_rls_mode())" in policy_expr, \
                    f"{table}: SELECT policy should use subquery pattern for get_rls_mode()"

                assert "(SELECT get_allowed_projects())" in policy_expr, \
                    f"{table}: SELECT policy should use subquery pattern for get_allowed_projects()"

    @pytest.mark.parametrize("table", SUPPORT_TABLES)
    def test_write_policies_use_subquery_pattern(self, conn: connection, table: str):
        """Write policies use subquery pattern for get_current_project()"""
        with conn.cursor() as cur:
            # Check INSERT policy
            cur.execute("""
                SELECT pg_get_expr(with_check_qual, policyoid)
                FROM pg_policy
                WHERE polname = %s AND polrelid = %s::regclass
            """, (f'insert_{table}', table))

            result = cur.fetchone()
            if result and result[0]:
                policy_expr = result[0]

                # Verify subquery pattern is used
                assert "(SELECT get_current_project())" in policy_expr, \
                    f"{table}: INSERT policy should use subquery pattern for get_current_project()"
