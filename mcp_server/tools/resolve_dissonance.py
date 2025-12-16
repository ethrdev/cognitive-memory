"""
resolve_dissonance Tool Implementation

MCP tool for creating resolution hyperedges for detected dissonances.
Documents the development process without deleting original edges.

Story 7.5: Dissonance Engine - Resolution via Hyperedge
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from mcp_server.analysis.dissonance import resolve_dissonance
from mcp.types import Tool, TextContent

logger = logging.getLogger(__name__)

# Tool definition for MCP registration
RESOLVE_DISSONANCE_TOOL = Tool(
    name="resolve_dissonance",
    description="Erstellt eine Resolution-Hyperedge für eine erkannte Dissonanz. Dokumentiert die Entwicklung ohne Original-Edges zu löschen.",
    inputSchema={
        "type": "object",
        "properties": {
            "review_id": {  # KORRIGIERT: review_id statt dissonance_id
                "type": "string",
                "description": "UUID des NuanceReviewProposal (aus get_pending_reviews() oder dissonance_check.pending_reviews)"
            },
            "resolution_type": {
                "type": "string",
                "enum": ["EVOLUTION", "CONTRADICTION", "NUANCE"],
                "description": "Art der Resolution: EVOLUTION (ersetzt), CONTRADICTION (Widerspruch bleibt), NUANCE (Spannung akzeptiert)"
            },
            "context": {
                "type": "string",
                "description": "Beschreibung der Resolution (z.B. 'Position entwickelt sich von X zu Y')"
            },
            "resolved_by": {
                "type": "string",
                "default": "I/O",
                "description": "Wer die Resolution erstellt hat"
            }
        },
        "required": ["review_id", "resolution_type", "context"]
    }
)


async def handle_resolve_dissonance(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Handler für resolve_dissonance MCP Tool.

    Creates a resolution hyperedge for a detected dissonance. The original edges
    remain intact, preserving the full history of development.

    Args:
        arguments: Tool arguments containing review_id, resolution_type, context, resolved_by

    Returns:
        Dict with resolution details or error response
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        review_id = arguments.get("review_id")
        resolution_type = arguments.get("resolution_type")
        context = arguments.get("context")
        resolved_by = arguments.get("resolved_by", "I/O")

        # Parameter validation
        if not review_id or not isinstance(review_id, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'review_id' parameter (must be non-empty string)",
                "tool": "resolve_dissonance",
            }

        if not resolution_type or not isinstance(resolution_type, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'resolution_type' parameter (must be string)",
                "tool": "resolve_dissonance",
            }

        if not context or not isinstance(context, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'context' parameter (must be non-empty string)",
                "tool": "resolve_dissonance",
            }

        # Validate resolution_type enum
        valid_types = ["EVOLUTION", "CONTRADICTION", "NUANCE"]
        if resolution_type not in valid_types:
            return {
                "error": "Parameter validation failed",
                "details": f"Invalid 'resolution_type' parameter (must be one of: {', '.join(valid_types)})",
                "tool": "resolve_dissonance",
            }

        # Validate resolved_by
        if not isinstance(resolved_by, str):
            return {
                "error": "Parameter validation failed",
                "details": "Invalid 'resolved_by' parameter (must be string)",
                "tool": "resolve_dissonance",
            }

        # Start performance timing
        start_time = time.time()

        try:
            # Call the resolve_dissonance function
            result = resolve_dissonance(
                review_id=review_id,
                resolution_type=resolution_type,
                context=context,
                resolved_by=resolved_by
            )

            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Log success
            logger.info(
                f"resolve_dissonance completed: review_id={review_id[:8]}..., "
                f"resolution_type={resolution_type}, resolved_by={resolved_by}, "
                f"resolution_id={result['resolution_id'][:8]}..., time={execution_time:.2f}ms"
            )

            return {
                "resolution": result,
                "input_params": {
                    "review_id": review_id,
                    "resolution_type": resolution_type,
                    "context": context,
                    "resolved_by": resolved_by
                },
                "execution_time_ms": round(execution_time, 2),
                "status": "success"
            }

        except ValueError as ve:
            # Handle specific validation errors from resolve_dissonance
            logger.error(f"ValueError in resolve_dissonance: {ve}")
            return {
                "error": "Resolution failed",
                "details": str(ve),
                "tool": "resolve_dissonance",
                "error_type": "validation_error"
            }

        except Exception as re:
            # Handle other resolution errors
            logger.error(f"Resolution error: {re}")
            return {
                "error": "Resolution operation failed",
                "details": str(re),
                "tool": "resolve_dissonance",
                "error_type": "resolution_error"
            }

    except Exception as e:
        logger.error(f"Unexpected error in resolve_dissonance handler: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "resolve_dissonance",
            "error_type": "handler_error"
        }