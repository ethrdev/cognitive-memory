#!/bin/bash
#
# Golden Test Cron Wrapper - 
#
# Shell wrapper for daily Golden Test execution via cron.
# Calls Python script with proper environment setup.
#
# Cron Configuration:
#   0 2 * * * /path/to/run_golden_test.sh >> /var/log/mcp-server/golden-test.log 2>&1
#
# Exit Codes:
#   0 = Success
#   1 = Configuration error
#   2 = Database error
#   3 = Runtime error
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Project root directory (adjust if needed)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Python executable (use virtualenv if available)
PYTHON_EXEC="${PROJECT_ROOT}/.venv/bin/python3"
if [ ! -f "$PYTHON_EXEC" ]; then
    # Fallback to system python3
    PYTHON_EXEC="python3"
fi

# Python script
SCRIPT_PATH="${PROJECT_ROOT}/mcp_server/scripts/run_golden_test.py"

# Log directory
LOG_DIR="/var/log/mcp-server"
LOG_FILE="${LOG_DIR}/golden-test.log"

# =============================================================================
# Pre-flight Checks
# =============================================================================

# Create log directory if it doesn't exist (with fallback)
if [ ! -d "$LOG_DIR" ]; then
    if mkdir -p "$LOG_DIR" 2>/dev/null; then
        echo "Created log directory: $LOG_DIR"
    else
        # Fallback to project logs
        LOG_DIR="${PROJECT_ROOT}/logs"
        LOG_FILE="${LOG_DIR}/golden-test.log"
        mkdir -p "$LOG_DIR"
        echo "Using fallback log directory: $LOG_DIR"
    fi
fi

# Check Python script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: Python script not found at $SCRIPT_PATH" | tee -a "$LOG_FILE"
    exit 3
fi

# =============================================================================
# Execute Golden Test
# =============================================================================

echo "================================================" | tee -a "$LOG_FILE"
echo "Golden Test Cron Job - $(date)" | tee -a "$LOG_FILE"
echo "================================================" | tee -a "$LOG_FILE"
echo "Project Root: $PROJECT_ROOT" | tee -a "$LOG_FILE"
echo "Python Exec: $PYTHON_EXEC" | tee -a "$LOG_FILE"
echo "Log File: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Change to project root for proper imports
cd "$PROJECT_ROOT"

# Execute Python script and capture exit code
"$PYTHON_EXEC" "$SCRIPT_PATH"
EXIT_CODE=$?

# Log completion
echo "" | tee -a "$LOG_FILE"
echo "Golden Test completed with exit code: $EXIT_CODE" | tee -a "$LOG_FILE"
echo "================================================" | tee -a "$LOG_FILE"

exit $EXIT_CODE
