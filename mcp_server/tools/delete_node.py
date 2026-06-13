"""
delete_node Tool Implementation

MCP tool for deleting a graph node together with all of its incident edges,
project-scoped, guarded by an explicit confirmation flag.

The node can be addressed either directly by `node_id`, or by `name`
(resolved via get_node_by_name, which is project-scoped).

Graph-Enforcement A3: new delete_node tool.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.graph import delete_node, get_node_by_name
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_delete_node(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Delete a graph node and its incident edges.

    Args:
        arguments: Tool arguments containing either:
            - node_id (str): UUID of the node to delete, OR
            - name (str): node name to resolve
            - confirm (bool, required): must be True to actually delete

    Returns:
        Dict with deletion status (deleted, edges_deleted, ...) and metadata.
    """
    logger = logging.getLogger(__name__)

    try:
        project_id = get_current_project()

        node_id = arguments.get("node_id")
        name = arguments.get("name")
        confirm = bool(arguments.get("confirm", False))

        # Confirmation gate — deletion is destructive (node + all incident edges).
        if not confirm:
            return add_response_metadata({
                "deleted": False,
                "status": "confirmation_required",
                "details": (
                    "Set confirm=true to delete this node and all of its "
                    "incident edges. This cannot be undone."
                ),
                "tool": "delete_node",
            }, project_id)

        # Resolve node_id from name if not given directly
        if not node_id:
            if not name or not isinstance(name, str) or not name.strip():
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Provide either 'node_id' or a non-empty 'name'.",
                    "tool": "delete_node",
                }, project_id)

            node = await get_node_by_name(name)
            if not node:
                return add_response_metadata({
                    "deleted": False,
                    "status": "not_found",
                    "details": f"No node named '{name}' found in this project.",
                    "tool": "delete_node",
                }, project_id)
            node_id = node["id"]

        if not isinstance(node_id, str) or not node_id.strip():
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'node_id' (must be non-empty string)",
                "tool": "delete_node",
            }, project_id)

        try:
            result = await delete_node(node_id=node_id)
            result["status"] = "success" if result.get("deleted") else "not_deleted"
            result["tool"] = "delete_node"
            return add_response_metadata(result, project_id)

        except Exception as db_error:
            logger.error(f"Database error in delete_node: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "delete_node",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in delete_node: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "delete_node",
        }, get_current_project())
