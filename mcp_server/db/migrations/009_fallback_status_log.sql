-- Migration 009: Fallback Status Log Table
-- : Claude Code Fallback für Haiku API Ausfall (Degraded Mode)
-- Date: 2025-11-18

-- =============================================================================
-- Fallback Status Log Table
-- =============================================================================
-- Tracks fallback mode activation and recovery events for external API services.
-- Enables monitoring when system enters degraded mode (Haiku API unavailable)
-- and automatic recovery tracking when API becomes available again.
-- Used for observability, uptime analysis, and degraded mode duration metrics.

CREATE TABLE IF NOT EXISTS fallback_status_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'recovered')),
    reason VARCHAR(100) NOT NULL,
    metadata JSONB
);

-- =============================================================================
-- Indexes for Query Performance
-- =============================================================================

-- Index on timestamp (DESC) for fast recent queries and timeline analysis
-- Supports queries like: "Zeige mir Fallback-Events letzte 7 Tage"
CREATE INDEX IF NOT EXISTS idx_fallback_timestamp
ON fallback_status_log(timestamp DESC);

-- Index on service_name for per-service fallback analysis
-- Supports queries filtering by specific services (e.g., WHERE service_name = 'haiku_evaluation')
CREATE INDEX IF NOT EXISTS idx_fallback_service
ON fallback_status_log(service_name);

-- Index on status for active fallback detection
-- Supports queries like: "Zeige mir alle aktuell aktiven Fallbacks"
CREATE INDEX IF NOT EXISTS idx_fallback_status
ON fallback_status_log(status);

-- =============================================================================
-- Comments
-- =============================================================================

COMMENT ON TABLE fallback_status_log IS
'Fallback mode tracking for external API services (Haiku Evaluation, Haiku Reflexion). Logs activation events when API becomes unavailable (after 4 retries) and recovery events when API becomes available again. Enables degraded mode monitoring and uptime analysis.';

COMMENT ON COLUMN fallback_status_log.id IS
'Auto-incrementing primary key (allows multiple fallback cycles per service)';

COMMENT ON COLUMN fallback_status_log.timestamp IS
'Timestamp when fallback event occurred (TIMESTAMPTZ for timezone awareness)';

COMMENT ON COLUMN fallback_status_log.service_name IS
'Service in fallback mode: haiku_evaluation | haiku_reflexion';

COMMENT ON COLUMN fallback_status_log.status IS
'Fallback status: active (degraded mode activated) | recovered (API back online, degraded mode deactivated)';

COMMENT ON COLUMN fallback_status_log.reason IS
'Reason for status change: haiku_api_unavailable (activation) | api_recovered (deactivation) | health_check_success | manual_recovery';

COMMENT ON COLUMN fallback_status_log.metadata IS
'Additional context as JSON: {error_message: str, retry_count: int, last_error_type: str, health_check_attempts: int}';

-- =============================================================================
-- Validation Queries
-- =============================================================================

-- Query 1: View fallback events for last 7 days
-- Expected: All fallback activation/recovery events grouped by service
--
-- SELECT service_name,
--        COUNT(*) as total_events,
--        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as activation_count,
--        SUM(CASE WHEN status = 'recovered' THEN 1 ELSE 0 END) as recovery_count,
--        MAX(timestamp) FILTER (WHERE status = 'active') as last_activation,
--        MAX(timestamp) FILTER (WHERE status = 'recovered') as last_recovery
-- FROM fallback_status_log
-- WHERE timestamp >= NOW() - INTERVAL '7 days'
-- GROUP BY service_name
-- ORDER BY last_activation DESC NULLS LAST;

-- Query 2: Check current fallback status (active degraded modes)
-- Expected: Services currently in fallback mode (most recent event is 'active')
--
-- WITH latest_events AS (
--     SELECT service_name,
--            status,
--            timestamp,
--            reason,
--            metadata,
--            ROW_NUMBER() OVER (PARTITION BY service_name ORDER BY timestamp DESC) as rn
--     FROM fallback_status_log
-- )
-- SELECT service_name, status, timestamp, reason, metadata
-- FROM latest_events
-- WHERE rn = 1 AND status = 'active';

-- Query 3: Calculate degraded mode duration
-- Expected: Time spent in degraded mode for each fallback cycle
--
-- WITH fallback_pairs AS (
--     SELECT service_name,
--            timestamp as activation_time,
--            LEAD(timestamp) OVER (PARTITION BY service_name ORDER BY timestamp) as recovery_time,
--            status,
--            LEAD(status) OVER (PARTITION BY service_name ORDER BY timestamp) as next_status
--     FROM fallback_status_log
-- )
-- SELECT service_name,
--        activation_time,
--        recovery_time,
--        recovery_time - activation_time as degraded_duration,
--        EXTRACT(EPOCH FROM (recovery_time - activation_time)) / 60 as degraded_minutes
-- FROM fallback_pairs
-- WHERE status = 'active' AND next_status = 'recovered'
-- ORDER BY activation_time DESC
-- LIMIT 20;

-- Query 4: Check for constraint violations (should return 0)
-- Expected: 0 rows (status must be 'active' or 'recovered')
--
-- SELECT id, status
-- FROM fallback_status_log
-- WHERE status NOT IN ('active', 'recovered');

-- Query 5: Recent fallback timeline (last 50 entries)
-- Expected: Chronological view of all recent fallback events
--
-- SELECT timestamp, service_name, status, reason, metadata
-- FROM fallback_status_log
-- ORDER BY timestamp DESC
-- LIMIT 50;

-- Query 6: Fallback frequency analysis
-- Expected: How often each service enters fallback mode
--
-- SELECT service_name,
--        DATE_TRUNC('day', timestamp) as date,
--        COUNT(*) FILTER (WHERE status = 'active') as activations_per_day,
--        COUNT(*) FILTER (WHERE status = 'recovered') as recoveries_per_day
-- FROM fallback_status_log
-- WHERE timestamp >= NOW() - INTERVAL '30 days'
-- GROUP BY service_name, DATE_TRUNC('day', timestamp)
-- ORDER BY date DESC, service_name;
