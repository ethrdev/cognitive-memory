# Bug Report: MCP Server Async/Await Fehler (Detaillierte Analyse)

**Datum:** 2026-01-13
**Analysiert von:** I/O
**Repository:** cognitive-memory
**Severity:** HIGH
**Status:** ✅ FIXED (2026-01-14, commit 3b7582a)

---

## Executive Summary

Drei MCP-Tools scheitern mit async-bezogenen Fehlern. Nach Code-Analyse:
- **1 Bug ist eindeutig identifiziert** (fehlendes `await`)
- **2 Bugs erfordern weitere Untersuchung** (Context Manager Protokoll-Mismatch)

---

## Bug 1: `get_insight_by_id` - ✅ BEHOBEN

### Fehlermeldung
```json
{
  "error": "Database operation failed",
  "details": "'coroutine' object is not subscriptable"
}
```

### Ursache
**Datei:** `mcp_server/tools/get_insight_by_id.py`
**Zeile 60:**
```python
insight = get_insight_by_id(insight_id)  # ❌ FEHLENDES AWAIT
```

### Kontext
- Import in Zeile 15: `from mcp_server.db.insights import get_insight_by_id`
- Die importierte Funktion ist `async def` (`mcp_server/db/insights.py`, Zeile 20-72)
- Ohne `await` ist `insight` ein Coroutine-Objekt, nicht das Ergebnis
- `insight["id"]` auf einem Coroutine-Objekt erzeugt den Fehler

### Fix
```python
# Zeile 60 ändern von:
insight = get_insight_by_id(insight_id)

# zu:
insight = await get_insight_by_id(insight_id)
```

### Verifizierung
```bash
grep -n "insight = get_insight_by_id" mcp_server/tools/get_insight_by_id.py
# Zeile 60: insight = get_insight_by_id(insight_id)
```

---

## Bug 2: `get_insight_history` - ✅ BEHOBEN

### Fehlermeldung
```json
{
  "error": {
    "code": 500,
    "message": "Database operation failed",
    "details": "'_GeneratorContextManager' object does not support the asynchronous context manager protocol"
  }
}
```

### Analyse
**Datei:** `mcp_server/tools/insights/history.py`

Der Code in Zeile 92 sieht korrekt aus:
```python
insight = await get_insight_by_id(insight_id)  # ✓ Hat await
```

Der Code in Zeile 126 sieht auch korrekt aus:
```python
async with get_connection() as conn:  # ✓ Hat async with
```

### Das Problem
Die Fehlermeldung sagt `_GeneratorContextManager` (SYNC), nicht `_AsyncGeneratorContextManager` (ASYNC).

Aber `get_connection()` in `mcp_server/db/connection.py` ist mit `@asynccontextmanager` dekoriert (Zeile 114-115):
```python
@asynccontextmanager
async def get_connection(max_retries: int = 3, retry_delay: float = 0.5) -> AsyncIterator[connection]:
```

### Hypothesen
1. **Import-Konflikt:** Irgendwo wird eine andere `get_connection` Funktion importiert
2. **Runtime-Problem:** Der MCP Event Loop interferiert mit dem Async Context Manager
3. **Transitive Abhängigkeit:** Die Funktion `get_insight_by_id` in `db/insights.py` verwendet intern `async with get_connection()` - vielleicht liegt der Fehler dort

### Debug-Schritte
```bash
# Prüfen ob get_insight_by_id in db/insights.py korrekt ist
grep -n "async with get_connection" mcp_server/db/insights.py

# Prüfen ob es mehrere get_connection Funktionen gibt
grep -rn "def get_connection" mcp_server/
```

---

## Bug 3: `hybrid_search` - ✅ BEHOBEN

### Fehlermeldung
```json
{
  "error": "Tool execution failed",
  "details": "'_AsyncGeneratorContextManager' object does not support the context manager protocol"
}
```

### Analyse
**Datei:** `mcp_server/tools/__init__.py`

Der Code in Zeile 1377 sieht korrekt aus:
```python
async with get_connection() as conn:  # ✓ Hat async with
```

### Das Problem
Die Fehlermeldung sagt `_AsyncGeneratorContextManager` (ASYNC) wird mit SYNC `with` verwendet.

Aber der Code verwendet `async with`. Das widerspricht sich.

### Hypothesen
1. **Nested Context Manager:** Innerhalb von `semantic_search` oder `keyword_search` wird vielleicht ein sync `with` verwendet
2. **Exception-Handling:** Der Fehler könnte in einem `finally` Block entstehen
3. **Runtime-Isolation:** MCP Tools werden möglicherweise in einem isolierten Context ausgeführt

### Debug-Schritte
```bash
# Suche nach sync "with" in semantic_search/keyword_search
grep -n "with get_connection\|with conn" mcp_server/tools/__init__.py

# Prüfe ob psycopg2-Objekte korrekt verwendet werden
grep -n "with conn\|with cursor" mcp_server/tools/__init__.py
```

---

## Funktionierende Funktionen (Referenz)

Diese verwenden die gleichen Patterns und funktionieren:

| Tool | Datei | Pattern |
|------|-------|---------|
| `graph_add_node` | `tools/graph_add_node.py` | `async with get_connection()` |
| `graph_add_edge` | `tools/graph_add_edge.py` | `async with get_connection()` |
| `graph_query_neighbors` | `tools/graph_query_neighbors.py` | `async with get_connection()` |
| `list_episodes` | `tools/list_episodes.py` | `async with get_connection()` |

**Vergleichs-Analyse empfohlen:** Was machen diese Tools anders als die fehlerhaften?

---

## Empfohlene Fix-Reihenfolge

1. **Bug 1 zuerst fixen** - eindeutig identifiziert, einfacher Ein-Zeilen-Fix
2. **Nach Fix testen** - manchmal sind Fehler kettenreaktiv
3. **Bug 2 & 3 debuggen** - mit Logging oder Breakpoints

---

## Test-Strategie nach Fix

```python
# Integration Test für alle drei Tools
async def test_regression_async_await():
    """Verhindert zukünftige async/await Fehler."""

    # Test 1: get_insight_by_id
    result = await mcp_call("get_insight_by_id", {"id": 1})
    assert "error" not in result or result.get("status") == "not_found"

    # Test 2: get_insight_history
    result = await mcp_call("get_insight_history", {"insight_id": 1})
    assert "'coroutine'" not in str(result.get("details", ""))
    assert "'_GeneratorContextManager'" not in str(result.get("details", ""))

    # Test 3: hybrid_search
    result = await mcp_call("hybrid_search", {"query_text": "test"})
    assert "'_AsyncGeneratorContextManager'" not in str(result.get("details", ""))
```

---

## Appendix: Vollständige Stack Traces

Die originalen Fehlermeldungen enthalten keine vollständigen Stack Traces, da MCP-Fehler vom Server gefangen und als JSON zurückgegeben werden. Für vollständige Traces:

```bash
# MCP Server mit DEBUG logging starten
LOG_LEVEL=DEBUG python -m mcp_server 2>&1 | tee debug.log
```

---

*Dieser Report ersetzt bug-report-mcp-async-errors.md mit präziserer Analyse.*
