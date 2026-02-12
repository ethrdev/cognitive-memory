# Hybrid Search Fix Plan — Asymmetrische Filter & Tote Kanäle

**Erstellt:** 2026-02-11
**Quelle:** BMAD Party Mode Analyse (Winston, Amelia, Murat, Mary)
**Projekt:** cognitive-memory
**Betrifft:** `mcp_server/tools/__init__.py`, `mcp_server/db/graph.py`, `mcp_server/tools/graph_update_node.py` (neu)

---

## Zusammenfassung

hybrid_search läuft auf ~29% Kapazität. Drei von fünf RRF-Kanälen sind tot oder fehlkonfiguriert:

| Kanal | Gewicht | Status | Problem |
|-------|---------|--------|---------|
| L2 Semantic | 60% (geteilt) | Leer | Nur 2 Meta-Insights, keine Inhalts-Insights |
| L2 Keyword | 60% (geteilt) | Leer | Gleicher Grund |
| Episode Semantic | 60% (geteilt) | Funktional | Aber: `tags_filter` und `sector_filter` werden ignoriert |
| Episode Keyword | 60% (geteilt) | Funktional | Gleicher Mangel |
| Graph → L2 | 20% | Tot | Kein Node hat `vector_id` gesetzt |

**Ziel:** ~85% Kapazität durch 4 Code-Fixes + Daten-Workflow.

---

## Fix 1: `date_from` / `date_to` String-Parsing (P0)

### Problem

`date_from` und `date_to` werden als Strings aus `arguments.get()` extrahiert (Zeile 1503-1504), aber `validate_filter_params()` vergleicht sie mit `>` Operator — der auf Strings nur lexikographisch funktioniert. Die Downstream-Funktionen (`semantic_search`, `episode_semantic_search`) erwarten `datetime` Objekte für `created_at >= %s`.

### Datei

`mcp_server/tools/__init__.py`

### Exakte Stelle

Zeile 1503-1504, innerhalb `handle_hybrid_search()`:

```python
# VORHER (Zeile 1503-1504):
date_from = arguments.get("date_from")
date_to = arguments.get("date_to")
```

### Fix

```python
# NACHHER:
date_from_raw = arguments.get("date_from")
date_to_raw = arguments.get("date_to")

# Parse ISO-format strings to datetime objects
# (datetime bereits im File-Header importiert)
date_from = None
date_to = None
if date_from_raw is not None:
    try:
        date_from = datetime.fromisoformat(date_from_raw) if isinstance(date_from_raw, str) else date_from_raw
    except ValueError:
        return {
            "error": "Parameter validation failed",
            "details": f"Invalid date_from format: '{date_from_raw}'. Expected ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
            "tool": "hybrid_search",
        }
if date_to_raw is not None:
    try:
        date_to = datetime.fromisoformat(date_to_raw) if isinstance(date_to_raw, str) else date_to_raw
    except ValueError:
        return {
            "error": "Parameter validation failed",
            "details": f"Invalid date_to format: '{date_to_raw}'. Expected ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)",
            "tool": "hybrid_search",
        }
```

**Hinweis:** `from datetime import datetime` ist bereits im File-Header importiert. Kein zusätzlicher Import nötig.

### Verifikation

```
hybrid_search(query_text="test", date_from="2026-02-01", date_to="2026-02-11")
# Erwartung: Ergebnisse nur aus dem Zeitraum, kein Crash
```

---

## Fix 2: `tags_filter` + `sector_filter` für Episode-Suchen (P0)

### Problem

`episode_semantic_search()` und `episode_keyword_search()` akzeptieren nur `date_from`/`date_to`. Die `tags_filter` und `sector_filter` Parameter werden in `handle_hybrid_search()` nicht an sie weitergereicht (Zeile 1665-1670). Die DB-Tabelle `episode_memory` hat seit Migration 041 eine `tags TEXT[]` Spalte mit GIN-Index — der Code nutzt sie nicht.

Effekt: `hybrid_search(query_text="...", tags_filter=["dark-romance"])` gibt ungetaggte Episodes zurück. Der Filter "lügt".

### Dateien

1. `mcp_server/tools/__init__.py` — Funktions-Signaturen + SQL
2. `mcp_server/tools/__init__.py` — `handle_hybrid_search()` Aufruf-Stellen

### Fix 2a: `episode_semantic_search()` erweitern

**Datei:** `mcp_server/tools/__init__.py`, ab Zeile 494

Signatur ändern:

```python
# VORHER (Zeile 494-500):
def episode_semantic_search(
    query_embedding: list[float],
    top_k: int,
    conn: Any,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[dict]:

# NACHHER:
def episode_semantic_search(
    query_embedding: list[float],
    top_k: int,
    conn: Any,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tags_filter: list[str] | None = None,
    sector_filter: list[str] | None = None,
) -> list[dict]:
```

WHERE-Clause erweitern. Nach dem bestehenden `date_filter_clause` Block (Zeile 527-536), einfügen:

```python
    # Tags filter using GIN index on tags column (like semantic_search)
    tags_filter_clause = ""
    tags_params = []
    if tags_filter is not None:
        tags_filter_clause = " AND tags @> %s::text[]"
        tags_params = [tags_filter]

    # Sector filter with COALESCE safety (Fix 4):
    # Episodes WITH memory_sector must match; WITHOUT (NULL) pass through
    sector_filter_clause = ""
    sector_params = []
    if sector_filter is not None:
        sector_filter_clause = " AND (metadata->>'memory_sector' = ANY(%s::text[]) OR metadata->>'memory_sector' IS NULL)"
        sector_params = [sector_filter]
```

SQL-Query anpassen (Zeile 542-549):

```python
    # VORHER:
    query = f"""
        SELECT id, query, reflection, reward, created_at, project_id,
               embedding <=> %s::vector AS distance
        FROM episode_memory
        WHERE project_id::TEXT = ANY((SELECT get_allowed_projects())::TEXT[])
        {date_filter_clause}
        ORDER BY distance
        LIMIT %s;
        """
    params = [query_embedding] + date_params + [top_k]

    # NACHHER:
    query = f"""
        SELECT id, query, reflection, reward, created_at, project_id,
               embedding <=> %s::vector AS distance
        FROM episode_memory
        WHERE project_id::TEXT = ANY((SELECT get_allowed_projects())::TEXT[])
        {date_filter_clause}
        {tags_filter_clause}
        {sector_filter_clause}
        ORDER BY distance
        LIMIT %s;
        """
    params = [query_embedding] + date_params + tags_params + sector_params + [top_k]
```

Logging erweitern (Zeile 557-565):

```python
    # VORHER:
    if date_from or date_to:
        logger.debug(
            "Pre-filter applied to episode_semantic_search",
            extra={
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "results_count": len(results),
            }
        )

    # NACHHER:
    if date_from or date_to or tags_filter or sector_filter:
        logger.debug(
            "Pre-filter applied to episode_semantic_search",
            extra={
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "tags_filter": tags_filter,
                "sector_filter": sector_filter,
                "results_count": len(results),
            }
        )
```

### Fix 2b: `episode_keyword_search()` erweitern

**Datei:** `mcp_server/tools/__init__.py`, ab Zeile 587

Identisches Pattern wie 2a. Signatur:

```python
# VORHER (Zeile 587-593):
def episode_keyword_search(
    query_text: str,
    top_k: int,
    conn: Any,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    language: str = "simple"
) -> list[dict]:

# NACHHER:
def episode_keyword_search(
    query_text: str,
    top_k: int,
    conn: Any,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tags_filter: list[str] | None = None,
    sector_filter: list[str] | None = None,
    language: str = "simple"
) -> list[dict]:
```

Gleiche Filter-Clauses einfügen (nach Zeile 627), gleiche SQL-Erweiterung (Zeile 633-646):

```python
    # Tags + Sector filter (identisch zu episode_semantic_search)
    tags_filter_clause = ""
    tags_params = []
    if tags_filter is not None:
        tags_filter_clause = " AND tags @> %s::text[]"
        tags_params = [tags_filter]

    sector_filter_clause = ""
    sector_params = []
    if sector_filter is not None:
        sector_filter_clause = " AND metadata->>'memory_sector' = ANY(%s::text[])"
        sector_params = [sector_filter]
```

SQL anpassen:

```python
    query = f"""
        SELECT id, query, reflection, reward, created_at, project_id,
               ts_rank(
                   to_tsvector('{language}', query || ' ' || reflection),
                   plainto_tsquery('{language}', %s)
               ) AS rank
        FROM episode_memory
        WHERE to_tsvector('{language}', query || ' ' || reflection)
              @@ plainto_tsquery('{language}', %s)
          AND project_id::TEXT = ANY((SELECT get_allowed_projects())::TEXT[])
        {date_filter_clause}
        {tags_filter_clause}
        {sector_filter_clause}
        ORDER BY rank DESC
        LIMIT %s;
        """
    params = [query_text, query_text] + date_params + tags_params + sector_params + [top_k]
```

### Fix 2c: `handle_hybrid_search()` — Filter durchreichen

**Datei:** `mcp_server/tools/__init__.py`, Zeile 1665-1670

```python
# VORHER (Zeile 1660-1670):
# Story 9-4: Episodes not filtered by sector (future enhancement)
# Story 9.3.1: Episodes filtered by date range only
episode_semantic_results = episode_semantic_search(
    query_embedding, top_k, conn, date_from, date_to
) if run_episode_semantic else []
episode_keyword_results = episode_keyword_search(
    query_text, top_k, conn, date_from, date_to
) if run_episode_keyword else []

# NACHHER:
# Episodes filtered by all available filters (date, tags, sector)
episode_semantic_results = episode_semantic_search(
    query_embedding, top_k, conn, date_from, date_to,
    tags_filter, sector_filter
) if run_episode_semantic else []
episode_keyword_results = episode_keyword_search(
    query_text, top_k, conn, date_from, date_to,
    tags_filter, sector_filter
) if run_episode_keyword else []
```

Kommentar auf Zeile 1662-1663 entfernen (er behauptet "Episodes not filtered by sector" — das stimmt nach dem Fix nicht mehr).

### Verifikation

```
# Schritt 1: Manuell eine Episode taggen (direkt in DB oder via store_episode)
# Schritt 2: hybrid_search mit tags_filter
hybrid_search(query_text="dark romance", tags_filter=["dark-romance"])
# Erwartung: NUR getaggte Episodes, nicht alle

# Schritt 3: Ohne tags_filter
hybrid_search(query_text="dark romance")
# Erwartung: Alle relevanten Episodes (Regression-Check)
```

### Achtung

**Reihenfolge beachten:** Zuerst mindestens 5-10 Episodes taggen, DANN den Fix deployen. Sonst liefert `tags_filter` korrekt 0 Ergebnisse — was technisch korrekt aber nutzlos ist.

---

## Fix 3: `graph_update_node` — Neues MCP-Tool (P0)

### Problem

Graph-Nodes können bei Erstellung einen `vector_id` bekommen. Aber bestehende 138 Nodes haben keinen. Es gibt keine MCP-Funktion um `vector_id` nachträglich zu setzen. Die DB-Funktion `update_node_properties()` in `db/graph.py:370` existiert — aber sie updated nur `properties` (JSONB), nicht `vector_id` (INTEGER FK).

### Architektur-Entscheidung

**Bestehende DB-Schicht wiederverwenden.** `update_node_properties()` in `db/graph.py:370` wird um `vector_id` Support erweitert. Der Tool-Handler ruft die DB-Funktion auf — kein rohes SQL im Handler.

### Schritt 1: DB-Funktion erweitern

**Datei:** `mcp_server/db/graph.py`, Funktion `update_node_properties()` ab Zeile 370

```python
# VORHER (Zeile 370):
async def update_node_properties(node_id: str, new_properties: dict[str, Any]) -> dict[str, Any]:

# NACHHER:
async def update_node_properties(
    node_id: str,
    new_properties: dict[str, Any] | None = None,
    vector_id: int | None = None,
) -> dict[str, Any]:
```

SQL-Query erweitern (Zeile 393-401):

```python
    # VORHER:
    cursor.execute(
        """
        UPDATE nodes
        SET properties = properties || %s::jsonb
        WHERE id = %s::uuid
        RETURNING id, label, name, properties, vector_id, created_at;
        """,
        (json.dumps(new_properties), node_id),
    )

    # NACHHER:
    set_clauses = []
    params = []

    if new_properties is not None:
        set_clauses.append("properties = properties || %s::jsonb")
        params.append(json.dumps(new_properties))

    if vector_id is not None:
        set_clauses.append("vector_id = %s")
        params.append(vector_id)

    if not set_clauses:
        raise ValueError("At least one of new_properties or vector_id must be provided")

    params.append(node_id)

    cursor.execute(
        f"""
        UPDATE nodes
        SET {', '.join(set_clauses)}
        WHERE id = %s::uuid
        RETURNING id, label, name, properties, vector_id, created_at;
        """,
        params,
    )
```

### Schritt 2: Tool-Handler erstellen

**Datei:** `mcp_server/tools/graph_update_node.py` (neu)

```python
"""
graph_update_node Tool Implementation

MCP tool for updating existing graph node properties and vector_id.
Enables retroactive linking of graph nodes to L2 insights.
Delegates to db/graph.py:update_node_properties() for DB operations.

Created: 2026-02-11 (Hybrid Search Fix Plan)
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.graph import get_node_by_name, update_node_properties
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata

logger = logging.getLogger(__name__)


async def handle_graph_update_node(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Update an existing graph node's properties and/or vector_id.

    Lookup by name (not UUID) for ergonomic MCP usage.
    Delegates to update_node_properties() in db/graph.py.

    Args:
        arguments: Tool arguments containing name, properties, vector_id

    Returns:
        Dict with updated node data or error
    """
    try:
        project_id = get_current_project()

        name = arguments.get("name")
        properties = arguments.get("properties")
        vector_id = arguments.get("vector_id")

        # Validation
        if not name or not isinstance(name, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'name' parameter (must be non-empty string)",
                "tool": "graph_update_node",
            }, project_id)

        if properties is not None and not isinstance(properties, dict):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'properties' parameter (must be object/dict)",
                "tool": "graph_update_node",
            }, project_id)

        if vector_id is not None and (not isinstance(vector_id, int) or vector_id <= 0):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'vector_id' parameter (must be positive integer referencing l2_insights.id)",
                "tool": "graph_update_node",
            }, project_id)

        if properties is None and vector_id is None:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "At least one of 'properties' or 'vector_id' must be provided",
                "tool": "graph_update_node",
            }, project_id)

        # Lookup node by name
        node = await get_node_by_name(name)
        if not node:
            return add_response_metadata({
                "error": "Node not found",
                "details": f"No node with name '{name}' exists",
                "tool": "graph_update_node",
            }, project_id)

        # Delegate to DB layer
        result = await update_node_properties(
            node_id=node["id"],
            new_properties=properties,
            vector_id=vector_id,
        )

        logger.info(f"Updated node: name={name}, vector_id={vector_id}")
        return add_response_metadata({
            "node_id": result["id"],
            "name": result["name"],
            "label": result["label"],
            "properties": result["properties"],
            "vector_id": result["vector_id"],
            "status": "success",
        }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in graph_update_node: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_update_node",
        }, get_current_project())
```

### Registrierung in `mcp_server/tools/__init__.py`

**1. Import hinzufügen** (bei den anderen graph imports, ~Zeile 55-58):

```python
from mcp_server.tools.graph_update_node import handle_graph_update_node
```

**2. Tool-Definition hinzufügen** (nach `graph_add_node` Definition, ~Zeile 2911):

```python
        Tool(
            name="graph_update_node",
            description="Update an existing graph node's properties and/or vector_id. Lookup by name. Properties are merged (not replaced). Use this to retroactively link nodes to L2 insights via vector_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the node to update (exact match)",
                    },
                    "properties": {
                        "type": "object",
                        "description": "Properties to merge into existing properties (additive, not replacing)",
                    },
                    "vector_id": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Foreign key to l2_insights.id — links this node to an L2 insight for graph search",
                    },
                },
                "required": ["name"],
            },
        ),
```

**3. Handler-Mapping hinzufügen** (~Zeile 3507, bei den anderen graph handlers):

```python
"graph_update_node": handle_graph_update_node,
```

**4. Dispatch-Funktion hinzufügen** (~Zeile 3594, bei den anderen graph dispatchers):

```python
        async def graph_update_node(arguments: dict[str, Any]) -> dict[str, Any]:
            return await handle_graph_update_node(arguments)
```

### Verifikation

```
# Schritt 1: Bestehenden Node prüfen
get_node_by_name(name="I/O")
# Erwartung: vector_id ist null

# Schritt 2: L2 Insight erstellen
compress_to_l2_insight(content="[self] ...", source_ids=[], tags=["identitaet"])
# Notiere returned ID, z.B. 5

# Schritt 3: Node updaten
graph_update_node(name="I/O", vector_id=5)
# Erwartung: status=success, vector_id=5

# Schritt 4: hybrid_search mit Graph-Kanal testen
hybrid_search(query_text="I/O Identität")
# Erwartung: graph_results_count > 0
```

---

## Fix 4: `sector_filter` für Episodes — COALESCE-Safety (P1)

### Problem

Episodes speichern `memory_sector` in der `metadata` JSONB-Spalte (falls gesetzt). Aber die meisten bestehenden Episodes haben kein `metadata` oder kein `memory_sector` darin. Fix 2 fügt den Filter-Code ein — aber er matcht nur wenn `metadata->>'memory_sector'` existiert.

### Entscheidung: Option A mit COALESCE-Safety

Strikte Filterung WENN `memory_sector` gesetzt ist, aber Episodes mit NULL-Sector passieren den Filter. So bricht nichts am Bestand, und neue Episodes (die automatisch klassifiziert werden) werden korrekt gefiltert.

### Umsetzung

Die `sector_filter_clause` in Fix 2a und 2b wie folgt formulieren:

```python
    # Sector filter with COALESCE safety:
    # - Episodes WITH memory_sector: must match filter
    # - Episodes WITHOUT memory_sector (NULL): pass through (not excluded)
    sector_filter_clause = ""
    sector_params = []
    if sector_filter is not None:
        sector_filter_clause = " AND (metadata->>'memory_sector' = ANY(%s::text[]) OR metadata->>'memory_sector' IS NULL)"
        sector_params = [sector_filter]
```

**Ergebnis:** Rückwärtskompatibel. Bestehende Episodes ohne `memory_sector` werden nicht fälschlich ausgefiltert. Neue Episodes mit gesetztem Sector werden korrekt gefiltert.

**Perspektive:** Wenn `store_episode` um automatische `classify_memory_sector()` erweitert wird (wie bei L2 bereits vorhanden), kann die NULL-Fallback-Klausel langfristig entfernt werden.

---

## Daten-Workflow: Selektives Taggen (Phase 2)

### Warum nicht alle 120 taggen?

~95% der Episodes sind self-referentiell (über I/O's eigene Patterns). Die meisten brauchen keine projekt-spezifischen Tags. Fokus auf die 20-30 die inhaltlich relevante Kategorien haben.

### Vorgehen

1. `list_episodes(limit=20, offset=0)` → Durchlesen, Tags zuweisen
2. Direkt in DB:
   ```sql
   UPDATE episode_memory SET tags = ARRAY['dark-romance', 'stil']
   WHERE id = 42;
   ```
3. Oder: Neue MCP-Funktion `update_episode` (optional, nicht im Scope dieses Plans)

### Prioritäts-Tags

| Tag | Beschreibung | Erwartete Anzahl |
|-----|-------------|------------------|
| `dark-romance` | Szenen, Stil, Feedback | ~5-8 |
| `drift` | Drift-Projekt, Layer-Lesungen | ~3-5 |
| `i-o-system` | System-Architektur, Hooks, Skills | ~10-15 |
| `cognitive-memory` | Memory-System, Bugs, Fixes | ~5-8 |
| `beziehung` | ethr-I/O Beziehungsdynamik | ~5-10 |
| `identitaet` | Eigene Patterns, Erkenntnisse | ~10-15 |
| `stil` | Schreibstil, Anti-Patterns | ~3-5 |

### Graph vector_id Linking

Nach jedem `compress_to_l2_insight` in `/io-end`:

1. Insight-ID merken
2. Prüfen ob relevanter Graph-Node existiert (`get_node_by_name`)
3. Falls ja: `graph_update_node(name="...", vector_id=<insight_id>)`
4. Falls nein: `graph_add_node(name="...", label="...", vector_id=<insight_id>)`

---

## Implementierungs-Reihenfolge

```
Schritt 1: Fix 1 (date_from/date_to)          ~15 min    → Sofort testbar
Schritt 2: Fix 3 (graph_update_node)           ~30 min    → Neues Tool, sofort nutzbar
Schritt 3: Tags auf 10 Episodes setzen         ~20 min    → Daten für Fix 2
Schritt 4: Fix 2 (episode tags_filter)         ~30 min    → Testbar gegen getaggte Episodes
Schritt 5: Fix 4 (sector_filter Entscheidung)  ~10 min    → Nach Erfahrung mit Fix 2
```

**Geschätzter Gesamtaufwand:** ~2 Stunden

**Erwartetes Ergebnis:** hybrid_search Kapazität von ~29% auf ~60-70% (sofort) und ~85% (nach 2-3 Wochen organischer L2-Befüllung via /io-end).

---

## Testplan (Murat)

### Before/After Matrix

| # | Test | Vor Fix | Nach Fix | Validierung |
|---|------|---------|----------|-------------|
| 1 | `hybrid_search(query_text="test", date_from="2026-02-01")` | Crash oder Fehlverhalten | Korrekte Filterung | Fix 1 |
| 2 | `hybrid_search(query_text="Kira", tags_filter=["dark-romance"])` auf ungetaggte Episodes | 5 Ergebnisse (Bug: Filter ignoriert) | 0 Episode-Ergebnisse | Fix 2 |
| 3 | Gleicher Query nach Taggen von 3 Episodes | 5 (Bug) | 3 (korrekt gefiltert) | Fix 2 + Daten |
| 4 | `hybrid_search(query_text="test")` ohne Filter | N Ergebnisse | N Ergebnisse (unverändert) | Regression |
| 5 | `graph_update_node(name="I/O", vector_id=5)` | Tool existiert nicht | success, vector_id=5 | Fix 3 |
| 6 | `hybrid_search(query_text="I/O")` nach vector_id Linking | graph_results_count: 0 | graph_results_count: >0 | Fix 3 + Daten |
| 7 | `source_type_filter: ["episode_memory"]` + `tags_filter` | Filter ignoriert | Nur getaggte Episodes | Fix 2 |

### Regression-Checks

- Baseline-Query ohne Filter: Ergebnis-Anzahl darf sich nicht ändern
- `list_episodes(tags=["dark-romance"])`: Muss weiterhin funktionieren (unabhängig von hybrid_search)
- `list_insights`: Muss weiterhin funktionieren
- Bestehende Graph-Queries (`get_node_by_name`, `graph_query_neighbors`): Unverändert

---

---

## Zusätzliche Fixes N1-N4 (Session 2, 2026-02-11)

*Identifiziert durch erweiterte Architektur-Analyse: 4 Party-Mode-Runden + Web-Recherche + Code-Counter-Check.*

### Fix N1: `memory_strength` Scoring-Formel (P0)

**Problem:** `tools/__init__.py:185` — `result["score"] = result["score"] * memory_strength`. Default memory_strength=0.5 halbiert jeden L2 Score. Kein Insight ohne explizites ms>0.5 kann jemals höher ranken als ein Episode mit gleichem RRF-Score.

**Fix:** `result["score"] = result["score"] * (0.5 + memory_strength)`

| ms | Faktor (alt) | Faktor (neu) |
|----|-------------|-------------|
| 0.0 | 0.0 (unsichtbar) | 0.5 (herabgestuft) |
| 0.5 | 0.5 (Bug!) | 1.0 (neutral) |
| 0.9 | 0.9 | 1.4 (Boost) |

**Status:** Implementiert (2026-02-11).

### Fix N2: Graph-Gewicht auf 0.0 für Standard-Queries (P0)

**Problem:** `tools/__init__.py:866`, `get_adjusted_weights()` gibt `graph: 0.2` zurück. 138 Nodes, 0 mit vector_id. 20% Gewicht auf totem Kanal bestraft alle Ergebnisse.

**Fix:** `{"semantic": 0.75, "keyword": 0.25, "graph": 0.0}` mit TODO-Kommentar. Relational-Queries behalten `graph: 0.4`.

**Monitoring:** `SELECT COUNT(*) FROM nodes WHERE vector_id IS NOT NULL;` — bei >20: zurückdrehen auf `graph: 0.15-0.2`.

**Status:** Implementiert (2026-02-11).

### Fix N3: FTS Index Language Mismatch (P0)

**Problem:** Migration 001 Zeile 45: `CREATE INDEX idx_l2_fts ... to_tsvector('english', content)`. Runtime nutzt `language='simple'`. PostgreSQL matcht GIN-Index nur bei exakter tsvector-Config → Index wird NICHT benutzt, sequential scan auf jeder L2 Keyword-Query.

**Fix:** Migration 042: `DROP INDEX idx_l2_fts; CREATE INDEX idx_l2_fts ... to_tsvector('simple', content);`

**Status:** Migration 042 erstellt (2026-02-11). Muss ausgeführt werden.

### Fix N4: Fehlender Episode FTS Index (P1)

**Problem:** Kein FTS-Index auf `episode_memory`. `episode_keyword_search()` berechnet `to_tsvector('simple', query || ' ' || reflection)` pro Zeile bei jedem Query — sequential scan mit Expression-Evaluation.

**Fix:** Migration 042: `CREATE INDEX idx_episode_fts ... to_tsvector('simple', query || ' ' || reflection);`

**Status:** Migration 042 erstellt (2026-02-11). Muss ausgeführt werden.

---

## Status-Übersicht (2026-02-11)

| Fix | Beschreibung | Code | Migration | Server-Restart |
|-----|-------------|------|-----------|----------------|
| Fix 1 | date_from/date_to Parsing | Implementiert | — | Nötig |
| Fix 2 | Episode tags_filter/sector_filter | Implementiert | — | Nötig |
| Fix 3 | graph_update_node Tool | Implementiert | — | Nötig |
| Fix 4 | COALESCE-Safety sector_filter | Implementiert | — | Nötig |
| **N1** | **memory_strength Formel** | **Implementiert** | — | **Nötig** |
| **N2** | **Graph-Gewicht 0.0** | **Implementiert** | — | **Nötig** |
| **N3** | **FTS Index Mismatch** | — | **042 erstellt** | **Nötig** |
| **N4** | **Episode FTS Index** | — | **042 erstellt** | **Nötig** |

**Nächster Schritt:** Migration 042 ausführen → Server-Restart → Golden Queries Diff.

---

*Dieses Dokument enthält alle Informationen für die Umsetzung. Kein weiterer Kontext nötig.*
