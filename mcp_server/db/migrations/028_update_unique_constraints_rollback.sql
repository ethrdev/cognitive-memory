-- Migration 028 Rollback: Restore Original Unique Constraints
-- Story 11.1.3: Update Unique Constraints - Rollback
-- Risk: MEDIUM - May fail if duplicate names exist across projects
--
-- Purpose: Restore original unique constraints (without project_id)
--          WARNING: This will FAIL if cross-project duplicate names exist!
--
-- Rollback Pattern:
--   1. Create original indexes CONCURRENTLY (no lock)
--   2. Drop new composite constraints (brief lock)
--   3. Restore original constraints using recreated indexes (brief lock)
--   4. Clean up new indexes

-- ============================================================================
-- PRE-ROLLBACK VALIDATION
-- ============================================================================

-- Check for duplicate node names across projects BEFORE proceeding
-- Run this query first - if it returns any rows, DO NOT PROCEED with rollback
--
-- SELECT name, COUNT(*) as count, array_agg(DISTINCT project_id) as projects
-- FROM nodes
-- GROUP BY name
-- HAVING COUNT(*) > 1;
--
-- If any duplicates exist, either:
--   1. Do not rollback - fix-forward instead
--   2. Manually resolve duplicates before rollback
--   3. Use data migration to rename/move conflicting entities

-- Check for duplicate edges across projects BEFORE proceeding
--
-- SELECT source_id, target_id, relation, COUNT(*) as count, array_agg(DISTINCT project_id) as projects
-- FROM edges
-- GROUP BY source_id, target_id, relation
-- HAVING COUNT(*) > 1;

-- ============================================================================
-- SET lock_timeout for constraint operations
-- ============================================================================
SET lock_timeout = '5s';

-- ============================================================================
-- STEP 1: Recreate original indexes CONCURRENTLY (no table lock)
-- ============================================================================

-- Nodes: Recreate original unique index on (name) only
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_nodes_unique_original
    ON nodes(name);

-- Edges: Recreate original unique index on (source_id, target_id, relation)
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_unique_original
    ON edges(source_id, target_id, relation);

-- ============================================================================
-- STEP 2: Drop new composite constraints (brief ACCESS EXCLUSIVE lock)
-- ============================================================================

-- Drop new nodes constraint (includes project_id)
-- This also drops the associated index
ALTER TABLE nodes DROP CONSTRAINT IF EXISTS nodes_project_name_unique;

-- Drop new edges constraint (includes project_id)
-- This also drops the associated index
ALTER TABLE edges DROP CONSTRAINT IF EXISTS edges_project_unique;

-- ============================================================================
-- STEP 3: Recreate original constraints with original names (brief lock)
-- ============================================================================

-- Recreate original nodes constraint with original index and name
ALTER TABLE nodes
    ADD CONSTRAINT idx_nodes_unique
    UNIQUE USING INDEX idx_nodes_unique_original;

-- Recreate original edges constraint with original index and name
ALTER TABLE edges
    ADD CONSTRAINT idx_edges_unique
    UNIQUE USING INDEX idx_edges_unique_original;

-- ============================================================================
-- VERIFICATION QUERIES (run after rollback)
-- ============================================================================

-- Verify original constraints and indexes are restored
-- SELECT conname AS constraint_name, pg_get_constraintdef(oid) AS definition
-- FROM pg_constraint
-- WHERE conrelid::regclass IN ('nodes', 'edges')
--   AND contype = 'u'
-- ORDER BY conrelid::regclass::text;

-- Expected results:
--   idx_nodes_unique on (name)
--   idx_edges_unique on (source_id, target_id, relation)

-- Verify original indexes are restored
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('nodes', 'edges')
--   AND indexname IN ('idx_nodes_unique', 'idx_edges_unique')
-- ORDER BY tablename, indexname;

-- Expected results:
--   idx_nodes_unique on (name)
--   idx_edges_unique on (source_id, target_id, relation)

-- ============================================================================
-- CLEANUP
-- ============================================================================
RESET lock_timeout;

-- ============================================================================
-- IMPORTANT NOTES
-- ============================================================================
-- After this rollback:
--   - All entities must have globally unique names
--   - Cross-project duplicate names will violate constraints
--   - Any INSERT with duplicate names will fail
--
-- If you encounter constraint violations after rollback:
--   1. Identify duplicates using the pre-rollback validation queries
--   2. Either: re-apply migration 028 (fix-forward), or resolve duplicates manually
