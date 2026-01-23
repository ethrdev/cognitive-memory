# Alembic + RLS: Deklarative Policy-Verwaltung

> Research Summary: 2026-01-22
> Source: Deep Research F8 - Alembic und Row-Level Security
> Status: VALIDATED

## Executive Summary

`alembic_utils` ermöglicht deklaratives RLS-Management mit automatischer Änderungserkennung und Rollback-Fähigkeit. **Kritisch:** Tabellenstruktur und RLS-Policies müssen in separaten Migrationen erstellt werden.

**Kernpunkte:**
1. PGPolicy-Klasse für deklarative Policy-Definition
2. FORCE RLS ist Pflicht für Owner-Bypass-Schutz
3. Zwei-Phasen-Migration: Struktur → Sicherheit

---

## alembic_utils RLS-Unterstützung

### Deklaratives Management statt Raw-SQL

```python
# app/database/policies.py
from alembic_utils.pg_policy import PGPolicy

tenant_isolation_policy = PGPolicy(
    schema="public",
    signature="tenant_isolation_policy",
    on_entity="public.l2_insights",
    definition="USING (project_id = (SELECT current_setting('app.current_project', TRUE)))"
)

# Für WITH CHECK (INSERT/UPDATE)
tenant_write_policy = PGPolicy(
    schema="public",
    signature="tenant_write_policy",
    on_entity="public.l2_insights",
    definition="""
        FOR INSERT
        WITH CHECK (project_id = (SELECT current_setting('app.current_project', TRUE)))
    """
)
```

### Integration in env.py

```python
# alembic/env.py
from alembic_utils.replaceable_entity import register_entities
from app.database.policies import (
    tenant_isolation_policy,
    tenant_write_policy,
)

register_entities([
    tenant_isolation_policy,
    tenant_write_policy,
])
```

### Autogenerate-Erkennung

```bash
# Änderung in Python-Definition erkennen
alembic revision --autogenerate -m "Update tenant isolation policy"

# Generiert automatisch:
# - upgrade(): replace_entity(new_policy)
# - downgrade(): replace_entity(old_policy)  # Automatisch gespeichert!
```

---

## Idempotenz und Rollback

### Replaceable Entities Pattern

`alembic_utils` behandelt Policies als austauschbare Entitäten:

| Szenario | Verhalten |
|----------|-----------|
| Policy neu | `CREATE POLICY` |
| Policy geändert | `DROP POLICY` + `CREATE POLICY` |
| Policy entfernt | `DROP POLICY` |

### Automatische Rollback-Logik

```python
# Generierte Migration (vereinfacht)
def upgrade():
    op.replace_entity(
        PGPolicy(
            schema="public",
            signature="tenant_policy",
            on_entity="public.l2_insights",
            definition="USING (project_id = get_current_project())"  # NEU
        )
    )

def downgrade():
    op.replace_entity(
        PGPolicy(
            schema="public",
            signature="tenant_policy",
            on_entity="public.l2_insights",
            definition="USING (project_id = current_setting('app.current_project'))"  # ALT
        )
    )
```

**Vorteil:** Alte Policy-Definition wird automatisch im Downgrade gespeichert.

---

## Kritische Migrations-Sequenz

### Die zwingende Reihenfolge

```
1. CREATE TABLE           → Tabelle existiert
2. ENABLE ROW LEVEL SECURITY  → Default Deny aktiviert
3. FORCE ROW LEVEL SECURITY   → Owner unterliegt auch RLS
4. CREATE POLICY          → Selektiver Zugriff
```

### Der "Dependency Gap" Problem

**Problem:** `alembic_utils` validiert Policies in temporärer Transaktion. Wenn Tabelle und Policy in derselben Migration erstellt werden, ist die Tabelle für die Validierung noch nicht sichtbar.

**Lösung: Zwei-Phasen-Migration**

```python
# Migration A: Struktur (001_create_tables.py)
def upgrade():
    op.create_table(
        'l2_insights',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.String(50), nullable=False),
        sa.Column('content', sa.Text()),
        sa.Column('embedding', Vector(1536)),
    )
    # Index für RLS-Spalte (Performance!)
    op.create_index('idx_l2_insights_project', 'l2_insights', ['project_id'])

# Migration B: Sicherheit (002_enable_rls.py)
def upgrade():
    # 1. RLS aktivieren
    op.execute("ALTER TABLE l2_insights ENABLE ROW LEVEL SECURITY")
    # 2. FORCE für Owner-Bypass-Schutz
    op.execute("ALTER TABLE l2_insights FORCE ROW LEVEL SECURITY")
    # 3. Policies werden durch alembic_utils gehandelt
    op.create_entity(tenant_isolation_policy)
```

---

## FORCE RLS: Owner-Bypass-Schutz

### Warum FORCE RLS Pflicht ist

```sql
-- OHNE FORCE: Owner umgeht RLS komplett!
ALTER TABLE l2_insights ENABLE ROW LEVEL SECURITY;

-- Als Owner (z.B. mcp_app_user):
SELECT * FROM l2_insights;  -- Sieht ALLE Daten!

-- MIT FORCE: Owner unterliegt auch Policies
ALTER TABLE l2_insights FORCE ROW LEVEL SECURITY;

SELECT * FROM l2_insights;  -- Sieht nur erlaubte Daten
```

### Wann FORCE RLS nötig ist

| Szenario | FORCE RLS |
|----------|-----------|
| App-User = Table Owner | ✅ PFLICHT |
| App-User ≠ Table Owner | Optional |
| Superuser | Immer Bypass (auch mit FORCE) |

---

## Sichere Policy-Definitionen

### Robustheit gegen fehlenden Kontext

```sql
-- UNSICHER: Fehler wenn Variable nicht gesetzt
CREATE POLICY bad_policy ON l2_insights
  USING (project_id = current_setting('app.current_project'));

-- SICHER: Default zu NULL → Deny
CREATE POLICY good_policy ON l2_insights
  USING (project_id = current_setting('app.current_project', TRUE));
  -- TRUE = missing_ok, gibt NULL zurück statt Fehler
  -- NULL = project_id vergleicht nie TRUE → Deny
```

### Subquery-Wrapping für Performance

```sql
-- LANGSAM: Funktion pro Zeile evaluiert
USING (project_id = current_setting('app.current_project', TRUE))

-- SCHNELL: Einmal pro Query (initPlan)
USING (project_id = (SELECT current_setting('app.current_project', TRUE)))
```

---

## Best Practices für cognitive-memory

### 1. Policy-Organisation

```
mcp_server/
├── db/
│   ├── policies/
│   │   ├── __init__.py
│   │   ├── l2_insights.py      # Policies für l2_insights
│   │   ├── graph_nodes.py      # Policies für graph_nodes
│   │   └── graph_edges.py      # Policies für graph_edges
│   └── migrations/
│       ├── env.py              # register_entities()
│       └── versions/
```

### 2. Standard-Policy-Template

```python
# mcp_server/db/policies/base.py
from alembic_utils.pg_policy import PGPolicy

def create_tenant_isolation_policy(table_name: str) -> PGPolicy:
    """Standard tenant isolation policy für alle Tabellen."""
    return PGPolicy(
        schema="public",
        signature=f"{table_name}_tenant_isolation",
        on_entity=f"public.{table_name}",
        definition="""
            FOR ALL
            USING (project_id = (SELECT current_setting('app.current_project', TRUE)))
            WITH CHECK (project_id = (SELECT current_setting('app.current_project', TRUE)))
        """
    )
```

### 3. Migrations-Checkliste

- [ ] Tabelle hat `project_id` Spalte
- [ ] Index auf `project_id` existiert
- [ ] ENABLE ROW LEVEL SECURITY ausgeführt
- [ ] FORCE ROW LEVEL SECURITY ausgeführt
- [ ] PGPolicy in policies/ definiert
- [ ] Policy in env.py registriert
- [ ] Subquery-Wrapping in USING-Klausel

### 4. Index-Strategie

```sql
-- PFLICHT: B-Tree auf Policy-Spalte
CREATE INDEX idx_l2_insights_project ON l2_insights(project_id);

-- Bei Vektor-Suche: Composite oder Partial Index
CREATE INDEX idx_l2_insights_project_embedding
  ON l2_insights USING hnsw(embedding vector_cosine_ops)
  WHERE project_id = 'io';  -- Partial Index pro Mandant (optional)
```

---

## Häufige Fehler

### 1. Vergessenes FORCE RLS

```python
# FALSCH
def upgrade():
    op.execute("ALTER TABLE t ENABLE ROW LEVEL SECURITY")
    # Owner kann immer noch alles sehen!

# RICHTIG
def upgrade():
    op.execute("ALTER TABLE t ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE t FORCE ROW LEVEL SECURITY")
```

### 2. Fehlender Index

```python
# FALSCH: Policy ohne Index → Full Table Scan
op.create_entity(tenant_policy)

# RICHTIG: Index VOR Policy
op.create_index('idx_t_project', 't', ['project_id'])
op.create_entity(tenant_policy)
```

### 3. Struktur und Policy in einer Migration

```python
# FALSCH: Validierungsfehler möglich
def upgrade():
    op.create_table('t', ...)
    op.create_entity(policy_for_t)  # Tabelle noch nicht "sichtbar"!

# RICHTIG: Separate Migrationen
# 001_create_table.py
# 002_enable_rls.py
```

---

## Referenzen

- alembic_utils Docs: PGPolicy
- PostgreSQL Docs: ALTER TABLE ... ENABLE/FORCE ROW LEVEL SECURITY
- PostgreSQL Docs: CREATE POLICY

