#!/usr/bin/env python3
"""
Shadow Phase Violation Checker

Story 11.8.1: Monitor rls_audit_log for would-be denial violations during shadow phase.
Story 11.8.2: Enhanced with exit criteria validation and eligibility checking.

Usage:
    python check_shadow_violations.py
    python check_shadow_violations.py --project sm
    python check_shadow_violations.py --check-eligibility
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import initialize_pool_sync, get_connection_sync


# Exit Criteria Thresholds
MIN_SHADOW_DAYS = 7
MIN_TRANSACTIONS = 1000
MAX_SHADOW_DAYS = 14


@dataclass
class ViolationReport:
    """Violation report for a project."""
    project_id: str
    total_violations: int
    table_breakdown: dict[str, int]
    operation_breakdown: dict[str, int]
    sample_violations: list[dict[str, Any]]


@dataclass
class EligibilityStatus:
    """Shadow phase eligibility status for a project."""
    project_id: str
    eligible: bool
    shadow_days: int
    transaction_count: int
    violation_count: int
    reasons: list[str]
    recommendation: str


def check_shadow_violations(project_id: str | None = None) -> list[ViolationReport]:
    """
    Check rls_audit_log for shadow phase violations.

    Args:
        project_id: Optional project ID to filter (None = all projects)

    Returns:
        List of violation reports per project
    """
    reports = []

    try:
        initialize_pool_sync()

        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Get projects with shadow violations
                if project_id:
                    cur.execute("""
                        SELECT project_id
                        FROM rls_audit_log
                        WHERE would_be_denied = TRUE
                          AND project_id = %s
                        GROUP BY project_id
                    """, (project_id,))
                else:
                    cur.execute("""
                        SELECT project_id
                        FROM rls_audit_log
                        WHERE would_be_denied = TRUE
                        GROUP BY project_id
                    """)

                projects = [row[0] for row in cur.fetchall()]

                for proj in projects:
                    # Total violations
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM rls_audit_log
                        WHERE would_be_denied = TRUE
                          AND project_id = %s
                    """, (proj,))
                    total = cur.fetchone()[0]

                    # Breakdown by table
                    cur.execute("""
                        SELECT table_name, COUNT(*) as count
                        FROM rls_audit_log
                        WHERE would_be_denied = TRUE
                          AND project_id = %s
                        GROUP BY table_name
                        ORDER BY count DESC
                    """, (proj,))
                    table_breakdown = {row[0]: row[1] for row in cur.fetchall()}

                    # Breakdown by operation
                    cur.execute("""
                        SELECT operation, COUNT(*) as count
                        FROM rls_audit_log
                        WHERE would_be_denied = TRUE
                          AND project_id = %s
                        GROUP BY operation
                        ORDER BY count DESC
                    """, (proj,))
                    operation_breakdown = {row[0]: row[1] for row in cur.fetchall()}

                    # Sample violations (top 5)
                    cur.execute("""
                        SELECT table_name, operation, row_project_id, session_user, logged_at
                        FROM rls_audit_log
                        WHERE would_be_denied = TRUE
                          AND project_id = %s
                        ORDER BY logged_at DESC
                        LIMIT 5
                    """, (proj,))
                    samples = [
                        {
                            "table": row[0],
                            "operation": row[1],
                            "row_project": row[2],
                            "user": row[3],
                            "timestamp": row[4].isoformat()
                        }
                        for row in cur.fetchall()
                    ]

                    reports.append(ViolationReport(
                        project_id=proj,
                        total_violations=total,
                        table_breakdown=table_breakdown,
                        operation_breakdown=operation_breakdown,
                        sample_violations=samples
                    ))

    except Exception as e:
        print(f"Error checking shadow violations: {e}")
        return []

    return reports


def check_eligibility(project_id: str | None = None) -> list[EligibilityStatus]:
    """
    Check shadow phase eligibility for projects based on exit criteria.

    Exit Criteria:
    - Minimum Duration: >= 7 days (using updated_at timestamp)
    - Minimum Transactions: >= 1000 tool calls (from rls_audit_log)
    - Violation Count: = 0 (no would_be_denied = TRUE)

    Args:
        project_id: Optional project ID to filter (None = all shadow projects)

    Returns:
        List of eligibility status per project
    """
    statuses = []

    try:
        initialize_pool_sync()

        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Get all projects in shadow phase
                if project_id:
                    cur.execute("""
                        SELECT rs.project_id, rs.updated_at
                        FROM rls_migration_status rs
                        WHERE rs.migration_phase = 'shadow'
                          AND rs.project_id = %s
                    """, (project_id,))
                else:
                    cur.execute("""
                        SELECT rs.project_id, rs.updated_at
                        FROM rls_migration_status rs
                        WHERE rs.migration_phase = 'shadow'
                        ORDER BY rs.project_id
                    """)

                projects = cur.fetchall()

                for proj_id, updated_at in projects:
                    # Calculate shadow duration in days
                    shadow_duration = datetime.now(timezone.utc) - updated_at
                    shadow_days = shadow_duration.days

                    # Count violations
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM rls_audit_log
                        WHERE project_id = %s AND would_be_denied = TRUE
                    """, (proj_id,))
                    violation_count = cur.fetchone()[0]

                    # Estimate transaction count (all audit log entries since shadow started)
                    cur.execute("""
                        SELECT COUNT(*)
                        FROM rls_audit_log
                        WHERE project_id = %s AND logged_at >= %s
                    """, (proj_id, updated_at))
                    transaction_count = cur.fetchone()[0]

                    # Determine eligibility
                    reasons = []
                    eligible = True

                    # Check minimum duration
                    if shadow_days < MIN_SHADOW_DAYS:
                        eligible = False
                        reasons.append(f"Shadow duration: {shadow_days} days (minimum: {MIN_SHADOW_DAYS})")
                    else:
                        reasons.append(f"Shadow duration: {shadow_days} days \u2713")

                    # Check transaction count
                    if transaction_count < MIN_TRANSACTIONS:
                        eligible = False
                        reasons.append(f"Transactions: {transaction_count} (minimum: {MIN_TRANSACTIONS})")
                    else:
                        reasons.append(f"Transactions: {transaction_count} \u2713")

                    # Check violations
                    if violation_count > 0:
                        eligible = False
                        reasons.append(f"Violations: {violation_count} detected")
                    else:
                        reasons.append(f"Violations: {violation_count} \u2713")

                    # Determine recommendation
                    if eligible:
                        recommendation = "ELIGIBLE for enforcing phase"
                    elif violation_count > 0:
                        recommendation = "INVESTIGATE violations before proceeding"
                    elif shadow_days >= MAX_SHADOW_DAYS:
                        recommendation = "URGENT: Exceeds maximum shadow duration"
                    else:
                        recommendation = "Continue monitoring"

                    statuses.append(EligibilityStatus(
                        project_id=proj_id,
                        eligible=eligible,
                        shadow_days=shadow_days,
                        transaction_count=transaction_count,
                        violation_count=violation_count,
                        reasons=reasons,
                        recommendation=recommendation
                    ))

    except Exception as e:
        print(f"Error checking eligibility: {e}")
        return []

    return statuses


def print_eligibility_report(statuses: list[EligibilityStatus]) -> None:
    """Print formatted eligibility report."""
    if not statuses:
        print("\u2713 No projects currently in shadow phase")
        return

    print(f"\nShadow Phase Eligibility Report:")
    print("=" * 70)

    for status in statuses:
        print(f"\nProject: {status.project_id}")
        print(f"Status: {'\u2713 ELIGIBLE' if status.eligible else '\u2717 NOT ELIGIBLE'}")
        print(f"Recommendation: {status.recommendation}")

        print(f"\nMetrics:")
        print(f"  Days in Shadow: {status.shadow_days}")
        print(f"  Transaction Count: {status.transaction_count}")
        print(f"  Violation Count: {status.violation_count}")

        print(f"\nExit Criteria:")
        for reason in status.reasons:
            print(f"  \u2022 {reason}")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Check shadow phase violations and eligibility"
    )
    parser.add_argument("--project", help="Filter by project ID")
    parser.add_argument(
        "--check-eligibility",
        action="store_true",
        help="Check exit criteria eligibility instead of violations"
    )
    args = parser.parse_args()

    if args.check_eligibility:
        statuses = check_eligibility(args.project)
        print_eligibility_report(statuses)
    else:
        reports = check_shadow_violations(args.project)

        if not reports:
            print("\u2713 No shadow phase violations found")
            return

        print(f"\nShadow Phase Violations Report:")
        print("=" * 60)

        for report in reports:
            print(f"\nProject: {report.project_id}")
            print(f"Total Violations: {report.total_violations}")

            if report.table_breakdown:
                print("\nBy Table:")
                for table, count in report.table_breakdown.items():
                    print(f"  {table}: {count}")

            if report.operation_breakdown:
                print("\nBy Operation:")
                for op, count in report.operation_breakdown.items():
                    print(f"  {op}: {count}")

            if report.sample_violations:
                print("\nSample Violations:")
                for i, sample in enumerate(report.sample_violations, 1):
                    print(f"  {i}. {sample['table']}/{sample['operation']} "
                          f"by {sample['user']} -> row {sample['row_project']}")

        print()


if __name__ == "__main__":
    main()
