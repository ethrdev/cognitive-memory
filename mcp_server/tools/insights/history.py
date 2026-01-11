"""
get_insight_history Tool Implementation

MCP tool for retrieving the complete revision history of an L2 insight.
Reads from l2_insight_history table (Migration 024 + 024b) with field mapping.

Story 26.7: Revision History (Stretch Goal)
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.insights import get_insight_by_id


async def handle_get_insight_history(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve the complete revision history of an L2 insight.

    Returns all historical versions chronologically (oldest first).
    Works for both active and soft-deleted insights (Archäologie-Prinzip).

    Schema Mapping (Migration 024 → Story 26.7 response):
    - version_id → version_id (direct)
    - old_content → previous_content
    - old_memory_strength → previous_memory_strength
    - created_at → changed_at
    - actor → changed_by
    - reason → change_reason

    Args:
        arguments: Tool arguments containing 'insight_id' parameter

    Returns:
        Dict with:
        - Success: {
            "insight_id": int,
            "current_content": str|null,
            "is_deleted": bool,
            "history": [
                {
                    "version_id": int,
                    "previous_content": str,
                    "previous_memory_strength": float,
                    "changed_at": str,
                    "changed_by": str,
                    "change_reason": str
                },
                ...
            ],
            "total_revisions": int
        }
        - NotFound: {"error": {"code": 404, "message": "Insight not found"}}
        - Error: {"error": {"code": 500, "message": str}}

    Raises:
        No exceptions - all errors return structured error responses (EP-5)
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        insight_id = arguments.get("insight_id")

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

        # ===== DATABASE LOOKUP =====

        try:
            # Get current insight data (to check existence and deletion status)
            insight = await get_insight_by_id(insight_id)

            if not insight:
                logger.debug(f"Insight not found: id={insight_id}")
                return {
                    "error": {
                        "code": 404,
                        "message": f"Insight {insight_id} not found"
                    }
                }

            # Query history from l2_insight_history table
            # Uses schema mapping: old_content→previous_content, actor→changed_by, etc.
            # AC-1: History Query
            # AC-2: Version Details
            # AC-3: Empty History (graceful return)
            # AC-4: Deleted Insight History (Archäologie-Prinzip)
            history_query = """
                SELECT
                    version_id,
                    old_content as previous_content,
                    old_memory_strength as previous_memory_strength,
                    created_at as changed_at,
                    actor as changed_by,
                    reason as change_reason,
                    action
                FROM l2_insight_history
                WHERE insight_id = $1
                ORDER BY version_id ASC
            """

            # Import database connection
            from mcp_server.db.connection import get_connection

            async with get_connection() as conn:
                history_rows = await conn.fetch(
                    history_query,
                    insight_id
                )

            # Format response according to Story 26.7 ACs
            history_list = []
            for row in history_rows:
                history_list.append({
                    "version_id": row["version_id"],
                    "previous_content": row["previous_content"],
                    "previous_memory_strength": row["previous_memory_strength"],
                    "changed_at": row["changed_at"].isoformat() if row["changed_at"] else None,
                    "changed_by": row["changed_by"],
                    "change_reason": row["change_reason"]
                })

            # Check if insight is soft-deleted (Migration 023b from Story 26.3)
            # AC-4: Deleted Insight History (Archäologie-Prinzip)
            is_deleted = insight.get("is_deleted", False)

            # Get current content (null if deleted)
            current_content = None if is_deleted else insight.get("content")

            logger.debug(f"History retrieved for insight_id={insight_id}: {len(history_list)} revisions")

            return {
                "insight_id": insight_id,
                "current_content": current_content,
                "is_deleted": is_deleted,
                "history": history_list,
                "total_revisions": len(history_list)
            }

        except Exception as db_error:
            logger.error(f"Database error in get_insight_history: {db_error}")
            return {
                "error": {
                    "code": 500,
                    "message": "Database operation failed",
                    "details": str(db_error)
                }
            }

    except Exception as e:
        logger.error(f"Unexpected error in get_insight_history: {e}")
        return {
            "error": {
                "code": 500,
                "message": "Tool execution failed",
                "details": str(e)
            }
        }


# Tool metadata for MCP server registration
TOOL_NAME = "get_insight_history"
TOOL_DESCRIPTION = (
    "Retrieve the complete revision history of an L2 insight (Story 26.7). "
    "Returns all historical versions chronologically (oldest first). "
    "Works for both active and soft-deleted insights (Archäologie-Prinzip)."
)
TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "insight_id": {
            "type": "integer",
            "description": "ID of the L2 insight to get history for",
            "minimum": 1
        }
    },
    "required": ["insight_id"]
}
