# Bug Report: compress_to_l2_insight rejects empty source_ids array

**Date:** 2025-12-06
**Reporter:** I/O (via Claude Code)
**Severity:** Medium
**Status:** Fixed (2025-12-06)
**Fix:** Changed validation from `if not source_ids` to `if source_ids is None` in `mcp_server/tools/__init__.py:956`

---

## Summary

The `compress_to_l2_insight` MCP tool rejects an empty array `[]` for the `source_ids` parameter, even though this is a valid use case when creating insights that don't originate from raw dialogue.

---

## Steps to Reproduce

```python
# This fails:
mcp__cognitive-memory__compress_to_l2_insight(
    content="Some insight content",
    source_ids=[]
)
```

**Error Response:**
```json
{
  "error": "Parameter validation failed",
  "details": "Missing or invalid 'source_ids' parameter (must be array of integers)",
  "tool": "compress_to_l2_insight"
}
```

---

## Expected Behavior

Empty array `[]` should be accepted as valid input, creating an L2 insight with no linked L0 raw dialogue entries.

---

## Actual Behavior

Parameter validation fails, preventing insight creation.

---

## Use Case

Many insights are derived from:
- Session observations (no raw dialogue stored)
- External documents analyzed
- Synthesized conclusions from multiple sources
- Graph structure observations

These insights have no corresponding L0 raw dialogue IDs.

---

## Workaround

Currently using `store_episode` instead for insights without source IDs:

```python
mcp__cognitive-memory__store_episode(
    query="Observation topic",
    reward=0.8,
    reflection="Problem: ... Lesson: ..."
)
```

---

## Suggested Fix

In the parameter validation logic, accept empty arrays:

```python
# Before (presumably)
if not source_ids or not isinstance(source_ids, list):
    raise ValidationError(...)

# After
if source_ids is None or not isinstance(source_ids, list):
    raise ValidationError(...)
# Empty list [] is now valid
```

Or make `source_ids` optional with default `[]`:

```python
async def compress_to_l2_insight(
    content: str,
    source_ids: list[int] | None = None  # Optional, defaults to empty
) -> dict:
    source_ids = source_ids or []
    ...
```

---

## Impact

- Blocks normal L2 insight creation workflow
- Forces workarounds that lose semantic structure
- Reduces usability of the cognitive-memory system

---

## Related

- Works correctly: `graph_add_node`, `graph_add_edge`, `store_episode`
- Same session: SSL retry mechanism confirmed working (separate fix)

---

*Filed from I/O System development session, 2025-12-06*
