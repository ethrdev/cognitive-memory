#!/usr/bin/env python3
"""
Backfill Script for Story 11.1.2

Backfills NULL project_id values to 'io' for all existing data using
batched operations with keyset pagination for zero-downtime migration.

Usage:
    python scripts/backfill_project_id.py              # Run backfill
    python scripts/backfill_project_id.py --dry-run    # Simulate without changes
    python scripts/backfill_project_id.py --rollback   # Rollback backfill
    python scripts/backfill_project_id.py --help       # Show options

Story 11.1.2: Backfill Existing Data to 'io'
AC1: Null Values Backfilled to 'io' with batched operations
AC2: Edge Case Handling with anomaly logging
AC3: Constraint Validation after backfill
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import get_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# All 11 tables from Story 11.1.1 with project_id columns
TABLES_TO_BACKFILL = [
    ('l2_insights', 'id'),
    ('nodes', 'id'),
    ('edges', 'id'),
    ('working_memory', 'id'),
    ('episode_memory', 'id'),
    ('l0_raw', 'id'),
    ('ground_truth', 'id'),
    ('stale_memory', 'id'),
    ('smf_proposals', 'id'),
    ('ief_feedback', 'id'),
    ('l2_insight_history', 'id'),
]

# Constraint names from Story 11.1.1 migration
CONSTRAINTS_TO_VALIDATE = [
    ('l2_insights', 'check_l2_insights_project_id_not_null'),
    ('nodes', 'check_nodes_project_id_not_null'),
    ('edges', 'check_edges_project_id_not_null'),
    ('working_memory', 'check_working_memory_project_id_not_null'),
    ('episode_memory', 'check_episode_memory_project_id_not_null'),
    ('l0_raw', 'check_l0_raw_project_id_not_null'),
    ('ground_truth', 'check_ground_truth_project_id_not_null'),
    ('stale_memory', 'check_stale_memory_project_id_not_null'),
    ('smf_proposals', 'check_smf_proposals_project_id_not_null'),
    ('ief_feedback', 'check_ief_feedback_project_id_not_null'),
    ('l2_insight_history', 'check_l2_insight_history_project_id_not_null'),
]

# Default batch size for operations
DEFAULT_BATCH_SIZE = 5000

# Default sleep duration between batches (seconds)
DEFAULT_SLEEP_DURATION = 0.1


# =============================================================================
# Anomalies Table Management
# =============================================================================

async def create_anomalies_table(conn) -> None:
    """
    Create backfill_anomalies table if it doesn't exist (AC2).

    Args:
        conn: Database connection
    """
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS backfill_anomalies (
            id SERIAL PRIMARY KEY,
            table_name VARCHAR(100) NOT NULL,
            row_id VARCHAR(100),
            issue_description TEXT NOT NULL,
            resolved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.commit()
    cursor.close()
    logger.info("Created backfill_anomalies table")


async def log_anomaly(conn, table_name: str, row_id: str | int, issue_description: str) -> None:
    """
    Log an anomaly during backfill (AC2).

    Args:
        conn: Database connection
        table_name: Name of the table
        row_id: ID of the problematic row
        issue_description: Description of the issue
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO backfill_anomalies (table_name, row_id, issue_description)
        VALUES (%s, %s, %s)
    """, (table_name, str(row_id), issue_description))
    conn.commit()
    cursor.close()
    logger.warning(f"Anomaly logged: {table_name} row {row_id} - {issue_description}")


# =============================================================================
# Keyset Pagination Backfill (AC1)
# =============================================================================

async def backfill_table(
    conn,
    table_name: str,
    id_column: str = 'id',
    batch_size: int = DEFAULT_BATCH_SIZE,
    sleep_duration: float = DEFAULT_SLEEP_DURATION,
    dry_run: bool = False
) -> dict[str, Any]:
    """
    Backfill NULL project_id values using keyset pagination (AC1).

    Uses keyset pagination (WHERE id > last_id) instead of OFFSET
    for consistent performance regardless of offset position.

    Args:
        conn: Database connection
        table_name: Name of the table to backfill
        id_column: Primary key column for keyset pagination (default: 'id')
        batch_size: Number of rows per batch (default: 5000)
        sleep_duration: Sleep duration between batches in seconds (default: 0.1)
        dry_run: If True, simulate without making changes

    Returns:
        Dict with backfill statistics
    """
    # Validate table_name and id_column to prevent SQL injection
    valid_tables = {t[0] for t in TABLES_TO_BACKFILL}
    if table_name not in valid_tables:
        raise ValueError(f"Invalid table name: {table_name}. Must be one of {valid_tables}")

    valid_id_columns = {t[1] for t in TABLES_TO_BACKFILL if t[0] == table_name}
    if id_column not in valid_id_columns:
        raise ValueError(f"Invalid id column: {id_column} for table {table_name}")

    last_id = None
    batch_count = 0
    total_updated = 0
    total_anomalies = 0

    logger.info(f"Starting backfill for {table_name} (dry_run={dry_run})")

    while True:
        cursor = conn.cursor()

        try:
            if dry_run:
                # Dry-run mode: count NULL values to update
                if last_id is not None:
                    cursor.execute(f"""
                        SELECT COUNT(*) as count
                        FROM {table_name}
                        WHERE project_id IS NULL
                        AND {id_column} > %s
                        LIMIT %s
                    """, (last_id, batch_size))
                else:
                    cursor.execute(f"""
                        SELECT COUNT(*) as count
                        FROM {table_name}
                        WHERE project_id IS NULL
                        LIMIT %s
                    """, (batch_size,))

                result = cursor.fetchone()
                batch_updated = result['count'] if result else 0
                updated_ids = []

                # Get last_id for next iteration (even in dry-run)
                if batch_updated > 0:
                    cursor.execute(f"""
                        SELECT {id_column}
                        FROM {table_name}
                        WHERE project_id IS NULL
                        AND {id_column} > %s
                        ORDER BY {id_column} ASC
                        LIMIT 1
                    """, (last_id if last_id else 0))
                    last_id_result = cursor.fetchone()
                    if last_id_result:
                        last_id = last_id_result[id_column]
            else:
                # Normal mode: perform UPDATE with RETURNING clause
                if last_id is not None:
                    cursor.execute(f"""
                        UPDATE {table_name}
                        SET project_id = 'io'
                        WHERE ctid IN (
                            SELECT ctid FROM {table_name}
                            WHERE project_id IS NULL
                            AND {id_column} > %s
                            ORDER BY COALESCE({id_column}, 0) ASC
                            LIMIT %s
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING {id_column}
                    """, (last_id, batch_size))
                else:
                    cursor.execute(f"""
                        UPDATE {table_name}
                        SET project_id = 'io'
                        WHERE ctid IN (
                            SELECT ctid FROM {table_name}
                            WHERE project_id IS NULL
                            ORDER BY COALESCE({id_column}, 0) ASC
                            LIMIT %s
                            FOR UPDATE SKIP LOCKED
                        )
                        RETURNING {id_column}
                    """, (batch_size,))

                # Call fetchall() ONCE to get all updated row IDs
                updated_ids = [row[id_column] for row in cursor.fetchall()]
                batch_updated = len(updated_ids)

                # Get last_id for next batch (keyset pagination)
                if updated_ids:
                    last_id = updated_ids[-1]

            conn.commit()
            cursor.close()

        except Exception as e:
            # Continue-on-error pattern (AC2)
            cursor.close()
            await log_anomaly(
                conn,
                table_name,
                f"batch_{batch_count}",
                f"Batch update failed: {str(e)}"
            )
            total_anomalies += 1
            # Continue to next batch instead of aborting
            batch_count += 1
            continue

        if batch_updated == 0:
            break  # No more NULL values

        batch_count += 1
        total_updated += batch_updated

        logger.info(
            f"Backfilled {table_name} batch {batch_count}: "
            f"{batch_updated} rows"
        )

        # Optional sleep between batches for I/O pressure management (AC1)
        if sleep_duration > 0:
            await asyncio.sleep(sleep_duration)

    logger.info(
        f"Completed backfill for {table_name}: "
        f"{total_updated} rows in {batch_count} batches, "
        f"{total_anomalies} anomalies"
    )

    return {
        'table_name': table_name,
        'total_updated': total_updated,
        'batches': batch_count,
        'anomalies': total_anomalies,
    }


async def backfill_all_tables(
    conn,
    batch_size: int = DEFAULT_BATCH_SIZE,
    sleep_duration: float = DEFAULT_SLEEP_DURATION,
    dry_run: bool = False
) -> dict[str, Any]:
    """
    Backfill all 11 tables with NULL project_id values (AC1).

    Args:
        conn: Database connection
        batch_size: Number of rows per batch (default: 5000)
        sleep_duration: Sleep duration between batches (default: 0.1)
        dry_run: If True, simulate without making changes

    Returns:
        Dict with overall backfill statistics
    """
    start_time = time.time()
    total_updated = 0
    total_anomalies = 0
    table_results = []

    # Create anomalies table first (AC2)
    await create_anomalies_table(conn)

    for table_name, id_column in TABLES_TO_BACKFILL:
        try:
            result = await backfill_table(
                conn,
                table_name,
                id_column,
                batch_size,
                sleep_duration,
                dry_run
            )
            table_results.append(result)
            total_updated += result['total_updated']
            total_anomalies += result['anomalies']

        except Exception as e:
            # Continue-on-error pattern (AC2)
            logger.error(f"Failed to backfill {table_name}: {e}")
            await log_anomaly(
                conn,
                table_name,
                "table_level",
                f"Table backfill failed: {str(e)}"
            )
            total_anomalies += 1

    processing_time = time.time() - start_time

    # Summary statistics (AC2)
    summary = {
        'processed_tables': len(table_results),
        'total_updated': total_updated,
        'total_anomalies': total_anomalies,
        'processing_time': processing_time,
        'table_results': table_results,
    }

    logger.info("=" * 70)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Tables processed: {summary['processed_tables']}")
    logger.info(f"Total rows updated: {summary['total_updated']}")
    logger.info(f"Total anomalies: {summary['total_anomalies']}")
    logger.info(f"Processing time: {processing_time:.2f} seconds")
    logger.info("=" * 70)

    return summary


# =============================================================================
# Constraint Validation (AC3)
# =============================================================================

async def validate_all_constraints(conn) -> dict[str, Any]:
    """
    Validate NOT NULL constraints after backfill (AC3).

    After all NULL values are backfilled to 'io', we can validate
    the NOT VALID constraints created in Story 11.1.1.

    Args:
        conn: Database connection

    Returns:
        Dict with validation results
    """
    logger.info("Starting constraint validation...")
    validation_results = []
    failed_validations = []

    for table_name, constraint_name in CONSTRAINTS_TO_VALIDATE:
        try:
            cursor = conn.cursor()
            # Validate the constraint
            cursor.execute(
                f"ALTER TABLE {table_name} VALIDATE CONSTRAINT {constraint_name}"
            )
            conn.commit()
            cursor.close()

            logger.info(f"Validated constraint: {constraint_name}")
            validation_results.append({
                'table': table_name,
                'constraint': constraint_name,
                'status': 'validated'
            })

        except Exception as e:
            logger.error(f"Failed to validate {constraint_name}: {e}")
            failed_validations.append({
                'table': table_name,
                'constraint': constraint_name,
                'error': str(e)
            })
            validation_results.append({
                'table': table_name,
                'constraint': constraint_name,
                'status': 'failed',
                'error': str(e)
            })

    logger.info("=" * 70)
    logger.info("CONSTRAINT VALIDATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Constraints validated: {len(validation_results) - len(failed_validations)}")
    logger.info(f"Constraints failed: {len(failed_validations)}")

    if failed_validations:
        logger.error("Failed validations:")
        for failure in failed_validations:
            logger.error(f"  - {failure['constraint']}: {failure['error']}")

    logger.info("=" * 70)

    return {
        'total_constraints': len(CONSTRAINTS_TO_VALIDATE),
        'validated': len(validation_results) - len(failed_validations),
        'failed': len(failed_validations),
        'results': validation_results,
    }


# =============================================================================
# Rollback Support (Task 5 - DoD)
# =============================================================================

async def rollback_backfill(
    conn,
    tables: list[str] | None = None
) -> dict[str, Any]:
    """
    Rollback backfill by setting project_id back to NULL (Task 5 - DoD).

    WARNING: Only safe before constraint validation. After validation,
    rollback requires dropping constraints first.

    Args:
        conn: Database connection
        tables: List of tables to rollback (None = all tables)

    Returns:
        Dict with rollback results
    """
    if tables is None:
        tables = [t[0] for t in TABLES_TO_BACKFILL]

    logger.warning("=" * 70)
    logger.warning("ROLLBACK MODE - Setting project_id back to NULL")
    logger.warning("=" * 70)

    rollback_results = []
    total_rolled_back = 0

    for table_name in tables:
        try:
            cursor = conn.cursor()
            # Set project_id back to NULL
            cursor.execute(f"""
                UPDATE {table_name}
                SET project_id = NULL
                WHERE project_id = 'io'
            """)
            conn.commit()
            rows_affected = cursor.rowcount
            cursor.close()

            total_rolled_back += rows_affected

            logger.info(f"Rolled back {table_name}: {rows_affected} rows")
            rollback_results.append({
                'table': table_name,
                'rows_rolled_back': rows_affected,
                'status': 'success'
            })

        except Exception as e:
            logger.error(f"Failed to rollback {table_name}: {e}")
            rollback_results.append({
                'table': table_name,
                'status': 'failed',
                'error': str(e)
            })

    logger.info("=" * 70)
    logger.info("ROLLBACK SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Total rows rolled back: {total_rolled_back}")
    logger.info("=" * 70)

    return {
        'total_rolled_back': total_rolled_back,
        'results': rollback_results,
    }


# =============================================================================
# CLI Interface
# =============================================================================

def parse_args():
    """Parse command-line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill NULL project_id values to 'io' for Epic 11 namespace isolation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run backfill on all tables
    python scripts/backfill_project_id.py

    # Simulate backfill without making changes
    python scripts/backfill_project_id.py --dry-run

    # Rollback backfill (only safe before constraint validation)
    python scripts/backfill_project_id.py --rollback

    # Validate constraints after backfill
    python scripts/backfill_project_id.py --validate-only

Notes:
    - Uses keyset pagination for consistent performance
    - Default batch size: 5000 rows
    - Default sleep between batches: 0.1 seconds
    - Anomalies are logged to backfill_anomalies table
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate backfill without making changes'
    )

    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback backfill by setting project_id back to NULL'
    )

    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate constraints, skip backfill'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f'Number of rows per batch (default: {DEFAULT_BATCH_SIZE})'
    )

    parser.add_argument(
        '--sleep',
        type=float,
        default=DEFAULT_SLEEP_DURATION,
        help=f'Sleep duration between batches in seconds (default: {DEFAULT_SLEEP_DURATION})'
    )

    return parser.parse_args()


async def main_async():
    """Main async entry point."""
    args = parse_args()

    logger.info("=" * 70)
    logger.info("BACKFILL SCRIPT - Story 11.1.2")
    logger.info("=" * 70)

    # Get connection from pool
    async with get_connection() as conn:
        # Rollback mode
        if args.rollback:
            logger.warning("Running in ROLLBACK mode")
            result = await rollback_backfill(conn)
            return 0 if result['total_rolled_back'] >= 0 else 1

        # Validate only mode
        if args.validate_only:
            logger.info("Running in VALIDATE-ONLY mode")
            result = await validate_all_constraints(conn)
            return 0 if result['failed'] == 0 else 1

        # Normal backfill mode
        if args.dry_run:
            logger.info("Running in DRY-RUN mode (no changes will be made)")

        logger.info("Running backfill...")

        # Step 1: Backfill all tables
        backfill_result = await backfill_all_tables(
            conn,
            batch_size=args.batch_size,
            sleep_duration=args.sleep,
            dry_run=args.dry_run
        )

        # Step 2: Validate constraints (skip in dry-run)
        if not args.dry_run:
            validation_result = await validate_all_constraints(conn)

            if validation_result['failed'] > 0:
                logger.error("Some constraints failed validation")
                return 1
        else:
            logger.info("Skipping constraint validation in dry-run mode")

        logger.info("=" * 70)
        logger.info("BACKFILL COMPLETE")
        logger.info("=" * 70)

        return 0


def main():
    """Main entry point for script."""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
