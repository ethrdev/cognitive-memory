#!/usr/bin/env python3
"""
Backfill node embeddings (Gesamtplan A4).

For every graph node of a given project that has no `vector_id`, generate an
embedding via the same auto-embedding path used by graph_add_node
(generate_node_embedding, text = name + summary), persist it as a
graph_node_embedding carrier L2 row, and set the node's `vector_id`.

Idempotent: only nodes WHERE vector_id IS NULL are touched. A second run after a
complete first run finds nothing to do and creates no duplicate carrier rows.

Usage:
    python mcp_server/scripts/backfill_node_embeddings.py            # backfill tethr
    python mcp_server/scripts/backfill_node_embeddings.py --project tethr
    python mcp_server/scripts/backfill_node_embeddings.py --dry-run  # no writes

Exit codes:
    0 = success (all eligible nodes embedded, or nothing to do)
    1 = configuration error (no DB / OpenAI key)
    2 = completed with one or more per-node failures
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv

    for candidate in (
        project_root / "config" / ".env.development",
        project_root / ".env.development",
        project_root / ".env",
    ):
        if candidate.exists():
            load_dotenv(candidate)
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_node_embeddings")


async def _list_nodes_without_vector(project_id: str) -> list[dict]:
    """Return [{id, name, properties}] for project nodes lacking a vector_id."""
    from mcp_server.db.connection import get_connection_with_project_context

    async with get_connection_with_project_context(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id::text AS id, name, properties
            FROM nodes
            WHERE vector_id IS NULL
                AND project_id::TEXT = ANY((SELECT get_allowed_projects())::TEXT[])
            ORDER BY created_at ASC;
            """
        )
        rows = cursor.fetchall()
        return [
            {"id": r["id"], "name": r["name"], "properties": r["properties"] or {}}
            for r in rows
        ]


async def _count_vector_state(project_id: str) -> tuple[int, int]:
    """Return (total_nodes, nodes_with_vector_id) for the project."""
    from mcp_server.db.connection import get_connection_with_project_context

    async with get_connection_with_project_context(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(vector_id) AS with_vector
            FROM nodes
            WHERE project_id::TEXT = ANY((SELECT get_allowed_projects())::TEXT[]);
            """
        )
        row = cursor.fetchone()
        return int(row["total"]), int(row["with_vector"])


async def run(project_id: str, dry_run: bool) -> int:
    from mcp_server.db.graph import update_node_properties
    from mcp_server.middleware.context import clear_context, set_project_id
    from mcp_server.tools.embedding import generate_node_embedding

    set_project_id(project_id)
    try:
        total, with_vector = await _count_vector_state(project_id)
        nodes = await _list_nodes_without_vector(project_id)

        logger.info("=" * 60)
        logger.info(f"Backfill node embeddings — project '{project_id}'")
        logger.info("-" * 60)
        logger.info(f"  Nodes total:            {total}")
        logger.info(f"  Already with vector_id: {with_vector}")
        logger.info(f"  Missing vector_id:      {len(nodes)}")
        if dry_run:
            logger.info("  MODE: DRY-RUN (no writes)")
        logger.info("=" * 60)

        if not nodes:
            logger.info("Nothing to backfill — all nodes already embedded.")
            return 0

        embedded = 0
        failed = 0
        for node in nodes:
            name = node["name"]
            if dry_run:
                logger.info(f"  [dry-run] would embed: {name}")
                continue
            try:
                vector_id = await generate_node_embedding(name, node["properties"])
                if vector_id is None:
                    failed += 1
                    logger.warning(f"  [FAIL] embedding returned None: {name}")
                    continue
                await update_node_properties(node_id=node["id"], vector_id=vector_id)
                embedded += 1
                logger.info(f"  [ok] {name} -> vector_id={vector_id}")
            except Exception as e:  # noqa: BLE001 — report per-node, keep going
                failed += 1
                logger.warning(f"  [FAIL] {name}: {e}")

        logger.info("-" * 60)
        if dry_run:
            logger.info(f"DRY-RUN complete — {len(nodes)} nodes would be embedded.")
            return 0

        total_after, with_vector_after = await _count_vector_state(project_id)
        logger.info(f"Embedded:  {embedded}")
        logger.info(f"Failed:    {failed}")
        logger.info(f"Now with vector_id: {with_vector_after}/{total_after}")
        logger.info("=" * 60)
        return 2 if failed else 0
    finally:
        clear_context()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill node embeddings (Gesamtplan A4)")
    parser.add_argument("--project", default="tethr", help="project_id to backfill (default: tethr)")
    parser.add_argument("--dry-run", action="store_true", help="show what would be done, no writes")
    args = parser.parse_args()

    import os

    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL not set — aborting.")
        return 1
    if not os.getenv("OPENAI_API_KEY") and not args.dry_run:
        logger.error("OPENAI_API_KEY not set — aborting (needed for embeddings).")
        return 1

    from mcp_server.db.connection import initialize_pool_sync

    initialize_pool_sync(min_connections=1, max_connections=5)
    return asyncio.run(run(args.project, args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
