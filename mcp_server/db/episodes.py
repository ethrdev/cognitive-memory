"""
Episodes Database Operations Module

Provides database functions for listing and querying episode memory.

Story 6.4: list_episodes MCP Tool
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


def list_episodes(
    limit: int = 50,
    offset: int = 0,
    since: datetime | None = None,
) -> dict[str, Any]:
    """
    List episodes with pagination and optional time filter.

    Args:
        limit: Maximum number of episodes to return (default: 50)
        offset: Number of episodes to skip (default: 0)
        since: Optional datetime to filter episodes created after this time

    Returns:
        Dict with:
        - episodes: List of episode dicts with id, query, reward, created_at
        - total_count: Total number of matching episodes (ignoring pagination)
        - limit: The limit that was applied
        - offset: The offset that was applied

    Raises:
        Exception: If database operation fails
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Data Query - get_connection() returns RealDictCursor
            cursor.execute(
                """
                SELECT id, query, reward, created_at
                FROM episode_memory
                WHERE (%s::timestamptz IS NULL OR created_at >= %s)
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (since, since, limit, offset),
            )

            rows = cursor.fetchall()
            episodes = [
                {
                    "id": row["id"],
                    "query": row["query"],
                    "reward": row["reward"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in rows
            ]

            # Count Query - total count independent of pagination
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM episode_memory
                WHERE (%s::timestamptz IS NULL OR created_at >= %s)
                """,
                (since, since),
            )

            total_count = cursor.fetchone()["count"]

            logger.debug(f"Listed {len(episodes)} episodes (total: {total_count})")

            return {
                "episodes": episodes,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            }

    except Exception as e:
        logger.error(f"Failed to list episodes: {e}")
        raise
