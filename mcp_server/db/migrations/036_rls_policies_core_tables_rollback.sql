-- Migration 036 Rollback: RLS Policies for Core Tables
-- Story 11.3.3: RLS Policies for Core Tables
--
-- Purpose: Rollback RLS policies on core tables (l2_insights, nodes, edges)
-- Risk: MEDIUM - Removes RLS enforcement
-- This migration is idempotent - safe to run multiple times

SET lock_timeout = '5s';

-- ============================================================================
-- DROP L2_INSIGHTS POLICIES
-- ============================================================================

-- Drop policies in reverse order of creation (optional but clean)
DROP POLICY IF EXISTS delete_l2_insights ON l2_insights;
DROP POLICY IF EXISTS update_l2_insights ON l2_insights;
DROP POLICY IF EXISTS insert_l2_insights ON l2_insights;
DROP POLICY IF EXISTS select_l2_insights ON l2_insights;
DROP POLICY IF EXISTS require_project_id ON l2_insights;

-- Disable ROW LEVEL SECURITY on l2_insights
ALTER TABLE l2_insights NO FORCE ROW LEVEL SECURITY;
ALTER TABLE l2_insights DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- DROP NODES POLICIES
-- ============================================================================

DROP POLICY IF EXISTS delete_nodes ON nodes;
DROP POLICY IF EXISTS update_nodes ON nodes;
DROP POLICY IF EXISTS insert_nodes ON nodes;
DROP POLICY IF EXISTS select_nodes ON nodes;
DROP POLICY IF EXISTS require_project_id ON nodes;

-- Disable ROW LEVEL SECURITY on nodes
ALTER TABLE nodes NO FORCE ROW LEVEL SECURITY;
ALTER TABLE nodes DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- DROP EDGES POLICIES
-- ============================================================================

DROP POLICY IF EXISTS delete_edges ON edges;
DROP POLICY IF EXISTS update_edges ON edges;
DROP POLICY IF EXISTS insert_edges ON edges;
DROP POLICY IF EXISTS select_edges ON edges;
DROP POLICY IF EXISTS require_project_id ON edges;

-- Disable ROW LEVEL SECURITY on edges
ALTER TABLE edges NO FORCE ROW LEVEL SECURITY;
ALTER TABLE edges DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify RLS is disabled on all core tables (rowsecurity should be false)
-- SELECT tablename, rowsecurity AS rls_enabled, forcerowsecurity AS force_rls
-- FROM pg_tables WHERE schemaname='public' AND tablename IN ('l2_insights', 'nodes', 'edges');

-- Verify no policies exist on core tables (should return 0 rows)
-- SELECT schemaname, tablename, policyname
-- FROM pg_policies WHERE schemaname='public' AND tablename IN ('l2_insights', 'nodes', 'edges');

RESET lock_timeout;
