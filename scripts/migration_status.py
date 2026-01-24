#!/usr/bin/env python3
"""
Migration Status Reporter

Story 11.8.1: Report current migration status for all projects.

Usage:
    python migration_status.py

Expected Output:
    RLS Migration Status
    ============================================================

    Summary:
      Pending:   5 projects
      Shadow:    2 projects
      Enforcing: 1 projects
      Complete:  0 projects

    Project      Phase        Access      Updated
    ------------------------------------------------------------
    sm           shadow       ISOLATED    2d 4h ago
    motoko       shadow       ISOLATED    1d 12h ago
    io           pending      SUPER       5h ago
    ...
"""

from __future__ import annotations

from datetime import datetime, timezone

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import initialize_pool_sync, get_connection_sync


def get_migration_status() -> list[dict[str, any]]:
    """Get migration status for all projects."""
    try:
        initialize_pool_sync()

        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        rs.project_id,
                        rs.migration_phase,
                        rs.rls_enabled,
                        rs.migrated_at,
                        rs.updated_at,
                        pr.access_level
                    FROM rls_migration_status rs
                    JOIN project_registry pr ON rs.project_id = pr.project_id
                    ORDER BY
                        CASE rs.migration_phase
                            WHEN 'pending' THEN 1
                            WHEN 'shadow' THEN 2
                            WHEN 'enforcing' THEN 3
                            WHEN 'complete' THEN 4
                        END,
                        rs.project_id
                """)

                results = []
                for row in cur.fetchall():
                    results.append({
                        "project_id": row[0],
                        "phase": row[1],
                        "rls_enabled": row[2],
                        "migrated_at": row[3],
                        "updated_at": row[4],
                        "access_level": row[5]
                    })

    except Exception as e:
        print(f"Error getting migration status: {e}")
        return []

    return results


def format_duration(updated_at: datetime) -> str:
    """Format duration since update."""
    now = datetime.now(timezone.utc)
    delta = now - updated_at
    days = delta.days
    hours = delta.seconds // 3600
    return f"{days}d {hours}h ago"


def main() -> None:
    """CLI entry point."""
    status_list = get_migration_status()

    print("\nRLS Migration Status")
    print("=" * 60)

    # Count by phase
    phase_counts = {"pending": 0, "shadow": 0, "enforcing": 0, "complete": 0}

    for status in status_list:
        phase_counts[status["phase"]] += 1

    # Print summary
    print(f"\nSummary:")
    print(f"  Pending:   {phase_counts['pending']} projects")
    print(f"  Shadow:    {phase_counts['shadow']} projects")
    print(f"  Enforcing: {phase_counts['enforcing']} projects")
    print(f"  Complete:  {phase_counts['complete']} projects")

    # Print details
    print(f"\n{'Project':<12} {'Phase':<12} {'Access':<10} {'Updated':<15}")
    print("-" * 60)

    phase_colors = {
        "pending": "\033[33m",      # Yellow
        "shadow": "\033[34m",       # Blue
        "enforcing": "\033[38;5;208m",  # Orange
        "complete": "\033[32m"      # Green
    }
    reset = "\033[0m"

    for status in status_list:
        phase = status["phase"]
        color = phase_colors.get(phase, "")
        duration = format_duration(status["updated_at"])

        print(f"{status['project_id']:<12} "
              f"{color}{phase:<12}{reset} "
              f"{status['access_level']:<10} "
              f"{duration:<15}")

    print()


if __name__ == "__main__":
    main()
