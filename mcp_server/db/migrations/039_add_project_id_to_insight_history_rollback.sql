-- Migration 039 Rollback: Remove project_id from l2_insight_history
-- Story 11.5.2: L2 Insight Write Operations

SET lock_timeout = '5s';

-- Drop index
DROP INDEX IF EXISTS idx_insight_history_project_id;

-- Remove column (requires CASCADE due to defaults)
ALTER TABLE l2_insight_history DROP COLUMN IF EXISTS project_id;
