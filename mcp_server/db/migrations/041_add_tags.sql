-- Migration 041: Add tags and metadata columns
-- Story: 9.1.1 - Tags Schema Migration
-- Date: 2026-02-11
-- Description: Adds TEXT[] tags column to episode_memory and l2_insights,
--              plus JSONB metadata column to episode_memory

-- =============================================================================
-- Phase 1: Add tags and metadata columns to episode_memory
-- =============================================================================

-- Add tags column (TEXT[] array)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'episode_memory' AND column_name = 'tags'
    ) THEN
        ALTER TABLE episode_memory ADD COLUMN tags TEXT[] DEFAULT '{}';
    END IF;
END $$;

COMMENT ON COLUMN episode_memory.tags IS
'Text array tags for structured retrieval (Epic 9). Enables deterministic filtering by user-defined categories.';

-- Add metadata column (JSONB)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'episode_memory' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE episode_memory ADD COLUMN metadata JSONB DEFAULT '{}';
    END IF;
END $$;

COMMENT ON COLUMN episode_memory.metadata IS
'Extensible JSONB metadata for future enhancements (Epic 9). Allows adding structured data without schema changes.';

-- =============================================================================
-- Phase 2: Add tags column to l2_insights
-- =============================================================================

-- Add tags column (TEXT[] array)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'l2_insights' AND column_name = 'tags'
    ) THEN
        ALTER TABLE l2_insights ADD COLUMN tags TEXT[] DEFAULT '{}';
    END IF;
END $$;

COMMENT ON COLUMN l2_insights.tags IS
'Text array tags for structured retrieval (Epic 9). Enables deterministic filtering by user-defined categories.';

-- =============================================================================
-- Phase 3: Create GIN indexes (CONCURRENTLY for zero-downtime deployment)
-- =============================================================================
-- IMPORTANT: CONCURRENTLY cannot be used inside a transaction block.
-- Run this migration outside of a transaction (e.g., psql --single-transaction).
-- If using a migration tool that wraps in transactions, create indexes separately.

-- Note: If you get "CREATE INDEX CONCURRENTLY cannot run inside a transaction block",
-- run these index creation statements separately after the migration completes.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_episode_memory_tags
ON episode_memory USING gin(tags);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_l2_insights_tags
ON l2_insights USING gin(tags);

-- =============================================================================
-- Verification Queries (commented - run manually to verify)
-- =============================================================================

-- Verify episode_memory columns
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'episode_memory' AND column_name IN ('tags', 'metadata');

-- Verify l2_insights columns
-- SELECT column_name, data_type, column_default
-- FROM information_schema.columns
-- WHERE table_name = 'l2_insights' AND column_name = 'tags';

-- Verify indexes were created
-- SELECT indexname, tablename, indexdef
-- FROM pg_indexes
-- WHERE indexname IN ('idx_episode_memory_tags', 'idx_l2_insights_tags');

-- Test empty array storage format
-- INSERT INTO episode_memory (query, reward, reflection, embedding, project_id, tags)
-- VALUES ('test', 0.5, 'test', '[0]'::vector, 'test-project', ARRAY[]::TEXT[])
-- RETURNING id, tags;
