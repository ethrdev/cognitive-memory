#!/bin/bash
# Environment Setup Verification Script
# 
#
# Purpose: Verify environment separation is configured correctly
# Usage: ./scripts/verify_environment_setup.sh [development|production|all]

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="/home/user/i-o"
CONFIG_DIR="$PROJECT_ROOT/config"

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}Environment Setup Verification${NC}"
echo -e "${BLUE}
echo -e "${BLUE}==============================================================================${NC}"
echo ""

# Function to check file exists
check_file() {
    local file=$1
    local description=$2
    if [ -f "$file" ]; then
        echo -e "${GREEN}  ✓ $description exists${NC}"
        return 0
    else
        echo -e "${RED}  ✗ $description NOT found${NC}"
        return 1
    fi
}

# Function to check file permissions
check_permissions() {
    local file=$1
    local expected=$2
    local description=$3

    if [ ! -f "$file" ]; then
        echo -e "${RED}  ✗ $description: File not found${NC}"
        return 1
    fi

    actual=$(stat -c "%a" "$file")
    if [ "$actual" = "$expected" ]; then
        echo -e "${GREEN}  ✓ $description: $actual (correct)${NC}"
        return 0
    else
        echo -e "${YELLOW}  ⚠ $description: $actual (expected: $expected)${NC}"
        return 1
    fi
}

# Function to check gitignore
check_gitignore() {
    local pattern=$1
    local description=$2

    if grep -q "^$pattern$" "$PROJECT_ROOT/.gitignore"; then
        echo -e "${GREEN}  ✓ $description in .gitignore${NC}"
        return 0
    else
        echo -e "${YELLOW}  ⚠ $description NOT in .gitignore${NC}"
        return 1
    fi
}

# Test 1: Environment Files (AC 3.7.1)
echo -e "${YELLOW}Test 1: Environment Files mit Secrets Separation${NC}"
check_file "$CONFIG_DIR/.env.template" "config/.env.template"
check_file "$CONFIG_DIR/.env.development" "config/.env.development"
check_file "$CONFIG_DIR/.env.production" "config/.env.production"
echo ""

echo -e "${YELLOW}Test 2: File Permissions (chmod 600 for secrets)${NC}"
check_permissions "$CONFIG_DIR/.env.development" "600" ".env.development"
check_permissions "$CONFIG_DIR/.env.production" "600" ".env.production"
echo ""

echo -e "${YELLOW}Test 3: Gitignore Configuration${NC}"
check_gitignore ".env.development" ".env.development"
check_gitignore ".env.production" ".env.production"
check_gitignore ".env" ".env"
echo ""

# Test 4: Config.yaml Structure (AC 3.7.3)
echo -e "${YELLOW}Test 4: config.yaml Structure${NC}"
if [ -f "$CONFIG_DIR/config.yaml" ]; then
    if grep -q "^base:" "$CONFIG_DIR/config.yaml"; then
        echo -e "${GREEN}  ✓ base: section exists${NC}"
    else
        echo -e "${RED}  ✗ base: section NOT found${NC}"
    fi

    if grep -q "^development:" "$CONFIG_DIR/config.yaml"; then
        echo -e "${GREEN}  ✓ development: section exists${NC}"
    else
        echo -e "${RED}  ✗ development: section NOT found${NC}"
    fi

    if grep -q "^production:" "$CONFIG_DIR/config.yaml"; then
        echo -e "${GREEN}  ✓ production: section exists${NC}"
    else
        echo -e "${RED}  ✗ production: section NOT found${NC}"
    fi

    # Check for development database name
    if grep -A 5 "^development:" "$CONFIG_DIR/config.yaml" | grep -q "name: \"cognitive_memory_dev\""; then
        echo -e "${GREEN}  ✓ Development database: cognitive_memory_dev${NC}"
    else
        echo -e "${YELLOW}  ⚠ Development database name might be incorrect${NC}"
    fi
else
    echo -e "${RED}  ✗ config/config.yaml NOT found${NC}"
fi
echo ""

# Test 5: YAML Syntax Validation
echo -e "${YELLOW}Test 5: YAML Syntax Validation${NC}"
if command -v python3 &> /dev/null; then
    if python3 -c "import yaml; yaml.safe_load(open('$CONFIG_DIR/config.yaml'))" 2>/dev/null; then
        echo -e "${GREEN}  ✓ config.yaml syntax valid${NC}"
    else
        echo -e "${RED}  ✗ config.yaml syntax INVALID${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠ Python3 not available, skipping YAML validation${NC}"
fi
echo ""

# Test 6: Environment Loading Module (AC 3.7.5)
echo -e "${YELLOW}Test 6: Environment Loading Logic${NC}"
check_file "$PROJECT_ROOT/mcp_server/config.py" "mcp_server/config.py"
if [ -f "$PROJECT_ROOT/mcp_server/config.py" ]; then
    if grep -q "def load_environment" "$PROJECT_ROOT/mcp_server/config.py"; then
        echo -e "${GREEN}  ✓ load_environment() function exists${NC}"
    else
        echo -e "${RED}  ✗ load_environment() function NOT found${NC}"
    fi

    if grep -q "def _validate_required_variables" "$PROJECT_ROOT/mcp_server/config.py"; then
        echo -e "${GREEN}  ✓ Variable validation implemented${NC}"
    else
        echo -e "${RED}  ✗ Variable validation NOT found${NC}"
    fi
fi
echo ""

# Test 7: MCP Server Integration
echo -e "${YELLOW}Test 7: MCP Server Integration${NC}"
if [ -f "$PROJECT_ROOT/mcp_server/__main__.py" ]; then
    if grep -q "from mcp_server.config import load_environment" "$PROJECT_ROOT/mcp_server/__main__.py"; then
        echo -e "${GREEN}  ✓ __main__.py imports load_environment${NC}"
    else
        echo -e "${RED}  ✗ __main__.py does NOT import load_environment${NC}"
    fi

    if grep -q "config = load_environment()" "$PROJECT_ROOT/mcp_server/__main__.py"; then
        echo -e "${GREEN}  ✓ __main__.py calls load_environment()${NC}"
    else
        echo -e "${RED}  ✗ __main__.py does NOT call load_environment()${NC}"
    fi
else
    echo -e "${RED}  ✗ mcp_server/__main__.py NOT found${NC}"
fi
echo ""

# Test 8: Production Checklist Documentation (AC 3.7.4)
echo -e "${YELLOW}Test 8: Production Checklist Documentation${NC}"
check_file "$PROJECT_ROOT/docs/operations/production-checklist.md" "docs/operations/production-checklist.md"
if [ -f "$PROJECT_ROOT/docs/operations/production-checklist.md" ]; then
    # Check for required sections
    if grep -q "Pre-Deployment Checklist" "$PROJECT_ROOT/docs/operations/production-checklist.md"; then
        echo -e "${GREEN}  ✓ Pre-Deployment Checklist section exists${NC}"
    fi
    if grep -q "Deployment Steps" "$PROJECT_ROOT/docs/operations/production-checklist.md"; then
        echo -e "${GREEN}  ✓ Deployment Steps section exists${NC}"
    fi
    if grep -q "Post-Deployment Validation" "$PROJECT_ROOT/docs/operations/production-checklist.md"; then
        echo -e "${GREEN}  ✓ Post-Deployment Validation section exists${NC}"
    fi
    if grep -q "Operational Readiness" "$PROJECT_ROOT/docs/operations/production-checklist.md"; then
        echo -e "${GREEN}  ✓ Operational Readiness section exists${NC}"
    fi
fi
echo ""

# Test 9: Database Setup Script
echo -e "${YELLOW}Test 9: Database Setup Script${NC}"
check_file "$PROJECT_ROOT/scripts/setup_dev_database.sh" "scripts/setup_dev_database.sh"
if [ -f "$PROJECT_ROOT/scripts/setup_dev_database.sh" ]; then
    if [ -x "$PROJECT_ROOT/scripts/setup_dev_database.sh" ]; then
        echo -e "${GREEN}  ✓ setup_dev_database.sh is executable${NC}"
    else
        echo -e "${YELLOW}  ⚠ setup_dev_database.sh is NOT executable${NC}"
    fi
fi
echo ""

# Test 10: Git Status Check
echo -e "${YELLOW}Test 10: Git Status - Verify Secrets Not Tracked${NC}"
cd "$PROJECT_ROOT"
if git status --short | grep -E "(\.env\.development|\.env\.production)"; then
    echo -e "${RED}  ✗ WARNING: .env files appear in git status!${NC}"
    echo -e "${RED}    Secrets may be committed to Git${NC}"
else
    echo -e "${GREEN}  ✓ .env files properly ignored by Git${NC}"
fi

if git ls-files | grep -q "config/.env.template"; then
    echo -e "${GREEN}  ✓ .env.template tracked in Git${NC}"
else
    echo -e "${YELLOW}  ⚠ .env.template NOT tracked in Git${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE}Verification Complete${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""
echo "Next Steps:"
echo "  1. Review any warnings (⚠) or failures (✗) above"
echo "  2. Run database setup: ./scripts/setup_dev_database.sh"
echo "  3. Fill in real API keys in config/.env.development and config/.env.production"
echo "  4. Test environment loading:"
echo "     ENVIRONMENT=development python -c 'from mcp_server.config import load_environment; load_environment()'"
echo "  5. Test MCP Server startup:"
echo "     ENVIRONMENT=development python -m mcp_server"
echo ""
