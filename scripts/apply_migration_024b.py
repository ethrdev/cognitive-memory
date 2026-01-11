"""
Apply Migration 024b: Add version_id to l2_insight_history table.

Story 26.7: Revision History - Chronological version queries
Extends Migration 024 with version_id for chronological history retrieval.
"""
import os
import sys
import logging
from pathlib import Path

from mcp_server.db.connection import initialize_pool, get_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Resolve paths relative to project root
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent


def apply_migration():
    """Apply Migration 024b to add version_id column for Story 26.7."""
    migration_file = PROJECT_ROOT / "mcp_server/db/migrations/024b_add_version_id_to_l2_insight_history.sql"

    if not os.path.exists(migration_file):
        logger.error(f"Migration file not found: {migration_file}")
        sys.exit(1)

    try:
        # Read SQL
        with open(migration_file, 'r') as f:
            sql = f.read()

        # Initialize pool
        initialize_pool()

        # Execute SQL
        with get_connection() as conn:
            cursor = conn.cursor()
            logger.info(f"Applying migration: {migration_file}")
            cursor.execute(sql)
            conn.commit()
            logger.info("✅ Migration 024b applied successfully - version_id column added to l2_insight_history")

            # Verification queries
            logger.info("Verifying migration...")

            # Check version_id column exists
            cursor.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'l2_insight_history' AND column_name = 'version_id'
                """
            )
            version_id_col = cursor.fetchone()

            if version_id_col:
                logger.info(f"  ✓ version_id column exists ({version_id_col[1]})")
            else:
                logger.warning("  ⚠ version_id column not found!")

            # Check index exists
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'l2_insight_history'
                  AND indexname = 'idx_l2_insight_history_version'
                """
            )
            index_exists = cursor.fetchone()

            if index_exists:
                logger.info(f"  ✓ Index {index_exists[0]} exists for chronological queries")
            else:
                logger.warning("  ⚠ Index idx_l2_insight_history_version not found!")

            # Check trigger exists
            cursor.execute(
                """
                SELECT trigger_name
                FROM information_schema.triggers
                WHERE trigger_name = 'trigger_l2_insight_history_version'
                """
            )
            trigger_exists = cursor.fetchone()

            if trigger_exists:
                logger.info(f"  ✓ Trigger {trigger_exists[0]} exists for auto-increment")
            else:
                logger.warning("  ⚠ Trigger trigger_l2_insight_history_version not found!")

        logger.info("✅ Migration 024b verification complete")

    except Exception as e:
        logger.error(f"❌ Migration 024b failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    apply_migration()
