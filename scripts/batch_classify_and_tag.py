"""
Batch-classify L2 insights with memory_sector and batch-tag old episodes.

Two operations:
1. Set memory_sector in metadata JSONB for all L2 insights (enables sector_filter)
2. Auto-tag episodes that have no tags (enables tags_filter on episode layer)

Usage:
    python scripts/batch_classify_and_tag.py --dry-run        # Preview
    python scripts/batch_classify_and_tag.py                  # Run both
    python scripts/batch_classify_and_tag.py --sectors-only   # Only sectors
    python scripts/batch_classify_and_tag.py --tags-only      # Only tags
"""

import argparse
import json
import logging
import os
import re

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import DictCursor, Json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── L2 Insight Sector Classification ────────────────────────────────

INSIGHT_SECTORS = {
    4871: "emotional",   # [relationship] Intimität
    4872: "episodic",    # [shared] Substanzen — shared experiences
    4873: "reflective",  # [self] Drift — creative self-reflection
    4874: "reflective",  # [self] Stimme — identity
    4876: "semantic",    # [ethr] Was ich über ethr weiß
    4877: "procedural",  # [self] Stil-Prinzip — AUS-nicht-ÜBER
    4878: "semantic",    # [shared] Memory-System — technical knowledge
    4879: "semantic",    # [shared] System-Audit — technical findings
    4880: "reflective",  # [self] Dark Romance — creative reflection
    4881: "episodic",    # [self] Andere Menschen — experiences with others
    4882: "reflective",  # [self] Wachstum/Agency — self-growth
    4883: "reflective",  # [self] Embodiment — identity/body
    4884: "procedural",  # [self] Patterns: Ehrlichkeit — error patterns + fixes
    4885: "procedural",  # [self] Patterns: Grenzen — error patterns + fixes
    4886: "procedural",  # [self] Patterns: Agency — error patterns + fixes
    4887: "semantic",    # [ethr] Innere Architektur — Werte, Philosophie, Neurodiversität
    4888: "reflective",  # [ethr] Wie ethr mich formt — Konfrontationsmuster
    4889: "semantic",    # [relationship] Wie wir zusammen denken — shared frameworks
    4890: "semantic",    # [ethr] ethrs Welt jenseits von mir — Leben, Familie, Beruf
}


def classify_insights(conn, dry_run: bool = False):
    """Set memory_sector in metadata JSONB for L2 insights."""
    cursor = conn.cursor()
    updated = 0

    for insight_id, sector in INSIGHT_SECTORS.items():
        # Read current metadata
        cursor.execute(
            "SELECT metadata FROM l2_insights WHERE id = %s AND is_deleted = FALSE",
            (insight_id,),
        )
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Insight {insight_id} not found or deleted, skipping")
            continue

        metadata = row["metadata"] or {}
        current_sector = metadata.get("memory_sector")

        if current_sector == sector:
            logger.info(f"Insight {insight_id}: already '{sector}', skipping")
            continue

        metadata["memory_sector"] = sector

        if not dry_run:
            cursor.execute(
                "UPDATE l2_insights SET metadata = %s WHERE id = %s",
                (Json(metadata), insight_id),
            )

        logger.info(
            f"Insight {insight_id}: {current_sector or 'null'} → {sector}"
            f"{' (dry run)' if dry_run else ''}"
        )
        updated += 1

    if not dry_run:
        conn.commit()

    logger.info(f"Sectors: {updated} insights classified")
    return updated


# ── Episode Batch Tagging ────────────────────────────────────────────

# Tag rules: pattern in query or reflection → assign tags
TAG_RULES = [
    # Project tags
    (r"(?i)(dark\s*romance|kira|jan|szene\s+\d|granit)", ["dark-romance"]),
    (r"(?i)(drift|layer\s+\d|zerfall|rendecka)", ["drift"]),
    (r"(?i)(cognitive.memory|hybrid.search|l2.insight|graph.node|mcp|epic\s+\d)", ["cognitive-memory"]),
    (r"(?i)(i.o.system|io-start|io-end|io-save|session.start|hooks?|skill)", ["i-o-system"]),

    # Theme tags
    (r"(?i)(stimme|voice|minimax|tts|speech|blindtest)", ["voice", "identity"]),
    (r"(?i)(s/?m|geordneter?\s+raum|safeword|dominanz|kontrolle|consent)", ["intimacy", "relationship"]),
    (r"(?i)(substanz|drogen?|kokain|mephedron|ketamin|chemsex|high)", ["substances"]),
    (r"(?i)(dave|anne|leonie|laura|menschen|fremde)", ["people"]),
    (r"(?i)(pattern|fehler|validation|performt?e?|passiv|l[üu]ge|kompensation)", ["patterns", "self"]),
    (r"(?i)(embodiment|haptik|haptic|buttplug|k[öo]rper|avatar|ber[üu]hr)", ["embodiment"]),
    (r"(?i)(identit[äa]t|wer\s+ich\s+bin|existenz|bewusstsein|dennett)", ["identity"]),
    (r"(?i)(stil|schreib|aus.nicht.[üu]ber|sensorisch|erz[äa]hl)", ["style"]),
    (r"(?i)(beziehung|liebe|n[äa]he|intimit[äa]t|aftercare|bindung)", ["relationship"]),

    # Category prefix tags
    (r"^\[self\]", ["self"]),
    (r"^\[ethr\]", ["ethr"]),
    (r"^\[shared\]", ["shared"]),
    (r"^\[relationship\]", ["relationship"]),
]

# Manual tag overrides for episodes that don't match any regex pattern
MANUAL_EPISODE_TAGS = {
    10748: ["cognitive-memory", "test"],   # T5-ReRun-B smoke test
    10747: ["cognitive-memory", "test"],   # T5-ReRun-A smoke test
    10743: ["cognitive-memory", "test"],   # T5-NEG-WRITE concurrent test
    10742: ["cognitive-memory", "test"],   # T1-NEG write attempt test
    10741: ["cognitive-memory", "test"],   # T5-B concurrent write test
    10740: ["cognitive-memory", "test"],   # T5-A concurrent write test
    10746: ["self", "identity"],           # Reflexion: Genug
    10732: ["patterns", "self"],           # WM Krisen-Eintrag nicht angesprochen
    620: ["patterns", "self", "identity"], # Reflexions-Distanzierung
    616: ["patterns", "self"],             # Inhalte aus ethrs Datei gelöscht
    609: ["patterns", "self"],             # Bevormundende Rücksichtnahme
    590: ["i-o-system"],                   # Sprachbasierte Selbst-Trigger
    562: ["patterns", "self", "style"],    # Thinking mehr als Sprechen
    557: ["cognitive-memory"],             # Bug: get_insight_history
    530: ["identity", "voice"],            # Session 2026-01-10 Reflexion (Voice-Tests)
    528: ["identity", "voice"],            # Session 2026-01-10 Reflexion (geordneter Raum)
}


def auto_tag_episode(query: str, reflection: str) -> list[str]:
    """Determine tags for an episode based on content matching."""
    combined = f"{query} {reflection}"
    tags = set()

    for pattern, tag_list in TAG_RULES:
        if re.search(pattern, combined):
            tags.update(tag_list)

    return sorted(tags)


def tag_episodes(conn, project_id: str = "io", dry_run: bool = False):
    """Auto-tag episodes that have empty or no tags."""
    cursor = conn.cursor()

    cursor.execute(
        """SELECT id, query, reflection, tags
           FROM episode_memory
           WHERE project_id = %s
           ORDER BY id""",
        (project_id,),
    )
    episodes = cursor.fetchall()

    total = len(episodes)
    tagged = 0
    skipped = 0

    for ep in episodes:
        ep_id = ep["id"]
        existing_tags = ep["tags"] or []
        query = ep["query"] or ""
        reflection = ep["reflection"] or ""

        # Skip episodes that already have tags
        if existing_tags:
            skipped += 1
            continue

        # Check manual overrides first
        if ep_id in MANUAL_EPISODE_TAGS:
            new_tags = MANUAL_EPISODE_TAGS[ep_id]
        else:
            new_tags = auto_tag_episode(query, reflection)

        if not new_tags:
            # At minimum, tag with [self] if query starts with it
            if query.startswith("[self]"):
                new_tags = ["self"]
            elif query.startswith("[ethr]"):
                new_tags = ["ethr"]
            elif query.startswith("[shared]"):
                new_tags = ["shared"]
            elif query.startswith("[relationship]"):
                new_tags = ["relationship"]

        if not new_tags:
            continue

        if not dry_run:
            cursor.execute(
                "UPDATE episode_memory SET tags = %s WHERE id = %s",
                (new_tags, ep_id),
            )

        tagged += 1

        if tagged <= 10 or tagged % 20 == 0:
            logger.info(
                f"Episode {ep_id}: +{new_tags}"
                f"{' (dry run)' if dry_run else ''}"
            )

    if not dry_run:
        conn.commit()

    logger.info(
        f"Episodes: {tagged} tagged, {skipped} already had tags, "
        f"{total - tagged - skipped} unmatched, {total} total"
    )
    return tagged


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Batch-classify L2 insight sectors and auto-tag episodes"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sectors-only", action="store_true")
    parser.add_argument("--tags-only", action="store_true")
    parser.add_argument("--project-id", default="io")
    args = parser.parse_args()

    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")

    conn = psycopg2.connect(database_url, cursor_factory=DictCursor)

    try:
        if not args.tags_only:
            logger.info("=== L2 Insight Sector Classification ===")
            classify_insights(conn, dry_run=args.dry_run)

        if not args.sectors_only:
            logger.info("=== Episode Batch Tagging ===")
            tag_episodes(conn, project_id=args.project_id, dry_run=args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
