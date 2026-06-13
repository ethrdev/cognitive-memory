"""
graph_add_node Tool Implementation

MCP tool for creating or finding graph nodes with idempotent operations.
Supports properties metadata and optional vector linking to L2 insights.

Story 4.2: graph_add_node Tool Implementation
Story 8.4: FR25 Documentation for Future Node-Edge Classification
Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata

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
from mcp_server.graph_vocabulary import is_vocabulary_enforced, validate_label
from mcp_server.middleware.context import get_current_project
from mcp_server.tools.embedding import generate_node_embedding
from mcp_server.utils.response import add_response_metadata

logger = logging.getLogger(__name__)

# Standard labels for validation and consistency.
# NOTE: This global set is the *soft* (warning-only) whitelist used for projects
# that do NOT have a hard-enforced vocabulary (see mcp_server.graph_vocabulary).
# Projects with a configured vocabulary (e.g. "tethr") are validated against that
# vocabulary instead, and violations are rejected rather than merely logged.
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
        plus metadata containing project_id (FR29),
        or error response with metadata if validation/database operations fail
    """
    logger = logging.getLogger(__name__)

    try:
        # Story 11.4.3: Get project_id from middleware context
        project_id = get_current_project()

        # Extract parameters
        label = arguments.get("label")
        name = arguments.get("name")
        properties = arguments.get("properties")  # Optional
        vector_id = arguments.get("vector_id")    # Optional

        # Parameter validation
        if not label or not isinstance(label, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'label' parameter (must be non-empty string)",
                "tool": "graph_add_node",
            }, project_id)

        if not name or not isinstance(name, str):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'name' parameter (must be non-empty string)",
                "tool": "graph_add_node",
            }, project_id)

        if properties is not None and not isinstance(properties, dict):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'properties' parameter (must be object/dict)",
                "tool": "graph_add_node",
            }, project_id)

        if vector_id is not None and (not isinstance(vector_id, int) or vector_id <= 0):
            return add_response_metadata({
                "error": "Parameter validation failed",
                "details": "Invalid 'vector_id' parameter (must be positive integer)",
                "tool": "graph_add_node",
            }, project_id)

        # Property-convention soft check (Graph-Enforcement A5, non-blocking):
        # summary should stay <= 300 chars (one-glance content; substance lives
        # in L2). Only warn — never block — to avoid data loss / surprise.
        # Scoped to vocabulary-enforced projects (tethr); others unchanged.
        if is_vocabulary_enforced(project_id) and isinstance(properties, dict):
            for prop_key in ("summary", "content"):
                value = properties.get(prop_key)
                if isinstance(value, str) and len(value) > 300:
                    logger.warning(
                        f"Property '{prop_key}' on node '{name}' exceeds 300 chars "
                        f"({len(value)}). Keep summaries short; put substance in L2."
                    )

        # Label validation:
        #  - Projects WITH a configured vocabulary (e.g. "tethr") -> hard block.
        #  - Projects WITHOUT a configured vocabulary -> warning-only (unchanged).
        if is_vocabulary_enforced(project_id):
            label_error = validate_label(project_id, label)
            if label_error:
                logger.warning(
                    f"Rejected non-vocabulary label for project '{project_id}': '{label}'"
                )
                return add_response_metadata({
                    "error": "Label not in project vocabulary",
                    "details": label_error,
                    "tool": "graph_add_node",
                }, project_id)
        elif label not in STANDARD_LABELS:
            logger.warning(f"Non-standard label used: '{label}'. Standard labels: {sorted(STANDARD_LABELS)}")

        # Auto-embedding (Graph-Enforcement A4): if the caller did not pass an
        # explicit vector_id, generate an embedding from name + summary so the
        # node is immediately visible to hybrid/graph search. On failure we fall
        # back to vector_id=None (node still gets created) and log a warning.
        # Scoped to vocabulary-enforced projects (tethr) only — other projects
        # (io, ab, njord) keep pre-enforcement behaviour: no auto-embed, no cost.
        if vector_id is None and is_vocabulary_enforced(project_id):
            generated_vector_id = await generate_node_embedding(name, properties)
            if generated_vector_id is not None:
                vector_id = generated_vector_id
            else:
                logger.warning(
                    f"Auto-embedding failed for node '{name}' — created without vector_id"
                )

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

            return add_response_metadata({
                "node_id": result["node_id"],
                "created": result["created"],
                "label": result["label"],
                "name": result["name"],
                "vector_id": vector_id,
                "status": "success",
            }, project_id)

        except Exception as db_error:
            logger.error(f"Database error in graph_add_node: {db_error}")
            return add_response_metadata({
                "error": "Database operation failed",
                "details": str(db_error),
                "tool": "graph_add_node",
            }, project_id)

    except Exception as e:
        logger.error(f"Unexpected error in graph_add_node: {e}")
        return add_response_metadata({
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "graph_add_node",
        }, project_id)
