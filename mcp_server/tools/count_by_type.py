"""
count_by_type Tool Implementation

MCP tool for retrieving counts of all memory types for audit and integrity checks.
Returns counts for graph_nodes, graph_edges, l2_insights, episodes, working_memory,
and raw_dialogues.

Story 6.3: count_by_type MCP Tool
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.stats import get_all_counts


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
        # Database lookup - get all counts in single query
        counts = get_all_counts()

        logger.debug(f"Retrieved counts: {counts}")

        # Return response with all counts + status at end
        return {
            "graph_nodes": counts["graph_nodes"],
            "graph_edges": counts["graph_edges"],
            "l2_insights": counts["l2_insights"],
            "episodes": counts["episodes"],
            "working_memory": counts["working_memory"],
            "raw_dialogues": counts["raw_dialogues"],
            "status": "success",
        }

    except Exception as db_error:
        logger.error(f"Database error in count_by_type: {db_error}")
        return {
            "error": "Database operation failed",
            "details": str(db_error),
            "tool": "count_by_type",
        }
