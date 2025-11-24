#!/usr/bin/env python3
"""
L2 Insights Git Export Script for Cognitive Memory System
Story 3.6: PostgreSQL Backup Strategy Implementation

Exports L2 insights (content + metadata, excluding embeddings) to JSON format
for Git-based fallback recovery. Embeddings can be regenerated via OpenAI API.

Features:
- Query PostgreSQL l2_insights table (exclude embedding_vector column)
- Export to timestamped JSON files
- Optional Git commit and push (configurable)
- Comprehensive error handling and logging
- No blocking on Git failures (WARNING only)

Usage: python scripts/export_l2_insights.py
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
import yaml
from dotenv import load_dotenv
from psycopg2.extras import DictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class L2InsightsExporter:
    """Exports L2 insights from PostgreSQL to JSON format for Git backup."""

    def __init__(self, output_dir: str, git_export_enabled: bool = False) -> None:
        """
        Initialize L2 Insights exporter.

        Args:
            output_dir: Directory path for JSON export files
            git_export_enabled: Whether to commit and push exports to Git
        """
        self.output_dir = Path(output_dir)
        self.git_export_enabled = git_export_enabled
        self.export_date = datetime.now().strftime("%Y-%m-%d")
        self.export_file = self.output_dir / f"{self.export_date}.json"

    def create_output_directory(self) -> None:
        """Create output directory if it doesn't exist."""
        if not self.output_dir.exists():
            logger.info(f"Creating output directory: {self.output_dir}")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Output directory created")
        else:
            logger.info(f"Output directory exists: {self.output_dir}")

    def load_database_credentials(self) -> str:
        """
        Load DATABASE_URL from environment.

        Returns:
            DATABASE_URL connection string

        Raises:
            ValueError: If DATABASE_URL not found in environment
        """
        # Load .env file
        env_file = Path(__file__).parent.parent / ".env"
        if not env_file.exists():
            env_file = Path(__file__).parent.parent / ".env.development"

        if env_file.exists():
            logger.info(f"Loading environment from {env_file}")
            load_dotenv(env_file)
        else:
            logger.warning("No .env file found, using system environment")

        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError("DATABASE_URL not found in environment")

        logger.info("Database credentials loaded successfully")
        return database_url

    def export_insights(self) -> int:
        """
        Export L2 insights from PostgreSQL to JSON.

        Queries l2_insights table for id, content, metadata, created_at, source_ids.
        Excludes embedding_vector column (1536 dimensions, too large for Git).

        Returns:
            Number of insights exported

        Raises:
            psycopg2.Error: If database query fails
        """
        database_url = self.load_database_credentials()

        logger.info("Connecting to PostgreSQL database...")

        try:
            # Connect to database
            with psycopg2.connect(database_url, cursor_factory=DictCursor) as conn:
                with conn.cursor() as cursor:
                    # Query l2_insights table (exclude embedding_vector)
                    query = """
                        SELECT
                            id,
                            content,
                            metadata,
                            created_at,
                            source_ids
                        FROM l2_insights
                        ORDER BY created_at DESC
                    """

                    logger.info("Executing query to fetch L2 insights...")
                    cursor.execute(query)

                    # Fetch all results
                    insights = cursor.fetchall()
                    insight_count = len(insights)

                    logger.info(f"Fetched {insight_count} insights from database")

                    # Convert to JSON-serializable format
                    insights_data = []
                    for insight in insights:
                        insight_dict = {
                            "id": insight["id"],
                            "content": insight["content"],
                            "metadata": insight["metadata"],
                            "created_at": insight["created_at"].isoformat()
                            if insight["created_at"]
                            else None,
                            "source_ids": insight["source_ids"],
                        }
                        insights_data.append(insight_dict)

                    # Create export object
                    export_data = {
                        "export_date": self.export_date,
                        "export_timestamp": datetime.now().isoformat(),
                        "insight_count": insight_count,
                        "insights": insights_data,
                        "note": "Embeddings excluded - can be regenerated via OpenAI API",
                    }

                    # Write to JSON file
                    logger.info(f"Writing export to {self.export_file}")
                    with open(self.export_file, "w", encoding="utf-8") as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False)

                    # Get file size
                    file_size_bytes = self.export_file.stat().st_size
                    file_size_mb = file_size_bytes / (1024 * 1024)

                    logger.info(f"Export completed successfully")
                    logger.info(
                        f"File size: {file_size_mb:.2f} MB ({file_size_bytes} bytes)"
                    )

                    return insight_count

        except psycopg2.Error as e:
            logger.error(f"Database error during export: {e}")
            raise

    def git_commit_and_push(self) -> bool:
        """
        Commit and push export file to Git repository.

        This is optional and non-blocking. If Git operations fail, logs WARNING
        but does not raise exception (pg_dump is critical path).

        Returns:
            True if Git operations succeeded, False otherwise
        """
        if not self.git_export_enabled:
            logger.info("Git export disabled (git_export_enabled=false)")
            return False

        try:
            logger.info("Committing L2 insights export to Git...")

            # Change to repository root
            repo_root = Path(__file__).parent.parent
            os.chdir(repo_root)

            # Git add
            subprocess.run(
                ["git", "add", str(self.export_file)],
                check=True,
                capture_output=True,
                text=True,
            )

            # Git commit
            commit_message = f"Automated L2 insights backup ({self.export_date})"
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                logger.info("Git commit successful")

                # Git push
                push_result = subprocess.run(
                    ["git", "push"], capture_output=True, text=True
                )

                if push_result.returncode == 0:
                    logger.info("Git push successful")
                    return True
                else:
                    logger.warning(f"Git push failed: {push_result.stderr}")
                    logger.warning("Export file committed locally but not pushed")
                    return False
            else:
                # Check if nothing to commit
                if "nothing to commit" in result.stdout:
                    logger.info("No changes to commit (export file unchanged)")
                    return True
                else:
                    logger.warning(f"Git commit failed: {result.stderr}")
                    return False

        except subprocess.CalledProcessError as e:
            logger.warning(f"Git operation failed: {e}")
            logger.warning("This is non-blocking - L2 export file was created")
            return False
        except Exception as e:
            logger.warning(f"Unexpected Git error: {e}")
            logger.warning("This is non-blocking - L2 export file was created")
            return False


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.yaml.

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config.yaml not found
    """
    # Try multiple config file locations
    config_paths = [
        Path(__file__).parent.parent / "config" / "config.yaml",
        Path(__file__).parent.parent / "config.yaml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            logger.info(f"Loading configuration from {config_path}")
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
                # Extract backup config if present
                if config and "backup" in config:
                    return config["backup"]
                return config or {}

    # Return default config if no file found
    logger.warning("No config.yaml found, using defaults")
    return {"git_export_enabled": False}


def main() -> int:
    """
    Main entry point for L2 Insights export script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info("=" * 50)
    logger.info("L2 Insights Export Script Started")
    logger.info("=" * 50)

    try:
        # Load configuration
        config = load_config()
        git_export_enabled = config.get("git_export_enabled", False)

        # Initialize exporter
        output_dir = "/memory/l2-insights"
        exporter = L2InsightsExporter(
            output_dir=output_dir, git_export_enabled=git_export_enabled
        )

        # Create output directory
        exporter.create_output_directory()

        # Export insights
        insight_count = exporter.export_insights()
        logger.info(f"Successfully exported {insight_count} insights")

        # Optional: Commit and push to Git
        if git_export_enabled:
            git_success = exporter.git_commit_and_push()
            if git_success:
                logger.info("Git export completed successfully")
            else:
                logger.warning("Git export failed (non-blocking)")
        else:
            logger.info("Git export skipped (disabled in config)")

        logger.info("=" * 50)
        logger.info("L2 Insights Export Script Completed")
        logger.info("=" * 50)

        return 0

    except Exception as e:
        logger.error(f"Export script failed: {e}", exc_info=True)
        logger.error("=" * 50)
        logger.error("L2 Insights Export Script Failed")
        logger.error("=" * 50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
