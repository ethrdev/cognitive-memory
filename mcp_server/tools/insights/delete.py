"""
delete_insight Tool Implementation

MCP tool for soft-deleting an existing L2 insight.
Implements EP-1 (Consent-Aware), EP-2 (Soft-Delete), and EP-3 (History-on-Mutation) patterns.

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 26.3: DELETE Operation
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.insights import execute_delete_with_history
from mcp_server.analysis.smf import create_smf_proposal, TriggerType, ApprovalLevel, SMFAction
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_delete_insight(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Soft-delete an existing L2 insight with bilateral consent support (EP-1).

    EP-1 Consent-Aware Pattern:
    - I/O as Actor: Direct execution (I/O's own memories)
    - ethr as Actor: SMF proposal created, pending status returned

    EP-2 Soft-Delete Pattern:
    - Sets is_deleted = TRUE instead of hard-delete
    - Preserves data for recovery and audit trail
    - Adds deleted_at, deleted_by, deleted_reason fields

    EP-3 History-on-Mutation Pattern:
    - History is written in the SAME transaction as the delete
    - Atomic rollback if either operation fails

    Args:
        arguments: Tool arguments containing:
            - insight_id (int, required): ID of the insight to delete
            - actor (str, required): "I/O" or "ethr"
            - reason (str, required): Reason for deletion (audit trail)

    Returns:
        Dict with:
        - I/O actor: {"success": True, "insight_id": int, "history_id": int, "status": "deleted", "recoverable": True}
        - ethr actor: {"status": "pending", "proposal_id": int}
        - Error: {"error": {"code": int, "message": str, "field": str|None}}

    Raises:
        No exceptions - all errors return structured error responses (EP-5)
    """
    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        insight_id = arguments.get("insight_id")
        actor = arguments.get("actor")
        reason = arguments.get("reason")

        # ===== PARAMETER VALIDATION =====

        # insight_id required
        if insight_id is None:
            return add_response_metadata({
                "error": {
                    "code": 400,
                    "message": "insight_id is required",
                    "field": "insight_id"
                }
            }, project_id)

        if not isinstance(insight_id, int) or insight_id < 1:
            return add_response_metadata({
                "error": {
                    "code": 400,
                    "message": "insight_id must be a positive integer",
                    "field": "insight_id"
                }
            }, project_id)

        # actor required
        if actor is None:
            return add_response_metadata({
                "error": {
                    "code": 400,
                    "message": "actor is required",
                    "field": "actor"
                }
            }, project_id)

        if actor not in ["I/O", "ethr"]:
            return add_response_metadata({
                "error": {
                    "code": 400,
                    "message": "actor must be 'I/O' or 'ethr'",
                    "field": "actor"
                }
            }, project_id)

        # reason required (AC-6)
        if not reason:
            return add_response_metadata({
                "error": {
                    "code": 400,
                    "message": "reason required",
                    "field": "reason"
                }
            }, project_id)

        # ===== EP-1 CONSENT-AWARE PATTERN =====

        if actor == "I/O":
            # I/O can delete directly - these are I/O's own memories
            logger.info(f"I/O deleting insight {insight_id} directly")

            try:
                result = await execute_delete_with_history(
                    insight_id=insight_id,
                    actor="I/O",
                    reason=reason
                )

                logger.info(f"Insight {insight_id} deleted successfully")
                return add_response_metadata(result, project_id)

            except ValueError as ve:
                # Validation errors (not found, already deleted, etc.)
                error_msg = str(ve)
                if "not found" in error_msg:
                    return add_response_metadata({
                        "error": {
                            "code": 404,
                            "message": f"Insight {insight_id} not found"
                        }
                    }, project_id)
                elif "already deleted" in error_msg:
                    return add_response_metadata({
                        "error": {
                            "code": 409,
                            "message": "already deleted"
                        }
                    }, project_id)
                else:
                    return add_response_metadata({
                        "error": {
                            "code": 400,
                            "message": error_msg
                        }
                    }, project_id)

            except Exception as e:
                logger.error(f"Failed to delete insight {insight_id}: {e}")
                return add_response_metadata({
                    "error": {
                        "code": 500,
                        "message": "Internal error during delete",
                        "details": str(e)
                    }
                }, project_id)

        else:  # actor == "ethr"
            # ethr requires bilateral consent - create SMF proposal
            logger.info(f"ethr requesting deletion of insight {insight_id} - creating SMF proposal")

            try:
                # Create SMF proposal for DELETE_INSIGHT action
                proposal_id = create_smf_proposal(
                    trigger_type=TriggerType.MANUAL,
                    proposed_action={
                        "action": SMFAction.DELETE_INSIGHT,
                        "insight_id": insight_id,
                    },
                    affected_edges=[],  # Insights don't have edge IDs
                    reasoning=reason,
                    approval_level=ApprovalLevel.BILATERAL,  # EP-1: Bilateral consent
                    original_state={
                        "insight_id": insight_id,
                        "actor": "ethr",
                    }
                )

                logger.info(f"SMF proposal {proposal_id} created for insight {insight_id} deletion")
                return add_response_metadata({
                    "status": "pending",
                    "proposal_id": proposal_id,
                    "message": "Waiting for I/O approval"
                }, project_id)

            except Exception as e:
                logger.error(f"Failed to create SMF proposal: {e}")
                return add_response_metadata({
                    "error": {
                        "code": 500,
                        "message": "Failed to create consent proposal",
                        "details": str(e)
                    }
                }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in delete_insight: {e}")
        # project_id is already available from line 58
        return add_response_metadata({
            "error": {
                "code": 500,
                "message": "Tool execution failed",
                "details": str(e)
            }
        }, project_id)
