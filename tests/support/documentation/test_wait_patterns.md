# Test Wait Patterns - Audit Results and Guidelines

**Date**: 2026-01-11
**Workflow**: quick-dev - Phase 1 Hard Wait Fixes
**Baseline Commit**: 630313b

---

## Executive Summary

Initial test review identified **609 occurrences** of `sleep|wait|timeout` patterns. After detailed audit, **actual problematic hard waits are much fewer**.

**Key Finding**: Most "sleep/wait" occurrences are legitimate uses (process control, performance simulation, timeout parameters).

---

## Audit Results

### Files Analyzed

| File | Sleep Occurrences | Real Issues | Status |
|------|-------------------|-------------|--------|
| `test_mcp_server.py` | 5 | 2 fixed | ✅ Complete |
| `test_graph_performance.py` | 8 | 0 (intentional) | ✅ Legitimate |
| `test_dual_judge.py` | 0 | 0 | ✅ Clean |
| `test_ief.py` | 0 | 0 | ✅ Clean |
| `test_io_integration.py` | 0 | 0 | ✅ Clean |

### Issues Fixed

**1. test_mcp_server.py:38 - Server startup wait**
- **Before**: `time.sleep(1)` - arbitrary 1 second wait
- **After**: Health check loop with `select()` for efficient I/O polling
- **Impact**: Server startup now responds quickly when ready, no unnecessary delay

**2. test_mcp_server.py:123 - Response reading busy-wait**
- **Before**: `time.sleep(0.1)` in polling loop
- **After**: `select.select()` with 0.01s fallback
- **Impact**: Faster response detection, reduced test execution time

---

## Legitimate Sleep Patterns (Do NOT Fix)

These patterns are **acceptable** and should **NOT** be replaced:

### 1. Process Control - subprocess.wait(timeout=X)

**Legitimate** - This is the OS API for waiting on subprocess termination.

```python
# ✅ GOOD: Standard subprocess control
try:
    exit_code = process.wait(timeout=10)  # Not a hard wait
except subprocess.TimeoutExpired:
    process.kill()
    process.wait()
```

### 2. Performance Test Simulation

**Legitimate** - Intentionally simulating slow operations for performance testing.

```python
# ✅ GOOD: Performance test latency simulation
async def test_search_performance_with_slow_components():
    """Verify search works with slow semantic/keyword/graph components."""
    async def slow_semantic(*args, **kwargs):
        await asyncio.sleep(0.01)  # Simulate 10ms API latency
        return [{"id": 1, "content": "Semantic doc"}]

    # This is intentional - testing performance characteristics
```

### 3. Minimal Backoff with select()

**Legitimate** - When `select()` unavailable, small sleep prevents CPU spinning.

```python
# ✅ GOOD: Fallback for systems without select()
try:
    import select
    ready_to_read, _, _ = select.select([stdout], [], [], 0)
except (ImportError, AttributeError):
    # Windows or other system without select
    time.sleep(0.01)  # Minimal backoff to prevent CPU spinning
```

### 4. Timeout Parameters

**Legitimate** - Function parameters for timeout specification.

```python
# ✅ GOOD: Timeout parameter (not a sleep call)
def read_response(timeout: int = 30):
    if time.time() - start_time > timeout:
        raise TimeoutError(f"No response within {timeout}s")
```

---

## Anti-Patterns to Avoid

### ❌ Bad: Arbitrary Sleep for "Give Time to Start"

```python
# ❌ BAD: Arbitrary wait without condition
process.start()
time.sleep(1)  # Why 1 second? What if server starts in 0.1s?
# What if server takes 2 seconds due to load?
```

**Fix**: Use explicit health check
```python
# ✅ GOOD: Poll with condition
process.start()
wait_for_process_ready(process, timeout=5)
```

### ❌ Bad: Fixed Sleep Before Checking State

```python
# ❌ BAD: Assume state is ready after fixed time
conn.execute("INSERT INTO ...")
conn.commit()
time.sleep(0.5)  # Hope commit is done
result = conn.fetchrow("SELECT ...")
```

**Fix**: Verify state explicitly or use synchronous operations
```python
# ✅ GOOD: Synchronous commit ensures completion
conn.execute("INSERT INTO ...")
conn.commit()  # PostgreSQL commit() is synchronous
result = conn.fetchrow("SELECT ...")  # Safe to read immediately
```

### ❌ Bad: Long Sleep in Polling Loop

```python
# ❌ BAD: Long sleep makes tests slow and flaky
while not condition():
    time.sleep(1)  # Tests take forever!
```

**Fix**: Use shorter interval with timeout
```python
# ✅ GOOD: Responsive polling with timeout
wait_for_condition(condition, timeout=5, poll_interval=0.05)
```

---

## Helper Functions Available

Use the helpers in `tests/support/helpers/async_polling.py`:

### wait_for_condition()

```python
from tests.support.helpers.async_polling import wait_for_condition

def is_job_complete():
    return db.fetchrow("SELECT status FROM jobs")["status"] == "done"

result = wait_for_condition(is_job_complete, timeout=5)
```

### wait_for_process_ready()

```python
from tests.support.helpers.async_polling import wait_for_process_ready

process = subprocess.Popen(["python", "-m", "mcp_server"])
wait_for_process_ready(process, timeout=10)
```

### wait_for_process_output()

```python
from tests.support.helpers.async_polling import wait_for_process_output

line = wait_for_process_output(process, stream="stdout", timeout=30)
```

---

## Guidelines for New Tests

### When to Use time.sleep()

1. **Performance tests** - Simulating latency (intentional)
2. **Process control** - `subprocess.wait(timeout=X)` (OS API)
3. **Last resort** - 0.01-0.05s backoff when select unavailable

### When NOT to Use time.sleep()

1. **Waiting for startup** - Use health check instead
2. **Waiting for state change** - Poll with condition instead
3. **Waiting for I/O** - Use select() or explicit wait instead
4. **Arbitrary delays** - Never use "give it time" sleeps

### Default Values

| Use Case | Timeout | Poll Interval |
|----------|---------|---------------|
| Server startup | 5-10s | 0.05s |
| Database query | 5s | 0.1s |
| API response | 30s | 0.01s (with select) |
| Process output | 30s | 0.01s (with select) |

---

## Related Documents

- **Helper Code**: `tests/support/helpers/async_polling.py`
- **Test Quality Review**: `_bmad-output/test-review.md`
- **Project Context**: `project-context.md`

---

## Quick Reference

```python
# ✅ GOOD - Explicit wait
from tests.support.helpers.async_polling import wait_for_condition
wait_for_condition(lambda: check_ready(), timeout=5)

# ❌ BAD - Hard wait
time.sleep(1)

# ✅ GOOD - Process control
process.wait(timeout=10)

# ✅ GOOD - Performance simulation
await asyncio.sleep(0.01)  # Intentional latency simulation
```

---

**Generated**: 2026-01-11
**Workflow**: quick-dev Phase 1
**Status**: Complete
