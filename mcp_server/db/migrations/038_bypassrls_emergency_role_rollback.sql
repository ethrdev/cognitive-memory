-- Migration 038 Rollback: BYPASSRLS Emergency Role
-- Story 11.3.5: BYPASSRLS Emergency Role
--
-- Purpose: Rollback the emergency bypass role
-- Risk: LOW - Removes role only, no data changes
-- Idempotent: Uses IF EXISTS pattern

SET lock_timeout = '5s';

-- ============================================================================
-- REMOVE EMERGENCY BYPASS ROLE
-- ============================================================================

-- Drop rls_emergency_bypass role if exists
DROP ROLE IF EXISTS rls_emergency_bypass;

-- Note: Any comments on the role are automatically removed when the role is dropped

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify role was dropped
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'rls_emergency_bypass') THEN
        RAISE EXCEPTION 'Rollback failed: rls_emergency_bypass role still exists';
    END IF;

    RAISE NOTICE 'Rollback complete: rls_emergency_bypass role removed';
END $$;

RESET lock_timeout;
