-- Migration 050 Rollback: Drop audit_log Table
--
-- Purpose: Remove the audit_log table created in 050_add_audit_log_table.sql,
--          including its RLS policies and indexes.
-- Risk: LOW - Drops a single additive table. WARNING: deletes all audit data.
--          After rollback, _log_audit_entry returns to silent-failure behavior
--          (the pre-migration bug), get_audit_log returns [] - no crash.
-- This migration is idempotent - safe to run multiple times.

SET lock_timeout = '5s';

-- Drop policies (no-op if table already gone)
DROP POLICY IF EXISTS delete_audit_log     ON audit_log;
DROP POLICY IF EXISTS update_audit_log     ON audit_log;
DROP POLICY IF EXISTS insert_audit_log     ON audit_log;
DROP POLICY IF EXISTS select_audit_log     ON audit_log;
DROP POLICY IF EXISTS require_project_id    ON audit_log;

-- Drop indexes (dropped with the table too, explicit for clarity / partial states)
DROP INDEX IF EXISTS idx_audit_log_created_at;
DROP INDEX IF EXISTS idx_audit_log_edge_id;

-- Drop the table
DROP TABLE IF EXISTS audit_log;

-- ============================================================================
-- VERIFICATION (commented - run manually)
-- ============================================================================

-- SELECT to_regclass('public.audit_log');  -- expect: NULL after rollback

RESET lock_timeout;
