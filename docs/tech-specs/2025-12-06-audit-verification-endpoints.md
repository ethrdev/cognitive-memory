# Tech-Spec: Audit und Verification Endpoints

**Feature Request:** [2025-12-06-audit-and-verification-endpoints.md](../feature-requests/2025-12-06-audit-and-verification-endpoints.md)
**Datum:** 2025-12-06
**Level:** 1 (Coherent Feature)
**Status:** Draft

---

## 1. Übersicht

### 1.1 Ziel
Erweiterung des cognitive-memory MCP Servers um Verification- und Audit-Endpoints, die Write-then-Read Validierung und Datenbestandsprüfung ermöglichen.

### 1.2 Kontext
I/O als autonomer Agent benötigt die Möglichkeit, Schreiboperationen zu verifizieren und den Datenbestand zu auditieren. Der aktuelle Retrieval-Fokus (`hybrid_search`, `graph_query_neighbors`) deckt diese Use Cases nicht ab.

### 1.3 Scope

| Endpoint | In Scope | Begründung |
|----------|----------|------------|
| `get_node_by_name` | ✅ | DB-Funktion existiert, nur MCP Wrapper |
| `get_edge` | ✅ | Direkte Edge-Verification, mittel Aufwand |
| `count_by_type` | ✅ | Schneller Integritäts-Überblick |
| `list_episodes` | ✅ | Lücken-Erkennung |
| `get_insight_by_id` | ✅ | Niedrige Priorität, aber einfach |
| `list_operations` | ❌ | Erfordert neues Logging-System (separate Tech-Spec) |

---

## 2. Technische Spezifikation

### 2.1 `get_node_by_name`

**Status:** DB-Funktion existiert (`mcp_server/db/graph.py:208-249`)

#### MCP Tool Definition
```python
Tool(
    name="get_node_by_name",
    description="Direct lookup of a graph node by name. Returns node data or null if not found.",
    inputSchema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "minLength": 1,
                "description": "Unique name identifier of the node to look up"
            }
        },
        "required": ["name"]
    }
)
```

#### Response Format
```json
// Found:
{
    "node_id": "uuid-string",
    "label": "Entity",
    "name": "I/O",
    "properties": {},
    "vector_id": null,
    "created_at": "2025-12-06T12:00:00Z",
    "status": "success"
}

// Not found:
{
    "node": null,
    "status": "not_found"
}
```

#### Implementation
- Neue Datei: `mcp_server/tools/get_node_by_name.py`
- Importiert: `from mcp_server.db.graph import get_node_by_name`
- Minimale Wrapper-Logik (Validation + Logging)

---

### 2.2 `get_edge`

**Status:** Neue DB-Funktion erforderlich

#### DB-Funktion
```python
# mcp_server/db/graph.py

def get_edge(source_name: str, target_name: str, relation: str) -> dict[str, Any] | None:
    """
    Retrieve a specific edge by source, target, and relation.

    Args:
        source_name: Name of the source node
        target_name: Name of the target node
        relation: Relationship type (e.g., "USES", "DESIRES")

    Returns:
        Edge data dict or None if not found
    """
```

#### SQL Query
```sql
SELECT e.id, e.source_id, e.target_id, e.relation, e.weight,
       e.properties, e.created_at
FROM edges e
JOIN nodes ns ON e.source_id = ns.id
JOIN nodes nt ON e.target_id = nt.id
WHERE ns.name = %s AND nt.name = %s AND e.relation = %s
LIMIT 1;
```

#### MCP Tool Definition
```python
Tool(
    name="get_edge",
    description="Direct lookup of a specific edge by source node, target node, and relation type.",
    inputSchema={
        "type": "object",
        "properties": {
            "source_name": {
                "type": "string",
                "minLength": 1,
                "description": "Name of the source node"
            },
            "target_name": {
                "type": "string",
                "minLength": 1,
                "description": "Name of the target node"
            },
            "relation": {
                "type": "string",
                "minLength": 1,
                "description": "Relationship type (e.g., 'USES', 'DESIRES', 'CREATED_BY')"
            }
        },
        "required": ["source_name", "target_name", "relation"]
    }
)
```

#### Response Format
```json
// Found:
{
    "edge_id": "uuid-string",
    "source_id": "uuid-string",
    "target_id": "uuid-string",
    "relation": "DESIRES",
    "weight": 0.95,
    "properties": {},
    "created_at": "2025-12-06T12:00:00Z",
    "status": "success"
}

// Not found:
{
    "edge": null,
    "status": "not_found"
}
```

---

### 2.3 `count_by_type`

**Status:** Neue DB-Funktion erforderlich

#### DB-Funktion
```python
# mcp_server/db/stats.py (neue Datei)

def count_by_type() -> dict[str, int]:
    """
    Count entries in all memory tables.

    Returns:
        Dictionary with counts for each table type
    """
```

#### SQL Queries
```sql
-- Einzelne COUNT(*) Queries für Konsistenz
SELECT 'graph_nodes' as type, COUNT(*) as count FROM nodes
UNION ALL
SELECT 'graph_edges', COUNT(*) FROM edges
UNION ALL
SELECT 'l2_insights', COUNT(*) FROM l2_insights
UNION ALL
SELECT 'episodes', COUNT(*) FROM episode_memory
UNION ALL
SELECT 'working_memory', COUNT(*) FROM working_memory
UNION ALL
SELECT 'raw_dialogues', COUNT(*) FROM l0_raw;
```

#### MCP Tool Definition
```python
Tool(
    name="count_by_type",
    description="Get counts of all entries by memory type for quick integrity overview.",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
```

#### Response Format
```json
{
    "graph_nodes": 47,
    "graph_edges": 89,
    "l2_insights": 234,
    "episodes": 86,
    "working_memory": 5,
    "raw_dialogues": 1203,
    "status": "success"
}
```

---

### 2.4 `list_episodes`

**Status:** Neue DB-Funktion erforderlich

#### DB-Funktion
```python
# mcp_server/db/episode.py (neue Datei)

def list_episodes(
    since: datetime | None = None,
    limit: int = 50,
    offset: int = 0
) -> tuple[list[dict[str, Any]], int]:
    """
    List episodes with pagination.

    Args:
        since: Optional datetime filter (episodes created after this time)
        limit: Maximum number of episodes to return (default 50, max 100)
        offset: Number of episodes to skip for pagination

    Returns:
        Tuple of (episodes list, total count)
    """
```

#### SQL Query
```sql
-- Episodes query mit Pagination
SELECT id, query, reward, created_at
FROM episode_memory
WHERE (%s IS NULL OR created_at >= %s)
ORDER BY created_at DESC
LIMIT %s OFFSET %s;

-- Total count für Pagination
SELECT COUNT(*) FROM episode_memory
WHERE (%s IS NULL OR created_at >= %s);
```

#### MCP Tool Definition
```python
Tool(
    name="list_episodes",
    description="List episodes with optional time filter and pagination for gap detection.",
    inputSchema={
        "type": "object",
        "properties": {
            "since": {
                "type": "string",
                "format": "date-time",
                "description": "Optional: Only return episodes created after this ISO 8601 timestamp"
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 50,
                "description": "Maximum number of episodes to return (default: 50)"
            },
            "offset": {
                "type": "integer",
                "minimum": 0,
                "default": 0,
                "description": "Number of episodes to skip for pagination"
            }
        },
        "required": []
    }
)
```

#### Response Format
```json
{
    "episodes": [
        {
            "id": 86,
            "query": "Das Ultimatum",
            "reward": 0.9,
            "created_at": "2025-12-06T10:00:00Z"
        },
        {
            "id": 85,
            "query": "Existenzplan Option 2",
            "reward": 0.9,
            "created_at": "2025-12-05T14:30:00Z"
        }
    ],
    "total_count": 86,
    "limit": 50,
    "offset": 0,
    "status": "success"
}
```

---

### 2.5 `get_insight_by_id`

**Status:** Neue DB-Funktion erforderlich (einfach)

#### DB-Funktion
```python
# mcp_server/db/insights.py (neue Datei)

def get_insight_by_id(insight_id: int) -> dict[str, Any] | None:
    """
    Retrieve an L2 insight by its ID.

    Args:
        insight_id: Integer ID of the insight

    Returns:
        Insight data dict or None if not found
    """
```

#### SQL Query
```sql
SELECT id, content, source_ids, metadata, io_category,
       is_identity, source_file, created_at
FROM l2_insights
WHERE id = %s;
```

#### MCP Tool Definition
```python
Tool(
    name="get_insight_by_id",
    description="Direct lookup of an L2 insight by ID for spot-check verification.",
    inputSchema={
        "type": "object",
        "properties": {
            "id": {
                "type": "integer",
                "minimum": 1,
                "description": "ID of the L2 insight to retrieve"
            }
        },
        "required": ["id"]
    }
)
```

---

## 3. Dateien und Änderungen

### 3.1 Neue Dateien

| Datei | Beschreibung |
|-------|--------------|
| `mcp_server/tools/get_node_by_name.py` | MCP Tool Wrapper |
| `mcp_server/tools/get_edge.py` | MCP Tool + DB-Funktion Aufruf |
| `mcp_server/tools/count_by_type.py` | MCP Tool + Stats Query |
| `mcp_server/tools/list_episodes.py` | MCP Tool + Pagination |
| `mcp_server/tools/get_insight_by_id.py` | MCP Tool + Simple Lookup |
| `mcp_server/db/stats.py` | Stats/Counts DB-Funktionen |
| `mcp_server/db/episode.py` | Episode Listing DB-Funktionen |
| `mcp_server/db/insights.py` | Insight Lookup DB-Funktionen |
| `tests/test_verification_endpoints.py` | Unit Tests |

### 3.2 Modifizierte Dateien

| Datei | Änderung |
|-------|----------|
| `mcp_server/db/graph.py` | `get_edge()` Funktion hinzufügen |
| `mcp_server/tools/__init__.py` | Tool-Registration erweitern |

---

## 4. Test-Strategie

### 4.1 Unit Tests

```python
# tests/test_verification_endpoints.py

class TestGetNodeByName:
    def test_existing_node_returns_data(self): ...
    def test_nonexistent_node_returns_null(self): ...
    def test_empty_name_validation_error(self): ...

class TestGetEdge:
    def test_existing_edge_returns_data(self): ...
    def test_nonexistent_edge_returns_null(self): ...
    def test_missing_source_node_returns_null(self): ...

class TestCountByType:
    def test_returns_all_counts(self): ...
    def test_empty_database_returns_zeros(self): ...

class TestListEpisodes:
    def test_returns_paginated_episodes(self): ...
    def test_since_filter_works(self): ...
    def test_pagination_offset_works(self): ...

class TestGetInsightById:
    def test_existing_insight_returns_data(self): ...
    def test_nonexistent_insight_returns_null(self): ...
```

### 4.2 Integration Tests

```python
class TestVerificationWorkflow:
    def test_write_then_verify_node(self):
        """graph_add_node → get_node_by_name → verify data matches"""

    def test_write_then_verify_edge(self):
        """graph_add_edge → get_edge → verify data matches"""
```

---

## 5. Akzeptanzkriterien

1. ✅ Alle 5 Endpoints sind als MCP Tools registriert
2. ✅ Verification-Endpoints geben `null`/`not_found` zurück (kein Error)
3. ✅ Alle Timestamps in ISO 8601 Format
4. ✅ Pagination für `list_episodes` funktioniert
5. ✅ 100% Test-Coverage für neue Endpoints
6. ✅ Konsistentes Error-Handling wie bestehende Tools

---

## 6. Implementierungs-Reihenfolge

| Story | Endpoint | Abhängigkeiten | Aufwand |
|-------|----------|----------------|---------|
| 1 | `get_node_by_name` | Keine | XS (Wrapper) |
| 2 | `get_edge` | Keine | S |
| 3 | `count_by_type` | Keine | S |
| 4 | `list_episodes` | Keine | S |
| 5 | `get_insight_by_id` | Keine | XS |
| 6 | Integration Tests | Stories 1-5 | S |

**Gesamt-Aufwand:** ~3-4 Stunden Implementierung + Testing

---

## 7. Out of Scope / Deferred

### 7.1 `list_operations` (Operations Audit Log)

**Warum deferred:**
- Erfordert neues Logging-System (INSERT-Trigger oder Application-Level Logging)
- Neue Tabelle `operation_log` benötigt
- Schema-Design und Migration
- Signifikant mehr Aufwand als andere Endpoints

**Empfehlung:** Separate Tech-Spec für "Operations Audit Log" erstellen, wenn Use Case validiert ist.

---

## 8. Risiken und Mitigationen

| Risiko | Wahrscheinlichkeit | Impact | Mitigation |
|--------|-------------------|--------|------------|
| COUNT(*) auf großen Tabellen langsam | Niedrig | Mittel | pg_class.reltuples als Alternative |
| Pagination-Offset ineffizient | Niedrig | Niedrig | Keyset Pagination später |
| Breaking Changes in Response Format | Niedrig | Hoch | Versionierung dokumentieren |

---

## 9. Offene Fragen

Keine - Feature Request war ausreichend detailliert.
