#!/usr/bin/env python3
"""
Enforcing Phase Activation Script

Story 11.8.3: CLI tool for activating enforcing phase for projects.

Usage:
    python activate_enforcing.py --project sm --dry-run
    python activate_enforcing.py --project sm
    python activate_enforcing.py --batch "sm,motoko" --phase enforcing
    python activate_enforcing.py --project sm --rollback

Exit Criteria (must ALL pass):
    - Zero violations in rls_audit_log (would_be_denied = FALSE for all)
    - Minimum 7 days in shadow phase
    - Minimum 1000 tool calls processed

Migration Sequence (from Story 11.8.2):
    Batch 1: sm (LOW risk)
    Batch 2: motoko (LOW risk)
    Batch 3: ab, aa, bap (MEDIUM risk)
    Batch 4: echo, ea (MEDIUM risk)
    Batch 5: io (HIGH risk - super, legacy)
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import get_connection_sync, initialize_pool_sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

MigrationPhase = Literal["pending", "shadow", "enforcing", "complete"]

# Exit Criteria Thresholds (from Story 11.8.2)
MIN_SHADOW_DAYS = 7
MIN_TRANSACTIONS = 1000


@dataclass
class EligibilityCheck:
    """Result of eligibility check for a project."""
    project_id: str
    eligible: bool
    shadow_days: int
    transaction_count: int
    violation_count: int
    reasons: list[str]


def validate_phase(phase: str) -> MigrationPhase:
    """Validate phase parameter."""
    valid_phases: list[MigrationPhase] = ["pending", "shadow", "enforcing", "complete"]
    if phase not in valid_phases:
        raise ValueError(f"Invalid phase: {phase}. Must be one of: {', '.join(valid_phases)}")
    return phase  # type: ignore[return-value]


def check_eligibility(project_id: str) -> EligibilityCheck:
    """
    Check if project meets exit criteria for enforcing activation.

    Args:
        project_id: Project identifier

    Returns:
        EligibilityCheck with eligibility status and details

    Raises:
        ValueError: If project_id not found
    """
    try:
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Get project migration status
                cur.execute("""
                    SELECT migration_phase, updated_at
                    FROM rls_migration_status
                    WHERE project_id = %s
                """, (project_id,))

                result = cur.fetchone()
                if not result:
                    raise ValueError(f"Project not found: {project_id}")

                current_phase, updated_at = result

                if current_phase != "shadow":
                    return EligibilityCheck(
                        project_id=project_id,
                        eligible=False,
                        shadow_days=0,
                        transaction_count=0,
                        violation_count=0,
                        reasons=[f"Current phase is '{current_phase}', must be 'shadow'"]
                    )

                # Calculate shadow duration in days
                shadow_duration = datetime.now(UTC) - updated_at
                shadow_days = shadow_duration.days

                # Count violations
                cur.execute("""
                    SELECT COUNT(*)
                    FROM rls_audit_log
                    WHERE project_id = %s AND would_be_denied = TRUE
                """, (project_id,))
                violation_count = cur.fetchone()[0]

                # Count transactions (all audit log entries since shadow started)
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

                return EligibilityCheck(
                    project_id=project_id,
                    eligible=eligible,
                    shadow_days=shadow_days,
                    transaction_count=transaction_count,
                    violation_count=violation_count,
                    reasons=reasons
                )

    except Exception as e:
        logger.error(f"Failed to check eligibility for {project_id}: {e}")
        raise


def activate_enforcing(
    project_id: str,
    dry_run: bool = False
) -> dict[str, Any]:
    """
    Activate enforcing phase for a single project.

    Args:
        project_id: Project identifier
        dry_run: If True, check eligibility without modifying database

    Returns:
        Dict with activation result

    Raises:
        ValueError: If project not eligible or other validation fails
    """
    # Check eligibility first
    eligibility = check_eligibility(project_id)

    if not eligibility.eligible:
        error_msg = f"Project {project_id} not eligible for enforcing phase:\n"
        for reason in eligibility.reasons:
            error_msg += f"  - {reason}\n"
        raise ValueError(error_msg)

    if dry_run:
        logger.info(f"[DRY-RUN] Would activate {project_id} for enforcing phase")
        return {
            "status": "dry-run",
            "project_id": project_id,
            "eligible": True,
            "check_details": {
                "shadow_days": eligibility.shadow_days,
                "transactions": eligibility.transaction_count,
                "violations": eligibility.violation_count
            }
        }

    try:
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Update migration status to enforcing
                cur.execute("""
                    UPDATE rls_migration_status
                    SET migration_phase = 'enforcing'::migration_phase_enum,
                        updated_at = NOW()
                    WHERE project_id = %s
                    RETURNING project_id, migration_phase
                """, (project_id,))

                result = cur.fetchone()
                if not result:
                    raise ValueError(f"Project not found: {project_id}")

                conn.commit()

                logger.info(f"Project {project_id} activated for enforcing phase")

                return {
                    "status": "success",
                    "project_id": result[0],
                    "phase": result[1]
                }

    except Exception as e:
        logger.error(f"Failed to activate enforcing for {project_id}: {e}")
        raise


def activate_batch(
    project_ids: list[str],
    dry_run: bool = False
) -> dict[str, Any]:
    """
    Activate enforcing phase for multiple projects in sequence.

    If any project activation fails, the process stops.

    Args:
        project_ids: List of project identifiers
        dry_run: If True, check eligibility without modifying database

    Returns:
        Dict with batch activation result
    """
    results = []
    failures = []

    for project_id in project_ids:
        try:
            result = activate_enforcing(project_id, dry_run=dry_run)
            results.append({
                "project_id": project_id,
                "status": result.get("status", "success")
            })
        except Exception as e:
            logger.error(f"Failed to activate {project_id}: {e}")
            failures.append({
                "project_id": project_id,
                "error": str(e)
            })
            # Stop on first failure for batch activation
            break

    if failures:
        return {
            "status": "partial_failure",
            "activated": results,
            "failed": failures
        }

    return {
        "status": "success",
        "count": len(results),
        "projects": results
    }


def rollback_project(
    project_id: str,
    dry_run: bool = False
) -> dict[str, Any]:
    """
    Rollback a project from enforcing to pending phase.

    This is the emergency rollback procedure for when issues are detected
    in enforcing mode.

    Args:
        project_id: Project identifier
        dry_run: If True, show what would happen without modifying database

    Returns:
        Dict with rollback result
    """
    if dry_run:
        logger.info(f"[DRY-RUN] Would rollback {project_id} to pending phase")
        return {
            "status": "dry-run",
            "project_id": project_id,
            "target_phase": "pending"
        }

    try:
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Rollback to pending
                cur.execute("""
                    UPDATE rls_migration_status
                    SET migration_phase = 'pending'::migration_phase_enum,
                        updated_at = NOW()
                    WHERE project_id = %s
                    RETURNING project_id, migration_phase
                """, (project_id,))

                result = cur.fetchone()
                if not result:
                    raise ValueError(f"Project not found: {project_id}")

                conn.commit()

                logger.info(f"Project {project_id} rolled back to pending phase")

                return {
                    "status": "success",
                    "project_id": result[0],
                    "phase": result[1]
                }

    except Exception as e:
        logger.error(f"Failed to rollback {project_id}: {e}")
        raise


def rollback_batch(
    project_ids: list[str],
    dry_run: bool = False
) -> dict[str, Any]:
    """
    Rollback multiple projects from enforcing to pending phase.

    Args:
        project_ids: List of project identifiers
        dry_run: If True, show what would happen without modifying database

    Returns:
        Dict with batch rollback result
    """
    results = []

    for project_id in project_ids:
        try:
            result = rollback_project(project_id, dry_run=dry_run)
            results.append({
                "project_id": project_id,
                "status": result.get("status", "success")
            })
        except Exception as e:
            logger.error(f"Failed to rollback {project_id}: {e}")
            results.append({
                "project_id": project_id,
                "status": "error",
                "error": str(e)
            })

    return {
        "status": "success",
        "count": len(results),
        "projects": results
    }


def print_eligibility(eligibility: EligibilityCheck) -> None:
    """Print formatted eligibility check result."""
    print(f"\nProject: {eligibility.project_id}")
    print(f"Status: {'\u2713 ELIGIBLE' if eligibility.eligible else '\u2717 NOT ELIGIBLE'}")

    print("\nMetrics:")
    print(f"  Days in Shadow: {eligibility.shadow_days}")
    print(f"  Transaction Count: {eligibility.transaction_count}")
    print(f"  Violation Count: {eligibility.violation_count}")

    print("\nExit Criteria:")
    for reason in eligibility.reasons:
        print(f"  \u2022 {reason}")


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Activate enforcing phase for RLS migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit Criteria (all must pass):
  - Minimum 7 days in shadow phase
  - Minimum 1000 transactions processed
  - Zero violations in rls_audit_log

Migration Sequence (recommended order):
  Batch 1: sm (LOW risk)
  Batch 2: motoko (LOW risk)
  Batch 3: ab, aa, bap (MEDIUM risk)
  Batch 4: echo, ea (MEDIUM risk)
  Batch 5: io (HIGH risk)

Examples:
  # Check eligibility without activating
  python activate_enforcing.py --project sm --dry-run

  # Activate single project
  python activate_enforcing.py --project sm

  # Activate batch of projects
  python activate_enforcing.py --batch "sm,motoko"

  # Rollback to pending (emergency)
  python activate_enforcing.py --project sm --rollback

  # Rollback batch
  python activate_enforcing.py --batch "sm,motoko" --rollback
        """
    )

    # Mutually exclusive: --project or --batch
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="Single project ID to activate/rollback")
    group.add_argument("--batch", help="Comma-separated list of project IDs")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check eligibility without modifying database"
    )

    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback from enforcing to pending phase"
    )

    args = parser.parse_args()

    try:
        # Initialize connection pool
        initialize_pool_sync()

        if args.rollback:
            # Rollback mode
            if args.project:
                result = rollback_project(args.project, dry_run=args.dry_run)
                if result["status"] != "dry-run":
                    print(f"\u2713 Rolled back {result['project_id']} to phase: {result['phase']}")
            elif args.batch:
                project_ids = [p.strip() for p in args.batch.split(",")]
                result = rollback_batch(project_ids, dry_run=args.dry_run)
                if result["status"] == "success":
                    print(f"\u2713 Rolled back {result['count']} projects to pending phase")
                    for p in result["projects"]:
                        print(f"  - {p['project_id']}: {p['status']}")
        else:
            # Activation mode
            if args.project:
                # Check eligibility first
                eligibility = check_eligibility(args.project)
                print_eligibility(eligibility)

                if not eligibility.eligible:
                    return 1

                result = activate_enforcing(args.project, dry_run=args.dry_run)
                if result["status"] != "dry-run":
                    print(f"\u2713 Activated {result['project_id']} for enforcing phase")

            elif args.batch:
                project_ids = [p.strip() for p in args.batch.split(",")]

                # Check eligibility for all projects first
                print(f"\nChecking eligibility for {len(project_ids)} projects...")
                all_eligible = True
                for project_id in project_ids:
                    eligibility = check_eligibility(project_id)
                    print_eligibility(eligibility)
                    if not eligibility.eligible:
                        all_eligible = False
                        print(f"\n\u2717 {project_id} is not eligible - stopping batch")
                        return 1
                    print()

                if not all_eligible:
                    return 1

                result = activate_batch(project_ids, dry_run=args.dry_run)
                if result["status"] == "success":
                    print(f"\u2713 Activated {result['count']} projects for enforcing phase")
                    for p in result["projects"]:
                        print(f"  - {p['project_id']}: {p['status']}")
                elif result["status"] == "partial_failure":
                    print("\u2717 Batch activation partially failed:")
                    for f in result.get("failed", []):
                        print(f"  - {f['project_id']}: {f.get('error', 'Unknown error')}")
                    return 1

        return 0

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Activation failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
