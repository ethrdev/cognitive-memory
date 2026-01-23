# MCP Middleware: Official SDK vs. FastMCP

> Research Summary: 2026-01-22
> Source: Deep Research F3 - Middleware-Architekturen im MCP Python SDK
> Status: VALIDATED

## Executive Summary

Das offizielle MCP Python SDK bietet Hook-basierte Interception mit eingeschränktem Header-Zugriff. **FastMCP (Standalone v2/v3)** implementiert eine vollständige Middleware-Pipeline mit Dependency Injection und nativem Header-Zugriff.

**Empfehlung:** FastMCP für produktive Multi-Tenant-Szenarien.

---

## Architektur-Vergleich

| Feature | Official SDK (v1.x) | FastMCP Standalone (v2/v3) |
|---------|---------------------|---------------------------|
| Middleware-Support | Hook-basiert, manuell | Deklarative Pipeline |
| Header-Zugriff | Eingeschränkt (Issue #750) | Nativ via `get_http_headers()` |
| Dependency Injection | Nicht vorhanden | Integriertes Docket-DI |
| Komponenten-Abstraktion | Direkt auf Primitiven | Components, Providers, Transforms |
| Multi-Tenancy Fokus | Basale Authorization | Umfassende Auth-Module |
| SDK v2.0 Kompatibilität | Referenz-Standard | Framework-abhängig |

---

## Official SDK: Request-Interception

### Limitation: Issue #750
Das SDK bietet keinen direkten Zugang zu HTTP-Headern in Tool-Handlern bei Streamable-HTTP-Transport.

### Workaround: contextvars + Starlette
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
async def hybrid_search(query_text: str) -> list:
    headers = request_headers.get()
    project_id = headers.get("x-project-id")
    if not project_id:
        raise ValueError("Missing X-Project-ID header")
    # ...
```

### request_context Zugriff
```python
@mcp.tool()
async def my_tool(ctx: Context) -> str:
    # Zugriff auf Session-Metadaten
    session_data = ctx.request_context
    client_info = ctx.client_info
    # ...
```

---

## FastMCP: Bidirektionale Middleware-Pipeline

### Architektur
```
Request  ──►  on_request  ──►  on_call_tool  ──►  Tool Handler
                                                        │
Response ◄──  on_request  ◄──  on_call_tool  ◄──────────┘
```

### Middleware-Hooks

| Hook | Auslöser | Use Case |
|------|----------|----------|
| `on_request` | Jede JSON-RPC Nachricht | Rate Limiting, Logging |
| `on_initialize` | Verbindungsaufbau | Client-Validierung, Reject |
| `on_call_tool` | Tool-Aufruf | ACL, Argument-Transformation |
| `on_list_tools` | Tool-Listing | Dynamische Tool-Filterung |

### Implementierung
```python
from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware

class TenantMiddleware(Middleware):
    async def on_initialize(self, ctx, next_handler):
        client_info = ctx.client_info
        # Reject unauthorized clients
        if not await self.validate_client(client_info):
            raise AuthenticationError("Unauthorized client")
        return await next_handler(ctx)

    async def on_call_tool(self, ctx, tool_name, arguments, next_handler):
        # Inject tenant context
        project_id = self.extract_project_id(ctx)
        ctx.set("project_id", project_id)
        return await next_handler(ctx, tool_name, arguments)

mcp = FastMCP("cognitive-memory")
mcp.add_middleware(TenantMiddleware())
```

---

## FastMCP: Dependency Injection (Docket)

### Konzept
Abhängigkeiten werden als Parameter deklariert und zur Laufzeit aufgelöst. **Kritisch:** DI-Parameter werden automatisch aus dem JSON-Schema für LLMs entfernt.

### Beispiel
```python
from fastmcp import FastMCP, Context
from fastmcp.server.dependencies import Depends

async def get_db_connection():
    async with pool.acquire() as conn:
        yield conn

async def get_current_project(ctx: Context) -> str:
    headers = ctx.http_headers
    return headers.get("X-Project-ID", "legacy")

@mcp.tool()
async def hybrid_search(
    query_text: str,
    # DI-Parameter (nicht im LLM-Schema sichtbar)
    conn = Depends(get_db_connection),
    project_id: str = Depends(get_current_project)
) -> list:
    await conn.execute(
        "SELECT set_config('app.current_project', $1, true)",
        project_id
    )
    # Query ausführen...
```

### Sicherheitsvorteil
```python
# LLM sieht dieses Schema:
{
  "name": "hybrid_search",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query_text": {"type": "string"}
    },
    "required": ["query_text"]
  }
}
# project_id und conn sind NICHT sichtbar
```

---

## Header-Zugriff im Vergleich

### Official SDK (Workaround)
```python
import contextvars

project_context = contextvars.ContextVar("project_id")

# In Starlette Middleware
project_context.set(request.headers.get("X-Project-ID"))

# In Tool
project_id = project_context.get()
```

### FastMCP (Native)
```python
from fastmcp.server.dependencies import get_http_headers

@mcp.tool()
async def my_tool() -> str:
    headers = get_http_headers()
    project_id = headers.get("X-Project-ID")
    # ...
```

---

## Multi-Tenant Production Pattern

### OAuth Resource Server
```python
from fastmcp import FastMCP
from fastmcp.server.auth import AuthMiddleware

class OAuthValidator:
    async def validate_token(self, token: str) -> dict:
        # JWT validieren gegen Identity Provider
        claims = await self.idp.verify(token)
        return {
            "user_id": claims["sub"],
            "tenant_id": claims["tenant"],
            "scopes": claims["scope"].split()
        }

mcp = FastMCP("cognitive-memory")
mcp.add_middleware(AuthMiddleware(validator=OAuthValidator()))
```

### Horizontale Skalierung mit Redis
```python
from fastmcp.session import RedisSessionStore

mcp = FastMCP(
    "cognitive-memory",
    session_store=RedisSessionStore(
        redis_url="redis://localhost:6379"
    )
)
```

---

## Migration: Official SDK → FastMCP

### Import-Änderungen
```python
# VORHER (Official SDK)
from mcp.server import Server
from mcp.types import Tool

# NACHHER (FastMCP Standalone)
from fastmcp import FastMCP
# Tools werden via Decorator registriert
```

### Versioning
```
# requirements.txt
fastmcp>=2.9,<4  # Aktuell stabil
# oder
fastmcp>=3.0,<4  # Mit neuester Middleware-API
```

### FastMCP v4.0 Roadmap
- Integration von MCP SDK v2.0 Änderungen
- Breaking Changes bei Transport-Handling erwartet

---

## Entscheidungsmatrix

| Kriterium | Official SDK | FastMCP |
|-----------|--------------|---------|
| Entwicklungsaufwand | Hoch | Niedrig |
| Zukunftssicherheit | Sehr Hoch | Mittel |
| Performance | Hoch | Sehr Hoch |
| Middleware-Flexibilität | Begrenzt | Umfassend |
| Header-Zugriff | Workaround nötig | Native |
| DI-System | Manuell | Integriert |
| Dokumentation | Spezifikations-fokussiert | Lösungs-orientiert |

### Empfehlung für cognitive-memory

**FastMCP Standalone v3.x** für:
- Native Middleware-Pipeline
- Integriertes DI für project_id Injection
- Besserer Header-Zugriff
- Production-ready Auth-Module

**Risiko-Mitigation:**
```python
# requirements.txt
fastmcp>=3.0,<4  # Pin auf Major Version

# Abstraktion für spätere Migration
from cognitive_memory.mcp import get_project_context
# Implementierung kann später ausgetauscht werden
```

---

## Referenzen

- GitHub Issue #750: HTTP Headers in Tool Logic
- GitHub Issue #1509: Per-Request Headers
- FastMCP Documentation: Middleware (gofastmcp.com)
- FastMCP Documentation: Dependency Injection
- FastMCP Releases: Changelog
