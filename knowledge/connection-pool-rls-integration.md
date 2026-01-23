# Connection Pool + SET LOCAL: RLS-Integration

> Research Summary: 2026-01-22
> Source: Deep Research F5 - Connection Pool und Transaktionsmanagement
> Status: VALIDATED

## Executive Summary

`SET LOCAL` ist der einzig sichere Mechanismus für Mandanten-Kontext in Connection-Pool-Umgebungen. Es erfordert **explizite Transaktionen** und wird bei COMMIT/ROLLBACK automatisch zurückgesetzt.

**Kritische Erkenntnis:** Der aktuelle psycopg2.SimpleConnectionPool funktioniert, erfordert aber diszipliniertes Transaction-Management. **asyncpg** bietet automatische Cleanup-Mechanismen und wird für Production empfohlen.

---

## SET LOCAL vs. SET SESSION

| Scope | Lebensdauer | Pool-Sicherheit | Empfehlung |
|-------|-------------|-----------------|------------|
| `SET` (default) | Session | ❌ Gefährlich | NICHT verwenden |
| `SET SESSION` | Session | ❌ Gefährlich | NICHT verwenden |
| `SET LOCAL` | Transaktion | ✅ Sicher | **VERWENDEN** |

### Warum SET SESSION gefährlich ist

```python
# GEFÄHRLICH: Context-Leak zwischen Requests
conn = pool.getconn()
cursor = conn.cursor()
cursor.execute("SET app.current_project = 'ProjectA'")  # SESSION scope!
# ... queries ...
pool.putconn(conn)

# Nächster Request (anderer Mandant) erhält dieselbe Connection
conn = pool.getconn()  # GLEICHE Connection mit ProjectA context!
cursor.execute("SELECT * FROM l2_insights")  # Sieht ProjectA Daten!
```

### Warum SET LOCAL sicher ist

```python
# SICHER: Context automatisch zurückgesetzt
with pool.getconn() as conn:
    with conn:  # Startet Transaction
        with conn.cursor() as cur:
            cur.execute("SET LOCAL app.current_project = %s", (project_id,))
            cur.execute("SELECT * FROM l2_insights")
            # ... business logic ...
    # COMMIT hier -> SET LOCAL wird automatisch zurückgesetzt
pool.putconn(conn)
# Connection ist sauber für nächsten Request
```

---

## Explizite Transaktionen: Pflicht für SET LOCAL

### Das Problem

SET LOCAL funktioniert NUR innerhalb einer expliziten Transaktion. In autocommit-Modus wird jedes Statement in einer eigenen Mikro-Transaktion ausgeführt.

```python
# BROKEN: autocommit=True
conn.autocommit = True
cur.execute("SET LOCAL app.current_project = 'aa'")  # Transaction endet HIER
cur.execute("SELECT * FROM l2_insights")  # Kein Context mehr!
```

### Die Lösung

```python
# CORRECT: Explizite Transaction
conn.autocommit = False
with conn:  # Context Manager startet Transaction
    with conn.cursor() as cur:
        cur.execute("SET LOCAL app.current_project = %s", (project_id,))
        # Alle Queries hier haben den Context
        cur.execute("SELECT * FROM l2_insights")
# COMMIT bei Exit -> SET LOCAL automatisch cleared
```

---

## psycopg2 Best Practices

### Empfohlenes Pattern für cognitive-memory

```python
# mcp_server/db/connection.py

from contextlib import contextmanager
from psycopg2 import pool

_pool = pool.SimpleConnectionPool(minconn=5, maxconn=20, dsn=DATABASE_URL)

@contextmanager
def get_connection_with_project_context(project_id: str):
    """
    Get a pooled connection with RLS context set.
    Context is automatically cleared on exit via transaction rollback/commit.
    """
    conn = _pool.getconn()
    try:
        with conn:  # Explicit transaction block
            with conn.cursor() as cur:
                # Set RLS context (transaction-scoped)
                cur.execute("SELECT set_project_context(%s)", (project_id,))
                yield cur
        # COMMIT on successful exit -> SET LOCAL cleared
    except Exception:
        conn.rollback()  # ROLLBACK -> SET LOCAL cleared
        raise
    finally:
        _pool.putconn(conn)  # Connection zurück in Pool (clean state)
```

### Connection Health Check

```python
def validate_connection(conn) -> bool:
    """
    Validate connection before using (detect ghost connections).
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None
    except Exception:
        return False
```

---

## Cleanup-Strategien

| Strategie | Performance | Sicherheit | Empfehlung |
|-----------|-------------|------------|------------|
| `COMMIT/ROLLBACK` | ✅ Minimal | ✅ Für SET LOCAL | **Standard** |
| `RESET app.current_project` | ✅ Gering | ✅ Gezielt | Bei SESSION vars |
| `RESET ALL` | ⚠️ Moderat | ✅ Umfassend | Bei Unsicherheit |
| `DISCARD ALL` | ❌ Hoch | ✅ Maximal | Nur bei Paranoia |

### Wann DISCARD ALL vermeiden

- Invalidiert Plan-Cache für Prepared Statements
- Erhöht CPU-Last signifikant
- Zerstört temporäre Tabellen
- Nur nötig bei expliziter SESSION-Variable-Nutzung

---

## Query Planner und plan_cache_mode

### Das Performance-Problem

PostgreSQL wechselt nach 5 Ausführungen von "custom plan" zu "generic plan". Bei RLS mit `current_setting()` kann dies zu Sequential Scans führen.

```sql
-- Generic Plan kennt tenant_id nicht -> Sequential Scan möglich
SELECT * FROM l2_insights WHERE project_id = current_setting('app.current_project');
```

### Die Lösung

```sql
-- Für den Applikations-User setzen
ALTER ROLE mcp_app_user SET plan_cache_mode = 'force_custom_plan';
```

| Setting | Verhalten | RLS-Eignung |
|---------|-----------|-------------|
| `auto` (default) | Wechselt zu generic nach 5x | ❌ Riskant |
| `force_custom_plan` | Immer custom mit aktuellen Werten | ✅ Empfohlen |
| `force_generic_plan` | Immer generic | ❌ Schlecht für RLS |

---

## asyncpg: Die bessere Alternative

### Vorteile gegenüber psycopg2

| Feature | psycopg2 | asyncpg |
|---------|----------|---------|
| Transaction Model | Implizit, manuell | Explizit `async with conn.transaction()` |
| Auto-Reset bei Pool-Return | ❌ Manuell | ✅ Automatisch (RESET ALL; UNLISTEN *; CLOSE ALL;) |
| Performance | Standard | 3x schneller (binary protocol) |
| Async Support | Nein (blocking) | Native asyncio |

### asyncpg Pattern

```python
import asyncpg

pool = await asyncpg.create_pool(DATABASE_URL)

async def get_connection_with_context(project_id: str):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SELECT set_project_context($1)", project_id)
            # ... queries ...
    # Connection automatisch zurück in Pool mit Reset
```

### Automatischer Reset in asyncpg

asyncpg führt bei jeder Pool-Rückgabe automatisch aus:
```sql
RESET ALL;
UNLISTEN *;
CLOSE ALL;
```

Dies eliminiert das Risiko von Context-Leaks vollständig.

---

## Empfehlung für cognitive-memory

### Kurzfristig (Epic 9.4)

1. **psycopg2 beibehalten** mit striktem Transaction-Management
2. **Alle DB-Operationen** in `get_connection_with_project_context()` wrappen
3. **SET LOCAL** (nicht SET SESSION) für `set_project_context()`
4. **plan_cache_mode = force_custom_plan** für mcp_app_user

### Mittelfristig (Post-Epic 9)

1. **Migration zu asyncpg** evaluieren
2. Native async-Transaktionen nutzen
3. Automatisches Connection-Reset als Sicherheitsnetz

---

## Monitoring

### Idle-in-Transaction Detection

```sql
SELECT pid, state, query, xact_start, query_start
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND xact_start < NOW() - INTERVAL '5 minutes';
```

Hohe Anzahl = Fehler im Transaction-Management!

### Context-Leak Detection (Debug)

```sql
-- Nach Pool-Return sollte dies NULL sein
SELECT current_setting('app.current_project', TRUE);
```

---

## Referenzen

- PostgreSQL Docs: SET LOCAL
- psycopg2 Docs: Connection Context Managers
- asyncpg Docs: Pool Management
- AWS Blog: RLS with Connection Pooling
