-- Rollback Migration 041: Remove tags and metadata columns
-- Story: 9.1.1 - Tags Schema Migration (Rollback)
-- Date: 2026-02-11
-- WARNING: This will permanently delete all tag and metadata data!

-- =============================================================================
-- Phase 1: Drop GIN indexes
-- =============================================================================

DROP INDEX IF EXISTS idx_episode_memory_tags;
DROP INDEX IF EXISTS idx_l2_insights_tags;

-- =============================================================================
-- Phase 2: Drop columns (in reverse order of creation)
-- =============================================================================

-- From l2_insights
ALTER TABLE l2_insights DROP COLUMN IF EXISTS tags;

-- From episode_memory (reverse order: metadata first, then tags)
ALTER TABLE episode_memory DROP COLUMN IF EXISTS metadata;
ALTER TABLE episode_memory DROP COLUMN IF EXISTS tags;

-- =============================================================================
-- Verification Queries (commented - run manually to verify)
-- =============================================================================

-- Verify columns were dropped
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name IN ('episode_memory', 'l2_insights')
-- AND column_name IN ('tags', 'metadata');
-- Expected: empty result set

-- Verify indexes were dropped
-- SELECT indexname, tablename
-- FROM pg_indexes
-- WHERE indexname IN ('idx_episode_memory_tags', 'idx_l2_insights_tags');
-- Expected: empty result set
