"""
update_insight Tool Implementation

MCP tool for updating an existing L2 insight.
Implements EP-1 (Consent-Aware) and EP-3 (History-on-Mutation) patterns.

Story 26.2: UPDATE Operation
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.insights import execute_update_with_history
from mcp_server.analysis.smf import create_smf_proposal, TriggerType, ApprovalLevel, SMFAction


async def handle_update_insight(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Update an existing L2 insight with bilateral consent support (EP-1).

    EP-1 Consent-Aware Pattern:
    - I/O as Actor: Direct execution (I/O's own memories)
    - ethr as Actor: SMF proposal created, pending status returned

    EP-3 History-on-Mutation Pattern:
    - History is written in the SAME transaction as the update
    - Atomic rollback if either operation fails

    Args:
        arguments: Tool arguments containing:
            - insight_id (int, required): ID of the insight to update
            - actor (str, required): "I/O" or "ethr"
            - reason (str, required): Reason for the update (audit trail)
            - new_content (str, optional): New content for the insight
            - new_memory_strength (float, optional): New memory strength (0.0-1.0)

    Returns:
        Dict with:
        - I/O actor: {"success": True, "insight_id": int, "history_id": int, "updated_fields": {...}}
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
        new_content = arguments.get("new_content")
        new_memory_strength = arguments.get("new_memory_strength")

        # ===== PARAMETER VALIDATION (AC-3, AC-4) =====

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

        # reason required (AC-3)
        if not reason:
            return {
                "error": {
                    "code": 400,
                    "message": "reason required",
                    "field": "reason"
                }
            }

        # At least one change required (AC-4)
        if new_content is None and new_memory_strength is None:
            return {
                "error": {
                    "code": 400,
                    "message": "no changes provided",
                    "field": None
                }
            }

        # Empty content check (AC-4)
        if new_content is not None and len(str(new_content).strip()) == 0:
            return {
                "error": {
                    "code": 400,
                    "message": "new_content cannot be empty",
                    "field": "new_content"
                }
            }

        # Memory strength range validation
        if new_memory_strength is not None:
            try:
                strength = float(new_memory_strength)
                if not (0.0 <= strength <= 1.0):
                    return {
                        "error": {
                            "code": 400,
                            "message": "new_memory_strength must be between 0.0 and 1.0",
                            "field": "new_memory_strength"
                        }
                    }
                new_memory_strength = strength
            except (ValueError, TypeError):
                return {
                    "error": {
                        "code": 400,
                        "message": "new_memory_strength must be a number",
                        "field": "new_memory_strength"
                    }
                }

        # ===== EP-1 CONSENT-AWARE PATTERN =====

        if actor == "I/O":
            # I/O can update directly - these are I/O's own memories
            logger.info(f"I/O updating insight {insight_id} directly")

            try:
                result = await execute_update_with_history(
                    insight_id=insight_id,
                    new_content=new_content,
                    new_memory_strength=new_memory_strength,
                    actor="I/O",
                    reason=reason
                )

                logger.info(f"Insight {insight_id} updated successfully")
                return result

            except ValueError as ve:
                # Validation errors (not found, etc.)
                error_msg = str(ve)
                if "not found" in error_msg:
                    return {
                        "error": {
                            "code": 404,
                            "message": f"Insight {insight_id} not found"
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
                logger.error(f"Failed to update insight {insight_id}: {e}")
                return {
                    "error": {
                        "code": 500,
                        "message": "Internal error during update",
                        "details": str(e)
                    }
                }

        else:  # actor == "ethr"
            # ethr requires bilateral consent - create SMF proposal
            logger.info(f"ethr requesting update to insight {insight_id} - creating SMF proposal")

            try:
                # Create SMF proposal for UPDATE_INSIGHT action
                proposal_id = create_smf_proposal(
                    trigger_type=TriggerType.MANUAL,
                    proposed_action={
                        "action": SMFAction.UPDATE_INSIGHT,
                        "insight_id": insight_id,
                        "new_content": new_content,
                        "new_memory_strength": new_memory_strength,
                    },
                    affected_edges=[],  # Insights don't have edge IDs
                    reasoning=reason,
                    approval_level=ApprovalLevel.BILATERAL,  # EP-1: Bilateral consent
                    original_state={
                        "insight_id": insight_id,
                        "actor": "ethr",
                    }
                )

                logger.info(f"SMF proposal {proposal_id} created for insight {insight_id} update")
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
        logger.error(f"Unexpected error in update_insight: {e}")
        return {
            "error": {
                "code": 500,
                "message": "Tool execution failed",
                "details": str(e)
            }
        }
