# Story 6.3: count_by_type MCP Tool

Status: done

## Story

Als autonomer Agent oder Entwickler,
möchte ich eine Übersicht aller Eintragstypen mit Counts,
sodass ich schnelle Integritätsprüfungen durchführen kann.

## Acceptance Criteria

### AC-6.3.1: count_by_type Tool erstellen

**Given** die Datenbank enthält verschiedene Memory-Typen
**When** ich das MCP Tool `count_by_type` aufrufe
**Then** erhalte ich alle Counts als strukturierte Response:

```json
{
    "graph_nodes": 47,
    "graph_edges": 89,
    "l2_insights": 234,
    "episodes": 86,
    "working_memory": 5,
    "raw_dialogues": 1203,
    "status": "success"
}
```

**Note:** `status` ist immer das letzte Feld (Pattern aus Story 6.1/6.2). Alle Count-Werte sind `int`.

### AC-6.3.2: Zero Counts bei leerer Datenbank

**Given** die Datenbank hat keine Einträge (oder nur leere Tabellen)
**When** ich `count_by_type` aufrufe
**Then** erhalte ich alle Counts als 0:

```json
{
    "graph_nodes": 0,
    "graph_edges": 0,
    "l2_insights": 0,
    "episodes": 0,
    "working_memory": 0,
    "raw_dialogues": 0,
    "status": "success"
}
```

**And** keine Errors bei leeren Tabellen (graceful handling)

### AC-6.3.3: Keine Parameter erforderlich

**Given** count_by_type ist ein parameterloser Audit-Endpoint
**When** ich das Tool ohne Parameter aufrufe
**Then** funktioniert es korrekt:

- Keine required Parameter
- inputSchema: `{"type": "object", "properties": {}, "required": []}`
- Keine Parameter-Validierung erforderlich (Tool ist parameterlos)

### AC-6.3.4: Error Handling

**Given** ein Database-Fehler tritt auf
**When** die Abfrage fehlschlägt
**Then** wird eine strukturierte Error-Response zurückgegeben:

```json
{
    "error": "Database operation failed",
    "details": "Connection timeout",
    "tool": "count_by_type"
}
```

## Tasks / Subtasks

### Task 1: DB-Funktion erstellen (AC: 6.3.1, 6.3.2)

- [x] Subtask 1.1: Erstelle `mcp_server/db/stats.py`
  - Neue Datei für Statistik-Funktionen
  - Module-Docstring:
    ```python
    """
    Stats Database Operations Module

    Provides database functions for counting all memory types.

    Story 6.3: count_by_type MCP Tool
    """
    ```
  - Importiere `get_connection` aus `mcp_server/db/connection.py`
  - Folge Logger-Pattern: `logger = logging.getLogger(__name__)` auf Modul-Ebene

- [x] Subtask 1.2: Implementiere `get_all_counts()` Funktion
  - SQL mit UNION ALL (siehe SQL Query Pattern unten)
  - Return: Dict mit allen 6 Counts (int-Werte, 0 bei leeren Tabellen)

### Task 2: MCP Tool Implementation (AC: 6.3.1, 6.3.3)

- [x] Subtask 2.1: Erstelle `mcp_server/tools/count_by_type.py`
  - async Handler `handle_count_by_type(arguments)`
  - Nutzt `get_all_counts` aus `mcp_server.db.stats`
  - Keine Parameter-Validierung (Tool ist parameterlos)
  - Folge Tool-Pattern aus `get_node_by_name.py`

- [x] Subtask 2.2: Implementiere Success Response
  - Alle 6 Count-Felder (int-Werte) + `status: "success"` am Ende
  - Keine Exception bei leeren Counts

### Task 3: Tool Registration (AC: 6.3.3)

- [x] Subtask 3.1: Registriere Tool in `mcp_server/tools/__init__.py`
  - Import bei Line ~30: `from mcp_server.tools.count_by_type import handle_count_by_type`
  - Tool Definition nach Line 2226 (nach `get_edge`):
    ```python
    Tool(
        name="count_by_type",
        description="Get counts of all memory types for audit and integrity checks. Returns counts for graph_nodes, graph_edges, l2_insights, episodes, working_memory, and raw_dialogues.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    ```
  - Handler Mapping bei Line ~2244: `"count_by_type": handle_count_by_type,`

- [x] Subtask 3.2: Docstring aktualisieren (Tool-Count: 14 → 15)
  - Suche nach "14 MCP Tools" und ersetze durch "15 MCP Tools"

### Task 4: Error Handling (AC: 6.3.4)

- [x] Subtask 4.1: Database Error Handling
  - Try/catch für DB-Fehler
  - Strukturierte Error Response mit `tool: "count_by_type"`

### Task 5: Testing (AC: 6.3.1, 6.3.2, 6.3.3, 6.3.4)

- [x] Subtask 5.1: Unit Tests erstellen (`tests/test_count_by_type.py`)
  - Test: Alle Counts werden zurückgegeben (Grundfunktionalität)
  - Test: Zero Counts bei leeren Tabellen
  - Test: Parameterloser Aufruf funktioniert (leeres `arguments` dict)
  - Test: Database Error Handling
  - Test: Response enthält alle 6 erwarteten Felder + status
  - Test: Alle Count-Werte sind vom Typ `int`
  - Test: Response-Struktur Validierung (status am Ende)

- [x] Subtask 5.2: Integration Test mit echter DB
  - Test mit echtem PostgreSQL (`@pytest.mark.integration`)
  - Prüfe initiale Counts, füge Test-Daten ein, prüfe erhöhte Counts
  - Cleanup im `finally`-Block

## Dev Notes

### Story Context

Story 6.3 ist Teil von **Epic 6 (Audit und Verification Endpoints)**, die Write-then-Verify Patterns und Audit-Funktionen für autonome Agenten ermöglichen.

**Strategische Bedeutung:**
- **Audit Foundation:** Erste Count-Funktion für Datenbestands-Übersicht
- **Sanity Check:** Schnelle Integritätsprüfung ("Wie viele Einträge gibt es?")
- **Parameterlos:** Einfachster Endpoint - keine Input-Validierung nötig

**Relation zu anderen Stories:**
- **Story 6.1 + 6.2 (Reference):** Graceful Error-Handling Pattern folgen
- **Story 6.6 (Nachfolger):** count_by_type wird in Integration Tests verwendet

### Critical Patterns from Stories 6.1 & 6.2

**MUST FOLLOW:**

1. **Logger Pattern:** Logger INNERHALB der async Funktion definieren
   ```python
   async def handle_count_by_type(arguments: dict[str, Any]) -> dict[str, Any]:
       logger = logging.getLogger(__name__)
   ```

2. **Error Response Structure:** Immer mit `tool` Feld
   ```python
   return {
       "error": "Database operation failed",
       "details": str(db_error),
       "tool": "count_by_type",
   }
   ```

3. **Integration Test Marker:** `@pytest.mark.integration` mit Cleanup im finally-Block

4. **Parameterlose Tools:** Keine Validierung erforderlich, aber `arguments` Parameter muss akzeptiert werden (auch wenn leer)

### SQL Query Pattern

Effiziente Single-Query mit UNION ALL:

```sql
SELECT 'graph_nodes' AS type, COUNT(*) AS count FROM nodes
UNION ALL
SELECT 'graph_edges' AS type, COUNT(*) AS count FROM edges
UNION ALL
SELECT 'l2_insights' AS type, COUNT(*) AS count FROM l2_insights
UNION ALL
SELECT 'episodes' AS type, COUNT(*) AS count FROM episode_memory
UNION ALL
SELECT 'working_memory' AS type, COUNT(*) AS count FROM working_memory
UNION ALL
SELECT 'raw_dialogues' AS type, COUNT(*) AS count FROM l0_raw;
```

**Warum UNION ALL statt UNION:**
- Effizienter: Keine Duplikat-Prüfung nötig (jede Tabelle hat eindeutigen type-Namen)
- Einzelne Query (minimale DB-Roundtrips)
- Alle Counts in einer Transaktion (konsistent)
- Funktioniert auch bei leeren Tabellen (COUNT(*) = 0)

### Table Name Mapping

| Response Field | Database Table | Notes |
|----------------|----------------|-------|
| `graph_nodes` | `nodes` | From Epic 4 GraphRAG |
| `graph_edges` | `edges` | From Epic 4 GraphRAG |
| `l2_insights` | `l2_insights` | Semantic insights with embeddings |
| `episodes` | `episode_memory` | Verbal RL reflexions |
| `working_memory` | `working_memory` | LRU session context |
| `raw_dialogues` | `l0_raw` | Original dialogue transcripts |

### File Locations (Exact Line References)

| Component | Location | Line Reference |
|-----------|----------|----------------|
| DB Connection | `mcp_server/db/connection.py` | `get_connection()` |
| Tool Pattern | `mcp_server/tools/get_node_by_name.py` | Full file reference |
| Tool Import | `mcp_server/tools/__init__.py` | ~Line 30 (with other imports) |
| Tool Definition | `mcp_server/tools/__init__.py` | After Line 2226 (after `get_edge`) |
| Handler Mapping | `mcp_server/tools/__init__.py` | ~Line 2244 (in `tool_handlers` dict) |
| Test Pattern | `tests/test_get_node_by_name.py` | Full file reference |

### Project Structure Notes

**NEW Files:**
- `mcp_server/db/stats.py` - Stats/audit DB functions
- `mcp_server/tools/count_by_type.py` - MCP Tool implementation
- `tests/test_count_by_type.py` - Test suite (7+ unit tests + 1 integration test)

**MODIFIED Files:**
- `mcp_server/tools/__init__.py` - Import, Tool definition, Handler mapping

### References

- [Source: bmad-docs/epics/epic-6-audit-verification-endpoints.md#Story-6.3] - User Story und ACs
- [Source: mcp_server/tools/get_node_by_name.py] - MCP Tool pattern
- [Source: mcp_server/db/graph.py] - DB function patterns

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-06 | Story created - ready for development | Claude Code (create-story workflow) |
| 2025-12-06 | Quality review - enhanced with exact line refs, inputSchema fix, test coverage | Bob (SM validate-create-story) |
| 2025-12-06 | Implementation complete - all ACs satisfied, 10 tests passing | Claude Opus 4.5 (dev-story workflow) |
| 2025-12-06 | Code review completed - 1 fix applied, story approved | Claude Opus 4.5 (code-review workflow) |

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

**Story 6.3 Implementation Completed Successfully**

- ✅ **AC-6.3.1 count_by_type Tool erstellen:** MCP tool returns all 6 count fields with `status: "success"`
- ✅ **AC-6.3.2 Zero Counts bei leerer Datenbank:** Empty tables return 0 counts gracefully
- ✅ **AC-6.3.3 Keine Parameter erforderlich:** Parameterless tool with `inputSchema: {"type": "object", "properties": {}, "required": []}`
- ✅ **AC-6.3.4 Error Handling:** Database errors return structured error response with `tool: "count_by_type"`
- ✅ **Red-Green-Refactor:** Tests written first (10 tests), then implementation
- ✅ **All 10 tests pass** (7 unit tests + 2 DB function tests + 1 integration test)
- ✅ **No regressions:** Story 6.1 (11 tests) and 6.2 (22 tests) still pass
- ✅ **Tool Count:** Updated from 14 to 15 tools in module docstring

### File List

**NEW Files:**
- `mcp_server/db/stats.py` - Stats/audit DB functions (67 lines)
- `mcp_server/tools/count_by_type.py` - MCP Tool implementation (60 lines)
- `tests/test_count_by_type.py` - Test suite with 10 tests (180 lines)

**MODIFIED Files:**
- `mcp_server/tools/__init__.py` - Import (line 41), Tool definition (lines 2228-2236), Handler mapping (line 2255)
- `bmad-docs/sprint-status.yaml` - Story status: in-progress → review

---

## Code Review Record

### Review Date: 2025-12-06

### Reviewer: Claude Opus 4.5 (code-review workflow)

### Review Summary

**Git vs Story Discrepancies:** 0 (alle Dateien korrekt dokumentiert)

### Issues Found & Resolution

| Severity | Issue | Resolution |
|----------|-------|------------|
| ~~HIGH~~ | Logger-Pattern Inkonsistenz in stats.py | **DISMISSED** - Mandate gilt für async Funktionen, stats.py ist sync |
| MEDIUM | Redundante doppelte try/except in count_by_type.py:32-64 | **FIXED** - Äußeres try entfernt (war toter Code) |
| MEDIUM | Test-Isolation für Integration Test | **NOTED** - Nice-to-have, kein kritisches Problem |
| MEDIUM | Keine Prüfung auf unerwartete Parameter | **DISMISSED** - Parameterlose Tools ignorieren Extra-Params (akzeptiertes Pattern) |
| LOW | Änderungen nicht committed | **NOTED** - Reminder für User |

### Fixes Applied

1. **count_by_type.py** - Redundantes äußeres try/except entfernt (Zeilen 58-64 waren toter Code, da inneres except alle Exceptions fing)

### AC Verification

| AC | Status | Verification |
|---|---|---|
| AC-6.3.1 | ✅ PASS | Tool gibt alle 6 Counts + status:success zurück |
| AC-6.3.2 | ✅ PASS | Leere Tabellen → 0 Counts (Test verifiziert) |
| AC-6.3.3 | ✅ PASS | inputSchema korrekt parameterlos |
| AC-6.3.4 | ✅ PASS | DB-Fehler → strukturierte Error Response |

### Test Results After Fix

```
tests/test_count_by_type.py ..........  [100%]
10 passed in 2.35s
```

### Review Decision: **APPROVED** ✅

Story ist produktionsreif. Alle ACs implementiert, Code-Qualität verbessert.
