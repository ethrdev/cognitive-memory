#!/usr/bin/env python3
"""Migration Script 05: Validate Migration.

Post-migration validation checks:
- Row counts plausible
- Embeddings valid (1536 dimensions)
- No NULL values in required fields
- Metadata JSONB well-formed
- Full-text search functional
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

from scripts.migration.utils.db_writer import (
    get_db_connection,
    get_row_counts,
    verify_embeddings,
)


def check_null_values() -> dict:
    """Check for NULL values in required fields."""
    results = {}

    with get_db_connection() as conn:
        cur = conn.cursor()

        # l0_raw required fields
        cur.execute("SELECT COUNT(*) FROM l0_raw WHERE session_id IS NULL")
        results["l0_raw_null_session_id"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM l0_raw WHERE content IS NULL")
        results["l0_raw_null_content"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM l0_raw WHERE speaker IS NULL")
        results["l0_raw_null_speaker"] = cur.fetchone()[0]

        # l2_insights required fields
        cur.execute("SELECT COUNT(*) FROM l2_insights WHERE content IS NULL")
        results["l2_insights_null_content"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM l2_insights WHERE embedding IS NULL")
        results["l2_insights_null_embedding"] = cur.fetchone()[0]

    return results


def check_metadata_validity() -> dict:
    """Check that metadata JSONB is well-formed."""
    results = {}

    with get_db_connection() as conn:
        cur = conn.cursor()

        # Check l0_raw metadata is valid JSONB
        cur.execute(
            """
            SELECT COUNT(*) FROM l0_raw
            WHERE metadata IS NOT NULL
            AND jsonb_typeof(metadata) = 'object'
        """
        )
        results["l0_raw_valid_metadata"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM l0_raw")
        results["l0_raw_total"] = cur.fetchone()[0]

        # Check l2_insights metadata
        cur.execute(
            """
            SELECT COUNT(*) FROM l2_insights
            WHERE metadata IS NOT NULL
            AND jsonb_typeof(metadata) = 'object'
        """
        )
        results["l2_insights_valid_metadata"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM l2_insights")
        results["l2_insights_total"] = cur.fetchone()[0]

    return results


def check_session_distribution() -> dict:
    """Check session ID distribution in l0_raw."""
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT COUNT(DISTINCT session_id) as sessions,
                   COUNT(*) as total_messages,
                   MIN(timestamp) as earliest,
                   MAX(timestamp) as latest
            FROM l0_raw
        """
        )
        row = cur.fetchone()

        return {
            "distinct_sessions": row[0],
            "total_messages": row[1],
            "earliest_timestamp": str(row[2]) if row[2] else None,
            "latest_timestamp": str(row[3]) if row[3] else None,
        }


def check_source_type_distribution() -> dict:
    """Check source type distribution in l2_insights."""
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT metadata->>'source_type' as source_type, COUNT(*)
            FROM l2_insights
            GROUP BY metadata->>'source_type'
            ORDER BY COUNT(*) DESC
        """
        )

        return {row[0] or "unknown": row[1] for row in cur.fetchall()}


def test_semantic_search(query: str = "Präsenz über Kontinuität") -> dict:
    """Test semantic search functionality."""
    with get_db_connection() as conn:
        cur = conn.cursor()

        # Simple text search (not semantic, but tests DB)
        cur.execute(
            """
            SELECT id, LEFT(content, 100) as content_preview
            FROM l2_insights
            WHERE content ILIKE %s
            LIMIT 5
        """,
            (f"%{query}%",),
        )

        results = []
        for row in cur.fetchall():
            results.append({"id": row[0], "preview": row[1]})

        return {"query": query, "results_count": len(results), "results": results}


def main():
    parser = argparse.ArgumentParser(description="Validate migration results")
    parser.add_argument("--output", help="Output file for validation report (JSON)")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    # Load environment
    env_file = Path(__file__).parent.parent.parent / ".env.development"
    if env_file.exists():
        load_dotenv(env_file)

    print("=" * 60)
    print("MIGRATION VALIDATION REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print("=" * 60)

    report = {"timestamp": datetime.now().isoformat(), "checks": {}}

    # 1. Row counts
    print("\n1. ROW COUNTS")
    print("-" * 40)
    counts = get_row_counts()
    for table, count in counts.items():
        status = "✓" if count > 0 else "⚠"
        print(f"  {status} {table}: {count:,} rows")
    report["checks"]["row_counts"] = counts

    # 2. Embedding validation
    print("\n2. EMBEDDING VALIDATION")
    print("-" * 40)
    emb_stats = verify_embeddings("l2_insights", expected_dim=1536)
    print(f"  Total rows:        {emb_stats['total']:,}")
    print(f"  Valid dimensions:  {emb_stats['valid_dimensions']:,}")
    print(f"  Null embeddings:   {emb_stats['null_embeddings']:,}")
    print(f"  Invalid:           {emb_stats['invalid']:,}")

    emb_status = (
        "✓ PASS"
        if emb_stats["invalid"] == 0 and emb_stats["null_embeddings"] == 0
        else "✗ FAIL"
    )
    print(f"  Status: {emb_status}")
    report["checks"]["embeddings"] = emb_stats

    # 3. NULL value check
    print("\n3. NULL VALUE CHECK")
    print("-" * 40)
    null_checks = check_null_values()
    all_null_zero = all(v == 0 for v in null_checks.values())

    for field, count in null_checks.items():
        status = "✓" if count == 0 else "✗"
        print(f"  {status} {field}: {count}")

    null_status = "✓ PASS" if all_null_zero else "✗ FAIL"
    print(f"  Status: {null_status}")
    report["checks"]["null_values"] = null_checks

    # 4. Metadata validity
    print("\n4. METADATA VALIDITY")
    print("-" * 40)
    meta_checks = check_metadata_validity()

    l0_valid = meta_checks["l0_raw_valid_metadata"] == meta_checks["l0_raw_total"]
    l2_valid = (
        meta_checks["l2_insights_valid_metadata"] == meta_checks["l2_insights_total"]
    )

    print(
        f"  l0_raw:       {meta_checks['l0_raw_valid_metadata']}/{meta_checks['l0_raw_total']} valid"
    )
    print(
        f"  l2_insights:  {meta_checks['l2_insights_valid_metadata']}/{meta_checks['l2_insights_total']} valid"
    )

    meta_status = "✓ PASS" if l0_valid and l2_valid else "✗ FAIL"
    print(f"  Status: {meta_status}")
    report["checks"]["metadata"] = meta_checks

    # 5. Session distribution
    print("\n5. SESSION DISTRIBUTION (l0_raw)")
    print("-" * 40)
    session_stats = check_session_distribution()
    print(f"  Distinct sessions:  {session_stats['distinct_sessions']:,}")
    print(f"  Total messages:     {session_stats['total_messages']:,}")
    print(
        f"  Date range:         {session_stats['earliest_timestamp']} to {session_stats['latest_timestamp']}"
    )
    report["checks"]["sessions"] = session_stats

    # 6. Source type distribution
    print("\n6. SOURCE TYPE DISTRIBUTION (l2_insights)")
    print("-" * 40)
    source_types = check_source_type_distribution()
    for stype, count in source_types.items():
        print(f"  {stype}: {count}")
    report["checks"]["source_types"] = source_types

    # 7. Search test
    print("\n7. TEXT SEARCH TEST")
    print("-" * 40)
    search_results = test_semantic_search()
    print(f"  Query: '{search_results['query']}'")
    print(f"  Results: {search_results['results_count']}")
    if args.verbose and search_results["results"]:
        for r in search_results["results"][:3]:
            print(f"    - [{r['id']}] {r['preview']}...")
    report["checks"]["search_test"] = search_results

    # Overall status
    print("\n" + "=" * 60)
    print("OVERALL STATUS")
    print("=" * 60)

    issues = []
    if emb_stats["invalid"] > 0:
        issues.append(f"Invalid embeddings: {emb_stats['invalid']}")
    if emb_stats["null_embeddings"] > 0:
        issues.append(f"Null embeddings: {emb_stats['null_embeddings']}")
    if not all_null_zero:
        issues.append("NULL values in required fields")
    if not (l0_valid and l2_valid):
        issues.append("Invalid metadata")
    if counts.get("l0_raw", 0) == 0:
        issues.append("No data in l0_raw")
    if counts.get("l2_insights", 0) == 0:
        issues.append("No data in l2_insights")

    if issues:
        print("✗ VALIDATION FAILED")
        print("\nIssues found:")
        for issue in issues:
            print(f"  - {issue}")
        report["status"] = "FAILED"
        report["issues"] = issues
    else:
        print("✓ VALIDATION PASSED")
        print("\nAll checks passed. Migration data looks good!")
        report["status"] = "PASSED"
        report["issues"] = []

    # Save report if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nReport saved to: {args.output}")

    return 0 if not issues else 1


if __name__ == "__main__":
    sys.exit(main())
