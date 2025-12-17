-- Migration 019: Add IEF Feedback Table for ICAI Calibration
-- Story 7.7: IEF (Integrative Evaluation Function) + ICAI
--
-- This table collects feedback on IEF search results to enable
-- automatic weight recalibration via the ICAI (Integrative Context
-- Assembly Interface) architecture.
--
-- Recalibration triggers after RECALIBRATION_THRESHOLD (50) feedbacks.

CREATE TABLE IF NOT EXISTS ief_feedback (
    id SERIAL PRIMARY KEY,
    query_id UUID NOT NULL DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    helpful BOOLEAN,  -- true/false/null - set by user
    feedback_reason TEXT,  -- Optional: "zu viele irrelevante Ergebnisse"
    constitutive_weight_used FLOAT NOT NULL DEFAULT 2.0,
    -- Additional context for calibration
    result_count INTEGER,
    conflict_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for calibration queries
CREATE INDEX IF NOT EXISTS idx_ief_feedback_helpful
ON ief_feedback(helpful)
WHERE helpful IS NOT NULL;

-- Index for time-based analysis
CREATE INDEX IF NOT EXISTS idx_ief_feedback_created_at
ON ief_feedback(created_at DESC);

COMMENT ON TABLE ief_feedback IS 'ICAI feedback collection for IEF weight recalibration (Story 7.7)';
COMMENT ON COLUMN ief_feedback.helpful IS 'User feedback: true=helpful, false=unhelpful, null=no feedback';
COMMENT ON COLUMN ief_feedback.constitutive_weight_used IS 'The constitutive_weight value used for this query (for calibration analysis)';
