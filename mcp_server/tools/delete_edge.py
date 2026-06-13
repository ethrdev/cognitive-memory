"""
delete_edge Tool Implementation

MCP tool for deleting a graph edge, project-scoped, with constitutive-edge
protection (bilateral consent) carried over from the DB layer.

The edge can be addressed either directly by `edge_id`, or by
`source_name` + `target_name` + `relation` (resolved via get_edge_by_names,
which is itself project-scoped).

Graph-Enforcement A3: expose the existing delete_edge DB function as a tool.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.graph import (
    ConstitutiveEdgeProtectionError,
    delete_edge,
    get_edge_by_names,
)
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_delete_edge(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Delete a graph edge.

    Args:
        arguments: Tool arguments containing either:
            - edge_id (str): UUID of the edge to delete, OR
            - source_name + target_name + relation (str each): to resolve the edge
            - consent_given (bool, optional): required to delete constitutive edges

    Returns:
        Dict with deletion status and metadata (project_id).
    """
    logger = logging.getLogger(__name__)

    try:
        project_id = get_current_project()

        edge_id = arguments.get("edge_id")
        source_name = arguments.get("source_name")
        target_name = arguments.get("target_name")
        relation = arguments.get("relation")
        consent_given = bool(arguments.get("consent_given", False))

        # Resolve edge_id from names if not given directly
        if not edge_id:
            if not (source_name and target_name and relation):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": (
                        "Provide either 'edge_id' or all of "
                        "'source_name', 'target_name', 'relation'."
                    ),
                    "tool": "delete_edge",
                }, project_id)

            edge = await get_edge_by_names(source_name, target_name, relation)
            if not edge:
                return add_response_metadata({
                    "deleted": False,
                    "status": "not_found",
                    "details": (
                        f"No edge {source_name} -[{relation}]-> {target_name} "
                        "found in this project."
                    ),
                    "tool": "delete_edge",
                }, project_id)
            edge_id = edge["id"]

        if not isinstance(edge_id, str) or not edge_id.strip():
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'edge_id' (must be non-empty string)",
                "tool": "delete_edge",
            }, project_id)

        try:
            result = await delete_edge(edge_id=edge_id, consent_given=consent_given)
            result["status"] = "success" if result.get("deleted") else "not_deleted"
            result["tool"] = "delete_edge"
            return add_response_metadata(result, project_id)

        except ConstitutiveEdgeProtectionError as protect_err:
            logger.warning(f"delete_edge blocked (constitutive): {protect_err}")
            return add_response_metadata({
                "deleted": False,
                "status": "blocked",
                "error": "Constitutive edge protection",
                "details": getattr(protect_err, "message", str(protect_err)),
                "hint": "Pass consent_given=true to delete a constitutive edge.",
                "tool": "delete_edge",
            }, project_id)

        except Exception as db_error:
            logger.error(f"Database error in delete_edge: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "delete_edge",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in delete_edge: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "delete_edge",
        }, get_current_project())
