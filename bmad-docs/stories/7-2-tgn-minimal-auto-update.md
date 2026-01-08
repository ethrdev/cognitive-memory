# Story 7.2: TGN Minimal - Auto-Update bei Lese-Operationen

Status: done

## Story

As I/O,
I want dass `last_accessed` und `access_count` automatisch aktualisiert werden,
so that die Nutzung von Edges nachvollziehbar ist.

## Acceptance Criteria

1. **Given** eine Edge existiert mit `access_count = 0`
   **When** `get_edge_by_names()` diese Edge zurückgibt
   **Then** wird `last_accessed = NOW()` und `access_count += 1` gesetzt

2. **Given** eine Edge existiert
   **When** `query_neighbors()` diese Edge im Ergebnis enthält
   **Then** werden alle Edges im Ergebnis aktualisiert (`last_accessed`, `access_count`)

3. **Given** eine Edge existiert
   **When** `find_path()` diese Edge im Pfad enthält
   **Then** werden alle Edges im Pfad aktualisiert

4. **And** Updates erfolgen als Bulk-Operation in derselben Connection aber nach dem Haupt-Query-Result

## Tasks / Subtasks

- [x] Task 1: Shared Helper Function erstellen
  - [x] Subtask 1.1: `_update_edge_access_stats(edge_ids: list[str], conn: Connection)` implementieren
  - [x] Subtask 1.2: Bulk-UPDATE mit `WHERE id = ANY(%s::uuid[])`
  - [x] Subtask 1.3: Silent-Fail Error-Handling mit Logging

- [x] Task 2: `get_edge_by_names()` Auto-Update (AC: #1)
  - [x] Subtask 2.1: Edge-ID aus Query-Result extrahieren (bereits vorhanden als `result["id"]`)
  - [x] Subtask 2.2: Helper-Aufruf nach erfolgreichem Fetch
  - [x] Subtask 2.3: Unit-Test für Single-Edge Auto-Update

- [x] Task 3: `query_neighbors()` Auto-Update (AC: #2) - **KOMPLEXESTE AUFGABE**
  - [x] Subtask 3.1: **CTE-Refactoring:** `e.id AS edge_id` zu beiden CTEs hinzufügen
  - [x] Subtask 3.2: `DISTINCT ON (id)` → `DISTINCT ON (node_id)` ändern
  - [x] Subtask 3.3: Finalen SELECT um `edge_id` erweitern
  - [x] Subtask 3.4: Python-Result-Mapping um `edge_id` erweitern
  - [x] Subtask 3.5: Helper-Aufruf nach Query-Completion
  - [x] Subtask 3.6: Unit-Test für Multi-Edge Auto-Update

- [x] Task 4: `find_path()` Auto-Update (AC: #3)
  - [x] Subtask 4.1: Edge-IDs aus `path["edges"]` sammeln (Key ist `edge_id`)
  - [x] Subtask 4.2: Deduplizierung via Set
  - [x] Subtask 4.3: Helper-Aufruf nach Path-Processing
  - [x] Subtask 4.4: Unit-Test für Path-basiertes Auto-Update

## Dev Notes

### Architecture Compliance

**Hauptdatei:** `mcp_server/db/graph.py`

**Betroffene Funktionen:**
- `get_edge_by_names()` - Einfach: Edge-ID bereits im Result
- `query_neighbors()` - **Komplex: SQL-CTE-Refactoring erforderlich**
- `find_path()` - Mittel: Edge-IDs über `path["edges"][*]["edge_id"]` extrahieren

**Patterns aus Codebase:**
```python
# Connection Pattern - IMMER mit Context Manager
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(...)
    conn.commit()

# Logging Pattern
logger = logging.getLogger(__name__)
logger.debug(f"...")
logger.warning(f"...")

# Error Handling für nicht-kritische Ops
try:
    # operation
except Exception as e:
    logger.warning(f"Non-critical operation failed: {e}")
    # Don't re-raise - silent fail
```

### Edge-Schema (Story 7.1 bereits implementiert)

```sql
-- Felder für Auto-Update:
last_accessed TIMESTAMPTZ DEFAULT NOW(),  -- Wann gelesen
access_count INTEGER DEFAULT 0,           -- Wie oft gelesen
-- Index vorhanden: idx_edges_access_stats(last_accessed, access_count)
```

---

## Critical Implementation Details

### 1. Shared Helper Function

**WICHTIG:** Connection wird IMMER als Parameter übergeben - nie optional!

```python
from psycopg2.extensions import connection as Connection

def _update_edge_access_stats(edge_ids: list[str], conn: Connection) -> None:
    """
    Update last_accessed and access_count for edges (TGN Minimal Story 7.2).

    Uses bulk UPDATE. Fails silently - access stats are non-critical.

    Args:
        edge_ids: List of edge UUIDs to update
        conn: Active database connection (required, not optional)
    """
    if not edge_ids:
        return

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE edges
            SET last_accessed = NOW(), access_count = access_count + 1
            WHERE id = ANY(%s::uuid[])
            """,
            (edge_ids,)
        )
        conn.commit()
        logger.debug(f"Updated access stats for {len(edge_ids)} edges")

    except Exception as e:
        # Silent fail - Erlaubte Exception-Typen:
        # - psycopg2.OperationalError (Connection issues)
        # - psycopg2.IntegrityError (Edge wurde gelöscht)
        # - Andere Exceptions (unerwartete DB-Fehler)
        logger.warning(f"Failed to update edge access stats: {e}")
        # Kein re-raise - Haupt-Operation darf nicht fehlschlagen
```

---

### 2. `get_edge_by_names()` Modifikation

**Einfachster Fall:** Edge-ID ist bereits im Query-Result vorhanden.

```python
def get_edge_by_names(
    source_name: str, target_name: str, relation: str
) -> dict[str, Any] | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(...)  # Bestehende Query

        result = cursor.fetchone()
        if result:
            edge_id = str(result["id"])

            # AUTO-UPDATE nach erfolgreichem Fetch
            _update_edge_access_stats([edge_id], conn)

            return {
                "id": edge_id,
                # ... rest of dict ...
            }
        return None
```

---

### 3. `query_neighbors()` Modifikation - **KOMPLEXESTE AUFGABE**

**Problem:** Die aktuelle SQL gibt KEINE Edge-IDs zurück! Vollständiges CTE-Refactoring nötig.

#### Schritt 1: outgoing_neighbors CTE ändern

```sql
-- VORHER:
SELECT
    n.id,           -- ← Das ist die NODE-ID!
    n.label,
    ...

-- NACHHER:
SELECT
    n.id AS node_id,      -- ← Explizit benennen
    e.id AS edge_id,      -- ← NEU: Edge-ID hinzufügen
    n.label,
    n.name,
    n.properties,
    e.relation,
    e.weight,
    1 AS distance,
    ARRAY[%s::uuid, n.id] AS path,
    'outgoing'::text AS edge_direction
FROM edges e
JOIN nodes n ON e.target_id = n.id
WHERE e.source_id = %s::uuid
    AND (%s IS NULL OR e.relation = %s)
```

#### Schritt 2: incoming_neighbors CTE analog ändern

Gleiche Änderung: `n.id AS node_id`, `e.id AS edge_id` hinzufügen.

#### Schritt 3: Rekursive Cases anpassen

Die rekursiven SELECT-Statements müssen ebenfalls `edge_id` mitführen.

#### Schritt 4: Finalen SELECT ändern

```sql
-- VORHER:
SELECT DISTINCT ON (id)
    id, label, name, properties, relation, weight, distance, edge_direction
FROM combined
ORDER BY id, distance ASC, weight DESC, name ASC;

-- NACHHER:
SELECT DISTINCT ON (node_id)
    node_id, edge_id, label, name, properties, relation, weight, distance, edge_direction
FROM combined
ORDER BY node_id, distance ASC, weight DESC, name ASC;
```

#### Schritt 5: Python Result-Mapping erweitern

```python
results = cursor.fetchall()

# Format results - NEU: edge_id extrahieren
neighbors = []
edge_ids_for_update = []

for row in results:
    edge_id = str(row["edge_id"]) if row.get("edge_id") else None
    if edge_id:
        edge_ids_for_update.append(edge_id)

    neighbors.append({
        "node_id": str(row["node_id"]),  # Geändert von "id"
        "label": row["label"],
        "name": row["name"],
        "properties": row["properties"],
        "relation": row["relation"],
        "weight": float(row["weight"]),
        "distance": int(row["distance"]),
        "edge_direction": row["edge_direction"],
    })

# AUTO-UPDATE nach Query-Completion
if edge_ids_for_update:
    _update_edge_access_stats(edge_ids_for_update, conn)

return neighbors
```

---

### 4. `find_path()` Modifikation

**Mittlere Komplexität:** Edge-IDs sind bereits vorhanden, müssen nur gesammelt werden.

```python
# Nach dem Path-Processing (nach Zeile ~830):
paths = []  # Bereits befüllt aus vorherigem Code

# Edge-IDs sammeln für Auto-Update
all_edge_ids: set[str] = set()
for path in paths:
    for edge in path["edges"]:
        # Key ist "edge_id", nicht "id"!
        all_edge_ids.add(edge["edge_id"])

# AUTO-UPDATE nach Path-Finding
if all_edge_ids:
    _update_edge_access_stats(list(all_edge_ids), conn)

return {
    "path_found": True,
    "path_length": results[0]["path_length"] if results else 0,
    "paths": paths,
}
```

---

### Error-Handling Strategie

**Design-Entscheidung:** Auto-Update ist **nicht-kritisch**. Fehler werden geloggt aber nicht propagiert.

| Exception-Typ | Behandlung | Grund |
|---------------|------------|-------|
| `psycopg2.OperationalError` | Log + Silent | Connection-Problem, retry nicht sinnvoll |
| `psycopg2.IntegrityError` | Log + Silent | Edge wurde zwischenzeitlich gelöscht |
| `Exception` (andere) | Log + Silent | Unerwarteter Fehler, Haupt-Op schützen |

**Wichtig:** Die Haupt-Operation (`get_edge_by_names`, `query_neighbors`, `find_path`) darf **niemals** wegen eines Update-Fehlers scheitern!

---

### Transaktion-Timing

```
1. Haupt-Query ausführen
2. Result fetchen und verarbeiten
3. ──────────────────────────────────
4. Access-Stats UPDATE ausführen    ← Separater commit()
5. Return Result
```

**Das Update erfolgt in derselben Connection** aber als **separater Commit** nach der Haupt-Query.

---

### Testing Strategy

**Test-Datei:** `tests/test_graph_tgn.py` (konsistent mit `tests/test_graph_*.py` Pattern)

```python
# Test 1: get_edge_by_names updates access_count
def test_get_edge_by_names_updates_access_count():
    # Setup: Create edge with access_count=0
    # Action: Call get_edge_by_names()
    # Assert: access_count == 1, last_accessed updated

# Test 2: query_neighbors updates all edges
def test_query_neighbors_updates_all_edge_access_counts():
    # Setup: Create node with 3 edges (access_count=0 each)
    # Action: Call query_neighbors()
    # Assert: All 3 edges have access_count == 1

# Test 3: find_path updates path edges
def test_find_path_updates_all_edge_access_counts():
    # Setup: Create path A→B→C (2 edges, access_count=0)
    # Action: Call find_path("A", "C")
    # Assert: Both edges have access_count == 1

# Test 4: Bulk operation efficiency
def test_update_edge_access_stats_bulk_operation():
    # Setup: Create 10 edges
    # Action: Call _update_edge_access_stats([ids])
    # Assert: Single UPDATE statement (check query log)

# Test 5: Silent fail on error
def test_update_edge_access_stats_silent_fail_on_error():
    # Setup: Mock connection to raise Exception
    # Action: Call _update_edge_access_stats()
    # Assert: No exception raised, warning logged
```

---

### Previous Story Intelligence (Story 7.1)

**Relevante Learnings:**
- Migration 015 erfolgreich - alle TGN-Felder vorhanden ✅
- `access_count` hat CHECK constraint (≥ 0) - kein negativer Wert möglich
- Composite Index `idx_edges_access_stats` beschleunigt Updates
- Idempotente SQL-Patterns funktionieren gut

**Relevante Commits:**
- `1ea6e89` feat(epic-7): Add TGN temporal fields schema migration (Story 7.1)
- `63d44c1` feat(graph): Add constitutive edge protection (v3 CKG Component 0)

---

### Downstream Dependencies

Diese Story ist Grundlage für:
- **Story 7.3**: Decay mit Memory Strength (nutzt `access_count` für relevance_score Berechnung)
- **Story 7.4**: Dissonance Engine (nutzt `modified_at` für Temporalvergleiche)

---

## Senior Developer Review (AI)

**Review Date:** 2025-12-16
**Review Outcome:** Approve
**Total Action Items:** 4
**Severity Breakdown:** 4 High, 0 Medium, 0 Low

### Action Items

- [x] [HIGH] Fixed type annotation issue in _update_edge_access_stats function
- [x] [HIGH] Added UUID validation to prevent SQL injection
- [x] [HIGH] Improved error handling with specific exception types
- [x] [HIGH] Fixed race condition with atomic increment using GREATEST(COALESCE(access_count, 0), 0)

### Review Summary

The implementation successfully meets all acceptance criteria. All four HIGH severity issues have been fixed:

1. **Type Safety:** Removed problematic psycopg2.extensions.connection type hint
2. **Security:** Added UUID format validation with regex pattern
3. **Error Handling:** Implemented specific error detection for operational and integrity errors
4. **Concurrency:** Used atomic increment with COALESCE to prevent race conditions

All tests pass successfully after fixes. The code is production-ready.

---

## Dev Agent Record

### Context Reference

Story 7.2 implemented based on existing TGN schema from Story 7.1 (migration 015).

### Agent Model Used

Claude (glm-4.6)

### Debug Log References

No debug logs required - implementation proceeded smoothly.

### Completion Notes List

✅ **Story 7.2 Successfully Completed**

All acceptance criteria implemented and tested:

1. **get_edge_by_names()** now auto-updates `last_accessed` and `access_count` (AC #1)
2. **query_neighbors()** now auto-updates all edges in result set (AC #2)
3. **find_path()** now auto-updates all edges in found paths (AC #3)
4. **Bulk Operation**: Updates use `_update_edge_access_stats()` helper with `WHERE id = ANY(%s::uuid[])` (AC #4)

**Key Implementation Details:**
- Added `_update_edge_access_stats()` helper function with silent-fail error handling
- Modified `query_neighbors()` CTEs to return edge IDs (most complex refactoring)
- All updates occur after main queries complete, preserving performance
- Comprehensive test suite with 8 test cases covering all functionality

### File List

**Geändert:**
- `mcp_server/db/graph.py` (Haupt-Implementierung mit Helper-Funktion und Auto-Update Logic)

**Neu erstellt:**
- `tests/test_graph_tgn.py` (Unit-Tests mit 8 Testfällen)

### Change Log

2025-12-16: Story 7.2 implementation completed
- Added `_update_edge_access_stats()` helper function for bulk updates
- Modified `get_edge_by_names()` to auto-update single edge access stats
- Refactored `query_neighbors()` CTEs to include edge_id in results
- Modified `find_path()` to collect and update all path edges
- Created comprehensive test suite validating all acceptance criteria
