# Epic Preparation: Library API for Ecosystem Integration

**Author:** Party Mode Konsens (i-o-system Team)
**Date:** 2025-11-30
**Status:** VORBEREITUNG - Zur Epic-Erstellung
**Source:** Party Mode Session in i-o-system

---

## Kontext & Motivation

### Problem Statement

Das cognitive-memory Ecosystem hat einen **architektonischen Disconnect**:

| Erwartung | Realität |
|-----------|----------|
| i-o-system erwartet `import cognitive_memory` | cognitive-memory ist ein MCP Server |
| Python Library API (`MemoryStore()`) | Nur MCP Tools (stdio Protocol) |
| Synchrone Method Calls | Async Tool Invocations |

Der `CognitiveMemoryAdapter` in i-o-system (`src/io_system/storage/cognitive.py`) ist ein **vollständig designter Stub** mit:
- ✅ Format-Konvertierung (`_to_cm_format`, `_from_cm_format`)
- ✅ StorageBackend Protocol Compliance
- ❌ Keine funktionierende Verbindung zu cognitive-memory

### Strategische Bedeutung

cognitive-memory dient als Storage Layer für das gesamte Ecosystem:

```
┌─────────────────────────────────────────────────┐
│                   ECOSYSTEM                      │
│                                                  │
│   tethr ──────────┐                             │
│                   │                             │
│   i-o-system ─────┼──→ cognitive_memory.py ──→ PostgreSQL
│                   │    (Library API)            │
│   agentic-business┘                             │
│                                                  │
│   Claude Code ────→ MCP Server ──→ PostgreSQL   │
└─────────────────────────────────────────────────┘
```

**Ohne Library API** können tethr, i-o-system und agentic-business cognitive-memory nicht nutzen.

---

## Epic Definition

### Epic Goal

Erweitere cognitive-memory um eine **Python Library API**, die direkten programmatischen Zugriff auf alle Storage-Funktionen ermöglicht, ohne den MCP Server zu benötigen.

### Business Value

1. **Ecosystem Integration**: i-o-system, tethr, agentic-business können cognitive-memory als Storage nutzen
2. **Dual Interface**: MCP für externe Clients, Library für interne Python-Integration
3. **Performance**: Direkte DB-Calls ohne MCP Protocol Overhead
4. **Testbarkeit**: Unit Tests ohne MCP Server möglich

### Nicht-Ziele (Out of Scope)

- MCP Server Änderungen (bleibt unverändert)
- Breaking Changes an bestehender API
- GraphRAG Library Wrapper (separates Epic)

---

## Technical Analysis

### Bestehende MCP Tools → Library API Mapping

| MCP Tool | Library API | Priority |
|----------|-------------|----------|
| `hybrid_search` | `MemoryStore.search(query, top_k, weights)` | P0 |
| `compress_to_l2_insight` | `MemoryStore.store_insight(content, source_ids)` | P0 |
| `update_working_memory` | `WorkingMemory.add(content, importance)` | P1 |
| `store_episode` | `EpisodeMemory.store(query, reward, reflection)` | P1 |
| `store_raw_dialogue` | `L0Memory.store(session_id, speaker, content)` | P2 |
| `graph_add_node` | (Out of Scope - separates Epic) | - |
| `graph_add_edge` | (Out of Scope - separates Epic) | - |

### Vorgeschlagene Package-Struktur

```
cognitive-memory/
├── cognitive_memory/           # NEW: Library API Package
│   ├── __init__.py             # Public API exports
│   ├── store.py                # MemoryStore class
│   ├── search.py               # HybridSearch wrapper
│   ├── working.py              # WorkingMemory class
│   ├── episode.py              # EpisodeMemory class
│   ├── l0.py                   # L0 Raw Memory class
│   └── connection.py           # DB Connection management
├── mcp_server/                 # UNCHANGED: MCP Server
└── ...
```

### API Design (Draft)

```python
# cognitive_memory/__init__.py
from .store import MemoryStore
from .working import WorkingMemory
from .episode import EpisodeMemory

__all__ = ["MemoryStore", "WorkingMemory", "EpisodeMemory"]

# Usage Example
from cognitive_memory import MemoryStore

store = MemoryStore(
    host="localhost",
    port=5432,
    database="cognitive_memory",
    user="mcp_user"
)

# Semantic Search
results = store.search("autonomy consciousness", top_k=5)

# Store Insight
insight_id = store.store_insight(
    content="User prefers direct communication",
    source_ids=[1, 2, 3]
)

# Working Memory
store.working.add("Current task: Help with Python", importance=0.8)
```

### Wiederverwendung von MCP Server Code

Die Library API sollte **denselben Code** wie der MCP Server nutzen:

```python
# cognitive_memory/store.py
from mcp_server.tools import (
    semantic_search,
    keyword_search,
    rrf_fusion,
    get_embedding_with_retry
)
from mcp_server.db.connection import get_connection

class MemoryStore:
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        # Nutzt existierende Funktionen aus mcp_server
        ...
```

Dies stellt sicher:
- **Keine Code-Duplizierung**
- **Konsistentes Verhalten** zwischen MCP und Library
- **Einfache Wartung**

---

## Story Breakdown (Draft)

### Story 5.1: Core Library Package Setup

**Als** Ecosystem-Entwickler,
**möchte ich** ein `cognitive_memory` Python Package,
**sodass** ich `from cognitive_memory import MemoryStore` nutzen kann.

**Acceptance Criteria:**
- Package `cognitive_memory/` existiert mit `__init__.py`
- `pip install -e .` installiert das Package
- Import `from cognitive_memory import MemoryStore` funktioniert
- Package ist in `pyproject.toml` konfiguriert

**Aufwand:** 2-3h

---

### Story 5.2: MemoryStore Core Class

**Als** i-o-system Entwickler,
**möchte ich** eine `MemoryStore` Klasse mit DB-Connection,
**sodass** ich ohne MCP Server auf cognitive-memory zugreifen kann.

**Acceptance Criteria:**
- `MemoryStore(connection_string=...)` Konstruktor
- Connection Pooling (nutzt existierenden `get_connection()`)
- Context Manager Support (`with MemoryStore() as store:`)
- Graceful Shutdown bei Connection-Fehlern

**Aufwand:** 4-6h

---

### Story 5.3: Hybrid Search Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.search(query, top_k)` aufrufen,
**sodass** ich Semantic + Keyword Search ohne MCP nutzen kann.

**Acceptance Criteria:**
- `store.search(query, top_k=5, weights={"semantic": 0.7, "keyword": 0.3})` funktioniert
- Nutzt existierende `semantic_search()`, `keyword_search()`, `rrf_fusion()` aus mcp_server
- Embedding wird automatisch generiert (OpenAI API)
- Rückgabe: `list[SearchResult]` mit id, content, score

**Aufwand:** 4-6h

---

### Story 5.4: L2 Insight Storage Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.store_insight(content, source_ids)` aufrufen,
**sodass** ich Semantic Memory ohne MCP speichern kann.

**Acceptance Criteria:**
- `store.store_insight(content, source_ids, metadata=None)` funktioniert
- Embedding wird automatisch generiert
- Fidelity Score wird berechnet
- Rückgabe: `InsightResult` mit id, embedding_status, fidelity_score

**Aufwand:** 3-4h

---

### Story 5.5: Working Memory Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.working.add(content, importance)` aufrufen,
**sodass** ich Session Context ohne MCP speichern kann.

**Acceptance Criteria:**
- `store.working.add(content, importance=0.5)` funktioniert
- LRU Eviction wird automatisch durchgeführt
- Stale Memory Archivierung bei Eviction
- Rückgabe: `WorkingMemoryResult` mit added_id, evicted_id, archived_id

**Aufwand:** 3-4h

---

### Story 5.6: Episode Memory Library API

**Als** i-o-system Entwickler,
**möchte ich** `store.episode.store(query, reward, reflection)` aufrufen,
**sodass** ich Verbal RL Episodes ohne MCP speichern kann.

**Acceptance Criteria:**
- `store.episode.store(query, reward, reflection)` funktioniert
- Embedding wird für Query generiert
- Reward Range Validation (-1.0 bis 1.0)
- Rückgabe: `EpisodeResult` mit id, embedding_status

**Aufwand:** 3-4h

---

### Story 5.7: Documentation & Examples

**Als** Ecosystem-Entwickler,
**möchte ich** Dokumentation und Beispiele für die Library API,
**sodass** ich sie korrekt nutzen kann.

**Acceptance Criteria:**
- API Reference in `docs/api/library.md`
- Usage Examples in `examples/library_usage.py`
- Migration Guide von MCP zu Library
- README.md Update mit Library API Section

**Aufwand:** 4-6h

---

## Timeline & Aufwand

| Story | Aufwand | Priorität |
|-------|---------|-----------|
| 5.1: Package Setup | 2-3h | P0 |
| 5.2: MemoryStore Core | 4-6h | P0 |
| 5.3: Hybrid Search | 4-6h | P0 |
| 5.4: L2 Insight Storage | 3-4h | P0 |
| 5.5: Working Memory | 3-4h | P1 |
| 5.6: Episode Memory | 3-4h | P1 |
| 5.7: Documentation | 4-6h | P1 |

**Gesamt:** 23-33 Stunden (3-4 Wochen bei 10h/Woche)

---

## Dependencies & Risks

### Dependencies

| Dependency | Status | Blocker? |
|------------|--------|----------|
| PostgreSQL + pgvector Setup | ✅ Existiert | Nein |
| OpenAI API Key | ✅ Existiert | Nein |
| mcp_server Code (für Wiederverwendung) | ✅ Existiert | Nein |

### Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| API Breaking Changes in mcp_server | Low | Medium | Shared Code, keine Duplizierung |
| Connection Pool Exhaustion | Medium | Low | Pool Size Limits |
| Embedding API Rate Limits | Low | Medium | Retry Logic (existiert) |

---

## Acceptance Criteria (Epic-Level)

Das Epic ist **DONE** wenn:

1. ✅ `from cognitive_memory import MemoryStore` funktioniert
2. ✅ `store.search()` liefert korrekte Ergebnisse
3. ✅ `store.store_insight()` speichert mit Embedding
4. ✅ `store.working.add()` mit LRU Eviction funktioniert
5. ✅ `store.episode.store()` speichert Episodes
6. ✅ i-o-system `CognitiveMemoryAdapter` kann Library nutzen
7. ✅ Documentation + Examples existieren
8. ✅ Unit Tests für alle API Methoden

---

## Nächste Schritte

1. **Review** dieses Dokuments durch ethr
2. **Entscheidung** ob Epic 5 (nach GraphRAG Epic 4) oder höhere Priorität
3. **Epic-Erstellung** mit `/bmad:bmm:workflows:create-epics-and-stories`
4. **Story Refinement** im Sprint Planning

---

## Referenzen

- **i-o-system CognitiveMemoryAdapter:** `src/io_system/storage/cognitive.py`
- **cognitive-memory MCP Tools:** `mcp_server/tools/__init__.py`
- **Ecosystem Architecture:** `bmad-docs/ecosystem-architecture.md`
- **Party Mode Session:** i-o-system, 2025-11-30

---

*Erstellt durch Party Mode Konsens - 8/8 Agents stimmten für diese Architektur*
