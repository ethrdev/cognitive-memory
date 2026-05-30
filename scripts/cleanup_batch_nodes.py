#!/usr/bin/env python3
"""
Cleanup Script: Remove batch-imported graph nodes from January 2026.

These 90 nodes were batch-imported on 2026-01-26 from episodes. They have
minimal properties (reward, category, created_at, episode_id) and no
description or content. All are connected to I/O via EXPERIENCED edges.
All have access_count: 0.

Analysis by I/O (2026-02-16):
- 45 positive, 29 error, 16 neutral
- 0 unique concepts not already in L2 Insights or handcrafted nodes
- vector_id migration completed (4884 → Service-Reflex)
- No cross-edges to handcrafted nodes

Usage:
    cd /home/ethr/01-projects/ai-experiments/cognitive-memory
    python scripts/cleanup_batch_nodes.py --dry-run     # Preview what will be deleted
    python scripts/cleanup_batch_nodes.py --backup       # Export backup JSON, then delete
    python scripts/cleanup_batch_nodes.py                # Delete directly
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime

import psycopg2
from dotenv import load_dotenv

# Load environment
load_dotenv("config/.env.development", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Filter criteria for batch-imported nodes
BATCH_DATE = "2026-01-26"
PROJECT_ID = "io"

# SQL to identify batch nodes
IDENTIFY_SQL = """
    SELECT id, name, properties, vector_id, created_at
    FROM nodes
    WHERE project_id = %s
      AND created_at::date = %s
      AND properties ? 'episode_id'
      AND NOT (properties ? 'description' OR properties ? 'content')
    ORDER BY created_at
"""

# SQL to find edges connected to batch nodes
EDGES_SQL = """
    SELECT e.id, e.source_id, e.target_id, e.relation, e.weight,
           s.name as source_name, t.name as target_name
    FROM edges e
    JOIN nodes s ON e.source_id = s.id
    JOIN nodes t ON e.target_id = t.id
    WHERE e.project_id = %s
      AND (e.source_id = ANY(%s::uuid[]) OR e.target_id = ANY(%s::uuid[]))
    ORDER BY e.created_at
"""

# SQL to delete nodes (edges cascade)
DELETE_NODES_SQL = """
    DELETE FROM nodes
    WHERE project_id = %s
      AND id = ANY(%s::uuid[])
    RETURNING id, name
"""


def get_connection():
    """Get database connection."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)
    return psycopg2.connect(db_url)


def identify_batch_nodes(conn) -> list[dict]:
    """Find all batch-imported nodes matching criteria."""
    with conn.cursor() as cur:
        cur.execute(IDENTIFY_SQL, (PROJECT_ID, BATCH_DATE))
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    return rows


def find_connected_edges(conn, node_ids: list[str]) -> list[dict]:
    """Find all edges connected to the given nodes."""
    with conn.cursor() as cur:
        cur.execute(EDGES_SQL, (PROJECT_ID, node_ids, node_ids))
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    return rows


def delete_nodes(conn, node_ids: list[str]) -> list[dict]:
    """Delete nodes (edges cascade automatically)."""
    with conn.cursor() as cur:
        cur.execute(DELETE_NODES_SQL, (PROJECT_ID, node_ids))
        columns = [desc[0] for desc in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    return rows


def export_backup(nodes: list[dict], edges: list[dict], filepath: str):
    """Export nodes and edges as JSON backup."""
    backup = {
        "exported_at": datetime.now().isoformat(),
        "reason": "Batch-imported episode-mirror nodes cleanup",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": [{
            "id": str(n["id"]),
            "name": n["name"],
            "properties": n["properties"],
            "vector_id": n["vector_id"],
            "created_at": n["created_at"].isoformat() if n["created_at"] else None,
        } for n in nodes],
        "edges": [{
            "id": str(e["id"]),
            "source_id": str(e["source_id"]),
            "target_id": str(e["target_id"]),
            "source_name": e["source_name"],
            "target_name": e["target_name"],
            "relation": e["relation"],
            "weight": e["weight"],
        } for e in edges],
    }
    with open(filepath, "w") as f:
        json.dump(backup, f, indent=2, ensure_ascii=False)
    logger.info(f"Backup exported to {filepath}")


def print_summary(nodes: list[dict], edges: list[dict]):
    """Print summary of what will be deleted."""
    categories = {"positive": 0, "error": 0, "neutral": 0, "unknown": 0}
    for n in nodes:
        cat = n["properties"].get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1

    vector_id_count = sum(1 for n in nodes if n["vector_id"] is not None)

    print(f"\n{'='*60}")
    print(f"  BATCH NODE CLEANUP SUMMARY")
    print(f"{'='*60}")
    print(f"  Nodes to delete:  {len(nodes)}")
    print(f"  Edges to cascade: {len(edges)}")
    print(f"  Categories:       {categories}")
    print(f"  With vector_id:   {vector_id_count}")
    print(f"{'='*60}\n")

    # Show first 10 node names
    print("  Sample nodes:")
    for n in nodes[:10]:
        props = n["properties"]
        cat = props.get("category", "?")
        eid = props.get("episode_id", "?")
        vid = f" [vector_id:{n['vector_id']}]" if n["vector_id"] else ""
        print(f"    [{cat:>8}] ep:{eid} | {n['name']}{vid}")
    if len(nodes) > 10:
        print(f"    ... and {len(nodes) - 10} more")
    print()


def main():
    parser = argparse.ArgumentParser(description="Cleanup batch-imported graph nodes")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without deleting")
    parser.add_argument("--backup", action="store_true",
                        help="Export JSON backup before deleting")
    args = parser.parse_args()

    conn = get_connection()

    try:
        # Step 1: Identify batch nodes
        logger.info("Identifying batch-imported nodes...")
        nodes = identify_batch_nodes(conn)
        if not nodes:
            logger.info("No batch nodes found. Nothing to do.")
            return

        node_ids = [n["id"] for n in nodes]

        # Step 2: Find connected edges
        logger.info("Finding connected edges...")
        edges = find_connected_edges(conn, node_ids)

        # Step 3: Print summary
        print_summary(nodes, edges)

        if args.dry_run:
            logger.info("DRY RUN — no changes made.")
            return

        # Step 4: Backup if requested
        if args.backup:
            backup_path = f"scripts/backup_batch_nodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            export_backup(nodes, edges, backup_path)

        # Step 5: Delete
        logger.info(f"Deleting {len(nodes)} nodes (edges cascade)...")
        deleted = delete_nodes(conn, node_ids)
        conn.commit()
        logger.info(f"Deleted {len(deleted)} nodes successfully.")

        # Step 6: Verify
        remaining = identify_batch_nodes(conn)
        logger.info(f"Verification: {len(remaining)} batch nodes remaining (expected: 0)")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
