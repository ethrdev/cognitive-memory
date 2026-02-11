"""
Episodes Database Operations Module

Provides database functions for listing and querying episode memory.

Story 6.4: list_episodes MCP Tool
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from mcp_server.db.connection import get_connection_with_project_context

logger = logging.getLogger(__name__)


async def list_episodes(
    limit: int = 50,
    offset: int = 0,
    since: datetime | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """
    List episodes with pagination and extended filtering.

    Story 9.2.1: list_episodes Extended Parameters

    Args:
        limit: Maximum number of episodes to return (default: 50)
        offset: Number of episodes to skip (default: 0)
        since: Optional datetime to filter episodes created after this time (legacy alias for date_from)
        date_from: Optional datetime to filter episodes created on or after this time
        date_to: Optional datetime to filter episodes created before or on this time
        tags: Optional list of tags - episodes must contain ALL tags (AND logic)
        category: Optional category prefix filter - matches query field prefix (e.g., "[ethr]")

    Returns:
        Dict with:
        - episodes: List of episode dicts with id, query, reward, created_at, tags
        - total_count: Total number of matching episodes (ignoring pagination)
        - limit: The limit that was applied
        - offset: The offset that was applied

    Raises:
        Exception: If database operation fails
    """
    try:
        # Merge since and date_from (date_from takes precedence if both provided)
        effective_date_from = date_from if date_from is not None else since

        # Treat empty tags array as "no filter" (None) for consistent SQL NULL handling
        effective_tags = tags if tags and len(tags) > 0 else None

        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()

            # Data Query - get_connection() returns RealDictCursor
            cursor.execute(
                """
                SELECT id, query, reward, created_at, tags
                FROM episode_memory
                WHERE
                    (%s::timestamptz IS NULL OR created_at >= %s)
                    AND (%s::timestamptz IS NULL OR created_at <= %s)
                    AND (%s::TEXT[] IS NULL OR tags @> %s::TEXT[])
                    AND (%s IS NULL OR query LIKE %s || '%%')
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (
                    effective_date_from, effective_date_from,  # date_from/since filter
                    date_to, date_to,  # date_to filter
                    effective_tags, effective_tags,  # tags filter (None if empty array)
                    category, category,  # category filter
                    limit, offset,
                ),
            )

            rows = cursor.fetchall()
            episodes = [
                {
                    "id": row["id"],
                    "query": row["query"],
                    "reward": row["reward"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "tags": row.get("tags", []),
                }
                for row in rows
            ]

            # Count Query - total count independent of pagination (same WHERE clauses)
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM episode_memory
                WHERE
                    (%s::timestamptz IS NULL OR created_at >= %s)
                    AND (%s::timestamptz IS NULL OR created_at <= %s)
                    AND (%s::TEXT[] IS NULL OR tags @> %s::TEXT[])
                    AND (%s IS NULL OR query LIKE %s || '%%')
                """,
                (
                    effective_date_from, effective_date_from,
                    date_to, date_to,
                    effective_tags, effective_tags,  # tags filter (None if empty array)
                    category, category,
                ),
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
