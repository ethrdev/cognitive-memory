# Tech-Spec: Bidirektionale Graph-Neighbor-Abfrage

**Erstellt:** 2025-12-07
**Status:** ✅ Completed (2025-12-07)
**Bug-Report:** BUG-REPORT-2025-12-07.md

## Overview

### Problem Statement

Die `graph_query_neighbors`-Funktion findet aktuell nur **ausgehende** Edges (Beziehungen wo der abgefragte Node die `source_id` ist). Eingehende Edges werden komplett ignoriert.

**Konsequenz:** Nodes erscheinen fälschlich "isoliert", obwohl sie eingehende Verbindungen haben. Graph-Analyse liefert unvollständige Ergebnisse.

**Reproduktion:**
```
# Edge: A → B existiert
graph_query_neighbors("A")  # Findet B ✅
graph_query_neighbors("B")  # Findet A NICHT ❌
```

### Solution

Erweiterung der SQL-Query um eingehende Edges mittels `UNION ALL`. Optionaler `direction`-Parameter für explizite Kontrolle:

- `direction="both"` (Default) → Beide Richtungen
- `direction="outgoing"` → Nur ausgehende (bisheriges Verhalten)
- `direction="incoming"` → Nur eingehende

### Scope

**In Scope:**
- Fix für `query_neighbors()` in `mcp_server/db/graph.py`
- Neuer `direction`-Parameter im Tool und DB-Layer
- Tests für bidirektionales Verhalten
- Update der MCP-Tool-Schema

**Out of Scope:**
- Performance-Optimierung (separates Issue falls nötig)
- Änderungen an `find_path()` (verwendet bereits bidirektionale Traversal)

## Context for Development

### Codebase Patterns

```python
# Typ-Pattern für optionale Parameter
def query_neighbors(
    node_id: str,
    relation_type: str | None = None,  # ← Existierendes Pattern
    max_depth: int = 1,
    direction: str = "both"  # ← Neuer Parameter, gleiches Pattern
) -> list[dict[str, Any]]:
```

```sql
-- SQL-Pattern: WITH RECURSIVE CTE für Graph-Traversal
WITH RECURSIVE neighbors AS (
    -- Base case + Recursive case
)
SELECT ... FROM neighbors ...
```

### Files to Reference

| Datei | Relevanz |
|-------|----------|
| `mcp_server/db/graph.py:446-533` | Hauptlogik `query_neighbors()` |
| `mcp_server/tools/graph_query_neighbors.py` | MCP-Tool-Wrapper |
| `tests/test_graph_query_neighbors.py` | Existierende Tests |

### Technical Decisions

1. **Default `direction="both"`** → Standard-Graph-Theorie-Verhalten für "Neighbors"
2. **UNION ALL statt OR** → Bessere Query-Plan-Optimierung in PostgreSQL
3. **Separater `direction` Filter** → Erlaubt explizite Kontrolle ohne Breaking Change
4. **DISTINCT ON (id) mit kürzestem Pfad** → Bei Multiple Paths wird kürzester behalten, Relation geht ggf. verloren (akzeptabel für V1, `include_all_paths` für V2 vorgemerkt)
5. **Path-Array für Cycle Detection** → Start-Node initial im Array verhindert Rückkehr zum Ursprung
6. **`edge_direction` Feld im Result** → Zeigt ob Edge eingehend/ausgehend war (nützlich für Debugging/Analyse)

## Implementation Plan

### Tasks

- [ ] Task 1: `query_neighbors()` in `graph.py` erweitern
  - Neuer Parameter `direction: str = "both"` hinzufügen
  - SQL-Query mit UNION ALL für eingehende Edges erweitern
  - Direction-Filter implementieren (`if direction == "both"` etc.)

- [ ] Task 2: Tool-Wrapper aktualisieren
  - `graph_query_neighbors.py`: Neuen `direction`-Parameter durchreichen
  - Parameter-Validierung hinzufügen (`direction in ["both", "outgoing", "incoming"]`)

- [ ] Task 3: MCP-Schema aktualisieren
  - `__init__.py`: Tool-Schema mit neuem Parameter erweitern

- [ ] Task 4: Tests erweitern
  - Test: Eingehende Edges werden gefunden
  - Test: Multi-hop in beide Richtungen
  - Test: `direction="outgoing"` gibt bisheriges Verhalten
  - Test: `direction="incoming"` findet nur eingehende
  - Test: Node mit nur eingehenden Edges ist nicht "isoliert"
  - Test: Multiple Paths → kürzester Pfad wird behalten (AC 6)
  - Test: Zyklischer Graph terminiert korrekt (AC 7)
  - Test: `edge_direction` Feld korrekt gesetzt

- [ ] Task 5: Bug-Report schließen
  - Verification-Checklist im Bug-Report abhaken
  - Status auf "FIXED" setzen

### SQL-Änderung (Kern-Fix)

**Vorher (nur ausgehend):**
```sql
-- Base case
FROM edges e
JOIN nodes n ON e.target_id = n.id
WHERE e.source_id = %s::uuid
```

**Nachher (bidirektional) - VOLLSTÄNDIGE QUERY:**
```sql
WITH RECURSIVE neighbors AS (
    -- ═══════════════════════════════════════════════════════════════
    -- BASE CASE: Direkte Nachbarn (distance = 1)
    -- ═══════════════════════════════════════════════════════════════

    -- Ausgehende Edges (direction = 'outgoing' OR 'both')
    SELECT n.id, n.label, n.name, n.properties, e.relation, e.weight,
           1 AS distance,
           ARRAY[%s::uuid, n.id] AS path,
           'outgoing' AS edge_direction
    FROM edges e
    JOIN nodes n ON e.target_id = n.id
    WHERE e.source_id = %s::uuid
        AND (%s IS NULL OR e.relation = %s)
        AND %s IN ('outgoing', 'both')

    UNION ALL

    -- Eingehende Edges (direction = 'incoming' OR 'both')
    SELECT n.id, n.label, n.name, n.properties, e.relation, e.weight,
           1 AS distance,
           ARRAY[%s::uuid, n.id] AS path,
           'incoming' AS edge_direction
    FROM edges e
    JOIN nodes n ON e.source_id = n.id
    WHERE e.target_id = %s::uuid
        AND (%s IS NULL OR e.relation = %s)
        AND %s IN ('incoming', 'both')

    UNION ALL

    -- ═══════════════════════════════════════════════════════════════
    -- RECURSIVE CASE: Multi-hop Traversal (distance > 1)
    -- ═══════════════════════════════════════════════════════════════

    -- Rekursiv ausgehend: Von gefundenem Node weiter nach außen
    SELECT n.id, n.label, n.name, n.properties, e.relation, e.weight,
           nb.distance + 1 AS distance,
           nb.path || n.id AS path,
           'outgoing' AS edge_direction
    FROM neighbors nb
    JOIN edges e ON e.source_id = nb.id
    JOIN nodes n ON e.target_id = n.id
    WHERE nb.distance < %s                    -- max_depth Check
        AND NOT (n.id = ANY(nb.path))         -- Cycle Detection
        AND (%s IS NULL OR e.relation = %s)
        AND %s IN ('outgoing', 'both')

    UNION ALL

    -- Rekursiv eingehend: Von gefundenem Node weiter nach innen
    SELECT n.id, n.label, n.name, n.properties, e.relation, e.weight,
           nb.distance + 1 AS distance,
           nb.path || n.id AS path,
           'incoming' AS edge_direction
    FROM neighbors nb
    JOIN edges e ON e.target_id = nb.id
    JOIN nodes n ON e.source_id = n.id
    WHERE nb.distance < %s                    -- max_depth Check
        AND NOT (n.id = ANY(nb.path))         -- Cycle Detection
        AND (%s IS NULL OR e.relation = %s)
        AND %s IN ('incoming', 'both')
)
-- Finale Selektion: Kürzester Pfad pro Node, höchstes Gewicht bei Gleichstand
SELECT DISTINCT ON (id)
    id, label, name, properties, relation, weight, distance, edge_direction
FROM neighbors
ORDER BY id, distance ASC, weight DESC, name ASC;
```

### Edge Cases & Design-Entscheidungen

#### 1. Multiple Paths zum selben Node (DISTINCT ON Verhalten)

**Szenario:** Node A ist über zwei verschiedene Pfade/Relations erreichbar:
```
Start → A (via USES, distance=1, weight=0.9)
Start → B → A (via RELATED_TO, distance=2, weight=0.8)
```

**Entscheidung:** `DISTINCT ON (id)` behält nur den **kürzesten Pfad** (distance ASC) bzw. bei Gleichstand das **höchste Gewicht** (weight DESC).

**Begründung:**
- "Neighbors" bedeutet semantisch "wie nah ist dieser Node?"
- Kürzester Pfad ist die relevanteste Information
- Alternative wäre `ARRAY_AGG(relation)` für alle Relations → komplexere API, meist nicht benötigt

**Wenn alle Relations benötigt:** Separater Parameter `include_all_paths: bool = False` in V2.

#### 2. Cycle Detection bei Bidirektionalem Traversal

**Problem:** Bei `direction="both"` kann A→B gefunden werden, dann B→A (eingehend) → führt zurück zu Start.

**Lösung:** Der `path`-Array verhindert Zyklen:
```sql
AND NOT (n.id = ANY(nb.path))  -- Cycle Detection
```

**Beispiel:**
```
Start=X, Edge X→A→B, Edge B→X (Zyklus)

Schritt 1: path = [X, A]         ✅ A gefunden
Schritt 2: path = [X, A, B]      ✅ B gefunden
Schritt 3: B→X? X IN path? JA    ❌ Zyklus verhindert
```

**Wichtig:** Der Start-Node wird initial in den Path eingefügt (`ARRAY[%s::uuid, n.id]`), sodass er nie wieder besucht wird.

#### 3. Bidirektionales Traversal ≠ Richtungswechsel

**Klarstellung:** Bei `direction="both"` wird NICHT die Richtung gewechselt, sondern BEIDE Richtungen werden PARALLEL verfolgt.

```
Graph: A → B → C ← D

query_neighbors("B", depth=2, direction="both"):
- Ausgehend von B: C (d=1)
- Eingehend zu B: A (d=1)
- Ausgehend von C: nichts
- Eingehend zu C: D (d=2) ← D zeigt auf C
- Ausgehend von A: B (Zyklus, blockiert)

Ergebnis: [A(d=1), C(d=1), D(d=2)]
```

### Acceptance Criteria

- [ ] AC 1: `graph_query_neighbors("NodeB")` findet Nodes die via **eingehende** Edges verbunden sind
  - Given: Edge A→B existiert
  - When: `graph_query_neighbors("B")` aufgerufen wird
  - Then: Node A erscheint in den Ergebnissen

- [ ] AC 2: Default-Verhalten ist bidirektional (`direction="both"`)
  - Given: Keine explizite `direction` angegeben
  - When: `graph_query_neighbors` aufgerufen wird
  - Then: Beide Richtungen werden durchsucht

- [ ] AC 3: `direction="outgoing"` gibt bisheriges Verhalten
  - Given: Edge A→B existiert
  - When: `graph_query_neighbors("B", direction="outgoing")` aufgerufen wird
  - Then: Leere Ergebnisse (B hat keine ausgehenden Edges zu A)

- [ ] AC 4: Multi-hop Traversal funktioniert bidirektional
  - Given: Kette A→B→C
  - When: `graph_query_neighbors("C", depth=2)` aufgerufen wird
  - Then: Sowohl B (distance=1) als auch A (distance=2) erscheinen

- [ ] AC 5: Keine Performance-Regression >20%
  - Given: Test-Dataset mit 1000 Nodes/5000 Edges
  - When: Query mit `direction="both"` ausgeführt wird
  - Then: Execution Time < 1.2× bisherige Zeit

- [ ] AC 6: Multiple Paths → Kürzester Pfad wird behalten
  - Given: Edges A→B (USES) und A→C→B (RELATED_TO)
  - When: `graph_query_neighbors("A", depth=2)` aufgerufen wird
  - Then: Node B erscheint nur einmal mit distance=1 (nicht distance=2)

- [ ] AC 7: Cycle Detection verhindert Endlosschleifen
  - Given: Zyklischer Graph A→B→C→A
  - When: `graph_query_neighbors("A", depth=5)` aufgerufen wird
  - Then: Query terminiert, jeder Node erscheint maximal einmal

## Additional Context

### Dependencies

- PostgreSQL (WITH RECURSIVE CTE Support) ✅ bereits vorhanden
- Keine neuen Python-Dependencies

### Testing Strategy

1. **Unit Tests** (mocked DB):
   - Parameter-Validierung für `direction`
   - Korrekte Durchreichung an DB-Layer

2. **Integration Tests** (echte DB):
   - Bidirektionale Neighbor-Suche
   - Multi-hop in beide Richtungen
   - Cycle Detection mit bidirektionalem Traversal

3. **Regression Tests**:
   - Alle existierenden Tests müssen weiterhin passen
   - `direction="outgoing"` muss identische Ergebnisse wie aktueller Code liefern

### Notes

- **Breaking Change Risiko:** Gering. Default `"both"` ist das "korrekte" Verhalten nach Graph-Theorie. User die explizit nur ausgehende Edges wollen, können `direction="outgoing"` setzen.

- **Performance:** UNION ALL ist performanter als OR in WHERE-Klausel. PostgreSQL kann beide Branches parallel planen.

- **Alternative verworfen:** UNION statt UNION ALL → Würde Duplikate entfernen, aber DISTINCT ON (id) macht das bereits effizienter.
