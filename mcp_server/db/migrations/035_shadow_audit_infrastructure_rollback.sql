-- Rollback Migration 035: Shadow Audit Infrastructure
-- Story 11.3.2: Shadow Audit Infrastructure
--
-- Purpose: Rollback shadow audit infrastructure created in migration 035
-- Risk: LOW - Drops table, triggers, and functions only, no data changes
-- Idempotent: Uses DROP IF EXISTS and CASCADE

SET lock_timeout = '5s';

-- ============================================================================
-- DROP TRIGGERS (Task 4, AC3)
-- ============================================================================

-- Drop triggers from core tables
DROP TRIGGER IF EXISTS tr_l2_insights_shadow_audit ON l2_insights;
DROP TRIGGER IF EXISTS tr_nodes_shadow_audit ON nodes;
DROP TRIGGER IF EXISTS tr_edges_shadow_audit ON edges;

-- ============================================================================
-- DROP FUNCTIONS (in dependency order)
-- ============================================================================

-- Drop trigger function first (depends on rls_check_access)
DROP FUNCTION IF EXISTS shadow_audit_trigger() CASCADE;

-- Drop access check function
DROP FUNCTION IF EXISTS rls_check_access(VARCHAR(50), VARCHAR(50), VARCHAR(10)) CASCADE;

-- ============================================================================
-- DROP TABLE AND INDEXES (AC1)
-- ============================================================================

-- Drop rls_audit_log table (indexes are dropped automatically with CASCADE)
DROP TABLE IF EXISTS rls_audit_log CASCADE;

-- ============================================================================
-- VERIFY CLEANUP
-- ============================================================================

-- Verify all objects are dropped
DO $$
BEGIN
    -- Verify table is dropped
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'rls_audit_log'
    ) THEN
        RAISE WARNING 'rls_audit_log table still exists after rollback';
    END IF;

    -- Verify functions are dropped
    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'rls_check_access'
    ) THEN
        RAISE WARNING 'rls_check_access function still exists after rollback';
    END IF;

    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'shadow_audit_trigger'
    ) THEN
        RAISE WARNING 'shadow_audit_trigger function still exists after rollback';
    END IF;

    -- Verify triggers are dropped
    IF EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'tr_l2_insights_shadow_audit'
    ) THEN
        RAISE WARNING 'tr_l2_insights_shadow_audit trigger still exists after rollback';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'tr_nodes_shadow_audit'
    ) THEN
        RAISE WARNING 'tr_nodes_shadow_audit trigger still exists after rollback';
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'tr_edges_shadow_audit'
    ) THEN
        RAISE WARNING 'tr_edges_shadow_audit trigger still exists after rollback';
    END IF;

    RAISE NOTICE 'Shadow audit infrastructure rolled back successfully';
END $$;

RESET lock_timeout;
