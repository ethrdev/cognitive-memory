-- Migration 031: Create project_read_permissions Table
-- Story 11.2.2: Create project_read_permissions Table
--
-- Purpose: Create explicit read permissions between projects
--          Enables SHARED projects to access semantic-memory and other cross-project resources
-- Dependencies: Migration 030 (project_registry table must exist)
-- Risk: LOW - New table, no data changes
-- Rollback: 031_create_project_read_permissions_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- TABLE CREATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS project_read_permissions (
    id SERIAL PRIMARY KEY,
    reader_project_id VARCHAR(50) NOT NULL,
    target_project_id VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Foreign Keys with CASCADE delete
    CONSTRAINT fk_permissions_reader
        FOREIGN KEY (reader_project_id)
        REFERENCES project_registry(project_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_permissions_target
        FOREIGN KEY (target_project_id)
        REFERENCES project_registry(project_id)
        ON DELETE CASCADE,

    -- Unique constraint: one permission per (reader, target) pair
    CONSTRAINT uq_permission_pair
        UNIQUE (reader_project_id, target_project_id),

    -- Check constraint: no self-references
    CONSTRAINT chk_no_self_reference
        CHECK (reader_project_id != target_project_id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_permissions_reader
    ON project_read_permissions(reader_project_id);

-- ============================================================================
-- COMMENTS (for documentation)
-- ============================================================================

COMMENT ON TABLE project_read_permissions IS
    'Explicit read permissions between projects for cross-project access in ACL system';

COMMENT ON COLUMN project_read_permissions.reader_project_id IS
    'Project that is requesting read access (the "who")';

COMMENT ON COLUMN project_read_permissions.target_project_id IS
    'Project being accessed (the "what")';

COMMENT ON COLUMN project_read_permissions.created_at IS
    'Timestamp when permission was granted';

COMMENT ON CONSTRAINT fk_permissions_reader ON project_read_permissions IS
    'Cascade delete: if reader project is deleted, remove its permissions';

COMMENT ON CONSTRAINT fk_permissions_target ON project_read_permissions IS
    'Cascade delete: if target project is deleted, remove permissions to it';

COMMENT ON CONSTRAINT uq_permission_pair ON project_read_permissions IS
    'Prevent duplicate permission entries for same (reader, target) pair';

COMMENT ON CONSTRAINT chk_no_self_reference ON project_read_permissions IS
    'Prevent meaningless self-permissions (project reading from itself)';

COMMENT ON INDEX idx_permissions_reader IS
    'Index for efficient RLS policy lookup: WHERE reader_project_id = current_project';

RESET lock_timeout;
