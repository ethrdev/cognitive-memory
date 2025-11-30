-- Rollback Migration 012: Remove Graph Tables (Nodes + Edges)
-- Story 4.1: Graph Schema Migration Rollback
--
-- Reverses all changes from 012_add_graph_tables.sql
-- Order: DROP edges first (FK dependencies), then nodes
-- Note: gen_random_uuid() extension cleanup if no longer needed

-- ============================================================================
-- STEP 1: Verify tables exist before dropping (safety check)
-- ============================================================================

-- Uncomment to check tables exist before rollback
-- \echo "Checking if graph tables exist..."
-- SELECT 'nodes' AS table_name FROM pg_tables WHERE schemaname='public' AND tablename='nodes'
-- UNION ALL
-- SELECT 'edges' AS table_name FROM pg_tables WHERE schemaname='public' AND tablename='edges';

-- ============================================================================
-- STEP 2: DROP Foreign Key Constraints (explicit removal)
-- ============================================================================

-- Remove FK constraints from edges table
ALTER TABLE edges DROP CONSTRAINT IF EXISTS fk_edges_source_id RESTRICT;
ALTER TABLE edges DROP CONSTRAINT IF EXISTS fk_edges_target_id RESTRICT;

-- Remove FK constraint from nodes table
ALTER TABLE nodes DROP CONSTRAINT IF EXISTS fk_nodes_vector_id RESTRICT;

-- ============================================================================
-- STEP 3: DROP Indexes (explicit removal)
-- ============================================================================

-- Drop nodes table indexes
DROP INDEX IF EXISTS idx_nodes_unique;
DROP INDEX IF EXISTS idx_nodes_label;
DROP INDEX IF EXISTS idx_nodes_name;
DROP INDEX IF EXISTS idx_nodes_vector_id;
DROP INDEX IF EXISTS idx_nodes_properties;

-- Drop edges table indexes
DROP INDEX IF EXISTS idx_edges_unique;
DROP INDEX IF EXISTS idx_edges_source_id;
DROP INDEX IF EXISTS idx_edges_target_id;
DROP INDEX IF EXISTS idx_edges_relation;
DROP INDEX IF EXISTS idx_edges_weight;
DROP INDEX IF EXISTS idx_edges_properties;

-- ============================================================================
-- STEP 4: DROP Tables (order matters: edges first due to FK dependencies)
-- ============================================================================

-- Drop edges table first (depends on nodes)
DROP TABLE IF EXISTS edges CASCADE;

-- Drop nodes table
DROP TABLE IF EXISTS nodes CASCADE;

-- ============================================================================
-- STEP 5: Clean up gen_random_uuid() if no longer used (optional)
-- ============================================================================

-- Check if any other tables still use UUID columns before dropping extension
-- Uncomment only if you're certain no other tables use UUID columns
-- DO $$
-- BEGIN
--   IF NOT EXISTS (
--     SELECT 1 FROM information_schema.columns
--     WHERE data_type = 'uuid'
--     AND table_schema = 'public'
--     AND table_name NOT IN ('nodes', 'edges')
--   ) THEN
--     \echo "No remaining UUID columns found. Consider dropping pgcrypto extension."
--     -- DROP EXTENSION IF EXISTS pgcrypto;  -- Uncomment if safe
--   ELSE
--     \echo "UUID columns still exist in other tables. Keeping pgcrypto extension.";
--   END IF;
-- END $$;

-- ============================================================================
-- VERIFICATION (run after rollback)
-- ============================================================================

-- Verify tables are gone (should return 0 rows)
-- \echo "Verifying tables have been dropped..."
-- SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('nodes', 'edges');

-- Verify indexes are gone (should return 0 rows)
-- \echo "Verifying indexes have been dropped..."
-- SELECT indexname FROM pg_indexes WHERE schemaname='public' AND
--   indexname LIKE 'idx_%nodes%' OR indexname LIKE 'idx_%edges%';

\echo "Rollback completed successfully. Graph tables 'nodes' and 'edges' have been removed."