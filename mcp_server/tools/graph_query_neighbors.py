"""
graph_query_neighbors Tool Implementation

MCP tool for finding neighbor nodes in a graph with single-hop and multi-hop traversal.
Supports filtering by relation type, depth-limited traversal, cycle detection,
and bidirectional traversal (both/outgoing/incoming).

Story 4.4: graph_query_neighbors Tool Implementation
Bug Fix: Bidirectional graph neighbors (2025-12-07)
Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from mcp_server.audit.shadow_logger import ShadowAuditLogger
from mcp_server.db.graph import get_node_by_name, query_neighbors
from mcp_server.middleware.context import get_current_project
from mcp_server.utils.response import add_response_metadata

logger = logging.getLogger(__name__)


async def handle_graph_query_neighbors(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Find neighbor nodes of a given node with single-hop and multi-hop traversal.

    Args:
        arguments: Tool arguments containing node_name, relation_type, depth, direction, properties_filter

    Returns:
        Dict with array of neighbor nodes with relation, distance, weight, and edge_direction data,
        plus metadata containing project_id (FR29),
        or error response with metadata if validation/database operations fail

    Story 7.6: Added properties_filter parameter for JSONB-based edge property filtering
    Story 11.4.3: Added project_id from middleware context and response metadata
    """
    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        node_name = arguments.get("node_name")
        relation_type = arguments.get("relation_type")  # Optional
        depth = arguments.get("depth", 1)  # Optional, default 1
        direction = arguments.get("direction", "both")  # Optional, default "both"
        include_superseded = arguments.get("include_superseded", False)  # Optional, default False
        properties_filter = arguments.get("properties_filter")  # Optional, Story 7.6
        sector_filter = arguments.get("sector_filter")  # Optional, Story 9-3
        use_ief = arguments.get("use_ief", False)  # Optional, Story 7.7
        query_embedding = arguments.get("query_embedding")  # Optional

        # Parameter validation
        if not node_name or not isinstance(node_name, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'node_name' parameter (must be non-empty string)",
                "tool": "graph_query_neighbors",
            }, project_id)

        if relation_type is not None and not isinstance(relation_type, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'relation_type' parameter (must be string)",
                "tool": "graph_query_neighbors",
            }, project_id)

        # Depth validation (must be integer between 1 and 5)
        try:
            depth = int(depth)
            if not (1 <= depth <= 5):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'depth' parameter (must be integer between 1 and 5)",
                    "tool": "graph_query_neighbors",
                }, project_id)
        except (ValueError, TypeError):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'depth' parameter (must be integer between 1 and 5)",
                "tool": "graph_query_neighbors",
            }, project_id)

        # Direction validation (must be "both", "outgoing", or "incoming")
        valid_directions = ("both", "outgoing", "incoming")
        if not isinstance(direction, str) or direction not in valid_directions:
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": f"Invalid 'direction' parameter (must be one of: {', '.join(valid_directions)})",
                "tool": "graph_query_neighbors",
            }, project_id)

        # include_superseded validation (must be boolean)
        if not isinstance(include_superseded, bool):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'include_superseded' parameter (must be boolean)",
                "tool": "graph_query_neighbors",
            }, project_id)

        # Story 7.6: properties_filter validation (must be dict/object if provided)
        if properties_filter is not None:
            if not isinstance(properties_filter, dict):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'properties_filter' parameter (must be object/dict)",
                    "tool": "graph_query_neighbors",
                }, project_id)

        # Story 9-3: sector_filter validation (must be list of valid MemorySector values or None)
        if sector_filter is not None:
            if not isinstance(sector_filter, list):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'sector_filter' parameter (must be array of sector names)",
                    "tool": "graph_query_neighbors",
                }, project_id)
            valid_sectors = {"emotional", "episodic", "semantic", "procedural", "reflective"}
            invalid_sectors = set(sector_filter) - valid_sectors
            if invalid_sectors:
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": f"Invalid sector(s): {invalid_sectors}. Must be one of: {valid_sectors}",
                    "tool": "graph_query_neighbors",
                }, project_id)

        # use_ief validation (must be boolean)
        if not isinstance(use_ief, bool):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'use_ief' parameter (must be boolean)",
                "tool": "graph_query_neighbors",
            }, project_id)

        # query_embedding validation (must be array of 1536 numbers if provided)
        if query_embedding is not None:
            if not isinstance(query_embedding, list):
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'query_embedding' parameter (must be array of numbers)",
                    "tool": "graph_query_neighbors",
                }, project_id)
            if len(query_embedding) != 1536:
                return add_response_metadata({
                    "error": "Parameter validation failed",
                    "details": "Invalid 'query_embedding' parameter (must be exactly 1536 numbers)",
                    "tool": "graph_query_neighbors",
                }, project_id)

        # Start performance timing
        start_time = time.time()

        # Database operation with retry logic
        try:
            # First, find the start node by name
            start_node = await get_node_by_name(name=node_name)
            if not start_node:
                return add_response_metadata({
                    "error": "Start node not found",
                    "details": f"No node found with name '{node_name}'",
                    "tool": "graph_query_neighbors",
                }, project_id)

            # Query neighbors with the specified parameters
            # Story 7.6: Added properties_filter parameter
            # Story 9-3: Added sector_filter parameter
            result = await query_neighbors(
                node_id=start_node["id"],
                relation_type=relation_type,
                max_depth=depth,
                direction=direction,
                include_superseded=include_superseded,
                properties_filter=properties_filter,
                sector_filter=sector_filter,
                use_ief=use_ief,
                query_embedding=query_embedding
            )

            # Story 11.3.2: Shadow audit for SELECT operations
            # Log cross-project violations if in shadow mode (non-blocking)
            try:
                shadow_logger = ShadowAuditLogger()
                # Story 11.6.2: Use project-scoped connection for shadow audit consistency
                from mcp_server.db.connection import get_connection_with_project_context
                async with get_connection_with_project_context(read_only=True) as audit_conn:
                    cur = audit_conn.cursor()
                    cur.execute("SELECT current_setting('app.current_project', TRUE) AS project_id")
                    row = cur.fetchone()
                    current_project = row.get("project_id") if row else None

                if current_project:
                    await shadow_logger.log_select_violations(result, current_project)
            except Exception as audit_error:
                # Shadow audit failures never block response
                logger.warning("Shadow audit logging failed (non-blocking)", extra={"error": str(audit_error)})

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
                f"depth={depth}, direction={direction}, relation_type={relation_type or 'all'}, "
                f"found={len(result)} neighbors, time={execution_time:.2f}ms"
            )

            return add_response_metadata({
                "neighbors": result,
                "start_node": {
                    "node_id": start_node["id"],
                    "label": start_node["label"],
                    "name": start_node["name"],
                },
                "query_params": {
                    "depth": depth,
                    "relation_type": relation_type,
                    "direction": direction,
                    "include_superseded": include_superseded,
                    "properties_filter": properties_filter,  # Story 7.6
                    "sector_filter": sector_filter,  # Story 9-3
                    "use_ief": use_ief,  # Story 7.7: ICAI parameter
                },
                "execution_time_ms": round(execution_time, 2),
                "neighbor_count": len(result),
                "status": "success",
            }, project_id)

        except Exception as db_error:
            logger.error(f"Database error in graph_query_neighbors: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "graph_query_neighbors",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in graph_query_neighbors: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_query_neighbors",
        }, project_id)
