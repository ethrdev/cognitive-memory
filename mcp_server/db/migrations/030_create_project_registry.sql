-- Migration 030: Create project_registry Table
-- Story 11.2.1: Create project_registry Table
--
-- Purpose: Create the project registry table for access control
--          Defines access levels (super/shared/isolated) for each project
-- Dependencies: Migration 027 (project_id columns must exist)
-- Risk: LOW - New table, no data changes
-- Rollback: 030_create_project_registry_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- ENUM TYPE CREATION
-- ============================================================================

-- Use DO block for idempotency (CREATE TYPE has no IF NOT EXISTS)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'access_level_enum') THEN
        CREATE TYPE access_level_enum AS ENUM ('super', 'shared', 'isolated');
    END IF;
END $$;

-- ============================================================================
-- TABLE CREATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS project_registry (
    id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    access_level access_level_enum NOT NULL DEFAULT 'isolated',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_project_registry_project_id
    ON project_registry(project_id);

-- ============================================================================
-- COMMENTS (for documentation)
-- ============================================================================

COMMENT ON TABLE project_registry IS
    'Registry of all projects with their access levels for multi-tenant isolation';

COMMENT ON COLUMN project_registry.project_id IS
    'Unique project identifier (matches project_id column in all tenant tables)';

COMMENT ON COLUMN project_registry.access_level IS
    'Access level: super (read all), shared (read own + semantic-memory), isolated (read own only)';

COMMENT ON COLUMN project_registry.name IS
    'Human-readable project name';

COMMENT ON COLUMN project_registry.created_at IS
    'Timestamp when project was registered';

COMMENT ON COLUMN project_registry.updated_at IS
    'Timestamp when project record was last updated';

COMMENT ON INDEX idx_project_registry_project_id IS
    'Index for efficient project_id lookups in ACL checks';

-- ============================================================================
-- TRIGGER for updated_at auto-update
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

-- Create trigger for project_registry
DROP TRIGGER IF EXISTS update_project_registry_updated_at ON project_registry;
CREATE TRIGGER update_project_registry_updated_at
    BEFORE UPDATE ON project_registry
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TRIGGER update_project_registry_updated_at ON project_registry IS
    'Automatically updates updated_at timestamp on row modification';

RESET lock_timeout;
