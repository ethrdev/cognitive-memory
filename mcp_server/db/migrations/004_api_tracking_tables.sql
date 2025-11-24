-- Migration 004: API Cost and Retry Tracking Tables
-- : External API Setup für Haiku (Evaluation + Reflexion)
-- Date: 2025-11-16
--
-- Purpose:
--   - Cost tracking for all external API calls (Haiku, GPT-4o, OpenAI Embeddings)
--   - Retry statistics for monitoring API reliability
--   - Budget alert support (monthly cost projection)
--
-- Tables:
--   1. api_cost_log: Cost tracking with daily/monthly aggregation
--   2. api_retry_log: Retry attempt statistics for reliability monitoring

-- ============================================================================
-- Table 1: api_cost_log
-- ============================================================================
-- Tracks costs for all external API calls to enable:
-- - Daily/monthly cost aggregation
-- - Budget alerts (projected monthly >€10/mo threshold)
-- - Per-API cost breakdown (haiku_eval, haiku_refl, openai_embed, gpt4o_judge)

CREATE TABLE IF NOT EXISTS api_cost_log (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    api_name VARCHAR(50) NOT NULL,     -- 'haiku_eval' | 'haiku_refl' | 'openai_embed' | 'gpt4o_judge'
    num_calls INTEGER NOT NULL DEFAULT 1,
    token_count INTEGER,                -- Total tokens (input + output)
    estimated_cost FLOAT NOT NULL,      -- Cost in EUR (€)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast date-based queries (daily/monthly aggregation)
CREATE INDEX idx_api_cost_date ON api_cost_log(date DESC);

-- Index for per-API cost breakdown
CREATE INDEX idx_api_cost_name ON api_cost_log(api_name, date DESC);

-- Comments for documentation
COMMENT ON TABLE api_cost_log IS 'Cost tracking for external API calls (Haiku, GPT-4o, OpenAI Embeddings)';
COMMENT ON COLUMN api_cost_log.api_name IS 'API identifier: haiku_eval, haiku_refl, openai_embed, gpt4o_judge, haiku_judge';
COMMENT ON COLUMN api_cost_log.token_count IS 'Total tokens used (input + output combined)';
COMMENT ON COLUMN api_cost_log.estimated_cost IS 'Estimated cost in EUR based on API pricing';

-- ============================================================================
-- Table 2: api_retry_log
-- ============================================================================
-- Logs retry attempts for monitoring API reliability and identifying:
-- - Unstable APIs (high retry rates)
-- - Retry pattern effectiveness
-- - Network/service issues

CREATE TABLE IF NOT EXISTS api_retry_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    api_name VARCHAR(50) NOT NULL,      -- 'haiku_eval' | 'haiku_refl' | 'openai_embed' | 'gpt4o_judge'
    error_type VARCHAR(100),             -- Exception class name (e.g., 'RateLimitError', 'TimeoutError')
    retry_count INTEGER,                 -- Which retry attempt (1-4)
    success BOOLEAN NOT NULL,            -- Did the retry ultimately succeed?
    delay_seconds FLOAT                  -- Delay before this retry (with jitter applied)
);

-- Index for analyzing retry patterns by API
CREATE INDEX idx_api_retry_name ON api_retry_log(api_name, timestamp DESC);

-- Index for analyzing retry outcomes
CREATE INDEX idx_api_retry_success ON api_retry_log(success, timestamp DESC);

-- Comments for documentation
COMMENT ON TABLE api_retry_log IS 'Retry attempt statistics for external API reliability monitoring';
COMMENT ON COLUMN api_retry_log.error_type IS 'Exception type that triggered retry (e.g., RateLimitError, TimeoutError)';
COMMENT ON COLUMN api_retry_log.retry_count IS 'Retry attempt number (1-4 based on exponential backoff)';
COMMENT ON COLUMN api_retry_log.success IS 'Whether the operation ultimately succeeded after retries';
COMMENT ON COLUMN api_retry_log.delay_seconds IS 'Actual delay before retry (includes ±20% jitter)';

-- ============================================================================
-- Helper View: Daily Cost Summary
-- ============================================================================
-- Convenient view for daily cost monitoring and budget alerts

CREATE OR REPLACE VIEW daily_api_costs AS
SELECT
    date,
    SUM(estimated_cost) as total_cost,
    SUM(estimated_cost) * 30 as projected_monthly_cost,
    COUNT(DISTINCT api_name) as apis_used,
    SUM(num_calls) as total_calls,
    SUM(token_count) as total_tokens
FROM api_cost_log
GROUP BY date
ORDER BY date DESC;

COMMENT ON VIEW daily_api_costs IS 'Daily API cost summary with monthly projection for budget alerts';

-- ============================================================================
-- Helper View: API Reliability Summary
-- ============================================================================
-- Monitors retry rates and success rates per API

CREATE OR REPLACE VIEW api_reliability_summary AS
SELECT
    api_name,
    COUNT(*) as total_retries,
    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful_retries,
    AVG(retry_count) as avg_retry_count,
    AVG(delay_seconds) as avg_delay_seconds,
    DATE_TRUNC('day', timestamp) as day
FROM api_retry_log
GROUP BY api_name, DATE_TRUNC('day', timestamp)
ORDER BY day DESC, total_retries DESC;

COMMENT ON VIEW api_reliability_summary IS 'Daily retry statistics and success rates per API';

-- ============================================================================
-- Usage Examples (for reference)
-- ============================================================================

-- Example 1: Check daily costs and budget alert
-- SELECT * FROM daily_api_costs WHERE date = CURRENT_DATE;
-- -- If projected_monthly_cost > 10.0, trigger budget alert

-- Example 2: Monthly cost breakdown by API
-- SELECT
--     api_name,
--     SUM(estimated_cost) as monthly_cost,
--     SUM(num_calls) as total_calls,
--     SUM(token_count) as total_tokens
-- FROM api_cost_log
-- WHERE date >= DATE_TRUNC('month', CURRENT_DATE)
-- GROUP BY api_name
-- ORDER BY monthly_cost DESC;

-- Example 3: Retry failure rate (APIs needing attention)
-- SELECT
--     api_name,
--     COUNT(*) as retry_attempts,
--     SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures,
--     ROUND(100.0 * SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) / COUNT(*), 2) as failure_rate_pct
-- FROM api_retry_log
-- WHERE timestamp >= NOW() - INTERVAL '7 days'
-- GROUP BY api_name
-- HAVING COUNT(*) > 0
-- ORDER BY failure_rate_pct DESC;
