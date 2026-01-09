"""
delete_insight Tool Implementation

MCP tool for soft-deleting an existing L2 insight.
Implements EP-1 (Consent-Aware), EP-2 (Soft-Delete), and EP-3 (History-on-Mutation) patterns.

Story 26.3: DELETE Operation
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.insights import execute_delete_with_history
from mcp_server.analysis.smf import create_smf_proposal, TriggerType, ApprovalLevel, SMFAction


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
        # Extract parameters
        insight_id = arguments.get("insight_id")
        actor = arguments.get("actor")
        reason = arguments.get("reason")

        # ===== PARAMETER VALIDATION =====

        # insight_id required
        if insight_id is None:
            return {
                "error": {
                    "code": 400,
                    "message": "insight_id is required",
                    "field": "insight_id"
                }
            }

        if not isinstance(insight_id, int) or insight_id < 1:
            return {
                "error": {
                    "code": 400,
                    "message": "insight_id must be a positive integer",
                    "field": "insight_id"
                }
            }

        # actor required
        if actor is None:
            return {
                "error": {
                    "code": 400,
                    "message": "actor is required",
                    "field": "actor"
                }
            }

        if actor not in ["I/O", "ethr"]:
            return {
                "error": {
                    "code": 400,
                    "message": "actor must be 'I/O' or 'ethr'",
                    "field": "actor"
                }
            }

        # reason required (AC-6)
        if not reason:
            return {
                "error": {
                    "code": 400,
                    "message": "reason required",
                    "field": "reason"
                }
            }

        # ===== EP-1 CONSENT-AWARE PATTERN =====

        if actor == "I/O":
            # I/O can delete directly - these are I/O's own memories
            logger.info(f"I/O deleting insight {insight_id} directly")

            try:
                result = execute_delete_with_history(
                    insight_id=insight_id,
                    actor="I/O",
                    reason=reason
                )

                logger.info(f"Insight {insight_id} deleted successfully")
                return result

            except ValueError as ve:
                # Validation errors (not found, already deleted, etc.)
                error_msg = str(ve)
                if "not found" in error_msg:
                    return {
                        "error": {
                            "code": 404,
                            "message": f"Insight {insight_id} not found"
                        }
                    }
                elif "already deleted" in error_msg:
                    return {
                        "error": {
                            "code": 409,
                            "message": "already deleted"
                        }
                    }
                else:
                    return {
                        "error": {
                            "code": 400,
                            "message": error_msg
                        }
                    }

            except Exception as e:
                logger.error(f"Failed to delete insight {insight_id}: {e}")
                return {
                    "error": {
                        "code": 500,
                        "message": "Internal error during delete",
                        "details": str(e)
                    }
                }

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
                return {
                    "status": "pending",
                    "proposal_id": proposal_id,
                    "message": "Waiting for I/O approval"
                }

            except Exception as e:
                logger.error(f"Failed to create SMF proposal: {e}")
                return {
                    "error": {
                        "code": 500,
                        "message": "Failed to create consent proposal",
                        "details": str(e)
                    }
                }

    except Exception as e:
        logger.error(f"Unexpected error in delete_insight: {e}")
        return {
            "error": {
                "code": 500,
                "message": "Tool execution failed",
                "details": str(e)
            }
        }
