#!/usr/bin/env python3
"""
Shadow Phase Duration Threshold Checker

Story 11.8.2: Alert on shadow phases exceeding maximum duration.

Usage:
    python check_shadow_duration.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv(".env.development", override=True)

from mcp_server.db.connection import initialize_pool_sync, get_connection_sync

MAX_SHADOW_DAYS = 14


def check_shadow_duration_thresholds() -> list[dict[str, any]]:
    """
    Check for shadow phases exceeding maximum duration.

    Returns:
        List of alerts for projects exceeding threshold
    """
    initialize_pool_sync()

    alerts = []

    with get_connection_sync() as conn:
        with conn.cursor() as cur:
            # Find projects in shadow phase >14 days
            cur.execute(f"""
                SELECT
                    rs.project_id,
                    pr.access_level,
                    EXTRACT(DAY FROM (NOW() - rs.updated_at)) as days_in_shadow,
                    (
                        SELECT COUNT(*)
                        FROM rls_audit_log
                        WHERE project_id = rs.project_id AND would_be_denied = TRUE
                    ) as violation_count
                FROM rls_migration_status rs
                JOIN project_registry pr ON rs.project_id = pr.project_id
                WHERE rs.migration_phase = 'shadow'
                  AND NOW() - rs.updated_at > INTERVAL '{MAX_SHADOW_DAYS} days'
            """)

            for row in cur.fetchall():
                alerts.append({
                    "project_id": row[0],
                    "access_level": row[1],
                    "days_in_shadow": int(row[2]),
                    "violation_count": row[3]
                })

    return alerts


def main() -> int:
    """CLI entry point."""
    alerts = check_shadow_duration_thresholds()

    if not alerts:
        print("\u2713 No projects exceeding maximum shadow duration")
        return 0

    print(f"\n\u26a0 ALERT: {len(alerts)} project(s) exceeding maximum shadow duration ({MAX_SHADOW_DAYS} days)")
    print("=" * 70)

    for alert in alerts:
        print(f"\nProject: {alert['project_id']} ({alert['access_level']})")
        print(f"  Days in Shadow: {alert['days_in_shadow']}")
        print(f"  Violations: {alert['violation_count']}")
        print(f"  Action: Move to enforcing within 3 business days")

    # Return non-zero for alerts (for CI/CD integration)
    return 1 if alerts else 0


if __name__ == "__main__":
    sys.exit(main())
