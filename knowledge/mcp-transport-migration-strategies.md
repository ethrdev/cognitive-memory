# MCP Transport-Migration: stdio zu HTTP/SSE

> Research Summary: 2026-01-22
> Source: Deep Research F1 - Transport-Architektur und Client-Kompatibilität
> Status: VALIDATED

## Executive Summary

Das MCP Python SDK 1.25.0+ unterstützt drei Transportmechanismen. Für Multi-Tenant-Szenarien ist **Streamable HTTP** der empfohlene Standard, da nur dieser Header-basierte Kontextpropagierung ermöglicht.

---

## Transportmechanismen im Vergleich

| Transport | Anwendungsfall | Metadaten | Skalierbarkeit |
|-----------|----------------|-----------|----------------|
| **stdio** | Lokale IDEs, Claude Desktop | Nur Payload | 1:1 Prozess |
| **SSE** | Legacy Web-Integration | HTTP-Header | Deprecated |
| **Streamable HTTP** | Remote SaaS, Multi-Tenant | HTTP-Header | Horizontal |

### stdio Transport
- Kommunikation via stdin/stdout
- Inherent stateful (Prozess-Lebenszyklus = Session)
- **Limitation:** Keine Out-of-Band-Metadaten (keine Header)
- **Use Case:** Lokale Entwicklung, CLI-Tools

### Streamable HTTP Transport
- Hybrid: POST für Client→Server, SSE für Server→Client
- Session-Tracking via `MCP-Session-Id` Header
- Unterstützt OAuth 2.1 und Bearer Tokens
- **Kritisch:** Origin-Header-Validierung mandatory

---

## Claude Desktop Kompatibilität

### Lokale Konfiguration (stdio only)
```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "python",
      "args": ["-m", "mcp_server"]
    }
  }
}
```
**Limitation:** Direkte HTTP-URLs werden NICHT unterstützt.

### Remote Access via Custom Connectors
- Verfügbar für: Claude Pro, Team, Enterprise
- Konfiguration über Web-UI (nicht config.json)
- Unterstützt OAuth 2.1 Authentication Flow
- **Transport:** Streamable HTTP oder SSE (SSE deprecated)

### Bridge Pattern (Workaround für stdio-Clients)
```json
{
  "mcpServers": {
    "remote-bridge": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://remote-server.com/mcp"]
    }
  }
}
```
- **mcp-remote** (Node.js): `npx mcp-remote <URL>`
- **mcp-proxy** (Python): `pip install mcp-proxy`
- Ermöglicht stdio-Clients Zugriff auf HTTP-Server

---

## Code-Migration: stdio → HTTP

### Minimal-Änderung mit FastMCP
```python
# VORHER (stdio)
mcp.run()  # oder mcp.run(transport="stdio")

# NACHHER (HTTP)
mcp.run(transport="http", host="0.0.0.0", port=8000)
```

### Production Deployment (ASGI Mount)
```python
from fastmcp import FastMCP
import uvicorn

mcp = FastMCP("cognitive-memory")

# Tools registrieren...

if __name__ == "__main__":
    uvicorn.run(mcp.get_asgi_app(), host="0.0.0.0", port=8000)
```

---

## Parallelbetrieb: stdio + HTTP

Das SDK unterstützt NICHT nativ beide Transports in einem `run()`-Aufruf.

### Workaround 1: asyncio.gather()
```python
import asyncio

async def main():
    await asyncio.gather(
        mcp.run_async(transport="stdio"),
        mcp.run_async(transport="http", port=8000)
    )
```

### Workaround 2: mcp-proxy Tool
Existierenden stdio-Server als SSE-Endpoint exponieren:
```bash
mcp-proxy --stdio-command "python -m mcp_server" --port 8000
```

---

## SDK v2.0 Roadmap

**Geplant:** Q1 2026

### Erwartete Breaking Changes
- Fundamentale Änderungen am Transport-Layer
- Verbesserte bidirektionale Kommunikation
- Standardisierte Session-Persistenz
- Formalisierte Elicitation-Patterns

### Branching-Strategie (ab 1.25.0)
- **v1.x Branch:** Maintenance, Security Patches
- **main Branch:** v2.0 Development

### Empfehlung für cognitive-memory
```
# requirements.txt - Pin auf v1.x
mcp>=1.25,<2
```

---

## Entscheidungsmatrix für cognitive-memory

| Szenario | Empfohlener Transport |
|----------|----------------------|
| Lokales Development | stdio (default) |
| Single-User Remote | HTTP via ngrok/Tunnel |
| Multi-Tenant SaaS | Streamable HTTP + Redis |
| Hybrid (lokal + remote) | Bridge Pattern |

---

## Referenzen

- MCP Specification: Transports (modelcontextprotocol.io)
- FastMCP Documentation: Running Your Server
- GitHub: modelcontextprotocol/python-sdk/releases
- MCP-Remote: github.com/geelen/mcp-remote
