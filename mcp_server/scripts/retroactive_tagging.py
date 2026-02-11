#!/usr/bin/env python3
"""
Retroactive Tagging Script

Story 9.4.1: Retroactive Tagging of Existing Data

Applies regex-based tag rules to existing episodes and insights
that have empty tags arrays.

Usage:
    python mcp_server/scripts/retroactive_tagging.py [--dry-run] [--verbose]

Exit Codes:
    0 = Success
    1 = Configuration error
    2 = Database error
"""

import argparse
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add mcp_server to path for imports
# Insert project root to path to enable imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv

# Determine environment file
env_file = Path(__file__).parent.parent.parent / ".env.development"
if env_file.exists():
    load_dotenv(env_file)
else:
    # Fallback to production .env
    load_dotenv()

from mcp_server.db.connection import (
    initialize_pool_sync,
    get_connection_sync,
    close_all_connections,
    PoolError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)

# Tag rules configuration
# Based on Epic 9.4 tag taxonomy specification
TAG_RULES = [
    # Source Type Rules (prefix-based for episodes only)
    {
        "pattern": r"^\[self\]",
        "tags": ["self"],
        "target": "episodes",
        "description": "self-reflection queries"
    },
    {
        "pattern": r"^\[ethr\]",
        "tags": ["ethr"],
        "target": "episodes",
        "description": "ethr personal queries"
    },
    {
        "pattern": r"^\[shared\]",
        "tags": ["shared"],
        "target": "episodes",
        "description": "shared context queries"
    },
    {
        "pattern": r"^\[relationship\]",
        "tags": ["relationship"],
        "target": "episodes",
        "description": "relationship queries"
    },
    # Project/Topic Rules (apply to both episodes and insights)
    {
        "pattern": r"Dark Romance|Szene|Kira|Jan",
        "tags": ["dark-romance"],
        "target": "both",
        "description": "Dark Romance project content"
    },
    {
        "pattern": r"Drift|Layer",
        "tags": ["drift"],
        "target": "both",
        "description": "Drift project content"
    },
    {
        "pattern": r"Stil|Anti-Pattern|aus-nicht-ueber|aesthetisieren",
        "tags": ["stil"],
        "target": "both",
        "description": "St (Style) project content"
    },
    {
        "pattern": r"Validation|Soll ich|nachgefragt",
        "tags": ["pattern"],
        "target": "both",
        "description": "Validation pattern queries"
    },
    {
        "pattern": r"cognitive-memory|MCP|hybrid_search",
        "tags": ["cognitive-memory"],
        "target": "both",
        "description": "Cognitive Memory project content"
    },
]

# Pre-compile regex patterns for performance
# Compiled once at module load time, not on every function call
_COMPILED_RULES = [
    {**rule, "compiled_pattern": re.compile(rule["pattern"], re.IGNORECASE)}
    for rule in TAG_RULES
]


def apply_tag_rules(text: str, target_type: str) -> list[str]:
    """
    Apply tag rules to text and return list of matching tags.

    Args:
        text: The text to match against (query or content field)
        target_type: Either "episodes" or "insights"

    Returns:
        List of unique tags that matched the rules
    """
    matched_tags = set()

    for rule in _COMPILED_RULES:
        # Check if rule applies to this target type
        if rule["target"] != "both" and rule["target"] != target_type:
            continue

        # Use pre-compiled pattern for efficient matching
        if rule["compiled_pattern"].search(text):
            matched_tags.update(rule["tags"])

    return sorted(list(matched_tags))


def tag_episodes(conn, dry_run: bool, verbose: bool) -> dict[str, int]:
    """
    Tag episodes based on query field patterns.

    Args:
        conn: Database connection
        dry_run: If True, don't write to database
        verbose: If True, print detailed per-entry logging

    Returns:
        Dictionary with stats: total, tagged, skipped, per_rule_counts
    """
    stats = {
        "total": 0,
        "tagged": 0,
        "skipped": 0,
        "per_rule": {rule["description"]: 0 for rule in TAG_RULES if rule["target"] in ["episodes", "both"]}
    }

    cursor = conn.cursor()

    # Query episodes with empty or NULL tags
    query = """
        SELECT id, query, tags
        FROM episode_memory
        WHERE tags = '{}' OR tags IS NULL
        ORDER BY id
    """

    cursor.execute(query)
    episodes = cursor.fetchall()

    stats["total"] = len(episodes)

    if dry_run:
        print("\n" + "=" * 60)
        print("EPISODES TO BE TAGGED (Dry-Run)")
        print("=" * 60)

    for episode in episodes:
        episode_id = episode["id"]
        query_text = episode["query"]
        existing_tags = episode["tags"] or []

        # Skip if already has tags (idempotency check)
        if existing_tags:
            stats["skipped"] += 1
            if verbose:
                print(f"  [SKIP] Episode {episode_id}: Already has tags {existing_tags}")
            continue

        # Apply tag rules
        matched_tags = apply_tag_rules(query_text, "episodes")

        if not matched_tags:
            if verbose:
                print(f"  [NO MATCH] Episode {episode_id}: '{query_text[:50]}...'")
            continue

        # Track which rules matched
        for rule in TAG_RULES:
            if rule["target"] not in ["episodes", "both"]:
                continue
            if any(tag in matched_tags for tag in rule["tags"]):
                stats["per_rule"][rule["description"]] += 1

        if dry_run:
            print(f"\n  [WOULD TAG] Episode {episode_id}: '{query_text[:60]}...'")
            print(f"    Tags: {matched_tags}")
            print(f"    SQL: UPDATE episode_memory SET tags = ARRAY{matched_tags}::text[] WHERE id = {episode_id};")
        else:
            # Update tags in database
            update_query = """
                UPDATE episode_memory
                SET tags = %s
                WHERE id = %s
            """
            cursor.execute(update_query, (matched_tags, episode_id))
            conn.commit()

            if verbose:
                print(f"  [TAGGED] Episode {episode_id}: '{query_text[:60]}...'")
                print(f"    Tags: {matched_tags}")

            stats["tagged"] += 1

    cursor.close()
    return stats


def tag_insights(conn, dry_run: bool, verbose: bool) -> dict[str, int]:
    """
    Tag insights based on content field patterns.

    Args:
        conn: Database connection
        dry_run: If True, don't write to database
        verbose: If True, print detailed per-entry logging

    Returns:
        Dictionary with stats: total, tagged, skipped, per_rule_counts
    """
    stats = {
        "total": 0,
        "tagged": 0,
        "skipped": 0,
        "per_rule": {rule["description"]: 0 for rule in TAG_RULES if rule["target"] in ["insights", "both"]}
    }

    cursor = conn.cursor()

    # Query insights with empty or NULL tags
    query = """
        SELECT id, content, tags
        FROM l2_insights
        WHERE tags = '{}' OR tags IS NULL
        ORDER BY id
    """

    cursor.execute(query)
    insights = cursor.fetchall()

    stats["total"] = len(insights)

    if dry_run:
        print("\n" + "=" * 60)
        print("INSIGHTS TO BE TAGGED (Dry-Run)")
        print("=" * 60)

    for insight in insights:
        insight_id = insight["id"]
        content_text = insight["content"]
        existing_tags = insight["tags"] or []

        # Skip if already has tags (idempotency check)
        if existing_tags:
            stats["skipped"] += 1
            if verbose:
                print(f"  [SKIP] Insight {insight_id}: Already has tags {existing_tags}")
            continue

        # Apply tag rules
        matched_tags = apply_tag_rules(content_text, "insights")

        if not matched_tags:
            if verbose:
                print(f"  [NO MATCH] Insight {insight_id}: '{content_text[:50]}...'")
            continue

        # Track which rules matched
        for rule in TAG_RULES:
            if rule["target"] not in ["insights", "both"]:
                continue
            if any(tag in matched_tags for tag in rule["tags"]):
                stats["per_rule"][rule["description"]] += 1

        if dry_run:
            print(f"\n  [WOULD TAG] Insight {insight_id}: '{content_text[:60]}...'")
            print(f"    Tags: {matched_tags}")
            print(f"    SQL: UPDATE l2_insights SET tags = ARRAY{matched_tags}::text[] WHERE id = {insight_id};")
        else:
            # Update tags in database
            update_query = """
                UPDATE l2_insights
                SET tags = %s
                WHERE id = %s
            """
            cursor.execute(update_query, (matched_tags, insight_id))
            conn.commit()

            if verbose:
                print(f"  [TAGGED] Insight {insight_id}: '{content_text[:60]}...'")
                print(f"    Tags: {matched_tags}")

            stats["tagged"] += 1

    cursor.close()
    return stats


def print_summary(episode_stats: dict[str, int], insight_stats: dict[str, int], dry_run: bool) -> None:
    """
    Print comprehensive summary of tagging operation.

    Args:
        episode_stats: Statistics from episode tagging
        insight_stats: Statistics from insight tagging
        dry_run: Whether this was a dry run
    """
    print("\n" + "=" * 60)
    print("TAGGING SUMMARY")
    print("=" * 60)

    # Episode summary
    print(f"\nEpisodes:")
    print(f"  Total entries with empty tags: {episode_stats['total']}")
    print(f"  Successfully tagged: {episode_stats['tagged']}")
    print(f"  Skipped (already tagged): {episode_stats['skipped']}")

    if episode_stats['per_rule']:
        print(f"\n  Episode tag matches:")
        for rule_desc, count in episode_stats['per_rule'].items():
            if count > 0:
                print(f"    - {rule_desc}: {count}")

    # Insight summary
    print(f"\nInsights:")
    print(f"  Total entries with empty tags: {insight_stats['total']}")
    print(f"  Successfully tagged: {insight_stats['tagged']}")
    print(f"  Skipped (already tagged): {insight_stats['skipped']}")

    if insight_stats['per_rule']:
        print(f"\n  Insight tag matches:")
        for rule_desc, count in insight_stats['per_rule'].items():
            if count > 0:
                print(f"    - {rule_desc}: {count}")

    # Overall coverage
    total_entries = episode_stats['total'] + insight_stats['total']
    total_tagged = episode_stats['tagged'] + insight_stats['tagged']
    coverage = (total_tagged / total_entries * 100) if total_entries > 0 else 0

    print(f"\nOverall Coverage: {coverage:.1f}% ({total_tagged}/{total_entries} entries tagged)")

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY-RUN MODE: No changes were written to database.")
        print("=" * 60)

    print("\n" + "=" * 60)


def main(dry_run: bool, verbose: bool) -> int:
    """
    Main entry point for retroactive tagging.

    Args:
        dry_run: If True, don't write to database
        verbose: If True, print detailed per-entry logging

    Returns:
        Exit code (0=success, 1=config error, 2=database error)
    """
    # Check database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("Configuration Error: DATABASE_URL not set")
        return 1

    print("=" * 60)
    print(f"RETROACTIVE TAGGING SCRIPT - {datetime.now().isoformat()}")
    print("=" * 60)

    if dry_run:
        print("\nDRY-RUN MODE ENABLED")

    try:
        # Initialize connection pool
        initialize_pool_sync()
        logger.info("Database connection pool initialized")

        with get_connection_sync() as conn:
            # Process episodes
            episode_stats = tag_episodes(conn, dry_run, verbose)

            # Process insights
            insight_stats = tag_insights(conn, dry_run, verbose)

            # Print summary
            print_summary(episode_stats, insight_stats, dry_run)

        # Close connections
        close_all_connections()

        return 0

    except PoolError as e:
        logger.error(f"Database Pool Error: {e}")
        return 2
    except Exception as e:
        logger.error(f"Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Retroactively tag episodes and insights using pattern-based rules.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run to see what would be tagged
  python retroactive_tagging.py --dry-run

  # Verbose output with actual tagging
  python retroactive_tagging.py --verbose

  # Dry run with verbose output
  python retroactive_tagging.py --dry-run --verbose
        """
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be tagged without writing to database"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed per-entry logging"
    )
    args = parser.parse_args()

    exit_code = main(dry_run=args.dry_run, verbose=args.verbose)
    sys.exit(exit_code)
