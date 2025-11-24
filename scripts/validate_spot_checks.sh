#!/bin/bash
# Monthly Spot Check Validation Script ()
#
# Purpose: Validate spot check Kappa and revert to Dual Judge if below threshold
# Schedule: 1st of every month at midnight (cron: 0 0 1 * *)
# Exit codes: 0 = success, 1 = reverted to Dual Judge, 2 = error
#
# Usage:
#   ./validate_spot_checks.sh
#
# Cron Entry:
#   0 0 1 * * /path/to/i-o/scripts/validate_spot_checks.sh >> /var/log/mcp-server/spot-check-validation.log 2>&1

set -e  # Exit on error

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Activate virtual environment if exists
if [ -d "$PROJECT_ROOT/.venv" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
elif [ -d "$PROJECT_ROOT/venv" ]; then
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Log start
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting monthly spot check validation..."

# Call CLI tool with --validate-spot-checks command
python "$PROJECT_ROOT/scripts/staged_dual_judge_cli.py" --validate-spot-checks

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ Spot check validation passed. Continuing Single Judge Mode."
elif [ $EXIT_CODE -eq 1 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ⚠️ Spot check validation failed. Reverted to Dual Judge Mode."
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ Validation error (exit code: $EXIT_CODE)"
fi

exit $EXIT_CODE
