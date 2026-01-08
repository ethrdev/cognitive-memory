# Test Design: Epic 5 - Library API for Ecosystem Integration

**Date:** 2025-11-30
**Author:** ethr (erstellt von TEA Agent Murat)
**Status:** Draft

---

## Executive Summary

**Scope:** Full Test Design für Epic 5 (Library API)

**Risk Summary:**
- Total risks identified: 8
- High-priority risks (≥6): 3
- Critical categories: TECH (3), DATA (2), PERF (1), OPS (2)

**Coverage Summary:**
- P0 scenarios: 15 tests (30 hours)
- P1 scenarios: 21 tests (21 hours)
- P2/P3 scenarios: 22 tests (11 hours)
- **Total effort**: 62 hours (~8 Tage)

---

## Risk Assessment

### High-Priority Risks (Score ≥6)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner | Timeline |
|---------|----------|-------------|-------------|--------|-------|------------|-------|----------|
| R-001 | TECH | Import-Zyklus zwischen `cognitive_memory/` und `mcp_server/` - gegenseitige Abhängigkeit kann zu `ImportError` führen | 2 | 3 | **6** | Lazy Imports in `__init__.py`, klare Dependency Direction (cognitive_memory → mcp_server, nie umgekehrt), Unit Tests für Import-Chain | DEV | Story 5.1 |
| R-002 | DATA | Shared Connection Pool Exhaustion bei Concurrent Access - wenn mehrere Ecosystem-Projekte gleichzeitig auf DB zugreifen | 2 | 3 | **6** | Pool-Size Limits (default: 10), Connection Timeout (30s), Graceful Degradation bei Pool-Erschöpfung | DEV | Story 5.2 |
| R-003 | TECH | API-Divergenz zwischen Library und MCP (unterschiedliches Verhalten) - Library könnte andere Ergebnisse liefern als MCP Tool | 2 | 3 | **6** | Contract Tests zwischen Library und MCP, Shared Code (kein Duplizieren), Integration Tests mit gleichen Test-Daten | QA | Story 5.3-5.7 |

### Medium-Priority Risks (Score 3-4)

| Risk ID | Category | Description | Probability | Impact | Score | Mitigation | Owner |
|---------|----------|-------------|-------------|--------|-------|------------|-------|
| R-004 | PERF | OpenAI Embedding API Latenz blockiert synchrone Calls - kann bis zu 2-5s dauern | 2 | 2 | **4** | Retry mit Exponential Backoff (bereits in mcp_server), Embedding-Caching für wiederholte Queries (optional), Timeout-Dokumentation | DEV |
| R-005 | OPS | Package Installation Konflikte (`pyproject.toml` Erweiterung) - Poetry könnte Probleme mit zwei Packages haben | 1 | 3 | **3** | Poetry Install Tests in CI, Separate Test-Umgebung, Installation Guide | DEV |
| R-006 | DATA | Environment-Variable `DATABASE_URL` fehlt im Ecosystem-Projekt - Ecosystem-Projekt vergisst Config | 2 | 2 | **4** | Klare Error Messages mit Hinweis, `from_env()` Factory mit hilfreicher Exception, Dokumentation der Required Env Vars | DEV |

### Low-Priority Risks (Score 1-2)

| Risk ID | Category | Description | Probability | Impact | Score | Action |
|---------|----------|-------------|-------------|--------|-------|--------|
| R-007 | BUS | Fehlende Dokumentation führt zu falscher Nutzung | 1 | 2 | **2** | Story 5.8 (Documentation) liefert API Reference, Examples, Migration Guide |
| R-008 | OPS | Type Hints inkonsistent mit MCP Server | 1 | 1 | **1** | mypy CI Check, Type Stubs falls nötig |

### Risk Category Legend

- **TECH**: Technical/Architecture (Import-Zyklen, Wrapper-Fehler, API-Divergenz)
- **SEC**: Security (nicht kritisch für Epic 5 - interne Library)
- **PERF**: Performance (API-Latenz, Connection Pool)
- **DATA**: Data Integrity (Connection Pool, DB State)
- **BUS**: Business Impact (Dokumentation, UX)
- **OPS**: Operations (Installation, Type Hints)

---

## Test Coverage Plan

### Test Level Distribution

| Level | Beschreibung | Anteil | Begründung |
|-------|--------------|--------|------------|
| **Unit** | Dataclasses, Exceptions, Validation, Imports | 40% | Isolierte Logik, schnelles Feedback |
| **Integration** | Library ↔ PostgreSQL, Wrapper ↔ mcp_server | 50% | Kritische Interaktion mit Dependency |
| **E2E** | Nicht anwendbar | 0% | Keine UI, keine REST API |
| **Contract** | API-Stabilität, Ecosystem-Kompatibilität | 10% | Verhindert Breaking Changes |

### P0 (Critical) - Run on every commit

**Criteria**: Blocks core functionality + High risk (≥6) + No workaround

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|------------|-----------|------------|-------|-------|
| **Import Test**: `from cognitive_memory import MemoryStore` | Unit | R-001 | 1 | DEV | Verifiziert keine Import-Zyklen |
| **Import All**: Alle Public Exports importierbar | Unit | R-001 | 1 | DEV | SearchResult, InsightResult, etc. |
| **MemoryStore Instantiation**: Connection String + from_env | Unit | R-002 | 2 | DEV | Graceful Error bei fehlender DB |
| **search() Basic**: Query mit Ergebnissen | Integration | R-003 | 2 | QA | Vergleich mit MCP hybrid_search |
| **search() Empty**: Query ohne Ergebnisse | Integration | R-003 | 1 | QA | Leere Liste, keine Exception |
| **search() Weights**: Custom Weights funktionieren | Integration | R-003 | 2 | QA | 80/20, 60/40 etc. |
| **store_insight() Basic**: Content + Source IDs | Integration | R-003 | 2 | QA | Embedding wird generiert |
| **store_insight() Fidelity**: Score wird berechnet | Integration | R-003 | 2 | QA | Fidelity Score > 0 |
| **Connection Pool**: Concurrent Access | Integration | R-002 | 2 | QA | 5 gleichzeitige Queries |
| **Connection Pool**: Exhaustion Graceful | Integration | R-002 | 1 | QA | Exception statt Hang |

**Total P0**: 15 tests, **30 hours** (2h/test average für komplexe Integration)

### P1 (High) - Run on PR to main

**Criteria**: Important features + Medium risk (3-4) + Common workflows

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|------------|-----------|------------|-------|-------|
| **working.add() Basic**: Content + Importance | Integration | R-003 | 2 | QA | WorkingMemoryResult returned |
| **working.add() Eviction**: LRU Eviction bei >10 Items | Integration | R-003 | 2 | QA | evicted_id nicht None |
| **episode.store() Basic**: Query + Reward + Reflection | Integration | R-003 | 2 | QA | EpisodeResult returned |
| **episode.store() Validation**: Reward Range | Integration | R-003 | 2 | QA | ValidationError bei reward > 1 |
| **graph.query_neighbors() Basic**: Single Hop | Integration | R-003 | 2 | QA | Liste von GraphNode |
| **graph.query_neighbors() Multi-Hop**: depth=3 | Integration | R-003 | 1 | QA | Performance akzeptabel |
| **Context Manager**: with MemoryStore() as store | Unit | - | 2 | DEV | __enter__, __exit__ |
| **Exceptions**: CognitiveMemoryError Hierarchy | Unit | R-006 | 3 | DEV | ConnectionError, SearchError, etc. |
| **Error Messages**: Helpful Error bei fehlender DB | Unit | R-006 | 2 | DEV | Hinweis auf DATABASE_URL |
| **Dataclasses**: SearchResult Serialization | Unit | - | 2 | DEV | to_dict, from_dict |
| **Dataclasses**: Optional Fields | Unit | - | 1 | DEV | None Handling |

**Total P1**: 21 tests, **21 hours** (1h/test average)

### P2 (Medium) - Run nightly/weekly

**Criteria**: Secondary features + Low risk (1-2) + Edge cases

| Requirement | Test Level | Risk Link | Test Count | Owner | Notes |
|-------------|------------|-----------|------------|-------|-------|
| **graph.add_node() Basic**: Label + Name | Integration | - | 2 | QA | NodeResult returned |
| **graph.add_node() Idempotent**: Duplicate safe | Integration | - | 1 | QA | Kein Error bei Duplicate |
| **graph.add_edge() Basic**: Source + Target + Relation | Integration | - | 1 | QA | EdgeResult returned |
| **episode.search()**: Query-basierte Suche | Integration | - | 2 | QA | Ähnliche Episodes |
| **episode.list()**: Limit Parameter | Integration | - | 1 | QA | Max N Ergebnisse |
| **working.list()**: Alle Items | Integration | - | 1 | QA | Liste von WorkingMemoryItem |
| **working.clear()**: Reset | Integration | - | 1 | QA | Count returned |
| **working.get()**: By ID | Integration | - | 1 | QA | Item oder None |
| **Edge Case**: Empty query string | Unit | - | 2 | DEV | ValidationError |
| **Edge Case**: Very long content | Unit | - | 1 | DEV | Kein Truncation Error |
| **Edge Case**: Special characters in query | Unit | - | 2 | DEV | SQL-safe |
| **Edge Case**: Negative importance | Unit | - | 1 | DEV | ValidationError |
| **Edge Case**: Invalid source_ids | Unit | - | 2 | DEV | Graceful handling |

**Total P2**: 18 tests, **9 hours** (0.5h/test average)

### P3 (Low) - Run on-demand

**Criteria**: Nice-to-have + Exploratory + Performance benchmarks

| Requirement | Test Level | Test Count | Owner | Notes |
|-------------|------------|------------|-------|-------|
| **Performance**: search() Latency (<2s p95) | Integration | 1 | QA | Benchmark mit 100 Queries |
| **Performance**: store_insight() Latency (<3s p95) | Integration | 1 | QA | Inkl. Embedding |
| **Type Hints**: mypy --strict compliance | Static | 1 | DEV | CI Check |
| **Memory Usage**: No leaks unter Last | Integration | 1 | QA | 1000 Operations |

**Total P3**: 4 tests, **2 hours**

---

## Execution Order

### Smoke Tests (<3 min)

**Purpose**: Fast feedback, catch build-breaking issues

- [ ] Import Test: `from cognitive_memory import MemoryStore` (5s)
- [ ] MemoryStore Instantiation with from_env() (10s)
- [ ] search() Basic Query (30s)

**Total**: 3 scenarios, ~1 min

### P0 Tests (<15 min)

**Purpose**: Critical path validation

- [ ] All Import Tests (Unit)
- [ ] MemoryStore Connection Tests (Unit/Integration)
- [ ] search() Full Suite (Integration)
- [ ] store_insight() Full Suite (Integration)
- [ ] Connection Pool Tests (Integration)

**Total**: 15 scenarios, ~10-15 min

### P1 Tests (<30 min)

**Purpose**: Important feature coverage

- [ ] Working Memory Suite (Integration)
- [ ] Episode Memory Suite (Integration)
- [ ] Graph Query Suite (Integration)
- [ ] Exception Handling Suite (Unit)
- [ ] Dataclass Tests (Unit)

**Total**: 21 scenarios, ~20-30 min

### P2/P3 Tests (<45 min)

**Purpose**: Full regression coverage

- [ ] Graph Add Operations (Integration)
- [ ] Episode Search/List (Integration)
- [ ] Working Memory Operations (Integration)
- [ ] Edge Cases (Unit)
- [ ] Performance Benchmarks (Integration)

**Total**: 22 scenarios, ~30-45 min

---

## Resource Estimates

### Test Development Effort

| Priority | Count | Hours/Test | Total Hours | Notes |
|----------|-------|------------|-------------|-------|
| P0 | 15 | 2.0 | 30 | Complex Integration, Mocking |
| P1 | 21 | 1.0 | 21 | Standard Coverage |
| P2 | 18 | 0.5 | 9 | Simple Scenarios |
| P3 | 4 | 0.5 | 2 | Benchmarks, Static |
| **Total** | **58** | **-** | **62** | **~8 Tage** |

### Prerequisites

**Test Data:**
- `test_insight_factory` - Generiert L2 Insights mit Embeddings
- `test_episode_factory` - Generiert Episodes mit Reward/Reflection
- `test_graph_factory` - Generiert Nodes und Edges
- `test_working_memory_fixture` - Pre-populated Working Memory

**Tooling:**
- **pytest** für Test Runner
- **pytest-mock** für Mocking (OpenAI API, DB)
- **pytest-postgresql** für Integration Tests (Test-DB)
- **mypy** für Type Checking

**Environment:**
- PostgreSQL + pgvector (lokal oder Docker)
- OpenAI API Key (für echte Embedding Tests) ODER Mock
- `DATABASE_URL` Environment Variable

### Mock Strategy

```python
# tests/conftest.py
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_openai_embedding():
    """Mock OpenAI Embedding API für schnelle Unit Tests."""
    with patch('mcp_server.external.openai_client.get_embedding_with_retry') as mock:
        mock.return_value = [0.1] * 1536  # Fake 1536-dim Embedding
        yield mock

@pytest.fixture
def mock_db_connection():
    """Mock DB Connection für isolierte Unit Tests."""
    with patch('mcp_server.db.connection.get_connection') as mock:
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = MagicMock()
        mock.return_value = mock_conn
        yield mock_conn

@pytest.fixture
def real_db_connection():
    """Echte DB Connection für Integration Tests."""
    import os
    conn_string = os.environ.get('TEST_DATABASE_URL', 'postgresql://test:test@localhost/cognitive_memory_test')
    # Setup Test-DB, yield, Cleanup
    ...
```

---

## Quality Gate Criteria

### Pass/Fail Thresholds

- **P0 pass rate**: 100% (no exceptions)
- **P1 pass rate**: ≥95% (waivers required for failures)
- **P2/P3 pass rate**: ≥90% (informational)
- **High-risk mitigations**: 100% complete or approved waivers

### Coverage Targets

- **Critical paths (search, store_insight)**: ≥90%
- **Wrapper Methods**: ≥80%
- **Edge Cases**: ≥60%
- **Dataclasses**: 100%

### Non-Negotiable Requirements

- [ ] All P0 tests pass
- [ ] No high-risk (≥6) items unmitigated
- [ ] Import Tests pass (R-001 mitigated)
- [ ] Connection Pool Tests pass (R-002 mitigated)
- [ ] Contract Tests pass (R-003 mitigated)

---

## Mitigation Plans

### R-001: Import-Zyklus (Score: 6)

**Mitigation Strategy:**
1. `cognitive_memory/__init__.py` nutzt Lazy Imports für Sub-Module
2. Dependency Direction: `cognitive_memory/` → `mcp_server/`, nie umgekehrt
3. Unit Test: Import-Chain Test in P0

**Owner:** DEV
**Timeline:** Story 5.1
**Status:** Planned
**Verification:** Import Test im P0 Test Suite

```python
# tests/unit/test_imports.py
def test_import_memory_store():
    """Verifiziert keine Import-Zyklen."""
    from cognitive_memory import MemoryStore
    assert MemoryStore is not None

def test_import_all_exports():
    """Alle Public Exports importierbar."""
    from cognitive_memory import (
        MemoryStore,
        WorkingMemory,
        EpisodeMemory,
        GraphStore,
        SearchResult,
        InsightResult,
        CognitiveMemoryError,
    )
```

### R-002: Connection Pool Exhaustion (Score: 6)

**Mitigation Strategy:**
1. Pool-Size Limit: Default 10 Connections
2. Connection Timeout: 30s
3. Graceful Degradation: `ConnectionError` statt Hang
4. Integration Test: Concurrent Access Test

**Owner:** DEV
**Timeline:** Story 5.2
**Status:** Planned
**Verification:** Connection Pool Tests im P0 Test Suite

```python
# tests/integration/test_connection_pool.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

def test_concurrent_access():
    """5 gleichzeitige Queries sollten funktionieren."""
    store = MemoryStore.from_env()

    def query():
        return store.search("test query")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(query) for _ in range(5)]
        results = [f.result(timeout=30) for f in futures]

    assert all(isinstance(r, list) for r in results)
```

### R-003: API-Divergenz (Score: 6)

**Mitigation Strategy:**
1. Shared Code: Library nutzt `mcp_server/tools/` direkt, keine Duplizierung
2. Contract Tests: Gleiche Test-Daten für Library und MCP
3. Integration Tests: Vergleich Library-Result mit MCP-Result

**Owner:** QA
**Timeline:** Stories 5.3-5.7
**Status:** Planned
**Verification:** Contract Tests

```python
# tests/contract/test_api_consistency.py
def test_search_consistency():
    """Library search() liefert gleiche Ergebnisse wie MCP hybrid_search."""
    # Setup: Gleiche Test-Daten
    query = "test query"

    # Library Result
    store = MemoryStore.from_env()
    library_results = store.search(query, top_k=5)

    # MCP Result (via direct function call)
    from mcp_server.tools.hybrid_search import hybrid_search
    mcp_results = hybrid_search(query, top_k=5)

    # Compare
    assert len(library_results) == len(mcp_results)
    for lib_r, mcp_r in zip(library_results, mcp_results):
        assert lib_r.id == mcp_r['id']
        assert abs(lib_r.score - mcp_r['score']) < 0.001
```

---

## Assumptions and Dependencies

### Assumptions

1. PostgreSQL + pgvector läuft lokal oder in Docker für Tests
2. OpenAI API Key ist verfügbar (oder Mock für Unit Tests)
3. `mcp_server/` Code ist stabil und getestet
4. Test-Daten können via DB Fixtures erstellt werden

### Dependencies

1. **Story 5.1 (Package Setup)** - Required by alle anderen Stories
2. **Story 5.2 (MemoryStore Core)** - Required by Stories 5.3-5.7
3. **pytest + pytest-mock** - Required für Test-Ausführung
4. **Test-DB** - Required für Integration Tests

### Risks to Plan

- **Risk**: OpenAI API nicht verfügbar während Tests
  - **Impact**: Integration Tests schlagen fehl
  - **Contingency**: Mock-Modus für CI, echte API nur lokal

- **Risk**: Test-DB nicht korrekt initialisiert
  - **Impact**: Alle Integration Tests schlagen fehl
  - **Contingency**: pytest-postgresql für automatische Setup/Teardown

---

## Test File Structure

```
tests/
├── unit/
│   ├── test_imports.py          # R-001: Import-Chain Tests
│   ├── test_dataclasses.py      # SearchResult, InsightResult, etc.
│   ├── test_exceptions.py       # Exception Hierarchy
│   ├── test_validation.py       # Input Validation
│   └── test_context_manager.py  # with MemoryStore()
├── integration/
│   ├── conftest.py              # Fixtures, Mock-Setup
│   ├── test_search.py           # store.search() Tests
│   ├── test_store_insight.py    # store.store_insight() Tests
│   ├── test_working_memory.py   # store.working.* Tests
│   ├── test_episode_memory.py   # store.episode.* Tests
│   ├── test_graph.py            # store.graph.* Tests
│   └── test_connection_pool.py  # R-002: Concurrent Access
├── contract/
│   └── test_api_consistency.py  # R-003: Library vs MCP
└── performance/
    └── test_benchmarks.py       # P3: Latency, Memory
```

---

## Approval

**Test Design Approved By:**

- [ ] Product Manager: _______________ Date: _______________
- [ ] Tech Lead: _______________ Date: _______________
- [ ] QA Lead: _______________ Date: _______________

**Comments:**

---

## Appendix

### Knowledge Base References

- `risk-governance.md` - Risk classification framework
- `probability-impact.md` - Risk scoring methodology
- `test-levels-framework.md` - Test level selection
- `test-priorities-matrix.md` - P0-P3 prioritization

### Related Documents

- PRD: `bmad-docs/PRD.md`
- Epic: `bmad-docs/epics.md` (Epic 5)
- Architecture: `bmad-docs/architecture.md` (Epic 5 Section)

---

**Generated by**: BMad TEA Agent - Test Architect Module (Murat)
**Workflow**: `bmad/bmm/testarch/test-design`
**Version**: 4.0 (BMad v6)
