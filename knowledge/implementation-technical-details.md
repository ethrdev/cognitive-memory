# Implementation Technical Details

> Research Summary from Deep Research (2026-01-22)
> Source: Vier technische Kernfragen für PostgreSQL Multi-Tenant Backend

## Executive Summary

Vier kritische Implementierungsfragen beantwortet:
1. **asyncpg + RLS**: `SET LOCAL` ist transaktionssicher, keine Race Conditions
2. **pgvector**: Bei ~10k Vektoren/Tenant reicht RLS, Partitioning nicht nötig
3. **MCP SDK**: Header-Zugriff via `contextvars` Workaround
4. **Alembic**: Hybrid-Ansatz mit `alembic_utils` für RLS-Policies

---

## 1. asyncpg und RLS: Thread-Safety

### Kernaussage

`SET LOCAL` ist inhärent sicher für Connection Pooling - PostgreSQL setzt Werte automatisch am Transaktionsende zurück.

### Empfohlenes Pattern

```python
async def execute_with_tenant(pool: asyncpg.Pool, tenant_id: str, query: str, *args):
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL app.current_tenant = $1", tenant_id)
            return await conn.fetch(query, *args)
            # Transaktion endet hier → SET LOCAL wird automatisch zurückgesetzt
```

### Sicherheitsregeln

- ✅ `SET LOCAL` verwenden (nicht `SET`)
- ✅ Jede Operation in expliziter Transaktion (`async with conn.transaction()`)
- ✅ Keine Connection-Objekte zwischen Tasks teilen
- ✅ Pool-Konfiguration: `min_size=5, max_size=20` als Startpunkt

### PgBouncer Kompatibilität

| Pooling-Methode | SET LOCAL | Prepared Statements | Empfehlung |
|-----------------|-----------|---------------------|------------|
| asyncpg.Pool | ✅ Sicher | ✅ Funktioniert | Standard für Python-Apps |
| PgBouncer Transaction | ✅ Sicher | ⚠️ `statement_cache_size=0` | Multi-App-Szenarien |
| PgBouncer Session | ⚠️ Riskant | ✅ Funktioniert | Nur wenn nötig |

---

## 2. pgvector Multi-Tenancy: RLS genügt

### Kernaussage

Für **~10.000 Vektoren pro Tenant ist Partitioning nicht notwendig**. B-Tree-Index auf `project_id` + RLS liefert ausreichende Performance.

### pgvector 0.8.0+ Iterative Scans

Das historische "Overfiltering"-Problem ist gelöst:

```sql
-- Aktivieren für bessere Multi-Tenant Performance
SET hnsw.iterative_scan = 'relaxed_order';
SET hnsw.max_scan_tuples = 20000;

SELECT * FROM embeddings
ORDER BY embedding <=> '[query_vector]'
LIMIT 10;
-- Scannt automatisch mehr Index-Einträge bis 10 Ergebnisse gefunden
```

**Ergebnis**: Bis zu 9x schnellere Queries und 100x mehr relevante Ergebnisse.

### Skalierungs-Empfehlungen

| Skalierungsstufe | Empfohlener Ansatz |
|------------------|-------------------|
| < 10.000 Vektoren/Tenant | Exakte Suche + RLS (perfekter Recall) |
| 10.000 – 100.000 | HNSW + RLS + Iterative Scans |
| 100.000 – 1M | Partitioning evaluieren |
| > 1M | Partitioning oder Sharding (Citus) |

### Für cognitive-memory

Mit aktuell ~wenigen tausend L2-Insights und 8 Projekten:
- **RLS + Index auf `project_id`** ist optimal
- HNSW-Index bleibt global (kein Partitioning nötig)
- pgvector 0.8.0+ für Iterative Scans nutzen

---

## 3. MCP Python SDK: Header-Zugriff

### Limitation

Das offizielle MCP SDK (v1.25.0) bietet **keinen direkten Zugang zu HTTP-Headern** innerhalb von Tools (GitHub Issue #750).

### Workaround: contextvars + Starlette Middleware

```python
from starlette.middleware.base import BaseHTTPMiddleware
import contextvars

# Context Variable für Request-scoped Header
request_headers = contextvars.ContextVar("headers", default={})

class HeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_headers.set(dict(request.headers))
        return await call_next(request)

# In MCP Tool
@mcp.tool()
def authenticated_tool() -> str:
    headers = request_headers.get()
    project_id = headers.get("x-project-id", "")
    if not project_id:
        raise ValueError("Missing X-Project-ID header")
    # ...
```

### Alternative: Third-Party `fastmcp`

```bash
pip install fastmcp
```

Bietet direkten Header-Zugriff via `get_http_headers()` und vollständiges Middleware-System.

### OAuth 2.1 (falls benötigt)

```python
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

class MyTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        # JWT validieren, Issuer/Audience prüfen
        pass

mcp = FastMCP(
    "Service",
    token_verifier=MyTokenVerifier(),
    auth=AuthSettings(
        issuer_url="https://auth.example.com",
        required_scopes=["user"],
    ),
)
```

### Hinweis

MCP SDK v2.0 geplant für Q1 2026 mit Breaking Changes - auf Migration vorbereitet sein.

---

## 4. Alembic für RLS: Hybrid-Ansatz

### Kernaussage

Alembic hat keine native RLS-Unterstützung - **`alembic_utils`** ergänzt PostgreSQL-spezifische Features.

### Installation

```bash
pip install alembic-utils
```

### RLS Policy Migration

```python
from alembic import op

def upgrade():
    # Tabelle erstellen
    op.create_table("l2_insights", ...)

    # RLS aktivieren
    op.execute("ALTER TABLE l2_insights ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE l2_insights FORCE ROW LEVEL SECURITY;")

    # Policy definieren
    op.execute("""
        CREATE POLICY project_isolation ON l2_insights
        FOR ALL
        USING (project_id = current_setting('app.current_project', true))
        WITH CHECK (project_id = current_setting('app.current_project', true));
    """)

def downgrade():
    op.execute("DROP POLICY IF EXISTS project_isolation ON l2_insights;")
    op.execute("ALTER TABLE l2_insights DISABLE ROW LEVEL SECURITY;")
```

### alembic_utils für Autogenerate

| Objekt | alembic_utils Klasse | Autogenerate |
|--------|---------------------|--------------|
| RLS Policies | `PGPolicy` | ✅ |
| Functions | `PGFunction` | ✅ |
| Views | `PGView` | ✅ |
| Extensions | `PGExtension` | ✅ |
| Triggers | `PGTrigger` | ✅ |

### pgvector in Alembic

In `env.py` registrieren:

```python
import pgvector.sqlalchemy
connection.dialect.ischema_names['vector'] = pgvector.sqlalchemy.Vector
```

### CI/CD Best Practice

```yaml
- name: Check single head
  run: |
    python -c "
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    config = Config('alembic.ini')
    ScriptDirectory.from_config(config).get_current_head()
    "

- name: Test migrations
  run: |
    alembic upgrade head
    alembic downgrade -1
    alembic upgrade head
```

---

## Zusammenfassung: Implementierungs-Checkliste

### asyncpg Setup
- [ ] `SET LOCAL` in allen DB-Operationen
- [ ] Explizite Transaktionen (`async with conn.transaction()`)
- [ ] Pool-Konfiguration: `min_size=5, max_size=20`

### pgvector Setup
- [ ] Version 0.8.0+ installiert
- [ ] Iterative Scans aktiviert (`SET hnsw.iterative_scan = 'relaxed_order'`)
- [ ] B-Tree-Index auf `project_id` für alle Tabellen

### MCP Server Setup
- [ ] `contextvars` für Header-Propagierung
- [ ] Starlette Middleware für Header-Extraktion
- [ ] Error-Response bei fehlendem X-Project-ID Header

### Migrations Setup
- [ ] `alembic-utils` installiert
- [ ] RLS Policies als Raw SQL in Migrations
- [ ] CI-Pipeline mit Single-Head-Check
- [ ] Downgrade-Tests für alle Migrations

---

## Referenzen

- PostgreSQL Documentation: SET LOCAL
- pgvector 0.8.0 Release Notes: Iterative Index Scans
- MCP Python SDK GitHub: Issue #750
- alembic_utils Documentation
- Heroku: PgBouncer Best Practices
