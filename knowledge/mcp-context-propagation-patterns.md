# MCP Kontextpropagierung: Multi-Tenancy ohne HTTP-Header

> Research Summary: 2026-01-22
> Source: Deep Research F2 - Kontextpropagierung im MCP-Protokoll
> Status: VALIDATED

## Executive Summary

Bei stdio-Transport existieren drei Mechanismen zur Mandanten-Identifikation:
1. **Statisch:** `clientInfo` / `initialization_options` (einmalig bei Verbindungsaufbau)
2. **Dynamisch:** `params._meta` Property-Bag (pro Anfrage)
3. **Architektonisch:** Gateway-basierte Föderation oder Prozess-Isolation

---

## Mechanismus 1: Initialisierungsbasierte Kontextübertragung

### clientInfo im Initialize-Request
```json
{
  "jsonrpc": "2.0",
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {...},
    "clientInfo": {
      "name": "cognitive-memory-client",
      "version": "1.0.0",
      "tenant_id": "io"  // Erweiterung für Multi-Tenancy
    }
  }
}
```

### Eigenschaften
| Aspekt | Bewertung |
|--------|-----------|
| Dynamik | Statisch (Lebensdauer = Prozess) |
| Sicherheit | Hoch (Prozess-Isolation) |
| Skalierbarkeit | Gering (N Mandanten = N Prozesse) |

### Limitation
Erfordert separaten Serverprozess pro Mandant. Für SaaS mit tausenden Mandanten nicht praktikabel.

---

## Mechanismus 2: _meta Property-Bag (Empfohlen)

### Konzept
Das `_meta`-Feld in JSON-RPC-Anfragen dient als Erweiterungspunkt für Metadaten, die nicht zu den funktionalen Tool-Argumenten gehören.

### Beispiel: Tool-Aufruf mit Mandanten-Kontext
```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "hybrid_search",
    "arguments": {
      "query_text": "Beispielsuche"
    },
    "_meta": {
      "project_id": "aa",
      "user_id": "user_123",
      "traceparent": "00-abc123-def456-01"
    }
  }
}
```

### Server-seitige Extraktion (Python)
```python
@mcp.tool()
async def hybrid_search(query_text: str, ctx: Context) -> list:
    # _meta aus Request-Context extrahieren
    meta = ctx.request_context.get("_meta", {})
    project_id = meta.get("project_id")

    if not project_id:
        raise ValueError("Missing project_id in _meta")

    # RLS-Context setzen
    async with get_connection() as conn:
        await conn.execute(
            "SELECT set_config('app.current_project', $1, true)",
            project_id
        )
        # Query ausführen...
```

### Eigenschaften
| Aspekt | Bewertung |
|--------|-----------|
| Dynamik | Hoch (pro Anfrage) |
| Sicherheit | Mittel (Validierung erforderlich) |
| Skalierbarkeit | Hoch (1 Prozess für N Mandanten) |

### OpenTelemetry-Integration
Das `_meta`-Feld ist der standardisierte Ort für Tracing-Kontexte:
```json
"_meta": {
  "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
  "tracestate": "congo=t61rcWkgMzE"
}
```

---

## Mechanismus 3: Prozess-Isolation (Azure Functions Pattern)

### Architektur
```
┌─────────────────┐      HTTP       ┌─────────────────┐
│  Client A       │ ───────────────►│  Adapter        │
│  session_id: X  │                 │  Instance       │
└─────────────────┘                 │                 │
                                    │  ┌───────────┐  │
┌─────────────────┐      HTTP       │  │ MCP Proc  │  │ ← session_id: X
│  Client B       │ ───────────────►│  │ (stdio)   │  │
│  session_id: Y  │                 │  └───────────┘  │
└─────────────────┘                 │                 │
                                    │  ┌───────────┐  │
                                    │  │ MCP Proc  │  │ ← session_id: Y
                                    │  │ (stdio)   │  │
                                    │  └───────────┘  │
                                    └─────────────────┘
```

### Implementierung (azurefunctions-mcp-stdio-adapter)
```python
class ProcessManager:
    def get_or_create_process(self, session_id: str) -> MCPProcess:
        if session_id not in self.processes:
            self.processes[session_id] = self.spawn_mcp_server(
                env={"TENANT_ID": session_id}
            )
        return self.processes[session_id]

    def cleanup_inactive(self, timeout_minutes: int = 30):
        # Inaktive Prozesse beenden
        ...
```

### Eigenschaften
| Aspekt | Bewertung |
|--------|-----------|
| Isolation | Maximal (OS-Ebene) |
| Ressourcenbedarf | Hoch (RAM pro Prozess) |
| Use Case | Lokale Ressourcen (Dateisystem, DBs) |

---

## Mechanismus 4: Gateway-basierte Föderation

### Plattformen
- **SageMCP:** Multi-Tenant MCP Server Platform
- **Agentgateway:** Zentrales Management mit Redis-Session-Store

### URL-Pfad-basiertes Routing
```
ws://gateway.example.com/api/v1/{tenant_slug}/mcp
```

### Gateway-Funktionen
1. Zentrale Authentifizierung (OAuth, JWT)
2. Mandanten-Routing zu Backend-Servern
3. Tool-Scoping (Sichtbarkeit pro Mandant)
4. Credential-Management (verschlüsselt)

### Kontext-Übersetzung
Gateway extrahiert Mandanten-ID aus URL/Header und injiziert sie in `_meta`:
```python
# Gateway Middleware
async def inject_tenant_context(request, call_next):
    tenant_id = extract_tenant_from_path(request.url)
    request.mcp_meta["project_id"] = tenant_id
    return await call_next(request)
```

---

## Sicherheitsimplikationen

### Risiko: Confused Deputy Attack
Ein Angreifer könnte versuchen, eine fremde `project_id` in `_meta` zu injizieren.

### Mitigation
```python
async def validate_tenant_access(ctx: Context, project_id: str) -> bool:
    # 1. Prüfen ob project_id in registrierten Projekten
    if project_id not in REGISTERED_PROJECTS:
        raise AuthorizationError(f"Unknown project: {project_id}")

    # 2. Prüfen ob Client für dieses Projekt autorisiert
    client_info = ctx.client_info
    allowed = await check_acl(client_info, project_id)

    if not allowed:
        raise AuthorizationError(f"Access denied to project: {project_id}")

    return True
```

### Risiko: Secret Sprawl
API-Keys oder Tokens in `_meta` könnten in Logs exponiert werden.

### Mitigation
1. **Asymmetrische Verschlüsselung:** Sensible Daten mit Server-Public-Key verschlüsseln
2. **Elicitation-Pattern:** Token nur on-demand anfordern
3. **OAuth-Proxying:** Gateway injiziert Token erst bei Upstream-Call

---

## Spezifikationsvorschläge (GitHub Discussions)

### Discussion #193: clientConfig Extension
```json
{
  "params": {
    "arguments": {...},
    "clientConfig": {
      "github_token": "encrypted:...",
      "repository_url": "https://github.com/..."
    }
  }
}
```
- Server deklariert `clientConfig`-Schema in Capabilities
- Client muss Schema erfüllen für erfolgreiche Ausführung

### Discussion #234: Tool-Level Authorization
```json
{
  "tools": [{
    "name": "delete_file",
    "authRequirements": {
      "method": "oauth2",
      "scopes": ["files:write"]
    }
  }]
}
```
- Client injiziert Token in `_meta` bei Aufruf
- Server validiert Scopes vor Ausführung

---

## Empfehlung für cognitive-memory

### Primärstrategie: _meta + HTTP Hybrid

1. **HTTP-Transport:** X-Project-ID Header für Production
2. **stdio-Transport:** _meta.project_id als Fallback für lokale Entwicklung

### Implementierung
```python
def get_project_id(ctx: Context) -> str:
    # 1. Versuche HTTP-Header (bei HTTP-Transport)
    headers = getattr(ctx, 'http_headers', {})
    if project_id := headers.get('X-Project-ID'):
        return project_id

    # 2. Fallback auf _meta (bei stdio-Transport)
    meta = ctx.request_context.get("_meta", {})
    if project_id := meta.get("project_id"):
        return project_id

    # 3. Fehler wenn beides fehlt
    raise ValueError("Missing project context (X-Project-ID header or _meta.project_id)")
```

---

## Referenzen

- MCP Specification: Lifecycle (modelcontextprotocol.io)
- GitHub Discussion #193: Multi-Tenant Client Support
- GitHub Discussion #234: Multi-user Authorization
- OpenTelemetry: Semantic Conventions for MCP
- Azure Functions MCP Stdio Adapter (PyPI)
