"""
smf_pending_proposals Tool Implementation

MCP tool for retrieving all pending SMF proposals that need approval.
Returns proposals with full details for review and decision-making.

Story 7.9: SMF mit Safeguards + Neutral Framing - AC #7
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.analysis.smf import get_pending_proposals


async def handle_smf_pending_proposals(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve all pending SMF proposals that need approval.

    Args:
        arguments: Tool arguments (no parameters required)

    Returns:
        Dict with list of pending proposals and their details.
        Each proposal includes: proposal_id, trigger_type, proposed_action,
        reasoning, approval_level, created_at, affected_edges
    """
    logger = logging.getLogger(__name__)

    try:
        # Get all pending proposals from database
        proposals = get_pending_proposals()

        # Format response for MCP consumption
        formatted_proposals = []
        for proposal in proposals:
            formatted_proposal = {
                "proposal_id": proposal["id"],
                "trigger_type": proposal["trigger_type"],
                "proposed_action": proposal["proposed_action"],
                "affected_edges": proposal["affected_edges"],
                "reasoning": proposal["reasoning"],
                "approval_level": proposal["approval_level"],
                "created_at": proposal["created_at"],
            }
            formatted_proposals.append(formatted_proposal)

        logger.info(f"Retrieved {len(formatted_proposals)} pending SMF proposals")

        return {
            "proposals": formatted_proposals,
            "count": len(formatted_proposals),
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error retrieving SMF pending proposals: {e}")
        return {
            "error": "Failed to retrieve pending proposals",
            "details": str(e),
            "tool": "smf_pending_proposals",
            "status": "error"
        }