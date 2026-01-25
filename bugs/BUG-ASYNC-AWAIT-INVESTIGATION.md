# async/await Bug Investigation - Remaining Issues

**Date:** 2026-01-14
**Status:** ✅ FIXED (commit 3b7582a, b8bbee1)

---

## Summary

Fixed async/await issues in Phase 3:
- ✅ Changed `semantic_search`, `keyword_search`, `episode_semantic_search`, `episode_keyword_search` from `async def` to `def` (sync-only functions)
- ✅ These functions use psycopg2 cursor.execute() which is sync
- ✅ `handle_compress_to_l2_insight` fixed
- ✅ `handle_hybrid_search` fixed

## Error Analysis

### Symptom
```
'coroutine' object has no attribute 'execute'
```

### Investigation

1. **Code Review:** Both functions use correct `async with get_connection()` pattern
2. **Function Signatures:** Both are `async def` with proper `await` statements
3. **Possible Causes:**
   - `get_connection()` may be returning a Coroutine in some contexts
   - Dependency cycle in imports may cause async/sync mismatch
   - `register_vector()` may have hidden async call that's not awaited
   - Connection pool mocking may be interfering

### Test Behavior
- Tests fail with async/await error even with mocking
- Error occurs during database operation phase (line ~1120-1150)
- Error persists after fixing obvious async/await patterns

### Known Working Patterns
- `handle_graph_add_node` - works correctly with async functions
- `handle_graph_add_edge` - works correctly
- `graph_add_node`, `query_neighbors` in db/graph.py - work with async

### Hypothesis

The issue may be that somewhere in the call chain:
1. An async function is called without `await`
2. A function that should be sync is declared `async def`
3. A dependency creates a Coroutine object that's then treated as sync object

### Next Steps for Fix

1. **Full async audit:** Trace all function calls in `handle_compress_to_l2_insight` from start to end
2. **Dependency graph:** Map which functions are async vs sync
3. **Test with minimal mocks:** Start with real DB if available, reduce mocks gradually
4. **Check imports:** Ensure all imports are loaded correctly
5. **Check global state:** Verify no globals are modified unexpectedly

## Files to Investigate

- `mcp_server/tools/__init__.py` - lines 1035-1175 (handle_compress_to_l2_insight)
- `mcp_server/tools/__init__.py` - lines 1241-1450 (handle_hybrid_search)
- `mcp_server/db/connection.py` - get_connection function and pool management
- `mcp_server/db/insights.py` - async functions in insights module

## Related Files

- `bugs/BUG-MCP-ASYNC-AWAIT-DETAILED.md` - Original bug report
- `tests/integration/test_regression_workflows.py` - Tests that currently skip these

---

**Priority:** MEDIUM-HIGH (blocks 5 P0 tests)

**Time Estimate:** 2-4 hours for full investigation and fix
