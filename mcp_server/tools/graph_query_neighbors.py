"""
graph_query_neighbors Tool Implementation

MCP tool for finding neighbor nodes in a graph with single-hop and multi-hop traversal.
Supports filtering by relation type, depth-limited traversal, and cycle detection.

Story 4.4: graph_query_neighbors Tool Implementation
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from mcp_server.db.graph import get_node_by_name, query_neighbors

logger = logging.getLogger(__name__)


async def handle_graph_query_neighbors(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Find neighbor nodes of a given node with single-hop and multi-hop traversal.

    Args:
        arguments: Tool arguments containing node_name, relation_type, depth

    Returns:
        Dict with array of neighbor nodes with relation, distance, and weight data,
        or error response if validation/database operations fail
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        node_name = arguments.get("node_name")
        relation_type = arguments.get("relation_type")  # Optional
        depth = arguments.get("depth", 1)  # Optional, default 1

        # Parameter validation
        if not node_name or not isinstance(node_name, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'node_name' parameter (must be non-empty string)",
                "tool": "graph_query_neighbors",
            }

        if relation_type is not None and not isinstance(relation_type, str):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'relation_type' parameter (must be string)",
                "tool": "graph_query_neighbors",
            }

        # Depth validation (must be integer between 1 and 5)
        try:
            depth = int(depth)
            if not (1 <= depth <= 5):
                return {
                    "error": "Parameter validation failed",
                    "details": "Invalid 'depth' parameter (must be integer between 1 and 5)",
                    "tool": "graph_query_neighbors",
                }
        except (ValueError, TypeError):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'depth' parameter (must be integer between 1 and 5)",
                "tool": "graph_query_neighbors",
            }

        # Start performance timing
        start_time = time.time()

        # Database operation with retry logic
        try:
            # First, find the start node by name
            start_node = get_node_by_name(name=node_name)
            if not start_node:
                return {
                    "error": "Start node not found",
                    "details": f"No node found with name '{node_name}'",
                    "tool": "graph_query_neighbors",
                }

            # Query neighbors with the specified parameters
            result = query_neighbors(
                node_id=start_node["id"],
                relation_type=relation_type,
                max_depth=depth
            )

            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Log timing information for performance monitoring
            if execution_time < 50:
                logger.debug(f"graph_query_neighbors completed in {execution_time:.2f}ms (fast)")
            elif execution_time < 200:
                logger.info(f"graph_query_neighbors completed in {execution_time:.2f}ms (acceptable)")
            else:
                logger.warning(f"graph_query_neighbors completed in {execution_time:.2f}ms (slow)")

            logger.info(
                f"Query neighbors: node='{node_name}' ({start_node['id']}), "
                f"depth={depth}, relation_type={relation_type or 'all'}, "
                f"found={len(result)} neighbors, time={execution_time:.2f}ms"
            )

            return {
                "neighbors": result,
                "start_node": {
                    "node_id": start_node["id"],
                    "label": start_node["label"],
                    "name": start_node["name"],
                },
                "query_params": {
                    "depth": depth,
                    "relation_type": relation_type,
                },
                "execution_time_ms": round(execution_time, 2),
                "neighbor_count": len(result),
                "status": "success",
            }

        except Exception as db_error:
            logger.error(f"Database error in graph_query_neighbors: {db_error}")
            return {
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "graph_query_neighbors",
            }

    except Exception as e:
        logger.error(f"Unexpected error in graph_query_neighbors: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_query_neighbors",
        }