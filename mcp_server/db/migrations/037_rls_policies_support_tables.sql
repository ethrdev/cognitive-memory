-- Migration 037: RLS Policies for Support Tables
-- Story 11.3.4: RLS Policies for Support Tables
--
-- Purpose: Create Row-Level Security policies on support tables (working_memory, episode_memory, l0_raw,
--          ground_truth, smf_proposals, stale_memory) with conditional enforcement based on migration phase
-- Dependencies: Migration 034 (RLS Helper Functions), Migration 027 (project_id columns)
-- Risk: MEDIUM - Enables RLS with conditional enforcement (shadow mode first)
-- Rollback: 037_rls_policies_support_tables_rollback.sql
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
--
-- Support Tables Covered:
--   - working_memory: Transient context must be project-scoped
--   - episode_memory: Reinforcement learning history must not leak between projects
--   - l0_raw: Raw dialogue history is sensitive data
--   - ground_truth: Evaluation data must be project-specific
--   - smf_proposals: Consent workflow must respect project boundaries
--   - stale_memory: Archived items must remain isolated

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
        RAISE EXCEPTION 'Dependency check failed: set_project_context function does not exist. Please run Story 11.3.1 migration first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_allowed_projects'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_allowed_projects function does not exist. Please run Story 11.3.1 migration first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_rls_mode'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_rls_mode function does not exist. Please run Story 11.3.1 migration first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_current_project'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_current_project function does not exist. Please run Story 11.3.1 migration first.';
    END IF;
END $$;

-- Verify project_id columns exist on all support tables
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'working_memory' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: working_memory.project_id column does not exist. Please run Migration 027 first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'episode_memory' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: episode_memory.project_id column does not exist. Please run Migration 027 first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'l0_raw' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: l0_raw.project_id column does not exist. Please run Migration 027 first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'ground_truth' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: ground_truth.project_id column does not exist. Please run Migration 027 first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'smf_proposals' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: smf_proposals.project_id column does not exist. Please run Migration 027 first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'stale_memory' AND column_name = 'project_id'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: stale_memory.project_id column does not exist. Please run Migration 027 first.';
    END IF;
END $$;

-- ============================================================================
-- WORKING_MEMORY POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on working_memory
ALTER TABLE working_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE working_memory FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id
CREATE POLICY require_project_id ON working_memory
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON working_memory IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode
CREATE POLICY select_working_memory ON working_memory
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

COMMENT ON POLICY select_working_memory ON working_memory IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation. pending/shadow=allow all, enforcing/complete=use get_allowed_projects().';

-- Policy 3: INSERT - Own-project-only
CREATE POLICY insert_working_memory ON working_memory
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_working_memory ON working_memory IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- Policy 4: UPDATE - Own-project-only
CREATE POLICY update_working_memory ON working_memory
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_working_memory ON working_memory IS
    'UPDATE policy: Own-project-only write access. USING filters existing rows, WITH CHECK validates new values.';

-- Policy 5: DELETE - Own-project-only
CREATE POLICY delete_working_memory ON working_memory
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_working_memory ON working_memory IS
    'DELETE policy: Own-project-only write access.';

-- ============================================================================
-- EPISODE_MEMORY POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on episode_memory
ALTER TABLE episode_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE episode_memory FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id
CREATE POLICY require_project_id ON episode_memory
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON episode_memory IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode
CREATE POLICY select_episode_memory ON episode_memory
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

COMMENT ON POLICY select_episode_memory ON episode_memory IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation.';

-- Policy 3: INSERT - Own-project-only
CREATE POLICY insert_episode_memory ON episode_memory
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_episode_memory ON episode_memory IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- Policy 4: UPDATE - Own-project-only
CREATE POLICY update_episode_memory ON episode_memory
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_episode_memory ON episode_memory IS
    'UPDATE policy: Own-project-only write access.';

-- Policy 5: DELETE - Own-project-only
CREATE POLICY delete_episode_memory ON episode_memory
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_episode_memory ON episode_memory IS
    'DELETE policy: Own-project-only write access.';

-- ============================================================================
-- L0_RAW POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on l0_raw
ALTER TABLE l0_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE l0_raw FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id
CREATE POLICY require_project_id ON l0_raw
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON l0_raw IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode
CREATE POLICY select_l0_raw ON l0_raw
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

COMMENT ON POLICY select_l0_raw ON l0_raw IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation.';

-- Policy 3: INSERT - Own-project-only
CREATE POLICY insert_l0_raw ON l0_raw
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_l0_raw ON l0_raw IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- Policy 4: UPDATE - Own-project-only
CREATE POLICY update_l0_raw ON l0_raw
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_l0_raw ON l0_raw IS
    'UPDATE policy: Own-project-only write access.';

-- Policy 5: DELETE - Own-project-only
CREATE POLICY delete_l0_raw ON l0_raw
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_l0_raw ON l0_raw IS
    'DELETE policy: Own-project-only write access.';

-- ============================================================================
-- GROUND_TRUTH POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on ground_truth
ALTER TABLE ground_truth ENABLE ROW LEVEL SECURITY;
ALTER TABLE ground_truth FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id
CREATE POLICY require_project_id ON ground_truth
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON ground_truth IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode
CREATE POLICY select_ground_truth ON ground_truth
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

COMMENT ON POLICY select_ground_truth ON ground_truth IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation.';

-- Policy 3: INSERT - Own-project-only
CREATE POLICY insert_ground_truth ON ground_truth
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_ground_truth ON ground_truth IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- Policy 4: UPDATE - Own-project-only
CREATE POLICY update_ground_truth ON ground_truth
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_ground_truth ON ground_truth IS
    'UPDATE policy: Own-project-only write access.';

-- Policy 5: DELETE - Own-project-only
CREATE POLICY delete_ground_truth ON ground_truth
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_ground_truth ON ground_truth IS
    'DELETE policy: Own-project-only write access.';

-- ============================================================================
-- SMF_PROPOSALS POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on smf_proposals
ALTER TABLE smf_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE smf_proposals FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id
CREATE POLICY require_project_id ON smf_proposals
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON smf_proposals IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode
CREATE POLICY select_smf_proposals ON smf_proposals
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

COMMENT ON POLICY select_smf_proposals ON smf_proposals IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation.';

-- Policy 3: INSERT - Own-project-only
CREATE POLICY insert_smf_proposals ON smf_proposals
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_smf_proposals ON smf_proposals IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- Policy 4: UPDATE - Own-project-only
CREATE POLICY update_smf_proposals ON smf_proposals
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_smf_proposals ON smf_proposals IS
    'UPDATE policy: Own-project-only write access.';

-- Policy 5: DELETE - Own-project-only
CREATE POLICY delete_smf_proposals ON smf_proposals
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_smf_proposals ON smf_proposals IS
    'DELETE policy: Own-project-only write access.';

-- ============================================================================
-- STALE_MEMORY POLICIES
-- ============================================================================

-- Enable FORCE ROW LEVEL SECURITY on stale_memory
ALTER TABLE stale_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE stale_memory FORCE ROW LEVEL SECURITY;

-- Policy 1: RESTRICTIVE - require_project_id
CREATE POLICY require_project_id ON stale_memory
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON stale_memory IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Evaluates BEFORE permissive policies for defense-in-depth.';

-- Policy 2: SELECT - Conditional enforcement by rls_mode
CREATE POLICY select_stale_memory ON stale_memory
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

COMMENT ON POLICY select_stale_memory ON stale_memory IS
    'SELECT policy: Conditional enforcement by rls_mode. Uses subquery pattern for single evaluation.';

-- Policy 3: INSERT - Own-project-only
CREATE POLICY insert_stale_memory ON stale_memory
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_stale_memory ON stale_memory IS
    'INSERT policy: Own-project-only write access. Applies to all modes - write isolation is absolute.';

-- Policy 4: UPDATE - Own-project-only
CREATE POLICY update_stale_memory ON stale_memory
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_stale_memory ON stale_memory IS
    'UPDATE policy: Own-project-only write access.';

-- Policy 5: DELETE - Own-project-only
CREATE POLICY delete_stale_memory ON stale_memory
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_stale_memory ON stale_memory IS
    'DELETE policy: Own-project-only write access.';

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify RLS is enabled on all support tables (should return 6 rows)
-- SELECT tablename, rowsecurity AS rls_enabled, forcerowsecurity AS force_rls
-- FROM pg_tables WHERE schemaname='public'
-- AND tablename IN ('working_memory', 'episode_memory', 'l0_raw', 'ground_truth', 'smf_proposals', 'stale_memory');

-- Verify all policies exist (should return 30 policies - 5 per table)
-- SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
-- FROM pg_policies WHERE schemaname='public'
-- AND tablename IN ('working_memory', 'episode_memory', 'l0_raw', 'ground_truth', 'smf_proposals', 'stale_memory')
-- ORDER BY tablename, policyname;

-- Verify RESTRICTIVE policies exist (should return 6 rows)
-- SELECT tablename, policyname
-- FROM pg_policies WHERE schemaname='public' AND permissive = false
-- AND tablename IN ('working_memory', 'episode_memory', 'l0_raw', 'ground_truth', 'smf_proposals', 'stale_memory');

RESET lock_timeout;
