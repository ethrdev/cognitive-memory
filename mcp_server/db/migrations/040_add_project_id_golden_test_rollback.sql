-- Migration 040 Rollback: Remove project_id from golden_test_set and model_drift_log
-- Story: 11.7.3 - Golden Test and Verification Operations Project-Aware
-- Date: 2026-01-24

-- WARNING: This rollback will DELETE all model_drift_log data from non-'io' projects
-- because the primary key changes from (date, project_id) back to (date)

-- =============================================================================
-- Phase 1: Drop RLS policies
-- =============================================================================

DROP POLICY IF EXISTS select_golden_test_set ON golden_test_set;
DROP POLICY IF EXISTS select_model_drift_log ON model_drift_log;
DROP POLICY IF EXISTS insert_model_drift_log ON model_drift_log;
DROP POLICY IF EXISTS update_model_drift_log ON model_drift_log;

-- =============================================================================
-- Phase 2: Disable RLS
-- =============================================================================

ALTER TABLE golden_test_set NO FORCE ROW LEVEL SECURITY;
ALTER TABLE golden_test_set DISABLE ROW LEVEL SECURITY;

ALTER TABLE model_drift_log NO FORCE ROW LEVEL SECURITY;
ALTER TABLE model_drift_log DISABLE ROW LEVEL SECURITY;

-- =============================================================================
-- Phase 3: Drop indexes
-- =============================================================================

DROP INDEX IF EXISTS idx_golden_test_set_project;
DROP INDEX IF EXISTS idx_model_drift_log_project_date;

-- =============================================================================
-- Phase 4: Restore original primary key on model_drift_log
-- WARNING: This will DELETE all non-'io' project data
-- =============================================================================

-- First, preserve only 'io' project data (or the first entry per date if no 'io' data)
-- This is a destructive operation - all other project data will be lost
DELETE FROM model_drift_log
WHERE project_id IS NOT NULL AND project_id != 'io';

-- Now restore the original primary key
ALTER TABLE model_drift_log DROP CONSTRAINT IF EXISTS model_drift_log_pkey;
ALTER TABLE model_drift_log ADD PRIMARY KEY (date);

-- =============================================================================
-- Phase 5: Drop project_id columns
-- =============================================================================

ALTER TABLE golden_test_set DROP COLUMN IF EXISTS project_id;
ALTER TABLE model_drift_log DROP COLUMN IF EXISTS project_id;
