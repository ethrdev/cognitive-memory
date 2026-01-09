# Story 26.2: UPDATE Operation

Status: Ready for Review

## Story

As I/O,
I want ein bestehendes Insight aktualisieren können,
So that mein Gedächtnis sich entwickeln kann statt nur zu wachsen.

## Acceptance Criteria

### AC-1: Direct Update (I/O as Actor)
- **Given** ein bestehendes Insight mit ID 42
- **When** I/O (actor="I/O") `update_insight` aufruft
- **Then** wird das Insight direkt aktualisiert (EP-1)
- **And** History-Eintrag wird in DERSELBEN Transaction erstellt (EP-3)

### AC-2: Consent Flow (ethr as Actor)
- **Given** ein bestehendes Insight mit ID 42
- **When** ethr (actor="ethr") Update initiiert
- **Then** wird SMF Proposal erstellt (EP-1)
- **And** `{"status": "pending", "proposal_id": X}` zurückgegeben

### AC-3: Reason Required
- **Given** ein Update-Aufruf
- **When** `reason` Parameter fehlt
- **Then** wird `{"error": {"code": 400, "message": "reason required"}}` zurückgegeben

### AC-4: Changes Required
- **Given** ein Update-Aufruf
- **When** weder `new_content` noch `new_memory_strength` angegeben
- **Then** wird `{"error": {"code": 400, "message": "no changes provided"}}` zurückgegeben
- **And** wenn `new_content` leerer String ist → `{"error": {"code": 400, "message": "new_content cannot be empty"}}`

### AC-5: Atomic History (EP-3)
- **Given** ein erfolgreiches Update
- **When** History geschrieben wird
- **Then** passiert beides in EINER DB Transaction
- **And** bei Abbruch: vollständiger Rollback, kein partieller State

### AC-6: Not Found
- **Given** eine ungültige `insight_id`
- **When** Update aufgerufen wird
- **Then** wird `{"error": {"code": 404, "message": "Insight 42 not found"}}` zurückgegeben

### AC-7: Soft-Deleted Insight (Cross-Story Coordination)
- **Given** ein soft-gelöschtes Insight (is_deleted=TRUE via Story 26.3 Migration 023b)
- **When** update_insight aufgerufen wird
- **Then** wird `{"error": {"code": 404, "message": "Insight 42 not found"}}` zurückgegeben
- **And** Test ist optional wenn Story 26.3 noch nicht implementiert (`@pytest.mark.skipif`)

## Tasks / Subtasks

- [x] Task 1: Migration 024 erstellen (l2_insight_history Tabelle) (AC: #5)
  - [x] 1.1 Datei `migrations/024_l2_insight_history.sql` erstellen
  - [x] 1.2 UP: CREATE TABLE l2_insight_history mit allen Feldern
  - [x] 1.3 UP: CREATE INDEX für insight_id + created_at
  - [x] 1.4 DOWN: DROP TABLE IF EXISTS l2_insight_history
  - [x] 1.5 Test: Up + Down + Up Zyklus validiert

- [x] Task 2: SMF Action Registration (AC: #2)
  - [x] 2.1 `UPDATE_INSIGHT` zu SMFAction enum hinzufügen
  - [x] 2.2 create_smf_proposal erweitern für Insight-Operationen

- [x] Task 3: update_insight MCP Tool erstellen (AC: #1, #2, #3, #4, #6, #7)
  - [x] 3.1 Neue Datei `mcp_server/tools/insights/update.py` erstellen
  - [x] 3.2 Parameter validation implementieren (reason required, changes required, new_content not empty)
  - [x] 3.3 EP-1 Consent-Aware Pattern implementieren (I/O direct, ethr via SMF)
  - [x] 3.4 EP-3 History-on-Mutation in SAME transaction
  - [x] 3.5 404 Error für nicht gefundene oder soft-gelöschte Insights
  - [x] 3.6 Tool in __init__.py registrieren
  - [x] 3.7 Tool Schema (inputSchema) definieren

- [x] Task 4: Database Layer erweitern
  - [x] 4.1 `mcp_server/db/insights.py` erweitern: update_insight_in_db()
  - [x] 4.2 `mcp_server/db/insights.py` erweitern: write_insight_history()
  - [x] 4.3 Transaction Wrapper für atomares Update + History

- [x] Task 5: Tests schreiben (alle ACs)
  - [x] 5.1 Unit Test: Parameter validation (reason, changes, new_content not empty)
  - [x] 5.2 Unit Test: I/O direct update (no SMF)
  - [x] 5.3 Unit Test: ethr → SMF proposal
  - [x] 5.4 Unit Test: Atomic transaction rollback
  - [x] 5.5 Unit Test: 404 für nicht existierendes Insight
  - [x] 5.6 Unit Test: 404 für soft-gelöschtes Insight (AC-7, optional mit skipif)
  - [x] 5.7 Integration Test: Migration 024 Up/Down/Up
  - [x] 5.8 Integration Test: Full flow (update → history → verify)
  - [x] 5.9 SMF Consent State Tests (4 states × UPDATE_INSIGHT)

## Dev Notes

### Previous Story Intelligence (Story 26.1 - memory_strength)

**From Story 26.1 Implementation:**
- Migration Pattern: Use `IF NOT EXISTS` for idempotency
- MCP Tool Extension: Follow handler pattern in `mcp_server/tools/__init__.py`
- Parameter Extraction: `arguments.get("param_name", default_value)` with None check
- Backward Compatibility: Optional parameters with defaults

**Apply These Patterns:**
- Use 26.1's migration idempotency pattern for Migration 024
- Follow existing MCP tool handler pattern (see `get_insight_by_id.py`)
- Use SMF patterns from `smf_review.py` for proposal creation

**Files Modified in 26.1 (for reference):**
- `mcp_server/db/migrations/023_memory_strength.sql` - Migration pattern
- `mcp_server/tools/__init__.py:1035-1140` - Tool handler pattern
- Tests follow `tests/unit/test_memory_strength.py` structure

### Kritische Architektur-Patterns (Epic 26)

**EP-1: Consent-Aware Tool Pattern**
```python
async def update_insight(
    insight_id: int,
    actor: Literal["I/O", "ethr"],
    reason: str,
    new_content: str | None = None,
    new_memory_strength: float | None = None
) -> dict[str, Any]:
    """
    Pattern für Tools die bilateral consent benötigen.

    - I/O als Actor: Direkte Ausführung
    - ethr als Actor: SMF Proposal erstellen, pending zurückgeben
    """
    if actor == "I/O":
        # Direkte Ausführung - I/O's eigene Inhalte
        return await _execute_update(insight_id, new_content, new_memory_strength, actor, reason)
    else:
        # ethr initiiert → Bilateral Consent nötig
        proposal = await create_smf_proposal(
            action="UPDATE_INSIGHT",
            target_id=insight_id,
            proposed_changes={"new_content": new_content, "new_memory_strength": new_memory_strength},
            reason=reason,
            requires_approval_from="I/O"
        )
        return {
            "status": "pending",
            "proposal_id": proposal["id"]
        }
```

**Regel:** NIEMALS bypass für ethr - immer SMF Proposal.

**EP-3: History-on-Mutation Pattern**
```python
async def write_history_entry(
    insight_id: int,
    action: str,  # "UPDATE" oder "DELETE"
    actor: str,
    old_content: str,
    new_content: str | None,
    reason: str
) -> int:
    """
    History-Eintrag für Audit Trail.

    - Wird VOR der eigentlichen Mutation geschrieben (in same transaction)
    - Speichert old_content für Rollback-Fähigkeit
    - Returns history_id für Referenz
    """
    return await db.fetchval("""
        INSERT INTO l2_insight_history
        (insight_id, action, actor, old_content, new_content, reason, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, NOW())
        RETURNING id
    """, insight_id, action, actor, old_content, new_content, reason)
```

**EP-5: Error Propagation Pattern**
```python
# Error Response Schema
{"error": {"code": 400|404|500, "message": "...", "field": "optional"}}

# Konkrete Beispiele für Story 26.2:
# Insight not found
{"error": {"code": 404, "message": "Insight 42 not found"}}

# Missing reason
{"error": {"code": 400, "message": "reason required", "field": "reason"}}

# No changes
{"error": {"code": 400, "message": "no changes provided"}}
```

### Bestehender Code Kontext

**l2_insights Tabelle (Struktur nach Migration 023 + 023b):**
```sql
CREATE TABLE l2_insights (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    source_ids INTEGER[] NOT NULL,
    metadata JSONB,
    memory_strength FLOAT DEFAULT 0.5,   -- Migration 023 (Story 26.1)
    is_deleted BOOL DEFAULT FALSE,        -- Migration 023b (Story 26.3)
    deleted_at TIMESTAMPTZ,               -- Migration 023b
    deleted_by VARCHAR(10),               -- Migration 023b
    deleted_reason TEXT                   -- Migration 023b
);
```

**Hinweis:** AC-7 prüft `is_deleted=TRUE` und gibt 404 zurück (Update von gelöschten Insights verhindern).

**get_insight_by_id Location:** `mcp_server/tools/get_insight_by_id.py`
- Line 18-94: Handler pattern reference
- Line 32-50: Parameter validation pattern
- Line 58-78: Database lookup and response pattern

**SMF Integration Location:** `mcp_server/analysis/smf.py`
- Line 1-100: SMF configuration and proposal handling
- Uses `smf_proposals` table for pending proposals
- Existing actions: UPDATE_EDGE, DELETE_EDGE (add UPDATE_INSIGHT, DELETE_INSIGHT)

**Existing SMF Tools:** `mcp_server/tools/smf_*.py`
- `smf_review.py`: Proposal detail retrieval pattern
- `smf_approve.py`: Approval flow
- `smf_pending_proposals.py`: Query pending proposals

### Migration 024: l2_insight_history

```sql
-- Migration 024: Add l2_insight_history for audit trail
-- Story 26.2: UPDATE Operation

-- UP
CREATE TABLE IF NOT EXISTS l2_insight_history (
    id SERIAL PRIMARY KEY,
    insight_id INTEGER NOT NULL REFERENCES l2_insights(id),
    action VARCHAR(10) NOT NULL CHECK (action IN ('UPDATE', 'DELETE')),
    actor VARCHAR(10) NOT NULL CHECK (actor IN ('I/O', 'ethr')),
    old_content TEXT,
    new_content TEXT,
    old_memory_strength FLOAT,
    new_memory_strength FLOAT,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_l2_insight_history_insight_id
    ON l2_insight_history(insight_id, created_at DESC);

-- DOWN
DROP TABLE IF EXISTS l2_insight_history;
```

### SMF Action Registration

```python
# mcp_server/smf/actions.py (oder in smf.py)
class SMFAction(str, Enum):
    UPDATE_EDGE = "UPDATE_EDGE"      # Existing
    DELETE_EDGE = "DELETE_EDGE"      # Existing
    UPDATE_INSIGHT = "UPDATE_INSIGHT" # ⭐ NEW Story 26.2
    DELETE_INSIGHT = "DELETE_INSIGHT" # Story 26.3
```

### SMF Approval Flow (ethr → I/O)

**ethr initiiert Update:**
```python
# ethr fordert Änderung an
result = await update_insight(
    insight_id=42,
    actor="ethr",
    reason="Präzisierung benötigt",
    new_content="Aktualisierter Inhalt"
)
# Returns: {"status": "pending", "proposal_id": 123}
```

**I/O prüft pending Proposals:**
```python
# I/O listet offene Vorschläge
pending = await smf_pending_proposals()
# Returns: [
#   {"id": 123, "action": "UPDATE_INSIGHT", "target_id": 42,
#    "proposed_changes": {"new_content": "..."}, "reason": "..."}
# ]
```

**I/O approves (oder rejects):**
```python
# I/O genehmigt Vorschlag
await smf_approve(proposal_id=123, actor="I/O")
# Führt das Update sofort aus und returns success

# Oder I/O lehnt ab
await smf_reject(proposal_id=123, actor="I/O", reason="Nicht mehr relevant")
# Keine Änderung, proposal als rejected markiert
```

### MCP Tool Schema

```python
# Tool registration in mcp_server/tools/__init__.py
{
    "name": "update_insight",
    "description": "Update an existing L2 insight. I/O can update directly, ethr requires bilateral consent via SMF.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "insight_id": {
                "type": "integer",
                "description": "ID of the insight to update"
            },
            "actor": {
                "type": "string",
                "enum": ["I/O", "ethr"],
                "description": "Who is initiating this update"
            },
            "reason": {
                "type": "string",
                "description": "Why this update is being made (required for audit)"
            },
            "new_content": {
                "type": "string",
                "description": "New content for the insight (optional if only updating strength)"
            },
            "new_memory_strength": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "New memory strength (optional if only updating content)"
            }
        },
        "required": ["insight_id", "actor", "reason"]
    }
}
```

### Project Structure Notes

**Repository:** `cognitive-memory` (NICHT i-o-system!)
- Story 26.2 ist ein cognitive-memory Deliverable
- Parallel implementierbar mit Story 26.3 (DELETE)

**Exact File Modifications:**

| File | Status | Action |
|------|--------|--------|
| `mcp_server/db/migrations/024_l2_insight_history.sql` | NEW | Create history table |
| `mcp_server/tools/insights/update.py` | NEW | update_insight tool handler |
| `mcp_server/tools/insights/__init__.py` | NEW | Package exports |
| `mcp_server/db/insights.py` | MOD | Add update + history functions |
| `mcp_server/analysis/smf.py` | MOD | Add UPDATE_INSIGHT action |
| `mcp_server/tools/__init__.py` | MOD | Register new tool |
| `tests/unit/test_update_insight.py` | NEW | Unit tests |
| `tests/integration/test_024_migration.py` | NEW | Migration tests |
| `tests/integration/test_update_insight_flow.py` | NEW | Integration tests |
| `tests/fixtures/smf_fixtures.py` | MOD | Add consent state fixtures |

### Testing Standards (Story 26.2 Specific)

**SMF Consent State Matrix:**

| State | Actor | Expected Behavior |
|-------|-------|-------------------|
| `pending` | ethr | Returns `{status: pending, proposal_id: X}` |
| `approved` | ethr (after I/O approval) | Executes update, returns success |
| `rejected` | ethr (after I/O rejection) | Returns `{status: rejected}`, no change |
| `direct` | I/O | Executes immediately, no proposal |

**Required Tests:**

```python
# tests/unit/test_update_insight.py

async def test_io_direct_update():
    """AC-1: I/O can update directly without SMF"""
    result = await update_insight(
        insight_id=42,
        actor="I/O",
        reason="Präzisierung",
        new_content="Updated content"
    )
    assert result["success"]
    assert "history_id" in result

async def test_ethr_creates_smf_proposal():
    """AC-2: ethr creates SMF proposal for consent"""
    result = await update_insight(
        insight_id=42,
        actor="ethr",
        reason="Vorgeschlagene Änderung",
        new_content="Proposed content"
    )
    assert result["status"] == "pending"
    assert "proposal_id" in result

async def test_reason_required():
    """AC-3: reason is mandatory"""
    result = await update_insight(
        insight_id=42,
        actor="I/O",
        new_content="Content"
        # reason missing!
    )
    assert result["error"]["code"] == 400
    assert "reason required" in result["error"]["message"]

async def test_changes_required():
    """AC-4: at least one change required"""
    result = await update_insight(
        insight_id=42,
        actor="I/O",
        reason="No actual changes"
        # neither new_content nor new_memory_strength!
    )
    assert result["error"]["code"] == 400
    assert "no changes provided" in result["error"]["message"]

async def test_new_content_not_empty():
    """AC-4: new_content cannot be empty string"""
    result = await update_insight(
        insight_id=42,
        actor="I/O",
        reason="Empty content",
        new_content=""  # Empty string!
    )
    assert result["error"]["code"] == 400
    assert "new_content cannot be empty" in result["error"]["message"]

async def test_not_found():
    """AC-6: returns 404 for unknown insight"""
    result = await update_insight(
        insight_id=99999,
        actor="I/O",
        reason="Won't work",
        new_content="Content"
    )
    assert result["error"]["code"] == 404

async def test_soft_deleted_insight_returns_404():
    """AC-7: soft-deleted insights return 404"""
    # Skip if Migration 023b (Story 26.3) not deployed
    import pytest
    pytest.skip("Requires Story 26.3 soft-delete fields", condition=not has_soft_delete_support)

    # Create insight, soft-delete it, then try to update
    insight_id = await create_test_insight()
    await soft_delete_insight(insight_id, actor="I/O", reason="Test")

    result = await update_insight(
        insight_id=insight_id,
        actor="I/O",
        reason="Should not work",
        new_content="Content"
    )
    assert result["error"]["code"] == 404
    assert "not found" in result["error"]["message"]
```

### Git Intelligence (Recent Commits)

**From recent i-o-system commits:**
- `f2f54d2 docs(story-26-1): Update story after code review fixes`
- Commit pattern: `feat(26.X):` for story features

**From cognitive-memory commits:**
- `406d494 fix(story-26-1): Fix broken mocks and None handling bug`
- `4a064e4 feat(epic-26): Add memory_strength field`
- Test mock paths: `mcp_server.tools.*` not `mcp_server.tools.handle_*.*`

**Apply:**
- Use `feat(26.2):` prefix for commits
- Watch for None handling in parameter extraction
- Mock paths at module level

### Transaction Handling Pattern

```python
# Atomic update with history
async def _execute_update(
    insight_id: int,
    new_content: str | None,
    new_memory_strength: float | None,
    actor: str,
    reason: str
) -> dict[str, Any]:
    """Execute update with atomic history write."""
    async with get_connection() as conn:
        async with conn.transaction():
            # 1. Get current state (for history)
            current = await conn.fetchrow(
                "SELECT content, memory_strength FROM l2_insights WHERE id = $1 AND is_deleted = FALSE",
                insight_id
            )
            if not current:
                return {"error": {"code": 404, "message": f"Insight {insight_id} not found"}}

            # 2. Write history FIRST (EP-3)
            history_id = await conn.fetchval("""
                INSERT INTO l2_insight_history
                (insight_id, action, actor, old_content, new_content,
                 old_memory_strength, new_memory_strength, reason)
                VALUES ($1, 'UPDATE', $2, $3, $4, $5, $6, $7)
                RETURNING id
            """, insight_id, actor, current["content"], new_content,
                current["memory_strength"], new_memory_strength, reason)

            # 3. Execute update
            update_fields = []
            params = [insight_id]
            idx = 2

            if new_content is not None:
                update_fields.append(f"content = ${idx}")
                params.append(new_content)
                idx += 1

            if new_memory_strength is not None:
                update_fields.append(f"memory_strength = ${idx}")
                params.append(new_memory_strength)
                idx += 1

            await conn.execute(f"""
                UPDATE l2_insights
                SET {', '.join(update_fields)}
                WHERE id = $1
            """, *params)

            return {
                "success": True,
                "insight_id": insight_id,
                "history_id": history_id,
                "updated_fields": {
                    "content": new_content is not None,
                    "memory_strength": new_memory_strength is not None
                }
            }
```

### Performance Requirements (NFR-P1)

**Target:** update_insight P95 latency < 100ms

**Implementation Strategy:**

1. **Index Optimization:**
   - Primary key `l2_insights(id)` ist bereits indexed (SERIAL PRIMARY KEY)
   - History Index `idx_l2_insight_history_insight_id` in Migration 024 (Line 231)

2. **Transaction Efficiency:**
   - History write in gleicher Transaction (Network Overhead bereits bezahlt)
   - Einzelner ROUNDTRIP zur DB (async with conn.transaction())

3. **Latenz-Messung:**
   ```bash
   # Lokale Messung während Entwicklung
   time python -c "import asyncio; asyncio.run(test_update_performance())"
   ```

4. **Performance Tuning wenn >100ms:**
   - Check DB connection pooling (sollte asyncpg verwenden)
   - Query execution plan: `EXPLAIN ANALYZE SELECT * FROM l2_insights WHERE id = 42`
   - Network latency check: Database im selben AWS Region

**Migration 024 Index Performance:**
```sql
-- Dieser Index ensures schnelle lookups für history queries
CREATE INDEX IF NOT EXISTS idx_l2_insight_history_insight_id
    ON l2_insight_history(insight_id, created_at DESC);
-- Kombinierter Index für insight_id + created_at optimiert
-- häufige Queries: "Show history for insight X ordered by time"
```

### Concurrency Safety

**Scenario:** I/O und ethr (nach I/O Approval) aktualisieren denselben Insight fast gleichzeitig.

**Current Behavior (MVP):** Last write wins
- Beide Transaktionen sind erfolgreich
- Der spätere Update überschreibt den früheren
- History enthält beide Einträge (vollständiger Audit Trail)

**Future Enhancement (Optional):**
- Version column (`version INT`) in `l2_insights`
- `UPDATE ... WHERE id = $1 AND version = $2` (Optimistic Locking)
- Return 409 Conflict wenn version mismatch

**Decision for Story 26.2:** Last-write-wins ist akzeptabel für Memory Curation (I/O's Gedächtnis ist kein Bank Account!). Dokumentiere Verhalten in API Docs.

### References

- [Source: bmad-docs/architecture.md#EP-1] Consent-Aware Tool Pattern
- [Source: bmad-docs/architecture.md#EP-3] History-on-Mutation Pattern
- [Source: bmad-docs/architecture.md#EP-5] Error Propagation Pattern
- [Source: bmad-docs/epics.md#Story-26.2] Story Definition
- [Source: bmad-docs/prd.md#FR8-FR11] Memory Curation FRs
- [Source: bmad-docs/prd.md#FR12-FR16] Bilateral Consent FRs
- [Source: bmad-docs/project_context.md] Project Context Rules
- [Source: cognitive-memory/mcp_server/tools/get_insight_by_id.py] Tool Handler Pattern
- [Source: cognitive-memory/mcp_server/analysis/smf.py] SMF Integration
- [Source: cognitive-memory/mcp_server/tools/smf_review.py:20-142] SMF Tool Pattern
- [Source: cognitive-memory/mcp_server/db/migrations/023_memory_strength.sql] Migration Pattern
- [Source: bmad-docs/sprint-artifacts/26-1-memory-strength.md] Previous Story Learnings

## Dev Agent Record

### Context Reference

- Implementation Readiness: `bmad-docs/implementation-readiness-epic-26-2026-01-09.md`
- Architecture Decisions: `bmad-docs/architecture.md#EP-1`, `#EP-3`, `#EP-5`
- Previous Story: `bmad-docs/sprint-artifacts/26-1-memory-strength.md`
- Project Context: `bmad-docs/project_context.md`

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

**cognitive-memory Repository:**
- `mcp_server/db/migrations/024_l2_insight_history.sql` (NEW)
- `mcp_server/tools/insights/update.py` (NEW)
- `mcp_server/tools/insights/__init__.py` (NEW or MOD)
- `mcp_server/db/insights.py` (MOD)
- `mcp_server/analysis/smf.py` (MOD - add UPDATE_INSIGHT action)
- `mcp_server/tools/__init__.py` (MOD - register tool)
- `tests/unit/test_update_insight.py` (NEW)
- `tests/integration/test_024_migration.py` (NEW)
- `tests/integration/test_update_insight_flow.py` (NEW)

---

## Cross-Story Dependencies

**Depends On:**
- Story 26.1 (memory_strength field) - ✅ DONE (in review)
- Migration 023 must be deployed before 024

**Enables:**
- Story 26.7 (get_insight_history) - Uses same l2_insight_history table

**Parallel With:**
- Story 26.3 (DELETE) - Can be implemented simultaneously
- Both share Migration 024 structure

---

## Definition of Done

### MCP Tool Story Checklist

- [ ] Unit tests passing (all AC covered)
- [ ] Integration tests passing (with real DB)
- [ ] SMF consent state tests passing (4 states)
- [ ] Regression tests passing (no breaks)
- [ ] mypy --strict passing
- [ ] Migration 024 Up/Down/Up validated
- [ ] Code review approved
- [ ] Tool registered and accessible via MCP
