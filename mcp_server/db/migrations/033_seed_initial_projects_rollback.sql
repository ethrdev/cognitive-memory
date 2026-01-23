-- Rollback Migration 033: Remove Seeded Project Data
--
-- WARNING: Only run if Story 11.2.4 needs to be rolled back
-- This removes all seeded project data from the namespace isolation tables
--
-- IMPORTANT: Delete order is critical due to foreign key constraints
-- 1. Delete migration status (has FK to project_registry)
-- 2. Delete read permissions (has FK to project_registry)
-- 3. Delete projects (no dependencies remaining)

SET lock_timeout = '5s';

-- ============================================================================
-- DELETE IN REVERSE ORDER OF DEPENDENCIES
-- ============================================================================

-- 1. Delete RLS migration status (depends on project_registry.project_id)
DELETE FROM rls_migration_status
WHERE project_id IN ('io', 'echo', 'ea', 'ab', 'aa', 'bap', 'motoko', 'sm');

-- 2. Delete read permissions (depends on project_registry.project_id)
DELETE FROM project_read_permissions
WHERE reader_project_id IN ('ab', 'aa', 'bap');

-- 3. Delete projects (referenced by foreign keys, now safe to delete)
DELETE FROM project_registry
WHERE project_id IN ('io', 'echo', 'ea', 'ab', 'aa', 'bap', 'motoko', 'sm');

RESET lock_timeout;
