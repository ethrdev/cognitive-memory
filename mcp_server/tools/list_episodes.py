"""
list_episodes Tool Implementation

MCP tool for listing episode memory entries with pagination.
Supports time filtering and offset-based pagination for audit purposes.

Story 6.4: list_episodes MCP Tool
Story 9.2.3: pagination-validation - Uses shared pagination validation utility
Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from mcp_server.db.episodes import list_episodes
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.pagination import (
    LimitValidationError,
    OffsetValidationError,
    validate_pagination_params,
)
from mcp_server.utils.response import add_response_metadata


async def handle_list_episodes(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    List episode memory entries with pagination and extended filtering.

    Story 9.2.1: list_episodes Extended Parameters

    Args:
        arguments: Tool arguments containing optional limit, offset, since, date_from,
                   date_to, tags, category

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
        date_from_str = arguments.get("date_from")
        date_to_str = arguments.get("date_to")
        tags = arguments.get("tags")
        category = arguments.get("category")

        # Story 9.2.3: Use shared pagination validation utility
        try:
            validated = validate_pagination_params(limit=limit, offset=offset)
            limit = validated["limit"]
            offset = validated["offset"]
        except (LimitValidationError, OffsetValidationError) as e:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": str(e),
                "tool": "list_episodes",
            }, project_id)

        # Parse since timestamp (ISO 8601) - legacy alias
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

        # Parse date_from timestamp (ISO 8601)
        date_from: datetime | None = None
        if date_from_str:
            try:
                date_from = datetime.fromisoformat(date_from_str.replace("Z", "+00:00"))
            except ValueError:
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": f"Invalid ISO 8601 timestamp: {date_from_str}",
                    "tool": "list_episodes",
                }, project_id)

        # Parse date_to timestamp (ISO 8601)
        date_to: datetime | None = None
        if date_to_str:
            try:
                date_to = datetime.fromisoformat(date_to_str.replace("Z", "+00:00"))
            except ValueError:
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": f"Invalid ISO 8601 timestamp: {date_to_str}",
                    "tool": "list_episodes",
                }, project_id)

        # Validate tags parameter (must be array of strings if provided)
        if tags is not None:
            if not isinstance(tags, list):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "tags must be an array of strings",
                    "tool": "list_episodes",
                }, project_id)
            # Validate all items are strings
            for tag in tags:
                if not isinstance(tag, str):
                    return add_response_metadata({
                        "error": "Parameter validation failed",
                        "details": "tags must be an array of strings",
                        "tool": "list_episodes",
                    }, project_id)
            # Treat empty array as no filter (None) for consistent SQL NULL handling
            if len(tags) == 0:
                tags = None

        # Validate category parameter (must be string if provided)
        if category is not None and not isinstance(category, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "category must be a string",
                "tool": "list_episodes",
            }, project_id)

        # Database lookup
        try:
            result = await list_episodes(
                limit=limit,
                offset=offset,
                since=since,  # Legacy parameter
                date_from=date_from,  # New parameter
                date_to=date_to,
                tags=tags,
                category=category,
            )

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
