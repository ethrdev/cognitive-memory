# pgTAP Verfügbarkeit und RLS-Testing Strategien

> Research Summary: 2026-01-22
> Source: Deep Research F7 - pgTAP in Managed PostgreSQL Services
> Status: VALIDATED

## Executive Summary

pgTAP ist in **AWS RDS/Aurora** und **Google Cloud SQL** verfügbar. Bei **Azure** ist die Unterstützung fraglich. **Supabase** bietet die beste Integration mit Test-Helpers.

**Empfehlung für cognitive-memory:** Hybrid-Ansatz mit pgTAP für DB-native Tests + Pytest für Integration-Tests.

---

## pgTAP Verfügbarkeit nach Cloud-Provider

| Provider | pgTAP Support | Version | Admin-Rolle | CLI Tool |
|----------|---------------|---------|-------------|----------|
| **AWS RDS/Aurora** | ✅ Ja | 1.3.3 | rds_superuser | pg_prove |
| **Google Cloud SQL** | ✅ Ja | 1.3.0 | cloudsqlsuperuser | gcloud/psql |
| **Azure Flexible** | ⚠️ Fraglich | - | azure_pg_admin | Azure CLI |
| **Supabase** | ✅ Ja (integriert) | - | postgres | supabase test db |

---

## AWS RDS / Aurora PostgreSQL

### Installation

```sql
-- Erfordert rds_superuser Rolle
CREATE EXTENSION pgtap;
```

### Test-Ausführung mit pg_prove

```bash
# Lokal gespeicherte Tests gegen RDS ausführen
pg_prove --host mydb.xxx.rds.amazonaws.com \
         --username myuser \
         --dbname mydb \
         tests/db/*.sql
```

### Limitationen

- Extension-Versionen upgraden nicht automatisch bei Engine-Upgrade
- Manuelles `ALTER EXTENSION pgtap UPDATE;` nach Engine-Upgrade nötig

---

## Google Cloud SQL

### Installation

```sql
-- Erfordert cloudsqlsuperuser Rolle (postgres User hat diese)
CREATE EXTENSION pgtap;
```

### Besonderheiten

- Extensions werden auf Primary installiert, automatisch zu Replicas repliziert
- Keine Custom Extensions (nur aus Support-Liste)
- Flags müssen VOR Extension-Erstellung gesetzt sein

---

## Azure Database for PostgreSQL

### Status: Nicht explizit unterstützt

- pgTAP fehlt in der offiziellen Extension-Liste (PostgreSQL 11-18)
- `azure.extensions` Server-Parameter muss Extensions allowlisten
- Bekannte Permission-Probleme bei Extension-Erstellung

### Alternative für Azure

**Pytest-basierte RLS-Tests** (siehe unten)

---

## Supabase: Beste Integration

### Built-in Test CLI

```bash
# Tests im Verzeichnis ./supabase/tests/database/
supabase test db
```

### Test-Helper-Funktionen

```sql
-- Supabase-spezifische Helper (basejump-supabase_test_helpers)
SELECT tests.create_supabase_user('test-user-id', 'test@example.com');
SELECT tests.authenticate_as('test-user-id');

-- Danach können RLS-Policies getestet werden
SELECT * FROM l2_insights;  -- Sieht nur erlaubte Daten
```

### Beispiel-Test

```sql
-- tests/database/test_rls_isolation.sql
BEGIN;
SELECT plan(3);

-- Setup: Zwei Test-User
SELECT tests.create_supabase_user('user-a', 'a@test.com');
SELECT tests.create_supabase_user('user-b', 'b@test.com');

-- Insert als User A
SELECT tests.authenticate_as('user-a');
INSERT INTO l2_insights (content, project_id) VALUES ('Secret A', 'project-a');

-- Test 1: User A sieht eigene Daten
SELECT is(
    (SELECT COUNT(*) FROM l2_insights WHERE content = 'Secret A'),
    1,
    'User A can see own data'
);

-- Test 2: User B sieht NICHT User A's Daten
SELECT tests.authenticate_as('user-b');
SELECT is(
    (SELECT COUNT(*) FROM l2_insights WHERE content = 'Secret A'),
    0,
    'User B cannot see User A data'
);

-- Test 3: Anonymous sieht nichts
SELECT tests.clear_authentication();
SELECT is(
    (SELECT COUNT(*) FROM l2_insights),
    0,
    'Anonymous sees nothing'
);

SELECT finish();
ROLLBACK;
```

---

## pgTAP Vorteile für RLS-Testing

### 1. Konfigurationsaudit

```sql
-- Prüfen ob RLS aktiviert ist
SELECT policies_are(
    'public',
    'l2_insights',
    ARRAY['tenant_isolation', 'super_access']
);

SELECT policy_cmd_is('public', 'l2_insights', 'tenant_isolation', 'SELECT');
SELECT policy_roles_are('public', 'l2_insights', 'tenant_isolation', ARRAY['authenticated']);
```

### 2. Interner Context-Switch

```sql
-- Innerhalb einer Transaktion Rollen wechseln
SET LOCAL ROLE stranger;
SET LOCAL app.current_project = 'other-project';
SELECT is_empty(
    'SELECT * FROM l2_insights WHERE project_id = ''my-project''',
    'Stranger cannot see my project data'
);
RESET ROLE;
```

### 3. Kein Type-Conversion

Tests vergleichen Werte direkt im PostgreSQL-Format (JSONB, UUID, etc.) ohne Konvertierung.

---

## Pytest-basierte RLS-Tests (Alternative)

### Wann Pytest statt pgTAP?

- Azure-Hosting (pgTAP nicht verfügbar)
- Python-zentrische Codebasis
- Integration mit Application-Layer-Tests

### Pattern mit pytest-postgresql

```python
import pytest
from pytest_postgresql import factories

postgresql_proc = factories.postgresql_proc()
postgresql = factories.postgresql('postgresql_proc')

@pytest.fixture
async def db_with_rls(postgresql):
    """Setup test database with RLS and test data."""
    # Admin-Connection für Setup
    await postgresql.execute("SELECT set_project_context('admin')")
    await postgresql.execute("""
        INSERT INTO l2_insights (content, project_id)
        VALUES ('Secret', 'project-a')
    """)
    yield postgresql

async def test_isolation(db_with_rls):
    """Test: User B cannot see User A's data."""
    # Als User B authentifizieren
    await db_with_rls.execute("SET ROLE app_user")
    await db_with_rls.execute("SELECT set_project_context('project-b')")

    # Query ausführen
    result = await db_with_rls.fetch("SELECT * FROM l2_insights")

    # Assertion
    assert len(result) == 0, "User B should not see project-a data"
```

### Limitationen von Pytest

| Aspekt | pgTAP | Pytest |
|--------|-------|--------|
| Cleanup | Transaction Rollback | DatabaseJanitor (langsam) |
| Performance | Lokal (schnell) | Netzwerk-Roundtrips |
| Strukturtest | `policies_are()`, `has_table()` | Nur Result-Validation |
| Multi-User | `SET LOCAL ROLE` in einer Tx | Mehrere Connections |

---

## RLS Test-Patterns (Provider-unabhängig)

### Test-Kategorien

Jede RLS-geschützte Tabelle benötigt:

1. **Owner Access Test**
   ```sql
   -- User kann eigene Daten sehen und modifizieren
   SELECT is((SELECT COUNT(*) FROM t WHERE owner = current_user), expected_count);
   ```

2. **Cross-Tenant Isolation Test**
   ```sql
   -- User A kann User B's Daten NICHT sehen
   SET LOCAL ROLE user_a;
   SELECT is_empty('SELECT * FROM t WHERE owner = ''user_b''');
   ```

3. **Anonymous/Public Test**
   ```sql
   -- Unauthentifizierte User sehen nur Public-Daten (oder nichts)
   SET LOCAL ROLE anon;
   SELECT results_eq('SELECT * FROM t', 'SELECT * FROM t WHERE is_public = true');
   ```

4. **Write Protection Test**
   ```sql
   -- User kann fremde Daten nicht modifizieren
   SET LOCAL ROLE user_a;
   INSERT INTO t (owner, data) VALUES ('user_b', 'hacked');
   -- Erwarte: Policy-Violation Error
   ```

---

## Empfehlung für cognitive-memory

### Wenn Self-Hosted oder AWS/GCP

**Primär: pgTAP**

```
tests/
├── db/
│   ├── sql/
│   │   └── install_test_extensions.sql  # CREATE EXTENSION pgtap;
│   └── pgtap/
│       ├── test_rls_l2_insights.sql
│       ├── test_rls_graph_nodes.sql
│       └── test_rls_graph_edges.sql
```

**Sekundär: Pytest für E2E**

```python
# tests/integration/test_rls_e2e.py
async def test_hybrid_search_isolation():
    """Full stack test: MCP client -> Server -> DB with RLS."""
```

### Wenn Azure

**Nur Pytest + SET ROLE**

```python
# tests/integration/test_rls_policies.py
@pytest.fixture
async def isolated_conn(project_id: str):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET ROLE app_user")
            await conn.execute("SELECT set_project_context($1)", project_id)
            yield conn
```

---

## Performance-Testing für RLS

### LEAKPROOF-Funktionen

```sql
-- Problem: Non-LEAKPROOF Funktionen verhindern Index-Nutzung
SELECT * FROM l2_insights
WHERE project_id = my_custom_function();  -- Möglicherweise Seq Scan!

-- Lösung: LEAKPROOF markieren (nur Superuser)
CREATE FUNCTION get_current_project() RETURNS text
LANGUAGE sql IMMUTABLE LEAKPROOF AS $$
  SELECT current_setting('app.current_project')
$$;
```

### Index auf Policy-Spalten

```sql
-- PFLICHT: Index auf Spalten in USING/WITH CHECK
CREATE INDEX idx_insights_project ON l2_insights(project_id);

-- EXPLAIN ANALYZE in Tests prüfen
SELECT * FROM l2_insights WHERE project_id = 'test';
-- Erwarte: Index Scan, NICHT Seq Scan
```

---

## Referenzen

- pgTAP Docs: pgtap.org
- AWS: Create Unit Testing Framework with pgTAP
- Supabase: Testing Overview
- pytest-postgresql: PyPI
