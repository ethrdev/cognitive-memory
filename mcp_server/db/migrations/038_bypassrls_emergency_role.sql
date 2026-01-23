-- Migration 038: BYPASSRLS Emergency Role
-- Story 11.3.5: BYPASSRLS Emergency Role
--
-- Purpose: Create rls_emergency_bypass role for debugging RLS issues
--          without disabling RLS system-wide (which has blocking risks)
-- Dependencies: Stories 11.3.3 and 11.3.4 (RLS policies must exist)
-- Risk: LOW - New role only, no data changes
-- Rollback: 038_bypassrls_emergency_role_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- DEPENDENCY VALIDATION
-- ============================================================================

-- Verify RLS policies exist on at least one table
DO $$
BEGIN
    -- Check that at least one RLS-enabled table exists
    -- Accepts tables from Stories 11.3.3 (Core), 11.3.4 (Support), or any other story
    IF NOT EXISTS (
        SELECT 1 FROM pg_tables
        WHERE schemaname = 'public' AND rowsecurity = true
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: No tables with RLS enabled found. Please ensure Stories 11.3.3 or 11.3.4 have been applied first.';
    END IF;
END $$;

-- Verify RLS helper functions exist (Story 11.3.1)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_current_project'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_current_project function does not exist. Please run Story 11.3.1 first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_rls_mode'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_rls_mode function does not exist. Please run Story 11.3.1 first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_allowed_projects'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_allowed_projects function does not exist. Please run Story 11.3.1 first.';
    END IF;
END $$;

-- ============================================================================
-- EMERGENCY BYPASS ROLE CREATION
-- ============================================================================

-- rls_emergency_bypass - Emergency role for debugging RLS issues
-- AC1: Role created with BYPASSRLS and NOLOGIN attributes
-- Security:
--   - NOLOGIN: Cannot be used for direct connections (must use SET ROLE)
--   - BYPASSRLS: Ignores all RLS policies when active
--   - No password: Prevents password-based bypass (audit risk)
--   - No default grants: Only superusers can SET ROLE (PostgreSQL default behavior)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'rls_emergency_bypass') THEN
        CREATE ROLE rls_emergency_bypass
            WITH NOLOGIN BYPASSRLS;

        COMMENT ON ROLE rls_emergency_bypass IS
            'Emergency role for debugging RLS issues. Use SET ROLE to activate. Document all uses with ticket numbers. NEVER use in production code.';
    END IF;
END $$;

-- ============================================================================
-- SECURITY CONSTRAINTS (PostgreSQL Default Behavior)
-- ============================================================================

-- Only superusers can SET ROLE to roles they are not a member of
-- We intentionally do NOT grant this role to any users
-- This is a security feature - only superusers can activate the bypass

-- If manual activation is needed for a specific user (emergency only):
--   GRANT rls_emergency_bypass TO specific_user;
-- Then that user can: SET ROLE rls_emergency_bypass;

-- ============================================================================
-- USAGE DOCUMENTATION (Comments)
-- ============================================================================

-- AC2: Role Activation
-- Usage: SET ROLE rls_emergency_bypass;
-- Effect: Subsequent queries bypass all RLS policies
-- Audit: Activation is logged in PostgreSQL logs (if log_statement = 'all')
--
-- Example:
--   BEGIN;
--   SET ROLE rls_emergency_bypass;  -- Activates bypass
--   SELECT * FROM l2_insights;      -- Shows ALL projects
--   RESET ROLE;                     -- Deactivates, RLS enforced again
--   COMMIT;

-- AC3: Role Deactivation
-- Usage: RESET ROLE;
-- Effect: RLS policies are enforced again based on app.current_project
--
-- Example:
--   SET ROLE rls_emergency_bypass;
--   -- Debug queries here...
--   RESET ROLE;  -- Normal RLS behavior resumes

-- AC4: Security Constraints
-- - Non-superusers cannot SET ROLE without being explicitly granted the role
-- - Permission denied is logged in PostgreSQL logs
-- - Only superusers can activate by default (security feature)

-- AC6: Lock Timeout Protection
-- For emergency RLS disable (LAST RESORT, prefer BYPASSRLS role):
--   SET lock_timeout = '5s';  -- Prevents cascade blocking
--   ALTER TABLE l2_insights DISABLE ROW LEVEL SECURITY;
--   RESET lock_timeout;
--
-- WARNING: ALTER TABLE ... DISABLE has blocking risks
--          Prefer SET ROLE rls_emergency_bypass over disabling RLS system-wide

-- AC7: Audit Requirements
-- When using this role for debugging, document:
--   - Incident ticket number
--   - Start/end time of bypass usage
--   - All queries executed during bypass
--   - Use log_statement = 'all' to capture activity

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify role was created correctly
DO $$
DECLARE
    v_role RECORD;
    v_comment TEXT;
BEGIN
    SELECT rolcanlogin, rolsuper, rolbypassrls
    INTO v_role
    FROM pg_roles
    WHERE rolname = 'rls_emergency_bypass';

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Role rls_emergency_bypass was not created';
    END IF;

    IF v_role.rolcanlogin = true THEN
        RAISE EXCEPTION 'Role rls_emergency_bypass should have NOLOGIN';
    END IF;

    IF v_role.rolbypassrls = false THEN
        RAISE EXCEPTION 'Role rls_emergency_bypass should have BYPASSRLS';
    END IF;

    -- Verify comment exists
    SELECT description
    INTO v_comment
    FROM pg_shdescription
    WHERE objoid = (SELECT oid FROM pg_roles WHERE rolname = 'rls_emergency_bypass');

    IF v_comment IS NULL THEN
        RAISE EXCEPTION 'Role rls_emergency_bypass should have a descriptive comment';
    END IF;

    RAISE NOTICE 'Role rls_emergency_bypass verified: NOLOGIN=%, BYPASSRLS=%, Comment=%',
        v_role.rolcanlogin, v_role.rolbypassrls, v_comment;
END $$;

RESET lock_timeout;
