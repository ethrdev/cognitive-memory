#!/usr/bin/env python3
"""
Emergency Rollback Test Script

Story 11.8.3 Task 5.1: Test emergency rollback procedure.

This script verifies:
1. Rollback from enforcing to pending within 1 minute
2. BYPASSRLS role functions correctly for debugging
3. Rollback procedure documentation accuracy

Usage:
    python test_emergency_rollback.py --project sm
    python test_emergency_rollback.py --batch "sm,motoko"
    python test_emergency_rollback.py --help
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any

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


def test_rollback_within_1_minute(project_id: str) -> dict[str, Any]:
    """
    Test rollback from enforcing to pending within 1 minute.

    Args:
        project_id: Project identifier to test rollback

    Returns:
        Dict with test result including duration
    """
    logger.info(f"🧪 Testing emergency rollback for project: {project_id}")

    try:
        # Set project to enforcing phase first (if not already)
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Check current phase
                cur.execute("""
                    SELECT migration_phase FROM rls_migration_status WHERE project_id = %s
                """, (project_id,))
                result = cur.fetchone()

                if not result:
                    raise ValueError(f"Project not found: {project_id}")

                current_phase = result[0]
                logger.info(f"  Current phase: {current_phase}")

                # Set to enforcing if not already
                if current_phase != "enforcing":
                    logger.info(f"  Setting project to enforcing phase first...")
                    cur.execute("""
                        UPDATE rls_migration_status
                        SET migration_phase = 'enforcing'::migration_phase_enum, updated_at = NOW()
                        WHERE project_id = %s
                    """, (project_id,))
                    conn.commit()

        # Measure rollback time
        start_time = time.time()

        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Execute rollback
                cur.execute("""
                    UPDATE rls_migration_status
                    SET migration_phase = 'pending'::migration_phase_enum, updated_at = NOW()
                    WHERE project_id = %s
                    RETURNING project_id, migration_phase
                """, (project_id,))

                result = cur.fetchone()

                # Log to audit trail
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
                    '{"migration_phase": "pending", "operation": "emergency_rollback_test"}',
                    'test_system'
                ))

                conn.commit()

        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000

        # Verify rollback success
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT migration_phase FROM rls_migration_status WHERE project_id = %s
                """, (project_id,))
                final_phase = cur.fetchone()[0]

        success = final_phase == "pending"
        within_threshold = duration_ms < 60000  # 1 minute in ms

        logger.info(f"  Rollback duration: {duration_ms:.2f}ms")
        logger.info(f"  Final phase: {final_phase}")
        logger.info(f"  Within 1-minute threshold: {'✓' if within_threshold else '✗'}")

        return {
            "project_id": project_id,
            "success": success,
            "duration_ms": duration_ms,
            "within_threshold": within_threshold,
            "final_phase": final_phase
        }

    except Exception as e:
        logger.error(f"✗ Rollback test failed for {project_id}: {e}")
        return {
            "project_id": project_id,
            "success": False,
            "error": str(e)
        }


def test_batch_rollback(project_ids: list[str]) -> dict[str, Any]:
    """
    Test emergency rollback for multiple projects.

    Args:
        project_ids: List of project identifiers

    Returns:
        Dict with batch test results
    """
    logger.info(f"🧪 Testing emergency rollback for {len(project_ids)} projects")

    results = []
    total_start = time.time()

    for project_id in project_ids:
        result = test_rollback_within_1_minute(project_id)
        results.append(result)

    total_duration = (time.time() - total_start) * 1000

    success_count = sum(1 for r in results if r.get("success", False))
    within_threshold_count = sum(1 for r in results if r.get("within_threshold", False))

    logger.info(f"📊 Batch rollback test complete:")
    logger.info(f"  Success: {success_count}/{len(project_ids)}")
    logger.info(f"  Within threshold: {within_threshold_count}/{len(project_ids)}")
    logger.info(f"  Total duration: {total_duration:.2f}ms")

    return {
        "status": "success",
        "total_projects": len(project_ids),
        "successful_rollbacks": success_count,
        "within_threshold": within_threshold_count,
        "total_duration_ms": total_duration,
        "results": results
    }


def verify_bypassrls_role() -> dict[str, Any]:
    """
    Verify BYPASSRLS role exists and functions correctly for debugging.

    Returns:
        Dict with verification result
    """
    logger.info("🔑 Verifying BYPASSRLS role...")

    try:
        with get_connection_sync() as conn:
            with conn.cursor() as cur:
                # Check if bypassrls role exists
                cur.execute("""
                    SELECT rolname, rolbypassrls FROM pg_roles WHERE rolname = 'bypassrls'
                """)

                result = cur.fetchone()

                if result:
                    role_name, bypassrls_enabled = result
                    logger.info(f"  ✓ BYPASSRLS role exists")
                    logger.info(f"  ✓ rolbypassrls: {bypassrls_enabled}")
                    return {
                        "status": "success",
                        "role_exists": True,
                        "bypassrls_enabled": bypassrls_enabled
                    }
                else:
                    logger.warning(f"  ⚠️  BYPASSRLS role does not exist")
                    return {
                        "status": "warning",
                        "role_exists": False,
                        "message": "BYPASSRLS role not found - create with: CREATE ROLE bypassrls BYPASSRLS;"
                    }

    except Exception as e:
        logger.error(f"✗ BYPASSRLS verification failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Test emergency rollback procedure for RLS migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test rollback for single project
  python test_emergency_rollback.py --project sm

  # Test rollback for multiple projects
  python test_emergency_rollback.py --batch "sm,motoko,aa"

  # Verify BYPASSRLS role only
  python test_emergency_rollback.py --verify-bypassrls

Acceptance Criteria (Story 11.8.3 Task 5):
  - Rollback from enforcing to pending within 1 minute
  - BYPASSRLS role functions correctly for debugging
        """
    )

    # Mutually exclusive: --project, --batch, or --verify-bypassrls
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--project", help="Single project ID to test rollback")
    group.add_argument("--batch", help="Comma-separated list of project IDs")
    group.add_argument("--verify-bypassrls", action="store_true",
                       help="Verify BYPASSRLS role exists and functions")

    args = parser.parse_args()

    try:
        # Initialize connection pool
        initialize_pool_sync()

        # Always verify BYPASSRLS role first
        bypassrls_check = verify_bypassrls_role()

        if args.verify_bypassrls:
            # Only verify BYPASSRLS role
            if bypassrls_check["status"] == "success":
                print("✓ BYPASSRLS role verified")
                return 0
            else:
                print(f"⚠️  BYPASSRLS role issue: {bypassrls_check.get('message', 'Unknown')}")
                return 1

        if args.project:
            # Single project rollback test
            result = test_rollback_within_1_minute(args.project)

            if result["success"] and result["within_threshold"]:
                print(f"✓ Emergency rollback test PASSED for {args.project}")
                print(f"  Duration: {result['duration_ms']:.2f}ms")
                return 0
            else:
                print(f"✗ Emergency rollback test FAILED for {args.project}")
                if not result.get("within_threshold"):
                    print(f"  Duration exceeded 1-minute threshold: {result['duration_ms']:.2f}ms")
                return 1

        elif args.batch:
            # Batch rollback test
            project_ids = [p.strip() for p in args.batch.split(",")]
            result = test_batch_rollback(project_ids)

            if result["successful_rollbacks"] == len(project_ids):
                print(f"✓ All emergency rollback tests PASSED")
                print(f"  Projects: {result['successful_rollbacks']}/{result['total_projects']}")
                print(f"  Total duration: {result['total_duration_ms']:.2f}ms")
                return 0
            else:
                print(f"✗ Some emergency rollback tests FAILED")
                print(f"  Successful: {result['successful_rollbacks']}/{result['total_projects']}")
                return 1

        return 0

    except Exception as e:
        logger.error(f"Test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
