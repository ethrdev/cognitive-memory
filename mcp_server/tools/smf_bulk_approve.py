"""
smf_bulk_approve Tool Implementation

MCP tool for bulk-approving SMF proposals by type filter.
Useful for batch-processing trivial NUANCE cases.

Created: 2026-01-03 by BMAD Team
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from mcp_server.analysis.smf import (
    get_pending_proposals,
    approve_proposal,
    get_proposal,
)


async def handle_smf_bulk_approve(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Bulk-approve SMF proposals with optional filtering.

    Args:
        arguments: Tool arguments containing:
            - actor: Who is approving ("I/O" | "ethr")
            - trigger_type: Optional filter by trigger type ("NUANCE" | "EVOLUTION" | "CONTRADICTION")
            - approval_level: Optional filter by approval level ("io" | "bilateral")
            - proposal_ids: Optional list of specific proposal IDs to approve
            - dry_run: If true, only report what would be approved without executing

    Returns:
        Dict with bulk approval results including success/failure counts.
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        actor = arguments.get("actor")
        trigger_type_filter = arguments.get("trigger_type")
        approval_level_filter = arguments.get("approval_level")
        proposal_ids = arguments.get("proposal_ids", [])
        dry_run = arguments.get("dry_run", False)

        # Parameter validation
        if not actor:
            return {
                "error": "Parameter validation failed",
                "details": "Missing 'actor' parameter (must be 'I/O' or 'ethr')",
                "tool": "smf_bulk_approve",
            }

        if actor not in ["I/O", "ethr"]:
            return {
                "error": "Parameter validation failed",
                "details": f"Invalid actor '{actor}'. Must be 'I/O' or 'ethr'",
                "tool": "smf_bulk_approve",
            }

        # Get all pending proposals
        all_proposals = get_pending_proposals()

        # Normalize filter for case-insensitive comparison
        # Note: resolution_type is in proposed_action, not trigger_type
        resolution_type_filter_upper = trigger_type_filter.upper() if trigger_type_filter else None

        # Helper to extract resolution_type from proposal
        def get_resolution_type(proposal: dict) -> str:
            """Extract resolution_type from proposed_action (handles dict or string)."""
            proposed_action = proposal.get("proposed_action", {})
            if isinstance(proposed_action, str):
                try:
                    import json
                    proposed_action = json.loads(proposed_action)
                except (json.JSONDecodeError, TypeError):
                    return ""
            return (proposed_action.get("resolution_type") or "").upper()

        # Apply filters
        filtered_proposals = []
        for p in all_proposals:
            # Filter by specific IDs if provided
            if proposal_ids and p["id"] not in proposal_ids:
                continue

            # Filter by resolution type (case-insensitive) - stored in proposed_action
            if resolution_type_filter_upper:
                proposal_resolution = get_resolution_type(p)
                if proposal_resolution != resolution_type_filter_upper:
                    continue

            # Filter by approval level
            if approval_level_filter and p.get("approval_level") != approval_level_filter:
                continue

            # Skip already approved by this actor
            if actor == "I/O" and p.get("approved_by_io", False):
                continue
            if actor == "ethr" and p.get("approved_by_ethr", False):
                continue

            filtered_proposals.append(p)

        # Dry run - just report
        if dry_run:
            # Case-insensitive breakdown counts using resolution_type
            def count_by_type(proposals: list, type_name: str) -> int:
                return len([p for p in proposals if get_resolution_type(p) == type_name.upper()])

            return {
                "dry_run": True,
                "proposals_to_approve": len(filtered_proposals),
                "proposal_ids": [p["id"] for p in filtered_proposals],
                "breakdown": {
                    "NUANCE": count_by_type(filtered_proposals, "NUANCE"),
                    "EVOLUTION": count_by_type(filtered_proposals, "EVOLUTION"),
                    "CONTRADICTION": count_by_type(filtered_proposals, "CONTRADICTION"),
                },
                "approval_levels": {
                    "io": len([p for p in filtered_proposals if p.get("approval_level") == "io"]),
                    "bilateral": len([p for p in filtered_proposals if p.get("approval_level") == "bilateral"]),
                },
                "message": f"Would approve {len(filtered_proposals)} proposals as {actor}",
                "tool": "smf_bulk_approve",
                "status": "dry_run",
            }

        # Execute bulk approval
        results = {
            "succeeded": [],
            "failed": [],
            "skipped_bilateral": [],
        }

        for p in filtered_proposals:
            proposal_id = p["id"]

            try:
                # For bilateral proposals, only record approval - don't execute yet
                result = await approve_proposal(
                    proposal_id=proposal_id,
                    actor=actor,
                    haiku_client=None  # No Haiku needed for approval tracking
                )

                if result.get("fully_approved"):
                    results["succeeded"].append({
                        "proposal_id": proposal_id,
                        "trigger_type": p.get("trigger_type"),
                        "executed": True,
                    })
                else:
                    # Bilateral - awaiting other approval
                    results["skipped_bilateral"].append({
                        "proposal_id": proposal_id,
                        "trigger_type": p.get("trigger_type"),
                        "reason": "Awaiting bilateral approval",
                    })

            except Exception as e:
                logger.warning(f"Failed to approve proposal {proposal_id}: {e}")
                results["failed"].append({
                    "proposal_id": proposal_id,
                    "trigger_type": p.get("trigger_type"),
                    "error": str(e),
                })

        total = len(filtered_proposals)
        succeeded = len(results["succeeded"])
        failed = len(results["failed"])
        bilateral = len(results["skipped_bilateral"])

        logger.info(
            f"Bulk approval completed: {succeeded} succeeded, {failed} failed, "
            f"{bilateral} awaiting bilateral approval"
        )

        return {
            "actor": actor,
            "total_processed": total,
            "succeeded": succeeded,
            "failed": failed,
            "awaiting_bilateral": bilateral,
            "details": results,
            "message": (
                f"Bulk approved {succeeded}/{total} proposals as {actor}. "
                f"{failed} failed, {bilateral} awaiting bilateral consent."
            ),
            "tool": "smf_bulk_approve",
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Bulk approval failed: {e}")
        return {
            "error": "Bulk approval failed",
            "details": str(e),
            "tool": "smf_bulk_approve",
            "status": "error",
        }
