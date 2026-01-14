#!/usr/bin/env python3
"""
Golden Test Set Creation Script

: Create separate Golden Test Set (50-100 queries) for daily
Precision@5 regression testing and model drift detection.

Key Requirements:
- Extract queries from L0 Raw Memory (different sessions than Ground Truth)
- Stratification: 40% Short, 40% Medium, 20% Long (±5% tolerance)
- NO overlap with Ground Truth sessions
- Target: 50-100 queries for statistical power >0.80

Implementation:
1. Query l0_raw for all unique session_ids
2. Exclude sessions already in ground_truth table
3. Sample queries stratified by length
4. Insert into golden_test_set table (unlabeled - expected_docs empty for now)

Usage:
    python mcp_server/scripts/create_golden_test_set.py [--target-count 75]
"""

import argparse
import logging
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.connection import get_connection, get_connection_sync, initialize_pool

# Import classify_query_type from  (REUSE)
# We'll import from validate_precision_at_5 once we verify path
sys.path.insert(0, str(Path(__file__).parent))
from validate_precision_at_5 import classify_query_type

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_TARGET_COUNT = 75  # Target 75 queries (middle of 50-100 range)

# Stratification targets (40%/40%/20%)
STRATIFICATION_TARGETS = {
    "short": 0.40,   # 40% Short (≤10 words)
    "medium": 0.40,  # 40% Medium (11-29 words)
    "long": 0.20,    # 20% Long (≥30 words)
}

TOLERANCE = 0.05  # ±5% tolerance per category

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# Session Sampling
# =============================================================================

def get_excluded_sessions() -> List[UUID]:
    """
    Get all session_ids that are already used in ground_truth table.

    These sessions must be EXCLUDED from Golden Test Set to prevent
    overfitting ("teaching to the test").

    Returns:
        List of UUID session_ids to exclude
    """
    with get_connection_sync() as conn:
        with conn.cursor() as cur:
            # Query ground_truth sessions
            # Note: ground_truth doesn't have session_id column directly,
            # but we can derive it from L2 insights via source_ids
            cur.execute("""
                SELECT DISTINCT l0.session_id
                FROM ground_truth gt
                CROSS JOIN LATERAL unnest(gt.expected_docs) AS l2_id
                JOIN l2_insights l2 ON l2.id = l2_id
                CROSS JOIN LATERAL unnest(l2.source_ids) AS l0_id
                JOIN l0_raw l0 ON l0.id = l0_id
                WHERE l0.session_id IS NOT NULL
            """)

            excluded_sessions = [row[0] for row in cur.fetchall()]
            logger.info(f"Found {len(excluded_sessions)} sessions to exclude (from ground_truth)")
            return excluded_sessions


def get_available_sessions(excluded_sessions: List[UUID]) -> List[UUID]:
    """
    Get all session_ids from l0_raw that are NOT in excluded list.

    Args:
        excluded_sessions: List of session_ids to exclude

    Returns:
        List of available session_ids
    """
    with get_connection_sync() as conn:
        with conn.cursor() as cur:
            # Get all unique sessions from l0_raw
            cur.execute("""
                SELECT DISTINCT session_id
                FROM l0_raw
                WHERE session_id IS NOT NULL
                  AND session_id NOT IN %s
                ORDER BY session_id
            """, (tuple(excluded_sessions) if excluded_sessions else (None,),))

            available_sessions = [row[0] for row in cur.fetchall()]
            logger.info(f"Found {len(available_sessions)} available sessions (not in ground_truth)")
            return available_sessions


# =============================================================================
# Query Extraction and Stratification
# =============================================================================

def extract_queries_from_sessions(
    session_ids: List[UUID],
    target_count: int
) -> List[Dict]:
    """
    Extract queries from given sessions with stratified sampling.

    Args:
        session_ids: List of session_ids to sample from
        target_count: Target number of queries (e.g., 75)

    Returns:
        List of query dicts with {query, session_id, query_type, word_count}
    """
    with get_connection_sync() as conn:
        with conn.cursor() as cur:
            # Extract user queries from l0_raw (speaker='user')
            cur.execute("""
                SELECT DISTINCT content, session_id
                FROM l0_raw
                WHERE session_id = ANY(%s)
                  AND speaker = 'user'
                  AND content IS NOT NULL
                  AND LENGTH(content) > 10  -- Filter out very short queries
                ORDER BY session_id, timestamp
            """, (session_ids,))

            raw_queries = cur.fetchall()
            logger.info(f"Extracted {len(raw_queries)} candidate queries from {len(session_ids)} sessions")

    # Classify queries by type
    classified_queries = []
    for content, session_id in raw_queries:
        query_type = classify_query_type(content)
        word_count = len(content.split())

        classified_queries.append({
            "query": content,
            "session_id": session_id,
            "query_type": query_type,
            "word_count": word_count
        })

    # Count by type
    type_counts = Counter(q["query_type"] for q in classified_queries)
    logger.info(f"Query distribution before sampling:")
    for qtype, count in type_counts.items():
        logger.info(f"  {qtype}: {count} queries ({count / len(classified_queries) * 100:.1f}%)")

    # Stratified sampling
    target_counts = {
        "short": int(target_count * STRATIFICATION_TARGETS["short"]),
        "medium": int(target_count * STRATIFICATION_TARGETS["medium"]),
        "long": int(target_count * STRATIFICATION_TARGETS["long"]),
    }

    # Adjust for rounding (ensure sum = target_count)
    total = sum(target_counts.values())
    if total < target_count:
        target_counts["medium"] += (target_count - total)

    logger.info(f"\nTarget stratification for {target_count} queries:")
    for qtype, count in target_counts.items():
        logger.info(f"  {qtype}: {count} queries ({count / target_count * 100:.1f}%)")

    # Sample queries stratified by type
    sampled_queries = []
    for qtype, target in target_counts.items():
        queries_of_type = [q for q in classified_queries if q["query_type"] == qtype]

        if len(queries_of_type) < target:
            logger.warning(f"⚠️  Not enough {qtype} queries: have {len(queries_of_type)}, need {target}")
            sampled = queries_of_type  # Take all available
        else:
            # Random sample (but deterministic for reproducibility)
            import random
            random.seed(42)  # Fixed seed for reproducibility
            sampled = random.sample(queries_of_type, target)

        sampled_queries.extend(sampled)
        logger.info(f"  Sampled {len(sampled)} {qtype} queries")

    # Verify final distribution
    final_counts = Counter(q["query_type"] for q in sampled_queries)
    logger.info(f"\n✅ Final distribution ({len(sampled_queries)} queries):")
    for qtype, count in final_counts.items():
        percentage = count / len(sampled_queries) * 100
        target_percentage = STRATIFICATION_TARGETS[qtype] * 100
        deviation = percentage - target_percentage
        logger.info(f"  {qtype}: {count} queries ({percentage:.1f}%) [target: {target_percentage:.0f}%, deviation: {deviation:+.1f}%]")

    return sampled_queries


# =============================================================================
# Database Insertion
# =============================================================================

def insert_golden_test_queries(queries: List[Dict]) -> int:
    """
    Insert sampled queries into golden_test_set table.

    Note: expected_docs is left EMPTY ([]) - will be filled via Streamlit UI labeling.

    Args:
        queries: List of query dicts

    Returns:
        Number of queries inserted
    """
    with get_connection_sync() as conn:
        with conn.cursor() as cur:
            # Insert queries (expected_docs empty for now - manual labeling required)
            inserted_count = 0
            for q in queries:
                cur.execute("""
                    INSERT INTO golden_test_set (
                        query, query_type, expected_docs, session_id, word_count, labeled_by
                    ) VALUES (
                        %s, %s, %s, %s, %s, 'ethr'
                    )
                """, (
                    q["query"],
                    q["query_type"],
                    [],  # Empty - to be labeled via UI
                    q["session_id"],
                    q["word_count"]
                ))
                inserted_count += 1

            conn.commit()
            logger.info(f"✅ Inserted {inserted_count} queries into golden_test_set")

    return inserted_count


# =============================================================================
# Validation
# =============================================================================

def validate_golden_test_set():
    """
    Validate Golden Test Set after creation.

    Checks:
    1. Total query count (50-100 expected)
    2. Stratification (40%/40%/20% ±5%)
    3. No overlap with ground_truth sessions
    """
    with get_connection_sync() as conn:
        with conn.cursor() as cur:
            # 1. Total count
            cur.execute("SELECT COUNT(*) FROM golden_test_set")
            total_count = cur.fetchone()[0]
            logger.info(f"\n📊 Validation Results:")
            logger.info(f"Total queries: {total_count}")

            if 50 <= total_count <= 100:
                logger.info("  ✅ Count within target range (50-100)")
            else:
                logger.warning(f"  ⚠️  Count outside target range: {total_count}")

            # 2. Stratification
            cur.execute("""
                SELECT query_type, COUNT(*) as count
                FROM golden_test_set
                GROUP BY query_type
                ORDER BY query_type
            """)

            logger.info(f"\nStratification:")
            for row in cur.fetchall():
                qtype, count = row
                percentage = count / total_count * 100
                target_percentage = STRATIFICATION_TARGETS[qtype] * 100
                deviation = abs(percentage - target_percentage)

                status = "✅" if deviation <= (TOLERANCE * 100) else "⚠️"
                logger.info(f"  {status} {qtype}: {count} ({percentage:.1f}%) [target: {target_percentage:.0f}% ± 5%]")

            # 3. Session overlap check
            cur.execute("""
                SELECT COUNT(*)
                FROM golden_test_set gts
                INNER JOIN (
                    SELECT DISTINCT l0.session_id
                    FROM ground_truth gt
                    CROSS JOIN LATERAL unnest(gt.expected_docs) AS l2_id
                    JOIN l2_insights l2 ON l2.id = l2_id
                    CROSS JOIN LATERAL unnest(l2.source_ids) AS l0_id
                    JOIN l0_raw l0 ON l0.id = l0_id
                ) gt_sessions ON gts.session_id = gt_sessions.session_id
            """)

            overlap_count = cur.fetchone()[0]
            if overlap_count == 0:
                logger.info(f"\n✅ No session overlap with ground_truth (expected: 0, actual: 0)")
            else:
                logger.error(f"\n❌ CRITICAL: Found {overlap_count} queries with ground_truth session overlap!")
                logger.error("  This violates AC-3.1.1 (no overlap requirement)")


# =============================================================================
# Main Execution
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Create Golden Test Set for model drift detection"
    )
    parser.add_argument(
        "--target-count",
        type=int,
        default=DEFAULT_TARGET_COUNT,
        help=f"Target number of queries (default: {DEFAULT_TARGET_COUNT})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't insert queries"
    )

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("Golden Test Set Creation Script - ")
    logger.info("=" * 80)
    logger.info(f"Target query count: {args.target_count}")
    logger.info(f"Dry run mode: {args.dry_run}")
    logger.info("")

    try:
        # Initialize database connection pool
        initialize_pool()

        # Step 1: Get excluded sessions (from ground_truth)
        logger.info("Step 1: Identifying sessions to exclude...")
        excluded_sessions = get_excluded_sessions()

        if not excluded_sessions:
            logger.warning("⚠️  No ground_truth sessions found - this is unexpected!")
            logger.warning("   Continuing anyway, but verify ground_truth table exists.")

        # Step 2: Get available sessions
        logger.info("\nStep 2: Finding available sessions...")
        available_sessions = get_available_sessions(excluded_sessions)

        if not available_sessions:
            logger.error("❌ No available sessions found!")
            logger.error("   All l0_raw sessions are already in ground_truth.")
            logger.error("   Cannot create Golden Test Set without new sessions.")
            sys.exit(1)

        # Step 3: Extract and sample queries
        logger.info("\nStep 3: Extracting and sampling queries...")
        sampled_queries = extract_queries_from_sessions(available_sessions, args.target_count)

        if len(sampled_queries) < 50:
            logger.error(f"❌ Only {len(sampled_queries)} queries sampled (minimum: 50)")
            logger.error("   Not enough queries for statistical power.")
            sys.exit(1)

        # Step 4: Insert into database
        if not args.dry_run:
            logger.info("\nStep 4: Inserting queries into golden_test_set...")
            insert_golden_test_queries(sampled_queries)

            # Step 5: Validate
            logger.info("\nStep 5: Validating Golden Test Set...")
            validate_golden_test_set()
        else:
            logger.info("\n[DRY RUN] Would insert {len(sampled_queries)} queries")

        logger.info("\n" + "=" * 80)
        logger.info("✅ Golden Test Set Creation Complete!")
        logger.info("=" * 80)
        logger.info(f"Queries created: {len(sampled_queries)}")
        logger.info(f"Next step: Run Streamlit UI to label queries")
        logger.info(f"  Command: streamlit run mcp_server/ui/golden_test_app.py")
        logger.info("")

    except Exception as e:
        logger.error(f"❌ Error during Golden Test Set creation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
