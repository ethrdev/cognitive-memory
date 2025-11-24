# CRITICAL BUGFIX - Story 1.8: Episode Memory Storage

## 🚨 URGENT - Critical Database Commit Bug

**Status:** BLOCKED - Episodes are permanently lost despite successful INSERT operations

## Required Fix (Line ~1028 in mcp_server/tools/__init__.py)

```python
# AFTER line 1027:
logger.info(f"Episode stored successfully with ID: {episode_id}")

# ADD THIS LINE:
conn.commit()  # ← MISSING CRITICAL LINE

return {
    "id": episode_id,
    "embedding_status": "success",
    "query": query,
    "reward": reward,
    "created_at": created_at.isoformat(),
}
```

## Root Cause
`get_connection()` context manager does NOT auto-commit. Transactions are rolled back when connection returned to pool.

## Test Fix Required
Add test with second connection to verify commit() behavior.

## Story Status
Current: review (BLOCKED) → Fix required → re-run review → approval
