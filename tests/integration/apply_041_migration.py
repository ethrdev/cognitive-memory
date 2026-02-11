"""
Script to apply migration 041 without CONCURRENTLY (for testing only).

IMPORTANT: This is a TEST-ONLY helper script.
In production, use 041_add_tags.sql with CONCURRENTLY for zero-downtime deployment.

This script exists because:
1. CREATE INDEX CONCURRENTLY cannot run inside a transaction block
2. Test fixtures wrap tests in transactions with auto-rollback
3. For testing, we accept regular CREATE INDEX since we control the database

Usage:
    python tests/integration/apply_041_migration.py

This script should ONLY be used in test/development environments.
"""

from dotenv import load_dotenv
load_dotenv('.env.development')

import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def apply_migration():
    """Apply migration 041 without CONCURRENTLY for testing."""
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # Phase 1: Add columns to episode_memory
    print("Phase 1: Adding columns to episode_memory...")

    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'episode_memory' AND column_name = 'tags'
            ) THEN
                ALTER TABLE episode_memory ADD COLUMN tags TEXT[] DEFAULT '{}';
            END IF;
        END $$;
    """)

    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'episode_memory' AND column_name = 'metadata'
            ) THEN
                ALTER TABLE episode_memory ADD COLUMN metadata JSONB DEFAULT '{}';
            END IF;
        END $$;
    """)

    # Phase 2: Add tags column to l2_insights
    print("Phase 2: Adding tags column to l2_insights...")
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'l2_insights' AND column_name = 'tags'
            ) THEN
                ALTER TABLE l2_insights ADD COLUMN tags TEXT[] DEFAULT '{}';
            END IF;
        END $$;
    """)

    # Phase 3: Create indexes (without CONCURRENTLY for testing)
    print("Phase 3: Creating GIN indexes...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_episode_memory_tags
        ON episode_memory USING gin(tags);
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_l2_insights_tags
        ON l2_insights USING gin(tags);
    """)

    # Verify
    cur.execute("SELECT COUNT(*) FROM pg_indexes WHERE indexname LIKE '%_tags'")
    index_count = cur.fetchone()[0]
    print(f"✅ Migration complete! {index_count} indexes created.")

    cur.execute("""
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_name IN ('episode_memory', 'l2_insights')
        AND column_name = 'tags'
    """)
    column_count = cur.fetchone()[0]
    print(f"✅ {column_count} tags columns created.")

    conn.close()

if __name__ == "__main__":
    apply_migration()
