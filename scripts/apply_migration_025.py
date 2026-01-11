"""
Apply Migration 025: Create ief_feedback table for Context Critic.

Story 26.4: Context Critic
Creates ief_feedback table with insight_id, feedback_type, context, created_at columns.
Implements EP-4 (Lazy Evaluation) pattern for feedback storage.
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
    migration_file = PROJECT_ROOT / "mcp_server/db/migrations/025_ief_feedback.sql"

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
            logger.info("✅ Migration 025 applied successfully - ief_feedback table created for Context Critic")

    except Exception as e:
        logger.error(f"❌ Migration 025 failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_migration()
