"""
get_insight_by_id Tool Implementation

MCP tool for retrieving an L2 insight by its ID for spot verification.
Returns insight data if found, or graceful null response if not found (no exception).

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 6.5: get_insight_by_id MCP Tool
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.insights import get_insight_by_id
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


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
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        insight_id = arguments.get("id")

        # Parameter validation
        if insight_id is None:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing required 'id' parameter",
                "tool": "get_insight_by_id",
            }, project_id)

        if not isinstance(insight_id, int):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "'id' must be an integer",
                "tool": "get_insight_by_id",
            }, project_id)

        if insight_id < 1:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "'id' must be >= 1",
                "tool": "get_insight_by_id",
            }, project_id)

        # Database lookup
        try:
            insight = await get_insight_by_id(insight_id)

            if insight:
                logger.debug(f"Insight found: id={insight_id}")
                return add_response_metadata({
                    "id": insight["id"],
                    "content": insight["content"],
                    "source_ids": insight["source_ids"],
                    "metadata": insight["metadata"] or {},  # Defensive: handle None from mocks
                    "created_at": insight["created_at"],
                    "status": "success",
                }, project_id)
            else:
                # Graceful null return - not an error
                logger.debug(f"Insight not found: id={insight_id}")
                return add_response_metadata({
                    "insight": None,
                    "status": "not_found",
                }, project_id)

        except Exception as db_error:
            logger.error(f"Database error in get_insight_by_id: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "get_insight_by_id",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in get_insight_by_id: {e}")
        # project_id is already available from line 37
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "get_insight_by_id",
        }, project_id)
