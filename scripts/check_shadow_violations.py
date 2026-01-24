#!/usr/bin/env python3
"""
Shadow Phase Violation Checker

Story 11.8.1: Monitor rls_audit_log for would-be denial violations during shadow phase.

Usage:
    python check_shadow_violations.py
    python check_shadow_violations.py --project sm
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import initialize_pool_sync, get_connection_sync


@dataclass
class ViolationReport:
    """Violation report for a project."""
    project_id: str
    total_violations: int
    table_breakdown: dict[str, int]
    operation_breakdown: dict[str, int]
    sample_violations: list[dict[str, Any]]


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
                        SELECT table_name, operation, user_name, denied_reason, created_at
                        FROM rls_audit_log
                        WHERE would_be_denied = TRUE
                          AND project_id = %s
                        ORDER BY created_at DESC
                        LIMIT 5
                    """, (proj,))
                    samples = [
                        {
                            "table": row[0],
                            "operation": row[1],
                            "user": row[2],
                            "reason": row[3],
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


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Check shadow phase violations in rls_audit_log"
    )
    parser.add_argument("--project", help="Filter by project ID")
    args = parser.parse_args()

    reports = check_shadow_violations(args.project)

    if not reports:
        print(" No shadow phase violations found")
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
                      f"by {sample['user']}: {sample['reason']}")

    print()


if __name__ == "__main__":
    main()
