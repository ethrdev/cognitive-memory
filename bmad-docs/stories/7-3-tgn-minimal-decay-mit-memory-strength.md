# Story 7.3: TGN Minimal - Decay mit Memory Strength

Status: Done

## Story

As I/O,
I want einen `relevance_score` für Edges basierend auf Decay UND Zugriffshäufigkeit,
so that "Intelligent Forgetting" nicht nur Aktualität, sondern auch Wichtigkeit berücksichtigt.

## Acceptance Criteria

1. **Given** eine deskriptive Edge mit `last_accessed` vor 100 Tagen und `access_count = 0`
   **When** der `relevance_score` berechnet wird
   **Then** ist der Score ~0.37 (exp(-100/100) ≈ 0.368)

2. **Given** eine deskriptive Edge mit `last_accessed` vor 100 Tagen und `access_count = 10`
   **When** der `relevance_score` berechnet wird
   **Then** ist der Score ~0.74 (S=340 → exp(-100/340) ≈ 0.745)

3. **Given** eine konstitutive Edge (`edge_type = "constitutive"`)
   **When** der `relevance_score` berechnet wird
   **Then** ist der Score immer 1.0 (kein Decay)

4. **And** `relevance_score` wird bei Queries berechnet, nicht gespeichert (dynamisch)

5. **Given** eine deskriptive Edge mit `importance = "high"` (S-Floor = 200)
   **When** der `relevance_score` berechnet wird nach 100 Tagen
   **Then** ist der Score ~0.61 (exp(-100/200) ≈ 0.606)

## Tasks / Subtasks

- [x] Task 1: `calculate_relevance_score()` Funktion implementieren (AC: #1, #2, #3, #5)
  - [x] Subtask 1.1: Memory Strength Formel mit logarithmischem access_count Faktor
  - [x] Subtask 1.2: Konstitutive Edge Check → immer 1.0
  - [x] Subtask 1.3: Importance-basierter S-Floor (low/medium/high)
  - [x] Subtask 1.4: Unit-Tests für alle Score-Berechnungen

- [x] Task 2: SQL-CTE Erweiterung für Edge-Daten
  - [x] Subtask 2.1: `e.properties` zu beiden CTEs hinzufügen
  - [x] Subtask 2.2: `e.last_accessed` zu beiden CTEs hinzufügen
  - [x] Subtask 2.3: `e.access_count` zu beiden CTEs hinzufügen
  - [x] Subtask 2.4: Python Result-Mapping erweitern

- [x] Task 3: `query_neighbors()` Integration (AC: #4)
  - [x] Subtask 3.1: `relevance_score` für jede Edge im Ergebnis berechnen
  - [x] Subtask 3.2: Score zum Result-Dict hinzufügen
  - [x] Subtask 3.3: Standard-Sortierung nach relevance_score (descending)

- [x] Task 4: `find_path()` Integration (AC: #4)
  - [x] Subtask 4.1: `get_edge_by_id()` Helper implementieren
  - [x] Subtask 4.2: `relevance_score` für jede Edge im Pfad berechnen
  - [x] Subtask 4.3: Aggregierte `path_relevance` (Produkt)

- [x] Task 5: Test Suite erweitern
  - [x] Subtask 5.1: `TestTGNDecayWithMemoryStrength` Klasse in `test_graph_tgn.py` hinzufügen
  - [x] Subtask 5.2: Tests für alle Score-Berechnungen
  - [x] Subtask 5.3: Integrationstests für query_neighbors + find_path

## Dev Notes

### Architecture Compliance

**Hauptdatei:** `mcp_server/db/graph.py`

**Neue Funktionen:**
- `calculate_relevance_score(edge_data: dict) -> float`
- `get_edge_by_id(edge_id: str) -> dict | None` (für find_path Integration)

**Modifikationen:**
- `query_neighbors()` - SQL-CTE erweitern + Score berechnen
- `find_path()` - Score pro Edge + path_relevance

**Patterns aus Story 7.2 (WIEDERVERWENDEN):**
```python
# Connection Pattern
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(...)

# Logging Pattern
logger.debug(f"Calculated relevance_score={score:.4f} for edge {edge_id}")

# Silent-fail für nicht-kritische Ops
try:
    # operation
except Exception as e:
    logger.warning(f"Non-critical operation failed: {e}")
```

---

### KRITISCH: SQL-CTE Erweiterung

**Problem:** Die aktuelle `query_neighbors()` CTE gibt KEINE Edge-Properties, last_accessed oder access_count zurück!

**HINZUFÜGEN zu outgoing_neighbors UND incoming_neighbors CTEs (graph.py:587-667):**

```sql
SELECT
    n.id AS node_id,
    e.id AS edge_id,
    n.label,
    n.name,
    n.properties AS node_properties,
    e.properties AS edge_properties,  -- NEU
    e.relation,
    e.weight,
    e.last_accessed,                  -- NEU
    e.access_count,                   -- NEU
    1 AS distance,
    ARRAY[%s::uuid, n.id] AS path,
    'outgoing'::text AS edge_direction
FROM edges e
JOIN nodes n ON e.target_id = n.id
WHERE e.source_id = %s::uuid
    AND (%s IS NULL OR e.relation = %s)
```

**Python Result-Mapping erweitern (graph.py:698-716):**

```python
neighbors.append({
    "node_id": str(row["node_id"]),
    "label": row["label"],
    "name": row["name"],
    "properties": row["node_properties"],      # Umbenannt
    "edge_properties": row["edge_properties"], # NEU
    "relation": row["relation"],
    "weight": float(row["weight"]),
    "distance": int(row["distance"]),
    "edge_direction": row["edge_direction"],
    "last_accessed": row["last_accessed"],     # NEU
    "access_count": row["access_count"],       # NEU
    "relevance_score": 0.0,                    # Wird nach Query berechnet
})
```

---

### Memory Strength Formel

```python
import math
from datetime import datetime, timezone, timedelta

def calculate_relevance_score(edge_data: dict) -> float:
    """
    Berechnet relevance_score basierend auf Ebbinghaus Forgetting Curve
    mit logarithmischem Memory Strength Faktor.

    Formel: relevance_score = exp(-days_since / S)
    wobei S = S_BASE * (1 + log(1 + access_count))

    Args:
        edge_data: Dict mit keys: edge_properties, last_accessed, access_count

    Returns:
        float zwischen 0.0 und 1.0
    """
    properties = edge_data.get("edge_properties") or edge_data.get("properties") or {}

    # Konstitutive Edges: IMMER 1.0
    if properties.get("edge_type") == "constitutive":
        return 1.0

    # Memory Strength berechnen
    S_BASE = 100  # Basis-Stärke in Tagen

    access_count = edge_data.get("access_count", 0) or 0
    S = S_BASE * (1 + math.log(1 + access_count))
    # access_count=0  → S = 100 * 1.0   = 100
    # access_count=10 → S = 100 * 3.4   = 340

    # S-Floor basierend auf importance
    S_FLOOR = {"low": None, "medium": 100, "high": 200}
    importance = properties.get("importance", "medium")  # Default: medium
    floor = S_FLOOR.get(importance)
    if floor:
        S = max(S, floor)

    # Tage seit letztem Zugriff
    last_accessed = edge_data.get("last_accessed")
    if not last_accessed:
        return 1.0  # Kein Timestamp = keine Decay-Berechnung

    if isinstance(last_accessed, str):
        last_accessed = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))

    days_since = (datetime.now(timezone.utc) - last_accessed).total_seconds() / 86400

    # Exponential Decay
    return max(0.0, min(1.0, math.exp(-days_since / S)))
```

**Mathematische Validierung:**

| Szenario | access_count | importance | S | days | Score |
|----------|--------------|------------|---|------|-------|
| AC #1 | 0 | medium | 100 | 100 | exp(-1) ≈ **0.37** |
| AC #2 | 10 | medium | 340 | 100 | exp(-0.29) ≈ **0.74** |
| AC #3 | 0 | - | ∞ | 1000 | **1.0** (konstitutiv) |
| AC #5 | 0 | high | 200 | 100 | exp(-0.5) ≈ **0.61** |

---

### get_edge_by_id() Helper (für find_path)

```python
def get_edge_by_id(edge_id: str) -> dict[str, Any] | None:
    """
    Hole Edge-Details für relevance_score Berechnung.

    Args:
        edge_id: UUID string der Edge

    Returns:
        Edge data dict oder None
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, properties, last_accessed, access_count
            FROM edges
            WHERE id = %s::uuid;
            """,
            (edge_id,)
        )
        result = cursor.fetchone()
        if result:
            return {
                "id": str(result["id"]),
                "edge_properties": result["properties"],
                "last_accessed": result["last_accessed"],
                "access_count": result["access_count"],
            }
        return None
```

---

### Integration in query_neighbors()

Nach dem Fetch der Results, VOR dem Return (graph.py:~718):

```python
# relevance_score für jede Edge berechnen
for neighbor in neighbors:
    edge_data = {
        "edge_properties": neighbor.get("edge_properties", {}),
        "last_accessed": neighbor.get("last_accessed"),
        "access_count": neighbor.get("access_count"),
    }
    neighbor["relevance_score"] = calculate_relevance_score(edge_data)

# Standard-Sortierung: höchste Relevanz zuerst
neighbors.sort(key=lambda n: n["relevance_score"], reverse=True)
```

---

### Integration in find_path()

Nach dem Path-Processing (graph.py:~905):

```python
# relevance_score für alle Edges im Pfad berechnen
for path in paths:
    edge_scores = []
    for edge in path["edges"]:
        edge_detail = get_edge_by_id(edge["edge_id"])
        if edge_detail:
            score = calculate_relevance_score(edge_detail)
            edge["relevance_score"] = score
            edge_scores.append(score)
        else:
            edge["relevance_score"] = 1.0  # Fallback
            edge_scores.append(1.0)

    # Produkt-Aggregation: "Alle Edges müssen relevant sein"
    # Bei Score 0.5 * 0.5 = 0.25 (Pfad-Qualität sinkt exponentiell)
    path["path_relevance"] = math.prod(edge_scores) if edge_scores else 1.0
```

---

## Previous Story Intelligence (Story 7.2)

**Direkt wiederverwendbar:**
- `_update_edge_access_stats()` - Bulk-Update Pattern
- UUID-Validierung mit Regex
- Silent-fail Error-Handling

**Relevante Code-Stellen:**
- `graph.py:289-339` - `_update_edge_access_stats()` Helper
- `graph.py:541-733` - `query_neighbors()` CTEs
- `graph.py:736-942` - `find_path()` mit edge_id Sammlung

**Review-Fixes aus 7.2 (übernehmen):**
- Type Safety: Keine `psycopg2.extensions.connection` Type Hints
- Security: UUID-Validierung vor SQL-Queries
- Concurrency: COALESCE für atomare Inkremente

---

## Testing Strategy

**Test-Datei:** `tests/test_graph_tgn.py`

**WICHTIG:** Erweitere die existierende Datei mit neuer Klasse `TestTGNDecayWithMemoryStrength`.

**Benötigte Imports hinzufügen:**
```python
from datetime import datetime, timezone, timedelta  # timedelta NEU
from mcp_server.db.graph import calculate_relevance_score  # NEU
```

**Test Cases:**

| Test | Beschreibung | Expected |
|------|--------------|----------|
| `test_relevance_score_new_edge` | Frische Edge | 0.99-1.0 |
| `test_relevance_score_100_days_no_access` | AC #1 | 0.35-0.40 |
| `test_relevance_score_100_days_high_access` | AC #2 | 0.70-0.78 |
| `test_relevance_score_constitutive` | AC #3 | 1.0 exact |
| `test_relevance_score_high_importance` | AC #5 | 0.58-0.65 |
| `test_query_neighbors_has_relevance_score` | AC #4 | key exists |
| `test_find_path_has_path_relevance` | AC #4 | key exists |

---

## Dependencies

**Upstream (vorausgesetzt):**
- ✅ Story 7.1: TGN Schema-Migration (Felder vorhanden)
- ✅ Story 7.2: Auto-Update (access_count wird gepflegt)
- ✅ Story 7.0: Konstitutive Edge Protection (edge_type Property)

**Downstream (blockiert von dieser Story):**
- Story 7.4: Dissonance Engine (nutzt relevance_score)
- Story 7.7: IEF (nutzt relevance_score)

---

## References

- [Source: bmad-docs/epics/epic-7-v3-constitutive-knowledge-graph.md#Story 7.3]
- [Source: mcp_server/db/graph.py - bestehende Implementierung]
- [Source: tests/test_graph_tgn.py - bestehende Tests erweitern]
- [Wissenschaft: Ebbinghaus Forgetting Curve]

---

## Dev Agent Record

### Context Reference

Story 7.3 basiert auf Epic 7 (v3 Constitutive Knowledge Graph), Phase 1 "TGN Minimal".
Voraussetzungen aus Story 7.1 (Schema) und Story 7.2 (Auto-Update) sind erfüllt.

### Agent Model Used

Claude-4 (claude-4-20241218)

### Debug Log References

Keine kritischen Issues während der Implementierung.

### Completion Notes List

**Story 7.3 vollständig implementiert mit allen Acceptance Criteria:**

✅ **AC #1**: Edge mit 100 Tagen, access_count=0 → Score ~0.37 (exp(-100/100))
✅ **AC #2**: Edge mit 100 Tagen, access_count=10 → Score ~0.74 (S=340 → exp(-100/340))
✅ **AC #3**: Konstitutive Edge → Score immer 1.0 (kein Decay)
✅ **AC #4**: relevance_score wird dynamisch berechnet, nicht gespeichert
✅ **AC #5**: High importance Edge → Score ~0.61 (exp(-100/200))

**Hauptimplementierung:**
- `calculate_relevance_score()` Funktion mit Memory Strength Formel implementiert
- SQL-CTEs in `query_neighbors()` erweitert um edge_properties, last_accessed, access_count
- `get_edge_by_id()` Helper für find_path Integration implementiert
- Relevance Score Integration in query_neighbors() mit Standard-Sortierung
- Path Relevance Aggregation (Produkt) in find_path() implementiert
- Umfassende Test Suite mit 12 Tests für alle Score-Berechnungen und Integration

**Mathematische Validierung erfolgreich:**
- Memory Strength: S = 100 * (1 + log(1 + access_count))
- Importance Floors: low=None, medium=100, high=200
- Exponential Decay: score = exp(-days_since / S)
- Path Relevance: Produkt aller Edge-Scores im Pfad

### File List

**Geändert:**
- `mcp_server/db/graph.py` (calculate_relevance_score, get_edge_by_id, SQL-CTE-Erweiterung, Integration)
- `tests/test_graph_tgn.py` (TestTGNDecayWithMemoryStrength Klasse mit 12 Tests)
- `bmad-docs/stories/7-3-tgn-minimal-decay-mit-memory-strength.md` (Status und Tasks aktualisiert)
- `bmad-docs/sprint-status.yaml` (Story Status auf "review" aktualisiert)

**Keine neuen Dateien erforderlich.**

---

## Review Follow-ups (AI-Review)

### Completed Fixes (Code Review 2025-12-16)

- [x] [AI-Review][HIGH] Naive datetime TypeError fix - added timezone handling [graph.py:333-335]
- [x] [AI-Review][MED] Type annotation für conn Parameter hinzugefügt [graph.py:345]
- [x] [AI-Review][MED] Tests zum Git hinzugefügt (war untracked)
- [x] [AI-Review][LOW] Test für naive datetime edge case hinzugefügt [test_graph_tgn.py:615-627]
- [x] [AI-Review][LOW] Unused psycopg2.extensions import entfernt [graph.py:21]

### Review Summary

**Initial Review Findings:** 1 HIGH, 3 MEDIUM, 2 LOW
**All Issues Fixed:** Yes
**Story Status:** Approved for Done
