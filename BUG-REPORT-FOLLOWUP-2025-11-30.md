# Cognitive Memory MCP Server - Follow-Up Bug Report

**Date:** 2025-11-30
**Context:** Während der Verifikation der Bug-Fixes vom gleichen Tag
**Status:** ✅ **ALL BUGS FIXED** (2025-11-30)
**Severity:** LOW - Kern-Funktionalität funktioniert, Edge-Cases betroffen

---

## Summary

Bei der Verifikation der drei ursprünglichen Bug-Fixes wurden **drei Issues** entdeckt und behoben:
- **Bug #4:** graph_find_path UUID Parsing Error → ✅ FIXED
- **Bug #5:** store_dual_judge_scores Missing Metadata + Type Mismatch → ✅ FIXED
- **Bug #6:** f-string Format Error in dual_judge (Bonus) → ✅ FIXED

---

## BUG #4: `graph_find_path` UUID Parsing Error ✅ FIXED

### Severity: LOW
### Status: ✅ FIXED in commit 610aa8c

### Description
Die Funktion `graph_find_path` schlägt mit einem UUID Parsing Error fehl. Der Code versucht anscheinend ein Dict oder einen ungültigen String als UUID zu parsen.

### Fix Applied
**File:** `mcp_server/db/graph.py:580-595`

PostgreSQL returns UUID arrays as string representation `"{uuid1,uuid2}"` which psycopg2 may not automatically convert to Python lists. Added string-to-list parsing:

```python
# Bug #4 Fix: Handle UUID arrays that may be returned as strings
if isinstance(node_path, str):
    node_path = [
        uuid_str.strip()
        for uuid_str in node_path.strip("{}").split(",")
        if uuid_str.strip()
    ]
```

**Tests:** 30/30 graph tests pass

### Steps to Reproduce
```python
# Voraussetzung: Zwei verbundene Nodes existieren
graph_add_node(name="NodeA", label="Test")
graph_add_edge(source_name="NodeA", target_name="NodeB", relation="CONNECTS")

# Dann:
graph_find_path(
    start_node="NodeA",
    end_node="NodeB",
    max_depth=3
)
```

### Expected Behavior
```json
{
    "path_found": true,
    "path": ["NodeA", "NodeB"],
    "path_length": 1
}
```

### Actual Behavior
```json
{
    "error": "Database operation failed",
    "details": "Database connection failed: invalid input syntax for type uuid: \"{\"\nLINE 4: WHERE id = '{'::uuid;\n                    ^"
}
```

### Root Cause Analysis
Der Error `WHERE id = '{'::uuid` zeigt dass:
- Ein Dict `{...}` wird als String übergeben
- Nur das erste Zeichen `{` wird als UUID interpretiert
- Vermutlich wird ein Node-Objekt statt der Node-ID übergeben

### Suggested Fix
```python
# Vermutlich in der find_path Implementierung:
# FALSCH:
cursor.execute("WHERE id = %s::uuid", (node,))  # node ist ein dict

# RICHTIG:
cursor.execute("WHERE id = %s::uuid", (node['node_id'],))  # Oder:
cursor.execute("WHERE name = %s", (node_name,))  # Lookup by name
```

### Impact
- `graph_find_path` ist nicht nutzbar
- Workaround: `graph_query_neighbors` mit manueller Pfad-Verfolgung
- Kern-Graph-Funktionalität (add_node, add_edge, query_neighbors) funktioniert

---

## BUG #5: `store_dual_judge_scores` Missing Metadata + Type Mismatch ✅ FIXED

### Severity: LOW
### Status: ✅ FIXED in commit 610aa8c

### Description
Nach dem Fix für den Dict-Adapter schlägt `store_dual_judge_scores` mit einem fehlenden Column-Error fehl. Die Spalte `metadata` existiert nicht in der relevanten Tabelle. Zusätzlich wurde ein Type Mismatch entdeckt: `judge1_score`/`judge2_score` sind `FLOAT[]` Arrays, nicht JSONB.

### Fix Applied
**1. Migration:** `mcp_server/db/migrations/014_add_ground_truth_metadata.sql`
```sql
ALTER TABLE ground_truth ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
```

**2. Type Fix:** `mcp_server/tools/dual_judge.py:579-580`
```python
# BEFORE (wrong):
SET judge1_score = %s::jsonb,
    judge2_score = %s::jsonb,

# AFTER (correct):
SET judge1_score = %s::double precision[],
    judge2_score = %s::double precision[],
```

### Steps to Reproduce
```python
store_dual_judge_scores(
    query_id=1,
    query="Test query",
    docs=[
        {"id": 1, "content": "Relevant document"},
        {"id": 2, "content": "Unrelated document"}
    ]
)
```

### Expected Behavior
Tool sollte die Dokumente mit zwei AI-Judges evaluieren und Scores speichern.

### Actual Behavior
```json
{
    "error": "Evaluation failed",
    "details": "Database connection failed: column \"metadata\" does not exist\nLINE 11: metadata = COALESCE(metadata, '{}'::...\n                    ^"
}
```

### Root Cause Analysis
Der Code referenziert eine `metadata` Spalte die:
1. Nie in einer Migration erstellt wurde, ODER
2. In einer anderen Tabelle existiert als erwartet, ODER
3. Kürzlich zum Code hinzugefügt aber nicht zur DB migriert wurde

### Suggested Fix
```sql
-- Migration hinzufügen:
ALTER TABLE ground_truth_scores  -- oder relevante Tabelle
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';
```

### Impact
- Dual Judge Evaluation ist nicht nutzbar
- Betrifft nur IRR-Validierung (Advanced Feature)
- Kern-Memory-Funktionen (store, search, episodes) nicht betroffen

---

## Priority Assessment

| Bug | Severity | User Impact | Fix Complexity |
|-----|----------|-------------|----------------|
| #4 graph_find_path | LOW | Pfad-Suche nicht nutzbar | ~30 min |
| #5 metadata column | LOW | Dual Judge nicht nutzbar | ~10 min (Migration) |

### Empfohlene Reihenfolge:
1. **Bug #5 zuerst** - Einfacher Fix (nur Migration)
2. **Bug #4 danach** - Benötigt Code-Analyse

---

## Verification Test Plan

Nach den Fixes bitte folgende Tests ausführen:

### Bug #4 Verification:
```python
# 1. Nodes erstellen
graph_add_node(name="PathTest-Start", label="Test")
graph_add_node(name="PathTest-End", label="Test")

# 2. Edge erstellen
graph_add_edge(
    source_name="PathTest-Start",
    target_name="PathTest-End",
    relation="CONNECTS"
)

# 3. Pfad finden
result = graph_find_path(
    start_node="PathTest-Start",
    end_node="PathTest-End",
    max_depth=3
)

# Erwartung:
assert result["path_found"] == True
assert result["path_length"] == 1
```

### Bug #5 Verification:
```python
result = store_dual_judge_scores(
    query_id=1,
    query="Test query",
    docs=[{"id": 1, "content": "Test doc"}]
)

# Erwartung:
assert result["status"] == "success"
assert len(result["judge1_scores"]) > 0
```

---

## Current System Status

Nach allen Bug-Fixes (2025-11-30):

| Feature | Status |
|---------|--------|
| ping | ✅ |
| store_raw_dialogue | ✅ |
| update_working_memory | ✅ |
| compress_to_l2_insight | ✅ |
| hybrid_search | ✅ |
| graph_add_node | ✅ |
| graph_add_edge | ✅ |
| graph_query_neighbors | ✅ |
| graph_find_path | ✅ Fixed! |
| store_episode | ✅ |
| get_golden_test_results | ✅ |
| store_dual_judge_scores | ✅ Fixed! |

**Overall: 12/12 Tools funktional (100%)** 🎉

---

## BUG #6: f-string Format Error in dual_judge ✅ FIXED (Bonus)

### Severity: LOW
### Status: ✅ FIXED in commit 610aa8c

### Description
Während der Behebung von Bug #5 wurde ein zusätzlicher Fehler entdeckt: Ein ungültiger f-string Format Specifier in der Logging-Ausgabe.

### Error
```
Invalid format specifier '.3f if kappa is not None else 'N/A'' for object of type 'float'
```

### Fix Applied
**File:** `mcp_server/tools/dual_judge.py:507-511`

```python
# BEFORE (wrong - can't have conditional in format specifier):
f"kappa={kappa:.3f if kappa is not None else 'N/A'}"

# AFTER (correct):
kappa_str = f"{kappa:.3f}" if kappa is not None else "N/A"
f"kappa={kappa_str}"
```

---

## Appendix: Modified Files

| File | Bug | Change |
|------|-----|--------|
| `mcp_server/db/graph.py` | #4 | UUID array string parsing |
| `mcp_server/tools/dual_judge.py` | #5, #6 | Type fix + f-string fix |
| `mcp_server/db/migrations/014_add_ground_truth_metadata.sql` | #5 | New migration |
