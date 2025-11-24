#!/bin/bash
# Story 3.11: 7-Day Stability Test - Pre-Test Validation & Initialization
# Author: BMad Dev-Story Workflow
# Date: 2025-11-20

set -e  # Exit on error

echo "═══════════════════════════════════════════════════════════════"
echo "  7-Day Stability Test - Pre-Test Validation"
echo "  Story 3.11: Production Readiness Validation"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Validation results
VALIDATION_PASSED=true

# Check 1: Verify all Epic 3 Stories (3.1-3.10) marked as "done"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 1: Epic 3 Stories Completion Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

SPRINT_STATUS="/home/ethr/01-projects/ai-experiments/i-o/bmad-docs/sprint-status.yaml"

if [ ! -f "$SPRINT_STATUS" ]; then
    echo -e "${RED}✗ FAIL: sprint-status.yaml not found${NC}"
    VALIDATION_PASSED=false
else
    echo "Checking Stories 3.1 through 3.10 status..."

    INCOMPLETE_STORIES=()
    for i in {1..10}; do
        STORY_KEY="3-${i}-"
        STATUS=$(grep "$STORY_KEY" "$SPRINT_STATUS" | grep -oP ':\s*\K\w+' || echo "not_found")

        if [ "$STATUS" != "done" ]; then
            INCOMPLETE_STORIES+=("Story 3.${i}: $STATUS")
        fi
    done

    if [ ${#INCOMPLETE_STORIES[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ PASS: All Epic 3 Stories (3.1-3.10) marked as 'done'${NC}"
    else
        echo -e "${RED}✗ FAIL: Following stories NOT done:${NC}"
        for story in "${INCOMPLETE_STORIES[@]}"; do
            echo "  - $story"
        done
        VALIDATION_PASSED=false
    fi
fi

echo ""

# Check 2: Verify systemd service running
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 2: systemd Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if systemctl is-active --quiet mcp-server; then
    echo -e "${GREEN}✓ PASS: mcp-server service is active (running)${NC}"
    systemctl status mcp-server --no-pager | head -3
else
    echo -e "${RED}✗ FAIL: mcp-server service is NOT running${NC}"
    echo "  Action: Start service with: sudo systemctl start mcp-server"
    VALIDATION_PASSED=false
fi

echo ""

# Check 3: Verify PostgreSQL database accessible
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 3: PostgreSQL Database Connectivity"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if psql -U mcp_user -d cognitive_memory -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PASS: PostgreSQL database 'cognitive_memory' is accessible${NC}"
else
    echo -e "${RED}✗ FAIL: Cannot connect to PostgreSQL database${NC}"
    echo "  Action: Check PostgreSQL service and credentials"
    VALIDATION_PASSED=false
fi

echo ""

# Check 4: Verify all cron jobs configured
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 4: Cron Jobs Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

CRON_JOBS=$(crontab -l 2>/dev/null || echo "")

DRIFT_CRON=$(echo "$CRON_JOBS" | grep -c "drift" || echo "0")
BACKUP_CRON=$(echo "$CRON_JOBS" | grep -c "backup\|pg_dump" || echo "0")
BUDGET_CRON=$(echo "$CRON_JOBS" | grep -c "budget" || echo "0")

if [ "$DRIFT_CRON" -gt 0 ] && [ "$BACKUP_CRON" -gt 0 ] && [ "$BUDGET_CRON" -gt 0 ]; then
    echo -e "${GREEN}✓ PASS: All 3 required cron jobs configured${NC}"
    echo "  - Model Drift Detection: Found"
    echo "  - PostgreSQL Backup: Found"
    echo "  - Budget Alert: Found"
else
    echo -e "${YELLOW}⚠ WARNING: Some cron jobs may be missing${NC}"
    echo "  - Model Drift Detection (2 AM): $([ "$DRIFT_CRON" -gt 0 ] && echo 'Found' || echo 'MISSING')"
    echo "  - PostgreSQL Backup (3 AM): $([ "$BACKUP_CRON" -gt 0 ] && echo 'Found' || echo 'MISSING')"
    echo "  - Budget Alert (4 AM): $([ "$BUDGET_CRON" -gt 0 ] && echo 'Found' || echo 'MISSING')"
    echo "  Note: If configured via systemd timers instead of cron, this check may show false negative"
fi

echo ""

# Check 5: Verify API keys configured
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 5: API Keys Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ENV_FILE="/home/ethr/01-projects/ai-experiments/i-o/.env.production"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}✗ FAIL: .env.production file not found${NC}"
    VALIDATION_PASSED=false
else
    OPENAI_KEY=$(grep "OPENAI_API_KEY" "$ENV_FILE" | grep -v "^#" | cut -d'=' -f2 || echo "")
    ANTHROPIC_KEY=$(grep "ANTHROPIC_API_KEY" "$ENV_FILE" | grep -v "^#" | cut -d'=' -f2 || echo "")

    if [ -n "$OPENAI_KEY" ] && [ -n "$ANTHROPIC_KEY" ]; then
        echo -e "${GREEN}✓ PASS: Both API keys present in .env.production${NC}"
        echo "  - OPENAI_API_KEY: Configured"
        echo "  - ANTHROPIC_API_KEY: Configured"
    else
        echo -e "${RED}✗ FAIL: API keys missing${NC}"
        [ -z "$OPENAI_KEY" ] && echo "  - OPENAI_API_KEY: MISSING"
        [ -z "$ANTHROPIC_KEY" ] && echo "  - ANTHROPIC_API_KEY: MISSING"
        VALIDATION_PASSED=false
    fi
fi

echo ""

# Initialize Tracking File
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Stability Test Tracking Initialization"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$VALIDATION_PASSED" = true ]; then
    TRACKING_FILE="/tmp/stability-test-tracking.json"
    START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    UPTIME_START=$(systemctl show mcp-server --property=ActiveEnterTimestamp --value)
    BASELINE_QUERIES=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COUNT(*) FROM api_cost_log" 2>/dev/null || echo "0")

    cat > "$TRACKING_FILE" << EOF
{
  "test_version": "1.0",
  "story_id": "3.11",
  "start_time": "$START_TIME",
  "uptime_baseline": "$UPTIME_START",
  "baseline_query_count": $BASELINE_QUERIES,
  "validation_passed": true,
  "validation_date": "$START_TIME",
  "status": "in_progress"
}
EOF

    echo -e "${GREEN}✓ Tracking file created: $TRACKING_FILE${NC}"
    echo ""
    echo "Baseline Metrics Captured:"
    echo "  - Start Time: $START_TIME"
    echo "  - Service Uptime Start: $UPTIME_START"
    echo "  - Baseline Query Count: $BASELINE_QUERIES"
else
    echo -e "${RED}✗ Tracking file NOT created (validation failed)${NC}"
fi

echo ""

# Final Summary
echo "═══════════════════════════════════════════════════════════════"
echo "  Pre-Test Validation Summary"
echo "═══════════════════════════════════════════════════════════════"

if [ "$VALIDATION_PASSED" = true ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED - System is ready for 7-Day Stability Test${NC}"
    echo ""
    echo "Next Steps:"
    echo "  1. Review this validation report"
    echo "  2. Ensure you can commit to 7 days of monitoring"
    echo "  3. Run daily: ./scripts/daily_stability_check.sh"
    echo "  4. After 7 days: ./scripts/end_stability_test.sh"
    echo ""
    echo "Test officially starts: $START_TIME"
else
    echo -e "${RED}✗ VALIDATION FAILED - System is NOT ready for testing${NC}"
    echo ""
    echo "Required Actions:"
    echo "  1. Fix all failed checks above"
    echo "  2. Re-run this script to validate fixes"
    echo "  3. Only start test when ALL checks pass"
    exit 1
fi

echo "═══════════════════════════════════════════════════════════════"
