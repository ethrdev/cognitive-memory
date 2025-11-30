# Cognitive Memory MCP Server - Follow-Up Bug Report

**Date:** 2025-11-30
**Context:** Während der Verifikation der Bug-Fixes vom gleichen Tag
**Severity:** LOW - Kern-Funktionalität funktioniert, Edge-Cases betroffen

---

## Summary

Bei der Verifikation der drei ursprünglichen Bug-Fixes wurden **zwei neue Issues** entdeckt. Beide sind kleinere Probleme, die spezifische Features betreffen.

---

## BUG #4: `graph_find_path` UUID Parsing Error

### Severity: LOW

### Description
Die Funktion `graph_find_path` schlägt mit einem UUID Parsing Error fehl. Der Code versucht anscheinend ein Dict oder einen ungültigen String als UUID zu parsen.

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

## BUG #5: `store_dual_judge_scores` Missing Metadata Column

### Severity: LOW

### Description
Nach dem Fix für den Dict-Adapter schlägt `store_dual_judge_scores` mit einem fehlenden Column-Error fehl. Die Spalte `metadata` existiert nicht in der relevanten Tabelle.

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

Nach den ursprünglichen Fixes + diese zwei neuen Issues:

| Feature | Status |
|---------|--------|
| ping | ✅ |
| store_raw_dialogue | ✅ |
| update_working_memory | ✅ |
| compress_to_l2_insight | ✅ |
| hybrid_search | ✅ (mit custom weights) |
| graph_add_node | ✅ |
| graph_add_edge | ✅ (mit node dedup) |
| graph_query_neighbors | ✅ |
| graph_find_path | ❌ Bug #4 |
| store_episode | ✅ |
| get_golden_test_results | ✅ |
| store_dual_judge_scores | ❌ Bug #5 |

**Overall: 10/12 Tools funktional (83%)**

---

## Appendix: Related Files

Basierend auf dem ursprünglichen Bug-Fix-Report könnten folgende Dateien relevant sein:

- `src/tools/graph.py` - für Bug #4
- `src/tools/evaluation.py` - für Bug #5
- `migrations/` - für Bug #5 Schema-Fix
