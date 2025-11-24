#!/usr/bin/env python3
"""
Golden Test Cron Runner - Story 3.2

Daily execution script for Golden Test Set via direct Python import.
Bypasses MCP protocol overhead for efficient cron job execution.

Usage:
    python mcp_server/scripts/run_golden_test.py

Cron Configuration:
    0 2 * * * /path/to/run_golden_test.sh >> /var/log/mcp-server/golden-test.log 2>&1

Exit Codes:
    0 = Success (Golden Test executed, results stored)
    1 = Configuration error (API keys, config.yaml, etc.)
    2 = Database error (golden_test_set empty, connection failed)
    3 = Runtime error (API failures, unexpected errors)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add mcp_server to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv

# Determine environment file
env_file = Path(__file__).parent.parent.parent / ".env.development"
if env_file.exists():
    load_dotenv(env_file)
else:
    # Fallback to production .env
    load_dotenv()

# Import core function from get_golden_test_results
from tools.get_golden_test_results import execute_golden_test

# =============================================================================
# Logging Configuration
# =============================================================================

# Create log directory if it doesn't exist
log_dir = Path("/var/log/mcp-server")
if not log_dir.exists():
    # Fallback to local logs if /var/log not writable
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

log_file = log_dir / "golden-test.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout),  # Also log to stdout for cron email
    ],
)

logger = logging.getLogger(__name__)


# =============================================================================
# Main Execution
# =============================================================================


def main() -> int:
    """
    Execute Golden Test and return exit code.

    Returns:
        Exit code (0=success, 1=config error, 2=database error, 3=runtime error)
    """
    logger.info("=" * 80)
    logger.info(f"Golden Test Cron Job - {datetime.now().isoformat()}")
    logger.info("=" * 80)

    try:
        # Pre-flight checks
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-your-openai-api-key-here":
            logger.error(
                "Configuration Error: OPENAI_API_KEY not set or contains placeholder value"
            )
            return 1

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            logger.error("Configuration Error: DATABASE_URL not set")
            return 1

        # Execute Golden Test
        logger.info("Starting Golden Test execution...")
        result = execute_golden_test()

        # Log results
        logger.info("Golden Test execution completed successfully!")
        logger.info(f"  Date: {result['date']}")
        logger.info(f"  Precision@5: {result['precision_at_5']:.4f}")
        logger.info(f"  Num Queries: {result['num_queries']}")
        logger.info(f"  Drift Detected: {result['drift_detected']}")

        if result["baseline_p5"] is not None:
            logger.info(f"  Baseline P@5: {result['baseline_p5']:.4f}")
            logger.info(f"  Drop %: {result['drop_percentage']:.2%}")
        else:
            logger.info(
                "  Baseline P@5: NULL (insufficient historical data for drift detection)"
            )

        logger.info(
            f"  Avg Retrieval Time: {result['avg_retrieval_time']:.1f}ms"
        )
        logger.info(
            f"  Total Execution Time: {result['total_execution_time']:.2f}s"
        )

        if result["drift_detected"]:
            logger.warning(
                "🚨 DRIFT DETECTED! Please investigate model changes or API updates."
            )

        logger.info("=" * 80)
        return 0

    except RuntimeError as e:
        error_msg = str(e).lower()

        if "api key" in error_msg or "config" in error_msg:
            logger.error(f"Configuration Error: {e}")
            return 1
        elif (
            "empty" in error_msg
            or "database" in error_msg
            or "connection" in error_msg
        ):
            logger.error(f"Database Error: {e}")
            return 2
        else:
            logger.error(f"Runtime Error: {e}")
            return 3

    except Exception as e:
        logger.error(f"Unexpected Error: {e}")
        import traceback

        traceback.print_exc()
        return 3


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
