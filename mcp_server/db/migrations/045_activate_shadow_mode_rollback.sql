-- Rollback Migration 045: Revert shadow mode to pending
-- Story 11.7: Cross-Project Contamination Fix
-- Purpose: Roll back all projects from 'shadow' to 'pending'

UPDATE rls_migration_status
SET migration_phase = 'pending',
    updated_at = NOW()
WHERE migration_phase = 'shadow';

DO $$
DECLARE
    shadow_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO shadow_count
    FROM rls_migration_status
    WHERE migration_phase = 'shadow';

    IF shadow_count > 0 THEN
        RAISE WARNING 'Rollback incomplete: % projects still in shadow phase', shadow_count;
    ELSE
        RAISE NOTICE 'Rollback 045 complete: all projects reverted to pending';
    END IF;
END $$;
