"""
list_nodes_by_label Tool Implementation

MCP tool for retrieving all graph nodes with a specific label.
Enables bulk queries like "give me all MarketSignal nodes" without
requiring individual node name lookups.

Use case: CMO Opportunity-Detection needs to iterate ALL MarketSignal nodes
instead of fragile hybrid_search (which fails when nodes lack vector_ids).
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.graph import get_nodes_by_label
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata

logger = logging.getLogger(__name__)


async def handle_list_nodes_by_label(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    List all graph nodes with a specific label.

    Args:
        arguments: Tool arguments containing label and optional limit

    Returns:
        Dict with array of nodes matching the label, plus metadata
    """
    try:
        project_id = get_current_project()

        label = arguments.get("label")
        limit = arguments.get("limit")

        if not label or not isinstance(label, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'label' parameter (must be non-empty string)",
                "tool": "list_nodes_by_label",
            }, project_id)

        if limit is not None:
            try:
                limit = int(limit)
                if limit < 1:
                    return add_response_metadata({
                        "error": "Parameter validation failed",
                        "details": "Invalid 'limit' parameter (must be positive integer)",
                        "tool": "list_nodes_by_label",
                    }, project_id)
            except (ValueError, TypeError):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'limit' parameter (must be integer)",
                    "tool": "list_nodes_by_label",
                }, project_id)

        nodes = await get_nodes_by_label(label)

        if limit:
            nodes = nodes[:limit]

        return add_response_metadata({
            "nodes": nodes,
            "count": len(nodes),
            "label": label,
        }, project_id)

    except Exception as e:
        logger.error(f"list_nodes_by_label failed: {e}")
        project_id = get_current_project()
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "list_nodes_by_label",
        }, project_id)
