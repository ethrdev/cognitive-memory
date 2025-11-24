#!/bin/bash
# Setup Development Database for Cognitive Memory System
# Story 3.7: Production Configuration & Environment Setup
#
# Purpose: Create and configure cognitive_memory_dev database
# Usage: ./scripts/setup_dev_database.sh
#
# Prerequisites:
#   - PostgreSQL server running
#   - mcp_user already created (from Story 1.2)
#   - Migrations in mcp_server/db/migrations/

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}Development Database Setup${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""

# Database configuration
DEV_DB="cognitive_memory_dev"
PROD_DB="cognitive_memory"
DB_USER="mcp_user"
POSTGRES_USER="postgres"

# Check if PostgreSQL is running
if ! pg_isready -q; then
    echo -e "${RED}ERROR: PostgreSQL server is not running${NC}"
    echo "Please start PostgreSQL and try again"
    exit 1
fi

echo -e "${YELLOW}Step 1: Create Development Database${NC}"
# Check if database exists
if psql -U "$POSTGRES_USER" -lqt | cut -d \| -f 1 | grep -qw "$DEV_DB"; then
    echo -e "  Database '$DEV_DB' already exists"
else
    echo -e "  Creating database '$DEV_DB'..."
    psql -U "$POSTGRES_USER" -c "CREATE DATABASE $DEV_DB OWNER $DB_USER;"
    echo -e "${GREEN}  ✓ Database '$DEV_DB' created${NC}"
fi
echo ""

echo -e "${YELLOW}Step 2: Grant Permissions${NC}"
echo -e "  Granting permissions to '$DB_USER' on '$DEV_DB'..."
psql -U "$POSTGRES_USER" -d "$DEV_DB" -c "GRANT ALL PRIVILEGES ON DATABASE $DEV_DB TO $DB_USER;"
psql -U "$POSTGRES_USER" -d "$DEV_DB" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"
echo -e "${GREEN}  ✓ Permissions granted${NC}"
echo ""

echo -e "${YELLOW}Step 3: Run Migrations on Development Database${NC}"
MIGRATION_DIR="mcp_server/db/migrations"

if [ ! -d "$MIGRATION_DIR" ]; then
    echo -e "${RED}ERROR: Migration directory not found: $MIGRATION_DIR${NC}"
    exit 1
fi

# Find all migration files and run them in order
for migration in $(find "$MIGRATION_DIR" -name "*.sql" | sort); do
    migration_name=$(basename "$migration")
    echo -e "  Applying migration: $migration_name"
    psql -U "$DB_USER" -d "$DEV_DB" -f "$migration" -v ON_ERROR_STOP=1
    echo -e "${GREEN}  ✓ $migration_name applied${NC}"
done
echo ""

echo -e "${YELLOW}Step 4: Verify Schema Sync${NC}"
echo -e "  Comparing table counts between databases..."

# Get table count from production DB
PROD_TABLE_COUNT=$(psql -U "$DB_USER" -d "$PROD_DB" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" | xargs)

# Get table count from development DB
DEV_TABLE_COUNT=$(psql -U "$DB_USER" -d "$DEV_DB" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE';" | xargs)

echo -e "  Production DB tables: $PROD_TABLE_COUNT"
echo -e "  Development DB tables: $DEV_TABLE_COUNT"

if [ "$PROD_TABLE_COUNT" -eq "$DEV_TABLE_COUNT" ]; then
    echo -e "${GREEN}  ✓ Schema sync verified: Both databases have $DEV_TABLE_COUNT tables${NC}"
else
    echo -e "${YELLOW}  ⚠ WARNING: Table count mismatch!${NC}"
    echo -e "  This may be expected if migrations were added after production setup."
    echo -e "  Run migrations on production DB to sync schemas."
fi
echo ""

echo -e "${YELLOW}Step 5: Display Table Comparison${NC}"
echo -e "  Production database tables:"
psql -U "$DB_USER" -d "$PROD_DB" -c "\dt" | head -20

echo -e "  Development database tables:"
psql -U "$DB_USER" -d "$DEV_DB" -c "\dt" | head -20
echo ""

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}Development Database Setup Complete!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo "Database Details:"
echo "  Development DB: $DEV_DB"
echo "  Production DB:  $PROD_DB"
echo "  DB User:        $DB_USER"
echo ""
echo "Connection Strings:"
echo "  Development: postgresql://$DB_USER:password@localhost:5432/$DEV_DB"
echo "  Production:  postgresql://$DB_USER:password@localhost:5432/$PROD_DB"
echo ""
echo "Next Steps:"
echo "  1. Update config/.env.development with your PostgreSQL password"
echo "  2. Update config/.env.production with your PostgreSQL password"
echo "  3. Test environment loading with: ENVIRONMENT=development python -m mcp_server"
echo ""
