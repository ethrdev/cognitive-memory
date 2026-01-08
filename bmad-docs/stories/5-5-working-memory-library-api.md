# Story 5.5: Working Memory Library API

Status: done

## Story

Als i-o-system Entwickler,
möchte ich `store.working.add(content, importance)` aufrufen,
sodass ich Session Context ohne MCP speichern kann.

## Acceptance Criteria

### AC-5.5.1: Working Memory Add Operation

**Given** MemoryStore ist instanziiert und verbunden
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
    current_count: int
```

### AC-5.5.2: Working Memory List Operation

**Given** MemoryStore ist instanziiert und verbunden
**When** ich `store.working.list()` aufrufe
**Then** erhalte ich eine Liste aller Working Memory Items:

- Response: `list[WorkingMemoryItem]` mit `id`, `content`, `importance`, `last_accessed`, `created_at`
- Sortiert nach `last_accessed` (neueste zuerst)

```python
@dataclass
class WorkingMemoryItem:
    id: int
    content: str
    importance: float
    last_accessed: datetime
    created_at: datetime
```

### AC-5.5.3: Working Memory Clear Operation

**Given** MemoryStore ist instanziiert und Working Memory enthält Items
**When** ich `store.working.clear()` aufrufe
**Then** werden alle Items gelöscht:

- Response: `int` (Anzahl gelöschter Items)
- Working Memory ist anschließend leer
- Kritische Items (importance >0.8) werden zu Stale Memory archiviert vor dem Löschen

### AC-5.5.4: Working Memory Get Operation

**Given** MemoryStore ist instanziiert und Working Memory enthält Items
**When** ich `store.working.get(id)` aufrufe
**Then** erhalte ich das spezifische Item:

- Response: `WorkingMemoryItem | None`
- `None` falls Item nicht existiert
- `last_accessed` wird beim Abruf aktualisiert (LRU Touch)

### AC-5.5.5: Importance Validation

**Given** MemoryStore ist instanziiert
**When** ich `store.working.add(content, importance=X)` mit ungültigem Importance aufrufe
**Then** wird `ValidationError` geworfen:

- `importance < 0.0` → `ValidationError("Importance must be >= 0.0")`
- `importance > 1.0` → `ValidationError("Importance must be <= 1.0")`

### AC-5.5.6: Wrapper Pattern Compliance (ADR-007)

**Given** WorkingMemory Implementation
**When** Code-Review durchgeführt wird
**Then** folgt Implementation dem Wrapper Pattern:

- Importiert von `mcp_server/tools/update_working_memory.py` (oder DB-Layer direkt)
- Keine Code-Duplizierung
- Shared Connection Pool mit MemoryStore
- Konsistentes Verhalten mit MCP Tool `update_working_memory`

## Tasks / Subtasks

### Task 1: WorkingMemoryItem Dataclass erstellen (AC: 5.5.2, 5.5.4)

- [ ] Subtask 1.1: Erstelle `WorkingMemoryItem` Dataclass in `cognitive_memory/types.py`
- [ ] Subtask 1.2: Felder: `id`, `content`, `importance`, `last_accessed`, `created_at`
- [ ] Subtask 1.3: Verifiziere konsistenz mit `WorkingMemoryResult` (bereits vorhanden)

### Task 2: WorkingMemory.add() implementieren (AC: 5.5.1, 5.5.5)

- [ ] Subtask 2.1: Implementiere Importance-Validierung (0.0-1.0)
- [ ] Subtask 2.2: Implementiere Insert in `working_memory` Tabelle
- [ ] Subtask 2.3: Implementiere LRU Eviction Check (max 10 Items)
- [ ] Subtask 2.4: Implementiere Stale Memory Archivierung bei Eviction (importance >0.8)
- [ ] Subtask 2.5: Return `WorkingMemoryResult` mit allen Details
- [ ] Subtask 2.6: Schreibe Tests für `add()` mit verschiedenen Szenarien

### Task 3: WorkingMemory.list() implementieren (AC: 5.5.2)

- [ ] Subtask 3.1: Implementiere `get_all()` → `list[WorkingMemoryItem]`
- [ ] Subtask 3.2: Sortierung nach `last_accessed` DESC
- [ ] Subtask 3.3: Schreibe Tests für `list()` mit verschiedenen Item-Mengen

### Task 4: WorkingMemory.clear() implementieren (AC: 5.5.3)

- [ ] Subtask 4.1: Archiviere kritische Items (importance >0.8) zu Stale Memory
- [ ] Subtask 4.2: Lösche alle Items aus `working_memory`
- [ ] Subtask 4.3: Return Anzahl gelöschter Items
- [ ] Subtask 4.4: Schreibe Tests für `clear()` mit und ohne kritische Items

### Task 5: WorkingMemory.get() implementieren (AC: 5.5.4)

- [ ] Subtask 5.1: Implementiere `get(id)` → `WorkingMemoryItem | None`
- [ ] Subtask 5.2: Aktualisiere `last_accessed` bei Abruf (LRU Touch)
- [ ] Subtask 5.3: Return `None` falls Item nicht existiert
- [ ] Subtask 5.4: Schreibe Tests für `get()` mit existierendem und nicht-existierendem Item

### Task 6: Integration mit MemoryStore.working Property (AC: 5.5.6)

- [ ] Subtask 6.1: Verifiziere lazy-initialization von `store.working`
- [ ] Subtask 6.2: Verifiziere Connection Pool Sharing mit MemoryStore
- [ ] Subtask 6.3: Schreibe Integration-Tests für `store.working.add/list/get/clear`

### Task 7: Code Quality und Tests (AC: alle)

- [ ] Subtask 7.1: Erstelle `tests/library/test_working_memory.py`
- [ ] Subtask 7.2: Ruff lint alle neuen Dateien
- [ ] Subtask 7.3: MyPy Type-Check
- [ ] Subtask 7.4: Vollständige Docstrings für alle Methoden

## Dev Notes

### Story Context

Story 5.5 implementiert die **Working Memory Library API** - eine zentrale Komponente für Session Context Management. Die WorkingMemory-Klasse wrapat die bestehende MCP Tool-Logik und ermöglicht programmatischen Zugriff ohne MCP Protocol.

**Strategische Bedeutung:**

- **Session Context:** Ermöglicht Ecosystem-Projekten (i-o-system, tethr) schnellen Zugriff auf aktuellen Kontext
- **LRU-basiert:** Automatische Eviction bei Kapazitätsgrenze (10 Items)
- **Kritische Items:** Items mit importance >0.8 werden zu Stale Memory archiviert statt gelöscht

**Relation zu anderen Stories:**

- **Story 5.2 (Vorgänger):** MemoryStore Core Class mit Sub-Object Accessor Properties
- **Story 5.4 (parallel):** L2 Insight Storage Library API
- **Story 5.6 (Folge):** Episode Memory Library API
- **Story 5.7 (Folge):** Graph Query Neighbors Library API

[Source: bmad-docs/epics/epic-5-library-api-for-ecosystem-integration.md#Story-5.5]
[Source: bmad-docs/epic-5-tech-context.md#Working-Memory]

### Learnings from Previous Story

**From Story 5-2-memorystore-core-class (Status: done)**

Story 5.2 wurde erfolgreich mit APPROVED Review abgeschlossen (100% AC coverage, 33 Tests passing). Die wichtigsten Learnings für Story 5.5:

#### 1. Existierende Implementation nutzen

**Aus Story 5.2 Implementation:**

- `cognitive_memory/store.py` enthält bereits `WorkingMemory` Klasse mit:
  - Context Manager (`__enter__`, `__exit__`)
  - `_connection_manager: ConnectionManager` Attribut
  - `add()`, `get_all()`, `clear()` Stubs mit `NotImplementedError`
  - Lazy-Initialization via `store.working` Property

**Apply to Story 5.5:**

1. Erweitere bestehende Stubs - keine Neuschreibung der Klasse
2. Implementiere `add()`, `list()` (war `get_all()`), `get()`, `clear()` Methoden
3. Erstelle `WorkingMemoryItem` Dataclass in `types.py`

#### 2. Code-Organisation Best Practices

**Aus Story 5.2 Review:**

- Type Hints: Vollständig implementiert mit `from __future__ import annotations`
- Docstrings: Vollständig dokumentiert mit Args/Returns
- Logging: INFO/DEBUG/ERROR Levels korrekt
- Error Handling: Structured Error Responses via `cognitive_memory/exceptions.py`

**Apply to Story 5.5:**

1. Nutze gleiches Type Hints Pattern
2. Vollständige Docstrings für neue Methoden
3. `ValidationError` für Importance-Validierung
4. Logging bei add/clear Events

#### 3. Existing Types und Exceptions

**Aus Story 5.1/5.2 Implementation:**

- `cognitive_memory/types.py`: `WorkingMemoryResult` bereits vorhanden
- `cognitive_memory/exceptions.py`: `ValidationError` bereits vorhanden

**Apply to Story 5.5:**

1. Nutze bestehendes `WorkingMemoryResult`
2. Ergänze `WorkingMemoryItem` für list/get Operations
3. Nutze `ValidationError` für Importance-Validierung

[Source: bmad-docs/stories/5-2-memorystore-core-class.md#Completion-Notes-List]
[Source: bmad-docs/stories/5-2-memorystore-core-class.md#Senior-Developer-Review]

### Project Structure Notes

**Story 5.5 Deliverables:**

Story 5.5 modifiziert oder erstellt folgende Dateien:

**MODIFIED Files:**

1. `cognitive_memory/store.py` - WorkingMemory Methoden implementieren:
   - `add()` → Full Implementation
   - `list()` (rename von `get_all()` für API-Konsistenz)
   - `get()` → Neue Methode
   - `clear()` → Full Implementation

2. `cognitive_memory/types.py` - WorkingMemoryItem Dataclass hinzufügen

**NEW Files:**

1. `tests/library/test_working_memory.py` - Umfassende Tests für Working Memory

**Project Structure Alignment:**

```
cognitive-memory/
├─ cognitive_memory/              # EXISTING: Library API Package
│  ├─ __init__.py                 # EXISTING: Public API Exports
│  ├─ store.py                    # MODIFIED: WorkingMemory Implementation (this story)
│  ├─ types.py                    # MODIFIED: WorkingMemoryItem Dataclass
│  ├─ connection.py               # EXISTING: Connection Wrapper
│  └─ exceptions.py               # EXISTING: Exception Hierarchy
├─ mcp_server/                    # EXISTING: MCP Server Implementation
│  └─ tools/
│     └─ update_working_memory.py # REFERENCE: Existing MCP Tool to wrap (if exists)
├─ tests/
│  └─ library/                    # EXISTING: Library API Tests
│     ├─ test_imports.py          # EXISTING: Story 5.1 Tests
│     ├─ test_memorystore.py      # EXISTING: Story 5.2 Tests
│     └─ test_working_memory.py   # NEW: Story 5.5 Tests
└─ pyproject.toml                 # EXISTING: Package Configuration
```

[Source: bmad-docs/architecture.md#Projektstruktur]
[Source: bmad-docs/epic-5-tech-context.md#Package-Structure]

### Technical Implementation Notes

**Database Schema (working_memory Tabelle):**

```sql
CREATE TABLE working_memory (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    importance FLOAT DEFAULT 0.5,      -- 0.0-1.0, >0.8 = Critical
    last_accessed TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_wm_lru ON working_memory(last_accessed ASC);
```

**LRU Eviction Logic:**

```python
def add(self, content: str, importance: float = 0.5) -> WorkingMemoryResult:
    # 1. Validate importance
    if importance < 0.0 or importance > 1.0:
        raise ValidationError(f"Importance must be between 0.0 and 1.0, got {importance}")

    # 2. Check current count
    current_count = self._get_count()

    evicted_id = None
    archived_id = None

    # 3. If at capacity, evict LRU item
    if current_count >= 10:
        lru_item = self._get_lru_item()
        if lru_item.importance > 0.8:
            archived_id = self._archive_to_stale(lru_item)
        evicted_id = lru_item.id
        self._delete_item(lru_item.id)

    # 4. Insert new item
    added_id = self._insert_item(content, importance)

    return WorkingMemoryResult(
        added_id=added_id,
        evicted_id=evicted_id,
        archived_id=archived_id,
        current_count=self._get_count()
    )
```

**Wrapper Pattern (ADR-007):**

```python
# cognitive_memory/store.py - WorkingMemory wraps DB operations directly
# since mcp_server/tools/update_working_memory.py may not have reusable functions

from mcp_server.db.connection import get_connection

class WorkingMemory:
    def add(self, content: str, importance: float = 0.5) -> WorkingMemoryResult:
        """Add item to working memory with LRU eviction."""
        with self._connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # Direct SQL for simplicity
                cur.execute(...)
```

[Source: bmad-docs/architecture.md#Datenbank-Schema]
[Source: bmad-docs/architecture.md#ADR-007]

### Testing Strategy

**Story 5.5 Testing Approach:**

Story 5.5 fokussiert auf **Working Memory CRUD Testing** und **LRU Eviction Testing**.

**Test Categories:**

1. **add() Tests:**
   - Test einfaches Add → WorkingMemoryResult
   - Test mit importance=0.5 (default) und explizitem Wert
   - Test LRU Eviction bei >10 Items
   - Test Stale Memory Archivierung bei Eviction (importance >0.8)
   - Test ValidationError bei importance <0 oder >1

2. **list() Tests:**
   - Test leere Working Memory → leere Liste
   - Test mit 1-10 Items → korrekte Sortierung
   - Test Sortierung nach last_accessed DESC

3. **get() Tests:**
   - Test existierendes Item → WorkingMemoryItem
   - Test nicht-existierendes Item → None
   - Test last_accessed Update (LRU Touch)

4. **clear() Tests:**
   - Test leere Working Memory → 0
   - Test mit Items → korrekte Anzahl
   - Test Stale Memory Archivierung vor Löschen

**Mock Strategy:**

```python
from unittest.mock import patch, MagicMock
from cognitive_memory import MemoryStore

@patch('cognitive_memory.connection.get_connection')
def test_working_memory_add(mock_conn):
    mock_cursor = MagicMock()
    mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1,)  # Inserted ID

    store = MemoryStore("postgresql://test")
    store.connect()

    result = store.working.add("Test content", importance=0.7)

    assert result.added_id == 1
    assert result.evicted_id is None
```

[Source: bmad-docs/architecture.md#Testing-Strategy-für-Epic-5]
[Source: bmad-docs/epic-5-tech-context.md#ATDD-Test-Status]

### Alignment mit Architecture Decisions

**ADR-007: Library API Wrapper Pattern:**

Story 5.5 implementiert das Wrapper Pattern gemäß Architecture:

| Komponente | Implementation |
|------------|----------------|
| `WorkingMemory.add()` | Wraps DB INSERT + LRU Eviction Logic |
| `WorkingMemory.list()` | Wraps DB SELECT with ORDER BY |
| `WorkingMemory.get()` | Wraps DB SELECT + UPDATE last_accessed |
| `WorkingMemory.clear()` | Wraps Archive + DELETE |

**Code-Wiederverwendung:**

| Bestehende Komponente | Wiederverwendung |
|----------------------|------------------|
| `mcp_server/db/connection.py` | Via `ConnectionManager` |
| `cognitive_memory/types.py:WorkingMemoryResult` | Return Type |
| `cognitive_memory/exceptions.py:ValidationError` | Error Handling |

[Source: bmad-docs/architecture.md#ADR-007]

### References

- [Source: bmad-docs/epics/epic-5-library-api-for-ecosystem-integration.md#Story-5.5] - User Story und Acceptance Criteria (authoritative)
- [Source: bmad-docs/epic-5-tech-context.md] - Library API Design und Wrapper Pattern
- [Source: bmad-docs/architecture.md#Datenbank-Schema] - working_memory Tabelle
- [Source: bmad-docs/architecture.md#ADR-007] - Wrapper Pattern Decision
- [Source: bmad-docs/stories/5-2-memorystore-core-class.md] - Predecessor Story (Foundation)
- [Source: cognitive_memory/store.py:389-436] - Bestehende WorkingMemory Stubs
- [Source: cognitive_memory/types.py:59-73] - Bestehende WorkingMemoryResult

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-11-30 | Story created - Initial draft with ACs, tasks, dev notes from Epic 5.5 | BMad create-story workflow |

## Dev Agent Record

### Context Reference

- bmad-docs/stories/5-5-working-memory-library-api.context.xml

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

- Workflow execution completed successfully
- All acceptance criteria implemented
- Test framework created and validated

### Completion Notes List

Story 5.5 has been successfully completed with full implementation of the Working Memory Library API:

✅ **AC-5.5.1: Working Memory Add Operation** - Fully implemented with importance validation, LRU eviction logic, and stale memory archiving for critical items (>0.8 importance)

✅ **AC-5.5.2: Working Memory List Operation** - Implemented with proper sorting by last_accessed DESC, returning list of WorkingMemoryItem objects

✅ **AC-5.5.3: Working Memory Clear Operation** - Implemented with stale memory archiving for critical items before deletion

✅ **AC-5.5.4: Working Memory Get Operation** - Implemented with LRU touch functionality (updates last_accessed on retrieval)

✅ **AC-5.5.5: Importance Validation** - Comprehensive validation with proper error messages for importance < 0.0 and > 1.0

✅ **AC-5.5.6: Wrapper Pattern Compliance** - Implementation follows ADR-007, uses shared ConnectionManager, consistent with existing codebase patterns

### File List

**MODIFIED Files:**
1. `cognitive_memory/types.py` - Added WorkingMemoryItem dataclass for list/get operations
2. `cognitive_memory/store.py` - Implemented all WorkingMemory methods: add(), list(), get(), clear()
3. `bmad-docs/stories/5-5-working-memory-library-api.md` - Updated status to done
4. `bmad-docs/sprint-status.yaml` - Updated story status to done

**NEW Files:**
1. `tests/library/test_working_memory.py` - Comprehensive test suite covering all operations and edge cases
