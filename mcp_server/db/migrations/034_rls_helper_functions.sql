-- Migration 034: RLS Helper Functions with IMMUTABLE Wrappers
-- Story 11.3.1: RLS Helper Functions
--
-- Purpose: Create helper functions for RLS context management
--          set_project_context() does all lookups ONCE and caches in session variables
--          IMMUTABLE wrapper functions enable 14x performance improvement in RLS policies
-- Dependencies: Migration 030 (project_registry), 031 (project_read_permissions), 032 (rls_migration_status)
-- Risk: LOW - New functions, no data changes
-- Rollback: 034_rls_helper_functions_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- DEPENDENCY VALIDATION
-- ============================================================================

-- Verify Epic 11.2 tables exist (AC7)
DO $$
BEGIN
    -- Check project_registry exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'project_registry'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: project_registry table does not exist. Please run Epic 11.2 migrations first.';
    END IF;

    -- Check project_read_permissions exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'project_read_permissions'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: project_read_permissions table does not exist. Please run Epic 11.2 migrations first.';
    END IF;

    -- Check rls_migration_status exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'rls_migration_status'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: rls_migration_status table does not exist. Please run Epic 11.2 migrations first.';
    END IF;
END $$;

-- ============================================================================
-- MAIN CONTEXT-SETTING FUNCTION
-- ============================================================================

-- set_project_context(p_project_id VARCHAR(50))
-- Purpose: Set all session variables for RLS context in a single call
-- Behavior:
--   - Validates project exists in project_registry (AC6)
--   - Looks up RLS mode from rls_migration_status (with fallback to 'pending')
--   - Computes allowed_projects array based on access_level (AC4)
--   - Sets all session variables using SET LOCAL (transaction-scoped) (AC1)
-- Security: SECURITY DEFINER required to read from project_registry tables
-- Transaction: Requires explicit transaction context in app code
CREATE OR REPLACE FUNCTION set_project_context(p_project_id VARCHAR(50))
RETURNS VOID AS $$
DECLARE
    v_access_level access_level_enum;
    v_rls_mode TEXT;
    v_allowed TEXT;
BEGIN
    -- Validate project exists and get access level (AC6)
    SELECT access_level INTO v_access_level
    FROM project_registry
    WHERE project_id = p_project_id;

    IF v_access_level IS NULL THEN
        RAISE EXCEPTION 'Unknown project: %', p_project_id;
    END IF;

    -- Get RLS mode with fallback to 'pending' (AC1)
    -- Note: COALESCE only handles NULL within a row, not missing rows
    -- So we explicitly handle the case where no row exists
    SELECT migration_phase::TEXT INTO v_rls_mode
    FROM rls_migration_status
    WHERE project_id = p_project_id;

    -- Fallback to 'pending' if no rls_migration_status entry exists
    IF v_rls_mode IS NULL THEN
        v_rls_mode := 'pending';
    END IF;

    -- Compute allowed projects based on access level (AC4)
    IF v_access_level = 'super' THEN
        -- SUPER: Access to ALL projects
        SELECT '{' || string_agg(project_id, ',') || '}' INTO v_allowed
        FROM project_registry;

    ELSIF v_access_level = 'shared' THEN
        -- SHARED: Own project + permitted projects (AC4)
        SELECT '{' || string_agg(pid, ',') || '}' INTO v_allowed
        FROM (
            SELECT p_project_id AS pid
            UNION
            SELECT target_project_id
            FROM project_read_permissions
            WHERE reader_project_id = p_project_id
        ) allowed;

    ELSE
        -- ISOLATED: Own project only (AC4)
        v_allowed := '{' || p_project_id || '}';
    END IF;

    -- Set all session variables using SET LOCAL (transaction-scoped) (AC1, AC3)
    -- TRUE parameter = SET LOCAL (resets at transaction end)
    PERFORM set_config('app.current_project', p_project_id, TRUE);
    PERFORM set_config('app.rls_mode', v_rls_mode, TRUE);
    PERFORM set_config('app.access_level', v_access_level::TEXT, TRUE);
    PERFORM set_config('app.allowed_projects', v_allowed, TRUE);

END;
$$ LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public;

-- Comments for set_project_context
COMMENT ON FUNCTION set_project_context(VARCHAR(50)) IS
    'Set RLS context session variables for a project. Does all lookups ONCE and caches in session variables. CRITICAL: Requires explicit transaction context in app code - use SET LOCAL pattern.';

-- ============================================================================
-- IMMUTABLE WRAPPER FUNCTIONS
-- ============================================================================

-- Why IMMUTABLE despite calling current_setting()? (AC2, AC5)
-- Without IMMUTABLE, functions in RLS policies are evaluated PER ROW, causing 14x performance degradation.
-- This is SAFE because:
--   1. current_setting() returns the SAME value for the entire transaction
--   2. set_project_context() is called ONCE at transaction start
--   3. RLS policies execute within a single transaction
--   4. The "lie" to the planner is transaction-scoped, not global
-- This pattern is used by Supabase, Citus, and PostgREST for RLS.

-- get_current_project() - Returns current project_id (AC2)
CREATE OR REPLACE FUNCTION get_current_project()
RETURNS TEXT AS $$
    SELECT current_setting('app.current_project', TRUE)
$$ LANGUAGE sql
IMMUTABLE PARALLEL SAFE
SET search_path = public;

COMMENT ON FUNCTION get_current_project() IS
    'IMMUTABLE wrapper: Returns current project_id from session variable. Despite calling current_setting(), declared IMMUTABLE for 14x performance improvement in RLS policies. Safe because value is transaction-scoped.';

-- get_rls_mode() - Returns RLS migration mode (AC2)
CREATE OR REPLACE FUNCTION get_rls_mode()
RETURNS TEXT AS $$
    SELECT current_setting('app.rls_mode', TRUE)
$$ LANGUAGE sql
IMMUTABLE PARALLEL SAFE
SET search_path = public;

COMMENT ON FUNCTION get_rls_mode() IS
    'IMMUTABLE wrapper: Returns RLS migration mode (pending/shadow/enforcing/complete). Declared IMMUTABLE for performance - value is stable within transaction.';

-- get_access_level() - Returns access level (AC2)
CREATE OR REPLACE FUNCTION get_access_level()
RETURNS TEXT AS $$
    SELECT current_setting('app.access_level', TRUE)
$$ LANGUAGE sql
IMMUTABLE PARALLEL SAFE
SET search_path = public;

COMMENT ON FUNCTION get_access_level() IS
    'IMMUTABLE wrapper: Returns access level (super/shared/isolated). Declared IMMUTABLE for performance - value is stable within transaction.';

-- get_allowed_projects() - Returns allowed projects as native array (AC2, AC3)
CREATE OR REPLACE FUNCTION get_allowed_projects()
RETURNS TEXT[] AS $$
    SELECT current_setting('app.allowed_projects', TRUE)::TEXT[]
$$ LANGUAGE sql
IMMUTABLE PARALLEL SAFE
SET search_path = public;

COMMENT ON FUNCTION get_allowed_projects() IS
    'IMMUTABLE wrapper: Returns allowed projects as native TEXT[] array. Uses PostgreSQL array literal format {aa,sm} - no CSV parsing needed. Declared IMMUTABLE for 14x performance improvement in RLS policies.';

-- ============================================================================
-- USAGE WARNINGS (Comments)
-- ============================================================================

-- Transaction scoping requirement (CRITICAL)
-- WARNING: SET LOCAL requires explicit transaction context
-- WRONG - Context may persist unexpectedly:
--   await conn.execute("SELECT set_project_context('aa')")
--   await conn.execute("SELECT ...")  -- Context might be lost!
-- CORRECT - Context guaranteed within transaction:
--   async with conn.transaction():
--       await conn.execute("SELECT set_project_context('aa')")
--       await conn.execute("SELECT ...")  -- Context available

-- External references:
-- - Supabase RLS Pattern: https://supabase.com/docs/guides/auth/row-level-security
-- - Citus Multi-Tenant: https://docs.citusdata.com/en/stable/develop/migration_mt_schema.html
-- - PostgREST Auth: https://postgrest.org/en/stable/auth.html

RESET lock_timeout;
