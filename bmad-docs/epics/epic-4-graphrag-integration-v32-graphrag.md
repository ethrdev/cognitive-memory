# Epic 4: GraphRAG Integration (v3.2-GraphRAG)

**Epic Goal:** Erweitere cognitive-memory um Graph-basierte Speicherung und Abfrage von Entitäten und Beziehungen via PostgreSQL Adjacency List Pattern, um BMAD-BMM Agenten strukturierten Kontext für Architektur-Checks, Risikoanalysen und Knowledge Harvesting bereitzustellen.

**Business Value:** Ermöglicht Queries wie "Welche Technologien nutzt Projekt X?" oder "Gibt es Erfahrung mit Stripe API?" durch strukturierte Graphen-Traversierung. Hybrid Search wird auf 60% Semantic + 20% Keyword + 20% Graph erweitert für kontextreichere Retrieval-Ergebnisse.

**Timeline:** 30-40 Stunden (1.5-2 Wochen bei 20h/Woche)
**Budget:** €0/mo (keine zusätzlichen API-Kosten, rein PostgreSQL-basiert)

**Dependencies:**
- Benötigt: Story 1.2 (PostgreSQL Setup) ✅ bereits abgeschlossen
- Benötigt: Story 1.6 (hybrid_search Tool) für Erweiterung in Story 4.6
- Kann parallel zu Epic 3 laufen (erwünscht, nicht kritisch)

---

## Story 4.1: Graph Schema Migration (nodes + edges Tabellen)

**Als** Entwickler,
**möchte ich** die PostgreSQL-Tabellen für Graph-Speicherung erstellen,
**sodass** Entitäten und Beziehungen persistent gespeichert werden können.

**Acceptance Criteria:**

**Given** PostgreSQL läuft mit cognitive_memory Datenbank
**When** ich die Migration ausführe
**Then** existieren folgende Tabellen:

- `nodes` (id UUID, label VARCHAR, name VARCHAR, properties JSONB, vector_id FK, created_at)
- `edges` (id UUID, source_id FK, target_id FK, relation VARCHAR, weight FLOAT, properties JSONB, created_at)
- UNIQUE Constraints für Idempotenz (label+name bei nodes, source+target+relation bei edges)
- Indexes auf label, name, relation für schnelle Lookups
- FK Constraint von nodes.vector_id zu l2_insights.id (optional)

**And** Migration-Script ist erstellt:

- Datei: `mcp_server/db/migrations/003_add_graph_tables.sql`
- Kann mit `psql -f` ausgeführt werden
- Rollback-Script vorhanden

**Prerequisites:** Story 1.2 (PostgreSQL Setup)

**Technical Notes:**

- UUID statt SERIAL für Node IDs (besser für verteilte Systeme)
- ON DELETE CASCADE für edges (wenn Node gelöscht, auch Kanten löschen)
- GIN Index auf properties JSONB für flexible Metadaten-Queries
- Geschätzte Zeit: 3-4h

---

## Story 4.2: graph_add_node Tool Implementation

**Als** Claude Code,
**möchte ich** Graph-Knoten via MCP Tool erstellen,
**sodass** Entitäten (Projekte, Technologien, Kunden) im Graph gespeichert werden.

**Acceptance Criteria:**

**Given** Graph-Schema existiert (Story 4.1)
**When** Claude Code `graph_add_node` aufruft mit (label, name, properties, vector_id)
**Then** wird der Node erstellt oder gefunden:

- Idempotent: Wenn Node mit label+name existiert → Return existing ID
- Wenn neu: INSERT mit allen Feldern
- Optional: vector_id verknüpft Node mit L2 Insight Embedding

**And** Response enthält:

- `node_id` (UUID)
- `created` (boolean: true wenn neu, false wenn existierend)
- `label`, `name` zur Bestätigung

**And** Fehlerbehandlung:

- Bei ungültigen Parametern: Klare Error-Message
- Bei DB-Connection-Fehler: Retry-Logic (wie andere Tools)

**Prerequisites:** Story 4.1 (Schema vorhanden)

**Technical Notes:**

- SQL: `INSERT ... ON CONFLICT (label, name) DO NOTHING RETURNING id`
- Labels sollten standardisiert sein: "Project", "Technology", "Client", "Error", "Solution"
- Geschätzte Zeit: 4-5h

---

## Story 4.3: graph_add_edge Tool Implementation

**Als** Claude Code,
**möchte ich** Kanten zwischen Graph-Knoten erstellen,
**sodass** Beziehungen (USES, SOLVES, CREATED_BY) gespeichert werden.

**Acceptance Criteria:**

**Given** Nodes existieren (oder werden automatisch erstellt)
**When** Claude Code `graph_add_edge` aufruft mit (source_name, target_name, relation, source_label, target_label, weight)
**Then** wird die Kante erstellt:

- Source und Target Nodes werden automatisch erstellt falls nicht vorhanden (Upsert)
- Edge wird eingefügt mit Relation und optionalem Weight (default 1.0)
- Idempotent: Wenn Edge source+target+relation existiert → Update weight/properties

**And** Response enthält:

- `edge_id` (UUID)
- `created` (boolean)
- `source_id`, `target_id` zur Bestätigung

**And** Standardisierte Relations:

- "USES" - Projekt nutzt Technologie
- "SOLVES" - Lösung behebt Problem
- "CREATED_BY" - Entität wurde von Agent erstellt
- "RELATED_TO" - Allgemeine Verknüpfung
- "DEPENDS_ON" - Abhängigkeit

**Prerequisites:** Story 4.2 (graph_add_node funktioniert)

**Technical Notes:**

- Transaktional: Beide Node Upserts + Edge Insert in einer Transaktion
- Weight: 0.0-1.0, höher = stärkere Verbindung
- Geschätzte Zeit: 4-5h

---

## Story 4.4: graph_query_neighbors Tool Implementation

**Als** Claude Code,
**möchte ich** Nachbar-Knoten eines Nodes abfragen,
**sodass** ich strukturierte Queries wie "Welche Technologien nutzt Projekt X?" beantworten kann.

**Acceptance Criteria:**

**Given** Graph mit Nodes und Edges existiert
**When** Claude Code `graph_query_neighbors` aufruft mit (node_name, relation_type, depth)
**Then** werden verbundene Nodes gefunden:

- Bei depth=1: Direkte Nachbarn
- Bei depth>1: WITH RECURSIVE CTE für Multi-Hop Traversal
- Optional: Filterung nach relation_type (z.B. nur "USES" Kanten)
- Max depth: 5 (Performance-Limit)

**And** Response enthält Array von:

- `node_id`, `label`, `name`, `properties`
- `relation` (die Verbindungs-Relation)
- `distance` (Anzahl Hops vom Start-Node)
- `weight` (Kanten-Gewichtung)

**And** Sortierung:

- Primär nach distance (nähere Nodes zuerst)
- Sekundär nach weight (stärkere Verbindungen zuerst)

**Prerequisites:** Story 4.3 (Edges existieren)

**Technical Notes:**

- WITH RECURSIVE CTE für Graph-Traversal in PostgreSQL
- Performance: <50ms für depth=1-3, <200ms für depth=4-5
- Cycle Detection: Bereits besuchte Nodes ausschließen
- Geschätzte Zeit: 5-6h

---

## Story 4.5: graph_find_path Tool Implementation

**Als** Claude Code,
**möchte ich** den kürzesten Pfad zwischen zwei Nodes finden,
**sodass** ich Fragen wie "Gibt es Verbindung zwischen Kunde X und Problem Y?" beantworten kann.

**Acceptance Criteria:**

**Given** Graph mit Nodes und Edges existiert
**When** Claude Code `graph_find_path` aufruft mit (start_node, end_node, max_depth)
**Then** wird der kürzeste Pfad gefunden:

- BFS-basiertes Pathfinding via WITH RECURSIVE
- Stoppt wenn end_node erreicht oder max_depth (default 5) überschritten
- Gibt ALLE Pfade zurück falls mehrere gleichlange existieren (bis Limit)

**And** Response enthält:

- `path_found` (boolean)
- `path_length` (Anzahl Hops)
- `path`: Array von {node, edge} Objekten in Reihenfolge
- Bei keinem Pfad: `path_found: false`, leeres path Array

**And** Pathfinding-Limit:

- Max 10 Pfade zurückgeben (falls mehrere gleichlange)
- Timeout: 1s max für Pathfinding-Query

**Prerequisites:** Story 4.4 (Traversal funktioniert)

**Technical Notes:**

- Bidirektionales BFS für bessere Performance (optional)
- PostgreSQL WITH RECURSIVE mit Pfad-Tracking
- Cycle Detection in Path (keine Schleifen)
- Geschätzte Zeit: 5-6h

---

## Story 4.6: Hybrid Search Erweiterung (Vector + Keyword + Graph RRF)

**Als** Claude Code,
**möchte ich** Graph-Ergebnisse in Hybrid Search integrieren,
**sodass** strukturelle Beziehungen das Retrieval verbessern.

**Acceptance Criteria:**

**Given** hybrid_search Tool existiert (Story 1.6)
**When** Query relationale Keywords enthält (z.B. "nutzt", "verbunden mit")
**Then** wird Graph-Search zusätzlich ausgeführt:

- Query-Routing: Erkennung von relationalen vs. semantischen Queries
- Graph-Search: Extrahiere Entities aus Query, finde verbundene Nodes
- Lookup: Hole L2 Insights via nodes.vector_id Referenz

**And** RRF Fusion wird auf 3 Quellen erweitert:

- Aktuell: 80% Semantic + 20% Keyword
- Neu: 60% Semantic + 20% Keyword + 20% Graph
- Score: `rrf_score = w_s/(k+rank_s) + w_k/(k+rank_k) + w_g/(k+rank_g)`

**And** Query-Routing Logik:

- Keywords: "nutzt", "verwendet", "verbunden", "abhängig", "Projekt", "Technologie"
- Bei Match: weight_graph=0.4, weight_semantic=0.4, weight_keyword=0.2
- Sonst: Default 60/20/20

**And** Konfiguration in config.yaml:

- `hybrid_search_weights.semantic: 0.6`
- `hybrid_search_weights.keyword: 0.2`
- `hybrid_search_weights.graph: 0.2`

**Prerequisites:** Stories 4.1-4.5 (Graph-Tools funktionieren)

**Technical Notes:**

- Entity Extraction: Simple Regex/Keyword matching (kein LLM-NER)
- Graph-Score: Basiert auf Pfad-Distanz zu Query-Entities
- Fallback: Wenn keine Graph-Matches → 80/20 Semantic/Keyword wie bisher
- Geschätzte Zeit: 5-6h

---

## Story 4.7: Integration Testing mit BMAD-BMM Use Cases

**Als** Entwickler,
**möchte ich** die GraphRAG-Integration end-to-end testen,
**sodass** sichergestellt ist dass BMAD-BMM Agenten sie nutzen können.

**Acceptance Criteria:**

**Given** alle Graph-Tools implementiert (Stories 4.1-4.6)
**When** ich die drei primären Use Cases teste
**Then** funktionieren alle korrekt:

**Use Case 1: Architecture Check**
- Setup: Node "High Volume Requirement" + Edge "SOLVED_BY" → "PostgreSQL"
- Query: "Welche Datenbank für High Volume?"
- Expected: PostgreSQL in Top-3 Results

**Use Case 2: Risk Analysis**
- Setup: Nodes "Projekt A" + "Stripe API" + Edge "USES"
- Query: "Erfahrung mit Stripe API?"
- Expected: "Projekt A" als verbundenes Projekt gefunden

**Use Case 3: Knowledge Harvesting**
- Action: `graph_add_node` + `graph_add_edge` für neues Projekt
- Verification: Nodes und Edges korrekt in DB
- Query: Neues Projekt erscheint in Neighbor-Queries

**And** Performance-Validation:

- graph_query_neighbors (depth=1): <50ms
- graph_query_neighbors (depth=3): <100ms
- graph_find_path (5 Hops): <200ms
- Hybrid Search mit Graph: <1s (wie ohne Graph)

**Prerequisites:** Stories 4.1-4.6 (alle Graph-Tools implementiert)

**Technical Notes:**

- Test-Daten: Vordefinierte Test-Graphs für reproduzierbare Tests
- Manuelles Testing in Claude Code Interface
- Logging: Alle Graph-Queries mit Timing für Performance-Analyse
- Geschätzte Zeit: 3-4h

---

## Story 4.8: GraphRAG Documentation Update

**Als** ethr,
**möchte ich** vollständige Dokumentation für die GraphRAG-Erweiterung,
**sodass** ich die neuen Tools effektiv nutzen kann.

**Acceptance Criteria:**

**Given** alle GraphRAG-Features implementiert
**When** Dokumentation finalisiert wird
**Then** sind folgende Dokumente aktualisiert:

1. **`/docs/api-reference.md`** - Neue Tools
   - graph_add_node: Parameter, Beispiele, Use Cases
   - graph_add_edge: Parameter, Relations-Typen, Beispiele
   - graph_query_neighbors: Depth-Parameter, Response-Format
   - graph_find_path: Pathfinding-Beispiele

2. **`/docs/operations-manual.md`** - Graph Operations
   - Wie erstelle ich Graph-Nodes?
   - Wie baue ich Beziehungen auf?
   - Wie query ich den Graph?

3. **`/docs/graphrag-guide.md`** (NEU)
   - Konzept: Wann Vector vs. Graph?
   - Best Practices für Entity-Typen (Labels)
   - Best Practices für Relation-Typen
   - Beispiel-Workflows für BMAD-BMM Agenten

4. **README.md** - Feature-Highlight
   - GraphRAG als neues Feature erwähnen
   - Link zu graphrag-guide.md

**Prerequisites:** Stories 4.1-4.7 (alle Features getestet)

**Technical Notes:**

- Sprache: Deutsch (gemäß document_output_language)
- Beispiele: Konkrete BMAD-BMM Use Cases
- Diagramme: ASCII-Art für Graph-Visualisierung
- Geschätzte Zeit: 2-3h

---
