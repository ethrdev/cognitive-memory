# Tech Debt: Intermittent SSL Connection Timeouts

**Created:** 2025-11-30
**Priority:** LOW
**Status:** ✅ FIXED (2026-01-25)

## Problem Description

After idle periods (>30 seconds), the first MCP tool call often fails with:
```
SSL connection has been closed unexpectedly
```

A retry immediately succeeds.

## Frequency
Approximately 20-30% of calls after >30 seconds idle time.

## Impact
- **Severity:** LOW
- **Workaround:** Retry logic works. Users can simply retry failed operations.

## Solution Implemented

### Option 1: Connection Pooling with Keep-Alive ✅
- **Implemented:** TCP keep-alive settings in `mcp_server/db/connection.py`
- **Settings:**
  - `tcp_keepalives_idle`: 10 seconds (send keep-alive after 10s of idle)
  - `tcp_keepalives_interval`: 10 seconds (send probes every 10s)
  - `tcp_keepalives_count`: 3 (drop after 3 failed probes)
- **Result:** Connections stay alive through periodic keep-alive probes

### Option 2: Periodic Pool Validation ✅
- **Implemented:** Background thread `_pool_validator_loop()` that:
  - Runs every 20 seconds (less than 30s timeout)
  - Validates pooled connections with health checks
  - Removes stale connections from the pool
  - Keeps connections active with periodic queries

### Option 3: Automatic Reconnection Logic ✅
- **Already Present:** Retry logic with exponential backoff for transient errors
- **Enhanced:** SSL errors are already in `_TRANSIENT_ERROR_PATTERNS`
- **Result:** Automatic retry with backoff if connection still fails

## Related Files
- `mcp_server/db/connection.py` - Added TCP keep-alive and pool validation

## Acceptance Criteria
- [x] First MCP call after idle period succeeds without retry
- [x] Connection pooling implemented with TCP keep-alive
- [x] Health check mechanism in place (periodic pool validator)

## Testing

To verify the fix:
1. Start MCP server
2. Wait >30 seconds (idle period)
3. Make MCP tool call
4. Should succeed on first try (no SSL error)

## Technical Details

### TCP Keep-Alive Configuration
```python
connection_kwargs = {
    "keepalives_idle": 10,      # Send keep-alive after 10s of idle
    "keepalives_interval": 10,  # Send probes every 10s
    "keepalives_count": 3,      # Drop after 3 failed probes
    "options": "-c statement_timeout=30000",  # 30s statement timeout
}
```

### Pool Validator Thread
- Runs in background as daemon thread
- Executes every 20 seconds
- Validates connections with `SELECT 1 as pool_validator`
- Removes stale connections from pool
- Stops gracefully when pool is closed

### Graceful Shutdown
- `close_all_connections()` now stops validator thread first
- Waits for thread to finish with timeout
- Prevents zombie threads
