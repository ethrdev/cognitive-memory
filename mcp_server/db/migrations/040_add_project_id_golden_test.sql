-- Migration 040: Add project_id to golden_test_set and model_drift_log tables
-- Story: 11.7.3 - Golden Test and Verification Operations Project-Aware
-- Date: 2026-01-24

-- =============================================================================
-- Phase 1: Add project_id column to golden_test_set
-- =============================================================================

ALTER TABLE golden_test_set
ADD COLUMN IF NOT EXISTS project_id VARCHAR(50) NOT NULL DEFAULT 'io';

COMMENT ON COLUMN golden_test_set.project_id IS
'Project identifier for namespace isolation (Epic 11). Each project maintains its own golden test set.';

-- =============================================================================
-- Phase 2: Add project_id column to model_drift_log
-- =============================================================================

ALTER TABLE model_drift_log
ADD COLUMN IF NOT EXISTS project_id VARCHAR(50) NOT NULL DEFAULT 'io';

COMMENT ON COLUMN model_drift_log.project_id IS
'Project identifier for namespace isolation. Each project tracks its own model drift.';

-- Modify primary key constraint to include project_id
-- NOTE: This is a BREAKING CHANGE - the composite key changes from (date) to (date, project_id)
ALTER TABLE model_drift_log DROP CONSTRAINT IF EXISTS model_drift_log_pkey;
ALTER TABLE model_drift_log ADD PRIMARY KEY (date, project_id);

-- =============================================================================
-- Phase 3: Add indexes for project-scoped queries
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_golden_test_set_project
ON golden_test_set(project_id);

CREATE INDEX IF NOT EXISTS idx_model_drift_log_project_date
ON model_drift_log(project_id, date DESC);

-- =============================================================================
-- Phase 4: Enable RLS
-- =============================================================================

ALTER TABLE golden_test_set ENABLE ROW LEVEL SECURITY;
ALTER TABLE golden_test_set FORCE ROW LEVEL SECURITY;

ALTER TABLE model_drift_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_drift_log FORCE ROW LEVEL SECURITY;

-- =============================================================================
-- Phase 5: Create RLS policies
-- =============================================================================

-- golden_test_set: SELECT policy
CREATE POLICY select_golden_test_set ON golden_test_set
    FOR SELECT
    USING (
        CASE (SELECT get_rls_mode())
            WHEN 'pending' THEN TRUE
            WHEN 'shadow' THEN TRUE
            WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            ELSE TRUE
        END
    );

-- model_drift_log: SELECT policy
CREATE POLICY select_model_drift_log ON model_drift_log
    FOR SELECT
    USING (
        CASE (SELECT get_rls_mode())
            WHEN 'pending' THEN TRUE
            WHEN 'shadow' THEN TRUE
            WHEN 'enforcing' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            WHEN 'complete' THEN project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[])
            ELSE TRUE
        END
    );

-- model_drift_log: INSERT policy
CREATE POLICY insert_model_drift_log ON model_drift_log
    FOR INSERT
    WITH CHECK (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]));

-- model_drift_log: UPDATE policy
CREATE POLICY update_model_drift_log ON model_drift_log
    FOR UPDATE
    USING (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]))
    WITH CHECK (project_id::TEXT = ANY ((SELECT get_allowed_projects())::TEXT[]));

-- =============================================================================
-- Phase 6: Update existing data
-- =============================================================================

-- Set existing golden_test_set records to 'io' project (default super project)
-- Only update if project_id is the default (not already set by a previous run)
UPDATE golden_test_set
SET project_id = 'io'
WHERE project_id IS NULL OR project_id = 'io';

-- Set existing model_drift_log records to 'io' project (default super project)
-- Only update if project_id is the default (not already set by a previous run)
UPDATE model_drift_log
SET project_id = 'io'
WHERE project_id IS NULL OR project_id = 'io';
