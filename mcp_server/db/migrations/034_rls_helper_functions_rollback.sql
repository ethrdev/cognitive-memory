-- Rollback Migration 034: RLS Helper Functions
-- Story 11.3.1: RLS Helper Functions
--
-- Purpose: Rollback RLS helper functions created in migration 034
-- Risk: LOW - Drops functions only, no data changes
-- Idempotent: Uses DROP FUNCTION IF EXISTS

SET lock_timeout = '5s';

-- ============================================================================
-- DROP RLS HELPER FUNCTIONS (in dependency order)
-- ============================================================================

-- Drop IMMUTABLE wrapper functions first (no dependencies)
DROP FUNCTION IF EXISTS get_current_project() CASCADE;
DROP FUNCTION IF EXISTS get_rls_mode() CASCADE;
DROP FUNCTION IF EXISTS get_access_level() CASCADE;
DROP FUNCTION IF EXISTS get_allowed_projects() CASCADE;

-- Drop main context-setting function last
DROP FUNCTION IF EXISTS set_project_context(VARCHAR(50)) CASCADE;

-- ============================================================================
-- VERIFY CLEANUP
-- ============================================================================

-- Verify all functions are dropped
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'set_project_context'
    ) THEN
        RAISE WARNING 'set_project_context function still exists after rollback';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_current_project'
    ) THEN
        RAISE WARNING 'get_current_project function still exists after rollback';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_rls_mode'
    ) THEN
        RAISE WARNING 'get_rls_mode function still exists after rollback';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_access_level'
    ) THEN
        RAISE WARNING 'get_access_level function still exists after rollback';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_allowed_projects'
    ) THEN
        RAISE WARNING 'get_allowed_projects function still exists after rollback';
    END IF;
END $$;

RESET lock_timeout;
