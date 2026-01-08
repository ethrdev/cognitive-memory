# Story 7.6: Hyperedge via Properties (Konvention)

Status: done

## Story

Als I/O,
möchte ich multi-vertex Kontexte in Edges abbilden,
sodass Erfahrungen mit mehreren Beteiligten dargestellt werden können.

## Motivation

Eine Erfahrung wie die Dennett-Session ist nicht nur `I/O --EXPERIENCED--> Dennett-Entscheidung`. Sie ist ein Kontext aus I/O, ethr, dem Moment, der emotionalen Valenz. Das Properties-basierte Hyperedge-Muster ermöglicht die Darstellung solcher multi-vertex Kontexte ohne Schema-Änderung.

**Philosophischer Hintergrund (v3-exploration):**
- Erfahrungen sind relational, nicht binär
- Identitäts-definierende Momente haben mehrere Beteiligte
- Das System sollte komplexe Kontexte abbilden können

## Acceptance Criteria

1. **Given** eine Erfahrung mit mehreren Beteiligten
   **When** eine Edge erstellt wird
   **Then** kann `properties.participants` eine Liste von Node-Namen enthalten:
   ```json
   {
     "participants": ["I/O", "ethr", "2025-12-15"],
     "context_type": "shared_experience",
     "emotional_valence": "positive"
   }
   ```

2. **And** bestehende binäre `graph_add_edge` bleibt unverändert
   - Keine neuen Required-Parameter
   - Properties-Erweiterung ist optional

3. **And** Hyperedges sind in `query_neighbors` über `properties_filter` Parameter filterbar
   - Filtern nach `participants` Array-Inhalt (einzelnes Element)
   - Filtern nach `participants_contains_all` (alle Elemente)
   - Filtern nach `context_type`, `emotional_valence` etc.

4. **Given** eine Edge mit `properties.participants` Array
   **When** `query_neighbors()` aufgerufen wird
   **Then** enthält das Ergebnis alle Properties-Felder (inkl. participants)

5. **And** Konvention ist dokumentiert in README/Docs
   - Properties-Schema für Hyperedges
   - Beispiele für verschiedene Kontext-Typen
   - Best Practices für participants-Nutzung

## Task-zu-AC Mapping

| Task | AC Coverage | Priorität | Beschreibung |
|------|-------------|-----------|--------------|
| Task 1 | AC #3 | 🔴 HOCH | `properties_filter` Parameter Implementation |
| Task 2 | AC #3 | 🔴 HOCH | MCP Tool InputSchema erweitern |
| Task 3 | AC #5 | 🟡 MITTEL | Dokumentation erstellen |
| Task 4 | Test | 🟡 MITTEL | Test Suite für Properties-basierte Queries |

**Hinweis:** AC #2 und #4 sind bereits durch Story 7.5 erfüllt:
- `graph_add_edge` akzeptiert bereits Properties (AC #2)
- `edge_properties` ist bereits in `query_neighbors()` Ergebnissen (AC #4)

## Tasks / Subtasks

- [x] Task 1: `properties_filter` Parameter zu `query_neighbors()` (AC: #3) - **KERN-FEATURE**
  - [x] Subtask 1.1: Parameter `properties_filter: dict[str, Any] | None = None` hinzufügen zu `graph.py:711`
  - [x] Subtask 1.2: Input-Validierung für properties_filter implementieren
  - [x] Subtask 1.3: SQL-basierte JSONB-Filterung mit PostgreSQL Operators
  - [x] Subtask 1.4: `participants` Single-Element Filter (`properties->'participants' ? %s`)
  - [x] Subtask 1.5: `participants_contains_all` Array-Containment (`properties->'participants' @> %s::jsonb`)
  - [x] Subtask 1.6: Standard JSONB-Containment für andere Properties (`properties @> %s::jsonb`)

- [x] Task 2: MCP Tool InputSchema erweitern (AC: #3)
  - [x] Subtask 2.1: `properties_filter` Property zu `graph_query_neighbors.py` inputSchema
  - [x] Subtask 2.2: Handler-Funktion Parameter-Extraktion erweitern
  - [x] Subtask 2.3: Input-Validierung (Dict-Struktur prüfen)

- [x] Task 3: Dokumentation (AC: #5)
  - [x] Subtask 3.1: `docs/reference/api-reference.md` aktualisiert
  - [x] Subtask 3.2: Inline-Code-Dokumentation in graph.py
  - [x] Subtask 3.3: Beispiele für I/O-spezifische Hyperedges dokumentieren

- [x] Task 4: Test Suite
  - [x] Subtask 4.1: Tests für Hyperedge-Erstellung mit participants
  - [x] Subtask 4.2: Tests für `participants` Single-Element Filter
  - [x] Subtask 4.3: Tests für `participants_contains_all` Array-Filter
  - [x] Subtask 4.4: Tests für kombinierte Property-Filter
  - [x] Subtask 4.5: Tests für ungültige Filter-Inputs (Error-Handling)

## Dev Notes

### Architecture Compliance

**Datei-Modifikationen:**
- `mcp_server/db/graph.py:711` - `properties_filter` Parameter zu `query_neighbors()` hinzufügen
- `mcp_server/tools/graph_query_neighbors.py` - `properties_filter` im inputSchema und Handler

**Neue Dateien:**
- `docs/hyperedge-convention.md` - Konventions-Dokumentation
- `tests/test_hyperedge_properties.py` - Test Suite

**Keine Modifikationen an:**
- `mcp_server/tools/graph_add_edge.py` - bereits Properties-fähig via `properties` Parameter
- `mcp_server/db/migrations/*` - kein Schema-Change erforderlich

**Verifiziert:** GIN-Index auf `edges.properties` existiert bereits (`012_add_graph_tables.sql:68`):
```sql
CREATE INDEX idx_edges_properties ON edges USING gin(properties);
```

---

### `properties_filter` Implementation (Task 1)

**Signatur-Änderung in `graph.py:711`:**

```python
def query_neighbors(
    node_id: str,
    relation_type: str | None = None,
    max_depth: int = 1,
    direction: str = "both",
    include_superseded: bool = False,
    properties_filter: dict[str, Any] | None = None  # NEU
) -> list[dict[str, Any]]:
```

**SQL-basierte JSONB-Filterung (nach WHERE-Klausel hinzufügen):**

```python
# In der CTE vor ORDER BY einfügen
def _build_properties_filter_sql(
    properties_filter: dict[str, Any]
) -> tuple[list[str], list[Any]]:
    """
    Baut SQL WHERE-Klauseln für JSONB properties filtering.

    Unterstützte Filter-Keys:
    - "participants": str → Array-Element Query (? Operator)
    - "participants_contains_all": list[str] → Array-Containment (@> Operator)
    - Andere Keys: Standard JSONB-Containment (@> Operator)

    Returns:
        Tuple von (where_clauses: list[str], params: list[Any])

    Raises:
        ValueError: Bei ungültigem Filter-Format
    """
    where_clauses: list[str] = []
    params: list[Any] = []

    for key, value in properties_filter.items():
        if key == "participants" and isinstance(value, str):
            # Single participant check: properties->'participants' ? 'ethr'
            where_clauses.append("e.properties->'participants' ? %s")
            params.append(value)

        elif key == "participants_contains_all" and isinstance(value, list):
            # All participants must be present: @> '["I/O", "ethr"]'::jsonb
            where_clauses.append("e.properties->'participants' @> %s::jsonb")
            params.append(json.dumps(value))

        elif isinstance(value, (str, int, float, bool)):
            # Standard property match: properties @> '{"key": "value"}'::jsonb
            filter_obj = {key: value}
            where_clauses.append("e.properties @> %s::jsonb")
            params.append(json.dumps(filter_obj))

        elif isinstance(value, dict):
            # Nested object match
            filter_obj = {key: value}
            where_clauses.append("e.properties @> %s::jsonb")
            params.append(json.dumps(filter_obj))

        else:
            raise ValueError(
                f"Invalid properties_filter value for key '{key}': "
                f"expected str, int, float, bool, list (for participants_contains_all), or dict"
            )

    return where_clauses, params
```

**Integration in query_neighbors() CTE:**

```python
# Nach bestehenden WHERE-Klauseln (relation_type Filter):
# AND (%s IS NULL OR e.relation = %s)

# NEU: Properties-Filter hinzufügen
properties_where = ""
properties_params = []
if properties_filter:
    try:
        filter_clauses, filter_params = _build_properties_filter_sql(properties_filter)
        if filter_clauses:
            properties_where = " AND " + " AND ".join(filter_clauses)
            properties_params = filter_params
    except ValueError as e:
        raise ValueError(f"Invalid properties_filter: {e}")
```

---

### MCP Tool InputSchema (Task 2)

```python
# mcp_server/tools/graph_query_neighbors.py

# Im inputSchema dict erweitern:
"properties_filter": {
    "type": "object",
    "description": (
        "JSONB filter for edge properties. Supported filters:\n"
        "- 'participants': string - Filter edges where participants array contains this value\n"
        "- 'participants_contains_all': array - Filter edges where participants contains ALL values\n"
        "- 'context_type': string - Filter by context_type property\n"
        "- 'emotional_valence': string - Filter by emotional_valence property\n"
        "- Any other key: Standard JSONB containment filter"
    ),
    "additionalProperties": True,
    "examples": [
        {"participants": "ethr"},
        {"participants_contains_all": ["I/O", "ethr"]},
        {"context_type": "shared_experience"},
        {"context_type": "shared_experience", "emotional_valence": "positive"}
    ]
}

# Im Handler:
properties_filter = arguments.get("properties_filter")

# Input-Validierung
if properties_filter is not None:
    if not isinstance(properties_filter, dict):
        return {
            "error": "Parameter validation failed",
            "details": "Invalid 'properties_filter' parameter (must be object/dict)",
            "tool": "graph_query_neighbors",
        }

# An query_neighbors() weitergeben
result = query_neighbors(
    node_id=start_node["id"],
    relation_type=relation_type,
    max_depth=depth,
    direction=direction,
    include_superseded=include_superseded,
    properties_filter=properties_filter  # NEU
)
```

---

### Hyperedge Properties Schema (Konvention)

```python
# Empfohlene Properties für Hyperedges
HYPEREDGE_PROPERTIES_SCHEMA = {
    # Multi-vertex Kontext (KERN-FEATURE dieser Story)
    "participants": list[str],  # Node-Namen die an der Erfahrung beteiligt sind

    # Kontext-Klassifikation
    "context_type": str,  # "shared_experience" | "decision" | "reflection" | "conflict"

    # Emotionale Dimension (für I/O's Selbst-Narrative)
    "emotional_valence": str,  # "positive" | "negative" | "neutral" | "mixed"

    # Temporaler Kontext
    "temporal_marker": str,  # ISO-8601 oder beschreibender Text ("Frühjahr 2025")

    # Optional: Link zu Ursprungs-Erfahrung
    "source_experience": str,  # Node-Name oder Edge-ID
}
```

---

### Query-Beispiele

**1. Alle Edges mit ethr als Participant:**
```python
query_neighbors(
    node_id="io-uuid",
    properties_filter={"participants": "ethr"}
)
# SQL: ... AND e.properties->'participants' ? 'ethr'
```

**2. Alle shared_experience Edges:**
```python
query_neighbors(
    node_id="io-uuid",
    properties_filter={"context_type": "shared_experience"}
)
# SQL: ... AND e.properties @> '{"context_type": "shared_experience"}'::jsonb
```

**3. Positive konstitutive Erfahrungen:**
```python
query_neighbors(
    node_id="io-uuid",
    properties_filter={
        "emotional_valence": "positive",
        "edge_type": "constitutive"
    }
)
# SQL: ... AND e.properties @> '{"emotional_valence": "positive", "edge_type": "constitutive"}'::jsonb
```

**4. Edges mit I/O UND ethr als Participants:**
```python
query_neighbors(
    node_id="decision-node-uuid",
    properties_filter={"participants_contains_all": ["I/O", "ethr"]}
)
# SQL: ... AND e.properties->'participants' @> '["I/O", "ethr"]'::jsonb
```

---

### PostgreSQL JSONB-Operatoren Referenz

| Operator | Beschreibung | Beispiel |
|----------|--------------|----------|
| `@>` | Containment (linkes enthält rechtes) | `properties @> '{"key": "value"}'` |
| `?` | Hat Key/Element | `properties->'array' ? 'element'` |
| `?&` | Hat alle Keys | `properties ?& array['k1', 'k2']` |
| `?\|` | Hat irgendeinen Key | `properties ?\| array['k1', 'k2']` |
| `->` | Get JSON object | `properties->'participants'` |
| `->>` | Get JSON as text | `properties->>'context_type'` |

**GIN-Index Performance:** Der existierende Index `idx_edges_properties` unterstützt alle `@>` und `?` Queries effizient.

---

### Konsistenz mit Story 7.5 (Resolution-Hyperedges)

Story 7.5 verwendet bereits Properties-basierte Hyperedges für Resolutions:
- `supersedes`: `list[str]` - Edge-IDs die superseded werden
- `superseded_by`: `list[str]` - Edge-IDs die superseden
- `affected_edges`: `list[str]` - Bei CONTRADICTION/NUANCE

**Konvention-Alignment:**
- `participants` für Multi-Vertex Kontexte (Story 7.6)
- `supersedes`/`affected_edges` für Resolution-Kontexte (Story 7.5)
- Beide nutzen das gleiche JSONB Array-Pattern

---

## Previous Story Intelligence (Story 7.5)

**Direkt wiederverwendbar:**
- `query_neighbors()` Struktur mit `include_superseded` Parameter
- `edge_properties` in Ergebnissen bereits vorhanden
- MCP Tool InputSchema Erweiterungs-Pattern
- `_filter_superseded_edges()` Python-Filter als Referenz

**Relevante Code-Stellen:**
- `graph.py:711-940` - `query_neighbors()` Implementation
- `graph_query_neighbors.py:1-165` - MCP Tool Handler
- `dissonance.py:654-672` - Properties-basierte Hyperedge Erstellung

---

## Technical Dependencies

**Upstream (vorausgesetzt):**
- ✅ Epic 4: GraphRAG (`graph_add_edge`, `query_neighbors`, JSONB properties)
- ✅ Story 7.5: Resolution-Hyperedge (zeigt Properties-Nutzung für komplexe Edges)
- ✅ Migration 012: GIN-Index auf `edges.properties` vorhanden

**Downstream (blockiert von dieser Story):**
- Story 7.7: IEF (nutzt `properties_filter` für konstitutive Edge-Priorisierung)
- Story 7.9: SMF (erstellt Vorschläge basierend auf Properties-Analyse)

---

## Estimated Effort

**Gesamt:** 1 Tag (~6-8h)

**Breakdown:**
- Task 1: 3h (SQL-Filter Logic, Input-Validation, CTE-Integration)
- Task 2: 1h (MCP Tool Schema + Handler)
- Task 3: 1h (Dokumentation)
- Task 4: 2h (Tests)

---

## References

- [Source: bmad-docs/epics/epic-7-v3-constitutive-knowledge-graph.md#Story 7.6]
- [Source: mcp_server/db/graph.py - Graph Database Operations]
- [Source: mcp_server/tools/graph_add_edge.py - Edge Creation mit Properties]
- [Source: mcp_server/tools/graph_query_neighbors.py - Query Tool]
- [Source: mcp_server/db/migrations/012_add_graph_tables.sql - GIN-Index Verification]
- [Source: bmad-docs/stories/7-5-dissonance-engine-resolution.md - Resolution-Hyperedge Pattern]
- [Wissenschaft: HyperGraphRAG (2024) - Properties-basierte Hyperedges]
- [PostgreSQL Docs: JSONB Operators and Indexing]

---

## Dev Agent Record

### Context Reference

Story 7.6 basiert auf Epic 7 (v3 Constitutive Knowledge Graph), Phase 3 "IEF & Hyperedge".
Dies erweitert `query_neighbors()` um JSONB-basierte Properties-Filterung für Hyperedge-Queries.

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

**Story completed:** 2025-12-17

**Implementation Summary:**
1. **Task 1: `properties_filter` Parameter** - DONE
   - Added `_build_properties_filter_sql()` helper function in `graph.py:26-94`
   - Extended `query_neighbors()` signature with `properties_filter: dict[str, Any] | None = None`
   - Implemented SQL-based JSONB filtering with PostgreSQL operators
   - All filter types working: `participants`, `participants_contains_all`, standard containment

2. **Task 2: MCP Tool InputSchema** - DONE
   - Extended `graph_query_neighbors.py` handler with `properties_filter` extraction
   - Added input validation for dict type
   - Updated `__init__.py` Tool definition with properties_filter schema
   - Response includes `properties_filter` in `query_params`

3. **Task 3: Dokumentation** - DONE
   - Updated `docs/reference/api-reference.md` with full properties_filter documentation
   - Added inline documentation in `graph.py` and `graph_query_neighbors.py`
   - Documented examples for I/O-specific hyperedge queries

4. **Task 4: Test Suite** - DONE
   - Created `tests/test_hyperedge_properties.py` with 20 tests
   - All acceptance criteria covered
   - Updated existing `test_graph_query_neighbors.py` tests for new parameter signature

**Tests:** 47 tests passing (20 new + 27 existing updated)

**AC Coverage:**
- ✅ AC #1: Properties with participants array - via existing `graph_add_edge` (unchanged)
- ✅ AC #2: Binary graph_add_edge unchanged - no modifications needed
- ✅ AC #3: `properties_filter` parameter fully implemented
- ✅ AC #4: Results include all properties fields - via existing `edge_properties` (Story 7.5)
- ✅ AC #5: Documentation updated

### File List

**Modified:**
- `mcp_server/db/graph.py` - Added `_build_properties_filter_sql()`, extended `query_neighbors()`
- `mcp_server/tools/graph_query_neighbors.py` - Added `properties_filter` handling
- `mcp_server/tools/__init__.py` - Extended Tool inputSchema
- `tests/test_graph_query_neighbors.py` - Updated mock assertions for new parameters
- `docs/reference/api-reference.md` - Added `properties_filter` documentation
- `bmad-docs/stories/7-6-hyperedge-via-properties.md` - Status → done
- `bmad-docs/sprint-status.yaml` - Story status updated

**Created:**
- `tests/test_hyperedge_properties.py` - 21 tests for hyperedge properties filtering

---

## Validation Report (2025-12-17)

**Reviewer:** Claude Code (Adversarial Review Mode)
**Status:** ✅ All issues fixed, story improved

### Issues Fixed

| ID | Severity | Issue | Fix Applied |
|----|----------|-------|-------------|
| KRITISCH-1 | 🔴 | `properties_filter` Implementation fehlte | Added complete SQL-based implementation |
| KRITISCH-2 | 🔴 | SQL vs Python unclear | Clarified: SQL-basiert (nutzt GIN-Index) |
| KRITISCH-3 | 🔴 | MCP Tool InputSchema fehlte | Added complete inputSchema spec |
| KRITISCH-4 | 🔴 | Task 3 redundant | Removed, replaced with Documentation task |
| KRITISCH-5 | 🔴 | GIN-Index unverified | Verified: `idx_edges_properties` exists (012_add_graph_tables.sql:68) |
| ENHANCEMENT-1 | 🟡 | `participants_contains_any` fehlte | Future Enhancement noted (use `?\|` operator) |
| ENHANCEMENT-2 | 🟡 | Input-Validierung fehlte | Added ValueError handling in `_build_properties_filter_sql` |
| ENHANCEMENT-3 | 🟡 | Story 7.5 Integration unklar | Added "Konsistenz mit Story 7.5" section |
| ENHANCEMENT-4 | 🟡 | Error-Handling fehlte | Added in MCP Tool Handler |
| OPT-1 | 🟢 | Redundante Tasks | Consolidated to 4 essential tasks |
| OPT-2 | 🟢 | Verbosity | Reduced Dev Notes by ~40% |
| OPT-3 | 🟢 | Effort zu optimistisch | Updated to 1 Tag (~6-8h) |
| LLM-OPT-1 | 🟢 | Dev Notes zu lang | Consolidated, removed duplicates |
| LLM-OPT-2 | 🟢 | Task-Priorisierung fehlt | Added priority column in Task-zu-AC Mapping |

---

## Code Review (2025-12-17)

**Reviewer:** Claude Code (Adversarial Review Mode)
**Status:** ✅ APPROVED - All issues fixed

### Review Summary

| Severity | Found | Fixed |
|----------|-------|-------|
| Critical | 0 | - |
| High | 0 | - |
| Medium | 3 | 3 ✅ |
| Low | 2 | 1 ✅ (1 was false positive) |

### Issues Fixed

| ID | Severity | Issue | Fix |
|----|----------|-------|-----|
| MEDIUM-1 | 🟡 | File List missing `sprint-status.yaml` | Added to File List |
| MEDIUM-2 | 🟡 | Missing ValueError propagation test | Added `test_invalid_filter_value_propagates_as_database_error()` |
| MEDIUM-3 | 🟡 | Test documentation incomplete | Added Default Parameter Values section to module docstring |
| LOW-1 | 🟢 | json import verification | Verified: `import json` at line 14 ✅ |

### Test Results

```
48 tests passed (21 hyperedge + 27 query_neighbors)
- tests/test_hyperedge_properties.py: 21 passed ✅
- tests/test_graph_query_neighbors.py: 27 passed ✅
```

### Verification

- ✅ All ACs implemented and verified
- ✅ All Tasks completed
- ✅ Git changes match File List
- ✅ Tests passing
- ✅ Code compiles without errors
