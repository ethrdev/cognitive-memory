"""
count_by_type Tool Implementation

MCP tool for retrieving counts of all memory types for audit and integrity checks.
Returns counts for graph_nodes, graph_edges, l2_insights, episodes, working_memory,
and raw_dialogues.

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 6.3: count_by_type MCP Tool
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.stats import get_all_counts
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata


async def handle_count_by_type(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Retrieve counts of all memory types for audit purposes.

    Args:
        arguments: Tool arguments (empty - this is a parameterless tool)

    Returns:
        Dict with counts for all 6 memory types and status "success",
        or error response if database operation fails.
    """
    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Database lookup - get all counts in single query
        counts = await get_all_counts()

        logger.debug(f"Retrieved counts: {counts}")

        # Return response with all counts + status at end
        return add_response_metadata({
            "graph_nodes": counts["graph_nodes"],
            "graph_edges": counts["graph_edges"],
            "l2_insights": counts["l2_insights"],
            "episodes": counts["episodes"],
            "working_memory": counts["working_memory"],
            "raw_dialogues": counts["raw_dialogues"],
            "status": "success",
        }, project_id)

    except Exception as db_error:
        logger.error(f"Database error in count_by_type: {db_error}")
        # project_id is already available from line 37
        return add_response_metadata({
            "error": "Database operation failed",
            "details": str(db_error),
            "tool": "count_by_type",
        }, project_id)
