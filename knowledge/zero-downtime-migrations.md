# Zero-Downtime Schema-Migrationen in PostgreSQL

> Research Summary from Deep Research (2026-01-22)
> Source: Kategorie 3 - Fortgeschrittene Strategien für Zero-Downtime-Migrationen

## Executive Summary

Zero-Downtime-Migrationen erfordern das Vermeiden von `ACCESS EXCLUSIVE` Locks oder deren Minimierung auf Millisekunden. Die Schlüsseltechniken sind:
1. **NOT VALID Constraints** mit asynchroner Validierung
2. **Batch-basiertes Backfilling** mit Keyset Pagination
3. **Expand-Contract Pattern** mit View-Abstraktion (pgroll)

---

## Das PostgreSQL Sperrmodell verstehen

### Die Lock-Queue-Gefahr

```
Transaktion A: SELECT (ACCESS SHARE) - läuft 10s
Transaktion B: ALTER TABLE (ACCESS EXCLUSIVE) - wartet auf A
Transaktion C: SELECT (ACCESS SHARE) - wartet auf B!
```

**Kritisch:** Selbst kompatible Locks (C mit A) werden blockiert, wenn ein exklusiver Lock (B) in der Queue wartet. Die Applikation "hängt" bevor die Migration überhaupt startet.

### Lock-Typen und Kompatibilität

| Operation | Lock-Typ | Blockiert |
|-----------|----------|-----------|
| SELECT | ACCESS SHARE | Nichts (außer EXCLUSIVE) |
| INSERT/UPDATE/DELETE | ROW EXCLUSIVE | Schema-Änderungen |
| ALTER TABLE (meiste) | ACCESS EXCLUSIVE | ALLES |
| VALIDATE CONSTRAINT | SHARE UPDATE EXCLUSIVE | Nur andere Schema-Änderungen |

---

## NOT NULL Constraints ohne Downtime

### Der moderne 4-Phasen-Workflow (PostgreSQL 12+)

#### Phase 1: Definition ohne Validierung

```sql
ALTER TABLE large_table
ADD CONSTRAINT check_no_nulls
CHECK (column_name IS NOT NULL)
NOT VALID;
```

- Benötigt ACCESS EXCLUSIVE, aber nur Millisekunden
- Kein Table Scan
- Ab sofort: Neue Daten werden validiert

#### Phase 2: Asynchrones Backfilling

```sql
-- Alte NULL-Werte befüllen (siehe Backfilling-Strategien unten)
UPDATE large_table SET column_name = 'default' WHERE column_name IS NULL;
```

#### Phase 3: Constraint validieren

```sql
ALTER TABLE large_table VALIDATE CONSTRAINT check_no_nulls;
```

- Benötigt nur SHARE UPDATE EXCLUSIVE
- Erlaubt paralleles Lesen UND Schreiben
- Scannt Tabelle im Hintergrund

#### Phase 4: Optional - Nativer NOT NULL

```sql
-- PostgreSQL erkennt existierenden CHECK und überspringt Scan
ALTER TABLE large_table ALTER COLUMN column_name SET NOT NULL;
DROP CONSTRAINT check_no_nulls;
```

---

## Backfilling-Strategien

### NICHT empfohlen: LIMIT/OFFSET

```sql
-- Wird exponentiell langsamer!
SELECT * FROM table LIMIT 1000 OFFSET 5000000;
```

### EMPFOHLEN: Keyset Pagination

```sql
DO $
DECLARE
    batch_size CONSTANT integer := 5000;
    last_id bigint := 0;
    affected_rows integer;
BEGIN
    LOOP
        WITH batch AS (
            SELECT id
            FROM large_table
            WHERE id > last_id
              AND target_column IS NULL
            ORDER BY id ASC
            LIMIT batch_size
            FOR UPDATE SKIP LOCKED  -- Parallelisierung möglich!
        )
        UPDATE large_table
        SET target_column = 'default_value'
        FROM batch
        WHERE large_table.id = batch.id
        RETURNING batch.id INTO last_id;

        GET DIAGNOSTICS affected_rows = ROW_COUNT;
        COMMIT;  -- Ressourcen freigeben, Vacuum ermöglichen

        IF affected_rows < batch_size THEN
            EXIT;
        END IF;

        PERFORM pg_sleep(0.05);  -- Optional: I/O-Last reduzieren
    END LOOP;
END $;
```

### Vorteile dieser Strategie

| Aspekt | Vorteil |
|--------|---------|
| `FOR UPDATE SKIP LOCKED` | Mehrere Worker parallel möglich |
| `COMMIT` pro Batch | Verhindert Table Bloat, ermöglicht Vacuum |
| Keyset statt Offset | Konstante Performance O(1) |
| `pg_sleep` | Backpressure bei hoher Last |

---

## Expand-Contract Pattern

### Für destruktive Änderungen (Spalte umbenennen, aufteilen)

```
Phase 1: EXPAND
┌─────────────┐     ┌─────────────┐
│  old_col    │ ──► │  old_col    │
│             │     │  new_col    │ (nullable)
└─────────────┘     └─────────────┘
                    App schreibt in BEIDE

Phase 2: MIGRATE
┌─────────────┐
│  old_col    │ ──► Backfill nach new_col
│  new_col    │
└─────────────┘

Phase 3: CONTRACT
┌─────────────┐     ┌─────────────┐
│  old_col    │     │  new_col    │
│  new_col    │ ──► │             │
└─────────────┘     └─────────────┘
                    old_col löschen
```

### View-Abstraktion mit pgroll

```sql
-- Physische Tabelle
ALTER TABLE users RENAME TO users_physical;

-- Versioned Views
CREATE VIEW schema_v1.users AS
  SELECT id, old_col FROM users_physical;

CREATE VIEW schema_v2.users AS
  SELECT id, new_col FROM users_physical;

-- Applikation wählt Version via search_path
SET search_path TO schema_v2;
```

**Instant Rollback:** Nur `search_path` ändern, keine Datenmigration!

### pgroll Automatisierung

```bash
# Migration definieren
pgroll start migration.json

# Neue Version aktiv, alte weiterhin verfügbar
# Trigger synchronisieren Daten automatisch

# Nach Validierung
pgroll complete
```

---

## Rollback-Strategien

### Fix-Forward vs. Instant Rollback

| Strategie | Wann nutzen |
|-----------|-------------|
| Fix-Forward | Nicht-destruktive Fehler, neue Migration deployen |
| View Swapping | Mit pgroll, instant und datenverlustfrei |
| Shadow Table | Hochrisiko-Operationen (PK-Typ ändern) |

### Shadow Table Strategie

```sql
-- 1. Neue Tabelle erstellen
CREATE TABLE table_new (id BIGINT PRIMARY KEY, ...);

-- 2. Trigger für Synchronisation
CREATE TRIGGER sync_to_new
AFTER INSERT OR UPDATE OR DELETE ON table_old
FOR EACH ROW EXECUTE FUNCTION sync_tables();

-- 3. Backfill historischer Daten

-- 4. Atomarer Switch
BEGIN;
LOCK TABLE table_old IN ACCESS EXCLUSIVE MODE;
ALTER TABLE table_old RENAME TO table_archive;
ALTER TABLE table_new RENAME TO table_old;
COMMIT;

-- Rollback: Einfach zurück-umbenennen
```

---

## Anwendung auf cognitive-memory

### Migration: `project_id` hinzufügen

```sql
-- Phase 1: Spalte hinzufügen (instant, kein Rewrite seit PG11)
ALTER TABLE nodes ADD COLUMN project_id VARCHAR(50);
ALTER TABLE edges ADD COLUMN project_id VARCHAR(50);
ALTER TABLE l2_insights ADD COLUMN project_id VARCHAR(50);
-- ... weitere Tabellen

-- Phase 2: NOT VALID Constraint
ALTER TABLE nodes ADD CONSTRAINT check_project_id_not_null
CHECK (project_id IS NOT NULL) NOT VALID;

-- Phase 3: Backfill (mit Default-Wert 'legacy')
-- Batch-Script für jede Tabelle

-- Phase 4: Validierung
ALTER TABLE nodes VALIDATE CONSTRAINT check_project_id_not_null;

-- Phase 5: Unique Constraints anpassen
DROP INDEX idx_nodes_unique;
CREATE UNIQUE INDEX idx_nodes_unique ON nodes(project_id, name);
```

### Risikominimierung

1. **Staging-Test:** Vollständige Migration auf Kopie der Produktionsdaten
2. **Monitoring:** Lock-Wait-Zeiten während Migration überwachen
3. **Rollback-Plan:** Shadow Tables für kritische Tabellen vorbereiten
4. **Batch-Größe:** Mit 1000 starten, nach CPU/IO-Last anpassen

---

## Checkliste Zero-Downtime Migration

- [ ] Staging-Test mit Produktionsdaten-Kopie erfolgreich
- [ ] Lock-Timeout konfiguriert (`SET lock_timeout = '3s'`)
- [ ] Keine langlaufenden Queries während Migration
- [ ] NOT VALID für neue Constraints
- [ ] Batch-basiertes Backfilling implementiert
- [ ] Rollback-Strategie dokumentiert
- [ ] Monitoring für Lock-Waits aktiv
- [ ] Connection Pooler konfiguriert (Transaction Mode + SET LOCAL)

---

## Referenzen

- PostgreSQL 18: NOT NULL Constraints as NOT VALID
- pgroll: Zero-downtime, reversible schema changes
- GoCardless: Zero-downtime Postgres migrations - the hard parts
- Figma: Scaling Postgres to millions of queries per second
