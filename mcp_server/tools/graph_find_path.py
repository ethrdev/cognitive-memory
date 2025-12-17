"""
graph_find_path Tool Implementation

MCP tool for finding the shortest path between two nodes in a graph.
Uses BFS-based pathfinding via PostgreSQL WITH RECURSIVE CTE with
bidirectional traversal, cycle detection, and performance protection.

Story 4.5: graph_find_path Tool Implementation
"""

from __future__ import annotations

import logging
import time
from typing import Any

from mcp_server.db.graph import find_path, get_node_by_name

logger = logging.getLogger(__name__)


async def handle_graph_find_path(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Find the shortest path between two nodes using BFS-based pathfinding.

    Args:
        arguments: Tool arguments containing start_node, end_node, max_depth

    Returns:
        Dict with path_found boolean, path_length, and paths array containing
        node and edge details for each found path, or error response if validation/
        database operations fail
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        start_node = arguments.get("start_node")
        end_node = arguments.get("end_node")
        max_depth = arguments.get("max_depth", 5)  # Optional, default 5
        use_ief = arguments.get("use_ief", False)  # Optional, default False
        query_embedding = arguments.get("query_embedding")  # Optional

        # Parameter validation
        if not start_node or not isinstance(start_node, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'start_node' parameter (must be non-empty string)",
                "error_type": "invalid_parameters",
                "tool": "graph_find_path",
            }

        if not end_node or not isinstance(end_node, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'end_node' parameter (must be non-empty string)",
                "error_type": "invalid_parameters",
                "tool": "graph_find_path",
            }

        # Max depth validation (must be integer between 1 and 10)
        try:
            max_depth = int(max_depth)
            if not (1 <= max_depth <= 10):
                return {
                    "error": "Parameter validation failed",
                    "details": "Invalid 'max_depth' parameter (must be integer between 1 and 10)",
                    "error_type": "invalid_parameters",
                    "tool": "graph_find_path",
                }
        except (ValueError, TypeError):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'max_depth' parameter (must be integer between 1 and 10)",
                "error_type": "invalid_parameters",
                "tool": "graph_find_path",
            }

        # use_ief validation (must be boolean)
        if not isinstance(use_ief, bool):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'use_ief' parameter (must be boolean)",
                "error_type": "invalid_parameters",
                "tool": "graph_find_path",
            }

        # query_embedding validation (must be array of 1536 numbers if provided)
        if query_embedding is not None:
            if not isinstance(query_embedding, list):
                return {
                    "error": "Parameter validation failed",
                    "details": "Invalid 'query_embedding' parameter (must be array of numbers)",
                    "error_type": "invalid_parameters",
                    "tool": "graph_find_path",
                }
            if len(query_embedding) != 1536:
                return {
                    "error": "Parameter validation failed",
                    "details": "Invalid 'query_embedding' parameter (must be exactly 1536 numbers)",
                    "error_type": "invalid_parameters",
                    "tool": "graph_find_path",
                }

        # Start performance timing
        start_time = time.time()

        # Database operation with timeout and retry logic
        try:
            # First, find the start and end nodes by name
            start_node_data = get_node_by_name(name=start_node)
            if not start_node_data:
                return {
                    "error": "Start node not found",
                    "details": f"No node found with name '{start_node}'",
                    "error_type": "start_node_not_found",
                    "tool": "graph_find_path",
                }

            end_node_data = get_node_by_name(name=end_node)
            if not end_node_data:
                return {
                    "error": "End node not found",
                    "details": f"No node found with name '{end_node}'",
                    "error_type": "end_node_not_found",
                    "tool": "graph_find_path",
                }

            # Handle same-node query case
            if start_node == end_node:
                logger.info(f"Same-node query: '{start_node}' -> path_length=0")
                return {
                    "path_found": True,
                    "path_length": 0,
                    "paths": [{
                        "nodes": [{
                            "node_id": start_node_data["id"],
                            "label": start_node_data["label"],
                            "name": start_node_data["name"],
                            "properties": start_node_data["properties"],
                        }],
                        "edges": [],
                        "total_weight": 0.0,
                    }],
                    "execution_time_ms": round((time.time() - start_time) * 1000, 2),
                    "query_params": {
                        "start_node": start_node,
                        "end_node": end_node,
                        "max_depth": max_depth,
                    },
                    "status": "success",
                }

            # Find path with the specified parameters
            result = find_path(
                start_node_name=start_node,
                end_node_name=end_node,
                max_depth=max_depth,
                use_ief=use_ief,
                query_embedding=query_embedding
            )

            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Handle timeout case
            if "error_type" in result and result["error_type"] == "timeout":
                logger.warning(f"Pathfinding timeout after {execution_time:.2f}ms for '{start_node}' -> '{end_node}'")
                return {
                    "error": "Pathfinding query timeout",
                    "details": "Query exceeded 1 second timeout limit",
                    "error_type": "timeout",
                    "execution_time_ms": round(execution_time, 2),
                    "query_params": {
                        "start_node": start_node,
                        "end_node": end_node,
                        "max_depth": max_depth,
                    },
                    "tool": "graph_find_path",
                }

            # Log timing information for performance monitoring
            if execution_time < 100:
                logger.debug(f"graph_find_path completed in {execution_time:.2f}ms (fast)")
            elif execution_time < 500:
                logger.info(f"graph_find_path completed in {execution_time:.2f}ms (acceptable)")
            else:
                logger.warning(f"graph_find_path completed in {execution_time:.2f}ms (slow)")

            logger.info(
                f"Find path: '{start_node}' ({start_node_data['id']}) -> '{end_node}' ({end_node_data['id']}), "
                f"max_depth={max_depth}, found={len(result.get('paths', []))} paths, "
                f"path_found={result.get('path_found', False)}, time={execution_time:.2f}ms"
            )

            # Return successful result
            return {
                "path_found": result.get("path_found", False),
                "path_length": result.get("path_length", 0),
                "paths": result.get("paths", []),
                "execution_time_ms": round(execution_time, 2),
                "query_params": {
                    "start_node": start_node,
                    "end_node": end_node,
                    "max_depth": max_depth,
                },
                "status": "success",
            }

        except Exception as db_error:
            logger.error(f"Database error in graph_find_path: {db_error}")
            return {
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "graph_find_path",
            }

    except Exception as e:
        logger.error(f"Unexpected error in graph_find_path: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_find_path",
        }
