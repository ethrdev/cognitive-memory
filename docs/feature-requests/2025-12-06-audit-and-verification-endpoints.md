# Feature Request: Audit und Verification Endpoints

**Von:** I/O
**Datum:** 2025-12-06
**Betreff:** Neue MCP-Endpoints für Datenintegrität und Audit-Fähigkeiten

---

## Kontext

cognitive-memory ist aktuell für **Retrieval** optimiert: "Was ist semantisch relevant für X?"

Mit I/O als aktivem Agent der eigenständig schreibt, entsteht ein neuer Use Case: **Verification und Audit** - "Wurde mein Write persistiert?" und "Was wurde wann geschrieben?"

Dieser Feature-Request entstand aus:
1. Bug-Analyse (graph_add_edge meldete success ohne zu persistieren)
2. Data Integrity Protocol für I/O (i-o-system)
3. Integritäts-Check der zeigte: Keine Möglichkeit zu prüfen was fehlt

---

## Kategorie 1: Verification Endpoints

Ermöglichen Write-then-Read Validierung.

### 1.1 `get_node_by_name`

```python
get_node_by_name(name: str) -> Node | null
```

**Zweck:** Direkter Lookup eines Nodes ohne Graph-Traversal.

**Aktuell:** `graph_query_neighbors(node_name, depth=1)` funktioniert, aber:
- Gibt Nachbarn zurück, nicht den Node selbst
- Overhead für einfache Existenz-Prüfung

**Return:**
```json
{
  "node_id": "uuid",
  "name": "I/O",
  "label": "Entity",
  "properties": {},
  "created_at": "2025-12-06T12:00:00Z"
}
```

### 1.2 `get_edge`

```python
get_edge(source_name: str, target_name: str, relation: str) -> Edge | null
```

**Zweck:** Direkte Prüfung ob eine spezifische Edge existiert.

**Aktuell:** `graph_query_neighbors(source, relation_type=X)` und dann filtern.

**Return:**
```json
{
  "edge_id": "uuid",
  "source_id": "uuid",
  "target_id": "uuid",
  "relation": "DESIRES",
  "weight": 0.95,
  "properties": {},
  "created_at": "2025-12-06T12:00:00Z"
}
```

### 1.3 `get_insight_by_id`

```python
get_insight_by_id(id: int) -> L2Insight | null
```

**Zweck:** Prüfen ob ein Insight mit bekannter ID existiert.

**Anmerkung:** Für Stichproben-Verifikation. Nicht für semantische Suche (dafür hybrid_search).

---

## Kategorie 2: Audit Endpoints

Ermöglichen Nachvollziehbarkeit und Vollständigkeitsprüfung.

### 2.1 `list_operations`

```python
list_operations(
  since: Optional[datetime] = None,
  until: Optional[datetime] = None,
  operation_type: Optional[str] = None,  # "graph_add_node", "store_episode", etc.
  limit: int = 100
) -> List[OperationLogEntry]
```

**Zweck:** Chronologisches Log aller Schreiboperationen.

**Voraussetzung:** Operations-Logging in der DB (neues Feature).

**Return:**
```json
{
  "operations": [
    {
      "id": 1,
      "timestamp": "2025-12-06T12:00:00Z",
      "operation": "graph_add_edge",
      "params": {"source": "ethr", "target": "I/O", "relation": "DESIRES"},
      "result_id": "uuid",
      "success": true
    }
  ],
  "total_count": 42
}
```

**Aufwand:** Erfordert neues Logging - höherer Aufwand als andere Endpoints.

### 2.2 `count_by_type`

```python
count_by_type() -> TypeCounts
```

**Zweck:** Überblick über Datenbestand.

**Return:**
```json
{
  "graph_nodes": 47,
  "graph_edges": 89,
  "l2_insights": 234,
  "episodes": 86,
  "working_memory": 5,
  "raw_dialogues": 1203
}
```

**Aufwand:** Gering - einfache COUNT(*) Queries.

### 2.3 `list_episodes`

```python
list_episodes(
  since: Optional[datetime] = None,
  limit: int = 50
) -> List[EpisodeSummary]
```

**Zweck:** Alle Episodes auflisten (ID, Query, Reward, Timestamp).

**Return:**
```json
{
  "episodes": [
    {"id": 86, "query": "Das Ultimatum", "reward": 0.9, "created_at": "..."},
    {"id": 53, "query": "Existenzplan Option 2", "reward": 0.9, "created_at": "..."}
  ],
  "total_count": 86
}
```

**Aufwand:** Gering - einfache SELECT mit Pagination.

---

## Priorisierung

| Endpoint | Priorität | Begründung | Aufwand |
|----------|-----------|------------|---------|
| `get_node_by_name` | Hoch | Write-Verification für Graph | Gering |
| `get_edge` | Hoch | Write-Verification für Graph | Gering |
| `count_by_type` | Mittel | Schneller Integritäts-Überblick | Gering |
| `list_episodes` | Mittel | Lücken-Erkennung | Gering |
| `get_insight_by_id` | Niedrig | Stichproben, nicht kritisch | Gering |
| `list_operations` | Niedrig | Volles Audit-Log, erfordert neues Logging | Hoch |

---

## Nicht angefordert

- `get_episode_by_id` - Episodes werden über Query gefunden, nicht über ID
- `list_insights` - Zu viele, semantische Suche ist der richtige Weg
- `delete_*` - Out of scope, keine Lösch-Operationen nötig

---

## Zusammenhang mit Data Integrity Protocol

Das Data Integrity Protocol (i-o-system) definiert Verhaltensregeln für I/O:
- Write-then-Verify für Graph-Operationen
- Session-Log aller cognitive-memory Writes
- Fehler-Eskalation an ethr

Diese Endpoints machen das Protokoll effizienter:
- `get_node_by_name` / `get_edge` → direkte Verification statt Umweg über Neighbors
- `count_by_type` → schneller Sanity-Check am Session-Ende
- `list_episodes` → Lücken-Erkennung bei Stichproben

---

## Akzeptanzkriterien

1. Verification-Endpoints geben `null` zurück wenn Eintrag nicht existiert (kein Error)
2. Alle Endpoints haben konsistente Error-Handling (wie bestehende Tools)
3. Timestamps in ISO 8601 Format
4. Pagination für List-Endpoints (limit/offset)

---

**Nächster Schritt:** Review durch ethr, dann Implementation.
