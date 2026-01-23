# PostgreSQL Multi-Tenancy Patterns

> Research Summary from Deep Research (2026-01-22)
> Source: Kategorie 1 - Architekturmuster für PostgreSQL Multi-Tenancy

## Executive Summary

Für 10-100+ Tenants mit pgvector-Anforderungen ist **Shared Schema + RLS + Partitioned Vectors** die empfohlene Architektur. Sie bietet die beste Balance aus operationaler Effizienz, Sicherheit und Abfrageleistung.

---

## Die drei Hauptmuster

### Pattern 1: Shared Database, Shared Schema (Empfohlen)

Alle Mandanten teilen dieselbe Datenbank und dasselbe Schema. Unterscheidung über `tenant_id`/`project_id` Spalte.

**Vorteile:**
- Maximale Effizienz des PostgreSQL Buffer Pools (shared_buffers)
- Schema-Migrationen nur einmal ausführen (O(1))
- Cross-Tenant Analytics trivial möglich
- Exzellentes Connection Pooling (Transaction Mode)

**Nachteile:**
- Isolation rein logisch - hängt von korrekter Anwendungslogik ab
- "Noisy Neighbor"-Problem möglich
- Ohne RLS: Ein vergessener WHERE-Filter = Datenleck

**Mitigation:** Row-Level Security (RLS) als Sicherheitsnetz

### Pattern 2: Schema-per-Tenant

Jeder Mandant erhält ein eigenes PostgreSQL Schema (z.B. `tenant_a`, `tenant_b`).

**Vorteile:**
- Robustere Isolation als Shared Schema
- Einzelne Schemata separat backup-fähig (`pg_dump -n schema_name`)
- Ideal für 10-100 Tenants

**Nachteile:**
- Migrations-Overhead O(N) - wächst linear mit Tenant-Anzahl
- Connection Pooling problematisch (PgBouncer Transaction Mode inkompatibel mit `SET search_path`)
- PostgreSQL Katalog-Bloat ab ~1000 Schemata

### Pattern 3: Database-per-Tenant

Jeder Mandant erhält eine vollständig eigene Datenbank.

**Vorteile:**
- Maximale physische Isolation
- Unabhängige Backups und PITR
- Ideal für Compliance-kritische Anwendungen

**Nachteile:**
- Ressourcen-Fragmentierung (100 DBs = 100 Buffer Pools)
- Connection Pooling extrem komplex
- Cross-Tenant-Reporting erfordert Data Warehouse
- Administrative Last untragbar bei >100 Tenants

---

## Vergleichsmatrix (10-100 Tenants)

| Kriterium | Shared Schema (RLS) | Schema-per-Tenant | Database-per-Tenant |
|-----------|---------------------|-------------------|---------------------|
| Isolationsgrad | Logisch (Zeilenebene) | Logisch (Namespace) | Physisch |
| Migrationsaufwand | Sehr Gering O(1) | Mittel O(N) | Hoch O(N) |
| Ressourceneffizienz | Sehr Hoch | Hoch | Niedrig |
| Backup-Granularität | Gering (Full DB) | Mittel (Schema) | Hoch (DB) |
| Connection Pooling | Exzellent | Problematisch | Komplex |
| Katalog-Bloat | Kein Problem | Ab ~1000 Schemas | Kein Problem |

---

## Row-Level Security (RLS) - Best Practices

### Grundprinzip

RLS transformiert die Datenbank von passivem Datenspeicher zu aktiver Sicherheitskomponente.

```sql
-- Aktivieren von RLS
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE orders FORCE ROW LEVEL SECURITY; -- Auch für Table Owner!

-- Policy definieren
CREATE POLICY tenant_isolation_policy ON orders
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant')::INTEGER)
    WITH CHECK (tenant_id = current_setting('app.current_tenant')::INTEGER);
```

### Transparenz für Anwendung

```sql
-- Entwickler schreibt:
SELECT * FROM orders;

-- PostgreSQL transformiert automatisch zu:
SELECT * FROM orders WHERE tenant_id = current_setting('app.current_tenant')::INTEGER;
```

### Performance-Impact

- Bei simplen Gleichheitsprüfungen: **vernachlässigbar** (1-10%)
- Erfordert Index auf `tenant_id`
- **Vermeiden:** Komplexe Policies mit Subqueries (können Full Table Scans verursachen)

### Integration mit PgBouncer (Transaction Mode)

```sql
BEGIN;
-- Variable nur für diese Transaktion setzen
SELECT set_config('app.current_tenant', '123', true); -- true = local
-- Business-Logik
SELECT * FROM orders;
COMMIT;
-- Nach COMMIT ist Variable automatisch gelöscht
```

---

## pgvector und Multi-Tenancy

### Das Over-Filtering Problem (Pre-0.8.0)

HNSW-Index findet k ähnlichste Vektoren **global**, dann erst Filter → Tenant erhält weniger als k Ergebnisse.

### Lösung: Iterative Index Scans (pgvector 0.8.0+)

Index sucht weiter bis k Einträge gefunden, die **beide** Kriterien erfüllen (Ähnlichkeit UND tenant_id-Match).

### Empfohlene Architektur: Partitionierung nach Tenant

```sql
-- List-Partitioning für Vektortabellen
CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    embedding vector(1536),
    content TEXT
) PARTITION BY LIST (tenant_id);

-- Pro Tenant eine Partition mit eigenem HNSW-Index
CREATE TABLE embeddings_tenant_1 PARTITION OF embeddings FOR VALUES IN (1);
CREATE INDEX ON embeddings_tenant_1 USING hnsw (embedding vector_cosine_ops);
```

**Vorteile:**
- Kleiner Index pro Tenant → passt in RAM
- Automatisches Partition Pruning
- Queries scannen nur relevante Tenant-Partition

**Grenzen:** Praktikabel bis wenige tausend Partitions

### Index-Empfehlung: HNSW > IVFFlat

| Aspekt | HNSW | IVFFlat |
|--------|------|---------|
| Training erforderlich | Nein | Ja |
| Cold Start (neue Tenants) | Funktioniert sofort | Schlecht |
| RAM-Verbrauch | Höher | Niedriger |
| Wartung | Keine | Regelmäßiges REINDEX |
| Empfehlung | **Standard für SaaS** | Nur bei RAM-Limits |

---

## Anwendung auf cognitive-memory

### Aktuelle Situation
- Keine `project_id` Spalte in Tabellen
- Globaler unique constraint auf `(label, name)` für nodes
- Alle Projekte teilen denselben Datenraum

### Empfohlene Architektur

**Shared Schema + RLS** mit folgenden Anpassungen:

1. `project_id` Spalte zu allen Tabellen hinzufügen
2. Unique constraints auf `(project_id, ...)` erweitern
3. RLS Policies für alle Tabellen definieren
4. Für Vektortabellen (`l2_insights`): List-Partitioning nach `project_id` evaluieren

---

## Referenzen

- PostgreSQL Documentation: Row Security Policies
- pgvector 0.8.0 Release Notes: Iterative Index Scans
- Crunchy Data: Multi-Tenant Best Practices
- AWS Aurora: pgvector Performance Optimization
