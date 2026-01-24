-- Migration 039: RLS Policies for l2_insight_history Table
-- Story 11.6.3: Insight Read Operations - SECURITY FIX
--
-- Purpose: Create Row-Level Security policies on l2_insight_history table
--          CRITICAL: This table was missing from Migrations 036 and 037
-- Dependencies: Migration 034 (RLS Helper Functions), Migration 027 (project_id column)
-- Risk: HIGH - Closes security gap in history query isolation
-- Rollback: 039_rls_policies_insight_history_rollback.sql
--
-- Policy Structure:
--   1. RESTRICTIVE: require_project_id (blocks NULL project_id)
--   2. SELECT: select_l2_insight_history (conditional by rls_mode)
--   3. INSERT: insert_l2_insight_history (own-project-only)

SET lock_timeout = '5s';

-- ============================================================================
-- DEPENDENCY VALIDATION
-- ============================================================================

-- Verify Story 11.3.1 functions exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'set_project_context'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: set_project_context function does not exist.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_allowed_projects'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_allowed_projects function does not exist.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_rls_mode'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_rls_mode function does not exist.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_current_project'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_current_project function does not exist.';
    END IF;
END $$;

-- Verify project_id column exists on l2_insight_history
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'l2_insight_history' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: l2_insight_history.project_id column does not exist. Please run Migration 027 first.';
    END IF;
END $$;

-- ============================================================================
-- L2_INSIGHT_HISTORY POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on l2_insight_history
ALTER TABLE l2_insight_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE l2_insight_history FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id
CREATE POLICY require_project_id ON l2_insight_history
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON l2_insight_history IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode
CREATE POLICY select_l2_insight_history ON l2_insight_history
FOR SELECT
USING (
    CASE (SELECT get_rls_mode())
        WHEN 'pending' THEN TRUE  -- Legacy behavior
        WHEN 'shadow' THEN TRUE   -- Audit-only mode
        WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
        WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
        ELSE TRUE  -- Fail-safe
    END
);

COMMENT ON POLICY select_l2_insight_history ON l2_insight_history IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation.';

-- Policy 3: INSERT - Own-project-only
CREATE POLICY insert_l2_insight_history ON l2_insight_history
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_l2_insight_history ON l2_insight_history IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify RLS is enabled (should return 1 row)
-- SELECT tablename, rowsecurity AS rls_enabled, forcerowsecurity AS force_rls
-- FROM pg_tables WHERE schemaname='public' AND tablename = 'l2_insight_history';

-- Verify all policies exist (should return 3 policies)
-- SELECT schemaname, tablename, policyname, permissive
-- FROM pg_policies WHERE schemaname='public' AND tablename = 'l2_insight_history'
-- ORDER BY policyname;

RESET lock_timeout;
