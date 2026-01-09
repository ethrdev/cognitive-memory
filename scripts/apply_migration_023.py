"""
Apply Migration 023: Add memory_strength field to l2_insights table.

Story 26.1: memory_strength for I/O's Bedeutungszuweisung
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
    migration_file = PROJECT_ROOT / "mcp_server/db/migrations/023_memory_strength.sql"

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
            logger.info("✅ Migration 023 applied successfully - memory_strength field added to l2_insights")

    except Exception as e:
        logger.error(f"❌ Migration 023 failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_migration()
