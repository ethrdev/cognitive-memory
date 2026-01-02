# Bug: dissonance_check VARCHAR/UUID Type Mismatch

**Gefunden von:** I/O
**Datum:** 2026-01-02
**Repository:** cognitive-memory
**Status:** ✅ Behoben (2026-01-02)

---

## Beschreibung

`dissonance_check` schlägt mit einem Database-Fehler fehl.

## Reproduktion

```python
dissonance_check(context_node='I/O', scope='recent')
```

## Erwartetes Verhalten

Dissonanz-Analyse mit strukturiertem Output (dissonances_found, dissonance_type, etc.)

## Tatsächliches Verhalten

```
Database connection failed: operator does not exist: character varying = uuid
LINE 8: ...ns ON CAST(e.properties->>'source_node' AS VARCHAR) = pns.id
                                                               ^
HINT: No operator matches the given name and argument types. You might need to add explicit type casts.
```

## Vermutete Ursache

Schema-Migrations-Problem. Die Query versucht VARCHAR mit UUID zu vergleichen ohne expliziten Cast.

## Workaround

Keiner bekannt. Tool ist aktuell nicht nutzbar.

---

## Fix

**Datei:** `mcp_server/analysis/dissonance.py`
**Zeilen:** 285-286 und 304-305

Die SQL-Query in `_fetch_edges()` verwendete `CAST(...AS VARCHAR)` zum Vergleich mit UUID-Spalten.

**Vorher:**
```sql
LEFT JOIN nodes pns ON CAST(e.properties->>'source_node' AS VARCHAR) = pns.id
```

**Nachher:**
```sql
LEFT JOIN nodes pns ON (e.properties->>'source_node')::uuid = pns.id
```

Der Cast zu `::uuid` statt `AS VARCHAR` ermöglicht den korrekten Vergleich mit der UUID-Spalte `nodes.id`.
