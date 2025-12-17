"""
smf_undo Tool Implementation

MCP tool for undoing approved SMF proposals within 30-day retention window.
Reverses edge changes and marks resolution hyperedges as orphaned.

Story 7.9: SMF mit Safeguards + Neutral Framing - AC #11, #13
"""

from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timezone

from mcp_server.analysis.smf import undo_proposal, get_proposal


async def handle_smf_undo(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Undo an approved SMF proposal within the 30-day retention window.

    Args:
        arguments: Tool arguments containing:
            - proposal_id: ID of the proposal to undo
            - actor: Who is requesting the undo ("I/O" | "ethr")

    Returns:
        Dict with undo confirmation and proposal status.
        Returns error if proposal is older than 30 days.
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        proposal_id = arguments.get("proposal_id")
        actor = arguments.get("actor")

        # Parameter validation
        if not proposal_id:
            return {
                "error": "Parameter validation failed",
                "details": "Missing 'proposal_id' parameter",
                "tool": "smf_undo",
            }

        if not actor:
            return {
                "error": "Parameter validation failed",
                "details": "Missing 'actor' parameter (must be 'I/O' or 'ethr')",
                "tool": "smf_undo",
            }

        if actor not in ["I/O", "ethr"]:
            return {
                "error": "Parameter validation failed",
                "details": f"Invalid actor '{actor}'. Must be 'I/O' or 'ethr'",
                "tool": "smf_undo",
            }

        # Check if proposal exists and is approved
        proposal = get_proposal(proposal_id)
        if not proposal:
            return {
                "error": "Proposal not found",
                "details": f"No proposal found with ID: {proposal_id}",
                "tool": "smf_undo",
            }

        if proposal["status"] != "APPROVED":
            return {
                "error": "Invalid proposal status",
                "details": f"Proposal {proposal_id} is not APPROVED (current status: {proposal['status']})",
                "tool": "smf_undo",
            }

        # Check 30-day retention window
        undo_deadline = proposal.get("undo_deadline")
        if undo_deadline:
            try:
                deadline_date = datetime.fromisoformat(undo_deadline.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) > deadline_date:
                    return {
                        "error": "RETENTION_EXPIRED",
                        "details": f"30-day undo window has expired for proposal {proposal_id}",
                        "undo_deadline": undo_deadline,
                        "tool": "smf_undo",
                    }
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid undo_deadline format for proposal {proposal_id}: {e}")

        # Check bilateral consent for constitutive edge modifications
        proposed_action = proposal.get("proposed_action", {})
        if isinstance(proposed_action, str):
            import json
            try:
                proposed_action = json.loads(proposed_action)
            except json.JSONDecodeError:
                proposed_action = {}

        # For constitutive edge modifications, we need bilateral consent for undo too
        # This is a safeguard - let the undo_proposal function handle this check
        # as it has access to more detailed edge information

        # Execute undo
        result = undo_proposal(
            proposal_id=proposal_id,
            actor=actor
        )

        logger.info(f"SMF proposal {proposal_id} undone by {actor}")

        return {
            "proposal_id": proposal_id,
            "undone_by": actor,
            "undone_at": result["undone_at"],
            "proposal_status": result["status"],
            "undo_deadline": undo_deadline,
            "message": f"Proposal {proposal_id} has been successfully undone",
            "note": "All edge changes have been reverted and resolution hyperedges marked as orphaned",
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error undoing SMF proposal {proposal_id}: {e}")

        # Check if it's a specific retention expired error
        if "RETENTION_EXPIRED" in str(e):
            return {
                "error": "RETENTION_EXPIRED",
                "details": "30-day undo window has expired for this proposal",
                "tool": "smf_undo",
                "proposal_id": arguments.get("proposal_id"),
                "status": "error"
            }

        return {
            "error": "Failed to undo proposal",
            "details": str(e),
            "tool": "smf_undo",
            "proposal_id": arguments.get("proposal_id"),
            "actor": arguments.get("actor"),
            "status": "error"
        }