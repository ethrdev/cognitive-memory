"""
get_edge Tool Implementation

MCP tool for retrieving a graph edge by source name, target name, and relation
for write-then-verify operations.
Returns edge data if found, or graceful null response if not found (no exception).

Story 6.2: get_edge MCP Tool
Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.graph import get_edge_by_names
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_get_edge(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve a graph edge by source name, target name, and relation for verification.

    Args:
        arguments: Tool arguments containing 'source_name', 'target_name', 'relation'

    Returns:
        Dict with edge data and status "success" if found,
        or {edge: null, status: "not_found"} if not found.
        All responses include metadata with project_id (FR29).
        Never throws exception for missing edge - graceful null return.
    """
    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        source_name = arguments.get("source_name")
        target_name = arguments.get("target_name")
        relation = arguments.get("relation")

        # Parameter validation - source_name (must be non-empty, non-whitespace string)
        if not source_name or not isinstance(source_name, str) or not source_name.strip():
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'source_name' parameter (must be non-empty string)",
                "tool": "get_edge",
            }, project_id)

        # Parameter validation - target_name (must be non-empty, non-whitespace string)
        if not target_name or not isinstance(target_name, str) or not target_name.strip():
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'target_name' parameter (must be non-empty string)",
                "tool": "get_edge",
            }, project_id)

        # Parameter validation - relation (must be non-empty, non-whitespace string)
        if not relation or not isinstance(relation, str) or not relation.strip():
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'relation' parameter (must be non-empty string)",
                "tool": "get_edge",
            }, project_id)

        # Database lookup
        try:
            edge = await get_edge_by_names(source_name, target_name, relation)

            if edge:
                logger.debug(
                    f"Edge found: id={edge['id']}, "
                    f"source={source_name}, target={target_name}, relation={relation}"
                )
                return add_response_metadata({
                    "edge_id": edge["id"],
                    "source_id": edge["source_id"],
                    "target_id": edge["target_id"],
                    "relation": edge["relation"],
                    "weight": edge["weight"],
                    "properties": edge["properties"],
                    "memory_sector": edge["memory_sector"],  # Story 8-5: FR26
                    "created_at": edge["created_at"],
                    "status": "success",
                }, project_id)
            else:
                # Graceful null return - not an error
                logger.debug(
                    f"Edge not found: source={source_name}, "
                    f"target={target_name}, relation={relation}"
                )
                return add_response_metadata({
                    "edge": None,
                    "status": "not_found",
                }, project_id)

        except Exception as db_error:
            logger.error(f"Database error in get_edge: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "get_edge",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in get_edge: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "get_edge",
        }, project_id)
