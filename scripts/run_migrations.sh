#!/bin/bash
# Run Migrations on Production Database for Cognitive Memory System
#
# Purpose: Apply all migrations to cognitive_memory database
# Usage: ./scripts/run_migrations.sh
#
# Prerequisites:
#   - PostgreSQL server running
#   - mcp_user already created
#   - MCP_POSTGRES_PASSWORD environment variable set

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}==============================================================================${NC}"
echo -e "${CYAN}Production Database Migration Runner${NC}"
echo -e "${CYAN}==============================================================================${NC}"
echo ""

# Database configuration
DB_NAME="cognitive_memory"
DB_USER="mcp_user"
POSTGRES_USER="postgres"
MIGRATION_DIR="mcp_server/db/migrations"

# Check if PostgreSQL is running
if ! pg_isready -q; then
    echo -e "${RED}ERROR: PostgreSQL server is not running${NC}"
    echo "Please start PostgreSQL and try again"
    exit 1
fi

# Check if database exists
if ! psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${YELLOW}Database '$DB_NAME' does not exist. Creating...${NC}"
    psql -U "$POSTGRES_USER" -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
    echo -e "${GREEN}  Database '$DB_NAME' created${NC}"
fi

# Check migration directory
if [ ! -d "$MIGRATION_DIR" ]; then
    echo -e "${RED}ERROR: Migration directory not found: $MIGRATION_DIR${NC}"
    exit 1
fi

echo -e "${YELLOW}Step 1: Check pgvector Extension${NC}"
# Ensure pgvector extension is installed (requires superuser)
VECTOR_EXISTS=$(psql -U "$POSTGRES_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname='vector';" | xargs)
if [ "$VECTOR_EXISTS" -eq "0" ]; then
    echo -e "  Installing pgvector extension..."
    psql -U "$POSTGRES_USER" -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
    echo -e "${GREEN}  pgvector extension installed${NC}"
else
    echo -e "${GREEN}  pgvector extension already installed${NC}"
fi
echo ""

echo -e "${YELLOW}Step 2: Create Migration Tracking Table${NC}"
# Create migrations tracking table if not exists
psql -U "$DB_USER" -d "$DB_NAME" -c "
CREATE TABLE IF NOT EXISTS _migrations (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) UNIQUE NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);" 2>/dev/null || true
echo -e "${GREEN}  Migration tracking table ready${NC}"
echo ""

echo -e "${YELLOW}Step 3: Apply Migrations${NC}"
APPLIED=0
SKIPPED=0

# Find all migration files and run them in order
for migration in $(find "$MIGRATION_DIR" -name "*.sql" -type f | sort); do
    migration_name=$(basename "$migration")

    # Skip rollback files
    if [[ "$migration_name" == *"_rollback"* ]]; then
        echo -e "  ${CYAN}Skipping rollback file: $migration_name${NC}"
        continue
    fi

    # Check if migration already applied
    ALREADY_APPLIED=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM _migrations WHERE filename='$migration_name';" 2>/dev/null | xargs)

    if [ "$ALREADY_APPLIED" -gt "0" ]; then
        echo -e "  ${CYAN}Already applied: $migration_name${NC}"
        ((SKIPPED++))
        continue
    fi

    echo -e "  Applying migration: ${YELLOW}$migration_name${NC}"

    # Apply migration
    if psql -U "$DB_USER" -d "$DB_NAME" -f "$migration" -v ON_ERROR_STOP=1 2>&1; then
        # Record migration as applied
        psql -U "$DB_USER" -d "$DB_NAME" -c "INSERT INTO _migrations (filename) VALUES ('$migration_name');" 2>/dev/null
        echo -e "  ${GREEN}$migration_name applied${NC}"
        ((APPLIED++))
    else
        echo -e "  ${RED}FAILED: $migration_name${NC}"
        echo -e "  ${RED}Migration halted. Please fix the error and retry.${NC}"
        exit 1
    fi
done
echo ""

echo -e "${YELLOW}Step 4: Verify Schema${NC}"
echo -e "  Checking critical tables..."

# Check critical tables
TABLES=("l0_raw" "l2_insights" "working_memory" "episode_memory" "stale_memory" "nodes" "edges")
MISSING=0

for table in "${TABLES[@]}"; do
    EXISTS=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='$table';" | xargs)
    if [ "$EXISTS" -eq "1" ]; then
        echo -e "  ${GREEN}$table${NC}"
    else
        echo -e "  ${RED}$table - MISSING${NC}"
        ((MISSING++))
    fi
done

# Check vector extension
VECTOR_TYPE=$(psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM pg_type WHERE typname='vector';" | xargs)
if [ "$VECTOR_TYPE" -gt "0" ]; then
    echo -e "  ${GREEN}vector type OK${NC}"
else
    echo -e "  ${RED}vector type - MISSING${NC}"
    ((MISSING++))
fi
echo ""

echo -e "${CYAN}==============================================================================${NC}"
echo -e "${CYAN}Migration Summary${NC}"
echo -e "${CYAN}==============================================================================${NC}"
echo ""
echo -e "  Applied:  ${GREEN}$APPLIED${NC}"
echo -e "  Skipped:  ${CYAN}$SKIPPED${NC}"
if [ "$MISSING" -gt "0" ]; then
    echo -e "  Missing:  ${RED}$MISSING tables/types${NC}"
    echo ""
    echo -e "${RED}Some schema elements are missing. Check migrations and retry.${NC}"
    exit 1
else
    echo -e "  ${GREEN}All schema elements verified${NC}"
fi
echo ""
echo -e "${GREEN}Database migration complete!${NC}"
echo ""
