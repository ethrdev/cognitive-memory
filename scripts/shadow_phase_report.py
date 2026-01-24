#!/usr/bin/env python3
"""
Shadow Phase Report Generator

Story 11.8.2: Generate comprehensive shadow phase report for all projects.

Usage:
    python shadow_phase_report.py
    python shadow_phase_report.py --project sm
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
class ShadowPhaseStatus:
    """Shadow phase status for a project."""
    project_id: str
    access_level: str
    days_in_shadow: int
    transaction_count: int
    violation_count: int
    eligible: bool
    reasons: list[str]
    recommendation: str


def calculate_shadow_eligibility(project_id: str) -> ShadowPhaseStatus:
    """
    Calculate shadow phase eligibility for a project.

    Args:
        project_id: Project identifier

    Returns:
        ShadowPhaseStatus with eligibility determination
    """
    with get_connection_sync() as conn:
        with conn.cursor() as cur:
            # Get migration status
            cur.execute("""
                SELECT rs.migration_phase, rs.updated_at, pr.access_level
                FROM rls_migration_status rs
                JOIN project_registry pr ON rs.project_id = pr.project_id
                WHERE rs.project_id = %s
            """, (project_id,))

            result = cur.fetchone()
            if not result or result[0] != 'shadow':
                raise ValueError(f"Project {project_id} is not in shadow phase")

            phase, updated_at, access_level = result

            # Calculate days in shadow
            shadow_duration = datetime.now(timezone.utc) - updated_at
            days_in_shadow = shadow_duration.days

            # Count violations
            cur.execute("""
                SELECT COUNT(*)
                FROM rls_audit_log
                WHERE project_id = %s AND would_be_denied = TRUE
            """, (project_id,))
            violation_count = cur.fetchone()[0]

            # Estimate transaction count
            cur.execute("""
                SELECT COUNT(*)
                FROM rls_audit_log
                WHERE project_id = %s AND logged_at >= %s
            """, (project_id, updated_at))
            transaction_count = cur.fetchone()[0]

            # Determine eligibility
            reasons = []
            eligible = True

            # Check minimum duration
            if days_in_shadow < MIN_SHADOW_DAYS:
                eligible = False
                reasons.append(f"Shadow duration: {days_in_shadow} days (minimum: {MIN_SHADOW_DAYS})")
            else:
                reasons.append(f"Shadow duration: {days_in_shadow} days \u2713")

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
            elif days_in_shadow >= MAX_SHADOW_DAYS:
                recommendation = "URGENT: Exceeds maximum shadow duration"
            else:
                recommendation = "Continue monitoring"

            return ShadowPhaseStatus(
                project_id=project_id,
                access_level=access_level,
                days_in_shadow=days_in_shadow,
                transaction_count=transaction_count,
                violation_count=violation_count,
                eligible=eligible,
                reasons=reasons,
                recommendation=recommendation
            )


def generate_shadow_phase_report(project_id: str | None = None) -> dict[str, Any]:
    """
    Generate shadow phase report for all projects or specific project.

    Args:
        project_id: Optional project ID to filter

    Returns:
        Report dict with project statuses
    """
    initialize_pool_sync()

    if project_id:
        statuses = [calculate_shadow_eligibility(project_id)]
    else:
        statuses = []
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT project_id
                    FROM rls_migration_status
                    WHERE migration_phase = 'shadow'
                    ORDER BY project_id
                """)
                project_ids = [row[0] for row in cur.fetchall()]

        for pid in project_ids:
            try:
                statuses.append(calculate_shadow_eligibility(pid))
            except Exception as e:
                print(f"Error processing {pid}: {e}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_projects": len(statuses),
        "eligible_count": sum(1 for s in statuses if s.eligible),
        "projects": {
            s.project_id: {
                "access_level": s.access_level,
                "days_in_shadow": s.days_in_shadow,
                "transaction_count": s.transaction_count,
                "violation_count": s.violation_count,
                "eligible": s.eligible,
                "reasons": s.reasons,
                "recommendation": s.recommendation
            }
            for s in statuses
        }
    }


def print_report(report: dict[str, Any]) -> None:
    """Print formatted report to stdout."""
    print("\n" + "=" * 70)
    print(f"SHADOW PHASE REPORT - {report['generated_at']}")
    print("=" * 70)

    print(f"\nSummary:")
    print(f"  Total Projects in Shadow: {report['total_projects']}")
    print(f"  Eligible for Enforcing: {report['eligible_count']}")

    for project_id, status in report['projects'].items():
        print(f"\n{'\u2500' * 70}")
        print(f"Project: {project_id} ({status['access_level']})")
        print(f"{'\u2500' * 70}")

        eligible_symbol = "\u2713" if status['eligible'] else "\u2717"
        print(f"Status: {eligible_symbol} {status['recommendation']}")

        print(f"\nMetrics:")
        print(f"  Days in Shadow: {status['days_in_shadow']}")
        print(f"  Transaction Count: {status['transaction_count']}")
        print(f"  Violations: {status['violation_count']}")

        print(f"\nExit Criteria:")
        for reason in status['reasons']:
            print(f"  \u2022 {reason}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate shadow phase monitoring report"
    )
    parser.add_argument("--project", help="Filter by project ID")
    args = parser.parse_args()

    try:
        report = generate_shadow_phase_report(args.project)
        print_report(report)

        # Exit with non-zero if any projects exceed max duration
        for status in report['projects'].values():
            if status['days_in_shadow'] > MAX_SHADOW_DAYS and not status['eligible']:
                print(f"\n\u26a0 WARNING: {status['project_id']} exceeds maximum shadow duration!")
                return 1

        return 0

    except Exception as e:
        print(f"Error generating report: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
