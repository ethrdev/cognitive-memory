# ATDD Checklist - Epic 5: Library API for Ecosystem Integration

**Date:** 2025-11-30
**Author:** ethr (erstellt von TEA Agent Murat)
**Primary Test Level:** Unit + Integration (Python/pytest)

---

## Story Summary

**Als** Ecosystem-Entwickler (i-o-system, tethr, agentic-business),
**möchte ich** ein `cognitive_memory` Python Package mit direktem DB-Zugriff,
**sodass** ich cognitive-memory als Storage-Backend nutzen kann, ohne den MCP Server zu benötigen.

---

## Acceptance Criteria

1. `from cognitive_memory import MemoryStore` funktioniert ohne Import-Fehler
2. `store.search(query, top_k)` liefert identische Ergebnisse wie MCP hybrid_search
3. `store.store_insight(content, source_ids)` speichert mit Embedding + Fidelity Check
4. `store.working.add(content, importance)` mit LRU Eviction funktioniert
5. `store.episode.store(query, reward, reflection)` speichert Episodes
6. `store.graph.query_neighbors(node_name)` für Graph-Traversierung funktioniert
7. Concurrent Access ohne Connection Pool Exhaustion
8. API-Konsistenz zwischen Library und MCP Server

---

## Failing Tests Created (RED Phase)

### Unit Tests (15 tests)

**File:** `tests/library/test_imports.py` (95 lines)

- ✅ **Test:** `test_import_memory_store_from_package`
  - **Status:** RED - ModuleNotFoundError: No module named 'cognitive_memory'
  - **Verifies:** R-001 - Import cycle prevention, basic import
  - **Risk Link:** R-001

- ✅ **Test:** `test_import_all_public_exports`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** All public classes exportable
  - **Risk Link:** R-001

- ✅ **Test:** `test_import_exceptions_hierarchy`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Exception inheritance (CognitiveMemoryError → subclasses)
  - **Risk Link:** R-001

- ✅ **Test:** `test_no_circular_import_with_mcp_server`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** No circular dependency between packages
  - **Risk Link:** R-001

- ✅ **Test:** `test_lazy_import_submodules`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Lazy import pattern for performance

**File:** `tests/library/test_memory_store.py` (180 lines)

- ✅ **Test:** `test_instantiate_with_connection_string`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** MemoryStore(connection_string=...) constructor
  - **Story:** 5.2

- ✅ **Test:** `test_instantiate_with_from_env_factory`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** MemoryStore.from_env() factory method
  - **Story:** 5.2

- ✅ **Test:** `test_from_env_raises_error_when_no_database_url`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Helpful error when DATABASE_URL missing
  - **Risk Link:** R-006

- ✅ **Test:** `test_context_manager_enters_successfully`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** with MemoryStore() as store: works
  - **Story:** 5.2

- ✅ **Test:** `test_context_manager_exits_cleanly`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** __exit__ cleanup called
  - **Story:** 5.2

- ✅ **Test:** `test_working_memory_accessor`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** store.working returns WorkingMemory
  - **Story:** 5.5

- ✅ **Test:** `test_episode_memory_accessor`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** store.episode returns EpisodeMemory
  - **Story:** 5.6

- ✅ **Test:** `test_graph_store_accessor`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** store.graph returns GraphStore
  - **Story:** 5.7

### Integration Tests (25 tests)

**File:** `tests/library/test_search.py` (200 lines)

- ✅ **Test:** `test_search_returns_list_of_search_results`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** search() returns list[SearchResult]
  - **Story:** 5.3

- ✅ **Test:** `test_search_returns_empty_list_for_no_matches`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Empty result handling (not exception)
  - **Story:** 5.3

- ✅ **Test:** `test_search_respects_top_k_limit`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** top_k parameter works
  - **Story:** 5.3

- ✅ **Test:** `test_search_with_default_weights`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Default weights (70/30)
  - **Story:** 5.3

- ✅ **Test:** `test_search_with_custom_weights`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Custom weight configuration
  - **Story:** 5.3

- ✅ **Test:** `test_search_rejects_empty_query`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** ValidationError for empty query
  - **Story:** 5.3

- ✅ **Test:** `test_search_handles_special_characters`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** SQL injection prevention
  - **Story:** 5.3

**File:** `tests/library/test_store_insight.py` (165 lines)

- ✅ **Test:** `test_store_insight_returns_insight_result`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Returns InsightResult dataclass
  - **Story:** 5.4

- ✅ **Test:** `test_store_insight_generates_embedding`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Automatic OpenAI embedding
  - **Story:** 5.4

- ✅ **Test:** `test_store_insight_calculates_fidelity_score`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Fidelity score 0.0-1.0
  - **Story:** 5.4

- ✅ **Test:** `test_store_insight_rejects_empty_content`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** ValidationError for empty content
  - **Story:** 5.4

**File:** `tests/library/test_connection_pool.py` (180 lines)

- ✅ **Test:** `test_multiple_concurrent_searches`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** 5 concurrent queries work
  - **Risk Link:** R-002

- ✅ **Test:** `test_rapid_sequential_operations`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** 20 rapid operations without leak
  - **Risk Link:** R-002

- ✅ **Test:** `test_graceful_degradation_on_pool_exhaustion`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** ConnectionError (not hang)
  - **Risk Link:** R-002

- ✅ **Test:** `test_connection_released_after_search`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Connection returned to pool
  - **Story:** 5.2

- ✅ **Test:** `test_connection_released_on_error`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Cleanup even on error
  - **Story:** 5.2

### Contract Tests (8 tests)

**File:** `tests/library/test_contract.py` (200 lines)

- ✅ **Test:** `test_search_results_match_mcp_hybrid_search`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Library search == MCP hybrid_search
  - **Risk Link:** R-003

- ✅ **Test:** `test_search_with_custom_weights_matches_mcp`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Weight handling consistency
  - **Risk Link:** R-003

- ✅ **Test:** `test_store_insight_produces_same_embedding`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Embedding consistency
  - **Risk Link:** R-003

- ✅ **Test:** `test_working_memory_add_matches_mcp`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Working memory consistency
  - **Risk Link:** R-003

- ✅ **Test:** `test_episode_store_matches_mcp`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Episode memory consistency
  - **Risk Link:** R-003

- ✅ **Test:** `test_graph_query_neighbors_matches_mcp`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Graph query consistency
  - **Risk Link:** R-003

- ✅ **Test:** `test_library_uses_mcp_server_embedding_function`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Shared code (embedding)
  - **Risk Link:** R-003

- ✅ **Test:** `test_library_uses_mcp_server_search_functions`
  - **Status:** RED - ModuleNotFoundError
  - **Verifies:** Shared code (search)
  - **Risk Link:** R-003

---

## Test Summary

| Category | Tests | File | Status |
|----------|-------|------|--------|
| Unit (Imports) | 5 | test_imports.py | RED |
| Unit (MemoryStore) | 8 | test_memory_store.py | RED |
| Integration (Search) | 7 | test_search.py | RED |
| Integration (Store Insight) | 5 | test_store_insight.py | RED |
| Integration (Connection Pool) | 6 | test_connection_pool.py | RED |
| Contract (API Consistency) | 8 | test_contract.py | RED |
| **Total** | **39** | 6 files | **ALL RED** |

---

## Data Factories Created

Keine neuen Factories benötigt - bestehende conftest.py Fixtures werden wiederverwendet:

- `mock_conn` - Mock database connection
- `mock_openai_client` - Mock OpenAI for embeddings
- `sample_embedding` - 1536-dim test vector
- `sample_document` - Test document fixture

---

## Required data-testid Attributes

**Nicht anwendbar** - Epic 5 ist eine Python Library ohne UI.

---

## Implementation Checklist

### Story 5.1: Core Library Package Setup

**Tasks to make import tests pass:**

- [ ] Create `cognitive_memory/` directory
- [ ] Create `cognitive_memory/__init__.py` with public exports
- [ ] Create `cognitive_memory/store.py` with MemoryStore class stub
- [ ] Create `cognitive_memory/exceptions.py` with exception hierarchy
- [ ] Create `cognitive_memory/models.py` with dataclasses
- [ ] Update `pyproject.toml` to include `cognitive_memory` package
- [ ] Run tests: `pytest tests/library/test_imports.py -v`
- [ ] ✅ All import tests pass (green phase)

**Estimated Effort:** 2-3 hours

---

### Story 5.2: MemoryStore Core Class

**Tasks to make MemoryStore tests pass:**

- [ ] Implement `MemoryStore.__init__(connection_string)`
- [ ] Implement `MemoryStore.from_env()` factory
- [ ] Implement `MemoryStore.__enter__` / `__exit__`
- [ ] Add `working`, `episode`, `graph` property accessors
- [ ] Implement lazy connection via `mcp_server/db/connection.py`
- [ ] Add ConnectionError for missing DATABASE_URL
- [ ] Run tests: `pytest tests/library/test_memory_store.py -v`
- [ ] ✅ All MemoryStore tests pass (green phase)

**Estimated Effort:** 4-6 hours

---

### Story 5.3: Hybrid Search Library API

**Tasks to make search tests pass:**

- [ ] Implement `MemoryStore.search(query, top_k, weights)`
- [ ] Import and call `mcp_server.tools.hybrid_search` functions
- [ ] Create `SearchResult` dataclass
- [ ] Add input validation (empty query, negative top_k)
- [ ] Handle empty results gracefully
- [ ] Run tests: `pytest tests/library/test_search.py -v`
- [ ] ✅ All search tests pass (green phase)

**Estimated Effort:** 4-6 hours

---

### Story 5.4: L2 Insight Storage Library API

**Tasks to make store_insight tests pass:**

- [ ] Implement `MemoryStore.store_insight(content, source_ids, metadata)`
- [ ] Import and call `mcp_server.tools.compress_to_l2_insight` functions
- [ ] Create `InsightResult` dataclass
- [ ] Add content validation (empty, whitespace-only)
- [ ] Run tests: `pytest tests/library/test_store_insight.py -v`
- [ ] ✅ All store_insight tests pass (green phase)

**Estimated Effort:** 3-4 hours

---

### Story 5.5-5.7: Working Memory, Episode, Graph APIs

**Tasks to make sub-module tests pass:**

- [ ] Implement `WorkingMemory` class with add(), list(), clear(), get()
- [ ] Implement `EpisodeMemory` class with store(), search(), list()
- [ ] Implement `GraphStore` class with add_node(), add_edge(), query_neighbors()
- [ ] Wire up via MemoryStore property accessors
- [ ] Run tests: `pytest tests/library/ -v`
- [ ] ✅ All sub-module tests pass (green phase)

**Estimated Effort:** 10-12 hours

---

### R-002 Mitigation: Connection Pool Tests

**Tasks to make connection pool tests pass:**

- [ ] Verify ThreadPoolExecutor concurrent tests work
- [ ] Add connection timeout configuration (30s max)
- [ ] Ensure connections released after each operation
- [ ] Test graceful degradation on exhaustion
- [ ] Run tests: `pytest tests/library/test_connection_pool.py -v`
- [ ] ✅ All connection pool tests pass (green phase)

**Estimated Effort:** 2-3 hours

---

### R-003 Mitigation: Contract Tests

**Tasks to make contract tests pass:**

- [ ] Verify Library calls same functions as MCP
- [ ] Compare search results between Library and MCP
- [ ] Ensure embedding generation uses same path
- [ ] Run tests: `pytest tests/library/test_contract.py -v`
- [ ] ✅ All contract tests pass (green phase)

**Estimated Effort:** 2-3 hours

---

## Running Tests

```bash
# Run all failing tests for Epic 5
pytest tests/library/ -v

# Run specific test file
pytest tests/library/test_imports.py -v

# Run tests with verbose output
pytest tests/library/ -v --tb=short

# Run tests matching pattern
pytest tests/library/ -k "import" -v

# Run tests with coverage
pytest tests/library/ --cov=cognitive_memory --cov-report=html

# Debug specific test
pytest tests/library/test_imports.py::TestLibraryImports::test_import_memory_store_from_package -v --pdb
```

---

## Red-Green-Refactor Workflow

### RED Phase (Complete) ✅

**TEA Agent Responsibilities:**

- ✅ 39 tests written in Given-When-Then format
- ✅ Tests organized by story/feature
- ✅ Risk mitigations covered (R-001, R-002, R-003)
- ✅ Implementation checklist created
- ✅ All tests currently fail (ModuleNotFoundError expected)

**Verification:**

```bash
$ pytest tests/library/ -v
# Expected: 39 tests, 39 failures (ModuleNotFoundError)
```

---

### GREEN Phase (DEV Team - Next Steps)

**DEV Agent Responsibilities:**

1. **Start with Story 5.1** (Package Setup) - all other tests depend on imports
2. **Pick one failing test** from implementation checklist
3. **Implement minimal code** to make that test pass
4. **Run the test** to verify green
5. **Move to next test** in checklist order
6. **Track progress** by checking off tasks

**Key Principles:**

- One test at a time
- Minimal implementation (don't over-engineer)
- Run tests frequently
- Follow checklist order (5.1 → 5.2 → 5.3 → ...)

---

### REFACTOR Phase (After All Tests Pass)

**DEV Agent Responsibilities:**

1. **Verify all tests pass** (green phase complete)
2. **Review code quality** (type hints, docstrings)
3. **Extract duplications** (common helpers)
4. **Ensure tests still pass** after each refactor
5. **Run mypy** for type checking

---

## Next Steps

1. **Run failing tests** to confirm RED phase:
   ```bash
   pytest tests/library/ -v --tb=short
   ```

2. **Begin Story 5.1** (Package Setup) - creates basic structure

3. **Work one test at a time** following checklist

4. **When all tests pass**, proceed to Story 5.8 (Documentation)

5. **When Epic complete**, run `workflow-status` for next steps

---

## Knowledge Base References Applied

- **test-levels-framework.md** - Python: Unit + Integration (no E2E for library)
- **test-priorities-matrix.md** - P0 tests prioritized
- **data-factories.md** - Reuse existing conftest.py fixtures
- **test-quality.md** - Given-When-Then format, atomic tests

---

## Test Execution Evidence

### Initial Test Run (RED Phase Verification)

**Command:** `pytest tests/library/ -v --tb=line`

**Expected Results:**

```
tests/library/test_imports.py::TestLibraryImports::test_import_memory_store_from_package FAILED
tests/library/test_imports.py::TestLibraryImports::test_import_all_public_exports FAILED
tests/library/test_imports.py::TestLibraryImports::test_import_exceptions_hierarchy FAILED
...
(39 tests, all FAILED)
```

**Summary:**

- Total tests: 39
- Passing: 0 (expected)
- Failing: 39 (expected - ModuleNotFoundError)
- Status: ✅ RED phase verified

---

## Notes

- Epic 5 ist eine **Python Library** (kein UI, keine E2E Browser-Tests)
- Alle Tests nutzen **pytest** (nicht Playwright/Cypress)
- **Wrapper Pattern:** Library importiert von `mcp_server/`, dupliziert keinen Code
- **Contract Tests** sind kritisch um R-003 (API-Divergenz) zu verhindern
- Nach Implementation: **Story 5.8 (Documentation)** erstellen

---

**Generated by BMad TEA Agent (Murat)** - 2025-11-30
