-- Migration 005: Evaluation Log Table
-- : Self-Evaluation mit Haiku API
-- Date: 2025-11-16
--
-- Purpose:
--   - Store detailed evaluation results for every answer evaluation
--   - Track reward scores, reasoning, and metadata for analytics
--   - Enable post-mortem analysis of evaluation quality
--
-- Table:
--   - evaluation_log: Complete evaluation results with query, answer, reward, reasoning

-- ============================================================================
-- Table: evaluation_log
-- ============================================================================
-- Stores complete evaluation results for transparency and analytics.
-- Enables:
-- - Post-mortem analysis of evaluation quality
-- - Tracking reward score distribution over time
-- - Correlation between reward scores and user satisfaction
-- - Debug/troubleshooting of poor evaluations

CREATE TABLE IF NOT EXISTS evaluation_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    query TEXT NOT NULL,                -- User query that was evaluated
    context TEXT[],                     -- Retrieved context (array of L2 Insights)
    answer TEXT NOT NULL,               -- Generated answer that was evaluated
    reward_score FLOAT NOT NULL,        -- Reward score (-1.0 to +1.0)
    reasoning TEXT NOT NULL,            -- Haiku's evaluation reasoning
    token_count INTEGER NOT NULL,       -- Total tokens used (input + output)
    cost_eur FLOAT NOT NULL,            -- Estimated cost in EUR
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for timestamp-based queries (recent evaluations)
CREATE INDEX idx_evaluation_log_timestamp ON evaluation_log(timestamp DESC);

-- Index for reward score analytics (distribution analysis)
CREATE INDEX idx_evaluation_log_reward ON evaluation_log(reward_score);

-- Index for cost tracking (monthly aggregation)
CREATE INDEX idx_evaluation_log_cost ON evaluation_log(created_at, cost_eur);

-- Comments for documentation
COMMENT ON TABLE evaluation_log IS 'Detailed evaluation results for every answer evaluation ()';
COMMENT ON COLUMN evaluation_log.query IS 'User query that triggered the evaluation';
COMMENT ON COLUMN evaluation_log.context IS 'Retrieved L2 Insights (Top-5 from Hybrid Search)';
COMMENT ON COLUMN evaluation_log.answer IS 'Generated answer that was evaluated';
COMMENT ON COLUMN evaluation_log.reward_score IS 'Reward score (-1.0 to +1.0) based on Relevance, Accuracy, Completeness';
COMMENT ON COLUMN evaluation_log.reasoning IS 'Haiku API explanation for the reward score';
COMMENT ON COLUMN evaluation_log.token_count IS 'Total tokens used for evaluation (input + output)';
COMMENT ON COLUMN evaluation_log.cost_eur IS 'Estimated cost in EUR (€0.001/1K input, €0.005/1K output)';

-- ============================================================================
-- View: evaluation_stats_daily
-- ============================================================================
-- Daily aggregation of evaluation statistics for monitoring

CREATE OR REPLACE VIEW evaluation_stats_daily AS
SELECT
    DATE(timestamp) as date,
    COUNT(*) as num_evaluations,
    ROUND(AVG(reward_score)::numeric, 3) as avg_reward,
    ROUND(MIN(reward_score)::numeric, 3) as min_reward,
    ROUND(MAX(reward_score)::numeric, 3) as max_reward,
    ROUND(STDDEV(reward_score)::numeric, 3) as stddev_reward,
    SUM(token_count) as total_tokens,
    ROUND(SUM(cost_eur)::numeric, 6) as total_cost_eur,
    -- Count evaluations below reflexion threshold (0.3)
    COUNT(CASE WHEN reward_score < 0.3 THEN 1 END) as low_quality_count,
    ROUND(
        (COUNT(CASE WHEN reward_score < 0.3 THEN 1 END)::float / COUNT(*)::float * 100)::numeric,
        1
    ) as low_quality_pct
FROM evaluation_log
GROUP BY DATE(timestamp)
ORDER BY date DESC;

COMMENT ON VIEW evaluation_stats_daily IS 'Daily evaluation statistics (avg reward, cost, low quality rate)';

-- ============================================================================
-- View: recent_evaluations
-- ============================================================================
-- Recent evaluations with truncated text for monitoring

CREATE OR REPLACE VIEW recent_evaluations AS
SELECT
    id,
    timestamp,
    LEFT(query, 50) || CASE WHEN LENGTH(query) > 50 THEN '...' ELSE '' END as query_preview,
    LEFT(answer, 100) || CASE WHEN LENGTH(answer) > 100 THEN '...' ELSE '' END as answer_preview,
    reward_score,
    LEFT(reasoning, 100) || CASE WHEN LENGTH(reasoning) > 100 THEN '...' ELSE '' END as reasoning_preview,
    token_count,
    cost_eur
FROM evaluation_log
ORDER BY timestamp DESC
LIMIT 50;

COMMENT ON VIEW recent_evaluations IS 'Last 50 evaluations with truncated text for quick monitoring';
