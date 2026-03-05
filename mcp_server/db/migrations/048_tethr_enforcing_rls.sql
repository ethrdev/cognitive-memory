-- Migration 048: Advance tethr RLS from pending to enforcing
--
-- Purpose: Enable DB-level read isolation for tethr project.
--          In 'enforcing' mode, SELECT policy filters by allowed_projects
--          ({tethr}) even if application-level WHERE clause is missing.
--          Write isolation was already enforced via INSERT policy.
-- Context: tethr was registered in 048 with 'pending' status (after migration 045).
--          io and aa are already in 'enforcing' — this is the proven path.
-- Risk: LOW — tethr is a new project, no existing workflows to break.
--       If set_project_context is not called before a query, SELECT returns 0 rows
--       (not an error). INSERT remains enforced via WITH CHECK policy.
-- Dependencies: Migration 047 (tethr in project_registry + rls_migration_status)

SET lock_timeout = '5s';

-- Pre-flight check
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM rls_migration_status
        WHERE project_id = 'tethr' AND migration_phase = 'pending'
    ) THEN
        RAISE EXCEPTION 'tethr is not in pending phase — check current state before running';
    END IF;
END $$;

-- Advance tethr from pending to enforcing
UPDATE rls_migration_status
SET migration_phase = 'enforcing',
    updated_at = NOW()
WHERE project_id = 'tethr';

-- Verification
DO $$
DECLARE
    v_phase TEXT;
BEGIN
    SELECT migration_phase::TEXT INTO v_phase
    FROM rls_migration_status
    WHERE project_id = 'tethr';

    IF v_phase != 'enforcing' THEN
        RAISE EXCEPTION 'Verification failed: tethr phase is %, expected enforcing', v_phase;
    END IF;

    RAISE NOTICE 'Migration 048 complete: tethr RLS advanced to enforcing';
END $$;

RESET lock_timeout;
