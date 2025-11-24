-- Migration 010: API Cost Log Composite Index
-- Story 3.10: Budget Monitoring & Cost Optimization Dashboard
-- Date: 2025-11-20
--
-- Purpose:
--   - Add composite index (date DESC, api_name) for optimized budget monitoring queries
--   - Supports monthly cost aggregation and API breakdown queries efficiently
--
-- Note:
--   - api_cost_log table already exists from Migration 004
--   - This migration adds additional composite index for Story 3.10 requirements
--   - Existing indexes (idx_api_cost_date, idx_api_cost_name) remain for backward compatibility

-- =============================================================================
-- Composite Index for Budget Monitoring Queries
-- =============================================================================
-- Optimizes queries that filter by date range and group by API name
-- Used by: get_cost_breakdown_by_api(), get_monthly_cost(), check_budget_alert()

CREATE INDEX IF NOT EXISTS idx_cost_date_api ON api_cost_log(date DESC, api_name);

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON INDEX idx_cost_date_api IS
'Composite index for budget monitoring queries: date-range filtering + API grouping (Story 3.10)';

-- =============================================================================
-- Validation Queries
-- =============================================================================

-- Query 1: Verify index exists (should return 1 row)
-- Expected: indexname = 'idx_cost_date_api'
--
-- SELECT indexname
-- FROM pg_indexes
-- WHERE tablename = 'api_cost_log' AND indexname = 'idx_cost_date_api';

-- Query 2: Test index usage for monthly cost breakdown
-- Expected: Query plan uses idx_cost_date_api
--
-- EXPLAIN ANALYZE
-- SELECT api_name, SUM(estimated_cost) as total_cost, SUM(num_calls) as total_calls
-- FROM api_cost_log
-- WHERE date >= NOW() - INTERVAL '30 days'
-- GROUP BY api_name
-- ORDER BY total_cost DESC;

-- Query 3: Test index usage for monthly aggregation
-- Expected: Query plan uses idx_cost_date_api
--
-- EXPLAIN ANALYZE
-- SELECT SUM(estimated_cost) as total_cost
-- FROM api_cost_log
-- WHERE date >= NOW() - INTERVAL '30 days';
