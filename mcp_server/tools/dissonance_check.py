"""
MCP Tool for checking dissonances in knowledge graph edges.

This tool provides the dissonance_check function as an MCP tool
that can be called from Claude Code or other MCP clients.
"""

import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp_server.analysis.dissonance import DissonanceEngine

logger = logging.getLogger(__name__)

# Tool definition for dissonance check
DISSONANCE_CHECK_TOOL = Tool(
    name="dissonance_check",
    description="Prüft Edges eines Nodes auf potenzielle Konflikte und klassifiziert sie als EVOLUTION, CONTRADICTION oder NUANCE.",
    inputSchema={
        "type": "object",
        "properties": {
            "context_node": {
                "type": "string",
                "description": "Name des Nodes dessen Edges geprüft werden (z.B. 'I/O')"
            },
            "scope": {
                "type": "string",
                "enum": ["recent", "full"],
                "default": "recent",
                "description": "'recent' = letzte 30 Tage, 'full' = alle Edges"
            }
        },
        "required": ["context_node"]
    }
)


async def handle_dissonance_check(
    server: Server,
    context_node: str,
    scope: str = "recent"
) -> list[TextContent]:
    """
    Handle dissonance check tool invocation.

    Args:
        server: MCP server instance
        context_node: Name of the node whose edges to check
        scope: "recent" (last 30 days) or "full" (all edges)

    Returns:
        List of TextContent with the dissonance check results
    """
    try:
        # Initialize dissonance engine
        engine = DissonanceEngine()

        # Perform dissonance check
        result = await engine.dissonance_check(
            context_node=context_node,
            scope=scope
        )

        # Format results for display
        if result.fallback:
            # API was unavailable
            response_text = f"""⚠️ **Dissonanz-Check übersprungen**

Haiku API ist nach 4 Versuchen nicht erreichbar. Dissonanz-Prüfung wurde übersprungen.

**Status:** {result.status}
**Grund:** API nicht verfügbar

Bitte versuchen Sie es später erneut oder überprüfen Sie die API-Konfiguration."""
        elif result.status == "insufficient_data":
            # Not enough edges for analysis
            response_text = f"""ℹ️ **Dissonanz-Check - Unzureichende Daten**

Nicht genügend Edges für eine Dissonanz-Analyse gefunden.

**Analysierte Edges:** {result.edges_analyzed}
**Benötigt:** Mindestens 2 Edges
**Status:** {result.status}

Bitte fügen Sie mehr Edges zum Knoten '{context_node}' hinzu, um eine Analyse durchzuführen."""
        else:
            # Successful analysis
            # Format dissonances found
            dissonance_text = ""
            if result.dissonances:
                dissonance_lines = []
                for diss in result.dissonances:
                    emoji = {
                        "EVOLUTION": "🔄",
                        "CONTRADICTION": "⚠️",
                        "NUANCE": "🤔"
                    }.get(diss.dissonance_type.value, "❓")

                    strength_info = ""
                    if diss.edge_a_memory_strength is not None and diss.edge_b_memory_strength is not None:
                        auth_source = "👑" if diss.authoritative_source else ""
                        strength_info = f"""
  - **Memory Strength:** A={diss.edge_a_memory_strength:.2f}, B={diss.edge_b_memory_strength:.2f} {auth_source}"""

                    dissonance_lines.append(f"""
{emoji} **{diss.dissonance_type.value.upper()}** (Confidence: {diss.confidence_score:.2f})
  - **Edge A:** {diss.edge_a_id[:8]}...
  - **Edge B:** {diss.edge_b_id[:8]}...
  - **Beschreibung:** {diss.description}{strength_info}
  - **Review erforderlich:** {'Ja' if diss.requires_review else 'Nein'}""")

                dissonance_text = "\n".join(dissonance_lines)
            else:
                dissonance_text = "Keine Dissonanzen gefunden."

            # Format pending reviews
            reviews_text = ""
            if result.pending_reviews:
                reviews_text = f"""
**Ausstehende NUANCE Reviews:** {len(result.pending_reviews)}
  - Nuance-Klassifikationen erfordern Ihre Bestätigung
  - Verwenden Sie den Review-Workflow zur Entscheidung zwischen NUANCE und CONTRADICTION"""
            else:
                reviews_text = "Keine ausstehenden Reviews."

            # Cost information (placeholder)
            cost_text = f"""
**API-Nutzung:**
  - API-Aufrufe: {result.api_calls}
  - Geschätzte Kosten: €{result.estimated_cost_eur:.4f}"""

            response_text = f"""✅ **Dissonanz-Check abgeschlossen**

**Kontext-Node:** {context_node}
**Scope:** {result.scope}
**Analysierte Edges:** {result.edges_analyzed}
**Gefundene Konflikte:** {result.conflicts_found}

{dissonance_text}

{reviews_text}

{cost_text}"""

        return [TextContent(type="text", text=response_text)]

    except ValueError as e:
        # Validation error
        error_msg = f"❌ **Validierungsfehler:** {str(e)}"
        return [TextContent(type="text", text=error_msg)]

    except Exception as e:
        logger.error(f"Dissonance check failed: {e}", exc_info=True)
        error_msg = f"""❌ **Fehler beim Dissonanz-Check**

Ein unerwarteter Fehler ist aufgetreten:
{str(e)}

Bitte überprüfen Sie die Logs für weitere Details."""
        return [TextContent(type="text", text=error_msg)]