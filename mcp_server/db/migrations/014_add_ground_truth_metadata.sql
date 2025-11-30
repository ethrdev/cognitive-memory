-- Migration 014: Add metadata column to ground_truth table
--
-- Bug Fix #5: store_dual_judge_scores fails with "column metadata does not exist"
-- Root Cause: The metadata column was referenced in code but never added to the schema
--
-- Date: 2025-11-30

-- Add metadata column to ground_truth table
ALTER TABLE ground_truth ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- ============================================================================
-- VERIFICATION QUERIES (run after migration)
-- ============================================================================

-- Verify metadata column exists (should return 1 row with 'jsonb' type)
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name='ground_truth' AND column_name='metadata';
