"""
smf_reject Tool Implementation

MCP tool for rejecting SMF proposals with reason logging.
Updates proposal status and creates audit log entries.

Story 7.9: SMF mit Safeguards + Neutral Framing - AC #10, #13
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.analysis.smf import reject_proposal, get_proposal


async def handle_smf_reject(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Reject an SMF proposal with reason logging.

    Args:
        arguments: Tool arguments containing:
            - proposal_id: ID of the proposal to reject
            - reason: Reason for rejection
            - actor: Who is rejecting ("I/O" | "ethr" | "system")

    Returns:
        Dict with rejection confirmation and proposal status.
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        proposal_id = arguments.get("proposal_id")
        reason = arguments.get("reason", "")
        actor = arguments.get("actor", "system")

        # Parameter validation
        if not proposal_id:
            return {
                "error": "Parameter validation failed",
                "details": "Missing 'proposal_id' parameter",
                "tool": "smf_reject",
            }

        if not reason or not isinstance(reason, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'reason' parameter (must be non-empty string)",
                "tool": "smf_reject",
            }

        if actor not in ["I/O", "ethr", "system"]:
            return {
                "error": "Parameter validation failed",
                "details": f"Invalid actor '{actor}'. Must be 'I/O', 'ethr', or 'system'",
                "tool": "smf_reject",
            }

        # Check if proposal exists and is pending
        proposal = get_proposal(proposal_id)
        if not proposal:
            return {
                "error": "Proposal not found",
                "details": f"No proposal found with ID: {proposal_id}",
                "tool": "smf_reject",
            }

        if proposal["status"] != "PENDING":
            return {
                "error": "Invalid proposal status",
                "details": f"Proposal {proposal_id} is not PENDING (current status: {proposal['status']})",
                "tool": "smf_reject",
            }

        # Execute rejection
        result = reject_proposal(
            proposal_id=proposal_id,
            reason=reason,
            actor=actor
        )

        logger.info(f"SMF proposal {proposal_id} rejected by {actor}: {reason}")

        return {
            "proposal_id": proposal_id,
            "rejected_by": actor,
            "reason": reason,
            "rejected_at": result["resolved_at"],
            "proposal_status": result["status"],
            "message": f"Proposal {proposal_id} has been rejected by {actor}",
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error rejecting SMF proposal {proposal_id}: {e}")
        return {
            "error": "Failed to reject proposal",
            "details": str(e),
            "tool": "smf_reject",
            "proposal_id": arguments.get("proposal_id"),
            "actor": arguments.get("actor"),
            "status": "error"
        }