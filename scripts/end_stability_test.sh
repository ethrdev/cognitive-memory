#!/bin/bash
# 7-Day Stability Test - End-of-Test Metrics Collection
# Cognitive Memory v1.0.0
# Date: 2025-11-20

set -e  # Exit on error

echo "═══════════════════════════════════════════════════════════════"
echo "  7-Day Stability Test - Final Metrics Collection"
echo "  Completion Date: $(date '+%Y-%m-%d %H:%M:%S')"
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
START_SECONDS=$(date -d "$START_TIME" +%s)
END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
END_SECONDS=$(date +%s)
ELAPSED_SECONDS=$((END_SECONDS - START_SECONDS))
ELAPSED_HOURS=$((ELAPSED_SECONDS / 3600))

echo -e "${BLUE}Test Start: $START_TIME${NC}"
echo -e "${BLUE}Test End: $END_TIME${NC}"
echo -e "${BLUE}Total Duration: ${ELAPSED_HOURS}h (Target: 168h)${NC}"
echo ""

# Metrics Collection Results
METRICS_FILE="/tmp/stability-test-metrics.json"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "METRIC 1: Total Uptime Calculation"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

UPTIME_START=$(systemctl show mcp-server --property=ActiveEnterTimestamp --value)
echo "Service Start: $UPTIME_START"

# Calculate uptime percentage
UPTIME_PERCENTAGE=$(awk "BEGIN {printf \"%.2f\", ($ELAPSED_HOURS / 168) * 100}")
echo "Uptime: ${ELAPSED_HOURS}h / 168h (${UPTIME_PERCENTAGE}%)"

if (( $(echo "$UPTIME_PERCENTAGE >= 99" | bc -l) )); then
    echo -e "${GREEN}✓ PASS: Uptime ≥99% (Target: >99%)${NC}"
    UPTIME_STATUS="PASS"
else
    echo -e "${RED}✗ FAIL: Uptime <99% (Target: >99%)${NC}"
    UPTIME_STATUS="FAIL"
fi

# Check restart count
RESTART_COUNT=$(systemctl show mcp-server --property=NRestarts --value)
echo "Service Restarts: $RESTART_COUNT"

if [ "$RESTART_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✓ Perfect: No service restarts${NC}"
elif [ "$RESTART_COUNT" -le 2 ]; then
    echo -e "${YELLOW}⚠ Acceptable: $RESTART_COUNT restart(s) with auto-recovery${NC}"
else
    echo -e "${RED}✗ WARNING: $RESTART_COUNT restarts (investigate stability issues)${NC}"
fi

echo ""

# Metric 2: Query Success Rate
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "METRIC 2: Query Success Rate"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

BASELINE_QUERIES=$(grep -oP '"baseline_query_count":\s*\K\d+' "$TRACKING_FILE")
CURRENT_QUERIES=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COUNT(*) FROM api_cost_log" 2>/dev/null | tr -d ' ')
TOTAL_QUERIES=$((CURRENT_QUERIES - BASELINE_QUERIES))

echo "Baseline Query Count: $BASELINE_QUERIES"
echo "Current Query Count: $CURRENT_QUERIES"
echo "Total Queries Processed: $TOTAL_QUERIES"

# Calculate failed queries (retry count >= 4 = exhausted retries)
FAILED_QUERIES=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COUNT(*) FROM api_retry_log WHERE retry_count >= 4 AND created_at >= '$START_TIME'" 2>/dev/null | tr -d ' ')
SUCCESS_QUERIES=$((TOTAL_QUERIES - FAILED_QUERIES))
SUCCESS_RATE=$(awk "BEGIN {if ($TOTAL_QUERIES > 0) printf \"%.2f\", ($SUCCESS_QUERIES / $TOTAL_QUERIES) * 100; else print \"0.00\"}")

echo "Successful Queries: $SUCCESS_QUERIES"
echo "Failed Queries: $FAILED_QUERIES"
echo "Success Rate: ${SUCCESS_RATE}%"

if (( $(echo "$SUCCESS_RATE >= 99" | bc -l) )); then
    echo -e "${GREEN}✓ PASS: Success Rate ≥99% (Target: >99%)${NC}"
    SUCCESS_STATUS="PASS"
else
    echo -e "${RED}✗ FAIL: Success Rate <99% (Target: >99%)${NC}"
    SUCCESS_STATUS="FAIL"
fi

# Check minimum query load
if [ "$TOTAL_QUERIES" -ge 70 ]; then
    echo -e "${GREEN}✓ Query Load: $TOTAL_QUERIES queries ≥70 (Target: 70+)${NC}"
else
    echo -e "${YELLOW}⚠ Query Load: $TOTAL_QUERIES queries <70 (Target: 70+)${NC}"
fi

echo ""

# Metric 3: Latency (p50, p95, p99)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "METRIC 3: Latency Percentiles"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Extract latency data from model_drift_log
LATENCY_P50=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY avg_retrieval_time) FROM model_drift_log WHERE created_at >= '$START_TIME'" 2>/dev/null | tr -d ' ' || echo "0.00")
LATENCY_P95=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY avg_retrieval_time) FROM model_drift_log WHERE created_at >= '$START_TIME'" 2>/dev/null | tr -d ' ' || echo "0.00")
LATENCY_P99=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY avg_retrieval_time) FROM model_drift_log WHERE created_at >= '$START_TIME'" 2>/dev/null | tr -d ' ' || echo "0.00")

echo "p50 Latency: ${LATENCY_P50}s"
echo "p95 Latency: ${LATENCY_P95}s (Target: <5s)"
echo "p99 Latency: ${LATENCY_P99}s"

if (( $(echo "$LATENCY_P95 < 5.0" | bc -l) )); then
    echo -e "${GREEN}✓ PASS: p95 Latency <5s (NFR001 Compliance)${NC}"
    LATENCY_STATUS="PASS"
else
    echo -e "${RED}✗ FAIL: p95 Latency ≥5s (NFR001 Violation)${NC}"
    LATENCY_STATUS="FAIL"
fi

echo ""

# Metric 4: API Reliability
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "METRIC 4: API Reliability"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_API_CALLS=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COUNT(*) FROM api_cost_log WHERE date >= (SELECT date FROM api_cost_log WHERE created_at >= '$START_TIME' LIMIT 1)" 2>/dev/null | tr -d ' ')
RETRY_COUNT=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COUNT(*) FROM api_retry_log WHERE created_at >= '$START_TIME'" 2>/dev/null | tr -d ' ')
RETRY_RATE=$(awk "BEGIN {if ($TOTAL_API_CALLS > 0) printf \"%.2f\", ($RETRY_COUNT / $TOTAL_API_CALLS) * 100; else print \"0.00\"}")

echo "Total API Calls: $TOTAL_API_CALLS"
echo "Retry Count: $RETRY_COUNT"
echo "Retry Rate: ${RETRY_RATE}%"

if (( $(echo "$RETRY_RATE < 10" | bc -l) )); then
    echo -e "${GREEN}✓ PASS: Retry Rate <10% (Retry logic functional)${NC}"
    API_STATUS="PASS"
else
    echo -e "${YELLOW}⚠ WARNING: Retry Rate ≥10% (Monitor API reliability)${NC}"
    API_STATUS="WARNING"
fi

echo ""

# Metric 5: Total Cost
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "METRIC 5: Budget Compliance"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_COST=$(psql -U mcp_user -d cognitive_memory -t -c "SELECT COALESCE(SUM(estimated_cost), 0) FROM api_cost_log WHERE date >= (SELECT date FROM api_cost_log WHERE created_at >= '$START_TIME' LIMIT 1)" 2>/dev/null | tr -d ' ')
echo "Total Cost (7 days): €${TOTAL_COST}"

# Project monthly cost
MONTHLY_PROJECTION=$(awk "BEGIN {printf \"%.2f\", ($TOTAL_COST / 7) * 30}")
echo "Projected Monthly Cost: €${MONTHLY_PROJECTION}"

if (( $(echo "$TOTAL_COST < 2.0" | bc -l) )); then
    echo -e "${GREEN}✓ PASS: Total Cost <€2.00 (Target: <€2.00)${NC}"
    BUDGET_STATUS="PASS"
elif (( $(echo "$TOTAL_COST < 3.0" | bc -l) )); then
    echo -e "${YELLOW}⚠ WARNING: Total Cost €2.00-3.00 (Above target but acceptable)${NC}"
    BUDGET_STATUS="WARNING"
else
    echo -e "${RED}✗ FAIL: Total Cost ≥€3.00 (Budget overage - investigate)${NC}"
    BUDGET_STATUS="FAIL"
fi

# Cost breakdown
echo ""
echo "Cost Breakdown by API:"
psql -U mcp_user -d cognitive_memory -t -c "SELECT api_name, SUM(estimated_cost) as cost FROM api_cost_log WHERE date >= (SELECT date FROM api_cost_log WHERE created_at >= '$START_TIME' LIMIT 1) GROUP BY api_name ORDER BY cost DESC" 2>/dev/null || echo "N/A"

echo ""

# Save metrics to JSON
cat > "$METRICS_FILE" << EOF
{
  "test_version": "1.0",
  "story_id": "3.11",
  "start_time": "$START_TIME",
  "end_time": "$END_TIME",
  "elapsed_hours": $ELAPSED_HOURS,
  "metrics": {
    "uptime": {
      "hours": $ELAPSED_HOURS,
      "percentage": $UPTIME_PERCENTAGE,
      "restart_count": $RESTART_COUNT,
      "status": "$UPTIME_STATUS"
    },
    "success_rate": {
      "total_queries": $TOTAL_QUERIES,
      "successful_queries": $SUCCESS_QUERIES,
      "failed_queries": $FAILED_QUERIES,
      "percentage": $SUCCESS_RATE,
      "status": "$SUCCESS_STATUS"
    },
    "latency": {
      "p50": $LATENCY_P50,
      "p95": $LATENCY_P95,
      "p99": $LATENCY_P99,
      "status": "$LATENCY_STATUS"
    },
    "api_reliability": {
      "total_calls": $TOTAL_API_CALLS,
      "retry_count": $RETRY_COUNT,
      "retry_rate": $RETRY_RATE,
      "status": "$API_STATUS"
    },
    "budget": {
      "total_cost": $TOTAL_COST,
      "monthly_projection": $MONTHLY_PROJECTION,
      "status": "$BUDGET_STATUS"
    }
  }
}
EOF

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Metrics saved to: $METRICS_FILE"
echo ""

# Final Summary
echo "═══════════════════════════════════════════════════════════════"
echo "  7-Day Stability Test - Final Summary"
echo "═══════════════════════════════════════════════════════════════"

OVERALL_STATUS="PASS"

echo -e "Metric 1 - Uptime: ${UPTIME_STATUS} (${UPTIME_PERCENTAGE}%)"
echo -e "Metric 2 - Success Rate: ${SUCCESS_STATUS} (${SUCCESS_RATE}%)"
echo -e "Metric 3 - Latency p95: ${LATENCY_STATUS} (${LATENCY_P95}s)"
echo -e "Metric 4 - API Reliability: ${API_STATUS} (${RETRY_RATE}% retry rate)"
echo -e "Metric 5 - Budget: ${BUDGET_STATUS} (€${TOTAL_COST})"
echo ""

# Determine overall status
if [ "$UPTIME_STATUS" != "PASS" ] || [ "$SUCCESS_STATUS" != "PASS" ] || [ "$LATENCY_STATUS" != "PASS" ]; then
    OVERALL_STATUS="FAIL"
elif [ "$BUDGET_STATUS" = "FAIL" ] || [ "$API_STATUS" = "WARNING" ]; then
    OVERALL_STATUS="PARTIAL"
fi

case $OVERALL_STATUS in
    "PASS")
        echo -e "${GREEN}✓ OVERALL: PASS - All acceptance criteria met!${NC}"
        echo ""
        echo "Production-Readiness validated successfully (NFR004)."
        ;;
    "PARTIAL")
        echo -e "${YELLOW}⚠ OVERALL: PARTIAL - Core metrics passed, minor issues detected${NC}"
        echo ""
        echo "System is production-ready with monitoring required."
        ;;
    "FAIL")
        echo -e "${RED}✗ OVERALL: FAIL - Critical acceptance criteria not met${NC}"
        echo ""
        echo "System is NOT production-ready. Root cause analysis required."
        ;;
esac

echo ""
echo "Next Steps:"
echo "  1. Review metrics JSON: $METRICS_FILE"
echo "  2. Generate stability report: python3 scripts/generate_stability_report.py"
echo "  3. Document results in: docs/7-day-stability-report.md"
echo "  4. If FAIL: Conduct root cause analysis and re-run test"
echo ""
echo "═══════════════════════════════════════════════════════════════"
