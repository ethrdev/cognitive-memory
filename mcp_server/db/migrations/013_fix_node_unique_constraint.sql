-- Migration 013: Fix Node Unique Constraint (name only, not label+name)
-- Bug Fix: graph_add_edge creates duplicate nodes instead of reusing existing ones
--
-- Problem: UNIQUE INDEX on (label, name) means nodes with same name but different
--          labels are treated as different nodes. This breaks graph_add_edge auto-upsert
--          when source_label differs from original node's label.
--
-- Solution: UNIQUE only on (name) - nodes are globally unique by name
--           Labels become mutable attributes, not part of identity
--
-- Trade-off: Homonyms must be explicitly named (e.g., "Apple-Company" vs "Apple-Fruit")

-- ============================================================================
-- STEP 1: Drop existing unique constraint on (label, name)
-- ============================================================================
DROP INDEX IF EXISTS idx_nodes_unique;

-- ============================================================================
-- STEP 2: Create new unique constraint on (name) only
-- ============================================================================
-- Note: This will fail if duplicate names exist with different labels
-- Run cleanup query first if needed:
--   SELECT name, COUNT(*) FROM nodes GROUP BY name HAVING COUNT(*) > 1;
CREATE UNIQUE INDEX idx_nodes_unique ON nodes(name);

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Verify new index exists with correct column
-- SELECT indexname, indexdef FROM pg_indexes
-- WHERE tablename = 'nodes' AND indexname = 'idx_nodes_unique';

-- Test idempotent insert behavior (should update label, not create new node)
-- INSERT INTO nodes (label, name) VALUES ('TypeA', 'TestUnique')
-- ON CONFLICT (name) DO UPDATE SET label = EXCLUDED.label
-- RETURNING id, label, name;
--
-- INSERT INTO nodes (label, name) VALUES ('TypeB', 'TestUnique')
-- ON CONFLICT (name) DO UPDATE SET label = EXCLUDED.label
-- RETURNING id, label, name;
-- Should return SAME id with label='TypeB'
