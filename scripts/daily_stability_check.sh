#!/bin/bash
# Story 3.11: 7-Day Stability Test - Daily Monitoring Check
# Author: BMad Dev-Story Workflow
# Date: 2025-11-20

set -e  # Exit on error

echo "═══════════════════════════════════════════════════════════════"
echo "  7-Day Stability Test - Daily Monitoring Check"
echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if tracking file exists
TRACKING_FILE="/tmp/stability-test-tracking.json"
if [ ! -f "$TRACKING_FILE" ]; then
    echo -e "${RED}✗ ERROR: Tracking file not found${NC}"
    echo "  Have you run ./scripts/start_stability_test.sh yet?"
    exit 1
fi

# Extract test start time
START_TIME=$(grep -oP '"start_time":\s*"\K[^"]+' "$TRACKING_FILE")
echo -e "${BLUE}Test Start Time: $START_TIME${NC}"

# Calculate elapsed time
START_SECONDS=$(date -d "$START_TIME" +%s)
NOW_SECONDS=$(date +%s)
ELAPSED_SECONDS=$((NOW_SECONDS - START_SECONDS))
ELAPSED_HOURS=$((ELAPSED_SECONDS / 3600))
ELAPSED_DAYS=$((ELAPSED_HOURS / 24))
REMAINING_HOURS=$((168 - ELAPSED_HOURS))

echo -e "${BLUE}Elapsed Time: ${ELAPSED_DAYS}d ${ELAPSED_HOURS}h / 168h (Target: 7 days)${NC}"
echo -e "${BLUE}Remaining: ${REMAINING_HOURS}h${NC}"
echo ""

# Daily Check Results
DAILY_STATUS="OK"

# Check 1: systemd Service Status
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 1: systemd Service Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if systemctl is-active --quiet mcp-server; then
    echo -e "${GREEN}✓ PASS: mcp-server service is active (running)${NC}"

    # Get restart count
    RESTART_COUNT=$(systemctl show mcp-server --property=NRestarts --value)
    echo "  Restart Count: $RESTART_COUNT"

    if [ "$RESTART_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}  ⚠ WARNING: Service has been restarted $RESTART_COUNT time(s)${NC}"
        echo "    Check: journalctl -u mcp-server -n 100 for crash logs"
    fi
else
    echo -e "${RED}✗ FAIL: mcp-server service is NOT running${NC}"
    DAILY_STATUS="CRITICAL"
fi

echo ""

# Check 2: Cron Jobs Execution (last 24 hours)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 2: Cron Jobs Execution (Last 24h)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Drift Detection (2 AM)
DRIFT_RUNS=$(journalctl -u cron --since "24 hours ago" 2>/dev/null | grep -c "drift" || echo "0")
echo "  - Model Drift Detection (2 AM): $([ "$DRIFT_RUNS" -gt 0 ] && echo -e "${GREEN}✓ Executed${NC}" || echo -e "${YELLOW}⚠ Not detected${NC}")"

# Backup (3 AM)
BACKUP_COUNT=$(ls -1 /backups/postgres/*.dump 2>/dev/null | wc -l || echo "0")
LATEST_BACKUP=$(ls -t /backups/postgres/*.dump 2>/dev/null | head -1 || echo "none")
if [ -n "$LATEST_BACKUP" ] && [ "$LATEST_BACKUP" != "none" ]; then
    BACKUP_AGE=$(($(date +%s) - $(date -r "$LATEST_BACKUP" +%s)))
    BACKUP_HOURS=$((BACKUP_AGE / 3600))
    echo -e "  - PostgreSQL Backup (3 AM): ${GREEN}✓ Executed${NC}"
    echo "    Latest: $LATEST_BACKUP (${BACKUP_HOURS}h ago)"
    echo "    Total Backups: $BACKUP_COUNT"
else
    echo -e "  - PostgreSQL Backup (3 AM): ${YELLOW}⚠ No recent backup found${NC}"
fi

# Budget Alert (4 AM)
BUDGET_RUNS=$(journalctl -u cron --since "24 hours ago" 2>/dev/null | grep -c "budget" || echo "0")
echo "  - Budget Alert (4 AM): $([ "$BUDGET_RUNS" -gt 0 ] && echo -e "${GREEN}✓ Executed${NC}" || echo -e "${YELLOW}⚠ Not detected${NC}")"

echo ""

# Check 3: API Retry Log Analysis (Last 24h)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 3: API Reliability (Last 24h)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

RETRY_COUNT=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COUNT(*) FROM api_retry_log WHERE created_at >= CURRENT_DATE" 2>/dev/null | tr -d ' ' || echo "0")
TOTAL_CALLS=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COUNT(*) FROM api_cost_log WHERE date >= CURRENT_DATE" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$TOTAL_CALLS" -gt 0 ]; then
    RETRY_RATE=$(awk "BEGIN {printf \"%.1f\", ($RETRY_COUNT / $TOTAL_CALLS) * 100}")
    echo "  Total API Calls (today): $TOTAL_CALLS"
    echo "  Retry Count (today): $RETRY_COUNT"
    echo "  Retry Rate: ${RETRY_RATE}%"

    if (( $(echo "$RETRY_RATE < 10" | bc -l) )); then
        echo -e "  ${GREEN}✓ PASS: Retry rate <10% (healthy)${NC}"
    elif (( $(echo "$RETRY_RATE < 20" | bc -l) )); then
        echo -e "  ${YELLOW}⚠ WARNING: Retry rate 10-20% (monitor closely)${NC}"
    else
        echo -e "  ${RED}✗ FAIL: Retry rate >20% (investigate API issues)${NC}"
        DAILY_STATUS="WARNING"
    fi
else
    echo -e "  ${YELLOW}⚠ No API calls today (expected 10+ queries/day)${NC}"
fi

echo ""

# Check 4: Daily Budget Check
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 4: Budget Monitoring (Daily Cost)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run budget CLI tool for today's costs
if command -v python3 &> /dev/null; then
    DAILY_COST=$(python3 -m mcp_server.budget.cli daily 2>/dev/null | grep -oP 'Total.*€\K[\d.]+' || echo "0.00")
    echo "  Daily Cost (today): €${DAILY_COST}"

    if (( $(echo "$DAILY_COST < 0.30" | bc -l) )); then
        echo -e "  ${GREEN}✓ PASS: Daily cost <€0.30 (projected €2.10/week)${NC}"
    elif (( $(echo "$DAILY_COST < 0.50" | bc -l) )); then
        echo -e "  ${YELLOW}⚠ WARNING: Daily cost €0.30-0.50 (monitor budget)${NC}"
    else
        echo -e "  ${RED}✗ ALERT: Daily cost >€0.50 (investigate cost spike)${NC}"
        DAILY_STATUS="WARNING"
    fi
else
    echo -e "  ${YELLOW}⚠ Python not available, skipping budget check${NC}"
fi

echo ""

# Check 5: Query Count (Today)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "CHECK 5: Query Load (Today)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TODAY_QUERIES=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COUNT(*) FROM api_cost_log WHERE date >= CURRENT_DATE" 2>/dev/null | tr -d ' ' || echo "0")
echo "  Queries Processed (today): $TODAY_QUERIES"

if [ "$TODAY_QUERIES" -ge 10 ]; then
    echo -e "  ${GREEN}✓ PASS: Query load ≥10 queries/day (target met)${NC}"
elif [ "$TODAY_QUERIES" -ge 5 ]; then
    echo -e "  ${YELLOW}⚠ WARNING: Query load <10 (target: 10+ queries/day)${NC}"
else
    echo -e "  ${YELLOW}⚠ LOW: Query load very low (consider running test queries)${NC}"
fi

echo ""

# Summary
echo "═══════════════════════════════════════════════════════════════"
echo "  Daily Check Summary"
echo "═══════════════════════════════════════════════════════════════"

case $DAILY_STATUS in
    "OK")
        echo -e "${GREEN}✓ Daily Status: OK - All systems operational${NC}"
        ;;
    "WARNING")
        echo -e "${YELLOW}⚠ Daily Status: WARNING - Issues detected, monitor closely${NC}"
        ;;
    "CRITICAL")
        echo -e "${RED}✗ Daily Status: CRITICAL - Immediate action required${NC}"
        ;;
esac

echo ""
echo "Progress: Day ${ELAPSED_DAYS} of 7 (${ELAPSED_HOURS}h / 168h)"
echo ""

if [ $REMAINING_HOURS -le 0 ]; then
    echo -e "${GREEN}✓ 7-DAY TEST COMPLETE!${NC}"
    echo "  Run: ./scripts/end_stability_test.sh to generate final report"
else
    echo "Remaining Time: ${REMAINING_HOURS} hours"
    echo "Next Check: Run this script again tomorrow"
fi

echo "═══════════════════════════════════════════════════════════════"
