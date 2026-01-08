# Epic 6: Audit und Verification Endpoints

**Epic Goal:** Erweitere cognitive-memory um Verification- und Audit-Endpoints, die Write-then-Read Validierung und Datenbestandsprüfung für autonome Agenten ermöglichen.

**Business Value:** Ermöglicht I/O und anderen Agenten die Verifikation von Schreiboperationen ("Wurde mein Write persistiert?") und Datenbestandsprüfung ("Was wurde wann geschrieben?"). Kritisch für das Data Integrity Protocol autonomer Agenten.

**Timeline:** 3-4 Stunden Implementierung + Testing
**Budget:** €0/mo (keine API-Kosten, rein PostgreSQL-basiert)

**Dependencies:**
- Benötigt: Epic 4 (GraphRAG) ✅ bereits abgeschlossen
- Kann parallel zu anderen Epics laufen

**Tech-Spec:** [2025-12-06-audit-verification-endpoints.md](../tech-specs/2025-12-06-audit-verification-endpoints.md)

---

## Story 6.1: get_node_by_name MCP Tool

**Als** autonomer Agent (I/O),
**möchte ich** einen Graph-Node direkt per Name abfragen,
**sodass** ich Write-Operationen verifizieren kann ohne Graph-Traversal.

**Acceptance Criteria:**

**Given** `get_node_by_name` existiert als DB-Funktion (`mcp_server/db/graph.py:208`)
**When** ich das MCP Tool `get_node_by_name` mit `name: "I/O"` aufrufe
**Then** erhalte ich:
- Bei existierendem Node: `{node_id, label, name, properties, vector_id, created_at, status: "success"}`
- Bei nicht-existierendem Node: `{node: null, status: "not_found"}`

**And** Keine Error-Exception bei fehlendem Node (graceful null return)

**Technical Notes:**
- Datei: `mcp_server/tools/get_node_by_name.py`
- Minimaler Wrapper - DB-Funktion existiert bereits
- Geschätzte Zeit: 30min

---

## Story 6.2: get_edge MCP Tool

**Als** autonomer Agent (I/O),
**möchte ich** eine spezifische Edge direkt abfragen,
**sodass** ich `graph_add_edge` Operationen verifizieren kann.

**Acceptance Criteria:**

**Given** eine Edge zwischen zwei Nodes existiert
**When** ich `get_edge` mit `source_name`, `target_name`, `relation` aufrufe
**Then** erhalte ich:
- Bei existierender Edge: `{edge_id, source_id, target_id, relation, weight, properties, created_at, status: "success"}`
- Bei nicht-existierender Edge: `{edge: null, status: "not_found"}`

**And** Source/Target können in beliebiger Reihenfolge existieren (lookup by name, not ID)

**Technical Notes:**
- Neue DB-Funktion in `mcp_server/db/graph.py`
- SQL mit JOINs: `edges JOIN nodes ON source_id/target_id`
- Geschätzte Zeit: 45min

---

## Story 6.3: count_by_type MCP Tool

**Als** autonomer Agent oder Entwickler,
**möchte ich** eine Übersicht aller Eintragstypen mit Counts,
**sodass** ich schnelle Integritätsprüfungen durchführen kann.

**Acceptance Criteria:**

**Given** die Datenbank enthält verschiedene Memory-Typen
**When** ich `count_by_type` aufrufe
**Then** erhalte ich:
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

**And** Bei leerer Datenbank sind alle Counts 0 (keine Errors)

**Technical Notes:**
- Neue Datei: `mcp_server/db/stats.py`
- UNION ALL für effiziente Abfrage aller Counts
- Geschätzte Zeit: 30min

---

## Story 6.4: list_episodes MCP Tool

**Als** autonomer Agent (I/O),
**möchte ich** alle Episode-Einträge mit Pagination auflisten,
**sodass** ich Lücken erkennen kann (z.B. fehlende Sessions).

**Acceptance Criteria:**

**Given** Episodes existieren in der Datenbank
**When** ich `list_episodes` aufrufe mit optionalen Parametern:
- `since`: ISO 8601 Timestamp (optional)
- `limit`: 1-100 (default 50)
- `offset`: 0+ (default 0)
**Then** erhalte ich:
```json
{
    "episodes": [{id, query, reward, created_at}, ...],
    "total_count": 86,
    "limit": 50,
    "offset": 0,
    "status": "success"
}
```

**And** `since` Filter funktioniert korrekt
**And** Pagination mit `offset` funktioniert

**Technical Notes:**
- Neue Datei: `mcp_server/db/episode.py`
- Zwei Queries: Data + Count für Pagination
- Geschätzte Zeit: 45min

---

## Story 6.5: get_insight_by_id MCP Tool

**Als** Entwickler oder Agent,
**möchte ich** einen L2 Insight per ID abrufen,
**sodass** ich Stichproben-Verifikation durchführen kann.

**Acceptance Criteria:**

**Given** L2 Insights existieren mit bekannten IDs
**When** ich `get_insight_by_id` mit `id: 123` aufrufe
**Then** erhalte ich:
- Bei existierendem Insight: Full insight data mit `status: "success"`
- Bei nicht-existierendem Insight: `{insight: null, status: "not_found"}`

**Technical Notes:**
- Neue Datei: `mcp_server/db/insights.py`
- Simple SELECT by ID
- Geschätzte Zeit: 20min

---

## Story 6.6: Integration Tests für Verification Workflow

**Als** Entwickler,
**möchte ich** Integration Tests für den Write-then-Verify Workflow,
**sodass** die Verification-Endpoints in der Praxis funktionieren.

**Acceptance Criteria:**

**Given** alle Verification-Tools sind implementiert (Stories 6.1-6.5)
**When** ich den Integration Test ausführe
**Then** verifiziert der Test:

1. **Write-then-Verify Node:**
   - `graph_add_node(label, name)` → get node_id
   - `get_node_by_name(name)` → verify same node_id

2. **Write-then-Verify Edge:**
   - `graph_add_edge(source, target, relation)` → get edge_id
   - `get_edge(source, target, relation)` → verify same edge_id

3. **Count Sanity Check:**
   - Insert test data
   - `count_by_type()` → verify counts increased

**Technical Notes:**
- Datei: `tests/test_verification_endpoints.py`
- pytest fixtures für Cleanup
- Geschätzte Zeit: 1h

---

## Story Summary

| Story | Titel | Aufwand | Abhängigkeiten |
|-------|-------|---------|----------------|
| 6.1 | get_node_by_name | XS (30min) | - |
| 6.2 | get_edge | S (45min) | - |
| 6.3 | count_by_type | S (30min) | - |
| 6.4 | list_episodes | S (45min) | - |
| 6.5 | get_insight_by_id | XS (20min) | - |
| 6.6 | Integration Tests | S (1h) | 6.1-6.5 |

**Gesamt:** ~3.5 Stunden

---

## Out of Scope

### list_operations (Operations Audit Log)
Erfordert neues Logging-System mit INSERT-Trigger oder Application-Level Hooks. Separate Tech-Spec erforderlich wenn Use Case validiert.

---

## Definition of Done

- [ ] Alle 5 MCP Tools sind registriert und funktional
- [ ] Unit Tests für jeden Endpoint (100% Coverage)
- [ ] Integration Tests für Write-then-Verify Workflow
- [ ] Tool-Registration in `__init__.py` aktualisiert
- [ ] Dokumentation in README aktualisiert (optional)
