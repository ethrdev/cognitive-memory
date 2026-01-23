-- Migration 028: Update Unique Constraints for Multi-Project Support
-- Story 11.1.3: Update Unique Constraints
-- Risk: LOW - CONCURRENTLY pattern prevents long locks
-- Rollback: 028_update_unique_constraints_rollback.sql
--
-- Purpose: Update unique constraints to include project_id, enabling cross-project
--          duplicate entity names while maintaining uniqueness within each project.
--
-- Previous State:
--   - nodes: UNIQUE(name) from migration 013
--   - edges: UNIQUE(source_id, target_id, relation) from migration 012
--
-- New State:
--   - nodes: UNIQUE(project_id, name)
--   - edges: UNIQUE(project_id, source_id, target_id, relation)
--
-- Zero-Downtime Pattern:
--   1. CREATE UNIQUE INDEX CONCURRENTLY (no lock)
--   2. DROP CONSTRAINT IF EXISTS (brief ACCESS EXCLUSIVE lock, < 1s)
--   3. ADD CONSTRAINT ... USING INDEX (brief ACCESS EXCLUSIVE lock, < 1s)

-- ============================================================================
-- SET lock_timeout for constraint operations
-- ============================================================================
SET lock_timeout = '5s';

-- ============================================================================
-- STEP 1: Create new indexes CONCURRENTLY (no table lock)
-- ============================================================================
-- These indexes are built in the background without blocking reads/writes

-- Nodes: New composite unique index including project_id
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_nodes_project_name_new
    ON nodes(project_id, name);

-- Edges: New composite unique index including project_id
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_project_new
    ON edges(project_id, source_id, target_id, relation);

-- ============================================================================
-- STEP 2: Drop old constraints (brief ACCESS EXCLUSIVE lock)
-- ============================================================================

-- Drop old nodes unique constraint (also removes associated index)
-- From migration 013: idx_nodes_unique on (name)
ALTER TABLE nodes DROP CONSTRAINT IF EXISTS idx_nodes_unique;

-- Drop old edges unique constraint (also removes associated index)
-- From migration 012: idx_edges_unique on (source_id, target_id, relation)
ALTER TABLE edges DROP CONSTRAINT IF EXISTS idx_edges_unique;

-- ============================================================================
-- STEP 3: Add new constraints using created indexes (brief lock)
-- ============================================================================

-- Add new nodes constraint using the index created in STEP 1
-- This avoids rebuilding the index since it already exists
ALTER TABLE nodes
    ADD CONSTRAINT nodes_project_name_unique
    UNIQUE USING INDEX idx_nodes_project_name_new;

-- Add new edges constraint using the index created in STEP 1
ALTER TABLE edges
    ADD CONSTRAINT edges_project_unique
    UNIQUE USING INDEX idx_edges_project_new;

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Verify new constraints exist
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid::regclass IN ('nodes', 'edges')
--   AND contype = 'u'
-- ORDER BY conrelid::regclass::text;

-- Expected results:
--   nodes_project_name_unique on (project_id, name)
--   edges_project_unique on (project_id, source_id, target_id, relation)

-- Verify indexes exist
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('nodes', 'edges')
--   AND indexname IN ('idx_nodes_project_name_new', 'idx_edges_project_new')
-- ORDER BY tablename, indexname;

-- ============================================================================
-- CLEANUP
-- ============================================================================
RESET lock_timeout;
