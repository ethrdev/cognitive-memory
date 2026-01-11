"""
Stats Database Operations Module

Provides database functions for counting all memory types.

Story 6.3: count_by_type MCP Tool
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


async def get_all_counts() -> dict[str, int]:
    """
    Get counts of all memory types in the database.

    Executes a single efficient query using UNION ALL to count all
    memory types in one database roundtrip.

    Returns:
        Dict with counts for each memory type:
        - graph_nodes: Count from nodes table
        - graph_edges: Count from edges table
        - l2_insights: Count from l2_insights table
        - episodes: Count from episode_memory table
        - working_memory: Count from working_memory table
        - raw_dialogues: Count from l0_raw table

    Raises:
        Exception: If database operation fails
    """
    try:
        async with get_connection() as conn:
            cursor = conn.cursor()

            # Efficient UNION ALL query - single roundtrip for all counts
            cursor.execute(
                """
                SELECT 'graph_nodes' AS type, COUNT(*) AS count FROM nodes
                UNION ALL
                SELECT 'graph_edges' AS type, COUNT(*) AS count FROM edges
                UNION ALL
                SELECT 'l2_insights' AS type, COUNT(*) AS count FROM l2_insights
                UNION ALL
                SELECT 'episodes' AS type, COUNT(*) AS count FROM episode_memory
                UNION ALL
                SELECT 'working_memory' AS type, COUNT(*) AS count FROM working_memory
                UNION ALL
                SELECT 'raw_dialogues' AS type, COUNT(*) AS count FROM l0_raw;
                """
            )

            results = cursor.fetchall()

            # Convert to dict with type as key and count as value
            counts = {}
            for row in results:
                counts[row["type"]] = int(row["count"])

            logger.debug(f"Retrieved counts: {counts}")
            return counts

    except Exception as e:
        logger.error(f"Failed to get all counts: {e}")
        raise
