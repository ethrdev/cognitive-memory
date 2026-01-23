# MCP Server Multi-Tenant Architecture Patterns

> Research Summary from Deep Research (2026-01-22)
> Source: Kategorie 2 - Architekturmuster für Multi-Mandantenfähigkeit in MCP und KI-Gedächtnissystemen

## Executive Summary

MCP-Server können Multi-Tenancy über drei Hauptmechanismen implementieren:
1. **Pfad-basierte Virtualisierung** (URL enthält Tenant)
2. **Header-basierte Kontextinjektion** (X-Tenant-ID Header)
3. **Gateway-vermittelte Architektur** (zentraler Proxy)

Für cognitive-memory ist **Header-basierte Kontextinjektion mit Middleware** der empfohlene Ansatz.

---

## MCP Multi-Tenant Patterns

### Pattern 1: Pfad-basierte Isolation (Virtual Server)

```
ws://domain.com/api/v1/{tenant_slug}/mcp
```

**Mechanismus:**
- Jede Tenant-Verbindung = einzigartige URL
- Tenant-Kontext auf Verbindungsebene erzwungen
- Gesamter WebSocket/SSE-Lebenszyklus an Tenant gebunden

**Vorteile:**
- Einfache Client-Konfiguration
- Impliziter Kontext
- Load Balancer können Traffic segmentieren

**Nachteile:**
- Erfordert dynamische Routing-Infrastruktur
- Hoher Verbindungs-Overhead ohne Multiplexing

### Pattern 2: Header-basierte Kontextinjektion (Empfohlen)

```http
X-Tenant-ID: project_123
X-User-ID: user_456
Authorization: Bearer <JWT>
```

**Mechanismus:**
- Middleware extrahiert Header vor Tool-Ausführung
- Dependency Injection füllt Context-Objekt
- LLM sieht keine Tenant-IDs in Tool-Signaturen

**Sicherheitsvorteil:**
```python
# LLM sieht:
@mcp.tool()
async def list_files() -> str:
    ...

# Tatsächliche Signatur:
@mcp.tool()
async def list_files(ctx: Context) -> str:
    tenant_id = ctx.request_context.get("tenant_id")
    # Datenbankabfrage gefiltert nach tenant_id
```

**Kritisch:** Tenant-ID wird vom Server-Environment bereitgestellt, nicht vom LLM. Verhindert Prompt-Injection-Angriffe.

### Pattern 3: Gateway-vermittelte Architektur

```
Client → Gateway (Auth/Routing) → MCP Server(s)
```

**Aufgaben des Gateways:**
- OAuth-Token-Validierung
- Autorisierungsprüfung (User A darf Tool B nutzen?)
- Traffic-Routing (ggf. ephemeral Container pro Tenant)
- Token Audience Binding (verhindert Token Passthrough)

**Für:** Enterprise-Deployments mit komplexen Auth-Flows

---

## Lessons Learned von AI Memory Systemen

### Mem0: Hierarchische Kontext-Isolation

```python
from mem0 import Memory

# Initialisierung mit expliziten Primitiven
client = Memory(org_id="org_123", project_id="proj_456")

# Alle Operationen strikt auf dieses Tupel beschränkt
client.add("User prefers Python", user_id="user_789")
```

**Key Insight:**
- `org_id` + `project_id` als zwingende Metadatenfilter
- RBAC (OWNER/READER) direkt in API integriert
- Mandantenfähigkeit = Datenisolation + Governance

### Zep: Graph-basierte Isolation

**User-Graphen vs. Standalone-Graphen:**
- Jeder Benutzer hat isolierten Wissensgraph
- `thread.get_user_context()` → nur eigener Graph
- Shared State nur über explizite "Standalone Graphs"

**Filter-First Retrieval:**
```sql
-- Suchraum wird VOR Vektorsuche auf Tenant beschränkt
WHERE owner_id = $tenant_id
-- Dann erst Vektor-Ähnlichkeitssuche
ORDER BY embedding <=> $query_embedding
```

**Kritisch für cognitive-memory:** Niemals globale Indexsuche, dann Filtern!

### LangChain: Session-basierte Persistenz

**Key Namespacing Pattern:**
```
message_store:{tenant_id}:{session_id}
```

**Thread Safety:**
- Neue Chain/Agent pro Request instanziieren
- NICHT eine Agent-Instanz über Requests teilen
- RunnableWithMessageHistory-Factory für Benutzer-spezifisches Gedächtnis

### LlamaIndex: Metadatenfilterung + Sharding

**Soft Isolation (Metadatenfilter):**
```python
query_engine = index.as_query_engine(
    filters=MetadataFilter(key="tenant_id", value="123")
)
```

**Hard Isolation (Sharding):**
- Qdrant: Daten nach tenant_id zu Shards routen
- Nile Database: Tenant-Awareness in Postgres-Schicht

---

## Empfohlene Architektur für cognitive-memory

### "Middleware-Injected" Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Client                              │
│  (Claude Desktop, Agent Framework)                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP + SSE
                              │ Header: X-Project-ID: abc
                              │ Header: Authorization: Bearer <JWT>
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Gateway / Reverse Proxy                   │
│  - SSL Termination                                           │
│  - JWT Validation                                            │
│  - X-Project-ID Extraction                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ Validated Headers
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    cognitive-memory MCP Server               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Middleware: Extract X-Project-ID → Context             │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                               │
│                              ▼                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Tool: hybrid_search(ctx: Context, query: str)          │ │
│  │       project_id = ctx.project_id                      │ │
│  │       → DB Query mit WHERE project_id = $1             │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                               │
│                              ▼                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ PostgreSQL mit RLS                                     │ │
│  │ SET app.current_project = $project_id                  │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Implementierungsregeln

1. **Transport:** HTTP + SSE (nicht stdio für Multi-Tenant)
2. **Kontext-Propagierung:** Header → Middleware → Context-Objekt
3. **Tool-Signaturen:** NIEMALS `project_id` im JSON-Schema exponieren
4. **Datenbankzugriff:** Immer `SET LOCAL app.current_project` + RLS

### Code-Beispiel (FastMCP-Style)

```python
from mcp.server import Server
from mcp.server.middleware import Middleware

class TenantContextMiddleware(Middleware):
    async def process_request(self, request, next):
        # Header extrahieren
        project_id = request.headers.get("X-Project-ID")
        if not project_id:
            raise AuthenticationError("Missing X-Project-ID header")

        # Validieren (gegen registered projects)
        if not await self.validate_project(project_id):
            raise AuthorizationError(f"Unknown project: {project_id}")

        # In Context injizieren
        request.context["project_id"] = project_id

        return await next(request)

@server.tool()
async def hybrid_search(ctx: Context, query_text: str) -> list:
    project_id = ctx["project_id"]  # Aus Middleware

    async with get_connection() as conn:
        # RLS-Context setzen
        await conn.execute(
            "SELECT set_config('app.current_project', $1, true)",
            project_id
        )
        # Query ohne expliziten Filter - RLS übernimmt
        return await conn.fetch(
            "SELECT * FROM l2_insights ORDER BY embedding <=> $1 LIMIT 10",
            query_embedding
        )
```

---

## Vergleichstabelle: Kontext-Übergabe

| Methode | Sicherheit | Komplexität | Empfehlung |
|---------|------------|-------------|------------|
| Expliziter Parameter | Niedrig (LLM-Manipulation) | Niedrig | VERMEIDEN |
| Header-Injektion | Hoch | Mittel | EMPFOHLEN |
| URL-Pfad | Hoch | Mittel | Alternative |
| Gateway + Token | Sehr Hoch | Hoch | Enterprise |

---

## Referenzen

- Anthropic MCP Specification
- PydanticAI Client Documentation
- FastMCP Context Documentation
- Mem0 Organizations & Projects
- Zep FAQ: Graph Isolation
- LangChain Memory Overview
