-- Rollback Migration 029: Remove Composite Indexes
-- Story 11.1.4: Composite Indexes for RLS Performance
--
-- WARNING: Only run if Story 11.1.4 needs to be rolled back
-- This removes performance optimization indexes but doesn't affect data
--
-- Safe to rollback at any time (no data changes)
-- RLS queries will be slower without these indexes
-- Can re-run migration 029 to restore indexes

-- ============================================================================
-- DROP SINGLE-COLUMN project_id INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_nodes_project_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_edges_project_id;
DROP INDEX CONCURRENTLY IF EXISTS idx_l2_insights_project_id;

-- ============================================================================
-- DROP COMPOSITE FOREIGN KEY INDEXES
-- ============================================================================

DROP INDEX CONCURRENTLY IF EXISTS idx_edges_source_project;
DROP INDEX CONCURRENTLY IF EXISTS idx_edges_target_project;
DROP INDEX CONCURRENTLY IF EXISTS idx_l2_insights_node_project;

-- ============================================================================
-- VERIFICATION (uncomment to verify)
-- ============================================================================

-- Verify indexes are removed
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('nodes', 'edges', 'l2_insights')
--   AND indexname LIKE '%project%'
-- ORDER BY tablename, indexname;
--
-- Expected: No rows returned (all project_id indexes removed)
