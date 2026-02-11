"""
list_insights Tool Implementation

MCP tool for listing L2 insights with pagination and extended filtering.
Supports filtering by tags, date ranges, io_category, is_identity, and memory_sector.

Story 9.2.2: list_insights New Endpoint
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from mcp_server.db.insights import list_insights
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_list_insights(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    List L2 insights with pagination and extended filtering.

    Story 9.2.2: list_insights New Endpoint

    Args:
        arguments: Tool arguments containing optional limit, offset, tags,
                   date_from, date_to, io_category, is_identity, memory_sector

    Returns:
        Success response with insights list and pagination info, plus metadata with project_id,
        or error response with metadata if validation or database operation fails.
    """
    logger = logging.getLogger(__name__)

    try:
        # Get project_id from middleware context (Story 11.4.3 pattern)
        # Do this FIRST so error handlers can use it
        project_id = get_current_project()

        # Extract parameters with defaults
        limit = arguments.get("limit", 50)
        offset = arguments.get("offset", 0)
        tags = arguments.get("tags")
        date_from_str = arguments.get("date_from")
        date_to_str = arguments.get("date_to")
        io_category = arguments.get("io_category")
        is_identity = arguments.get("is_identity")
        memory_sector = arguments.get("memory_sector")

        # Parameter validation - limit
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "limit must be between 1 and 100",
                "tool": "list_insights",
            }, project_id)

        # Parameter validation - offset
        if not isinstance(offset, int) or offset < 0:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "offset must be >= 0",
                "tool": "list_insights",
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
                    "tool": "list_insights",
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
                    "tool": "list_insights",
                }, project_id)

        # Validate tags parameter (must be array of strings if provided)
        if tags is not None:
            if not isinstance(tags, list):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "tags must be an array of strings",
                    "tool": "list_insights",
                }, project_id)
            # Validate all items are strings
            for tag in tags:
                if not isinstance(tag, str):
                    return add_response_metadata({
                        "error": "Parameter validation failed",
                        "details": "tags must be an array of strings",
                        "tool": "list_insights",
                    }, project_id)
            # Treat empty array as no filter (None) for consistent SQL NULL handling
            if len(tags) == 0:
                tags = None

        # Validate io_category parameter (must be string if provided)
        if io_category is not None and not isinstance(io_category, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "io_category must be a string",
                "tool": "list_insights",
            }, project_id)
        # Validate io_category value (Story 9.2.2 AC-4)
        if io_category is not None and io_category not in ("self", "ethr", "shared", "relationship"):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": f"io_category must be one of: self, ethr, shared, relationship (got: {io_category})",
                "tool": "list_insights",
            }, project_id)

        # Validate is_identity parameter (must be boolean if provided)
        if is_identity is not None and not isinstance(is_identity, bool):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "is_identity must be a boolean",
                "tool": "list_insights",
            }, project_id)

        # Validate memory_sector parameter (must be string if provided)
        if memory_sector is not None and not isinstance(memory_sector, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "memory_sector must be a string",
                "tool": "list_insights",
            }, project_id)
        # Validate memory_sector value (Story 9.2.2 AC-6)
        if memory_sector is not None and memory_sector not in ("emotional", "episodic", "semantic", "procedural", "reflective"):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": f"memory_sector must be one of: emotional, episodic, semantic, procedural, reflective (got: {memory_sector})",
                "tool": "list_insights",
            }, project_id)

        # Database lookup
        try:
            result = await list_insights(
                limit=limit,
                offset=offset,
                tags=tags,
                date_from=date_from,
                date_to=date_to,
                io_category=io_category,
                is_identity=is_identity,
                memory_sector=memory_sector,
            )

            logger.debug(f"Listed {len(result['insights'])} insights")

            # Return response with status at end
            return add_response_metadata({
                "insights": result["insights"],
                "total_count": result["total_count"],
                "limit": result["limit"],
                "offset": result["offset"],
                "status": "success",
            }, project_id)

        except Exception as db_error:
            logger.error(f"Database error in list_insights: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "list_insights",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in list_insights: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "list_insights",
        }, project_id)
