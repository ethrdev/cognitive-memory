-- Rollback Migration 027: Remove project_id Columns
--
-- WARNING: Only run if Story 11.1.1 needs to be rolled back
-- Story 11.1.2+ may have validated constraints - full rollback requires
-- rolling back subsequent migrations first
--
-- Procedure:
--   1. Run rollback script in test environment first
--   2. Verify schema returns to pre-migration state
--   3. Check that no dependent migrations exist (11.1.2+ not yet applied)
--   4. Execute in production during maintenance window (if needed)

-- Core Tables (High Risk)
ALTER TABLE l2_insights DROP COLUMN IF EXISTS project_id;
ALTER TABLE nodes DROP COLUMN IF EXISTS project_id;
ALTER TABLE edges DROP COLUMN IF EXISTS project_id;

-- Support Tables (Lower Risk)
ALTER TABLE working_memory DROP COLUMN IF EXISTS project_id;
ALTER TABLE episode_memory DROP COLUMN IF EXISTS project_id;
ALTER TABLE l0_raw DROP COLUMN IF EXISTS project_id;
ALTER TABLE ground_truth DROP COLUMN IF EXISTS project_id;

-- Additional Tables (discovered in schema analysis)
ALTER TABLE stale_memory DROP COLUMN IF EXISTS project_id;
ALTER TABLE smf_proposals DROP COLUMN IF EXISTS project_id;
ALTER TABLE ief_feedback DROP COLUMN IF EXISTS project_id;
ALTER TABLE l2_insight_history DROP COLUMN IF EXISTS project_id;

-- Verification query - confirm columns removed:
-- SELECT table_name, column_name
-- FROM information_schema.columns
-- WHERE column_name = 'project_id'
-- ORDER BY table_name;
-- (Should return empty result set if rollback successful)
