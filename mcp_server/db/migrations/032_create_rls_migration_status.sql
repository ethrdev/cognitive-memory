-- Migration 032: Create rls_migration_status Table
-- Story 11.2.3: Create rls_migration_status Table
--
-- Purpose: Track RLS migration status per project for gradual rollout
--          Enables conditional RLS enforcement based on migration phase
-- Dependencies: Migration 030 (project_registry table must exist)
-- Risk: LOW - New table, no data changes
-- Rollback: 032_create_rls_migration_status_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- ENUM TYPE CREATION
-- ============================================================================

-- Use DO block for idempotency (CREATE TYPE has no IF NOT EXISTS)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'migration_phase_enum') THEN
        CREATE TYPE migration_phase_enum AS ENUM ('pending', 'shadow', 'enforcing', 'complete');
    END IF;
END $$;

-- ============================================================================
-- TABLE CREATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS rls_migration_status (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) UNIQUE NOT NULL,
    rls_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    migration_phase migration_phase_enum NOT NULL DEFAULT 'pending',
    migrated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Foreign Key with CASCADE delete
    CONSTRAINT fk_rls_status_project
        FOREIGN KEY (project_id)
        REFERENCES project_registry(project_id)
        ON DELETE CASCADE
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_rls_status_project_id
    ON rls_migration_status(project_id);

CREATE INDEX IF NOT EXISTS idx_rls_status_migration_phase
    ON rls_migration_status(migration_phase);

-- ============================================================================
-- TRIGGER: updated_at auto-update
-- ============================================================================

-- Reuse existing trigger function from migration 003 (update_updated_at_column)
-- If it doesn't exist, create it (idempotent)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for rls_migration_status
DROP TRIGGER IF EXISTS update_rls_migration_status_updated_at ON rls_migration_status;
CREATE TRIGGER update_rls_migration_status_updated_at
    BEFORE UPDATE ON rls_migration_status
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- COMMENTS (for documentation)
-- ============================================================================

COMMENT ON TABLE rls_migration_status IS
    'Track RLS migration status for each project during gradual rollout';

COMMENT ON COLUMN rls_migration_status.project_id IS
    'Reference to project_registry(project_id)';

COMMENT ON COLUMN rls_migration_status.rls_enabled IS
    'Quick boolean check: is RLS active for this project?';

COMMENT ON COLUMN rls_migration_status.migration_phase IS
    'Current migration phase: pending (not started), shadow (audit only), enforcing (RLS active), complete (stable)';

COMMENT ON COLUMN rls_migration_status.migrated_at IS
    'Timestamp when project entered enforcing phase (NULL for pending/shadow)';

COMMENT ON COLUMN rls_migration_status.created_at IS
    'Timestamp when migration status record was created';

COMMENT ON COLUMN rls_migration_status.updated_at IS
    'Timestamp when migration status was last updated';

COMMENT ON CONSTRAINT fk_rls_status_project ON rls_migration_status IS
    'Cascade delete: if project is deleted, remove its migration status';

COMMENT ON INDEX idx_rls_status_project_id IS
    'Index for fast lookup of single project status';

COMMENT ON INDEX idx_rls_status_migration_phase IS
    'Index for finding all projects in a specific phase';

COMMENT ON TRIGGER update_rls_migration_status_updated_at ON rls_migration_status IS
    'Automatically updates updated_at timestamp on row modification';

RESET lock_timeout;
