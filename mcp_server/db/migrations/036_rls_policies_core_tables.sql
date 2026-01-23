-- Migration 036: RLS Policies for Core Tables
-- Story 11.3.3: RLS Policies for Core Tables
--
-- Purpose: Create Row-Level Security policies on core tables (l2_insights, nodes, edges)
--          with conditional enforcement based on migration phase (pending/shadow/enforcing)
-- Dependencies: Migration 034 (RLS Helper Functions), Migration 027 (project_id columns)
-- Risk: MEDIUM - Enables RLS with conditional enforcement (shadow mode first)
-- Rollback: 036_rls_policies_core_tables_rollback.sql
--
-- Policy Structure per Table:
--   1. RESTRICTIVE: require_project_id (blocks NULL project_id - defense-in-depth)
--   2. SELECT: select_{table} (conditional by rls_mode, uses get_allowed_projects())
--   3. INSERT: insert_{table} (own-project-only, uses get_current_project())
--   4. UPDATE: update_{table} (own-project-only, uses get_current_project())
--   5. DELETE: delete_{table} (own-project-only, uses get_current_project())
--
-- Key Patterns:
--   - Subquery pattern: (SELECT get_allowed_projects()) for single evaluation per query
--   - FORCE ROW LEVEL SECURITY: Applies to table owners (superusers) too
--   - Conditional enforcement: Check get_rls_mode() before applying restrictions
--   - Write isolation absolute: Even super users cannot write to other projects

SET lock_timeout = '5s';

-- ============================================================================
-- DEPENDENCY VALIDATION
-- ============================================================================

-- Verify Story 11.3.1 functions exist (AC1)
DO $$
BEGIN
    -- Check set_project_context exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'set_project_context'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: set_project_context function does not exist. Please run Story 11.3.1 migration first.';
    END IF;

    -- Check get_allowed_projects exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_allowed_projects'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_allowed_projects function does not exist. Please run Story 11.3.1 migration first.';
    END IF;

    -- Check get_rls_mode exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_rls_mode'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_rls_mode function does not exist. Please run Story 11.3.1 migration first.';
    END IF;

    -- Check get_current_project exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_current_project'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_current_project function does not exist. Please run Story 11.3.1 migration first.';
    END IF;
END $$;

-- Verify project_id columns exist on core tables (AC1)
DO $$
BEGIN
    -- Check l2_insights has project_id column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'l2_insights' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: l2_insights.project_id column does not exist. Please run Migration 027 first.';
    END IF;

    -- Check nodes has project_id column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'nodes' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: nodes.project_id column does not exist. Please run Migration 027 first.';
    END IF;

    -- Check edges has project_id column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'edges' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: edges.project_id column does not exist. Please run Migration 027 first.';
    END IF;
END $$;

-- ============================================================================
-- L2_INSIGHTS POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on l2_insights (AC1)
-- FORCE applies to table owners (superusers) too - critical for security
ALTER TABLE l2_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE l2_insights FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id (AC2)
-- RESTRICTIVE policies evaluate BEFORE permissive policies - defense-in-depth
-- This ensures rows with NULL project_id are NEVER visible (fail-safe)
CREATE POLICY require_project_id ON l2_insights
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON l2_insights IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode (AC3, AC4)
-- Uses subquery pattern for single evaluation per query (14x performance)
CREATE POLICY select_l2_insights ON l2_insights
FOR SELECT
USING (
    CASE (SELECT get_rls_mode())
        WHEN 'pending' THEN TRUE  -- Legacy behavior - no enforcement
        WHEN 'shadow' THEN TRUE   -- Audit-only mode - shadow triggers log violations
        WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
        WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
        ELSE TRUE  -- Fail-safe: allow if mode unknown
    END
);

COMMENT ON POLICY select_l2_insights ON l2_insights IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation. pending/shadow=allow all, enforcing/complete=use get_allowed_projects().';

-- Policy 3: INSERT - Own-project-only (AC6, AC7)
-- WITH CHECK validates new values being inserted
-- Even super users cannot insert into other projects
CREATE POLICY insert_l2_insights ON l2_insights
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_l2_insights ON l2_insights IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute. Even super users cannot write to other projects.';

-- Policy 4: UPDATE - Own-project-only (AC6, AC7)
-- USING filters existing rows, WITH CHECK validates new values
CREATE POLICY update_l2_insights ON l2_insights
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_l2_insights ON l2_insights IS
    'UPDATE policy: Own-project-only write access. USING filters existing rows, WITH CHECK validates new values. Even super users cannot update other projects.';

-- Policy 5: DELETE - Own-project-only (AC6, AC7)
CREATE POLICY delete_l2_insights ON l2_insights
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_l2_insights ON l2_insights IS
    'DELETE policy: Own-project-only write access. Even super users cannot delete from other projects.';

-- ============================================================================
-- NODES POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on nodes (AC1)
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id (AC2)
CREATE POLICY require_project_id ON nodes
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON nodes IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode (AC3, AC4)
CREATE POLICY select_nodes ON nodes
FOR SELECT
USING (
    CASE (SELECT get_rls_mode())
        WHEN 'pending' THEN TRUE
        WHEN 'shadow' THEN TRUE
        WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
        WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
        ELSE TRUE
    END
);

COMMENT ON POLICY select_nodes ON nodes IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation. pending/shadow=allow all, enforcing/complete=use get_allowed_projects().';

-- Policy 3: INSERT - Own-project-only (AC6, AC7)
CREATE POLICY insert_nodes ON nodes
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_nodes ON nodes IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- Policy 4: UPDATE - Own-project-only (AC6, AC7)
CREATE POLICY update_nodes ON nodes
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_nodes ON nodes IS
    'UPDATE policy: Own-project-only write access. USING filters existing rows, WITH CHECK validates new values.';

-- Policy 5: DELETE - Own-project-only (AC6, AC7)
CREATE POLICY delete_nodes ON nodes
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_nodes ON nodes IS
    'DELETE policy: Own-project-only write access.';

-- ============================================================================
-- EDGES POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on edges (AC1)
ALTER TABLE edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE edges FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id (AC2)
CREATE POLICY require_project_id ON edges
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON edges IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode (AC3, AC4)
CREATE POLICY select_edges ON edges
FOR SELECT
USING (
    CASE (SELECT get_rls_mode())
        WHEN 'pending' THEN TRUE
        WHEN 'shadow' THEN TRUE
        WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
        WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
        ELSE TRUE
    END
);

COMMENT ON POLICY select_edges ON edges IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation. pending/shadow=allow all, enforcing/complete=use get_allowed_projects().';

-- Policy 3: INSERT - Own-project-only (AC6, AC7)
CREATE POLICY insert_edges ON edges
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_edges ON edges IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- Policy 4: UPDATE - Own-project-only (AC6, AC7)
CREATE POLICY update_edges ON edges
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_edges ON edges IS
    'UPDATE policy: Own-project-only write access. USING filters existing rows, WITH CHECK validates new values.';

-- Policy 5: DELETE - Own-project-only (AC6, AC7)
CREATE POLICY delete_edges ON edges
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_edges ON edges IS
    'DELETE policy: Own-project-only write access.';

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify RLS is enabled on all core tables (should return 3 rows)
-- SELECT tablename, rowsecurity AS rls_enabled,forcerowsecurity AS force_rls
-- FROM pg_tables WHERE schemaname='public' AND tablename IN ('l2_insights', 'nodes', 'edges');

-- Verify all policies exist (should return 15 policies - 5 per table)
-- SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
-- FROM pg_policies WHERE schemaname='public' AND tablename IN ('l2_insights', 'nodes', 'edges')
-- ORDER BY tablename, policyname;

-- Verify RESTRICTIVE policies exist (should return 3 rows)
-- SELECT tablename, policyname
-- FROM pg_policies WHERE schemaname='public' AND permissive = false
-- AND tablename IN ('l2_insights', 'nodes', 'edges');

RESET lock_timeout;
