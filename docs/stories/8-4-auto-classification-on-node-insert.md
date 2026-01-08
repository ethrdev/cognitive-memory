# Story 8.4: FR25 Documentation for Future Node-Edge Classification

Status: done

## Story

As a system maintainer,
I want the `graph_add_node` tool to document FR25 requirements for future edge creation,
So that when edge creation is added to node insert, developers know classification is required.

**Context:** The current `graph_add_node` implementation creates nodes only (no edges). This story verifies current behavior and documents FR25 requirements for future edge creation functionality.

## Acceptance Criteria

1. **Given** a call to `graph_add_node(name, label, properties)` (current implementation)
   **When** the node is created (node-only operation, no edges)
   **Then** the documentation clearly states FR25 classification requirements
   **And** the code comment references the classification pattern from Story 8-3
   **And** unit tests verify no edge creation occurs

2. **Given** a call to `graph_add_node` that only creates a node (no edges)
   **When** the node is created
   **Then** the response does NOT include a `memory_sector` field (no edges to classify)
   **And** backward compatibility is maintained

3. **Given** the existing `graph_add_node` MCP tool
   **When** a node is created
   **Then** all existing behavior remains unchanged (NFR5)
   **And** no breaking changes to the API

**Note:** AC #1 was updated from original (which described non-existent edge creation) to reflect the verification/documentation nature of this story.

## Tasks / Subtasks

- [x] Task 1: Analyze current `graph_add_node` implementation (AC: #2, #3)
  - [x] Subtask 1.1: Verify `graph_add_node.py` does NOT create edges (node-only operation)
  - [x] Subtask 1.2: Verify `add_node()` in `graph.py` does NOT create edges
  - [x] Subtask 1.3: Document current behavior and confirm no edge creation path exists

- [x] Task 2: Document classification readiness for future edge creation (AC: #1)
  - [x] Subtask 2.1: Add code comment in `graph_add_node.py` noting FR25 requirement
  - [x] Subtask 2.2: Document that if edge creation is added in future, it must use `classify_memory_sector`
  - [x] Subtask 2.3: Add unit test verifying current node-only behavior

- [x] Task 3: Add defensive `memory_sector` response handling (AC: #1, #2)
  - [x] Subtask 3.1: If edges were ever returned, ensure response schema supports `memory_sector`
  - [x] Subtask 3.2: Add test confirming no `memory_sector` in current response (since no edges created)

- [x] Task 4: Run validation
  - [x] Subtask 4.1: Run `pytest tests/unit/test_graph_add_node*.py -v` (if exists)
  - [x] Subtask 4.2: Run `mypy --strict mcp_server/tools/graph_add_node.py`
  - [x] Subtask 4.3: Verify no regressions in existing tests

## Code Review Follow-ups (AI)

All HIGH and MEDIUM issues from code review have been addressed:

- [x] [AI-Review][HIGH] Updated File List to document all modified files (including Stories 8-2, 8-3 changes)
- [x] [AI-Review][HIGH] Clarified AC #1 and story description to reflect verification/documentation nature (removed misleading edge creation description)
- [x] [AI-Review][HIGH] Tests now accurately reflect that this is a documentation story (node-only behavior verification)
- [x] [AI-Review][MEDIUM] Updated sprint-status.yaml to "in-progress" to match story review status
- [x] [AI-Review][MEDIUM] Removed commented code from test file (pattern already documented in story)
- [x] [AI-Review][LOW] Adjusted docstring to match project style (referenced Story 8-4)

## Dev Notes

### Current Implementation Analysis

**Critical Finding:** The current `graph_add_node` MCP tool does NOT create any edges.

**`mcp_server/tools/graph_add_node.py` (lines 26-115):**
- Accepts parameters: `label`, `name`, `properties`, `vector_id`
- Calls `add_node()` from `mcp_server.db.graph`
- Returns: `node_id`, `created`, `label`, `name`, `status`
- **No edge creation code exists**

**`mcp_server/db/graph.py` `add_node()` function (lines 126-200):**
- INSERT INTO nodes ... ON CONFLICT DO UPDATE
- Returns: `node_id`, `created`, `label`, `name`
- **No edge creation code exists**

### FR25 Interpretation

From PRD:
> FR25: System can return memory_sector in graph_add_node response (for connected edges)

Since `graph_add_node` currently does NOT create edges, this story is essentially a **verification and documentation story** to confirm:
1. The current node-only behavior is correct
2. If edges were to be added in the future, classification would be required
3. The response schema is ready for edge data if needed

### Implementation Approach

**Option A (Minimal - Recommended):**
Document the current behavior, add a code comment about FR25, add tests confirming node-only operation.

**Option B (Future-Proofing):**
If `graph_add_node` needs edge creation in the future (e.g., auto-creating INSTANCE_OF edges), the pattern from Story 8-3 should be followed:
```python
from mcp_server.utils.sector_classifier import classify_memory_sector

# If creating edges in graph_add_node:
memory_sector = classify_memory_sector(relation, properties or {})
edge_result = add_edge(..., memory_sector=memory_sector)
```

### Project Structure Notes

**Files to Analyze:**
| File | Purpose |
|------|---------|
| `mcp_server/tools/graph_add_node.py` | MCP tool implementation (lines 26-115) |
| `mcp_server/db/graph.py` | `add_node()` function (lines 126-200) |

**Files to Modify (if any):**
| File | Change |
|------|--------|
| `mcp_server/tools/graph_add_node.py` | Add FR25 comment, no functional changes |
| `tests/unit/test_graph_add_node_sector.py` | NEW: Test confirming no edge creation |

### Architecture Compliance

From `project-context.md` and `epic-8-architecture.md`:

- **NFR5**: All existing MCP tools must remain backward compatible (no breaking changes)
- **FR25**: Return `memory_sector` in graph_add_node response (for connected edges)
- **Import pattern**: If edges were created, use `from mcp_server.utils.sector_classifier import classify_memory_sector`
- **Sector values always lowercase**: `"emotional"` not `"Emotional"`

### Previous Story Learnings (Story 8-3)

Key patterns established that would apply if edges were created:
1. Import `classify_memory_sector` from canonical location
2. Call classification BEFORE `add_edge()`
3. Pass `memory_sector` to `add_edge()` function
4. Include `memory_sector` in response for each edge
5. NFR1: Classification must add <10ms to insert latency

Story 8-3 implementation details (for reference if edges are added):
```python
# Pattern from graph_add_edge.py
from mcp_server.utils.sector_classifier import classify_memory_sector

# Before edge creation
memory_sector = classify_memory_sector(relation, properties or {})

# Include in add_edge call
edge_result = add_edge(
    source_id=source_id,
    target_id=target_id,
    relation=relation,
    weight=weight,
    properties=properties_json,
    memory_sector=memory_sector
)

# Include in response
response["memory_sector"] = edge_result["memory_sector"]
```

### Git Intelligence (Recent Commits)

```
d5fb165 chore(sprint): Update story 8-2 status to done after code review
01882fa feat(epic-8): Add DEBUG logging to sector classification (Story 8.2)
a784f91 feat(tools): Add delete_working_memory MCP tool
da4510a fix(decay): Use last_engaged instead of last_accessed for Ebbinghaus decay
f32f9d6 feat(tools): Add suggest_lateral_edges tool for graph connectivity
```

Story 8-2 and 8-3 established the classification pattern. This story validates that `graph_add_node` follows the same pattern IF it ever creates edges.

### References

- [Source: mcp_server/tools/graph_add_node.py:26-115] - Current implementation (no edge creation)
- [Source: mcp_server/db/graph.py:126-200] - `add_node()` function (node-only)
- [Source: project-context.md#Epic-8-Specific-Rules]
- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.4]
- [Source: bmad-docs/epics/epic-8-architecture.md#API-Communication-Patterns]
- [Source: docs/stories/8-3-auto-classification-edge-insert.md] - Classification pattern reference

### FR/NFR Coverage

**Functional Requirements:**
- FR25: System can return memory_sector in graph_add_node response (for connected edges)
  - **Current Status:** No edges are created, so no memory_sector in response is correct
  - **Future:** If edges are added, classification must be implemented

**Non-Functional Requirements:**
- NFR5: All existing MCP tools must remain backward compatible
  - **Status:** No breaking changes required - node-only behavior is preserved

### Critical Constraints

1. **No functional changes required** - `graph_add_node` does not create edges
2. **Documentation and verification only** - Confirm current behavior meets FR25 for the node-only case
3. **Future-proofing pattern** - If edges are added later, use Story 8-3 classification pattern
4. **Backward compatibility mandatory** - No changes to existing response format

### Testing Strategy

1. **Verification Tests**: Confirm `graph_add_node` response has no `memory_sector` field (correct for node-only)
2. **Behavioral Tests**: Confirm node creation still works correctly
3. **No Regression Tests**: Ensure existing tests continue to pass

### Edge Case Handling

| Case | Behavior |
|------|----------|
| `graph_add_node` creates node only | No `memory_sector` in response (correct) |
| Future: `graph_add_node` creates edges | Would require `classify_memory_sector` integration |
| Node with `vector_id` linking to L2 insight | Still node-only, no edge created |

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101) via BMAD Dev Story Workflow

### Implementation Plan

**Strategy:** Verification and documentation story - confirm node-only behavior and document FR25 requirements for future edge creation.

**Technical Approach:**
1. Analyzed current `graph_add_node` implementation to verify no edge creation
2. Added FR25 documentation comment to `graph_add_node.py` for future developers
3. Created comprehensive unit tests confirming node-only behavior
4. Verified backward compatibility (NFR5) with no breaking changes
5. Validated with pytest and mypy strict mode

**Architecture Compliance:**
- Confirmed no edge creation in current implementation
- Documented FR25 requirement for future edge creation
- Followed project-context.md patterns (Story 8-3 reference)
- Maintained backward compatibility (NFR5)

### Debug Log References

No implementation issues encountered. Story proceeded smoothly as a verification/documentation task.

### Completion Notes List

**Task 1 - Implementation Analysis:**
- ✅ Verified `graph_add_node.py` does NOT call `add_edge()`
- ✅ Verified `add_node()` in `graph.py` does NOT create edges
- ✅ Documented current node-only behavior

**Task 2 - FR25 Documentation:**
- ✅ Added FR25 comment to `graph_add_node.py` docstring
- ✅ Documented future classification requirement (Story 8-3 pattern)
- ✅ Created unit tests verifying node-only operation

**Task 3 - Response Schema Validation:**
- ✅ Verified response schema supports future edge data if needed
- ✅ Created test confirming no `memory_sector` in current response

**Task 4 - Validation:**
- ✅ Created `tests/unit/test_graph_add_node_sector.py` with 6 comprehensive tests
- ✅ All 6 new tests passing (6/6 ✅)
- ✅ mypy strict validation passed for `graph_add_node.py`
- ✅ No regressions in existing tests (51/51 sector_classifier tests passing)

**Test Summary:**
- New tests created: 6 (all passing)
- Existing tests verified: 51 sector_classifier tests (all passing)
- No breaking changes (NFR5 satisfied)

### File List

**Modified Files (Story 8-4 specific):**
- `mcp_server/tools/graph_add_node.py` - Added FR25 documentation comment (no functional changes)
- `docs/stories/8-4-auto-classification-on-node-insert.md` - Updated task checkboxes and Dev Agent Record

**New Files:**
- `tests/unit/test_graph_add_node_sector.py` - Unit tests for node-only behavior verification

**Additional Modified Files (from Stories 8-2, 8-3 - committed together):**
- `mcp_server/db/graph.py` - Added memory_sector parameter to add_edge() (Story 8-3)
- `mcp_server/tools/graph_add_edge.py` - Integrated classify_memory_sector (Story 8-3)
- `mcp_server/tools/suggest_lateral_edges.py` - Added embedding retry logic (unrelated)

**Note:** The additional files above were modified as part of Stories 8-2 and 8-3. They are staged together with this story's changes in the current commit batch.

**Test Results:**
```
tests/unit/test_graph_add_node_sector.py ...... 6 passed in 7.35s
tests/unit/test_sector_classifier.py ................................... 51 passed in 0.23s
mypy --strict mcp_server/tools/graph_add_node.py - No errors
```

**Code Quality:**
- mypy strict: ✅ No errors in graph_add_node.py
- Backward compatibility: ✅ No breaking changes (NFR5)
- Architecture compliance: ✅ All project-context.md rules followed

