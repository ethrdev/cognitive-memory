# Story 6.1: get_node_by_name MCP Tool

Status: done

## Story

Als autonomer Agent (I/O),
möchte ich einen Graph-Node direkt per Name abfragen,
sodass ich Write-Operationen verifizieren kann ohne Graph-Traversal.

## Acceptance Criteria

### AC-6.1.1: get_node_by_name Tool erstellen

**Given** `get_node_by_name` existiert als DB-Funktion (`mcp_server/db/graph.py:208`)
**When** ich das MCP Tool `get_node_by_name` mit `name: "I/O"` aufrufe
**Then** wird der Node abgefragt:

- Bei existierendem Node: Return `{node_id, label, name, properties, vector_id, created_at, status: "success"}`
- Bei nicht-existierendem Node: Return `{node: null, status: "not_found"}`

### AC-6.1.2: Graceful Null Return

**Given** get_node_by_name wird mit nicht-existierendem Namen aufgerufen
**When** kein Node gefunden wird
**Then** wird KEINE Exception geworfen:

- Stattdessen: `{node: null, status: "not_found"}`
- Kein Error-Feld in der Response
- Ermöglicht Write-then-Verify Pattern ohne Try/Catch

### AC-6.1.3: Parameter Validierung

**Given** get_node_by_name wird mit ungültigen Parametern aufgerufen
**When** ein Validierungsfehler auftritt
**Then** wird korrekt gehandelt:

- Bei fehlendem/leerem `name`: Error mit klarer Message
- Bei nicht-string `name`: Error mit klarer Message

## Tasks / Subtasks

### Task 1: MCP Tool Implementation (AC: 6.1.1)

- [x] Subtask 1.1: Erstelle `mcp_server/tools/get_node_by_name.py`
  - MCP Tool Handler mit async Funktion
  - Nutzt bestehende `get_node_by_name` DB-Funktion aus `mcp_server/db/graph.py`
  - Folge Tool-Pattern aus `graph_add_node.py`
- [x] Subtask 1.2: Registriere Tool in `mcp_server/tools/__init__.py`
  - Import hinzufügen
  - Tool Definition mit inputSchema
  - Handler Mapping hinzufügen
- [x] Subtask 1.3: Docstring aktualisieren (Tool-Count: 12 → 13)

### Task 2: Response Handling (AC: 6.1.1, 6.1.2)

- [x] Subtask 2.1: Implementiere Success Response
  - `{node_id, label, name, properties, vector_id, created_at, status: "success"}`
- [x] Subtask 2.2: Implementiere Not-Found Response
  - `{node: null, status: "not_found"}`
  - KEIN error-Feld (graceful null)

### Task 3: Validation & Error Handling (AC: 6.1.3)

- [x] Subtask 3.1: Parameter Validierung
  - `name` muss non-empty string sein
  - Klare Error Messages
- [x] Subtask 3.2: Database Error Handling
  - Try/catch für DB-Fehler
  - Strukturierte Error Response

### Task 4: Testing (AC: 6.1.1, 6.1.2, 6.1.3)

- [x] Subtask 4.1: Unit Tests erstellen
  - Test: Existierenden Node finden
  - Test: Graceful null bei nicht-existierendem Node
  - Test: Parameter Validierung (missing, empty, wrong type)
  - Test: Database Error Handling
  - Test: Write-then-Verify Workflow Pattern
- [x] Subtask 4.2: Integration Test mit echter DB
  - Test mit echtem PostgreSQL (nicht nur Mocks)

### Review Follow-ups (AI)

- [x] [AI-Review][MEDIUM] M3: Logger-Pattern konsistent machen [get_node_by_name.py:30]
- [x] [AI-Review][LOW] L1: minLength: 1 zu inputSchema hinzufügen [__init__.py:2193]

## Dev Notes

### Story Context

Story 6.1 ist die **erste Story von Epic 6 (Audit und Verification Endpoints)**. Sie ermöglicht das Write-then-Verify Pattern für autonome Agenten.

**Strategische Bedeutung:**

- **Verification Foundation:** Erste Verification-Endpoint für Graph-Operationen
- **Graceful Null Pattern:** Etabliert Pattern für alle Verification-Tools (6.2-6.5)
- **Minimale Implementation:** Wrapper um bestehende DB-Funktion

**Relation zu anderen Stories:**

- **Story 4.2 (Reference):** Folgt Tool-Pattern von `graph_add_node`
- **Story 6.2-6.5 (Nachfolger):** Nutzen gleiches Graceful-Null Pattern
- **Story 6.6 (Integration):** Integration Tests für Write-then-Verify Workflow

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-06 | Story implemented - MCP Tool, Tests, Registration | Claude Code |
| 2025-12-06 | Code Review fixes - M3 (Logger), L1 (minLength) | Claude Code |

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Completion Notes List

**Story 6.1 Implementation Completed Successfully**
**Completed:** 2025-12-06
**Definition of Done:** All acceptance criteria met, code reviewed, tests passing

**Key Accomplishments:**
- MCP Tool Implementation: `get_node_by_name` tool with graceful null return
- Database Layer: Nutzt bestehende `get_node_by_name` aus `mcp_server/db/graph.py:208-249`
- Parameter Validation: Input validation mit klaren Error Messages
- Error Handling: Strukturierte Error Responses für DB-Fehler
- Code Quality: Logger-Pattern konsistent, inputSchema mit minLength
- Testing: 10 Unit Tests + 1 Integration Test

**Technical Implementation Details:**
- Minimaler Wrapper um bestehende DB-Funktion
- Graceful null return bei nicht-existierendem Node (kein Error)
- Folgt etabliertes Tool-Pattern aus `graph_add_node.py`
- Returns structured response: `{node_id, label, name, properties, vector_id, created_at, status}`

**Validation Completed:**
- Tool registration in MCP server successful
- Parameter validation working (5 test cases)
- Graceful null return verified
- Write-then-Verify pattern tested
- Code review fixes applied (M3, L1)

### File List

**NEW Files Created:**
- `mcp_server/tools/get_node_by_name.py` - MCP Tool implementation (82 lines)
- `tests/test_get_node_by_name.py` - Comprehensive test suite (10 tests)

**MODIFIED Files:**
- `mcp_server/tools/__init__.py` - Tool definition, import, handler registration
- `bmad-docs/sprint-status.yaml` - Story status: done

## Senior Developer Review (AI)

**Reviewer:** BMAD Code Review Workflow
**Date:** 2025-12-06
**Outcome:** APPROVED

### Summary

Story 6.1 has been reviewed and **APPROVED**. All acceptance criteria implemented, code review fixes applied.

### Key Findings

**HIGH SEVERITY:** None found

**MEDIUM SEVERITY:**
- M1: Kein separates Story-File → FIXED (dieses File)
- M2: Keine DB-Integration Tests → FIXED (test hinzugefügt)
- M3: Logger-Pattern inkonsistent → FIXED

**LOW SEVERITY:**
- L1: minLength fehlte → FIXED

### Acceptance Criteria Coverage

| AC# | Description | Status | Evidence |
|-----|-------------|--------|----------|
| AC-6.1.1 | get_node_by_name Tool | IMPLEMENTED | `get_node_by_name.py:18-81` |
| AC-6.1.2 | Graceful Null Return | IMPLEMENTED | `get_node_by_name.py:59-64` |
| AC-6.1.3 | Parameter Validierung | IMPLEMENTED | `get_node_by_name.py:36-42` |

**Summary: 3 of 3 acceptance criteria fully implemented**

### Action Items

**Code Changes Required:** None (all fixes applied)

**Advisory Notes:**
- Story ready for production deployment
- Foundation for Stories 6.2-6.5 established
- Integration Test mit echter DB hinzugefügt
