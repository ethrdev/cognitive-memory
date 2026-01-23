"""
submit_insight_feedback Tool Implementation

MCP tool for submitting feedback about recalled L2 insights.
Implements EP-4 (Lazy Evaluation) pattern - feedback is stored, IEF updates on next query.

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 26.4: Context Critic
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_submit_insight_feedback(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Submit feedback about whether a recalled L2 insight was helpful.

    EP-4 Lazy Evaluation Pattern:
    - Feedback is stored immediately in ief_feedback table
    - IEF score recalculation happens on NEXT query (not synchronous)
    - This keeps feedback submission fast (< 50ms P95)

    AC-3: Positive feedback (helpful) → stored, IEF will apply +0.1 boost on next query
    AC-4: Negative feedback (not_relevant) → stored with optional context, IEF applies -0.1 reduction
    AC-5: Not Now (not_now) → stored but no score effect

    Args:
        arguments: Tool arguments containing:
            - insight_id (int, required): ID of the insight being rated
            - feedback_type (str, required): One of "helpful", "not_relevant", "not_now"
            - context (str, optional): Additional context explaining the feedback

    Returns:
        Dict with:
        - Success: {"success": True, "feedback_id": int, "note": "IEF will update on next query"}
        - Error: {"error": {"code": int, "message": str, "field": str|None}}

    Raises:
        No exceptions - all errors return structured error responses (EP-5)
    """
    from mcp_server.db.connection import get_connection

    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        insight_id = arguments.get("insight_id")
        feedback_type = arguments.get("feedback_type")
        context = arguments.get("context")

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

        # feedback_type required
        if feedback_type is None:
            return add_response_metadata({
                "error": {
                    "code": 400,
                    "message": "feedback_type is required",
                    "field": "feedback_type"
                }
            }, project_id)

        # Validate feedback_type enum (AC-3, AC-4, AC-5)
        valid_types = ["helpful", "not_relevant", "not_now"]
        if feedback_type not in valid_types:
            return add_response_metadata({
                "error": {
                    "code": 400,
                    "message": f"feedback_type must be one of: {', '.join(valid_types)}",
                    "field": "feedback_type"
                }
            }, project_id)

        # context is optional, but validate it's a string if provided
        if context is not None and not isinstance(context, str):
            return add_response_metadata({
                "error": {
                    "code": 400,
                    "message": "context must be a string if provided",
                    "field": "context"
                }
            }, project_id)

        # ===== INSIGHT EXISTENCE CHECK (AC-8) =====

        # Check if insight exists and is not soft-deleted (EP-2)
        # Use same pattern as update_insight and delete_insight
        async with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, is_deleted
                FROM l2_insights
                WHERE id = %s;
                """,
                (insight_id,)
            )
            result = cursor.fetchone()

            if not result or result.get("is_deleted", False):
                # Return 404 for both not found and soft-deleted (like update/delete)
                return add_response_metadata({
                    "error": {
                        "code": 404,
                        "message": f"Insight {insight_id} not found"
                    }
                }, project_id)

            # ===== EP-4 LAZY EVALUATION: STORE FEEDBACK ONLY =====

            # Store feedback - NO IEF recalculate!
            # IEF will read this feedback on next hybrid_search query
            # Note: Uses 'insight_feedback' table (NOT 'ief_feedback' which is for Story 7.7 ICAI)
            cursor.execute(
                """
                INSERT INTO insight_feedback (insight_id, feedback_type, context, created_at)
                VALUES (%s, %s, %s, NOW())
                RETURNING id;
                """,
                (insight_id, feedback_type, context)
            )

            insert_result = cursor.fetchone()
            feedback_id = int(insert_result["id"])

            # Commit transaction
            conn.commit()

            logger.info(
                f"Feedback {feedback_id} stored for insight {insight_id}: "
                f"type={feedback_type}, context_provided={context is not None}"
            )

            # Return success with lazy evaluation note (AC-3, AC-5)
            return add_response_metadata({
                "success": True,
                "feedback_id": feedback_id,
                "note": "IEF will update on next query"
            }, project_id)

    except Exception as e:
        logger.error(f"Failed to submit feedback for insight {insight_id}: {e}")
        return add_response_metadata({
            "error": {
                "code": 500,
                "message": "Internal error during feedback submission",
                "details": str(e)
            }
        }, get_current_project())  # Still get project_id even in catch block
