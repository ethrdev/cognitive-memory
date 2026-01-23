# RLS Gradual Rollout and Rollback Strategies

> Research Summary from Deep Research (2026-01-22)
> Source: PostgreSQL RLS gradual rollout and rollback for multi-tenant SaaS

## Executive Summary

**Conditional RLS per Tenant ist möglich** durch Policy-Expressions die Migration-Status-Tabellen prüfen. Rollback erfordert ACCESS EXCLUSIVE Lock - daher Lock-Timeouts und BYPASSRLS Emergency Roles als Sicherheitsmechanismen.

**Kritische Erkenntnisse für cognitive-memory:**
1. Gradual Rollout durch `rls_migration_status` Tabelle + Session-cached Variables
2. Drei-Phasen-Migration: legacy → shadow/audit → enforcing
3. DISABLE RLS braucht ACCESS EXCLUSIVE Lock → `SET LOCAL lock_timeout = '5s'`
4. BYPASSRLS Role für Emergency Debugging ohne System-weites Disable
5. Silent Failures: SELECT gibt leere Ergebnisse, keine Errors

---

## 1. Conditional RLS per Tenant

### Migration Status Tabelle

```sql
CREATE TABLE rls_migration_status (
    project_id VARCHAR(50) PRIMARY KEY,
    rls_enabled BOOLEAN DEFAULT FALSE,
    migration_phase VARCHAR(20) DEFAULT 'pending'
        CHECK (migration_phase IN ('pending', 'shadow', 'enforcing', 'complete')),
    migrated_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Session-Cached Context Function

```sql
-- STABLE für Query Planner Optimization
CREATE OR REPLACE FUNCTION current_project_id()
RETURNS VARCHAR(50) AS $
    SELECT NULLIF(current_setting('app.current_project', TRUE), '')
$ LANGUAGE SQL STABLE;

CREATE OR REPLACE FUNCTION project_rls_mode()
RETURNS TEXT AS $
    SELECT COALESCE(current_setting('app.migration_phase', TRUE), 'legacy')
$ LANGUAGE SQL STABLE;
```

### Conditional Policy Pattern

```sql
CREATE POLICY project_isolation ON l2_insights
FOR ALL
TO app_user
USING (
    CASE project_rls_mode()
        WHEN 'enforcing' THEN project_id = current_project_id()
        WHEN 'shadow' THEN TRUE  -- Allow but audit
        ELSE TRUE  -- Legacy mode
    END
)
WITH CHECK (
    CASE project_rls_mode()
        WHEN 'enforcing' THEN project_id = current_project_id()
        ELSE TRUE
    END
);
```

### Context Setter (Called at Request Start)

```sql
CREATE OR REPLACE FUNCTION set_project_context(p_project_id VARCHAR(50))
RETURNS void AS $
DECLARE
    v_phase TEXT;
BEGIN
    SELECT migration_phase INTO v_phase
    FROM rls_migration_status WHERE project_id = p_project_id;

    PERFORM set_config('app.current_project', p_project_id, TRUE);  -- TRUE = LOCAL
    PERFORM set_config('app.migration_phase', COALESCE(v_phase, 'legacy'), TRUE);
END;
$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## 2. Three-Phase Gradual Rollout

### Phase 1: Legacy (Keine Enforcement)
- Bestehende Application-Level WHERE Clauses
- RLS Policies installiert aber nicht enforcing
- Baseline Performance Metrics sammeln

### Phase 2: Shadow/Audit (1-2 Wochen pro Projekt-Kohorte)
- Audit Triggers loggen "would-be-blocked" Operations
- Application Bugs werden sichtbar ohne User Impact
- Monitor `rls_audit_log` für Violations

### Phase 3: Enforcing
- RLS als Primary Enforcement
- Application WHERE Clauses als Backup behalten
- Monitor für Empty Results und Errors

### Migration eines Projekts

```sql
-- Shadow Phase aktivieren
UPDATE rls_migration_status
SET migration_phase = 'shadow'
WHERE project_id = 'io';

-- Nach erfolgreicher Shadow Phase
UPDATE rls_migration_status
SET rls_enabled = TRUE,
    migration_phase = 'enforcing',
    migrated_at = NOW()
WHERE project_id = 'io';
```

---

## 3. Shadow Audit Implementation

```sql
CREATE TABLE rls_audit_log (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    project_id VARCHAR(50),
    session_project_id VARCHAR(50),
    table_name TEXT,
    operation TEXT,
    row_data JSONB,
    would_be_blocked BOOLEAN
);

CREATE OR REPLACE FUNCTION audit_rls_violation()
RETURNS TRIGGER AS $
DECLARE
    v_session_project VARCHAR(50);
    v_would_block BOOLEAN;
BEGIN
    v_session_project := current_setting('app.current_project', TRUE);

    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        v_would_block := (OLD.project_id IS DISTINCT FROM v_session_project);
        IF v_would_block THEN
            INSERT INTO rls_audit_log (project_id, session_project_id, table_name,
                                       operation, row_data, would_be_blocked)
            VALUES (OLD.project_id, v_session_project, TG_TABLE_NAME,
                    TG_OP, row_to_json(OLD), TRUE);
        END IF;
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END;
$ LANGUAGE plpgsql SECURITY DEFINER;
```

---

## 4. Rollback Strategies

### Safe Disable with Lock Timeout

```sql
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE l2_insights DISABLE ROW LEVEL SECURITY;
COMMIT;
```

### BYPASSRLS Emergency Role

```sql
CREATE ROLE emergency_access WITH
    LOGIN
    PASSWORD 'strong_password_here'
    BYPASSRLS
    NOINHERIT
    NOSUPERUSER;

GRANT CONNECT ON DATABASE cognitive_memory TO emergency_access;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO emergency_access;
```

### Find and Cancel Blocking Queries

```sql
SELECT pid, now() - query_start as duration, state, query
FROM pg_stat_activity
WHERE state != 'idle' AND query ILIKE '%your_table%'
ORDER BY duration DESC;

SELECT pg_cancel_backend(pid) FROM pg_stat_activity
WHERE pid = blocking_pid AND pid != pg_backend_pid();
```

---

## 5. Performance Monitoring

### RLS Status Check

```sql
SELECT
    n.nspname AS schema_name,
    c.relname AS table_name,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS force_rls,
    COUNT(p.policyname) AS policy_count
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_policies p ON p.schemaname = n.nspname AND p.tablename = c.relname
WHERE c.relkind = 'r' AND c.relrowsecurity = true
GROUP BY n.nspname, c.relname, c.relrowsecurity, c.relforcerowsecurity;
```

### EXPLAIN ANALYZE für RLS Overhead

```sql
-- Als app_user (RLS applied)
SET ROLE app_user;
SET app.current_project = 'io';
EXPLAIN ANALYZE SELECT * FROM l2_insights WHERE content ILIKE '%pattern%';

-- Als BYPASSRLS role (Baseline)
SET ROLE emergency_access;
EXPLAIN ANALYZE SELECT * FROM l2_insights WHERE content ILIKE '%pattern%';
```

### pg_stat_statements Monitoring

```sql
SELECT
    query,
    calls,
    mean_exec_time AS avg_ms,
    (shared_blks_hit::float / NULLIF(shared_blks_hit + shared_blks_read, 0) * 100)::numeric(5,2) AS cache_hit_pct
FROM pg_stat_statements
WHERE calls > 100
  AND (query ILIKE '%current_setting%' OR query ILIKE '%current_project%')
ORDER BY mean_exec_time DESC
LIMIT 20;
```

---

## 6. Critical Pitfalls

### Connection Pool Leakage
- PgBouncer Transaction Mode: Immer `SET LOCAL` verwenden
- Session Variables persist wenn nicht cleared

### Views Bypass RLS
- PostgreSQL 15+: `CREATE VIEW ... WITH (security_invoker = true)`
- Ältere Versionen: Security Barrier Views oder Schema Isolation

### USING vs WITH CHECK
- USING filtert READs
- WITH CHECK validiert WRITEs
- Immer BEIDE für Write Operations!

### Silent Failures
- SELECT gibt leere Ergebnisse, keine Errors
- UPDATE/DELETE melden "0 rows affected"
- **Tests müssen erwartete Daten prüfen, nicht nur Query-Erfolg**

### Index Requirements
```sql
-- Jede RLS-Tabelle braucht project_id Index
CREATE INDEX CONCURRENTLY idx_nodes_project_id ON nodes(project_id);
CREATE INDEX CONCURRENTLY idx_edges_project_id ON edges(project_id);
-- Composite für häufige Query Patterns
CREATE INDEX CONCURRENTLY idx_nodes_project_name ON nodes(project_id, name);
```

---

## 7. Anwendung auf cognitive-memory

### Neue Requirements identifiziert:

| ID | Requirement | Epic |
|----|-------------|------|
| FR-NEW-1 | System kann `rls_migration_status` Tabelle verwalten | 9.2 |
| FR-NEW-2 | System kann `set_project_context()` Function ausführen | 9.3 |
| FR-NEW-3 | System kann Shadow Audit Triggers aktivieren | 9.3 |
| NFR-NEW-1 | BYPASSRLS Emergency Role für Debugging | 9.3 |
| NFR-NEW-2 | Lock Timeout bei RLS Disable (5s) | 9.3 |

### Migration Sequence für 8 Projekte:

1. **Batch 1 (Low Risk):** `sm` (semantic-memory) - isoliert, wenig Daten
2. **Batch 2:** `motoko` - isoliert, eigener Scope
3. **Batch 3:** `ab`, `aa`, `bap` - SHARED Level, testen ACL
4. **Batch 4:** `echo`, `ea` - SUPER Level, lesen alles
5. **Batch 5:** `io` - SUPER Level, Legacy Owner, kritischste Migration

---

## Referenzen

- PostgreSQL Documentation: Row Security Policies
- AWS SaaS Factory: Multi-tenant Architecture Patterns
- PgBouncer: Transaction Pooling Best Practices
