# Story 6.6: Integration Tests für Verification Workflow

Status: done

## Story

Als Entwickler,
möchte ich Integration Tests für den Write-then-Verify Workflow,
sodass die Verification-Endpoints in der Praxis funktionieren.

## Acceptance Criteria

### AC-6.6.1: Write-then-Verify Node Test

**Given** alle Graph-Verification-Tools sind implementiert (Stories 6.1, 6.3)
**When** ich den Integration Test ausführe
**Then** verifiziert der Test:

1. `graph_add_node(label, name)` → erhalte `node_id`
2. `get_node_by_name(name)` → verifiziere identische `node_id`
3. Cleanup: Test-Node löschen

### AC-6.6.2: Write-then-Verify Edge Test

**Given** alle Edge-Verification-Tools sind implementiert (Stories 6.1, 6.2)
**When** ich den Integration Test ausführe
**Then** verifiziert der Test:

1. Erstelle Source-Node: `graph_add_node(label, source_name)`
2. Erstelle Target-Node: `graph_add_node(label, target_name)`
3. `graph_add_edge(source, target, relation)` → erhalte `edge_id`
4. `get_edge(source, target, relation)` → verifiziere identische `edge_id`
5. Cleanup: Edges VOR Nodes löschen (FK-Constraint!)

### AC-6.6.3: Count Sanity Check Test

**Given** `count_by_type` Tool ist implementiert (Story 6.3)
**When** ich den Integration Test ausführe
**Then** verifiziert der Test:

1. `count_by_type()` → initialer Count (baseline)
2. Insert Test-Daten (Node + Edge)
3. `count_by_type()` → verifiziere Counts erhöht
4. Cleanup: Test-Daten löschen
5. `count_by_type()` → verifiziere Counts zurück auf baseline

### AC-6.6.4: List-Episodes-then-Verify Test

**Given** `list_episodes` und `store_episode` sind implementiert (Stories 1.8, 6.4)
**When** ich den Integration Test ausführe
**Then** verifiziert der Test:

1. `list_episodes()` → initialer Count
2. `store_episode(query, reward, reflection)` → erhalte `id`
3. `list_episodes()` → verifiziere Count erhöht + Episode enthalten
4. Cleanup: Episode löschen

**WICHTIG:** Dieser Test benötigt `OPENAI_API_KEY` (Embedding-Generierung). Test skippt wenn nicht konfiguriert.

### AC-6.6.5: Get-Insight-by-ID-then-Verify Test

**Given** `compress_to_l2_insight` und `get_insight_by_id` sind implementiert (Stories 1.5, 6.5)
**When** ich den Integration Test ausführe
**Then** verifiziert der Test:

1. `compress_to_l2_insight(content, source_ids)` → erhalte `id`
2. `get_insight_by_id(id)` → verifiziere Content und source_ids stimmen
3. Cleanup: Insight löschen

**WICHTIG:** Dieser Test benötigt `OPENAI_API_KEY` (Embedding-Generierung). Test skippt wenn nicht konfiguriert.

### AC-6.6.6: Complete Verification Workflow Test

**Given** ALLE Verification-Tools sind implementiert (Stories 6.1-6.5)
**When** ich einen vollständigen End-to-End Test ausführe
**Then** demonstriert der Test das komplette I/O Agent Verification Pattern:

1. **Phase 1: Data Creation** (Graph-only, kein API-Call)
   - Erstelle Graph-Node 1
   - Erstelle Graph-Node 2
   - Erstelle Edge zwischen Nodes

2. **Phase 2: Verification**
   - `get_node_by_name` → Node 1 verifizieren
   - `get_node_by_name` → Node 2 verifizieren
   - `get_edge` → Edge verifizieren
   - `count_by_type` → Graph-Counts korrekt

3. **Phase 3: Cleanup**
   - Edges VOR Nodes löschen (FK-Constraint!)
   - Counts wieder auf Baseline

## Tasks / Subtasks

### Task 1: Test-Datei Setup (AC: alle)

- [x] Subtask 1.1: Erstelle `tests/test_verification_endpoints.py`
  ```python
  """
  Integration Tests for Verification Workflow

  Tests the Write-then-Verify pattern across all Epic 6 tools:
  - get_node_by_name (Story 6.1)
  - get_edge (Story 6.2)
  - count_by_type (Story 6.3)
  - list_episodes (Story 6.4)
  - get_insight_by_id (Story 6.5)

  Story 6.6: Integration Tests für Verification Workflow

  IMPORTANT: Tests marked with @pytest.mark.integration require:
  - DATABASE_URL in .env.development
  - OPENAI_API_KEY for episode/insight tests (will skip if not configured)
  """

  from __future__ import annotations

  import os
  import uuid

  import pytest
  from dotenv import load_dotenv

  # Load environment FIRST
  load_dotenv(".env.development")

  # Tool Handler Imports (from specific modules for consistency)
  from mcp_server.tools.graph_add_node import handle_graph_add_node
  from mcp_server.tools.graph_add_edge import handle_graph_add_edge
  from mcp_server.tools.get_node_by_name import handle_get_node_by_name
  from mcp_server.tools.get_edge import handle_get_edge
  from mcp_server.tools.count_by_type import handle_count_by_type
  from mcp_server.tools.list_episodes import handle_list_episodes
  from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id

  # These are defined in __init__.py, import from package
  from mcp_server.tools import handle_store_episode, handle_compress_to_l2_insight

  from mcp_server.db.connection import get_connection
  ```

- [x] Subtask 1.2: Skip-Fixtures für fehlende Konfiguration
  ```python
  @pytest.fixture
  def require_database():
      """Skip test if DATABASE_URL not configured."""
      if not os.getenv("DATABASE_URL"):
          pytest.skip("DATABASE_URL not configured - skipping integration test")

  @pytest.fixture
  def require_openai():
      """Skip test if OPENAI_API_KEY not configured."""
      api_key = os.getenv("OPENAI_API_KEY")
      if not api_key or api_key == "sk-your-openai-api-key-here":
          pytest.skip("OPENAI_API_KEY not configured - skipping API-dependent test")
  ```

### Task 2: Write-then-Verify Node Test (AC: 6.6.1)

- [x] Subtask 2.1: Implementiere `test_write_then_verify_node()`
  ```python
  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_write_then_verify_node(require_database):
      """Test Write-then-Verify pattern for graph nodes."""
      test_name = f"TestNode_{uuid.uuid4().hex[:8]}"
      created_node_id = None

      try:
          # WRITE: Create node
          result = await handle_graph_add_node({
              "label": "TestLabel",
              "name": test_name
          })
          assert result["status"] == "success"
          assert result["created"] is True
          created_node_id = result["node_id"]

          # VERIFY: Get node by name
          verify = await handle_get_node_by_name({"name": test_name})
          assert verify["status"] == "success"
          assert verify["node_id"] == created_node_id
          assert verify["name"] == test_name

      finally:
          # CLEANUP
          if created_node_id:
              with get_connection() as conn:
                  with conn.cursor() as cur:
                      cur.execute("DELETE FROM nodes WHERE id = %s", (created_node_id,))
                  conn.commit()
  ```

### Task 3: Write-then-Verify Edge Test (AC: 6.6.2)

- [x] Subtask 3.1: Implementiere `test_write_then_verify_edge()`
  ```python
  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_write_then_verify_edge(require_database):
      """Test Write-then-Verify pattern for graph edges."""
      source_name = f"SourceNode_{uuid.uuid4().hex[:8]}"
      target_name = f"TargetNode_{uuid.uuid4().hex[:8]}"
      source_id = None
      target_id = None

      try:
          # Create source node
          source_result = await handle_graph_add_node({
              "label": "Test", "name": source_name
          })
          source_id = source_result["node_id"]

          # Create target node
          target_result = await handle_graph_add_node({
              "label": "Test", "name": target_name
          })
          target_id = target_result["node_id"]

          # WRITE: Create edge
          edge_result = await handle_graph_add_edge({
              "source_name": source_name,
              "target_name": target_name,
              "relation": "TEST_RELATION"
          })
          assert edge_result["status"] == "success"
          edge_id = edge_result["edge_id"]

          # VERIFY: Get edge
          verify = await handle_get_edge({
              "source_name": source_name,
              "target_name": target_name,
              "relation": "TEST_RELATION"
          })
          assert verify["status"] == "success"
          assert verify["edge_id"] == edge_id

      finally:
          # CLEANUP: Edges BEFORE nodes (FK constraint!)
          with get_connection() as conn:
              with conn.cursor() as cur:
                  if source_id and target_id:
                      cur.execute(
                          "DELETE FROM edges WHERE source_id = %s OR target_id = %s",
                          (source_id, target_id)
                      )
                  if source_id:
                      cur.execute("DELETE FROM nodes WHERE id = %s", (source_id,))
                  if target_id:
                      cur.execute("DELETE FROM nodes WHERE id = %s", (target_id,))
              conn.commit()
  ```

### Task 4: Count Sanity Check Test (AC: 6.6.3)

- [x] Subtask 4.1: Implementiere `test_count_sanity_check()`
  - Baseline Counts holen mit `handle_count_by_type({})`
  - Test-Node erstellen
  - Verifiziere `graph_nodes` erhöht um 1
  - Cleanup und verifiziere Counts zurück auf baseline

### Task 5: List-Episodes Test (AC: 6.6.4)

- [x] Subtask 5.1: Implementiere `test_list_episodes_verification()`
  ```python
  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_list_episodes_verification(require_database, require_openai):
      """Test store_episode → list_episodes verification."""
      episode_id = None

      try:
          # Get initial count
          initial = await handle_list_episodes({})
          initial_count = initial["total_count"]

          # WRITE: Store episode (CALLS OPENAI API!)
          result = await handle_store_episode({
              "query": f"Test query {uuid.uuid4().hex[:8]}",
              "reward": 0.75,
              "reflection": "Problem: Test problem. Lesson: Test lesson."
          })
          assert result["embedding_status"] == "success"
          episode_id = result["id"]  # NOTE: Field is "id", not "episode_id"!

          # VERIFY: List episodes
          after = await handle_list_episodes({})
          assert after["total_count"] == initial_count + 1

      finally:
          # CLEANUP
          if episode_id:
              with get_connection() as conn:
                  with conn.cursor() as cur:
                      cur.execute("DELETE FROM episode_memory WHERE id = %s", (episode_id,))
                  conn.commit()
  ```

### Task 6: Get-Insight-by-ID Test (AC: 6.6.5)

- [x] Subtask 6.1: Implementiere `test_get_insight_by_id_verification()`
  ```python
  @pytest.mark.integration
  @pytest.mark.asyncio
  async def test_get_insight_by_id_verification(require_database, require_openai):
      """Test compress_to_l2_insight → get_insight_by_id verification."""
      insight_id = None
      test_content = f"Test insight content {uuid.uuid4().hex[:8]}"

      try:
          # WRITE: Create insight (CALLS OPENAI API!)
          result = await handle_compress_to_l2_insight({
              "content": test_content,
              "source_ids": []  # Empty list is valid
          })
          assert result["embedding_status"] == "success"
          insight_id = result["id"]  # NOTE: Field is "id", not "insight_id"!

          # VERIFY: Get insight by ID
          verify = await handle_get_insight_by_id({"id": insight_id})
          assert verify["status"] == "success"
          assert verify["content"] == test_content
          assert verify["source_ids"] == []
          assert "embedding" not in verify  # Embedding excluded from response

      finally:
          # CLEANUP
          if insight_id:
              with get_connection() as conn:
                  with conn.cursor() as cur:
                      cur.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
                  conn.commit()
  ```

### Task 7: Complete E2E Workflow Test (AC: 6.6.6)

- [x] Subtask 7.1: Implementiere `test_complete_verification_workflow()`
  - Graph-only Test (keine OpenAI API)
  - Erstellt 2 Nodes + 1 Edge
  - Verifiziert alle mit get_node_by_name, get_edge, count_by_type
  - Vollständiges Cleanup

### Task 8: pytest Marker Configuration

- [x] Subtask 8.1: Dokumentiere pytest-Aufruf in Story-Notes
  - `pytest -m integration` für Integration Tests
  - `pytest -m "not integration"` für schnelle Unit Tests

## Dev Notes

### Story Context

Story 6.6 ist die **letzte Story von Epic 6 (Audit und Verification Endpoints)**. Sie bringt alle Verification-Tools zusammen in Integration Tests, die das Write-then-Verify Pattern für autonome Agenten validieren.

**Dependencies auf vorherige Stories (alle DONE):**
- **Story 6.1 (get_node_by_name):** done
- **Story 6.2 (get_edge):** done
- **Story 6.3 (count_by_type):** done
- **Story 6.4 (list_episodes):** done
- **Story 6.5 (get_insight_by_id):** done

### API-Dependency Warning

**KRITISCH:** `handle_store_episode` und `handle_compress_to_l2_insight` rufen die **OpenAI API** auf:
- Generieren 1536-dimensionale Embeddings
- **Kosten:** ~$0.0001 pro Call (text-embedding-3-small)
- **Latenz:** ~300-500ms pro Call
- Tests ohne `OPENAI_API_KEY` → `RuntimeError` oder Skip

**Deshalb:** AC-6.6.4 und AC-6.6.5 Tests müssen `require_openai` Fixture verwenden!

### Response Format Reference

**handle_graph_add_node:**
```python
{"status": "success", "node_id": "uuid-...", "created": True, "label": "...", "name": "..."}
```

**handle_graph_add_edge:**
```python
{"status": "success", "edge_id": "uuid-...", "created": True, ...}
```

**handle_get_node_by_name:**
```python
{"status": "success", "node_id": "uuid-...", "label": "...", "name": "...", "properties": {...}, "vector_id": null, "created_at": "..."}
# OR wenn nicht gefunden:
{"status": "not_found", "node": null}
```

**handle_get_edge:**
```python
{"status": "success", "edge_id": "uuid-...", "source_id": "...", "target_id": "...", "relation": "...", "weight": 1.0, ...}
# OR wenn nicht gefunden:
{"status": "not_found", "edge": null}
```

**handle_count_by_type:**
```python
{"graph_nodes": 47, "graph_edges": 89, "l2_insights": 234, "episodes": 86, "working_memory": 5, "raw_dialogues": 1203, "status": "success"}
```

**handle_list_episodes:**
```python
{"episodes": [...], "total_count": 86, "limit": 50, "offset": 0, "status": "success"}
```

**handle_store_episode:** (WICHTIG: "id" nicht "episode_id"!)
```python
{"id": 123, "embedding_status": "success", "query": "...", "reward": 0.8, "created_at": "..."}
```

**handle_compress_to_l2_insight:** (WICHTIG: "id" nicht "insight_id"!)
```python
{"id": 456, "embedding_status": "success", "fidelity_score": 0.85, ...}
```

**handle_get_insight_by_id:**
```python
{"status": "success", "id": 456, "content": "...", "source_ids": [...], "metadata": {...}, "created_at": "..."}
# OR wenn nicht gefunden:
{"status": "not_found", "insight": null}
```

### Critical Patterns

**1. Environment Setup:**
```python
from dotenv import load_dotenv
load_dotenv(".env.development")

if not os.getenv("DATABASE_URL"):
    pytest.skip("DATABASE_URL not configured")
```

**2. UUID für Test-Isolation:**
```python
test_name = f"TestNode_{uuid.uuid4().hex[:8]}"
```

**3. FK-Constraint beachten:** Edges VOR Nodes löschen!
```python
# RICHTIG:
cur.execute("DELETE FROM edges WHERE source_id = %s OR target_id = %s", (id, id))
cur.execute("DELETE FROM nodes WHERE id = %s", (id,))

# FALSCH (FK-Error):
cur.execute("DELETE FROM nodes WHERE id = %s", (id,))
```

**4. Cleanup in finally-Block:**
```python
created_id = None
try:
    result = await handler(...)
    created_id = result["node_id"]
    # assertions...
finally:
    if created_id:
        # cleanup SQL
```

### File Structure

```
tests/
├── test_get_node_by_name.py      # Story 6.1 (11 tests)
├── test_get_edge.py              # Story 6.2 (22 tests)
├── test_count_by_type.py         # Story 6.3 (10 tests)
├── test_list_episodes.py         # Story 6.4 (14 tests)
├── test_get_insight_by_id.py     # Story 6.5 (15 tests)
└── test_verification_endpoints.py # Story 6.6 - THIS FILE (6 tests)
```

**NEW Files:** `tests/test_verification_endpoints.py`
**NO MODIFIED Files:** Diese Story erstellt nur neue Test-Dateien

### Running the Tests

```bash
# All integration tests (requires DB + optional API)
PYTHONPATH=. pytest tests/test_verification_endpoints.py -v -m integration

# Graph-only tests (no OpenAI API needed)
PYTHONPATH=. pytest tests/test_verification_endpoints.py -v -k "node or edge or count"

# Skip integration tests entirely (fast)
PYTHONPATH=. pytest tests/test_verification_endpoints.py -v -m "not integration"
```

### References

- [Source: tests/test_get_node_by_name.py] - Integration test pattern with cleanup
- [Source: tests/test_count_by_type.py] - Count verification pattern
- [Source: mcp_server/tools/__init__.py:1631] - handle_store_episode definition
- [Source: mcp_server/tools/__init__.py:933] - handle_compress_to_l2_insight definition

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-12-06 | Story created with comprehensive developer context | Claude Opus 4.5 (create-story workflow) |
| 2025-12-07 | Quality review - added API dependency docs, response formats, skip fixtures | Bob SM (validate-create-story) |
| 2025-12-07 | Implementation complete - all 6 integration tests passing, 78 Epic 6 tests pass | Claude Opus 4.5 (dev-story workflow) |
| 2025-12-07 | Code review: 0 HIGH, 4 MED, 4 LOW issues. All MED fixed (type annotations). Story APPROVED | Claude Opus 4.5 (code-review workflow) |

## Dev Agent Record

### Context Reference

<!-- Path(s) to story context XML will be added here by context workflow -->

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Initial test run failed due to `graph_add_edge` default label behavior overwriting custom labels
- Fixed by passing explicit `source_label` and `target_label` parameters in E2E workflow test

### Completion Notes List

- Created `tests/test_verification_endpoints.py` with 6 comprehensive integration tests
- All tests implement Write-then-Verify pattern with proper cleanup in finally blocks
- Tests use UUID-based naming for isolation: `f"TestNode_{uuid.uuid4().hex[:8]}"`
- API-dependent tests (episodes, insights) use `require_openai` fixture for graceful skip
- All 78 Epic 6 tests pass (11+22+10+14+15+6)
- Discovery: `graph_add_edge` auto-upserts nodes with default label "Entity" - tests must pass explicit labels

### Review Follow-ups (AI)

**All MEDIUM issues FIXED:**
- [x] [AI-Review][MED] Added `-> Generator[None, None, None]` return type to `require_database` fixture
- [x] [AI-Review][MED] Added `-> Generator[None, None, None]` return type to `require_openai` fixture
- [x] [AI-Review][MED] Added type annotations to all 6 test functions (parameters + `-> None` return)
- [x] [AI-Review][MED] Cleaned up imports - alphabetized, removed redundant structure

**LOW issues NOT FIXED (acceptable):**
- [ ] [AI-Review][LOW] Docstring "fuer" → "für" FIXED
- [ ] [AI-Review][LOW] pytest marker registration in pyproject.toml (existing pattern)
- [ ] [AI-Review][LOW] Magic number 10 in Working Memory (not in this story's scope)
- [ ] [AI-Review][LOW] pytest marker docs in README (nice-to-have)

### File List

- `tests/test_verification_endpoints.py` (NEW) - 6 integration tests for verification workflow

---

## Code Review Summary

**Reviewer:** Claude Opus 4.5 (code-review workflow)
**Date:** 2025-12-07
**Verdict:** ✅ APPROVED

### Findings Summary

| Severity | Count | Fixed |
|----------|-------|-------|
| HIGH | 0 | - |
| MEDIUM | 4 | 4 ✅ |
| LOW | 4 | 1 |

### AC Validation: 6/6 ✅

All Acceptance Criteria implemented and verified:
- AC-6.6.1: Write-then-Verify Node Test ✅
- AC-6.6.2: Write-then-Verify Edge Test ✅
- AC-6.6.3: Count Sanity Check Test ✅
- AC-6.6.4: List-Episodes-then-Verify Test ✅
- AC-6.6.5: Get-Insight-by-ID-then-Verify Test ✅
- AC-6.6.6: Complete Verification Workflow Test ✅

### Test Results

```
tests/test_verification_endpoints.py ......  [100%]
6 passed in 7.51s

All 78 Epic 6 tests: PASS
```
