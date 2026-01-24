-- Migration 039: Add project_id to l2_insight_history
-- Story 11.5.2: L2 Insight Write Operations
--
-- Purpose: Add project_id column to l2_insight_history table for complete namespace isolation
-- Dependencies: Migration 024 (l2_insight_history table), Migration 034 (set_project_context function)
-- Risk: LOW - Adding column with default value, adding index
-- Rollback: 039_add_project_id_to_insight_history_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- ADD project_id COLUMN
-- ============================================================================

-- Add project_id column to l2_insight_history
ALTER TABLE l2_insight_history
ADD COLUMN IF NOT EXISTS project_id TEXT NOT NULL DEFAULT 'io';

-- Add comment
COMMENT ON COLUMN l2_insight_history.project_id IS
    'Project identifier for namespace isolation. Added in Story 11.5.2.';

-- ============================================================================
-- ADD INDEX FOR PERFORMANCE
-- ============================================================================

-- Create index on project_id for efficient filtering
CREATE INDEX IF NOT EXISTS idx_insight_history_project_id
ON l2_insight_history(project_id);

COMMENT ON INDEX idx_insight_history_project_id IS
    'Index for project-scoped history queries. Added in Story 11.5.2.';

-- ============================================================================
-- MIGRATE EXISTING DATA
-- ============================================================================

-- Migrate existing history entries: infer project_id from the insight
UPDATE l2_insight_history h
SET project_id = i.project_id
FROM l2_insights i
WHERE h.insight_id = i.id
  AND h.project_id = 'io'  -- Only update defaults
  AND i.project_id != 'io';  -- Where insight has different project_id

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify all history entries have a project_id
DO $$
DECLARE
    null_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO null_count
    FROM l2_insight_history
    WHERE project_id IS NULL;

    IF null_count > 0 THEN
        RAISE EXCEPTION 'Migration verification failed: % history entries have NULL project_id', null_count;
    END IF;

    RAISE NOTICE 'Migration verification passed: All l2_insight_history entries have project_id';
END $$;
