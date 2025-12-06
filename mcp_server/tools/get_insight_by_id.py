"""
get_insight_by_id Tool Implementation

MCP tool for retrieving an L2 insight by its ID for spot verification.
Returns insight data if found, or graceful null response if not found (no exception).

Story 6.5: get_insight_by_id MCP Tool
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.insights import get_insight_by_id


async def handle_get_insight_by_id(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve an L2 insight by its ID for verification purposes.

    Args:
        arguments: Tool arguments containing 'id' parameter

    Returns:
        Dict with insight data and status "success" if found,
        or {insight: null, status: "not_found"} if not found.
        Never throws exception for missing insight - graceful null return.
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        insight_id = arguments.get("id")

        # Parameter validation
        if insight_id is None:
            return {
                "error": "Parameter validation failed",
                "details": "Missing required 'id' parameter",
                "tool": "get_insight_by_id",
            }

        if not isinstance(insight_id, int):
            return {
                "error": "Parameter validation failed",
                "details": "'id' must be an integer",
                "tool": "get_insight_by_id",
            }

        if insight_id < 1:
            return {
                "error": "Parameter validation failed",
                "details": "'id' must be >= 1",
                "tool": "get_insight_by_id",
            }

        # Database lookup
        try:
            insight = get_insight_by_id(insight_id)

            if insight:
                logger.debug(f"Insight found: id={insight_id}")
                return {
                    "id": insight["id"],
                    "content": insight["content"],
                    "source_ids": insight["source_ids"],
                    "metadata": insight["metadata"] or {},  # Defensive: handle None from mocks
                    "created_at": insight["created_at"],
                    "status": "success",
                }
            else:
                # Graceful null return - not an error
                logger.debug(f"Insight not found: id={insight_id}")
                return {
                    "insight": None,
                    "status": "not_found",
                }

        except Exception as db_error:
            logger.error(f"Database error in get_insight_by_id: {db_error}")
            return {
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "get_insight_by_id",
            }

    except Exception as e:
        logger.error(f"Unexpected error in get_insight_by_id: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "get_insight_by_id",
        }
