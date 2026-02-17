-- Migration 045: Activate Shadow Mode for all projects
-- Story 11.7: Cross-Project Contamination Fix
-- Purpose: Advance all projects from 'pending' to 'shadow' migration phase
--          Shadow mode enables audit logging without blocking operations.
--          This is a prerequisite for 'enforcing' mode which will block
--          cross-project access violations.
--
-- Risk: LOW - Shadow mode only adds audit logging, does NOT block any operations
-- Rollback: 045_activate_shadow_mode_rollback.sql

-- ─────────────────────────────────────────────────────────────────
-- Pre-flight checks
-- ─────────────────────────────────────────────────────────────────
DO $$
BEGIN
    -- Verify rls_migration_status table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'rls_migration_status'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: rls_migration_status table does not exist. Run migration 032 first.';
    END IF;

    -- Verify shadow_audit_trigger function exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'shadow_audit_trigger'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: shadow_audit_trigger function does not exist. Run migration 035 first.';
    END IF;

    -- Verify all projects are currently in 'pending' (safe to advance)
    IF EXISTS (
        SELECT 1 FROM rls_migration_status
        WHERE migration_phase NOT IN ('pending', 'shadow')
    ) THEN
        RAISE EXCEPTION 'Safety check failed: Some projects are not in pending/shadow phase. Manual review required.';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────
-- Advance all projects from 'pending' to 'shadow'
-- ─────────────────────────────────────────────────────────────────
UPDATE rls_migration_status
SET migration_phase = 'shadow',
    updated_at = NOW()
WHERE migration_phase = 'pending';

-- ─────────────────────────────────────────────────────────────────
-- Verification
-- ─────────────────────────────────────────────────────────────────
DO $$
DECLARE
    pending_count INTEGER;
    shadow_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO pending_count
    FROM rls_migration_status
    WHERE migration_phase = 'pending';

    SELECT COUNT(*) INTO shadow_count
    FROM rls_migration_status
    WHERE migration_phase = 'shadow';

    IF pending_count > 0 THEN
        RAISE EXCEPTION 'Verification failed: % projects still in pending phase', pending_count;
    END IF;

    RAISE NOTICE 'Migration 045 complete: % projects now in shadow mode', shadow_count;
END $$;
