-- Migration 050: Add audit_log Table (Constitutive Edge Consent Audit)
--
-- Purpose: Create the audit_log table that mcp_server/db/graph.py already
--          reads/writes (_log_audit_entry, get_audit_log, clear_audit_log) but
--          which never existed in the database. Without it, _log_audit_entry's
--          INSERT failed silently (exception caught + logged only) while the
--          delete/block of a constitutive edge still went through -> the consent
--          audit trail for constitutive edges was effectively dead.
--
-- Scoping: Project-isolated (variant a). The table carries a project_id column
--          whose DEFAULT is get_current_project() (the RLS session GUC set by
--          set_project_context() inside get_connection_with_project_context()).
--          This lets _log_audit_entry's INSERT stay UNCHANGED (it does not pass
--          project_id) while still tagging each audit row with the active
--          project, and it satisfies the own-project INSERT WITH CHECK policy.
--          RLS mirrors the core-table pattern from migration 036 so io/ab/njord/
--          tethr each see only their own audit entries.
--
-- No FK: edge_id is a plain UUID value, NOT a foreign key to edges(id). The
--        audit protocols edge DELETIONS - once the edge is gone, an FK (worse
--        with CASCADE) would delete the audit row too and destroy the purpose.
--
-- Dependencies: Migration 034 (RLS helper functions: set_project_context,
--               get_current_project, get_rls_mode, get_allowed_projects),
--               Migration 036 (RLS policy pattern reference).
-- Risk: LOW - Additive. New table only, no change to existing tables or data.
-- Rollback: 050_add_audit_log_table_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- DEPENDENCY VALIDATION
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'get_current_project') THEN
        RAISE EXCEPTION 'Dependency check failed: get_current_project() does not exist. Run migration 034 first.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'get_allowed_projects') THEN
        RAISE EXCEPTION 'Dependency check failed: get_allowed_projects() does not exist. Run migration 034 first.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'get_rls_mode') THEN
        RAISE EXCEPTION 'Dependency check failed: get_rls_mode() does not exist. Run migration 034 first.';
    END IF;
END $$;

-- ============================================================================
-- TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    edge_id     UUID NOT NULL,                                  -- plain UUID value, intentionally NOT a FK to edges(id)
    action      TEXT NOT NULL,                                  -- e.g. DELETE_ATTEMPT, DELETE_SUCCESS
    blocked     BOOLEAN NOT NULL DEFAULT FALSE,
    reason      TEXT,
    actor       TEXT NOT NULL DEFAULT 'system',
    properties  JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    project_id  VARCHAR(50) NOT NULL DEFAULT get_current_project()  -- variant (a): auto-filled from RLS session GUC
);

COMMENT ON TABLE audit_log IS
    'Consent audit trail for constitutive edge operations (written by mcp_server/db/graph.py _log_audit_entry). Project-isolated via RLS. edge_id is a plain UUID, NOT a FK (audit must survive edge deletion).';
COMMENT ON COLUMN audit_log.edge_id IS
    'UUID of the affected edge. Plain value, no FK - the audited edge may already be deleted.';
COMMENT ON COLUMN audit_log.project_id IS
    'Owning project. DEFAULT get_current_project() fills it from the RLS session context so the application INSERT stays unchanged. NOT NULL for defense-in-depth RLS.';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- get_audit_log filters by edge_id
CREATE INDEX IF NOT EXISTS idx_audit_log_edge_id ON audit_log (edge_id);
-- get_audit_log orders by created_at DESC
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log (created_at DESC);

-- ============================================================================
-- ROW LEVEL SECURITY (mirrors migration 036 core-table pattern)
-- ============================================================================

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;

-- RESTRICTIVE: block rows with NULL project_id (evaluates before permissive policies)
CREATE POLICY require_project_id ON audit_log
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);

COMMENT ON POLICY require_project_id ON audit_log IS
    'RESTRICTIVE policy: Blocks rows with NULL project_id. Defense-in-depth, evaluates before permissive policies.';

-- SELECT: conditional enforcement by rls_mode (subquery pattern for single evaluation)
CREATE POLICY select_audit_log ON audit_log
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

COMMENT ON POLICY select_audit_log ON audit_log IS
    'SELECT policy: Conditional enforcement by rls_mode. pending/shadow=allow all, enforcing/complete=get_allowed_projects().';

-- INSERT: own-project-only. project_id defaults to get_current_project(), so the
-- application INSERT (which omits project_id) passes this check unchanged.
CREATE POLICY insert_audit_log ON audit_log
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY insert_audit_log ON audit_log IS
    'INSERT policy: Own-project-only. Write isolation is absolute. project_id DEFAULT get_current_project() keeps the app INSERT unchanged.';

-- UPDATE: own-project-only
CREATE POLICY update_audit_log ON audit_log
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

COMMENT ON POLICY update_audit_log ON audit_log IS
    'UPDATE policy: Own-project-only. USING filters existing rows, WITH CHECK validates new values.';

-- DELETE: own-project-only
CREATE POLICY delete_audit_log ON audit_log
FOR DELETE
USING (project_id = (SELECT get_current_project()));

COMMENT ON POLICY delete_audit_log ON audit_log IS
    'DELETE policy: Own-project-only.';

-- ============================================================================
-- VERIFICATION (commented - run manually)
-- ============================================================================

-- SELECT to_regclass('public.audit_log');  -- expect: audit_log (not NULL)
-- SELECT column_name, data_type, is_nullable, column_default
--   FROM information_schema.columns WHERE table_name='audit_log' ORDER BY ordinal_position;
-- SELECT policyname, cmd, permissive FROM pg_policies WHERE tablename='audit_log' ORDER BY policyname;

RESET lock_timeout;
