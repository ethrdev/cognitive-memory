-- Migration 037 Rollback: RLS Policies for Support Tables
-- Story 11.3.4: RLS Policies for Support Tables
--
-- Purpose: Rollback RLS policies on support tables (working_memory, episode_memory, l0_raw,
--          ground_truth, smf_proposals, stale_memory)
-- Risk: MEDIUM - Removes RLS enforcement
-- This migration is idempotent - safe to run multiple times

SET lock_timeout = '5s';

-- ============================================================================
-- DROP WORKING_MEMORY POLICIES
-- ============================================================================

DROP POLICY IF EXISTS delete_working_memory ON working_memory;
DROP POLICY IF EXISTS update_working_memory ON working_memory;
DROP POLICY IF EXISTS insert_working_memory ON working_memory;
DROP POLICY IF EXISTS select_working_memory ON working_memory;
DROP POLICY IF EXISTS require_project_id ON working_memory;

-- Disable ROW LEVEL SECURITY on working_memory
ALTER TABLE working_memory NO FORCE ROW LEVEL SECURITY;
ALTER TABLE working_memory DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- DROP EPISODE_MEMORY POLICIES
-- ============================================================================

DROP POLICY IF EXISTS delete_episode_memory ON episode_memory;
DROP POLICY IF EXISTS update_episode_memory ON episode_memory;
DROP POLICY IF EXISTS insert_episode_memory ON episode_memory;
DROP POLICY IF EXISTS select_episode_memory ON episode_memory;
DROP POLICY IF EXISTS require_project_id ON episode_memory;

-- Disable ROW LEVEL SECURITY on episode_memory
ALTER TABLE episode_memory NO FORCE ROW LEVEL SECURITY;
ALTER TABLE episode_memory DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- DROP L0_RAW POLICIES
-- ============================================================================

DROP POLICY IF EXISTS delete_l0_raw ON l0_raw;
DROP POLICY IF EXISTS update_l0_raw ON l0_raw;
DROP POLICY IF EXISTS insert_l0_raw ON l0_raw;
DROP POLICY IF EXISTS select_l0_raw ON l0_raw;
DROP POLICY IF EXISTS require_project_id ON l0_raw;

-- Disable ROW LEVEL SECURITY on l0_raw
ALTER TABLE l0_raw NO FORCE ROW LEVEL SECURITY;
ALTER TABLE l0_raw DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- DROP GROUND_TRUTH POLICIES
-- ============================================================================

DROP POLICY IF EXISTS delete_ground_truth ON ground_truth;
DROP POLICY IF EXISTS update_ground_truth ON ground_truth;
DROP POLICY IF EXISTS insert_ground_truth ON ground_truth;
DROP POLICY IF EXISTS select_ground_truth ON ground_truth;
DROP POLICY IF EXISTS require_project_id ON ground_truth;

-- Disable ROW LEVEL SECURITY on ground_truth
ALTER TABLE ground_truth NO FORCE ROW LEVEL SECURITY;
ALTER TABLE ground_truth DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- DROP SMF_PROPOSALS POLICIES
-- ============================================================================

DROP POLICY IF EXISTS delete_smf_proposals ON smf_proposals;
DROP POLICY IF EXISTS update_smf_proposals ON smf_proposals;
DROP POLICY IF EXISTS insert_smf_proposals ON smf_proposals;
DROP POLICY IF EXISTS select_smf_proposals ON smf_proposals;
DROP POLICY IF EXISTS require_project_id ON smf_proposals;

-- Disable ROW LEVEL SECURITY on smf_proposals
ALTER TABLE smf_proposals NO FORCE ROW LEVEL SECURITY;
ALTER TABLE smf_proposals DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- DROP STALE_MEMORY POLICIES
-- ============================================================================

DROP POLICY IF EXISTS delete_stale_memory ON stale_memory;
DROP POLICY IF EXISTS update_stale_memory ON stale_memory;
DROP POLICY IF EXISTS insert_stale_memory ON stale_memory;
DROP POLICY IF EXISTS select_stale_memory ON stale_memory;
DROP POLICY IF EXISTS require_project_id ON stale_memory;

-- Disable ROW LEVEL SECURITY on stale_memory
ALTER TABLE stale_memory NO FORCE ROW LEVEL SECURITY;
ALTER TABLE stale_memory DISABLE ROW LEVEL SECURITY;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify RLS is disabled on all support tables (rowsecurity should be false)
-- SELECT tablename, rowsecurity AS rls_enabled, forcerowsecurity AS force_rls
-- FROM pg_tables WHERE schemaname='public'
-- AND tablename IN ('working_memory', 'episode_memory', 'l0_raw', 'ground_truth', 'smf_proposals', 'stale_memory');

-- Verify no policies exist on support tables (should return 0 rows)
-- SELECT schemaname, tablename, policyname
-- FROM pg_policies WHERE schemaname='public'
-- AND tablename IN ('working_memory', 'episode_memory', 'l0_raw', 'ground_truth', 'smf_proposals', 'stale_memory');

RESET lock_timeout;
