"""
graph_update_node Tool Implementation

MCP tool for updating existing graph node properties and vector_id.
Enables retroactive linking of graph nodes to L2 insights.

Hybrid-search-fix Plan: Fix 3
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.graph import get_node_by_name, update_node_properties
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata

logger = logging.getLogger(__name__)


async def handle_graph_update_node(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Update an existing graph node's properties and/or vector_id.

    Lookup by name (not UUID) for ergonomic MCP usage.
    Properties are merged (not replaced). vector_id can be set or updated.

    Args:
        arguments: Tool arguments containing name, properties, vector_id

    Returns:
        Dict with updated node data or error
    """
    try:
        project_id = get_current_project()

        name = arguments.get("name")
        properties = arguments.get("properties")
        vector_id = arguments.get("vector_id")

        # Validation
        if not name or not isinstance(name, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'name' parameter (must be non-empty string)",
                "tool": "graph_update_node",
            }, project_id)

        if properties is not None and not isinstance(properties, dict):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'properties' parameter (must be object/dict)",
                "tool": "graph_update_node",
            }, project_id)

        if vector_id is not None and (not isinstance(vector_id, int) or vector_id <= 0):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'vector_id' parameter (must be positive integer referencing l2_insights.id)",
                "tool": "graph_update_node",
            }, project_id)

        if properties is None and vector_id is None:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "At least one of 'properties' or 'vector_id' must be provided",
                "tool": "graph_update_node",
            }, project_id)

        # Lookup node by name
        node = await get_node_by_name(name)
        if not node:
            return add_response_metadata({
                "error": "Node not found",
                "details": f"No node with name '{name}' exists",
                "tool": "graph_update_node",
            }, project_id)

        node_id = node["id"]

        # Update via DB layer (reuses existing update_node_properties)
        try:
            result = await update_node_properties(
                node_id=node_id,
                new_properties=properties,
                vector_id=vector_id,
            )

            logger.info(
                "Updated node",
                extra={"name": name, "vector_id": vector_id},
            )

            return add_response_metadata({
                "node_id": result["id"],
                "name": result["name"],
                "label": result["label"],
                "properties": result["properties"],
                "vector_id": result["vector_id"],
                "status": "success",
            }, project_id)

        except Exception as db_error:
            logger.error(
                "Database error in graph_update_node",
                extra={"error": str(db_error), "name": name},
            )
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "graph_update_node",
            }, project_id)

    except Exception as e:
        logger.error(
            "Unexpected error in graph_update_node",
            extra={"error": str(e)},
        )
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_update_node",
        }, get_current_project())
