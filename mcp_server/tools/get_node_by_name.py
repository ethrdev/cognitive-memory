"""
get_node_by_name Tool Implementation

MCP tool for retrieving a graph node by its name for write-then-verify operations.
Returns node data if found, or graceful null response if not found (no exception).

Story 6.1: get_node_by_name MCP Tool
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.graph import get_node_by_name


async def handle_get_node_by_name(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve a graph node by its name for verification purposes.

    Args:
        arguments: Tool arguments containing 'name' parameter

    Returns:
        Dict with node data and status "success" if found,
        or {node: null, status: "not_found"} if not found.
        Never throws exception for missing node - graceful null return.
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        name = arguments.get("name")

        # Parameter validation
        if not name or not isinstance(name, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'name' parameter (must be non-empty string)",
                "tool": "get_node_by_name",
            }

        # Database lookup
        try:
            node = await get_node_by_name(name)

            if node:
                logger.debug(f"Node found: id={node['id']}, name={name}")
                return {
                    "node_id": node["id"],
                    "label": node["label"],
                    "name": node["name"],
                    "properties": node["properties"],
                    "vector_id": node["vector_id"],
                    "created_at": node["created_at"],
                    "status": "success",
                }
            else:
                # Graceful null return - not an error
                logger.debug(f"Node not found: name={name}")
                return {
                    "node": None,
                    "status": "not_found",
                }

        except Exception as db_error:
            logger.error(f"Database error in get_node_by_name: {db_error}")
            return {
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "get_node_by_name",
            }

    except Exception as e:
        logger.error(f"Unexpected error in get_node_by_name: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "get_node_by_name",
        }
