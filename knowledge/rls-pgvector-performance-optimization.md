# RLS + pgvector: Performance-Optimierung

> Research Summary: 2026-01-22
> Source: Deep Research F4 - Row-Level Security mit pgvector
> Status: VALIDATED

## Executive Summary

Row-Level Security (RLS) kann bei pgvector-Operationen **10-30x Latenz-Overhead** verursachen, wenn nicht optimiert. Mit den richtigen Strategien lässt sich dieser Overhead auf **<10ms** reduzieren.

**Kritische Optimierungen:**
1. pgvector 0.8.0+ mit iterativen Scans
2. Subquery-Wrapping für Policy-Funktionen
3. IMMUTABLE-Funktionen für Prädikate
4. Partielle Indizes pro Mandant (bei Bedarf)

---

## Problem: Overfiltering

### Mechanismus
HNSW-Index liefert k Kandidaten → RLS filtert → Weniger als k Ergebnisse

```
HNSW sucht: k=10 Kandidaten
RLS-Filter: 90% nicht autorisiert
Ergebnis: 1 Treffer statt 10
→ Erneute Suche nötig → Latenz steigt
```

### Mathematisches Modell
```
T_RLS ≈ C·ln(N) + (k/s) · (T_filter + T_dist)

wobei:
- s = Selektivität (0.01 = nur 1% der Daten sichtbar)
- T_filter = Zeit für RLS-Policy-Evaluierung
- T_dist = Zeit für Distanzberechnung
```

Bei s=0.01 muss der Algorithmus ~100x mehr Kandidaten prüfen.

---

## Benchmark-Daten

### Latenz ohne vs. mit RLS (Standard-Konfiguration)

| Szenario | Ohne RLS | Mit Standard-RLS | Overhead |
|----------|----------|------------------|----------|
| Einfache ID-Prüfung (1k Zeilen) | 17 ms | 182 ms | 11x |
| HNSW Top-10 (1M Vektoren) | 8-12 ms | 150-400 ms | 15-30x |
| Aggregation (1k Zeilen) | 6.901 ms | 11.595 ms | 1.7x |

### Nach Optimierung

| Optimierung | Latenz | Verbesserung |
|-------------|--------|--------------|
| Subquery-Wrapping | 9 ms | 95% (von 179 ms) |
| IMMUTABLE-Funktionen | -54.5% | Signifikant |
| Iterative Scans (pgvector 0.8.0) | 13.1 ms | 9.4x schneller |
| Partielle Indizes | ~Baseline | ~100% |

---

## Optimierung 1: pgvector 0.8.0 Iterative Scans

### Konzept
Anstatt feste k Kandidaten zu liefern, iteriert der Index automatisch bis genügend autorisierte Ergebnisse gefunden sind.

### Aktivierung
```sql
-- Empfohlene Konfiguration
SET hnsw.iterative_scan = 'relaxed_order';
SET hnsw.max_scan_tuples = 20000;
```

### Modi

| Modus | Latenz | Recall | Use Case |
|-------|--------|--------|----------|
| OFF | Hoch | Gering | Legacy |
| strict_order | 28.8 ms | 100% | Exakte Reihenfolge |
| relaxed_order | 13.1 ms | 95-99% | Production (empfohlen) |

### Benchmark-Vergleich
```
Iterative Scan OFF:    123.3 ms (Overfiltering)
strict_order:           28.8 ms (4.3x schneller)
relaxed_order:          13.1 ms (9.4x schneller)
```

---

## Optimierung 2: Subquery-Wrapping (initPlan)

### Problem
```sql
-- SCHLECHT: Funktion wird pro Zeile evaluiert
CREATE POLICY tenant_policy ON l2_insights
  USING (project_id = current_setting('app.current_project'));
```

### Lösung
```sql
-- GUT: Funktion wird einmal pro Query evaluiert (initPlan)
CREATE POLICY tenant_policy ON l2_insights
  USING (project_id = (SELECT current_setting('app.current_project')));
```

### Benchmark
```
Ohne Wrapping:  179 ms
Mit Wrapping:     9 ms
Verbesserung:   95%
```

### Für Supabase auth.uid()
```sql
-- SCHLECHT
USING (user_id = auth.uid())

-- GUT
USING (user_id = (SELECT auth.uid()))
```

---

## Optimierung 3: IMMUTABLE + LEAKPROOF Funktionen

### Helper-Funktion für cognitive-memory
```sql
CREATE OR REPLACE FUNCTION get_current_project()
RETURNS TEXT AS $$
  SELECT current_setting('app.current_project', TRUE)
$$ LANGUAGE sql IMMUTABLE PARALLEL SAFE;

-- Oder mit LEAKPROOF (erlaubt frühere Filterung)
CREATE OR REPLACE FUNCTION get_allowed_projects()
RETURNS TEXT[] AS $$
  SELECT current_setting('app.allowed_projects', TRUE)::TEXT[]
$$ LANGUAGE sql IMMUTABLE LEAKPROOF PARALLEL SAFE;
```

### RLS-Policy mit Helper
```sql
CREATE POLICY project_isolation ON l2_insights
  FOR ALL
  USING (project_id = get_current_project())
  WITH CHECK (project_id = get_current_project());
```

### Hinweis
Die Funktion ist technisch nicht immutable (Wert ändert sich zwischen Transaktionen), aber **safe within transaction**. Dies ermöglicht Plan-Time-Evaluation mit 14x Performance-Verbesserung.

---

## Optimierung 4: Partielle Vektorindizes

### Konzept
Separate HNSW-Indizes pro Mandant eliminieren RLS-Overhead fast vollständig.

### Implementation
```sql
-- Index nur für Mandant 'io'
CREATE INDEX idx_l2_insights_io_embedding
  ON l2_insights USING hnsw(embedding vector_cosine_ops)
  WHERE project_id = 'io';

-- Index nur für Mandant 'aa'
CREATE INDEX idx_l2_insights_aa_embedding
  ON l2_insights USING hnsw(embedding vector_cosine_ops)
  WHERE project_id = 'aa';
```

### Query-Planner nutzt partiellen Index
```sql
-- Bei Query mit WHERE project_id = 'io'
-- wählt Planner automatisch idx_l2_insights_io_embedding
EXPLAIN ANALYZE
SELECT * FROM l2_insights
WHERE project_id = 'io'
ORDER BY embedding <=> '[...]'
LIMIT 10;
```

### Eigenschaften
| Aspekt | Bewertung |
|--------|-----------|
| Performance | Maximal (wie ohne RLS) |
| Speicher | Hoch (N Indizes) |
| Wartung | Aufwändig (Index pro Mandant) |
| Use Case | Wenige große Mandanten |

---

## Optimierung 5: GIN-Indizes für ACL

### Problem
Array-basierte Berechtigungen (z.B. `group_ids`) sind mit B-Tree ineffizient.

### Lösung
```sql
-- GIN-Index für Array-Spalte
CREATE INDEX idx_insights_groups ON l2_insights USING gin(group_ids);

-- RLS-Policy mit Array-Containment
CREATE POLICY group_access ON l2_insights
  USING (
    group_ids && (SELECT get_user_groups())::TEXT[]
  );
```

---

## Optimierung 6: Tabellenpartitionierung

### Konzept
Physische Trennung der Daten pro Mandant ermöglicht "Partition Pruning" im Query-Planner.

### Implementation
```sql
-- Partitionierte Haupttabelle
CREATE TABLE l2_insights (
  id SERIAL,
  project_id VARCHAR(50) NOT NULL,
  content TEXT,
  embedding vector(1536)
) PARTITION BY LIST (project_id);

-- Partitionen pro Mandant
CREATE TABLE l2_insights_io PARTITION OF l2_insights
  FOR VALUES IN ('io');
CREATE TABLE l2_insights_aa PARTITION OF l2_insights
  FOR VALUES IN ('aa');
-- ...

-- HNSW-Index pro Partition
CREATE INDEX ON l2_insights_io USING hnsw(embedding vector_cosine_ops);
CREATE INDEX ON l2_insights_aa USING hnsw(embedding vector_cosine_ops);
```

### Vorteile
- RLS-Policies pro Partition möglich
- Query-Planner schließt irrelevante Partitionen aus
- Physische Isolation der Mandanten-Daten

---

## Skalierungsempfehlungen

| Mandantenzahl | Vektoren/Mandant | Strategie |
|---------------|------------------|-----------|
| < 10 | < 100k | Einfaches RLS + Optimierte Policies |
| 10 - 100 | < 100k | RLS + Subquery-Wrapping + IMMUTABLE |
| > 100 | < 100k | Partitionierung + RLS |
| Beliebig | > 1M | Sharding (Citus) oder dedizierte DBs |

---

## HoneyBee Framework (Forschung)

### Konzept
Dynamische Partitionierung basierend auf RBAC-Struktur. Vektoren werden strategisch in überlappenden Indizes repliziert.

### Benchmark-Ergebnisse
| Metrik | Standard RLS | HoneyBee |
|--------|--------------|----------|
| Latenz | Baseline | 13.5x schneller |
| Speicher | Baseline | 1.24x |
| Recall | Variabel | Stabil hoch |

### Status
Akademische Forschung (arXiv:2505.01538). Noch nicht produktionsreif, aber vielversprechend für extreme Multi-Tenant-Szenarien.

---

## Checkliste für cognitive-memory

### Sofort implementieren
- [ ] pgvector 0.8.0+ installiert
- [ ] `SET hnsw.iterative_scan = 'relaxed_order'` als Default
- [ ] Subquery-Wrapping in allen RLS-Policies
- [ ] `get_current_project()` als IMMUTABLE-Funktion

### Bei Skalierung
- [ ] B-Tree-Index auf `project_id` für alle Tabellen
- [ ] GIN-Index falls Array-basierte ACLs
- [ ] Partitionierung ab >100 Mandanten evaluieren

### Monitoring
```sql
-- RLS-Policy-Performance prüfen
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM l2_insights
WHERE embedding <=> '[...]' < 0.5
ORDER BY embedding <=> '[...]'
LIMIT 10;

-- Achten auf:
-- - Seq Scan (schlecht) vs. Index Scan (gut)
-- - "Rows Removed by Filter" (RLS-Overhead)
-- - "Planning Time" vs. "Execution Time"
```

---

## Referenzen

- pgvector 0.8.0 Release Notes: Iterative Index Scans
- AWS Database Blog: Supercharging pgvector with 0.8.0
- Supabase Docs: RLS Performance Best Practices
- arXiv:2505.01538: HoneyBee Framework
- PostgreSQL Docs: Row Level Security
