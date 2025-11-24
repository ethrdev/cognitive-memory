#!/usr/bin/env python3
"""
Validate Golden Test Set

: Comprehensive validation of Golden Test Set for completeness,
quality, and compliance with stratification requirements.

Validation Checks:
1. Total query count (50-100 queries)
2. Stratification (40% Short, 40% Medium, 20% Long ±5%)
3. No overlap with Ground Truth sessions (Production only)
4. All expected_docs arrays populated
5. Query type classification consistency

Mock Mode:
- Validates against mock_golden_test_set.json
- Skips Ground Truth overlap check (requires PostgreSQL)

Production Mode:
- Validates against PostgreSQL golden_test_set table
- Checks overlap with ground_truth table
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime


# =============================================================================
# Configuration
# =============================================================================

MOCK_MODE = True  # Set to False when PostgreSQL connection available

MOCK_FILE = "/home/user/i-o/mcp_server/scripts/mock_golden_test_set.json"
LABELED_FILE = "/home/user/i-o/mcp_server/scripts/golden_test_set_labeled.json"

# Validation Thresholds
MIN_QUERIES = 50
MAX_QUERIES = 100

TARGET_STRATIFICATION = {
    "short": 0.40,
    "medium": 0.40,
    "long": 0.20
}

STRATIFICATION_TOLERANCE = 0.05  # ±5%


# =============================================================================
# Data Loading
# =============================================================================

def load_golden_test_set() -> List[Dict]:
    """Load Golden Test Set (mock or production)"""
    if MOCK_MODE:
        # Try labeled file first, fallback to mock
        labeled_path = Path(LABELED_FILE)
        if labeled_path.exists():
            with open(labeled_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("labeled_queries", [])

        # Fallback to mock
        with open(MOCK_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Production: Load from PostgreSQL
        # import psycopg2
        # conn = psycopg2.connect(...)
        # cur = conn.cursor()
        # cur.execute("SELECT * FROM golden_test_set")
        # return [dict(row) for row in cur.fetchall()]
        raise NotImplementedError("Production PostgreSQL loading not yet implemented")


# =============================================================================
# Validation Checks
# =============================================================================

def validate_query_count(queries: List[Dict]) -> Tuple[bool, str]:
    """
    Check 1: Total query count

    Returns:
        (is_valid, message)
    """
    total = len(queries)

    if total < MIN_QUERIES:
        return False, f"❌ Too few queries: {total} (minimum: {MIN_QUERIES})"
    elif total > MAX_QUERIES:
        return False, f"❌ Too many queries: {total} (maximum: {MAX_QUERIES})"
    else:
        return True, f"✅ Query count valid: {total} (target: {MIN_QUERIES}-{MAX_QUERIES})"


def validate_stratification(queries: List[Dict]) -> Tuple[bool, str, Dict]:
    """
    Check 2: Stratification balance

    Returns:
        (is_valid, message, stats)
    """
    total = len(queries)
    if total == 0:
        return False, "❌ No queries to validate", {}

    # Count by type
    counts = {"short": 0, "medium": 0, "long": 0}
    for q in queries:
        query_type = q.get("query_type", "unknown")
        if query_type in counts:
            counts[query_type] += 1

    # Calculate percentages
    percentages = {
        qtype: counts[qtype] / total
        for qtype in counts
    }

    # Check if within tolerance
    valid = True
    details = []

    for qtype, target in TARGET_STRATIFICATION.items():
        actual = percentages[qtype]
        diff = abs(actual - target)

        within_tolerance = diff <= STRATIFICATION_TOLERANCE

        status = "✅" if within_tolerance else "❌"
        details.append(
            f"{status} {qtype.capitalize()}: {counts[qtype]} ({actual:.1%}) "
            f"[target: {target:.0%} ±{STRATIFICATION_TOLERANCE:.0%}]"
        )

        if not within_tolerance:
            valid = False

    message = "\n   ".join(details)

    if valid:
        summary = f"✅ Stratification valid:\n   {message}"
    else:
        summary = f"❌ Stratification out of range:\n   {message}"

    stats = {
        "counts": counts,
        "percentages": percentages,
        "valid": valid
    }

    return valid, summary, stats


def validate_expected_docs(queries: List[Dict]) -> Tuple[bool, str]:
    """
    Check 3: All expected_docs arrays populated

    Returns:
        (is_valid, message)
    """
    empty_count = 0
    total = len(queries)

    for q in queries:
        expected_docs = q.get("expected_docs", [])
        if not expected_docs or len(expected_docs) == 0:
            empty_count += 1

    if empty_count > 0:
        return False, f"❌ {empty_count}/{total} queries have empty expected_docs"
    else:
        return True, f"✅ All {total} queries have expected_docs populated"


def validate_query_type_consistency(queries: List[Dict]) -> Tuple[bool, str]:
    """
    Check 4: Query type classification consistency

    Validates that query_type matches actual word count classification.

    Returns:
        (is_valid, message)
    """
    inconsistent_count = 0
    total = len(queries)

    for q in queries:
        query_text = q.get("query", "")
        declared_type = q.get("query_type", "")
        word_count = len(query_text.split())

        # Expected type based on word count
        if word_count <= 10:
            expected_type = "short"
        elif word_count >= 30:
            expected_type = "long"
        else:
            expected_type = "medium"

        if declared_type != expected_type:
            inconsistent_count += 1

    if inconsistent_count > 0:
        return False, f"❌ {inconsistent_count}/{total} queries have inconsistent query_type classification"
    else:
        return True, f"✅ All {total} queries have consistent query_type classification"


def validate_no_overlap_with_ground_truth(queries: List[Dict]) -> Tuple[bool, str]:
    """
    Check 5: No overlap with Ground Truth sessions

    Production only: Checks that no session_id exists in both
    golden_test_set and ground_truth tables.

    Returns:
        (is_valid, message)
    """
    if MOCK_MODE:
        return True, "⏭️ Ground Truth overlap check skipped (MOCK_MODE)"

    # Production: Query PostgreSQL
    # import psycopg2
    # conn = psycopg2.connect(...)
    # cur = conn.cursor()
    # cur.execute("""
    #     SELECT COUNT(*) FROM golden_test_set gts
    #     INNER JOIN ground_truth gt ON gts.session_id = gt.session_id
    # """)
    # overlap_count = cur.fetchone()[0]
    #
    # if overlap_count > 0:
    #     return False, f"❌ {overlap_count} queries overlap with Ground Truth sessions"
    # else:
    #     return True, "✅ No overlap with Ground Truth sessions"

    raise NotImplementedError("Production Ground Truth overlap check not yet implemented")


# =============================================================================
# Main Validation Execution
# =============================================================================

def run_validation() -> Dict:
    """
    Execute all validation checks

    Returns:
        {
            "timestamp": str,
            "mock_mode": bool,
            "total_queries": int,
            "checks": {
                "query_count": {"valid": bool, "message": str},
                "stratification": {"valid": bool, "message": str, "stats": dict},
                "expected_docs": {"valid": bool, "message": str},
                "type_consistency": {"valid": bool, "message": str},
                "ground_truth_overlap": {"valid": bool, "message": str}
            },
            "overall_valid": bool
        }
    """
    print("=" * 60)
    print("Golden Test Set Validation - ")
    print("=" * 60)
    print(f"Mode: {'MOCK (Infrastructure Testing)' if MOCK_MODE else 'PRODUCTION'}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    # Load data
    print("📥 Loading Golden Test Set...")
    queries = load_golden_test_set()
    print(f"   Loaded {len(queries)} queries")
    print()

    # Run checks
    results = {
        "timestamp": datetime.now().isoformat(),
        "mock_mode": MOCK_MODE,
        "total_queries": len(queries),
        "checks": {},
        "overall_valid": True
    }

    print("🔍 Running Validation Checks...")
    print()

    # Check 1: Query Count
    valid, message = validate_query_count(queries)
    results["checks"]["query_count"] = {"valid": valid, "message": message}
    print(f"1. {message}")
    if not valid:
        results["overall_valid"] = False

    # Check 2: Stratification
    valid, message, stats = validate_stratification(queries)
    results["checks"]["stratification"] = {
        "valid": valid,
        "message": message,
        "stats": stats
    }
    print(f"\n2. {message}")
    if not valid:
        results["overall_valid"] = False

    # Check 3: Expected Docs
    valid, message = validate_expected_docs(queries)
    results["checks"]["expected_docs"] = {"valid": valid, "message": message}
    print(f"\n3. {message}")
    if not valid:
        results["overall_valid"] = False

    # Check 4: Type Consistency
    valid, message = validate_query_type_consistency(queries)
    results["checks"]["type_consistency"] = {"valid": valid, "message": message}
    print(f"\n4. {message}")
    if not valid:
        results["overall_valid"] = False

    # Check 5: Ground Truth Overlap (Production only)
    try:
        valid, message = validate_no_overlap_with_ground_truth(queries)
        results["checks"]["ground_truth_overlap"] = {"valid": valid, "message": message}
        print(f"\n5. {message}")
        if not valid:
            results["overall_valid"] = False
    except NotImplementedError:
        results["checks"]["ground_truth_overlap"] = {
            "valid": None,
            "message": "⏭️ Check not implemented in mock mode"
        }
        print(f"\n5. ⏭️ Ground Truth overlap check skipped (requires production mode)")

    print()
    print("=" * 60)

    # Overall result
    if results["overall_valid"]:
        print("✅ VALIDATION PASSED - Golden Test Set is ready")
    else:
        print("❌ VALIDATION FAILED - Issues found (see above)")

    print("=" * 60)

    return results


def main():
    """Main validation execution"""
    results = run_validation()

    # Save results
    output_file = "/home/user/i-o/mcp_server/scripts/golden_test_set_validation.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Validation results saved to: {output_file}")

    # Exit code
    sys.exit(0 if results["overall_valid"] else 1)


if __name__ == "__main__":
    main()
