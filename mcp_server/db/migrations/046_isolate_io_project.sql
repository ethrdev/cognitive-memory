-- Migration 046: Change I/O project from 'super' to 'isolated'
-- Story 11.7: Cross-Project Contamination Fix
-- Purpose: I/O should only see its own data, not data from other projects.
--          Previously 'super' (sees everything), now 'isolated' (own data only).
--
-- Risk: LOW - Only affects I/O's read visibility. Write isolation unchanged.
-- Rollback: 046_isolate_io_project_rollback.sql

-- ─────────────────────────────────────────────────────────────────
-- Pre-flight check
-- ─────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM project_registry WHERE project_id = 'io'
    ) THEN
        RAISE EXCEPTION 'Project io not found in project_registry';
    END IF;
END $$;

-- ─────────────────────────────────────────────────────────────────
-- Change I/O from 'super' to 'isolated'
-- ─────────────────────────────────────────────────────────────────
UPDATE project_registry
SET access_level = 'isolated'
WHERE project_id = 'io';

-- ─────────────────────────────────────────────────────────────────
-- Verification
-- ─────────────────────────────────────────────────────────────────
DO $$
DECLARE
    v_level TEXT;
BEGIN
    SELECT access_level::TEXT INTO v_level
    FROM project_registry WHERE project_id = 'io';

    IF v_level != 'isolated' THEN
        RAISE EXCEPTION 'Verification failed: io access_level is %, expected isolated', v_level;
    END IF;

    RAISE NOTICE 'Migration 046 complete: io access_level changed to isolated';
END $$;
