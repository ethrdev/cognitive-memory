# Bug Report 2025-12-07

## Status: ✅ FIXED (2025-12-07)

---

## 1. graph_query_neighbors zeigt nur ausgehende Edges

**Status:** ✅ FIXED

**Beobachtet:**

- `graph_query_neighbors` findet nur Nodes die über **ausgehende** Edges verbunden sind
- **Eingehende** Edges werden ignoriert
- Nodes erscheinen "isoliert" obwohl sie eingehende Verbindungen haben

**Reproduktion:**

```
# Edge erstellen: A → B
graph_add_edge(source_name="Bedeutung-Projektion", target_name="People-Pleasing", relation="RELATED_TO")
→ {"created": true, "status": "success"}

# Von A aus abfragen → findet B ✅
graph_query_neighbors(node_name="Bedeutung-Projektion")
→ neighbors: [{"name": "People-Pleasing", "relation": "RELATED_TO", ...}]

# Von B aus abfragen → findet A NICHT ❌
graph_query_neighbors(node_name="People-Pleasing")
→ neighbors: []  # Leer, obwohl A→B existiert
```

**Erwartetes Verhalten:**

"Neighbors" in Graph-Theorie bedeutet alle verbundenen Nodes, unabhängig von Edge-Richtung. Die Abfrage von "People-Pleasing" sollte "Bedeutung-Projektion" als Nachbar zeigen.

**Root Cause:**

`mcp_server/db/graph.py:482-484`:

```sql
FROM edges e
JOIN nodes n ON e.target_id = n.id
WHERE e.source_id = %s::uuid
```

Die Query sucht nur nach Edges wo der Start-Node die `source_id` ist → nur ausgehende Edges.

---

## Fix Implementation (2025-12-07)

### Lösung: Neuer `direction` Parameter + Bidirektionale SQL-Query

**Parameter:**
- `direction="both"` → beide Richtungen (Default)
- `direction="outgoing"` → nur ausgehende (bisheriges Verhalten)
- `direction="incoming"` → nur eingehende

### Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `mcp_server/db/graph.py` | `query_neighbors()` mit UNION ALL für bidirektionale Query |
| `mcp_server/tools/graph_query_neighbors.py` | `direction` Parameter + Validierung |
| `mcp_server/tools/__init__.py` | MCP-Schema mit `direction` Enum |
| `tests/test_graph_query_neighbors.py` | 10 neue Tests für bidirektionales Verhalten |

### Tech-Spec

Vollständige Dokumentation: `docs/tech-specs/2025-12-07-bidirectional-graph-neighbors.md`

---

## Verification (nach Fix)

- [x] `graph_query_neighbors` findet eingehende Edges
- [x] Multi-hop Traversal funktioniert in beide Richtungen
- [x] Bestehende Tests passen (wurden angepasst)
- [x] Neue Tests für bidirektionales Verhalten (10 Tests hinzugefügt)
- [x] 27 Tests insgesamt bestanden

---

## Nutzung nach Fix

```python
# Alte Syntax funktioniert weiterhin (Default: direction="both")
graph_query_neighbors(node_name="People-Pleasing")
→ neighbors: [{"name": "Bedeutung-Projektion", "edge_direction": "incoming", ...}]  ✅

# Explizit nur ausgehende (bisheriges Verhalten)
graph_query_neighbors(node_name="People-Pleasing", direction="outgoing")
→ neighbors: []  # Korrekt, B hat keine ausgehenden Edges zu A

# Explizit nur eingehende
graph_query_neighbors(node_name="People-Pleasing", direction="incoming")
→ neighbors: [{"name": "Bedeutung-Projektion", "edge_direction": "incoming", ...}]
```

**Entdeckt von:** I/O, Session 2025-12-07
**Gefixt von:** Claude Code, Session 2025-12-07
