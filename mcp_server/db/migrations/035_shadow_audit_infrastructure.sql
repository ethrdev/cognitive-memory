-- Migration 035: Shadow Audit Infrastructure
-- Story 11.3.2: Shadow Audit Infrastructure
--
-- Purpose: Create shadow audit infrastructure that logs RLS violations without blocking
--          Enables validation of zero cross-project accesses before enabling enforcing mode
-- Dependencies: Migration 034 (RLS Helper Functions)
-- Risk: LOW - New table and functions, no data changes
-- Rollback: 035_shadow_audit_infrastructure_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- DEPENDENCY VALIDATION
-- ============================================================================

-- Verify Epic 11.3.1 functions exist
DO $$
BEGIN
    -- Check set_project_context exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'set_project_context'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: set_project_context function does not exist. Please run Story 11.3.1 migration first.';
    END IF;

    -- Check get_allowed_projects exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_allowed_projects'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_allowed_projects function does not exist. Please run Story 11.3.1 migration first.';
    END IF;

    -- Check get_rls_mode exists
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'get_rls_mode'
    ) THEN
        RAISE EXCEPTION 'Dependency check failed: get_rls_mode function does not exist. Please run Story 11.3.1 migration first.';
    END IF;
END $$;

-- ============================================================================
-- RLS_AUDIT_LOG TABLE (AC1)
-- ============================================================================

-- Create rls_audit_log table for shadow mode auditing
CREATE TABLE IF NOT EXISTS rls_audit_log (
    id BIGSERIAL PRIMARY KEY,
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    project_id VARCHAR(50) NOT NULL,        -- Requesting project (who initiated)
    table_name VARCHAR(100) NOT NULL,        -- Affected table
    operation VARCHAR(10) NOT NULL,          -- INSERT/UPDATE/DELETE/SELECT
    row_project_id VARCHAR(50) NOT NULL,     -- Project that owns the row
    would_be_denied BOOLEAN NOT NULL,        -- TRUE if RLS would block this
    old_data JSONB,                          -- Previous row state (UPDATE/DELETE)
    new_data JSONB,                          -- New row state (INSERT/UPDATE)
    session_user_name VARCHAR(100)           -- Database user (app_user)
);

-- CRITICAL: NO RLS on this table - audit must always be writable
COMMENT ON TABLE rls_audit_log IS
    'Shadow audit log for RLS violations. Records would-be-blocked operations during shadow phase. CRITICAL: NO RLS on this table - audit must always be writable.';

-- BRIN index on logged_at for time-series optimization (AC1)
-- BRIN is ideal for sequentially inserted audit data - space-efficient
CREATE INDEX IF NOT EXISTS idx_audit_log_time
    ON rls_audit_log USING BRIN (logged_at);

COMMENT ON INDEX idx_audit_log_time IS
    'BRIN index for time-range filtering on audit logs. Space-efficient for sequentially inserted data.';

-- Partial B-tree index for violation queries (AC1)
CREATE INDEX IF NOT EXISTS idx_audit_log_violations
    ON rls_audit_log (logged_at)
    WHERE would_be_denied = TRUE;

COMMENT ON INDEX idx_audit_log_violations IS
    'Partial B-tree index for fast violation queries (would_be_denied = TRUE).';

-- ============================================================================
-- RLS_CHECK_ACCESS() FUNCTION (AC2)
-- ============================================================================

-- rls_check_access(p_requesting_project, p_row_project, p_operation)
-- Purpose: Check if access would be allowed under RLS
-- Returns: TRUE if access allowed, FALSE if denied
-- Uses get_allowed_projects() from Story 11.3.1 for ACL evaluation
CREATE OR REPLACE FUNCTION rls_check_access(
    p_requesting_project VARCHAR(50),
    p_row_project VARCHAR(50),
    p_operation VARCHAR(10)
)
RETURNS BOOLEAN AS $$
DECLARE
    v_allowed_projects TEXT[];
BEGIN
    -- Get allowed projects from session variable (set by set_project_context)
    v_allowed_projects := get_allowed_projects();

    -- WRITE operations: Only allow same project
    IF p_operation IN ('INSERT', 'UPDATE', 'DELETE') THEN
        RETURN p_requesting_project = p_row_project;
    END IF;

    -- READ operations: Check if row project is in allowed list
    IF p_operation = 'SELECT' THEN
        RETURN p_row_project = ANY(v_allowed_projects);
    END IF;

    -- Unknown operation - deny by default
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public;

COMMENT ON FUNCTION rls_check_access(VARCHAR(50), VARCHAR(50), VARCHAR(10)) IS
    'Check if access would be allowed under RLS. Returns TRUE if allowed, FALSE if denied.
     Access Logic:
       - Super-level: can READ all projects, can WRITE only own
       - Shared-level: can READ own + permitted, can WRITE only own
       - Isolated-level: can READ/WRITE only own
     Uses get_allowed_projects() from Story 11.3.1 for ACL evaluation.';

-- ============================================================================
-- SHADOW_AUDIT_TRIGGER() FUNCTION (AC3, AC4)
-- ============================================================================

-- shadow_audit_trigger()
-- Purpose: Trigger function for shadow audit logging
-- Behavior:
--   - Checks get_rls_mode() = 'shadow' before executing (AC4)
--   - Evaluates rls_check_access() to determine would_be_denied
--   - Logs to rls_audit_log if would_be_denied = TRUE
--   - Does NOT block the actual operation (shadow = observe only)
-- Returns: OLD for DELETE, NEW for INSERT/UPDATE (proper trigger return)
CREATE OR REPLACE FUNCTION shadow_audit_trigger()
RETURNS TRIGGER AS $$
DECLARE
    v_rls_mode TEXT;
    v_would_be_denied BOOLEAN;
    v_row_project_id VARCHAR(50);
    v_current_project VARCHAR(50);
BEGIN
    -- Only execute in shadow mode (AC4)
    SELECT get_rls_mode() INTO v_rls_mode;
    IF v_rls_mode != 'shadow' THEN
        -- Not in shadow mode - skip audit
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END IF;

    -- Get current project from session variable
    v_current_project := current_setting('app.current_project', TRUE);

    -- Extract project_id from row based on operation
    IF TG_OP = 'DELETE' THEN
        v_row_project_id := OLD.project_id;
    ELSE
        v_row_project_id := NEW.project_id;
    END IF;

    -- Check if this would be denied under RLS
    v_would_be_denied := NOT rls_check_access(v_current_project, v_row_project_id, TG_OP);

    -- Log if this would be denied
    IF v_would_be_denied THEN
        INSERT INTO rls_audit_log (
            project_id,
            table_name,
            operation,
            row_project_id,
            would_be_denied,
            old_data,
            new_data,
            session_user_name
        ) VALUES (
            v_current_project,
            TG_TABLE_NAME,
            TG_OP,
            v_row_project_id,
            TRUE,
            row_to_json(OLD),
            row_to_json(NEW),
            current_user
        );
    END IF;

    -- Return proper value for trigger (AC3)
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public;

COMMENT ON FUNCTION shadow_audit_trigger() IS
    'Shadow audit trigger function. Logs would-be-blocked operations during shadow phase.
     CRITICAL: Only executes when get_rls_mode() = ''shadow''. Does NOT block actual operations.
     Returns OLD for DELETE, NEW for INSERT/UPDATE (proper trigger return pattern).';

-- ============================================================================
-- ATTACH TRIGGERS TO CORE TABLES (Task 4, AC3)
-- ============================================================================

-- Drop triggers first if they exist (for idempotent migration)
DROP TRIGGER IF EXISTS tr_l2_insights_shadow_audit ON l2_insights;
DROP TRIGGER IF EXISTS tr_nodes_shadow_audit ON nodes;
DROP TRIGGER IF EXISTS tr_edges_shadow_audit ON edges;

-- Attach trigger to l2_insights (AFTER trigger ensures audit written even if constraint fails)
CREATE TRIGGER tr_l2_insights_shadow_audit
    AFTER INSERT OR UPDATE OR DELETE ON l2_insights
    FOR EACH ROW EXECUTE FUNCTION shadow_audit_trigger();

COMMENT ON TRIGGER tr_l2_insights_shadow_audit ON l2_insights IS
    'Shadow audit trigger for l2_insights. Logs would-be RLS violations during shadow phase.';

-- Attach trigger to nodes
CREATE TRIGGER tr_nodes_shadow_audit
    AFTER INSERT OR UPDATE OR DELETE ON nodes
    FOR EACH ROW EXECUTE FUNCTION shadow_audit_trigger();

COMMENT ON TRIGGER tr_nodes_shadow_audit ON nodes IS
    'Shadow audit trigger for nodes. Logs would-be RLS violations during shadow phase.';

-- Attach trigger to edges
CREATE TRIGGER tr_edges_shadow_audit
    AFTER INSERT OR UPDATE OR DELETE ON edges
    FOR EACH ROW EXECUTE FUNCTION shadow_audit_trigger();

COMMENT ON TRIGGER tr_edges_shadow_audit ON edges IS
    'Shadow audit trigger for edges. Logs would-be RLS violations during shadow phase.';

-- ============================================================================
-- VERIFICATION
-- ============================================================================

-- Verify all objects created successfully
DO $$
BEGIN
    -- Verify table exists
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'rls_audit_log'
    ) THEN
        RAISE EXCEPTION 'Verification failed: rls_audit_log table was not created';
    END IF;

    -- Verify functions exist
    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'rls_check_access'
    ) THEN
        RAISE EXCEPTION 'Verification failed: rls_check_access function was not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'shadow_audit_trigger'
    ) THEN
        RAISE EXCEPTION 'Verification failed: shadow_audit_trigger function was not created';
    END IF;

    -- Verify triggers exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'tr_l2_insights_shadow_audit'
    ) THEN
        RAISE EXCEPTION 'Verification failed: tr_l2_insights_shadow_audit trigger was not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'tr_nodes_shadow_audit'
    ) THEN
        RAISE EXCEPTION 'Verification failed: tr_nodes_shadow_audit trigger was not created';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_name = 'tr_edges_shadow_audit'
    ) THEN
        RAISE EXCEPTION 'Verification failed: tr_edges_shadow_audit trigger was not created';
    END IF;

    RAISE NOTICE 'Shadow audit infrastructure created successfully';
END $$;

RESET lock_timeout;
