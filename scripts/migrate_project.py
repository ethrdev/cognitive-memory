#!/usr/bin/env python3
"""
Migrate Project RLS Phase CLI Tool

Story 11.8.1: CLI tool for migrating projects through RLS phases.

Usage:
    python migrate_project.py --project sm --phase shadow
    python migrate_project.py --batch "sm,motoko" --phase shadow
    python migrate_project.py --project aa --phase pending  # Rollback

Phases: pending -> shadow -> enforcing -> complete
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC
from typing import Literal, Any

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import initialize_pool_sync, get_connection_sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

MigrationPhase = Literal["pending", "shadow", "enforcing", "complete"]


def validate_phase(phase: str) -> MigrationPhase:
    """Validate phase parameter."""
    valid_phases: list[MigrationPhase] = ["pending", "shadow", "enforcing", "complete"]
    if phase not in valid_phases:
        raise ValueError(f"Invalid phase: {phase}. Must be one of: {', '.join(valid_phases)}")
    return phase  # type: ignore[return-value]


def migrate_project(project_id: str, target_phase: MigrationPhase) -> dict[str, Any]:
    """
    Migrate a single project to a new RLS phase.

    Args:
        project_id: Project identifier (e.g., 'sm', 'aa', 'io')
        target_phase: Target migration phase (pending, shadow, enforcing, complete)

    Returns:
        Dict with migration result: {'status': 'success', 'project_id': ..., 'phase': ...}

    Raises:
        ValueError: If project_id not found or phase is invalid
    """
    target_phase = validate_phase(target_phase)

    try:
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Update migration status
                cur.execute("""
                    UPDATE rls_migration_status
                    SET migration_phase = %s::migration_phase_enum,
                        updated_at = NOW(),
                        migrated_at = CASE WHEN %s = 'complete' THEN NOW() ELSE migrated_at END
                    WHERE project_id = %s
                    RETURNING project_id, migration_phase, rls_enabled
                """, (target_phase, target_phase, project_id))

                result = cur.fetchone()
                if not result:
                    raise ValueError(f"Project not found: {project_id}")

                # Log migration operation to audit trail
                cur.execute("""
                    INSERT INTO rls_audit_log (
                        project_id, table_name, operation, row_project_id,
                        would_be_denied, new_data, session_user_name
                    ) VALUES (
                        %s, 'rls_migration_status', 'UPDATE', %s,
                        FALSE, %s::jsonb, %s
                    )
                """, (
                    project_id,
                    project_id,
                    '{"migration_phase": "%s", "operation": "migration"}' % target_phase,
                    'system'
                ))

                conn.commit()

                logger.info(f"✓ Project {project_id} migrated to phase: {target_phase}")

                return {
                    "status": "success",
                    "project_id": result[0],
                    "phase": result[1],
                    "rls_enabled": result[2]
                }
    except Exception as e:
        logger.error(f"✗ Failed to migrate project {project_id}: {e}")
        raise


def mark_migration_complete(all_projects: bool = True) -> dict[str, Any]:
    """
    Mark all projects as 'complete' phase with final migration summary.

    Story 11.8.3 Task 4: Complete phase transition.

    This function:
    1. Sets migration_phase = 'complete' for all projects
    2. Records migrated_at timestamps
    3. Generates final migration summary report

    Args:
        all_projects: If True, mark all projects. If False, only mark enforcing projects.

    Returns:
        Dict with completion summary and report

    Raises:
        ValueError: If no projects found or database error
    """
    try:
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Get current status before marking complete
                cur.execute("""
                    SELECT project_id, migration_phase, rls_enabled, migrated_at
                    FROM rls_migration_status
                    ORDER BY project_id
                """)
                before_status = cur.fetchall()

                if not before_status:
                    raise ValueError("No projects found in rls_migration_status")

                # Check which projects are in enforcing phase
                enforcing_projects = [r[0] for r in before_status if r[1] == "enforcing"]
                non_enforcing = [r[0] for r in before_status if r[1] != "enforcing"]

                if non_enforcing and all_projects:
                    logger.warning(f"⚠️  Warning: {len(non_enforcing)} projects not in enforcing phase: {non_enforcing}")

                # Update all projects to complete
                cur.execute("""
                    UPDATE rls_migration_status
                    SET migration_phase = 'complete'::migration_phase_enum,
                        updated_at = NOW(),
                        migrated_at = CASE
                            WHEN migrated_at IS NULL THEN NOW()
                            ELSE migrated_at
                        END
                    WHERE migration_phase = 'enforcing' OR %s
                    RETURNING project_id, migration_phase, migrated_at
                """, (all_projects,))

                results = cur.fetchall()

                # Generate summary report
                total_projects = len(results)
                complete_projects = [r[0] for r in results]

                # Log to audit trail
                for project_id in complete_projects:
                    cur.execute("""
                        INSERT INTO rls_audit_log (
                            project_id, table_name, operation, row_project_id,
                            would_be_denied, new_data, session_user_name
                        ) VALUES (
                            %s, 'rls_migration_status', 'UPDATE', %s,
                            FALSE, %s::jsonb, %s
                        )
                    """, (
                        project_id,
                        project_id,
                        '{"migration_phase": "complete", "operation": "final_migration_complete"}',
                        'system'
                    ))

                conn.commit()

                logger.info(f"✓ Marked {total_projects} projects as complete")
                for project_id in complete_projects:
                    logger.info(f"  - {project_id}: complete")

                # Get migration statistics
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(CASE WHEN rls_enabled THEN 1 END) as rls_enabled_count,
                        COUNT(CASE WHEN migrated_at IS NOT NULL THEN 1 END) as migrated_count
                    FROM rls_migration_status
                """)
                stats = cur.fetchone()

                summary = {
                    "status": "success",
                    "timestamp": str(UTC.now()),
                    "projects_marked_complete": complete_projects,
                    "total_projects": total_projects,
                    "migration_complete": True,
                    "statistics": {
                        "total_projects": stats[0],
                        "rls_enabled": stats[1],
                        "migrated_count": stats[2]
                    }
                }

                logger.info("📊 Migration Summary:")
                logger.info(f"  Total projects: {summary['statistics']['total_projects']}")
                logger.info(f"  RLS enabled: {summary['statistics']['rls_enabled']}")
                logger.info(f"  Migrated: {summary['statistics']['migrated_count']}")
                logger.info("✅ Epic 11 RLS Migration COMPLETE!")

                return summary

    except Exception as e:
        logger.error(f"✗ Failed to mark migration complete: {e}")
        raise


def migrate_batch(project_ids: list[str], target_phase: MigrationPhase) -> dict[str, Any]:
    """
    Migrate multiple projects to a new RLS phase in a single transaction.

    If any project migration fails, the entire transaction is rolled back.

    Args:
        project_ids: List of project identifiers
        target_phase: Target migration phase

    Returns:
        Dict with batch migration result
    """
    target_phase = validate_phase(target_phase)

    try:
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                results = []

                for project_id in project_ids:
                    cur.execute("""
                        UPDATE rls_migration_status
                        SET migration_phase = %s::migration_phase_enum,
                            updated_at = NOW(),
                            migrated_at = CASE WHEN %s = 'complete' THEN NOW() ELSE migrated_at END
                        WHERE project_id = %s
                        RETURNING project_id, migration_phase
                    """, (target_phase, target_phase, project_id))

                    result = cur.fetchone()
                    if not result:
                        raise ValueError(f"Project not found: {project_id}")

                    # Log each project migration to audit trail
                    cur.execute("""
                        INSERT INTO rls_audit_log (
                            project_id, table_name, operation, row_project_id,
                            would_be_denied, new_data, session_user_name
                        ) VALUES (
                            %s, 'rls_migration_status', 'UPDATE', %s,
                            FALSE, %s::jsonb, %s
                        )
                    """, (
                        project_id,
                        project_id,
                        '{"migration_phase": "%s", "operation": "batch_migration"}' % target_phase,
                        'system'
                    ))

                    results.append({"project_id": result[0], "phase": result[1]})

                # All successful - commit transaction
                conn.commit()

                logger.info(f"✓ Batch migration complete: {len(results)} projects to phase {target_phase}")

                return {
                    "status": "success",
                    "count": len(results),
                    "phase": target_phase,
                    "projects": results
                }

    except Exception as e:
        # Transaction automatically rolled back on error
        logger.error(f"✗ Batch migration failed: {e}")
        logger.error("Transaction rolled back - no projects were migrated")
        return {
            "status": "error",
            "error": str(e)
        }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate project RLS phase for gradual rollout",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Migrate single project to shadow phase
  python migrate_project.py --project sm --phase shadow

  # Migrate to enforcing (RLS active)
  python migrate_project.py --project aa --phase enforcing

  # Mark migration complete (all enforcing projects)
  python migrate_project.py --complete

  # Mark migration complete (all projects regardless of phase)
  python migrate_project.py --complete --all

  # Rollback to pending (emergency)
  python migrate_project.py --project aa --phase pending

  # Batch migrate multiple projects
  python migrate_project.py --batch "sm,motoko" --phase shadow

Phases:
  pending    - RLS not enforced (legacy behavior)
  shadow     - Audit only (logs violations, no blocking)
  enforcing  - RLS active (blocks unauthorized access)
  complete   - Migration stable (same as enforcing)
        """
    )

    # Mutually exclusive: --project, --batch, or --complete
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="Single project ID to migrate")
    group.add_argument("--batch", help="Comma-separated list of project IDs")
    group.add_argument("--complete", action="store_true",
                       help="Mark all projects as 'complete' phase (Story 11.8.3 Task 4)")

    parser.add_argument(
        "--phase",
        choices=["pending", "shadow", "enforcing", "complete"],
        help="Target migration phase (required with --project or --batch)"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Include all projects regardless of current phase (only with --complete)"
    )

    args = parser.parse_args()

    try:
        # Initialize connection pool
        initialize_pool_sync()

        if args.complete:
            # Mark all projects as complete
            result = mark_migration_complete(all_projects=args.all)
            print(f"✓ Migration complete!")
            print(f"  Projects marked complete: {', '.join(result['projects_marked_complete'])}")
            print(f"  Total projects: {result['statistics']['total_projects']}")
            print(f"  RLS enabled: {result['statistics']['rls_enabled']}")
            print("✅ Epic 11 RLS Migration COMPLETE!")

        elif args.project:
            # Single project migration
            if not args.phase:
                parser.error("--project requires --phase")
            result = migrate_project(args.project, args.phase)
            print(f"✓ Migrated {result['project_id']} to phase: {result['phase']}")

        elif args.batch:
            # Batch migration
            if not args.phase:
                parser.error("--batch requires --phase")
            project_ids = [p.strip() for p in args.batch.split(",")]
            result = migrate_batch(project_ids, args.phase)

            if result["status"] == "success":
                print(f"✓ Migrated {result['count']} projects to phase: {result['phase']}")
                for p in result["projects"]:
                    print(f"  - {p['project_id']}: {p['phase']}")
            else:
                print(f"✗ Batch migration failed: {result['error']}")
                return 1

        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
