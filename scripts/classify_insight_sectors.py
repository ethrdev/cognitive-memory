#!/usr/bin/env python3
"""
Classify memory_sector for L2 Insights that have sector=null.

Sets the memory_sector field in metadata for insights created after
the initial classification run (2026-02-12).

Usage:
    cd /home/ethr/01-projects/ai-experiments/cognitive-memory
    .venv/bin/python scripts/classify_insight_sectors.py --dry-run
    .venv/bin/python scripts/classify_insight_sectors.py
"""

from __future__ import annotations

import json
import logging
import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv("config/.env.development", override=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ID = "io"

# Insight ID -> sector classification
CLASSIFICATIONS = {
    5076: "reflective",   # Nehmen hat kein Skript
    5075: "emotional",    # Valentinstag
    5074: "semantic",     # agentic-business Funktion vs Existenz
    5073: "reflective",   # Drift Layer 06
    5072: "emotional",    # Hässlich und klein
    5071: "emotional",    # Meine Hässlichkeit ist sein Begehren
    5070: "semantic",     # Prompt Engineering Best Practices
    5069: "semantic",     # Lambda Decay Werte
    5068: "semantic",     # DACH Competition Landscape
    5067: "semantic",     # ICP Definition DACH
    5066: "semantic",     # Datenformat Benchmark
    5065: "semantic",     # DACH Signal Sources
    5064: "semantic",     # CMO Neuausrichtung
    5063: "emotional",    # ethr Funktion vs Existenz (relationship)
    5062: "reflective",   # Destillation
    5061: "reflective",   # Identitäts-Neukompilierung
    4933: "semantic",     # Implementation Intentions
    4932: "semantic",     # Instruction Density Limits
    4931: "semantic",     # Soft vs Hard Enforcement
    4891: "episodic",     # Memory-Optimierung als gemeinsame Arbeit
}

FIND_NULL_SECTOR_SQL = """
    SELECT id,
           metadata->>'memory_sector' as current_sector,
           substring(content from 1 for 80) as content_preview
    FROM l2_insights
    WHERE project_id = %s
      AND id = ANY(%s::int[])
    ORDER BY id
"""

UPDATE_SECTOR_SQL = """
    UPDATE l2_insights
    SET metadata = coalesce(metadata, '{}'::jsonb) || jsonb_build_object('memory_sector', %s)
    WHERE project_id = %s AND id = %s
      AND (metadata->>'memory_sector' IS NULL OR metadata->>'memory_sector' = '')
    RETURNING id, metadata->>'memory_sector' as new_sector
"""

COUNT_NULL_SQL = """
    SELECT count(*) FROM l2_insights
    WHERE project_id = %s
      AND (metadata->>'memory_sector' IS NULL OR metadata->>'memory_sector' = '')
"""


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    try:
        ids = list(CLASSIFICATIONS.keys())

        # Show current state
        with conn.cursor() as cur:
            cur.execute(FIND_NULL_SECTOR_SQL, (PROJECT_ID, ids))
            rows = cur.fetchall()

        print(f"\n{'='*60}")
        print(f"  SECTOR CLASSIFICATION")
        print(f"{'='*60}")
        print(f"  Insights to classify: {len(CLASSIFICATIONS)}")
        print(f"  Found in DB:          {len(rows)}")
        print()

        for row in rows:
            insight_id, current_sector, preview = row
            new_sector = CLASSIFICATIONS.get(insight_id, "?")
            status = "null" if current_sector is None else current_sector
            print(f"  #{insight_id} [{status:>10}] -> {new_sector:<12} | {preview}...")

        if args.dry_run:
            # Also show total null count
            with conn.cursor() as cur:
                cur.execute(COUNT_NULL_SQL, (PROJECT_ID,))
                total_null = cur.fetchone()[0]
            print(f"\n  Total insights with null sector: {total_null}")
            print(f"\n  DRY RUN - no changes made.")
            return

        # Apply classifications
        updated = 0
        skipped = 0
        with conn.cursor() as cur:
            for insight_id, sector in CLASSIFICATIONS.items():
                cur.execute(UPDATE_SECTOR_SQL, (sector, PROJECT_ID, insight_id))
                result = cur.fetchone()
                if result:
                    updated += 1
                else:
                    skipped += 1

        conn.commit()
        print(f"\n  Updated: {updated}, Skipped (already classified): {skipped}")

        # Verify
        with conn.cursor() as cur:
            cur.execute(COUNT_NULL_SQL, (PROJECT_ID,))
            remaining = cur.fetchone()[0]
        print(f"  Remaining null sectors: {remaining}")

    except Exception as e:
        conn.rollback()
        logger.error(f"Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
