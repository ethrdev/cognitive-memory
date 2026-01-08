# Epic 5: Library API for Ecosystem Integration

**Epic Goal:** Erweitere cognitive-memory um eine Python Library API, die direkten programmatischen Zugriff auf alle Storage-Funktionen ermöglicht, ohne den MCP Server zu benötigen. Dies ermöglicht i-o-system, tethr und agentic-business die Nutzung von cognitive-memory als Storage-Backend.

**Business Value:**
1. **Ecosystem Integration** - i-o-system, tethr, agentic-business können cognitive-memory als Storage nutzen
2. **Dual Interface** - MCP für externe Clients, Library für interne Python-Integration
3. **Performance** - Direkte DB-Calls ohne MCP Protocol Overhead
4. **Testbarkeit** - Unit Tests ohne MCP Server möglich

**Timeline:** 27-38 Stunden (1.5-2 Wochen bei 20h/Woche)
**Budget:** €0/mo (keine zusätzlichen API-Kosten, nutzt bestehende OpenAI Embeddings)

**Dependencies:**
- Benötigt: Story 1.2 (PostgreSQL Setup) ✅ bereits abgeschlossen
- Benötigt: Story 1.6 (hybrid_search Implementation) ✅ bereits abgeschlossen
- Benötigt: Epic 4 (GraphRAG) ✅ bereits abgeschlossen
- Kann unabhängig von Epic 3 Status laufen

---

## Story 5.1: Core Library Package Setup

**Als** Ecosystem-Entwickler,
**möchte ich** ein `cognitive_memory` Python Package,
**sodass** ich `from cognitive_memory import MemoryStore` nutzen kann.

**Acceptance Criteria:**

**Given** das bestehende cognitive-memory Repository
**When** ich das Package installiere mit `pip install -e .`
**Then** existiert das Package `cognitive_memory/`:

- `cognitive_memory/__init__.py` mit Public API Exports
- `cognitive_memory/store.py` (Hauptklasse MemoryStore)
- `cognitive_memory/connection.py` (DB Connection Management)
- Package ist in `pyproject.toml` konfiguriert

**And** der Import funktioniert:

```python
from cognitive_memory import MemoryStore
```

**And** das Package koexistiert mit `mcp_server/`:

- Keine Konflikte mit bestehendem Code
- Shared Dependencies werden wiederverwendet (psycopg2, openai, etc.)

**Prerequisites:** Keine (Foundation Story für Epic 5)

**Technical Notes:**

- Package-Struktur parallel zu `mcp_server/`
- `pyproject.toml` erweitern um `cognitive_memory` als zusätzliches Package
- Re-use von `mcp_server/db/connection.py` für DB-Connections
- Geschätzte Zeit: 2-3h

---

## Story 5.2: MemoryStore Core Class

**Als** i-o-system Entwickler,
**möchte ich** eine `MemoryStore` Klasse mit DB-Connection Management,
**sodass** ich ohne MCP Server auf cognitive-memory zugreifen kann.

**Acceptance Criteria:**

**Given** Package-Setup aus Story 5.1
**When** ich `MemoryStore` instanziiere
**Then** wird eine DB-Connection hergestellt:

- `MemoryStore(connection_string="...")` Konstruktor
- Alternative: `MemoryStore.from_env()` liest `DATABASE_URL` aus Environment
- Connection Pooling via bestehender `get_connection()` Funktion

**And** Context Manager Support funktioniert:

```python
with MemoryStore() as store:
    results = store.search("query")
# Connection wird automatisch geschlossen
```

**And** Graceful Error Handling:

- Bei DB-Connection-Fehler: Klare Exception mit Retry-Hinweis
- Bei ungültiger Connection-String: Validierung mit hilfreicher Error-Message

**Prerequisites:** Story 5.1 (Package-Struktur)

**Technical Notes:**

- Wiederverwendung von `mcp_server/db/connection.py`
- Lazy Connection: Erst bei erstem DB-Zugriff verbinden
- Thread-Safety: Connection Pool für concurrent access
- Geschätzte Zeit: 4-6h

---

## Story 5.3: Hybrid Search Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.search(query, top_k)` aufrufen,
**sodass** ich Semantic + Keyword Search ohne MCP nutzen kann.

**Acceptance Criteria:**

**Given** MemoryStore ist instanziiert
**When** ich `store.search(query, top_k=5)` aufrufe
**Then** wird Hybrid Search ausgeführt:

- Embedding wird automatisch via OpenAI API generiert
- Semantic Search (70%) + Keyword Search (30%) mit RRF Fusion
- Konfigurierbare Weights: `store.search(query, weights={"semantic": 0.8, "keyword": 0.2})`

**And** Response enthält Liste von `SearchResult`:

```python
@dataclass
class SearchResult:
    id: int
    content: str
    score: float
    source: str  # "l2_insight" oder "l0_raw"
    metadata: dict
```

**And** Code-Wiederverwendung aus MCP Server:

- Nutzt `mcp_server/tools/semantic_search()`
- Nutzt `mcp_server/tools/keyword_search()`
- Nutzt `mcp_server/tools/rrf_fusion()`
- Nutzt `mcp_server/external/openai_client.py` für Embeddings

**Prerequisites:** Story 5.2 (MemoryStore Core)

**Technical Notes:**

- Import-Struktur: `from mcp_server.tools import semantic_search, keyword_search, rrf_fusion`
- Embedding-Caching optional (für wiederholte Queries)
- Geschätzte Zeit: 4-6h

---

## Story 5.4: L2 Insight Storage Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.store_insight(content, source_ids)` aufrufen,
**sodass** ich Semantic Memory ohne MCP speichern kann.

**Acceptance Criteria:**

**Given** MemoryStore ist instanziiert
**When** ich `store.store_insight(content, source_ids, metadata=None)` aufrufe
**Then** wird L2 Insight erstellt:

- Embedding wird automatisch via OpenAI API generiert
- Semantic Fidelity Check (E2 Enhancement) wird ausgeführt
- Insight wird in `l2_insights` Tabelle gespeichert

**And** Response enthält `InsightResult`:

```python
@dataclass
class InsightResult:
    id: int
    embedding_status: str  # "success" oder "failed"
    fidelity_score: float  # 0.0-1.0
    created_at: datetime
```

**And** Validation:

- `content` darf nicht leer sein
- `source_ids` müssen existierende L0 Raw IDs sein (optional: soft validation)

**Prerequisites:** Story 5.2 (MemoryStore Core)

**Technical Notes:**

- Wiederverwendung von `mcp_server/tools/compress_to_l2_insight.py` Logik
- Semantic Fidelity Check: Embedding-Similarity zwischen Input und Stored Content
- Geschätzte Zeit: 3-4h

---

## Story 5.5: Working Memory Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.working.add(content, importance)` aufrufen,
**sodass** ich Session Context ohne MCP speichern kann.

**Acceptance Criteria:**

**Given** MemoryStore ist instanziiert
**When** ich `store.working.add(content, importance=0.5)` aufrufe
**Then** wird Working Memory aktualisiert:

- Content wird zur Working Memory hinzugefügt
- LRU Eviction wenn >10 Items (oder konfigurierbar)
- Stale Memory Archivierung bei Eviction (Importance >0.8)

**And** Response enthält `WorkingMemoryResult`:

```python
@dataclass
class WorkingMemoryResult:
    added_id: int
    evicted_id: Optional[int]
    archived_id: Optional[int]  # Falls zu Stale Memory archiviert
```

**And** weitere Working Memory Operationen:

- `store.working.list()` → Liste aller Items
- `store.working.clear()` → Alle Items löschen
- `store.working.get(id)` → Einzelnes Item abrufen

**Prerequisites:** Story 5.2 (MemoryStore Core)

**Technical Notes:**

- Wiederverwendung von `mcp_server/tools/update_working_memory.py` Logik
- WorkingMemory als Sub-Objekt von MemoryStore (`store.working`)
- Geschätzte Zeit: 3-4h

---

## Story 5.6: Episode Memory Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.episode.store(query, reward, reflection)` aufrufen,
**sodass** ich Verbal RL Episodes ohne MCP speichern kann.

**Acceptance Criteria:**

**Given** MemoryStore ist instanziiert
**When** ich `store.episode.store(query, reward, reflection)` aufrufe
**Then** wird Episode gespeichert:

- Query-Embedding wird automatisch generiert
- Reward wird validiert (-1.0 bis +1.0)
- Episode wird in `episode_memory` Tabelle gespeichert

**And** Response enthält `EpisodeResult`:

```python
@dataclass
class EpisodeResult:
    id: int
    embedding_status: str
    created_at: datetime
```

**And** Episode Retrieval:

- `store.episode.search(query, min_similarity=0.7, limit=3)` → Ähnliche Episodes finden
- `store.episode.list(limit=10)` → Letzte Episodes abrufen

**And** Validation:

- `reward` muss im Bereich -1.0 bis +1.0 liegen
- `reflection` muss Format "Problem: ... Lesson: ..." folgen (soft validation)

**Prerequisites:** Story 5.2 (MemoryStore Core)

**Technical Notes:**

- Wiederverwendung von `mcp_server/tools/store_episode.py` Logik
- EpisodeMemory als Sub-Objekt von MemoryStore (`store.episode`)
- Geschätzte Zeit: 3-4h

---

## Story 5.7: Graph Query Neighbors Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.graph.query_neighbors(node_name)` aufrufen,
**sodass** ich Graph-Traversierung ohne MCP durchführen kann.

**Acceptance Criteria:**

**Given** MemoryStore ist instanziiert und Graph-Daten existieren
**When** ich `store.graph.query_neighbors(node_name, relation_type=None, depth=1)` aufrufe
**Then** werden Nachbar-Nodes gefunden:

- Single-Hop (depth=1) und Multi-Hop (depth>1) Traversal
- Optional Filterung nach `relation_type`
- Max depth: 5 (Performance-Limit)

**And** Response enthält Liste von `GraphNode`:

```python
@dataclass
class GraphNode:
    id: str  # UUID
    label: str
    name: str
    properties: dict
    relation: str  # Verbindungs-Relation
    distance: int  # Anzahl Hops
    weight: float
```

**And** weitere Graph-Operationen:

- `store.graph.add_node(label, name, properties=None)` → Node erstellen
- `store.graph.add_edge(source, target, relation, weight=1.0)` → Edge erstellen
- `store.graph.find_path(start, end, max_depth=5)` → Pfad finden

**Prerequisites:** Story 5.2 (MemoryStore Core), Epic 4 (GraphRAG)

**Technical Notes:**

- Wiederverwendung von `mcp_server/tools/graph_query_neighbors.py`
- GraphStore als Sub-Objekt von MemoryStore (`store.graph`)
- WITH RECURSIVE CTE für Traversal (wie MCP Tool)
- Geschätzte Zeit: 4-5h

---

## Story 5.8: Documentation & Examples

**Als** Ecosystem-Entwickler,
**möchte ich** Dokumentation und Beispiele für die Library API,
**sodass** ich sie korrekt nutzen kann.

**Acceptance Criteria:**

**Given** alle Library API Features implementiert (Stories 5.1-5.7)
**When** Dokumentation finalisiert wird
**Then** existieren folgende Dokumente:

1. **`/docs/api/library.md`** - API Reference
   - Alle Klassen und Methoden dokumentiert
   - Parameter-Beschreibungen und Return Types
   - Error Handling Patterns

2. **`/examples/library_usage.py`** - Vollständiges Beispiel
   - Connection Setup
   - Search, Store, Working Memory, Episode, Graph
   - Error Handling Beispiele

3. **`/docs/migration-guide.md`** - MCP → Library Migration
   - Wann MCP vs. Library nutzen?
   - Code-Beispiele für Umstellung
   - Performance-Unterschiede

4. **README.md** Update
   - Library API Section hinzufügen
   - Installation Instructions erweitern
   - Quick Start Beispiel

**And** i-o-system Integration:

- Dokumentation wie `CognitiveMemoryAdapter` die Library nutzen kann
- Beispiel für StorageBackend Protocol Compliance

**Prerequisites:** Stories 5.1-5.7 (alle Features implementiert)

**Technical Notes:**

- Sprache: Deutsch (gemäß document_output_language)
- Code-Beispiele: Python mit Type Hints
- Geschätzte Zeit: 4-6h

---
