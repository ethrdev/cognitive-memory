"""
graph_find_path Tool Implementation

MCP tool for finding the shortest path between two nodes in a graph.
Uses BFS-based pathfinding via PostgreSQL WITH RECURSIVE CTE with
bidirectional traversal, cycle detection, and performance protection.

Story 4.5: graph_find_path Tool Implementation
Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
"""

from __future__ import annotations

import logging
import time
from typing import Any

from mcp_server.db.graph import find_path, get_node_by_name
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata

logger = logging.getLogger(__name__)


async def handle_graph_find_path(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Find the shortest path between two nodes using BFS-based pathfinding.

    Args:
        arguments: Tool arguments containing start_node, end_node, max_depth

    Returns:
        Dict with path_found boolean, path_length, and paths array containing
        node and edge details for each found path, plus metadata containing project_id (FR29),
        or error response with metadata if validation/database operations fail
    """
    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        start_node = arguments.get("start_node")
        end_node = arguments.get("end_node")
        max_depth = arguments.get("max_depth", 5)  # Optional, default 5
        use_ief = arguments.get("use_ief", False)  # Optional, default False
        query_embedding = arguments.get("query_embedding")  # Optional

        # Parameter validation
        if not start_node or not isinstance(start_node, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'start_node' parameter (must be non-empty string)",
                "error_type": "invalid_parameters",
                "tool": "graph_find_path",
            }, project_id)

        if not end_node or not isinstance(end_node, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'end_node' parameter (must be non-empty string)",
                "error_type": "invalid_parameters",
                "tool": "graph_find_path",
            }, project_id)

        # Max depth validation (must be integer between 1 and 10)
        try:
            max_depth = int(max_depth)
            if not (1 <= max_depth <= 10):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'max_depth' parameter (must be integer between 1 and 10)",
                    "error_type": "invalid_parameters",
                    "tool": "graph_find_path",
                }, project_id)
        except (ValueError, TypeError):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'max_depth' parameter (must be integer between 1 and 10)",
                "error_type": "invalid_parameters",
                "tool": "graph_find_path",
            }, project_id)

        # use_ief validation (must be boolean)
        if not isinstance(use_ief, bool):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'use_ief' parameter (must be boolean)",
                "error_type": "invalid_parameters",
                "tool": "graph_find_path",
            }, project_id)

        # query_embedding validation (must be array of 1536 numbers if provided)
        if query_embedding is not None:
            if not isinstance(query_embedding, list):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'query_embedding' parameter (must be array of numbers)",
                    "error_type": "invalid_parameters",
                    "tool": "graph_find_path",
                }, project_id)
            if len(query_embedding) != 1536:
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'query_embedding' parameter (must be exactly 1536 numbers)",
                    "error_type": "invalid_parameters",
                    "tool": "graph_find_path",
                }, project_id)

        # Start performance timing
        start_time = time.time()

        # Database operation with timeout and retry logic
        try:
            # First, find the start and end nodes by name
            start_node_data = await get_node_by_name(name=start_node)
            if not start_node_data:
                return add_response_metadata({
                    "error": "Start node not found",
                    "details": f"No node found with name '{start_node}'",
                    "error_type": "start_node_not_found",
                    "tool": "graph_find_path",
                }, project_id)

            end_node_data = await get_node_by_name(name=end_node)
            if not end_node_data:
                return add_response_metadata({
                    "error": "End node not found",
                    "details": f"No node found with name '{end_node}'",
                    "error_type": "end_node_not_found",
                    "tool": "graph_find_path",
                }, project_id)

            # Handle same-node query case
            if start_node == end_node:
                logger.info(f"Same-node query: '{start_node}' -> path_length=0")
                return add_response_metadata({
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
                }, project_id)

            # Find path with the specified parameters
            result = await find_path(
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
                return add_response_metadata({
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
                }, project_id)

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
            return add_response_metadata({
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
            }, project_id)

        except Exception as db_error:
            logger.error(f"Database error in graph_find_path: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "graph_find_path",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in graph_find_path: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_find_path",
        }, project_id)
