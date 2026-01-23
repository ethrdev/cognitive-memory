"""
smf_reject Tool Implementation

MCP tool for rejecting SMF proposals with reason logging.
Updates proposal status and creates audit log entries.

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 7.9: SMF mit Safeguards + Neutral Framing - AC #10, #13
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.analysis.smf import reject_proposal, get_proposal
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


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
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        proposal_id = arguments.get("proposal_id")
        reason = arguments.get("reason", "")
        actor = arguments.get("actor", "system")

        # Parameter validation
        if not proposal_id:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing 'proposal_id' parameter",
                "tool": "smf_reject",
            }, project_id)

        if not reason or not isinstance(reason, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'reason' parameter (must be non-empty string)",
                "tool": "smf_reject",
            }, project_id)

        if actor not in ["I/O", "ethr", "system"]:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": f"Invalid actor '{actor}'. Must be 'I/O', 'ethr', or 'system'",
                "tool": "smf_reject",
            }, project_id)

        # Check if proposal exists and is pending
        proposal = get_proposal(proposal_id)
        if not proposal:
            return add_response_metadata({
                "error": "Proposal not found",
                "details": f"No proposal found with ID: {proposal_id}",
                "tool": "smf_reject",
            }, project_id)

        if proposal["status"] != "PENDING":
            return add_response_metadata({
                "error": "Invalid proposal status",
                "details": f"Proposal {proposal_id} is not PENDING (current status: {proposal['status']})",
                "tool": "smf_reject",
            }, project_id)

        # Execute rejection
        result = reject_proposal(
            proposal_id=proposal_id,
            reason=reason,
            actor=actor
        )

        logger.info(f"SMF proposal {proposal_id} rejected by {actor}: {reason}")

        return add_response_metadata({
            "proposal_id": proposal_id,
            "rejected_by": actor,
            "reason": reason,
            "rejected_at": result["resolved_at"],
            "proposal_status": result["status"],
            "message": f"Proposal {proposal_id} has been rejected by {actor}",
            "status": "success"
        }, project_id)

    except Exception as e:
        logger.error(f"Error rejecting SMF proposal {proposal_id}: {e}")
        return add_response_metadata({
            "error": "Failed to reject proposal",
            "details": str(e),
            "tool": "smf_reject",
            "proposal_id": arguments.get("proposal_id"),
            "actor": arguments.get("actor"),
            "status": "error"
        }, get_current_project())  # Still get project_id even in catch block
