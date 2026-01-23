"""
list_episodes Tool Implementation

MCP tool for listing episode memory entries with pagination.
Supports time filtering and offset-based pagination for audit purposes.

Story 6.4: list_episodes MCP Tool
Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from mcp_server.db.episodes import list_episodes
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_list_episodes(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    List episode memory entries with pagination.

    Args:
        arguments: Tool arguments containing optional limit, offset, since

    Returns:
        Success response with episodes list and pagination info, plus metadata with project_id (FR29),
        or error response with metadata if validation or database operation fails.
    """
    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters with defaults
        limit = arguments.get("limit", 50)
        offset = arguments.get("offset", 0)
        since_str = arguments.get("since")

        # Parameter validation - limit
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "limit must be between 1 and 100",
                "tool": "list_episodes",
            }, project_id)

        # Parameter validation - offset
        if not isinstance(offset, int) or offset < 0:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "offset must be >= 0",
                "tool": "list_episodes",
            }, project_id)

        # Parse since timestamp (ISO 8601)
        since: datetime | None = None
        if since_str:
            try:
                # Python 3.11+ supports ISO 8601 directly
                # Handle 'Z' suffix by replacing with '+00:00'
                since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
            except ValueError:
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": f"Invalid ISO 8601 timestamp: {since_str}",
                    "tool": "list_episodes",
                }, project_id)

        # Database lookup
        try:
            result = await list_episodes(limit=limit, offset=offset, since=since)

            logger.debug(f"Listed {len(result['episodes'])} episodes")

            # Return response with status at end
            return add_response_metadata({
                "episodes": result["episodes"],
                "total_count": result["total_count"],
                "limit": result["limit"],
                "offset": result["offset"],
                "status": "success",
            }, project_id)

        except Exception as db_error:
            logger.error(f"Database error in list_episodes: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "list_episodes",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in list_episodes: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "list_episodes",
        }, project_id)
