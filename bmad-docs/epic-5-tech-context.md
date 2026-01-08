# Epic 5 Technical Context: Library API for Ecosystem Integration

**Generated:** 2025-11-30
**Epic:** 5 - Library API for Ecosystem Integration
**Status:** Ready for Implementation
**Version:** v3.3.0-LibraryAPI

---

## Executive Summary

Epic 5 creates a Python Library API (`cognitive_memory` package) that wraps the existing `mcp_server/` tools, enabling ecosystem projects (i-o-system, tethr, agentic-business) to use cognitive-memory as a storage backend without the MCP protocol.

**Key Architecture Decision:** ADR-007 specifies a **Wrapper Pattern** where `cognitive_memory/` imports directly from `mcp_server/`, ensuring no code duplication and consistent behavior.

---

## Epic Overview

### Goal
Erweitere cognitive-memory um eine Python Library API, die direkten programmatischen Zugriff auf alle Storage-Funktionen ermöglicht, ohne den MCP Server zu benötigen.

### Business Value
1. **Ecosystem Integration** - i-o-system, tethr, agentic-business können cognitive-memory als Storage nutzen
2. **Dual Interface** - MCP für externe Clients, Library für interne Python-Integration
3. **Performance** - Direkte DB-Calls ohne MCP Protocol Overhead
4. **Testbarkeit** - Unit Tests ohne MCP Server möglich

### Timeline
27-38 Stunden (1.5-2 Wochen bei 20h/Woche)

### Dependencies (All Completed)
- Story 1.2: PostgreSQL Setup ✅
- Story 1.6: hybrid_search Implementation ✅
- Epic 4: GraphRAG ✅ (Stories 4.1-4.4 done)

---

## Stories Overview

| Story | Title | Effort | Status | Prerequisites |
|-------|-------|--------|--------|---------------|
| 5.1 | Core Library Package Setup | 2-3h | Backlog | None |
| 5.2 | MemoryStore Core Class | 4-6h | Backlog | 5.1 |
| 5.3 | Hybrid Search Library API | 4-6h | Backlog | 5.2 |
| 5.4 | L2 Insight Storage Library API | 3-4h | Backlog | 5.2 |
| 5.5 | Working Memory Library API | 3-4h | Backlog | 5.2 |
| 5.6 | Episode Memory Library API | 3-4h | Backlog | 5.2 |
| 5.7 | Graph Query Neighbors Library API | 3-4h | Backlog | 5.2, 4.4 |
| 5.8 | Documentation & Examples | 4-6h | Backlog | 5.1-5.7 |

---

## Technical Architecture

### Package Structure

```
cognitive-memory/
├─ cognitive_memory/              # NEW: Library API Package (Epic 5)
│  ├─ __init__.py                 # Public API: MemoryStore, WorkingMemory, EpisodeMemory, GraphStore
│  ├─ store.py                    # MemoryStore Core Class (wraps mcp_server)
│  ├─ search.py                   # SearchResult dataclass, search() method
│  ├─ working.py                  # WorkingMemory class (wraps update_working_memory)
│  ├─ episode.py                  # EpisodeMemory class (wraps store_episode)
│  ├─ graph.py                    # GraphStore class (wraps graph_* tools)
│  ├─ models.py                   # Dataclasses: SearchResult, InsightResult, etc.
│  ├─ exceptions.py               # Custom Exceptions: CognitiveMemoryError, etc.
│  └─ connection.py               # Connection wrapper (delegates to mcp_server/db)
├─ mcp_server/                    # Existing MCP Server (unchanged)
│  ├─ tools/                      # Tool implementations to wrap
│  │  ├─ hybrid_search.py         # → store.search()
│  │  ├─ compress_to_l2_insight.py → store.store_insight()
│  │  ├─ update_working_memory.py → store.working.add()
│  │  ├─ store_episode.py         → store.episode.store()
│  │  └─ graph_query_neighbors.py → store.graph.query_neighbors()
│  ├─ db/connection.py            # Shared Connection Pool
│  └─ external/openai_client.py   # Shared Embedding Generation
└─ tests/library/                 # ATDD Tests (already created - RED phase)
   ├─ test_imports.py             # R-001: Import cycle prevention
   ├─ test_memory_store.py        # Story 5.2: MemoryStore core
   ├─ test_search.py              # Story 5.3: Hybrid search
   ├─ test_store_insight.py       # Story 5.4: L2 insight storage
   ├─ test_connection_pool.py     # R-002: Connection pool exhaustion
   └─ test_contract.py            # R-003: API consistency
```

### Wrapper Pattern (ADR-007)

```python
# cognitive_memory/store.py - Wrapper imports from mcp_server
from mcp_server.db.connection import get_connection
from mcp_server.tools.hybrid_search import semantic_search, keyword_search, rrf_fusion
from mcp_server.external.openai_client import get_embedding_with_retry

class MemoryStore:
    def search(self, query: str, top_k: int = 5, weights: dict | None = None) -> list[SearchResult]:
        """Wraps mcp_server hybrid_search - NO code duplication."""
        weights = weights or {"semantic": 0.7, "keyword": 0.3}
        embedding = get_embedding_with_retry(query)
        conn = self._get_connection()
        semantic_results = semantic_search(conn, embedding, top_k * 2)
        keyword_results = keyword_search(conn, query, top_k * 2)
        fused = rrf_fusion(semantic_results, keyword_results, weights, top_k)
        return [SearchResult(**r) for r in fused]
```

---

## Public API Design

### Main Entry Point

```python
from cognitive_memory import MemoryStore

# With environment variable DATABASE_URL
store = MemoryStore.from_env()

# Or with explicit connection string
store = MemoryStore("postgresql://user:pass@localhost/cognitive_memory")

# Context manager support
with MemoryStore.from_env() as store:
    results = store.search("query")
```

### Core Methods

```python
class MemoryStore:
    def __init__(self, connection_string: str | None = None): ...

    @classmethod
    def from_env(cls) -> "MemoryStore": ...

    def __enter__(self) -> "MemoryStore": ...
    def __exit__(self, *args) -> None: ...

    # Core search
    def search(self, query: str, top_k: int = 5,
               weights: dict[str, float] | None = None) -> list[SearchResult]: ...

    # Store insight
    def store_insight(self, content: str, source_ids: list[int],
                      metadata: dict | None = None) -> InsightResult: ...

    # Sub-module access
    @property
    def working(self) -> WorkingMemory: ...

    @property
    def episode(self) -> EpisodeMemory: ...

    @property
    def graph(self) -> GraphStore: ...
```

### Sub-Module Classes

```python
class WorkingMemory:
    def add(self, content: str, importance: float = 0.5) -> WorkingMemoryResult
    def list(self) -> list[WorkingMemoryItem]
    def get(self, id: int) -> WorkingMemoryItem | None
    def clear(self) -> int

class EpisodeMemory:
    def store(self, query: str, reward: float, reflection: str) -> EpisodeResult
    def search(self, query: str, min_similarity: float = 0.7, limit: int = 3) -> list[Episode]
    def list(self, limit: int = 10) -> list[Episode]

class GraphStore:
    def add_node(self, label: str, name: str, properties: dict | None = None) -> NodeResult
    def add_edge(self, source: str, target: str, relation: str, weight: float = 1.0) -> EdgeResult
    def query_neighbors(self, node_name: str, relation_type: str | None = None, depth: int = 1) -> list[GraphNode]
```

---

## Data Models

```python
# cognitive_memory/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class SearchResult:
    id: int
    content: str
    score: float
    source: str  # "l2_insight" | "l0_raw"
    metadata: dict

@dataclass
class InsightResult:
    id: int
    embedding_status: str  # "success" | "failed"
    fidelity_score: float
    created_at: datetime

@dataclass
class WorkingMemoryResult:
    added_id: int
    evicted_id: Optional[int]
    archived_id: Optional[int]

@dataclass
class EpisodeResult:
    id: int
    embedding_status: str
    created_at: datetime

@dataclass
class GraphNode:
    id: str  # UUID
    label: str
    name: str
    properties: dict
    relation: str
    distance: int
    weight: float
```

---

## Exception Hierarchy

```python
# cognitive_memory/exceptions.py
class CognitiveMemoryError(Exception):
    """Base Exception für alle Library Errors."""

class ConnectionError(CognitiveMemoryError):
    """Database Connection Fehler."""

class SearchError(CognitiveMemoryError):
    """Hybrid Search Fehler (Embedding, Query, etc.)."""

class StorageError(CognitiveMemoryError):
    """Storage Operation Fehler (Insert, Update)."""

class ValidationError(CognitiveMemoryError):
    """Input Validation Fehler."""

class EmbeddingError(CognitiveMemoryError):
    """OpenAI Embedding API Fehler."""
```

---

## Risk Mitigations

### R-001: Import Cycle Prevention (Score: 6)

**Risk:** Import-Zyklus zwischen `cognitive_memory/` und `mcp_server/`

**Mitigation:**
1. Dependency direction: `cognitive_memory/` → `mcp_server/`, never reverse
2. Lazy imports in `cognitive_memory/__init__.py`
3. ATDD Tests: `tests/library/test_imports.py` (10 tests)

**Verification:**
```bash
pytest tests/library/test_imports.py -v
```

### R-002: Connection Pool Exhaustion (Score: 6)

**Risk:** Concurrent Access erschöpft Connection Pool

**Mitigation:**
1. Pool-Size Limit: Default 10 connections
2. Connection Timeout: 30s
3. Graceful Degradation: `ConnectionError` statt Hang
4. ATDD Tests: `tests/library/test_connection_pool.py` (7 tests)

**Verification:**
```bash
pytest tests/library/test_connection_pool.py -v
```

### R-003: API Divergence (Score: 6)

**Risk:** Library liefert andere Ergebnisse als MCP Tools

**Mitigation:**
1. Wrapper Pattern: Library nutzt `mcp_server/` direkt, keine Duplizierung
2. Contract Tests: Vergleich Library vs MCP Results
3. ATDD Tests: `tests/library/test_contract.py` (10 tests)

**Verification:**
```bash
pytest tests/library/test_contract.py -v
```

---

## ATDD Test Status

### Current Status: RED Phase (All Tests Fail)

```
tests/library/
├─ test_imports.py         10 tests (ModuleNotFoundError)
├─ test_memory_store.py    13 tests (ModuleNotFoundError)
├─ test_search.py          14 tests (ModuleNotFoundError)
├─ test_store_insight.py   11 tests (ModuleNotFoundError)
├─ test_connection_pool.py  7 tests (ModuleNotFoundError)
└─ test_contract.py        10 tests (ModuleNotFoundError)
                           ─────────
                           56 tests total (all failing)
```

### Run Tests
```bash
# All library tests
pytest tests/library/ -v --tb=short

# Specific story tests
pytest tests/library/test_imports.py -v          # Story 5.1
pytest tests/library/test_memory_store.py -v     # Story 5.2
pytest tests/library/test_search.py -v           # Story 5.3
pytest tests/library/test_store_insight.py -v    # Story 5.4
```

### TDD Workflow
1. **RED**: All 56 tests fail (current state)
2. **GREEN**: Implement minimal code to pass each test
3. **REFACTOR**: Clean up while keeping tests green

---

## Implementation Order

### Story 5.1: Core Library Package Setup (Foundation)
1. Create `cognitive_memory/` directory
2. Create `cognitive_memory/__init__.py` with exports
3. Create `cognitive_memory/exceptions.py`
4. Create `cognitive_memory/models.py` (dataclasses)
5. Update `pyproject.toml` to include package
6. Run `test_imports.py` → GREEN

### Story 5.2: MemoryStore Core Class
1. Create `cognitive_memory/store.py`
2. Implement `MemoryStore.__init__(connection_string)`
3. Implement `MemoryStore.from_env()`
4. Implement context manager (`__enter__`, `__exit__`)
5. Implement lazy connection via `mcp_server/db/connection.py`
6. Run `test_memory_store.py` → GREEN

### Story 5.3: Hybrid Search Library API
1. Implement `MemoryStore.search()`
2. Import from `mcp_server/tools/hybrid_search.py`
3. Import from `mcp_server/external/openai_client.py`
4. Return `list[SearchResult]`
5. Run `test_search.py` → GREEN

### Story 5.4: L2 Insight Storage Library API
1. Implement `MemoryStore.store_insight()`
2. Import from `mcp_server/tools/compress_to_l2_insight.py`
3. Return `InsightResult`
4. Run `test_store_insight.py` → GREEN

### Stories 5.5-5.7: Sub-modules
- Working Memory → `cognitive_memory/working.py`
- Episode Memory → `cognitive_memory/episode.py`
- Graph Store → `cognitive_memory/graph.py`

### Story 5.8: Documentation
- API Reference in `docs/library-api.md`
- Usage examples
- Migration guide for ecosystem projects

---

## Existing Code to Wrap

### MCP Server Tools (Import Targets)

| Library Method | MCP Tool File | Function to Import |
|----------------|---------------|-------------------|
| `store.search()` | `mcp_server/tools/hybrid_search.py` | `semantic_search`, `keyword_search`, `rrf_fusion` |
| `store.store_insight()` | `mcp_server/tools/compress_to_l2_insight.py` | `execute_compress_to_l2` |
| `store.working.add()` | `mcp_server/tools/update_working_memory.py` | `execute_update_working_memory` |
| `store.episode.store()` | `mcp_server/tools/store_episode.py` | `execute_store_episode` |
| `store.graph.query_neighbors()` | `mcp_server/tools/graph_query_neighbors.py` | `execute_graph_query_neighbors` |

### Shared Infrastructure

| Component | File | Usage |
|-----------|------|-------|
| Connection Pool | `mcp_server/db/connection.py` | `get_connection()` |
| Embedding | `mcp_server/external/openai_client.py` | `get_embedding_with_retry()` |
| RRF Fusion | `mcp_server/utils/rrf_fusion.py` | `rrf_fusion()` |

---

## Success Criteria

### Per-Story Criteria
- All ATDD tests for story pass (GREEN)
- No import cycles introduced
- No code duplication with mcp_server

### Epic Completion Criteria
- All 56 ATDD tests pass
- P0 tests: 100% pass rate (15 tests)
- P1 tests: ≥95% pass rate (21 tests)
- Contract tests verify Library = MCP behavior
- Documentation complete (Story 5.8)

### Quality Gates
- [ ] All imports work: `from cognitive_memory import MemoryStore`
- [ ] Connection pool handles 5 concurrent queries
- [ ] `store.search()` matches `hybrid_search` MCP tool results
- [ ] `store.store_insight()` generates embeddings correctly
- [ ] All dataclasses serialize/deserialize correctly

---

## Related Documents

- **PRD:** `bmad-docs/PRD.md`
- **Epic Definition:** `bmad-docs/epics.md` (Epic 5 section)
- **Architecture:** `bmad-docs/architecture.md` (ADR-007, Epic 5 Architecture section)
- **Test Design:** `bmad-docs/test-design-epic-5.md`
- **ATDD Checklist:** `bmad-docs/atdd-checklist-epic-5.md`
- **Tests:** `tests/library/`

---

_Generated by: epic-tech-context workflow_
_Project: cognitive-memory v3.3.0-LibraryAPI_
