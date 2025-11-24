-- Migration 002: Dual Judge Schema Updates for 
--  - Dual Judge Implementation mit GPT-4o + Haiku
--
-- Changes:
-- 1. Fix ground_truth.judge1_score/judge2_score: FLOAT → FLOAT[] for arrays
-- 2. Add api_cost_log table for API cost tracking

-- ============================================================================
-- CHANGE 1: Update ground_truth table for array scores
-- ============================================================================

-- Note: PostgreSQL handles ALTER TABLE TYPE changes differently for arrays
-- We need to drop and recreate columns to change from FLOAT to FLOAT[]

-- Drop existing columns (will lose any existing data)
ALTER TABLE ground_truth DROP COLUMN IF EXISTS judge1_score;
ALTER TABLE ground_truth DROP COLUMN IF EXISTS judge2_score;

-- Add new array columns
ALTER TABLE ground_truth ADD COLUMN judge1_score FLOAT[];
ALTER TABLE ground_truth ADD COLUMN judge2_score FLOAT[];

-- ============================================================================
-- CHANGE 2: Create api_cost_log table for cost tracking
-- ============================================================================

CREATE TABLE api_cost_log (
    id SERIAL PRIMARY KEY,
    api_name VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_eur DECIMAL(10, 4),
    query_id INTEGER REFERENCES ground_truth(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for cost queries
CREATE INDEX idx_api_cost_created ON api_cost_log(created_at DESC);
CREATE INDEX idx_api_cost_query ON api_cost_log(query_id);

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Verify ground_truth table has correct columns (should return FLOAT[] types)
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name='ground_truth' AND column_name IN ('judge1_score', 'judge2_score');

-- Verify api_cost_log table exists (should return 1 row)
-- SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename='api_cost_log';

-- Verify api_cost_log indexes exist (should return 2 rows)
-- SELECT indexname FROM pg_indexes WHERE schemaname='public' AND
--   indexname IN ('idx_api_cost_created', 'idx_api_cost_query');
