import os
import sys
import logging
from mcp_server.db.connection import initialize_pool, get_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def apply_migration():
    migration_file = "/home/ethr/01-projects/ai-experiments/cognitive-memory/mcp_server/db/migrations/011_io_system_metadata.sql"
    
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
            logger.info("Migration applied successfully.")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    apply_migration()
