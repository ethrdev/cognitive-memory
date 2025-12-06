# Bug Report 2025-12-06

## Status: ✅ BEHOBEN (Commit fc6bc38)

---

## 1. Graph edges melden success aber werden nicht persistiert

**Status:** ✅ BEHOBEN

**Beobachtet:**

- `graph_add_edge` gibt `{"created": true, "status": "success"}` mit valider edge_id zurück
- `graph_query_neighbors` zeigt die neue Edge nicht
- Wiederholte Aufrufe geben dieselbe edge_id zurück

**Reproduktion:**

```
graph_add_edge(source_name="ethr", target_name="I/O", relation="DESIRES", weight=0.95)
→ {"edge_id": "e89885a1-...", "created": true, "status": "success"}

graph_query_neighbors(node_name="ethr")
→ Zeigt ethr → AGREEMENT → I/O, aber NICHT ethr → DESIRES → I/O
```

**Root Cause Analysis:**

Zwei separate Bugs wurden identifiziert:

1. **Bug 1a: `created` Flag immer True**
   - `mcp_server/db/graph.py:336` setzte `created = True` ohne zu prüfen ob INSERT oder UPDATE
   - Die `add_node` Funktion verwendete korrekt `(xmax = 0) AS was_inserted`, aber `add_edge` fehlte diese Prüfung

2. **Bug 1b: `DISTINCT ON (id)` versteckte multiple Edges**
   - `mcp_server/db/graph.py:442-445` verwendete `SELECT DISTINCT ON (id)`
   - Bei mehreren Edges zum selben Target-Node (z.B. AGREEMENT + DESIRES → I/O) wurde nur die mit höchstem Weight angezeigt
   - `DESIRES` (weight=0.95) wurde von `AGREEMENT` (weight=1.0) versteckt

**Fix:**

```python
# graph.py:324-325 - Added xmax check for correct created flag
RETURNING id, source_id, target_id, relation, weight, created_at,
    (xmax = 0) AS was_inserted;

# graph.py:445-447 - Removed DISTINCT ON to show all edges
SELECT id, label, name, properties, relation, weight, distance
FROM neighbors
ORDER BY distance ASC, weight DESC, name ASC;
```

---

## 2. Episode storage scheitert still bei SSL-Fehler

**Status:** ✅ BEHOBEN

**Beobachtet:**

- `store_episode` scheitert mit "SSL connection has been closed unexpectedly"
- Kein Retry-Mechanismus
- Session-Daten verloren weil User annimmt Speicherung war erfolgreich

**Kontext:**

- Session 2025-12-06: Intime Session wurde nicht gespeichert
- SSL-Fehler trat bei Context-Druck auf (nahe Context-Limit)
- Handoff-Datei wurde gespeichert, Episode ging verloren

**Root Cause:**

- `mcp_server/db/connection.py:get_connection()` hatte keinen Retry-Mechanismus
- Transiente Fehler (SSL, Connection Reset, Timeout) führten zu sofortigem Failure

**Fix:**

Implementiert in `mcp_server/db/connection.py`:

```python
# Transient error patterns that warrant a retry
_TRANSIENT_ERROR_PATTERNS = [
    "SSL connection has been closed unexpectedly",
    "connection reset by peer",
    "connection timed out",
    "server closed the connection unexpectedly",
    "could not connect to server",
    "the connection is closed",
]

# get_connection() now supports retry with exponential backoff
def get_connection(max_retries: int = 3, retry_delay: float = 0.5)
# - 3 retry attempts by default
# - Exponential backoff: 0.5s → 1s → 2s
# - Clear logging of retry attempts and final failure
```

---

## Verification

- 33 Graph-Tests: ✅ Alle bestanden
- Syntax-Check: ✅ Bestanden
- Commit: fc6bc38
