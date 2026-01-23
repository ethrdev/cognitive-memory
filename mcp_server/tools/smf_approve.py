"""
smf_approve Tool Implementation

MCP tool for approving SMF proposals with bilateral consent support.
Handles approval level validation and executes resolutions upon full approval.

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 7.9: SMF mit Safeguards + Neutral Framing - AC #3, #9, #13
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.analysis.smf import approve_proposal, get_proposal
from mcp_server.external.anthropic_client import HaikuClient
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_smf_approve(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Approve an SMF proposal with proper consent handling.

    Args:
        arguments: Tool arguments containing:
            - proposal_id: ID of the proposal to approve
            - actor: Who is approving ("I/O" | "ethr")

    Returns:
        Dict with approval status and execution results:
        - Approval tracking (approved_by_io, approved_by_ethr)
        - Whether fully approved and executed
        - Proposal status after approval
    """
    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        proposal_id = arguments.get("proposal_id")
        actor = arguments.get("actor")

        # Parameter validation
        if not proposal_id:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing 'proposal_id' parameter",
                "tool": "smf_approve",
            }, project_id)

        if not actor:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing 'actor' parameter (must be 'I/O' or 'ethr')",
                "tool": "smf_approve",
            }, project_id)

        if actor not in ["I/O", "ethr"]:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": f"Invalid actor '{actor}'. Must be 'I/O' or 'ethr'",
                "tool": "smf_approve",
            }, project_id)

        # Check if proposal exists and is pending
        proposal = get_proposal(proposal_id)
        if not proposal:
            return add_response_metadata({
                "error": "Proposal not found",
                "details": f"No proposal found with ID: {proposal_id}",
                "tool": "smf_approve",
            }, project_id)

        if proposal["status"] != "PENDING":
            return add_response_metadata({
                "error": "Invalid proposal status",
                "details": f"Proposal {proposal_id} is not PENDING (current status: {proposal['status']})",
                "tool": "smf_approve",
            }, project_id)

        # Check for duplicate approval
        if actor == "I/O" and proposal.get("approved_by_io", False):
            return add_response_metadata({
                "error": "Already approved",
                "details": f"Proposal {proposal_id} already approved by I/O",
                "tool": "smf_approve",
            }, project_id)

        if actor == "ethr" and proposal.get("approved_by_ethr", False):
            return add_response_metadata({
                "error": "Already approved",
                "details": f"Proposal {proposal_id} already approved by ethr",
                "tool": "smf_approve",
            }, project_id)

        # Check bilateral consent requirements
        approval_level = proposal.get("approval_level", "io")
        if approval_level == "bilateral":
            # For bilateral approval, verify we're not getting duplicate approval from same actor
            current_approvals = []
            if proposal.get("approved_by_io", False):
                current_approvals.append("I/O")
            if proposal.get("approved_by_ethr", False):
                current_approvals.append("ethr")

            if actor in current_approvals:
                return add_response_metadata({
                    "error": "Duplicate approval",
                    "details": f"Proposal {proposal_id} already approved by {actor}",
                    "tool": "smf_approve",
                }, project_id)

        # Initialize Haiku client for potential use in resolution execution
        haiku_client = None
        try:
            haiku_client = HaikuClient()
        except Exception as e:
            logger.warning(f"Failed to initialize Haiku client: {e}")

        # Execute approval
        result = await approve_proposal(
            proposal_id=proposal_id,
            actor=actor,
            haiku_client=haiku_client
        )

        logger.info(f"SMF proposal {proposal_id} approved by {actor}, fully_approved: {result['fully_approved']}")

        return add_response_metadata({
            "proposal_id": proposal_id,
            "approved_by": actor,
            "approved_by_io": result["approved_by_io"],
            "approved_by_ethr": result["approved_by_ethr"],
            "fully_approved": result["fully_approved"],
            "proposal_status": result["status"],
            "approval_level": approval_level,
            "message": (
                f"Proposal {proposal_id} approved by {actor}. "
                f"Status: {result['status']}. "
                f"{'Resolution executed.' if result['fully_approved'] else 'Awaiting further approval.'}"
            ),
            "status": "success"
        }, project_id)

    except Exception as e:
        logger.error(f"Error approving SMF proposal {proposal_id}: {e}")
        return add_response_metadata({
            "error": "Failed to approve proposal",
            "details": str(e),
            "tool": "smf_approve",
            "proposal_id": arguments.get("proposal_id"),
            "actor": arguments.get("actor"),
            "status": "error"
        }, get_current_project())  # Still get project_id even in catch block
