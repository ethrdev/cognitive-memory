-- Migration 029: Add Composite Indexes for RLS Performance
-- Story 11.1.4: Composite Indexes for RLS Performance
--
-- Purpose: Add composite indexes with project_id as first column
--          to ensure efficient query performance for RLS-filtered queries
-- Dependencies: Migration 028 (unique constraints must exist)
-- Risk: LOW - CONCURRENTLY pattern prevents long locks
-- Rollback: 029_add_composite_indexes_rollback.sql
--
-- Why These Indexes:
--   - All indexes for RLS-protected tables MUST have project_id as the first column
--   - Single-column project_id indexes enable efficient filtering for simple project-scoped queries
--   - Composite indexes support foreign key lookups with project filtering
--   - CONCURRENTLY creation ensures zero-downtime deployment

-- ============================================================================
-- SET lock_timeout for safety
-- ============================================================================
SET lock_timeout = '5s';

-- ============================================================================
-- SINGLE-COLUMN project_id INDEXES
-- ============================================================================
-- These indexes enable efficient WHERE project_id = ? queries

-- Nodes table: Simple project filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_nodes_project_id
    ON nodes(project_id);

-- Edges table: Simple project filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_project_id
    ON edges(project_id);

-- L2 insights table: Simple project filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_l2_insights_project_id
    ON l2_insights(project_id);

-- ============================================================================
-- COMPOSITE FOREIGN KEY INDEXES
-- ============================================================================
-- These indexes support JOIN queries that filter by project_id

-- Edges foreign key indexes with project_id
-- Pattern: SELECT * FROM edges WHERE project_id = ? AND source_id = ?
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_source_project
    ON edges(project_id, source_id);

-- Pattern: SELECT * FROM edges WHERE project_id = ? AND target_id = ?
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_edges_target_project
    ON edges(project_id, target_id);

-- L2 insights foreign key index with project_id
-- Pattern: SELECT * FROM l2_insights WHERE project_id = ? AND node_id = ?
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_l2_insights_node_project
    ON l2_insights(project_id, node_id);

-- ============================================================================
-- VERIFICATION QUERIES (uncomment to verify)
-- ============================================================================

-- Check index creation
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN ('nodes', 'edges', 'l2_insights')
--   AND indexname LIKE '%project%'
-- ORDER BY tablename, indexname;
--
-- Expected results:
--   idx_edges_project_id         | CREATE INDEX idx_edges_project_id ON edges USING btree (project_id)
--   idx_edges_source_project     | CREATE INDEX idx_edges_source_project ON edges USING btree (project_id, source_id)
--   idx_edges_target_project     | CREATE INDEX idx_edges_target_project ON edges USING btree (project_id, target_id)
--   idx_l2_insights_node_project | CREATE INDEX idx_l2_insights_node_project ON l2_insights USING btree (project_id, node_id)
--   idx_l2_insights_project_id   | CREATE INDEX idx_l2_insights_project_id ON l2_insights USING btree (project_id)
--   idx_nodes_project_id         | CREATE INDEX idx_nodes_project_id ON nodes USING btree (project_id)

-- Verify index is valid (not invalid from failed CONCURRENTLY)
-- SELECT indexrelid::regclass AS index_name, indisvalid
-- FROM pg_index
-- WHERE indexrelid::regclass::text LIKE '%project%'
--   AND indexrelid::regclass::text LIKE 'idx_%';
--
-- All indisvalid should be TRUE

-- ============================================================================
-- CLEANUP
-- ============================================================================
RESET lock_timeout;
