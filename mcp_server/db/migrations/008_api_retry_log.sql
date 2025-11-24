-- Migration 008: API Retry Log Table
-- Story 3.3: API Retry-Logic Enhancement mit Exponential Backoff
-- Date: 2025-11-18

-- =============================================================================
-- API Retry Log Table
-- =============================================================================
-- Tracks retry attempts for all external API calls (OpenAI, Anthropic).
-- Enables analysis of API stability, retry patterns, and transient failure rates.
-- Used for observability and cost analysis (retry overhead tracking).

CREATE TABLE IF NOT EXISTS api_retry_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    api_name VARCHAR(50) NOT NULL,
    error_type VARCHAR(100),
    retry_count INTEGER NOT NULL CHECK (retry_count BETWEEN 1 AND 4),
    success BOOLEAN NOT NULL
);

-- =============================================================================
-- Indexes for Query Performance
-- =============================================================================

-- Index on timestamp (DESC) for fast recent queries and time-based analysis
-- Supports queries like: "Zeige mir Retry-Statistiken letzte 7 Tage"
CREATE INDEX IF NOT EXISTS idx_retry_timestamp
ON api_retry_log(timestamp DESC);

-- Index on api_name for per-API stability analysis
-- Supports queries filtering by specific APIs (e.g., WHERE api_name = 'haiku_eval')
CREATE INDEX IF NOT EXISTS idx_retry_api
ON api_retry_log(api_name);

-- Partial index on failed retries for fast failure analysis
-- Only indexes rows where success = FALSE (final failures)
-- Supports queries like: "Zeige mir alle Failed Final Retries"
CREATE INDEX IF NOT EXISTS idx_retry_failure
ON api_retry_log(success) WHERE success = FALSE;

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE api_retry_log IS
'Retry attempt tracking for external APIs (OpenAI Embeddings, Haiku Evaluation/Reflexion, Dual Judge). Logs all retry attempts (1-4) with success/failure status for observability and cost analysis.';

COMMENT ON COLUMN api_retry_log.id IS
'Auto-incrementing primary key (allows multiple retries per API call)';

COMMENT ON COLUMN api_retry_log.timestamp IS
'Timestamp when retry attempt was made (TIMESTAMPTZ for timezone awareness)';

COMMENT ON COLUMN api_retry_log.api_name IS
'API being called: openai_embeddings | haiku_eval | haiku_reflexion | gpt4o_judge | haiku_judge';

COMMENT ON COLUMN api_retry_log.error_type IS
'Human-readable error type: 429_rate_limit | 503_service_unavailable | timeout | network_error | connection_error';

COMMENT ON COLUMN api_retry_log.retry_count IS
'Retry attempt number (1-4). retry_count=1 means first retry after initial failure, retry_count=4 means final retry attempt.';

COMMENT ON COLUMN api_retry_log.success IS
'TRUE if this retry attempt succeeded (operation completed successfully). FALSE if this was the final failure (all retries exhausted).';

-- =============================================================================
-- Validation Queries
-- =============================================================================

-- Query 1: View retry statistics for last 7 days
-- Expected: All retry attempts grouped by API, showing success rate
--
-- SELECT api_name,
--        COUNT(*) as total_retries,
--        SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_retries,
--        SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failed_retries,
--        ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct
-- FROM api_retry_log
-- WHERE timestamp >= NOW() - INTERVAL '7 days'
-- GROUP BY api_name
-- ORDER BY total_retries DESC;

-- Query 2: View failed final retries (all 4 attempts exhausted)
-- Expected: Only entries where success=FALSE (final failures after 4 retries)
--
-- SELECT timestamp, api_name, error_type, retry_count
-- FROM api_retry_log
-- WHERE success = FALSE
-- ORDER BY timestamp DESC
-- LIMIT 20;

-- Query 3: Analyze retry patterns by error type
-- Expected: Breakdown of which errors trigger most retries
--
-- SELECT error_type,
--        COUNT(*) as occurrences,
--        AVG(retry_count) as avg_retry_attempts,
--        SUM(CASE WHEN success THEN 1 ELSE 0 END) as recovered_count
-- FROM api_retry_log
-- WHERE timestamp >= NOW() - INTERVAL '7 days'
-- GROUP BY error_type
-- ORDER BY occurrences DESC;

-- Query 4: Check for constraint violations (should return 0)
-- Expected: 0 rows (retry_count must be 1-4)
--
-- SELECT id, retry_count
-- FROM api_retry_log
-- WHERE retry_count < 1 OR retry_count > 4;

-- Query 5: Recent retry timeline (last 100 entries)
-- Expected: Chronological view of all recent retry attempts
--
-- SELECT timestamp, api_name, error_type, retry_count, success
-- FROM api_retry_log
-- ORDER BY timestamp DESC
-- LIMIT 100;
