# RLS Policies for Core Tables

**Story:** 11.3.3
**Migration:** 036_rls_policies_core_tables.sql
**Tables:** l2_insights, nodes, edges

## Overview

This document describes the Row-Level Security (RLS) policies implemented on the core tables of the Cognitive Memory System. These policies enforce project isolation at the database level with conditional enforcement support for gradual rollout.

## Policy Structure

Each core table has **5 policies** (1 RESTRICTIVE + 4 PERMISSIVE):

| Policy | Type | Purpose |
|--------|------|---------|
| `require_project_id` | RESTRICTIVE | Blocks rows with NULL project_id (defense-in-depth) |
| `select_{table}` | PERMISSIVE | Conditional READ enforcement by rls_mode |
| `insert_{table}` | PERMISSIVE | Own-project-only write access |
| `update_{table}` | PERMISSIVE | Own-project-only write access |
| `delete_{table}` | PERMISSIVE | Own-project-only write access |

### RESTRICTIVE Policy (Defense-in-Depth)

```sql
CREATE POLICY require_project_id ON {table}
AS RESTRICTIVE
FOR ALL
USING (project_id IS NOT NULL);
```

**Why RESTRICTIVE?**
- Evaluates BEFORE permissive policies
- Ensures rows with NULL project_id are NEVER visible
- Fail-safe protection against data leaks

### SELECT Policy (Conditional Enforcement)

```sql
CREATE POLICY select_{table} ON {table}
FOR SELECT
USING (
    CASE (SELECT get_rls_mode())
        WHEN 'pending' THEN TRUE  -- Legacy behavior
        WHEN 'shadow' THEN TRUE   -- Audit-only mode
        WHEN 'enforcing' THEN project_id = ANY (SELECT get_allowed_projects())
        WHEN 'complete' THEN project_id = ANY (SELECT get_allowed_projects())
        ELSE TRUE  -- Fail-safe
    END
);
```

**Subquery Pattern Critical:**
- `(SELECT get_rls_mode())` ensures single evaluation per query
- `(SELECT get_allowed_projects())` ensures single evaluation per query
- Without subqueries, IMMUTABLE functions are evaluated PER ROW (14x slower)

### INSERT/UPDATE/DELETE Policies (Own-Project-Only)

```sql
-- INSERT
CREATE POLICY insert_{table} ON {table}
FOR INSERT
WITH CHECK (project_id = (SELECT get_current_project()));

-- UPDATE
CREATE POLICY update_{table} ON {table}
FOR UPDATE
USING (project_id = (SELECT get_current_project()))
WITH CHECK (project_id = (SELECT get_current_project()));

-- DELETE
CREATE POLICY delete_{table} ON {table}
FOR DELETE
USING (project_id = (SELECT get_current_project()));
```

**Write Isolation is Absolute:**
- Even super users cannot write to other projects
- Applies to ALL migration phases (pending, shadow, enforcing, complete)

## Migration Phases

| Phase | Behavior | Use Case |
|-------|----------|----------|
| `pending` | No enforcement - all rows visible | Legacy behavior before RLS |
| `shadow` | All rows visible - violations logged | Pre-enforcement validation |
| `enforcing` | RLS active - filtered by allowed_projects | Active project isolation |
| `complete` | RLS active - filtered by allowed_projects | Final state |

## Access Control Matrix

| Project | Access Level | Can Read | Can Write |
|---------|--------------|----------|-----------|
| io | super | All projects | Own only |
| echo | super | All projects | Own only |
| ea | super | All projects | Own only |
| aa | shared | aa + sm | Own only |
| ab | shared | ab + sm | Own only |
| bap | shared | bap + sm | Own only |
| motoko | isolated | motoko only | Own only |
| sm | isolated | sm only | Own only |

**Schreibrechte:** Jedes Projekt kann NUR in eigene Daten schreiben.

## Key Implementation Patterns

### 1. Subquery Pattern for IMMUTABLE Functions

```sql
-- WRONG: Evaluates PER ROW (14x slower)
project_id = ANY (get_allowed_projects())

-- CORRECT: Single evaluation per query
project_id = ANY (SELECT get_allowed_projects())
```

### 2. SET LOCAL Pattern for Transaction Scoping

```python
# WRONG: Context may be lost
await conn.execute("SELECT set_project_context('aa')")

# CORRECT: Context preserved within transaction
async with conn.transaction():
    await conn.execute("SELECT set_project_context('aa')")
    await conn.execute("SELECT ...")  # Context available
```

### 3. Separate Policies per Operation

PostgreSQL requires separate policies for different operations because:
- READ uses `get_allowed_projects()` (multi-project access)
- WRITE uses `get_current_project()` (own-project-only)
- Cannot use `FOR ALL` due to different access logic

## FORCE ROW LEVEL SECURITY

```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
```

**Why FORCE?**
- Applies to table owners (superusers) too
- Prevents privilege escalation via table ownership
- Critical for security in multi-tenant environments

## Performance

### Index Usage

RLS policies automatically use indexes when available:

```sql
-- Query plan shows:
Index Cond: (project_id = ANY ('{aa,sm}'::text[]))
```

### Overhead

- Target: <10ms per query
- Achieved via subquery pattern (IMMUTABLE functions)
- Verified via `EXPLAIN ANALYZE`

## Rollback Procedure

To rollback RLS policies:

```bash
# Run rollback migration
psql $DATABASE_URL -f mcp_server/db/migrations/036_rls_policies_core_tables_rollback.sql
```

**What gets removed:**
- All 5 policies per table (15 total)
- FORCE ROW LEVEL SECURITY
- ROW LEVEL SECURITY (disabled)

**What stays:**
- project_id columns (Migration 027)
- Indexes on project_id (Migration 029)
- Helper functions (Migration 034)

## Testing

### pgTAP Tests

```bash
# Run all pgTAP RLS tests
pg_prove -d $DATABASE_URL tests/db/pgtap/test_rls_l2_insights.sql
pg_prove -d $DATABASE_URL tests/db/pgtap/test_rls_nodes.sql
pg_prove -d $DATABASE_URL tests/db/pgtap/test_rls_edges.sql
```

### Integration Tests

```bash
# Run pytest integration tests
pytest tests/integration/test_rls_core_tables.py -v
```

## Common Pitfalls

| Wrong | Right | Why |
|-------|-------|-----|
| `get_allowed_projects()` | `(SELECT get_allowed_projects())` | Single evaluation per query |
| Only USING for UPDATE | Both USING and WITH CHECK | USING filters existing, WITH CHECK validates new |
| No RESTRICTIVE policy | Always add RESTRICTIVE first | Defense-in-depth for NULL |
| FOR ALL | Separate per operation | Different read/write logic needed |
| Missing subquery in CASE | `(SELECT get_rls_mode())` | Single evaluation per query |

## References

- **Story 11.3.1:** RLS Helper Functions (IMMUTABLE wrappers)
- **Story 11.3.2:** Shadow Audit Infrastructure (shadow mode)
- **Story 11.3.0:** pgTAP + Test Infrastructure
- **Epic 11.2:** Access Control Tables (project_registry, project_read_permissions)
