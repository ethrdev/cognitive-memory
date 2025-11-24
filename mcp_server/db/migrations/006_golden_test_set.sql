-- Migration 006: Golden Test Set Table
-- : Golden Test Set Creation (separate von Ground Truth)
-- Date: 2025-11-18

-- =============================================================================
-- Golden Test Set Table
-- =============================================================================
-- Separate test set for daily Precision@5 regression tests and model drift
-- detection. Must NOT overlap with Ground Truth sessions to prevent overfitting.

CREATE TABLE IF NOT EXISTS golden_test_set (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    query_type VARCHAR(10) NOT NULL CHECK (query_type IN ('short', 'medium', 'long')),
    expected_docs INTEGER[] NOT NULL,
    session_id UUID,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Metadata
    word_count INTEGER,
    labeled_by VARCHAR(50) DEFAULT 'ethr',
    notes TEXT
);

-- =============================================================================
-- Indexes for Query Performance
-- =============================================================================

-- Index on query_type for stratification analysis
CREATE INDEX IF NOT EXISTS idx_golden_query_type
ON golden_test_set(query_type);

-- Index on created_at for temporal queries
CREATE INDEX IF NOT EXISTS idx_golden_created_at
ON golden_test_set(created_at);

-- Index on session_id for overlap verification
CREATE INDEX IF NOT EXISTS idx_golden_session_id
ON golden_test_set(session_id);

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE golden_test_set IS
'Separate test set for daily Precision@5 regression testing and model drift detection. Must be immutable after initial labeling.';

COMMENT ON COLUMN golden_test_set.query IS
'User query extracted from L0 Raw Memory (different sessions than Ground Truth)';

COMMENT ON COLUMN golden_test_set.query_type IS
'Query length classification: short (≤10 words), medium (11-29 words), long (≥30 words)';

COMMENT ON COLUMN golden_test_set.expected_docs IS
'Array of L2 Insight IDs that are relevant for this query (manually labeled)';

COMMENT ON COLUMN golden_test_set.session_id IS
'Original session_id from L0 Raw Memory - used to verify no overlap with Ground Truth';

COMMENT ON COLUMN golden_test_set.word_count IS
'Number of words in query (for classification verification)';

-- =============================================================================
-- Validation Query: Verify No Overlap with Ground Truth
-- =============================================================================

-- Run after Golden Test Set creation to ensure no overlap
-- Expected result: 0 rows (no overlap)
--
-- SELECT COUNT(*) as overlap_count
-- FROM golden_test_set gts
-- INNER JOIN ground_truth gt ON gts.session_id = gt.session_id;
