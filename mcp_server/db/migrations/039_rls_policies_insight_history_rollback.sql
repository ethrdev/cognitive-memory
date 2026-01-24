-- Migration 039 Rollback: RLS Policies for l2_insight_history Table
-- Story 11.6.3: Insight Read Operations

SET lock_timeout = '5s';

-- Drop all policies on l2_insight_history
DROP POLICY IF EXISTS require_project_id ON l2_insight_history;
DROP POLICY IF EXISTS select_l2_insight_history ON l2_insight_history;
DROP POLICY IF EXISTS insert_l2_insight_history ON l2_insight_history;

-- Disable RLS on l2_insight_history
ALTER TABLE l2_insight_history NO FORCE ROW LEVEL SECURITY;
ALTER TABLE l2_insight_history DISABLE ROW LEVEL SECURITY;

RESET lock_timeout;
