-- Migration 033: Seed Initial Project Data
-- Story 11.2.4: Seed Initial Data
--
-- Purpose: Populate project_registry, project_read_permissions, and rls_migration_status
--          with the 8 known projects and their initial configuration
-- Dependencies: Migrations 030, 031, 032 (tables must exist)
-- Risk: LOW - Data insertion with idempotency protection
-- Rollback: 033_seed_initial_projects_rollback.sql

SET lock_timeout = '5s';

-- ============================================================================
-- PROJECT REGISTRY
-- ============================================================================

-- SUPER Projects (can read all projects)
INSERT INTO project_registry (project_id, name, access_level)
VALUES ('io', 'I/O System', 'super')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO project_registry (project_id, name, access_level)
VALUES ('echo', 'Echo', 'super')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO project_registry (project_id, name, access_level)
VALUES ('ea', 'ethr-assistant', 'super')
ON CONFLICT (project_id) DO NOTHING;

-- SHARED Projects (can read semantic-memory)
INSERT INTO project_registry (project_id, name, access_level)
VALUES ('ab', 'Application Builder', 'shared')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO project_registry (project_id, name, access_level)
VALUES ('aa', 'Application Assistant', 'shared')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO project_registry (project_id, name, access_level)
VALUES ('bap', 'bmad-audit-polish', 'shared')
ON CONFLICT (project_id) DO NOTHING;

-- ISOLATED Projects (own scope only)
INSERT INTO project_registry (project_id, name, access_level)
VALUES ('motoko', 'Motoko', 'isolated')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO project_registry (project_id, name, access_level)
VALUES ('sm', 'Semantic Memory', 'isolated')
ON CONFLICT (project_id) DO NOTHING;

-- ============================================================================
-- PROJECT READ PERMISSIONS
-- ============================================================================

-- SHARED projects can read semantic-memory
-- Rationale: SHARED projects (Application Builder, Application Assistant,
-- bmad-audit-polish) need read access to semantic-memory because they operate
-- on the knowledge graph as their primary data source. This is a controlled
-- exception to isolation - semantic-memory is designed as a shared resource
-- for SHARED-level applications.
INSERT INTO project_read_permissions (reader_project_id, target_project_id)
VALUES ('ab', 'sm')
ON CONFLICT (reader_project_id, target_project_id) DO NOTHING;

INSERT INTO project_read_permissions (reader_project_id, target_project_id)
VALUES ('aa', 'sm')
ON CONFLICT (reader_project_id, target_project_id) DO NOTHING;

INSERT INTO project_read_permissions (reader_project_id, target_project_id)
VALUES ('bap', 'sm')
ON CONFLICT (reader_project_id, target_project_id) DO NOTHING;

-- ============================================================================
-- RLS MIGRATION STATUS
-- ============================================================================

-- All projects start in 'pending' phase
-- RLS will be enabled gradually in Epic 11.3 (RLS policies) and Epic 11.8 (Gradual Rollout)
INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('io', 'pending')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('echo', 'pending')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('ea', 'pending')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('ab', 'pending')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('aa', 'pending')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('bap', 'pending')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('motoko', 'pending')
ON CONFLICT (project_id) DO NOTHING;

INSERT INTO rls_migration_status (project_id, migration_phase)
VALUES ('sm', 'pending')
ON CONFLICT (project_id) DO NOTHING;

-- ============================================================================
-- VERIFICATION QUERIES (for manual testing)
-- ============================================================================

-- Uncomment to verify seeded data:
-- SELECT * FROM project_registry ORDER BY project_id;
-- SELECT * FROM project_read_permissions ORDER BY reader, target;
-- SELECT * FROM rls_migration_status ORDER BY project_id;

RESET lock_timeout;
