-- Migration 025: Create insight_feedback table for Context Critic
-- Story 26.4: Context Critic
--
-- Purpose: Store feedback about specific L2 insights to enable IEF score adjustments
-- Dependencies: Migration 001 (l2_insights table must exist)
-- Breaking Changes: KEINE - New table, migration is idempotent
--
-- NOTE: Named 'insight_feedback' NOT 'ief_feedback' to avoid conflict with
-- Story 7.7's ief_feedback table (used for ICAI recalibration with different schema).
-- Story 7.7 uses: query_id, query_text, helpful, feedback_reason, constitutive_weight_used
-- Story 26.4 uses: insight_id, feedback_type, context, created_at
-- These are SEPARATE concepts and should have separate tables.
--
-- Feedback Types:
--   - helpful: Positive feedback (+0.1 weight boost)
--   - not_relevant: Negative feedback (-0.1 weight reduction)
--   - not_now: Neutral feedback (no score effect)
--
-- ============================================================================
-- PHASE 1: SCHEMA MIGRATION - Create insight_feedback Table
-- ============================================================================

-- Table: insight_feedback - Store feedback for Context Critic feature
-- Stores user feedback about whether recalled L2 insights were helpful
CREATE TABLE IF NOT EXISTS insight_feedback (
    id SERIAL PRIMARY KEY,
    insight_id INTEGER NOT NULL REFERENCES l2_insights(id),
    feedback_type VARCHAR(20) NOT NULL CHECK (feedback_type IN ('helpful', 'not_relevant', 'not_now')),
    context TEXT,  -- Optional context for why feedback was given
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- PHASE 2: PERFORMANCE OPTIMIZATION - Create Indexes
-- ============================================================================

-- Index for fast lookups during IEF calculation
-- Most common query: "SELECT feedback_type FROM insight_feedback WHERE insight_id = $1"
CREATE INDEX IF NOT EXISTS idx_insight_feedback_insight_id
    ON insight_feedback(insight_id);

-- Index for time-based analysis and cleanup
-- Query: "SELECT * FROM insight_feedback ORDER BY created_at DESC LIMIT X"
CREATE INDEX IF NOT EXISTS idx_insight_feedback_created_at
    ON insight_feedback(created_at DESC);

-- ============================================================================
-- PHASE 3: DATA VALIDATION - Verify Table Creation
-- ============================================================================

-- Verification query (can be run manually):
-- SELECT
--     COUNT(*) as total_feedback,
--     COUNT(DISTINCT insight_id) as unique_insights,
--     COUNT(CASE WHEN feedback_type = 'helpful' THEN 1 END) as helpful_count,
--     COUNT(CASE WHEN feedback_type = 'not_relevant' THEN 1 END) as not_relevant_count,
--     COUNT(CASE WHEN feedback_type = 'not_now' THEN 1 END) as not_now_count
-- FROM insight_feedback;

-- Sample queries to verify table structure:
-- SELECT column_name, data_type, is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'insight_feedback'
-- ORDER BY ordinal_position;

-- ============================================================================
-- PHASE 4: ROLLBACK - DOWN Migration (for rollback scenario)
-- ============================================================================

-- For rollback: Remove indexes first, then table
-- DROP INDEX IF EXISTS idx_insight_feedback_insight_id;
-- DROP INDEX IF EXISTS idx_insight_feedback_created_at;
-- DROP TABLE IF EXISTS insight_feedback;

-- ============================================================================
-- UP-DOWN-UP CYCLE TEST (for Migration 025 Test Suite)
-- ============================================================================
-- Test Sequence:
--   1. UP: Migration ausführen (späterer Test)
--   2. VERIFY: insight_feedback table exists with correct columns
--   3. VERIFY: idx_insight_feedback_insight_id exists
--   4. VERIFY: idx_insight_feedback_created_at exists
--   5. VERIFY: CHECK constraint works on feedback_type
--   6. DOWN: Rollback ausführen
--   7. VERIFY: Table and indexes removed
--   8. UP: Migration erneut ausführen
--   9. VERIFY: Table and indexes recreated, idempotent
