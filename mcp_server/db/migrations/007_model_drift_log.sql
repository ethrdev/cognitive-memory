-- Migration 007: Model Drift Log Table
-- Story 3.2: Model Drift Detection mit Daily Golden Test
-- Date: 2025-11-18

-- =============================================================================
-- Model Drift Log Table
-- =============================================================================
-- Daily tracking of Golden Test Set Precision@5 metrics for API drift detection.
-- Enables early detection of Embedding Model updates or Haiku API changes.

CREATE TABLE IF NOT EXISTS model_drift_log (
    date DATE PRIMARY KEY,
    precision_at_5 FLOAT NOT NULL CHECK (precision_at_5 BETWEEN 0.0 AND 1.0),
    num_queries INTEGER NOT NULL CHECK (num_queries > 0),
    avg_retrieval_time FLOAT,
    embedding_model_version VARCHAR(50),
    drift_detected BOOLEAN DEFAULT FALSE NOT NULL,
    baseline_p5 FLOAT CHECK (baseline_p5 IS NULL OR (baseline_p5 BETWEEN 0.0 AND 1.0)),
    created_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- Indexes for Query Performance
-- =============================================================================

-- Index on date (DESC) for fast recent queries and 7-day rolling average
CREATE INDEX IF NOT EXISTS idx_drift_date
ON model_drift_log(date DESC);

-- Index on drift_detected for alert queries
CREATE INDEX IF NOT EXISTS idx_drift_detected
ON model_drift_log(drift_detected) WHERE drift_detected = TRUE;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE model_drift_log IS
'Daily Precision@5 metrics from Golden Test Set execution for model drift detection and API change monitoring.';

COMMENT ON COLUMN model_drift_log.date IS
'Date of Golden Test execution (PRIMARY KEY enforces one entry per day)';

COMMENT ON COLUMN model_drift_log.precision_at_5 IS
'Macro-average Precision@5 across all Golden Test queries (0.0-1.0)';

COMMENT ON COLUMN model_drift_log.num_queries IS
'Number of queries tested from Golden Test Set (expected 50-100)';

COMMENT ON COLUMN model_drift_log.avg_retrieval_time IS
'Average hybrid_search latency in milliseconds across all queries';

COMMENT ON COLUMN model_drift_log.embedding_model_version IS
'OpenAI Embedding Model version from API response headers (for tracking model updates)';

COMMENT ON COLUMN model_drift_log.drift_detected IS
'TRUE if Precision@5 dropped >5% (absolute) compared to 7-day rolling average baseline';

COMMENT ON COLUMN model_drift_log.baseline_p5 IS
'7-day rolling average baseline used for drift detection (NULL if <7 days of data exist)';

COMMENT ON COLUMN model_drift_log.created_at IS
'Timestamp when this entry was created (for audit trail)';

-- =============================================================================
-- Validation Queries
-- =============================================================================

-- Query 1: Check for duplicate entries (should return 0)
-- Expected: 0 rows (date PRIMARY KEY enforces uniqueness)
--
-- SELECT date, COUNT(*) as count
-- FROM model_drift_log
-- GROUP BY date
-- HAVING COUNT(*) > 1;

-- Query 2: Verify drift detection logic
-- Expected: drift_detected TRUE when (baseline_p5 - precision_at_5) > 0.05
--
-- SELECT date, precision_at_5, baseline_p5,
--        (baseline_p5 - precision_at_5) as drop,
--        drift_detected
-- FROM model_drift_log
-- WHERE drift_detected = TRUE;

-- Query 3: View recent 7-day trend
-- Expected: 7 rows (or fewer if <7 days of data)
--
-- SELECT date, precision_at_5, drift_detected, baseline_p5
-- FROM model_drift_log
-- WHERE date >= CURRENT_DATE - INTERVAL '7 days'
-- ORDER BY date DESC;

-- Query 4: Calculate current 7-day rolling average
-- Expected: Single row with average P@5 over last 7 days
--
-- SELECT AVG(precision_at_5) as rolling_7day_avg,
--        MIN(precision_at_5) as min_p5,
--        MAX(precision_at_5) as max_p5,
--        COUNT(*) as days_of_data
-- FROM model_drift_log
-- WHERE date >= CURRENT_DATE - INTERVAL '7 days';
