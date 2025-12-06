"""
L2 Insights Database Operations Module

Provides database functions for retrieving L2 insights by ID.

Story 6.5: get_insight_by_id MCP Tool
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


def get_insight_by_id(insight_id: int) -> dict[str, Any] | None:
    """
    Get an L2 insight by its ID.

    Args:
        insight_id: The ID of the insight to retrieve

    Returns:
        Dict with insight data (id, content, source_ids, metadata, created_at)
        if found, None if not found.
        Note: embedding is NOT returned (too large for response).

    Raises:
        Exception: If database operation fails
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Simple SELECT by ID - no embedding (too large)
            cursor.execute(
                """
                SELECT id, content, source_ids, metadata, created_at
                FROM l2_insights
                WHERE id = %s
                """,
                (insight_id,),
            )

            row = cursor.fetchone()

            if row is None:
                logger.debug(f"Insight not found: id={insight_id}")
                return None

            # Convert to dict with ISO 8601 datetime
            result = {
                "id": row["id"],
                "content": row["content"],
                "source_ids": row["source_ids"],
                "metadata": row["metadata"] or {},  # NULL -> empty dict
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }

            logger.debug(f"Retrieved insight: id={insight_id}")
            return result

    except Exception as e:
        logger.error(f"Failed to get insight by id: {e}")
        raise
