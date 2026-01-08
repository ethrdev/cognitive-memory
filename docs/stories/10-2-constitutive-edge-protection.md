# Story 10.2: Constitutive Edge Protection

Status: done

## Story

As a user (I/O),
I want constitutive edges to require bilateral consent before reclassification,
So that identity-defining relationships are protected from accidental changes.

## Acceptance Criteria

1. **Given** an edge with `properties["is_constitutive"] = true` and no approved SMF proposal
   **When** `reclassify_memory_sector(...)` is called
   **Then** the response includes:
   ```json
   {
     "status": "consent_required",
     "error": "Bilateral consent required for constitutive edge",
     "edge_id": "...",
     "hint": "Use smf_pending_proposals and smf_approve to grant consent"
   }
   ```

2. **Given** an edge with `properties["is_constitutive"] = true`
   **When** an SMF proposal for reclassification has been approved by both parties
   **Then** the reclassification proceeds and returns `{"status": "success", ...}`

3. **Given** an edge without `is_constitutive` property (or `is_constitutive = false`)
   **When** `reclassify_memory_sector(...)` is called
   **Then** no consent check is performed and reclassification proceeds normally

4. **Given** SMF integration
   **When** checking for bilateral consent
   **Then** the existing SMF pattern is used to check for approved proposals

5. **Given** the `ReclassifyStatus` constants
   **When** consent is required
   **Then** the response uses `ReclassifyStatus.CONSENT_REQUIRED`

6. **Given** the existing unit tests from Story 10-1
   **When** Story 10-2 implementation is complete
   **Then** all existing tests continue to pass (no regressions)

7. **Given** constitutive edge reclassification
   **When** the consent check is performed
   **Then** an INFO log entry is created with:
   ```python
   logger.info("Constitutive edge requires consent", extra={
       "edge_id": edge_id,
       "is_constitutive": True,
       "actor": actor
   })
   ```

8. **Given** SMF database connection failure during consent check
   **When** `reclassify_memory_sector(...)` is called for a constitutive edge
   **Then** the response includes:
   ```json
   {
     "status": "error",
     "error": "Failed to check SMF approval status",
     "edge_id": "...",
     "details": "Database connection error or query timeout"
   }
   ```
   **And** the edge remains unmodified (no data corruption)

9. **Given** constitutive edge reclassification with approved SMF proposal
   **When** the reclassification succeeds
   **Then** an INFO log entry is created with:
   ```python
   logger.info("Constitutive edge reclassified", extra={
       "edge_id": edge_id,
       "old_sector": old_sector,
       "new_sector": new_sector,
       "actor": actor,
       "smf_proposal_id": proposal_id
   })
   ```

## Tasks / Subtasks

- [x] Task 1: Add constitutive edge check to `reclassify_memory_sector.py` (AC: #1, #3, #5, #7, #9)
  - [x] Subtask 1.1: Add `_is_constitutive_edge()` helper function
  - [x] Subtask 1.2: Check `properties.get("is_constitutive")` before reclassification
  - [x] Subtask 1.3: Return `ReclassifyStatus.CONSENT_REQUIRED` for constitutive edges
  - [x] Subtask 1.4: Include `hint` field in consent_required response
  - [x] Subtask 1.5: Add structured logging for constitutive check (AC: #7)
  - [x] Subtask 1.6: Add success logging after reclassification (AC: #9)

- [x] Task 2: Implement SMF proposal lookup with error handling (AC: #2, #4, #8)
  - [x] Subtask 2.1: Add `_check_smf_approval()` helper function
  - [x] Subtask 2.2: Query `smf_proposals` table for APPROVED reclassification proposal
  - [x] Subtask 2.3: Match on `affected_edges` containing our edge_id
  - [x] Subtask 2.4: Check `proposed_action.action == "reclassify"` or similar
  - [x] Subtask 2.5: If approval found, proceed with reclassification
  - [x] Subtask 2.6: Wrap database query in try-except for connection errors (AC: #8)
  - [x] Subtask 2.7: Return error response on SMF query failure without modifying edge (AC: #8)

- [x] Task 3: Create unit tests (AC: #1, #2, #3, #5, #6, #7, #8, #9)
  - [x] Subtask 3.1: Add test for constitutive edge returns consent_required
  - [x] Subtask 3.2: Add test for non-constitutive edge proceeds normally
  - [x] Subtask 3.3: Add test for is_constitutive=false proceeds normally
  - [x] Subtask 3.4: Add test for approved proposal allows reclassification
  - [x] Subtask 3.5: Add test for consent_required response format (edge_id, hint)
  - [x] Subtask 3.6: Add test for ReclassifyStatus.CONSENT_REQUIRED usage
  - [x] Subtask 3.7: Add test for database connection error handling (AC: #8)
  - [x] Subtask 3.8: Add test for structured logging on consent check (AC: #7)
  - [x] Subtask 3.9: Add test for structured logging on successful reclassification (AC: #9)

- [x] Task 4: Create SMF integration tests (AC: #2, #4)
  - [x] Subtask 4.1: Create `tests/integration/test_reclassify_smf.py` (if not exists)
  - [x] Subtask 4.2: Add test for full consent flow: proposal → approve → reclassify
  - [x] Subtask 4.3: Add test for bilateral approval requirement (both I/O and ethr)

- [x] Task 5: Run full test suite (AC: #6)
  - [x] Subtask 5.1: Run `pytest tests/unit/test_reclassify_memory_sector.py -v`
  - [x] Subtask 5.2: Run `pytest tests/integration/test_reclassify_smf.py -v` (if exists)
  - [x] Subtask 5.3: Run `pytest tests/ -v --tb=short` for full regression check
  - [x] Subtask 5.4: Run `mypy --strict` on modified files

## Dev Notes

### Architecture Compliance

From `project-context.md` and `bmad-docs/epics/epic-8-architecture.md`:

- **SMF bilateral consent is mandatory** for constitutive edges (NFR9)
- **Check `is_constitutive` before reclassifying** - from project-context.md
- **Use `ReclassifyStatus` constants** for status values - already in place
- **Structured logging with `extra={}` dict pattern**
- **Import from canonical locations only** - never star imports

### Canonical Import Block

```python
# Additional imports for Story 10-2
from mcp_server.analysis.smf import get_pending_proposals, get_proposal
from mcp_server.utils.constants import ReclassifyStatus

# Existing imports from Story 10-1
from mcp_server.db.connection import get_connection
from mcp_server.utils.sector_classifier import MemorySector
```

### SMF Implementation Understanding

From `mcp_server/analysis/smf.py`:

**SMF Proposal Lifecycle:**
1. Proposals are created via `create_smf_proposal()`
2. Proposals have `approval_level` = "io" (I/O only) or "bilateral" (both parties)
3. Approval via `approve_proposal(proposal_id, actor)`
4. For bilateral: `approved_by_io` AND `approved_by_ethr` both must be True
5. Status transitions: PENDING → APPROVED | REJECTED | EXPIRED

**Constitutive Edge Detection (from SMF):**
```python
# SMF checks for edge_properties.edge_type == "constitutive"
# Epic 8 uses properties.is_constitutive = true
# We should support BOTH patterns for compatibility
```

**Key SMF Functions:**
- `get_pending_proposals()` - Returns list of PENDING proposals
- `get_proposal(proposal_id)` - Returns single proposal
- Proposals have: `affected_edges`, `proposed_action`, `approval_level`, `status`

### Implementation Pattern

**Modified `reclassify_memory_sector.py`:**
```python
async def reclassify_memory_sector(
    source_name: str,
    target_name: str,
    relation: str,
    new_sector: str,
    edge_id: str | None = None,
    actor: str = "I/O"
) -> dict[str, Any]:
    """..."""
    # ... validation and edge lookup (Story 10-1)

    # At this point, we have exactly one edge
    edge = edges[0]
    old_sector = edge.get("memory_sector", "semantic")

    # Story 10-2: Check constitutive edge protection
    if _is_constitutive_edge(edge):
        # Check for approved SMF proposal
        if not await _check_smf_approval(edge["id"], new_sector):
            logger.info("Constitutive edge requires consent", extra={
                "edge_id": edge["id"],
                "is_constitutive": True,
                "actor": actor
            })
            return {
                "status": ReclassifyStatus.CONSENT_REQUIRED,
                "error": "Bilateral consent required for constitutive edge",
                "edge_id": edge["id"],
                "hint": "Use smf_pending_proposals and smf_approve to grant consent"
            }

    # Proceed with reclassification...
```

**Helper Functions:**
```python
def _is_constitutive_edge(edge: dict[str, Any]) -> bool:
    """
    Check if edge is constitutive (identity-defining).

    Supports two patterns for compatibility:
    1. properties.is_constitutive = true (Epic 8 pattern)
    2. edge_properties.edge_type == "constitutive" (SMF pattern)
    """
    properties = edge.get("properties", {})

    # Epic 8 pattern
    if properties.get("is_constitutive") is True:
        return True

    # SMF pattern (for backward compatibility)
    if properties.get("edge_type") == "constitutive":
        return True

    return False


async def _check_smf_approval(
    edge_id: str,
    new_sector: str
) -> bool | dict[str, Any]:
    """
    Check if there's an approved SMF proposal for reclassifying this edge.

    Args:
        edge_id: UUID of the edge to check
        new_sector: Target sector for reclassification

    Returns:
        True if approved bilateral proposal exists, False otherwise
        OR error dict if database query fails (AC #8)

    Story 10-2: Added error handling for database connection failures
    """
    try:
        # Query smf_proposals table for APPROVED proposal
        # that affects our edge_id and is for reclassification
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, proposed_action, approval_level,
                       approved_by_io, approved_by_ethr
                FROM smf_proposals
                WHERE status = 'APPROVED'
                  AND %s = ANY(affected_edges)
                  AND (proposed_action->>'action' = 'reclassify'
                       OR proposed_action->>'action' = 'reclassify_sector')
                ORDER BY resolved_at DESC
                LIMIT 1
            """, (edge_id,))

            result = cursor.fetchone()

            if result:
                approval_level = result[2]
                approved_by_io = result[3]
                approved_by_ethr = result[4]

                # For bilateral, both must approve
                if approval_level == "bilateral":
                    return approved_by_io and approved_by_ethr
                # For io-only, just io approval needed
                return approved_by_io

            return False

    except Exception as e:
        # AC #8: Log database error and return error response
        logger.error("SMF approval check failed", extra={
            "edge_id": edge_id,
            "error": str(e),
            "error_type": type(e).__name__
        })
        return {
            "status": "error",
            "error": "Failed to check SMF approval status",
            "edge_id": edge_id,
            "details": str(e)
        }
```

### SMF Proposal for Reclassification

**Creating an SMF Proposal (for reference - done via smf_review tool):**
```python
# I/O would call smf_review to create a reclassification proposal
# The proposal would look like:
{
    "trigger_type": "MANUAL",
    "proposed_action": {
        "action": "reclassify",
        "edge_id": "uuid",
        "new_sector": "emotional"
    },
    "affected_edges": ["uuid"],
    "reasoning": "Reclassify edge to emotional sector",
    "approval_level": "bilateral"  # Constitutive = always bilateral
}
```

### Error Response Patterns

```python
# Consent required (Story 10-2 new)
{
    "status": "consent_required",
    "error": "Bilateral consent required for constitutive edge",
    "edge_id": "uuid",
    "hint": "Use smf_pending_proposals and smf_approve to grant consent"
}

# SMF database error (Story 10-2 AC #8 - NEW)
{
    "status": "error",
    "error": "Failed to check SMF approval status",
    "edge_id": "uuid",
    "details": "Database connection error or query timeout"
}

# Success (after approval)
{
    "status": "success",
    "edge_id": "uuid",
    "old_sector": "semantic",
    "new_sector": "emotional"
}

# Non-constitutive (no change from Story 10-1)
{
    "status": "success",
    ...
}
```

### Project Structure Notes

**Modified Files:**
| File | Changes |
|------|---------|
| `mcp_server/tools/reclassify_memory_sector.py` | Add constitutive check + SMF approval lookup |
| `tests/unit/test_reclassify_memory_sector.py` | Add tests for constitutive edge protection |

**New Files (if needed):**
| File | Purpose |
|------|---------|
| `tests/integration/test_reclassify_smf.py` | SMF integration tests (may already exist) |

### Previous Story Learnings (Story 10-1)

1. **Edge ID filtering BEFORE ambiguity check** - Critical AC5 logic
2. **JSONB merge operator (||)** preserves existing properties
3. **Use ReclassifyStatus constants** - Already in place
4. **ISO 8601 timestamps with Z suffix** - `"%Y-%m-%dT%H:%M:%SZ"`
5. **Structured logging with extra={}** - Never f-strings in log messages

### Git Intelligence (Recent Commits)

From recent commits:
- `b30b796 feat(epic-8,epic-9): Add sector query responses and decay config module`
- Story 10-1 completed: `reclassify_memory_sector.py` with full AC coverage
- SMF implementation from Epic 7 is production-ready
- `ReclassifyStatus.CONSENT_REQUIRED` already exists in `constants.py`

### Critical Constraints

1. **Bilateral consent is mandatory** for constitutive edges (cannot be overridden)
2. **Check both `is_constitutive` and `edge_type == "constitutive"`** for compatibility
3. **Don't create SMF proposals** - only check for existing approved ones
4. **Properties merge, not replace** - Use `||` operator in SQL
5. **Backwards compatible** - Non-constitutive edges work exactly as before

### Edge Cases

| Case | Behavior |
|------|----------|
| `is_constitutive = false` | Proceeds normally (no consent needed) |
| `is_constitutive` missing | Proceeds normally (no consent needed) |
| `is_constitutive = true`, no proposal | Return `consent_required` |
| `is_constitutive = true`, PENDING proposal | Return `consent_required` |
| `is_constitutive = true`, APPROVED proposal | Proceed with reclassification |
| `is_constitutive = true`, DB connection fails | Return `error` status (AC #8) |
| `edge_type == "constitutive"` (SMF pattern) | Treat as constitutive |

### FR/NFR Coverage

**Functional Requirements:**
- FR9: System can enforce bilateral consent requirement for reclassification of constitutive edges
- FR23: System can integrate sector reclassification with existing constitutive edge protection (SMF)

**Non-Functional Requirements:**
- NFR9: Sector reclassification must respect existing constitutive edge protection (SMF bilateral consent)

### Testing Strategy

1. **Unit Tests**: Mock-based tests for constitutive edge check logic
2. **Non-constitutive Tests**: Verify no change in behavior for regular edges
3. **SMF Approval Tests**: Mock SMF proposal lookup
4. **Integration Tests**: Full flow with DB (optional - can use mocks)
5. **Regression Tests**: All Story 10-1 tests must still pass

### References

- [Source: project-context.md#SMF-Rules] - Constitutive edges require bilateral consent
- [Source: _bmad-output/planning-artifacts/epics.md#Story-3.2] - Full acceptance criteria
- [Source: bmad-docs/epics/epic-8-architecture.md#SMF-Integration-Boundary] - SMF patterns
- [Source: mcp_server/analysis/smf.py] - SMF implementation details
- [Source: mcp_server/tools/reclassify_memory_sector.py] - Story 10-1 implementation
- [Source: docs/stories/10-1-reclassify-memory-sector-tool.md] - Previous story learnings

## Dev Agent Record

### Agent Model Used

Claude (glm-4.7)

### Debug Log References

None - Implementation completed without major debugging issues.

### Completion Notes List

**Implementation Summary:**
- ✅ All 9 Acceptance Criteria implemented and tested
- ✅ 22 unit tests passing (11 from Story 10-1 + 11 new for Story 10-2)
- ✅ 3 SMF integration tests passing
- ✅ Mypy strict: Success, no type errors

**Key Implementation Details:**
1. **`_is_constitutive_edge()` helper**: Supports both Epic 8 (`is_constitutive`) and SMF (`edge_type == "constitutive"`) patterns for backward compatibility
2. **`_check_smf_approval()` function**: Returns `dict[str, Any]` with `approved` and `proposal_id` fields, queries `smf_proposals` table for APPROVED reclassification proposals with proper error handling (AC #8)
3. **Constitutive edge check**: Integrated into main `reclassify_memory_sector()` function after edge lookup
4. **Structured logging**: Added for both consent required (AC #7) and successful reclassification including `smf_proposal_id` (AC #9)
5. **Error handling**: Database connection errors during SMF query return error response without modifying edge (AC #8)
6. **Sector validation**: Code review fix - validates `new_sector` matches SMF proposal's target sector

**Test Coverage:**
- AC #1: Constitutive edge without approval returns `consent_required` ✅
- AC #2: Approved SMF proposal allows reclassification ✅
- AC #3: Non-constitutive edges proceed normally ✅
- AC #4: SMF integration pattern verified ✅
- AC #5: Uses `ReclassifyStatus.CONSENT_REQUIRED` constant ✅
- AC #6: No regressions - all Story 10-1 tests still pass ✅
- AC #7: Structured logging on consent check ✅
- AC #8: Database connection error handling ✅
- AC #9: Structured logging on successful reclassification WITH smf_proposal_id ✅ (Code Review Fix)

**Test Results:**
```bash
# Unit tests
PYTHONPATH=. ./venv/bin/python -m pytest tests/unit/test_reclassify_memory_sector.py -v
# Result: 22 passed in 6.83s

# SMF integration tests
PYTHONPATH=. ./venv/bin/python -m pytest tests/integration/test_reclassify_smf.py -v
# Result: 3 passed in 6.23s

# Mypy strict type checking
PYTHONPATH=. ./venv/bin/python -m mypy --strict mcp_server/tools/reclassify_memory_sector.py
# Result: Success: no issues found in 1 source file
```

**Design Decisions:**
1. **SMF proposal lookup**: Returns `dict[str, Any]` with explicit structure for clarity (Code Review Fix)
2. **Constitutive detection**: Checks both `is_constitutive` and `edge_type == "constitutive"` for maximum compatibility
3. **Logging strategy**: Separate log entries for consent check vs. successful reclassification for better audit trail (AC #7, #9)
4. **Error handling**: Try-except wrapper in `_check_smf_approval()` ensures DB errors don't corrupt edge data
5. **Sector validation**: Validates that proposal's target sector matches requested sector (Code Review Fix)

**Integration Points:**
- Uses `smf_proposals` table with query for APPROVED status
- Checks `affected_edges` JSONB array for edge_id match
- Verifies `approval_level == "bilateral"` requires both `approved_by_io` AND `approved_by_ethr`
- Leverages existing `get_connection()` context manager pattern
- Extracts and logs `proposal_id` for audit trail (Code Review Fix)

**Code Review Fixes Applied (2026-01-08):**
1. **AC #9 Compliance**: Added `smf_proposal_id` to constitutive edge reclassification log
2. **Return Type Clarity**: Changed `_check_smf_approval()` from `bool | dict` to explicit `dict` structure
3. **Security Enhancement**: Added `new_sector` validation against SMF proposal
4. **Test Coverage**: Added test for SMF pattern `edge_type == "constitutive"`
5. **Documentation**: Updated all task checkboxes to reflect actual completion status

**No Issues Encountered:**
- Implementation proceeded smoothly with TDD approach (Red-Green-Refactor)
- All tests passed after code review fixes
- Mypy strict compliance achieved without modifications

### File List

**Modified Files (Story 10-2 Implementation):**
- `mcp_server/tools/reclassify_memory_sector.py` - Added constitutive edge protection logic, SMF approval lookup, proposal_id tracking (Code Review Fix)
- `tests/unit/test_reclassify_memory_sector.py` - Added 11 new unit tests for Story 10-2 (including SMF pattern test - Code Review Fix)

**New Files:**
- `tests/integration/test_reclassify_smf.py` - SMF integration tests for reclassification

**Other Files Modified During Sprint (git detected):**
- `bmad-docs/sprint-status.yaml` - Sprint tracking updates
- `mcp_server/tools/__init__.py` - Export updates
- `mcp_server/utils/__init__.py` - Export updates
- `pyproject.toml` - Dependency updates
- `tests/performance/test_sector_filter_performance.py` - Performance test updates
- `tests/test_hybrid_search.py` - Hybrid search test updates
- `docs/stories/10-1-reclassify-memory-sector-tool.md` - Story 10-1 documentation
- `docs/stories/9-4-sector-filter-for-hybrid-search.md` - Story 9-4 documentation
- `mcp_server/utils/constants.py` - Added ReclassifyStatus constants
- `tests/unit/test_constants.py` - Constants unit tests

**Note:** The sprint involved multiple stories (9-4, 10-1, 10-2). Only files directly related to Story 10-2 are listed above under "Modified Files (Story 10-2 Implementation)".

