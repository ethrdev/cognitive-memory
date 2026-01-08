# Story 6.4: list_episodes MCP Tool

Status: done

## Story

Als autonomer Agent (I/O),
möchte ich alle Episode-Einträge mit Pagination auflisten,
sodass ich Lücken erkennen kann (z.B. fehlende Sessions).

## Acceptance Criteria

### AC-6.4.1: list_episodes Tool erstellen

**Given** Episodes existieren in der Datenbank
**When** ich das MCP Tool `list_episodes` aufrufe mit optionalen Parametern
**Then** erhalte ich alle Episodes mit Pagination, sortiert nach `created_at DESC` (neueste zuerst):

```json
{
    "episodes": [
        {"id": 2, "query": "What is GraphRAG...", "reward": 0.6, "created_at": "2025-12-02T14:30:00+00:00"},
        {"id": 1, "query": "How to connect...", "reward": 0.8, "created_at": "2025-12-01T10:00:00+00:00"}
    ],
    "total_count": 86,
    "limit": 50,
    "offset": 0,
    "status": "success"
}
```

**Note:** `status` ist immer das letzte Feld. `created_at` ist ISO 8601 mit Timezone.

### AC-6.4.2: Pagination funktioniert

**Given** mehr als 50 Episodes existieren in der Datenbank
**When** ich `list_episodes` mit `limit: 10, offset: 20` aufrufe
**Then** erhalte ich:
- Episodes 21-30 (10 Einträge, sortiert DESC)
- `total_count`: Gesamtzahl aller Episodes (nicht nur Page)
- `limit`: 10
- `offset`: 20

**And** wenn `offset >= total_count`, dann leere `episodes` Liste (kein Error)

### AC-6.4.3: Zeitfilter funktioniert

**Given** Episodes aus verschiedenen Zeiträumen existieren
**When** ich `list_episodes` mit `since: "2025-12-01T00:00:00Z"` aufrufe
**Then** erhalte ich nur Episodes ab diesem Zeitpunkt

**And** `total_count` reflektiert die gefilterte Anzahl

### AC-6.4.4: Parameter-Validierung

**Given** list_episodes hat optionale Parameter
**When** ungültige Parameter übergeben werden:
- `limit` < 1 oder > 100
- `offset` < 0
- `since` kein gültiger ISO 8601 Timestamp
**Then** wird eine strukturierte Error-Response zurückgegeben:

```json
{
    "error": "Parameter validation failed",
    "details": "limit must be between 1 and 100",
    "tool": "list_episodes"
}
```

### AC-6.4.5: Leere Datenbank

**Given** keine Episodes existieren
**When** ich `list_episodes` aufrufe
**Then** erhalte ich:

```json
{
    "episodes": [],
    "total_count": 0,
    "limit": 50,
    "offset": 0,
    "status": "success"
}
```

### AC-6.4.6: Error Handling

**Given** ein Database-Fehler tritt auf
**When** die Abfrage fehlschlägt
**Then** wird eine strukturierte Error-Response zurückgegeben:

```json
{
    "error": "Database operation failed",
    "details": "Connection timeout",
    "tool": "list_episodes"
}
```

## Tasks / Subtasks

### Task 1: DB-Funktion erstellen (AC: 6.4.1, 6.4.2, 6.4.3, 6.4.5)

- [x] Subtask 1.1: Erstelle `mcp_server/db/episodes.py`
- [x] Subtask 1.2: Implementiere `list_episodes()` Funktion

### Task 2: MCP Tool Implementation (AC: 6.4.1, 6.4.4)

- [x] Subtask 2.1: Erstelle `mcp_server/tools/list_episodes.py`
- [x] Subtask 2.2: Parameter Extraction und Defaults
- [x] Subtask 2.3: Parameter-Validierung

### Task 3: Tool Registration (AC: 6.4.1)

- [x] Subtask 3.1: Registriere in `mcp_server/tools/__init__.py`
- [x] Subtask 3.2: Docstring Update (15 → 16 tools)

### Task 4: Error Handling (AC: 6.4.4, 6.4.6)

- [x] Subtask 4.1: Wrap DB-Call in try/except

### Task 5: Testing (AC: 6.4.1-6.4.6)

- [x] Subtask 5.1: Unit Tests (`tests/test_list_episodes.py`) - 14 tests
- [x] Subtask 5.2: Integration Test with real DB

## Dev Notes

### Critical Implementation Patterns

**1. RealDictCursor:** `get_connection()` returns cursor with dict-like row access:
```python
row["id"]      # ✅ Correct
row[0]         # ❌ Wrong - don't use tuple access
```

**2. datetime→ISO Konvertierung:**
```python
"created_at": row["created_at"].isoformat() if row["created_at"] else None
```

**3. Logger Patterns:**
- ASYNC handler: Logger INSIDE function
- SYNC DB function: Logger at module level

**4. Error Response:** Always include `"tool": "list_episodes"`

### episode_memory Schema

```sql
CREATE TABLE episode_memory (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    reward FLOAT NOT NULL,             -- -1.0 to +1.0
    reflection TEXT NOT NULL,          -- NOT returned (too large)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    embedding vector(1536) NOT NULL    -- NOT returned (too large)
);
```

### Response Mapping

| Field | DB Column | Transformation |
|-------|-----------|----------------|
| `id` | `id` | Direct int |
| `query` | `query` | Direct string |
| `reward` | `reward` | Direct float |
| `created_at` | `created_at` | `.isoformat()` |

### File Structure

**NEW:**
- `mcp_server/db/episodes.py`
- `mcp_server/tools/list_episodes.py`
- `tests/test_list_episodes.py`

**MODIFIED:**
- `mcp_server/tools/__init__.py`

### References

- [Pattern: mcp_server/db/stats.py] - DB function structure
- [Pattern: mcp_server/tools/count_by_type.py] - Tool handler structure
- [Pattern: tests/test_count_by_type.py] - Test structure
- [Schema: mcp_server/db/migrations/001_initial_schema.sql]

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-06 | Story created | Claude Opus 4.5 (create-story) |
| 2025-12-06 | Quality review - added critical patterns, test insert, ISO conversion | Bob SM (validate-create-story) |
| 2025-12-06 | Implementation complete - all ACs satisfied, 14 tests passing | Claude Opus 4.5 (dev-story workflow) |

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

**Story 6.4 Implementation Completed Successfully**

- ✅ **AC-6.4.1 list_episodes Tool erstellen:** MCP tool returns episodes with pagination, sorted by created_at DESC
- ✅ **AC-6.4.2 Pagination funktioniert:** limit/offset work correctly, total_count independent of pagination
- ✅ **AC-6.4.3 Zeitfilter funktioniert:** since parameter filters by created_at >= timestamp
- ✅ **AC-6.4.4 Parameter-Validierung:** Invalid limit (0, 101), offset (-1), since format rejected with structured error
- ✅ **AC-6.4.5 Leere Datenbank:** Empty DB returns empty list with total_count=0
- ✅ **AC-6.4.6 Error Handling:** DB errors return structured error response with tool identifier
- ✅ **Red-Green-Refactor:** Tests written first (14 tests), then implementation
- ✅ **All 14 tests pass** (11 unit tests + 2 DB function tests + 1 integration test)
- ✅ **No regressions:** Story 6.1 (11 tests), 6.2 (22 tests), 6.3 (10 tests) still pass (43 total)
- ✅ **Tool Count:** Updated from 15 to 16 tools in module docstring

### File List

**NEW Files:**
- `mcp_server/db/episodes.py` - Episodes DB query function (87 lines)
- `mcp_server/tools/list_episodes.py` - MCP Tool handler (85 lines)
- `tests/test_list_episodes.py` - Test suite with 14 tests (200 lines)

**MODIFIED Files:**
- `mcp_server/tools/__init__.py` - Import (line 42), Tool definition (lines 2238-2265), Handler mapping (line 2285)

---

## Code Review Record

### Review Date
2025-12-06

### Reviewer
Claude Opus 4.5 (code-review workflow)

### Review Summary

**Issues Found:** 0 High, 1 Medium, 2 Low
**Git vs Story Discrepancies:** 0

### Issues Fixed

**[MED-1] FIXED: Docstring fehlte `get_golden_test_results`**
- **File:** `mcp_server/tools/__init__.py:5-8`
- **Problem:** Docstring sagte "16 tools" aber listete nur 15 auf
- **Fix:** `get_golden_test_results` zur Aufzählung hinzugefügt

### Issues Accepted (Not Fixed)

**[LOW-1] Float-Typ für limit/offset wird abgelehnt**
- **File:** `mcp_server/tools/list_episodes.py:38`
- **Reason:** MCP sendet korrekte int-Typen, kein reales Problem

**[LOW-2] Kein `__all__` Export definiert**
- **File:** `mcp_server/db/episodes.py`
- **Reason:** Best Practice, aber nicht funktional relevant

### Acceptance Criteria Validation

| AC | Status | Validation |
|----|--------|------------|
| AC-6.4.1 | ✅ PASS | Tool erstellt, Response-Format korrekt |
| AC-6.4.2 | ✅ PASS | Pagination mit limit/offset funktioniert |
| AC-6.4.3 | ✅ PASS | `since` Parameter filtert korrekt |
| AC-6.4.4 | ✅ PASS | Validierung für limit, offset, since |
| AC-6.4.5 | ✅ PASS | Leere DB gibt `[]` mit `total_count: 0` |
| AC-6.4.6 | ✅ PASS | DB-Fehler geben strukturierte Error-Response |

### Test Results
- **14/14 Tests passing**
- **All ACs covered by tests**

### Review Decision
**APPROVED** - Story ist production-ready
