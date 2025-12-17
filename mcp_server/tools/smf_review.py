"""
smf_review Tool Implementation

MCP tool for reviewing detailed information about a specific SMF proposal.
Returns complete proposal details including affected edge information and
consequences of approval/rejection.

Story 7.9: SMF mit Safeguards + Neutral Framing - AC #8
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.analysis.smf import get_proposal
from mcp_server.db.graph import get_edge_by_id


async def handle_smf_review(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve complete details for a specific SMF proposal.

    Args:
        arguments: Tool arguments containing 'proposal_id' parameter

    Returns:
        Dict with full proposal details including:
        - All proposal fields
        - Betroffene Edge-Details
        - If-approved / If-rejected Konsequenzen
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        proposal_id = arguments.get("proposal_id")

        # Parameter validation
        if not proposal_id:
            return {
                "error": "Parameter validation failed",
                "details": "Missing 'proposal_id' parameter",
                "tool": "smf_review",
            }

        # Get proposal from database
        proposal = get_proposal(proposal_id)
        if not proposal:
            return {
                "error": "Proposal not found",
                "details": f"No proposal found with ID: {proposal_id}",
                "tool": "smf_review",
            }

        # Get details for affected edges
        affected_edges_details = []
        for edge_id in proposal.get("affected_edges", []):
            try:
                edge = get_edge_by_id(edge_id)
                if edge:
                    edge_details = {
                        "edge_id": edge["id"],
                        "relation": edge["relation"],
                        "source_name": edge.get("source_name", "Unknown"),
                        "target_name": edge.get("target_name", "Unknown"),
                        "properties": edge.get("properties", {}),
                        "created_at": edge.get("created_at"),
                        "edge_type": edge.get("properties", {}).get("edge_type", "descriptive")
                    }
                    affected_edges_details.append(edge_details)
            except Exception as edge_error:
                logger.warning(f"Failed to get details for edge {edge_id}: {edge_error}")
                # Continue with other edges even if one fails
                affected_edges_details.append({
                    "edge_id": edge_id,
                    "error": f"Failed to retrieve edge details: {str(edge_error)}"
                })

        # Parse proposed action to determine consequences
        proposed_action = proposal.get("proposed_action", {})
        if isinstance(proposed_action, str):
            import json
            try:
                proposed_action = json.loads(proposed_action)
            except json.JSONDecodeError:
                proposed_action = {"action": "unknown", "details": proposed_action}

        # Generate consequence descriptions based on resolution type
        resolution_type = proposed_action.get("resolution_type", "UNKNOWN")
        if_approved = ""
        if_rejected = ""

        if resolution_type == "EVOLUTION":
            if_approved = "Die ältere Position wird als superseded markiert, die neuere bleibt aktiv"
            if_rejected = "Beide Positionen bleiben aktiv, Dissonanz bleibt markiert"
        elif resolution_type == "CONTRADICTION":
            if_approved = "Ein Widerspruch wird dokumentiert, beide Edges bleiben erhalten"
            if_rejected = "Edges bleiben unverändert, Widerspruch bleibt unmarkiert"
        elif resolution_type == "NUANCE":
            if_approved = "Die Spannung wird als akzeptierte Nuance dokumentiert"
            if_rejected = "Edges bleiben unverändert, Spannung bleibt unmarkiert"
        else:
            if_approved = "Resolution wird basierend auf Vorschlag ausgeführt"
            if_rejected = "Keine Änderung, Status quo bleibt erhalten"

        # Format complete response
        response = {
            "proposal": {
                "proposal_id": proposal["id"],
                "trigger_type": proposal["trigger_type"],
                "proposed_action": proposed_action,
                "reasoning": proposal["reasoning"],
                "approval_level": proposal["approval_level"],
                "status": proposal["status"],
                "created_at": proposal["created_at"],
                "approved_by_io": proposal.get("approved_by_io", False),
                "approved_by_ethr": proposal.get("approved_by_ethr", False),
                "resolved_at": proposal.get("resolved_at"),
                "resolved_by": proposal.get("resolved_by"),
                "undo_deadline": proposal.get("undo_deadline")
            },
            "affected_edges": affected_edges_details,
            "consequences": {
                "if_approved": if_approved,
                "if_rejected": if_rejected
            },
            "status": "success"
        }

        logger.info(f"Retrieved details for SMF proposal {proposal_id}")
        return response

    except Exception as e:
        logger.error(f"Error reviewing SMF proposal {proposal_id}: {e}")
        return {
            "error": "Failed to review proposal",
            "details": str(e),
            "tool": "smf_review",
            "proposal_id": arguments.get("proposal_id"),
            "status": "error"
        }