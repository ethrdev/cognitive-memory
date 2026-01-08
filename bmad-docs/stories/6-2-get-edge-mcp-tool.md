# Story 6.2: get_edge MCP Tool

Status: done

## Story

Als autonomer Agent (I/O),
möchte ich eine spezifische Edge direkt abfragen,
sodass ich `graph_add_edge` Operationen verifizieren kann.

## Acceptance Criteria

### AC-6.2.1: get_edge Tool erstellen

**Given** eine Edge zwischen zwei Nodes existiert
**When** ich das MCP Tool `get_edge` mit `source_name`, `target_name`, `relation` aufrufe
**Then** erhalte ich bei existierender Edge:

```json
{
  "edge_id": "uuid-...",
  "source_id": "uuid-...",
  "target_id": "uuid-...",
  "relation": "USES",
  "weight": 1.0,
  "properties": {...},
  "created_at": "2025-12-06T...",
  "status": "success"
}
```

### AC-6.2.2: Graceful Null Return

**Given** get_edge wird mit nicht-existierender Edge aufgerufen
**When** keine Edge gefunden wird
**Then** wird KEINE Exception geworfen:

- Stattdessen: `{edge: null, status: "not_found"}`
- Kein Error-Feld in der Response
- Ermöglicht Write-then-Verify Pattern ohne Try/Catch

### AC-6.2.3: Lookup by Name

**Given** Source/Target sind Node-Namen (nicht IDs)
**When** get_edge aufgerufen wird
**Then** werden die Namen zu Node-IDs resolved:

- JOINs mit nodes Tabelle für source_name → source_id
- JOINs mit nodes Tabelle für target_name → target_id
- Bei nicht-existierendem Node: `{edge: null, status: "not_found"}`

### AC-6.2.4: Parameter Validierung

**Given** get_edge wird mit ungültigen Parametern aufgerufen
**When** ein Validierungsfehler auftritt
**Then** wird korrekt gehandelt:

- Bei fehlendem/leerem `source_name`: Error mit klarer Message
- Bei fehlendem/leerem `target_name`: Error mit klarer Message
- Bei fehlendem/leerem `relation`: Error mit klarer Message

## Tasks / Subtasks

### Task 1: DB-Funktion erstellen (AC: 6.2.1, 6.2.3)

- [x] Subtask 1.1: Erstelle `get_edge_by_names()` in `mcp_server/db/graph.py`
  - Parameter: source_name, target_name, relation
  - SQL mit JOINs: `edges JOIN nodes ON source_id/target_id`
  - Return: Edge dict oder None
  - Folge Pattern von `get_node_by_name()` (Zeile 208-249)

### Task 2: MCP Tool Implementation (AC: 6.2.1, 6.2.2)

- [x] Subtask 2.1: Erstelle `mcp_server/tools/get_edge.py`
  - async Handler `handle_get_edge(arguments)`
  - Nutzt neue `get_edge_by_names` DB-Funktion
  - Folge Tool-Pattern aus `get_node_by_name.py`
- [x] Subtask 2.2: Implementiere Success Response
  - `{edge_id, source_id, target_id, relation, weight, properties, created_at, status: "success"}`
- [x] Subtask 2.3: Implementiere Not-Found Response
  - `{edge: null, status: "not_found"}`
  - KEIN error-Feld (graceful null - wie Story 6.1)

### Task 3: Tool Registration (AC: 6.2.1)

- [x] Subtask 3.1: Registriere Tool in `mcp_server/tools/__init__.py`
  - Import hinzufügen
  - Tool Definition mit inputSchema (minLength: 1 für alle strings!)
  - Handler Mapping hinzufügen
- [x] Subtask 3.2: Docstring aktualisieren (Tool-Count: 13 → 14)

### Task 4: Validation & Error Handling (AC: 6.2.4)

- [x] Subtask 4.1: Parameter Validierung
  - `source_name` muss non-empty string sein
  - `target_name` muss non-empty string sein
  - `relation` muss non-empty string sein
  - Klare Error Messages
- [x] Subtask 4.2: Database Error Handling
  - Try/catch für DB-Fehler
  - Strukturierte Error Response

### Task 5: Testing (AC: 6.2.1, 6.2.2, 6.2.3, 6.2.4)

- [x] Subtask 5.1: Unit Tests erstellen (`tests/test_get_edge.py`)
  - Test: Existierende Edge finden
  - Test: Graceful null bei nicht-existierender Edge
  - Test: Graceful null bei nicht-existierendem Source-Node
  - Test: Graceful null bei nicht-existierendem Target-Node
  - Test: Parameter Validierung (missing, empty, wrong type)
  - Test: Database Error Handling
  - Test: Write-then-Verify Edge Workflow Pattern
- [x] Subtask 5.2: Integration Test mit echter DB
  - Test mit echtem PostgreSQL (pytest.mark.integration)
  - Cleanup im finally-Block

## Dev Notes

### Learnings from Story 6.1

**Critical Patterns to Follow:**

1. **Graceful Null Pattern:** `{edge: null, status: "not_found"}` - KEIN error-Feld
2. **Logger Pattern:** Logger innerhalb der async Funktion definieren (`logger = logging.getLogger(__name__)`)
3. **inputSchema:** Immer `minLength: 1` für string-Parameter
4. **Integration Test:** Mit `@pytest.mark.integration` markieren, Cleanup im finally-Block

### SQL Query Pattern

```sql
SELECT e.id, e.source_id, e.target_id, e.relation, e.weight, e.properties, e.created_at
FROM edges e
JOIN nodes ns ON e.source_id = ns.id
JOIN nodes nt ON e.target_id = nt.id
WHERE ns.name = %s AND nt.name = %s AND e.relation = %s
LIMIT 1;
```

### Project Structure Notes

**NEW Files:**
- `mcp_server/tools/get_edge.py` - MCP Tool implementation
- `tests/test_get_edge.py` - Test suite

**MODIFIED Files:**
- `mcp_server/db/graph.py` - Add `get_edge_by_names()` function
- `mcp_server/tools/__init__.py` - Tool registration

### File Locations

| Component | Location | Reference |
|-----------|----------|-----------|
| DB Functions | `mcp_server/db/graph.py` | `get_node_by_name()` at line 208-249 |
| Tool Pattern | `mcp_server/tools/get_node_by_name.py` | Story 6.1 implementation |
| Tool Registration | `mcp_server/tools/__init__.py` | `get_node_by_name` at line 2184-2199 |
| Test Pattern | `tests/test_get_node_by_name.py` | Story 6.1 tests |

### Edge Schema Reference

```sql
-- From migration 012_add_graph_tables.sql
CREATE TABLE edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    relation VARCHAR(255) NOT NULL,
    weight DECIMAL(5,4) DEFAULT 1.0,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (source_id, target_id, relation)
);
```

### References

- [Source: bmad-docs/epics/epic-6-audit-verification-endpoints.md#Story-6.2] - User Story und ACs
- [Source: mcp_server/db/graph.py:208-249] - get_node_by_name() DB function pattern
- [Source: mcp_server/tools/get_node_by_name.py] - MCP Tool pattern from Story 6.1
- [Source: bmad-docs/stories/6-1-get-node-by-name-mcp-tool.md] - Learnings and patterns

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-06 | Story created - ready for development | Claude Code (create-story workflow) |
| 2025-12-06 | Story implementation completed - all ACs satisfied | Claude Opus 4.5 (dev-story workflow) |

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

- ✅ **AC-6.2.1 get_edge Tool erstellen:** Implemented `get_edge` MCP tool that returns edge data with `edge_id`, `source_id`, `target_id`, `relation`, `weight`, `properties`, `created_at`, and `status: "success"`
- ✅ **AC-6.2.2 Graceful Null Return:** Returns `{edge: null, status: "not_found"}` without error field when edge doesn't exist
- ✅ **AC-6.2.3 Lookup by Name:** Uses SQL JOINs with nodes table to resolve source_name and target_name to node IDs
- ✅ **AC-6.2.4 Parameter Validierung:** All three parameters (source_name, target_name, relation) are validated for non-empty strings with clear error messages
- ✅ **Red-Green-Refactor:** Tests written first (19 unit tests + 1 integration test), then implementation
- ✅ **All 30 tests pass** (19 get_edge + 11 get_node_by_name for regression check)
- ✅ **Tool Count:** Updated from 13 to 14 tools in module docstring

### File List

**NEW Files:**
- `mcp_server/tools/get_edge.py` - MCP Tool implementation (107 lines)
- `tests/test_get_edge.py` - Test suite with 22 unit tests + 1 integration test (512 lines)

**MODIFIED Files:**
- `mcp_server/db/graph.py` - Added `get_edge_by_names()` function (lines 252-310)
- `mcp_server/tools/__init__.py` - Tool registration: import, Tool definition, handler mapping

---

## Senior Developer Code Review

### Review Date: 2025-12-06
### Reviewer: Claude Opus 4.5 (Adversarial Review Mode)

**Issues Found:** 0 Critical, 1 Medium (fixed), 2 Low (fixed)

### Fixes Applied:

1. **[MED] Unused Import (FIXED)**
   - Removed unused `MagicMock` import from `tests/test_get_edge.py:18`

2. **[MED] Missing Whitespace Validation (FIXED)**
   - Added `.strip()` validation to all three parameters in `get_edge.py:40,48,56`
   - Added 3 new tests for whitespace-only values (`test_parameter_validation_whitespace_*`)
   - Test count increased from 19 → 22

3. **[LOW] Line Count Correction (FIXED)**
   - Updated File List with accurate line counts (107 / 512)

### Review Result: ✅ APPROVED
All ACs verified, all tasks complete, code quality validated.
