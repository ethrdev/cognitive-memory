"""
graph_add_node Tool Implementation

MCP tool for creating or finding graph nodes with idempotent operations.
Supports properties metadata and optional vector linking to L2 insights.

Story 4.2: graph_add_node Tool Implementation
Story 8.4: FR25 Documentation for Future Node-Edge Classification

FR25 (Epic 8): If edge creation is added in the future, edges must be
classified using classify_memory_sector() from mcp_server.utils.sector_classifier.
See Story 8-4 for implementation pattern.

Current implementation: Node-only operation (no edge creation).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp_server.db.graph import add_node

logger = logging.getLogger(__name__)

# Standard labels for validation and consistency
STANDARD_LABELS = {
    "Project", "Technology", "Client", "Error", "Solution"
}


async def handle_graph_add_node(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Create or find a graph node with idempotent operation.

    Args:
        arguments: Tool arguments containing label, name, properties, vector_id

    Returns:
        Dict with node_id, created status, and confirmation data,
        or error response if validation/database operations fail
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        label = arguments.get("label")
        name = arguments.get("name")
        properties = arguments.get("properties")  # Optional
        vector_id = arguments.get("vector_id")    # Optional

        # Parameter validation
        if not label or not isinstance(label, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'label' parameter (must be non-empty string)",
                "tool": "graph_add_node",
            }

        if not name or not isinstance(name, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'name' parameter (must be non-empty string)",
                "tool": "graph_add_node",
            }

        if properties is not None and not isinstance(properties, dict):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'properties' parameter (must be object/dict)",
                "tool": "graph_add_node",
            }

        if vector_id is not None and (not isinstance(vector_id, int) or vector_id <= 0):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'vector_id' parameter (must be positive integer)",
                "tool": "graph_add_node",
            }

        # Log warning for non-standard labels (optional validation, not blocking)
        if label not in STANDARD_LABELS:
            logger.warning(f"Non-standard label used: '{label}'. Standard labels: {sorted(STANDARD_LABELS)}")

        # Convert properties to JSON string for JSONB storage
        properties_json = json.dumps(properties) if properties else "{}"

        # Database operation with retry logic
        try:
            result = await add_node(
                label=label,
                name=name,
                properties=properties_json,
                vector_id=vector_id
            )

            logger.info(f"Node {'created' if result['created'] else 'found'}: id={result['node_id']}, label={label}, name={name}")

            return {
                "node_id": result["node_id"],
                "created": result["created"],
                "label": result["label"],
                "name": result["name"],
                "status": "success",
            }

        except Exception as db_error:
            logger.error(f"Database error in graph_add_node: {db_error}")
            return {
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "graph_add_node",
            }

    except Exception as e:
        logger.error(f"Unexpected error in graph_add_node: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_add_node",
        }
