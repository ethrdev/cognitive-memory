"""
Apply Migration 024: Add l2_insight_history table for audit trail.

Story 26.2: UPDATE Operation - History-on-Mutation Pattern (EP-3)
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
    migration_file = PROJECT_ROOT / "mcp_server/db/migrations/024_l2_insight_history.sql"

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
            logger.info("✅ Migration 024 applied successfully - l2_insight_history table created")

    except Exception as e:
        logger.error(f"❌ Migration 024 failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_migration()
