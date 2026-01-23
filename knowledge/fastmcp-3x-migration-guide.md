# FastMCP 3.x Migration Guide

> Research Summary: 2026-01-22
> Source: Deep Research F6 - FastMCP Migration und Tool-Kompatibilität
> Status: VALIDATED

## Executive Summary

FastMCP 3.x führt eine grundlegende Architektur-Änderung ein: **Components, Providers, Transforms**. Die Migration vom Official SDK erfordert Import-Änderungen, aber der `@mcp.tool()`-Decorator bleibt weitgehend kompatibel.

**Kritische Änderung:** Decorated Functions sind in 3.x wieder direkt aufrufbar (Unit-Testing möglich!).

---

## Die drei Primitives in FastMCP 3.x

### 1. Components (Atome des Kontexts)

Components sind die atomaren Einheiten: **Tools, Resources, Prompts**.

```python
# Component = Tool mit Name, Schema, Verhalten
@mcp.tool(
    name="hybrid_search",
    description="Search across memory layers",
    version="2.0.0"  # NEU in 3.x
)
async def hybrid_search(query: str) -> str:
    ...
```

### 2. Providers (Quellen von Capabilities)

Providers definieren, woher Components stammen:
- Lokale Funktionen (`LocalProvider`)
- Dateisystem-Verzeichnisse (`FileSystemProvider`)
- Remote MCP Server (`RemoteProvider`)
- OpenAPI Specs (`OpenAPIProvider`)

```python
# Mehrere Provider kombinieren
mcp = FastMCP("cognitive-memory")
mcp.add_provider(local_tools)
mcp.add_provider(remote_memory_server)
```

### 3. Transforms (Middleware für Component-Pipeline)

Transforms modifizieren Components bevor sie zum Client gelangen:

```python
# Namespace-Prefix hinzufügen
from fastmcp.transforms import Namespace

mcp.add_transform(Namespace(prefix="memory"))
# Tool "search" wird zu "memory_search"
```

---

## Schritt-für-Schritt Migration

### 1. Dependencies aktualisieren

```bash
# requirements.txt
fastmcp>=3.0.0b1,<4

# Installation
pip install "fastmcp>=3.0.0b1"
# oder
uv add "fastmcp>=3.0.0b1"

# Version prüfen
fastmcp version
# Erwartung: 3.0.x mit MCP SDK 1.25.0+
```

### 2. Imports ändern

```python
# VORHER (Official SDK)
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool, InputSchema

# NACHHER (FastMCP Standalone 3.x)
from fastmcp import FastMCP
from fastmcp.types import Tool  # Falls nötig
```

### 3. Tool-Handler refaktorieren

```python
# VORHER (Official SDK mit Callback-Pattern)
@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "hybrid_search":
        query = arguments.get("query")
        # ... validation ...
        return CallToolResult(content=[TextContent(text=result)])
    elif name == "graph_add_node":
        # ...

# NACHHER (FastMCP 3.x mit Decorators)
@mcp.tool()
async def hybrid_search(query: str, top_k: int = 5) -> str:
    """Search across memory layers."""
    # Validation automatisch via Pydantic
    result = await perform_search(query, top_k)
    return result  # String wird automatisch in TextContent gewrappt
```

---

## Decorator-Kompatibilität

### @mcp.tool() Signatur in 3.x

| Parameter | Typ | Beschreibung | Breaking? |
|-----------|-----|--------------|-----------|
| `name` | str | Tool-Name (überschreibt Funktionsname) | Nein |
| `description` | str | Überschreibt Docstring | Nein |
| `version` | str/int | **NEU:** Versionierung | Nein |
| `timeout` | float | **NEU:** Timeout pro Tool | Nein |
| `enabled` | - | **ENTFERNT:** Nutze `mcp.enable()/disable()` | Ja |

### Decorated Functions sind aufrufbar!

**Kritische Verbesserung in 3.x:**

```python
# In 2.x: Decorator transformiert zu FunctionTool-Objekt
# Direkter Aufruf war nicht möglich

# In 3.x: Funktion bleibt aufrufbar
@mcp.tool()
async def hybrid_search(query: str) -> str:
    ...

# Unit-Test funktioniert!
async def test_hybrid_search():
    result = await hybrid_search("test query")
    assert "results" in result
```

---

## Breaking Changes 2.x → 3.x

### 1. Listing Methods: dict → list

```python
# VORHER (2.x)
tools = mcp.get_tools()
my_tool = tools["hybrid_search"]  # Dict-Zugriff

# NACHHER (3.x)
tools = mcp.get_tools()
my_tool = next(t for t in tools if t.name == "hybrid_search")  # List-Iteration
```

### 2. State Methods sind async

```python
# VORHER (2.x)
state = ctx.get_state("history")
ctx.set_state("history", new_value)

# NACHHER (3.x)
state = await ctx.get_state("history")
await ctx.set_state("history", new_value)
```

**Session State TTL:** Default 1 Tag (verhindert Memory-Leaks)

### 3. Transport-Änderungen

```python
# VORHER (2.x)
from fastmcp.transports import WSTransport  # WebSocket

# NACHHER (3.x)
from fastmcp.transports import StreamableHttpTransport  # HTTP+SSE
# WSTransport wurde entfernt!
```

### 4. Metadata Namespace

```python
# VORHER (2.x)
metadata["_fastmcp"]["version"]

# NACHHER (3.x)
metadata["fastmcp"]["version"]
```

### 5. CLI Einstellungen

```bash
# VORHER
FASTMCP_SHOW_CLI_BANNER=false

# NACHHER
FASTMCP_SHOW_SERVER_BANNER=false
```

---

## Middleware in FastMCP 3.x

### Transforms vs. Middleware

| Aspekt | Transforms | Middleware |
|--------|-----------|------------|
| Wirkt auf | Component-Definitionen | Request-Ausführung |
| Zeitpunkt | Bei `list_tools()` | Bei `call_tool()` |
| Zweck | Visibility, Naming, Filtering | Auth, Logging, Rate Limiting |

### Middleware-Hooks

```python
from fastmcp.server.middleware import Middleware

class TenantMiddleware(Middleware):
    async def on_message(self, ctx, next_handler):
        """Alle JSON-RPC Nachrichten (inkl. Notifications)"""
        return await next_handler(ctx)

    async def on_request(self, ctx, next_handler):
        """Nur Requests mit erwarteter Response"""
        # Auth-Check hier
        return await next_handler(ctx)

    async def on_call_tool(self, ctx, tool_name, arguments, next_handler):
        """Spezifisch für Tool-Aufrufe"""
        project_id = self.extract_project_id(ctx)
        ctx.set("project_id", project_id)
        return await next_handler(ctx, tool_name, arguments)

mcp.add_middleware(TenantMiddleware())
```

---

## Dependency Injection in 3.x

### CurrentContext Pattern

```python
from fastmcp import Context
from fastmcp.dependencies import CurrentContext, Depends

async def get_db_connection():
    async with pool.acquire() as conn:
        yield conn

@mcp.tool()
async def hybrid_search(
    query: str,
    # Diese Parameter sind NICHT im LLM-Schema sichtbar
    ctx: Context = CurrentContext(),
    conn = Depends(get_db_connection)
) -> str:
    project_id = ctx.get("project_id")
    await ctx.info(f"Searching for project {project_id}")
    # ... use conn ...
```

### Schema-Filterung

DI-Parameter werden automatisch aus dem JSON-Schema entfernt:

```json
{
  "name": "hybrid_search",
  "inputSchema": {
    "properties": {
      "query": {"type": "string"}
    },
    "required": ["query"]
  }
}
// ctx und conn sind NICHT sichtbar für LLM
```

---

## Type Annotations und Schema-Generierung

| Python Type | MCP Schema | Anmerkung |
|-------------|------------|-----------|
| `int`, `float` | number | Coercion wenn nicht strict |
| `str` | string | |
| `bool` | boolean | |
| `list[T]` | array | Item-Typ T validiert |
| `dict` | object | Typed Models bevorzugt |
| `Optional[T]` | T oder null | |
| Pydantic Model | object (nested) | Rekursiv verarbeitet |
| `bytes` | string | Manuelles base64 Decode nötig |

---

## Hot Reloading und Development

```bash
# Development mit Auto-Reload
fastmcp dev  # oder
fastmcp run --reload

# Automatische Claude Desktop Installation
fastmcp install

# OpenTelemetry Tracing (built-in)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 fastmcp run
```

---

## Migration Checkliste für cognitive-memory

### Phase 1: Preparation
- [ ] `fastmcp>=3.0.0b1,<4` in requirements.txt
- [ ] Import-Statements ändern
- [ ] Version verifizieren

### Phase 2: Core Migration
- [ ] `__main__.py` auf FastMCP 3.x umstellen
- [ ] Alle `@mcp.tool()` Decorators prüfen
- [ ] `enabled` Parameter entfernen (nutze `mcp.enable()`)

### Phase 3: State Management
- [ ] `ctx.get_state()` → `await ctx.get_state()`
- [ ] `ctx.set_state()` → `await ctx.set_state()`

### Phase 4: Middleware
- [ ] TenantMiddleware implementieren
- [ ] Transforms für Namespacing (falls nötig)

### Phase 5: Testing
- [ ] Unit-Tests für Tool-Funktionen (direkt aufrufbar!)
- [ ] Integration-Tests für Middleware-Pipeline

---

## Roadmap

### FastMCP 4.0 (geplant Q1-Q2 2026)

- Integration von MCP SDK v2.0 Änderungen
- Weitere Transport-Layer-Optimierungen
- Breaking Changes bei Transport-Handling erwartet

### Version Pinning

```
# Stabil auf 3.x bleiben
fastmcp>=3.0.0,<4
```

---

## Referenzen

- FastMCP Docs: gofastmcp.com
- Upgrade Guide: gofastmcp.com/development/upgrade-guide
- Middleware Docs: gofastmcp.com/servers/middleware
- GitHub: github.com/jlowin/fastmcp
