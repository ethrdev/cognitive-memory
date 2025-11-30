"""
graph_add_edge Tool Implementation

MCP tool for creating relationships between graph nodes with idempotent operations.
Supports auto-upsert of nodes and standardized relationship types.

Story 4.3: graph_add_edge Tool Implementation
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp_server.db.graph import add_edge, get_or_create_node

logger = logging.getLogger(__name__)

# Standard relations for validation and consistency
STANDARD_RELATIONS = {
    "USES", "SOLVES", "CREATED_BY", "RELATED_TO", "DEPENDS_ON"
}


async def handle_graph_add_edge(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Create or update a relationship edge between graph nodes with auto-upsert.

    Args:
        arguments: Tool arguments containing source_name, target_name, relation,
                   source_label, target_label, weight, properties

    Returns:
        Dict with edge_id, created status, and confirmation data,
        or error response if validation/database operations fail
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        source_name = arguments.get("source_name")
        target_name = arguments.get("target_name")
        relation = arguments.get("relation")
        source_label = arguments.get("source_label", "Entity")  # Optional, default "Entity"
        target_label = arguments.get("target_label", "Entity")  # Optional, default "Entity"
        weight = arguments.get("weight", 1.0)  # Optional, default 1.0
        properties = arguments.get("properties")  # Optional

        # Parameter validation
        if not source_name or not isinstance(source_name, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'source_name' parameter (must be non-empty string)",
                "tool": "graph_add_edge",
            }

        if not target_name or not isinstance(target_name, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'target_name' parameter (must be non-empty string)",
                "tool": "graph_add_edge",
            }

        if not relation or not isinstance(relation, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'relation' parameter (must be non-empty string)",
                "tool": "graph_add_edge",
            }

        if source_label is not None and not isinstance(source_label, str):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'source_label' parameter (must be string)",
                "tool": "graph_add_edge",
            }

        if target_label is not None and not isinstance(target_label, str):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'target_label' parameter (must be string)",
                "tool": "graph_add_edge",
            }

        # Weight validation (0.0-1.0 range)
        if weight is not None:
            try:
                weight = float(weight)
                if not (0.0 <= weight <= 1.0):
                    return {
                        "error": "Parameter validation failed",
                        "details": "Invalid 'weight' parameter (must be float between 0.0 and 1.0)",
                        "tool": "graph_add_edge",
                    }
            except (ValueError, TypeError):
                return {
                    "error": "Parameter validation failed",
                    "details": "Invalid 'weight' parameter (must be float between 0.0 and 1.0)",
                    "tool": "graph_add_edge",
                }

        if properties is not None and not isinstance(properties, dict):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'properties' parameter (must be object/dict)",
                "tool": "graph_add_edge",
            }

        # Log warning for non-standard relations (optional validation, not blocking)
        if relation not in STANDARD_RELATIONS:
            logger.warning(f"Non-standard relation used: '{relation}'. Standard relations: {sorted(STANDARD_RELATIONS)}")

        # Convert properties to JSON string for JSONB storage
        properties_json = json.dumps(properties) if properties else "{}"

        # Database operation with auto-upsert logic
        try:
            # Get or create source node
            source_result = get_or_create_node(name=source_name, label=source_label or "Entity")
            source_id = source_result["node_id"]
            source_created = source_result["created"]

            # Get or create target node
            target_result = get_or_create_node(name=target_name, label=target_label or "Entity")
            target_id = target_result["node_id"]
            target_created = target_result["created"]

            # Create edge between nodes
            edge_result = add_edge(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                weight=weight,
                properties=properties_json
            )

            logger.info(
                f"Edge {'created' if edge_result['created'] else 'updated'}: "
                f"id={edge_result['edge_id']}, source={source_name} ({source_id}), "
                f"target={target_name} ({target_id}), relation={relation}"
            )

            # Add node creation info for transparency
            nodes_info = {}
            if source_created:
                nodes_info["source_node_created"] = True
            if target_created:
                nodes_info["target_node_created"] = True

            response = {
                "edge_id": edge_result["edge_id"],
                "created": edge_result["created"],
                "source_id": edge_result["source_id"],
                "target_id": edge_result["target_id"],
                "relation": edge_result["relation"],
                "weight": edge_result["weight"],
                "status": "success",
            }

            if nodes_info:
                response.update(nodes_info)

            return response

        except Exception as db_error:
            logger.error(f"Database error in graph_add_edge: {db_error}")
            return {
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "graph_add_edge",
            }

    except Exception as e:
        logger.error(f"Unexpected error in graph_add_edge: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_add_edge",
        }