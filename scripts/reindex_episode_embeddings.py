"""
Reindex all existing episodes with combined query+reflection embeddings.

Background: Episodes were originally embedded using only the `query` field.
The `reflection` (haiku_reflection) field — which contains the actual lesson —
was stored but not included in the embedding. This made reflections unsearchable
via semantic search, while keyword search already concatenated both fields.

This script regenerates all embeddings using `f"{query} {reflection}"` to match
the fix applied to `add_episode()` in mcp_server/tools/__init__.py.

Usage:
    python scripts/reindex_episode_embeddings.py --dry-run     # Preview without changes
    python scripts/reindex_episode_embeddings.py               # Run reindex
    python scripts/reindex_episode_embeddings.py --batch-size 20  # Custom batch size

Cost estimate: ~124 episodes × ~500 tokens each ≈ 62k tokens ≈ $0.001 (negligible)
"""

import argparse
import logging
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg2 import register_vector
import psycopg2
from psycopg2.extras import DictCursor

# Setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_connection():
    """Create a direct database connection."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set in environment")

    conn = psycopg2.connect(database_url, cursor_factory=DictCursor)
    register_vector(conn)
    return conn


def get_embedding(client: OpenAI, text: str, max_retries: int = 3) -> list[float]:
    """Generate embedding with retry logic."""
    delays = [1, 2, 4]

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                encoding_format="float",
            )
            return response.data[0].embedding
        except Exception as e:
            if attempt < max_retries - 1:
                delay = delays[attempt]
                logger.warning(f"API error, retrying in {delay}s: {e}")
                time.sleep(delay)
            else:
                raise RuntimeError(f"Embedding failed after {max_retries} attempts: {e}") from e

    raise RuntimeError("Unreachable")


def reindex_episodes(batch_size: int = 50, dry_run: bool = False, project_id: str = "io"):
    """Reindex all episodes with combined query+reflection embeddings."""
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment")

    client = OpenAI(api_key=api_key)
    conn = get_connection()

    try:
        cursor = conn.cursor()

        # Count episodes
        cursor.execute(
            "SELECT COUNT(*) FROM episode_memory WHERE project_id = %s",
            (project_id,),
        )
        total = cursor.fetchone()[0]
        logger.info(f"Found {total} episodes for project '{project_id}'")

        if dry_run:
            logger.info("DRY RUN — no changes will be made")

        # Fetch all episodes
        cursor.execute(
            """SELECT id, query, reflection
               FROM episode_memory
               WHERE project_id = %s
               ORDER BY id""",
            (project_id,),
        )
        episodes = cursor.fetchall()

        success_count = 0
        error_count = 0

        for idx, episode in enumerate(episodes):
            ep_id = episode["id"]
            query = episode["query"] or ""
            reflection = episode["reflection"] or ""

            combined_text = f"{query} {reflection}".strip()

            if not combined_text:
                logger.warning(f"Episode {ep_id}: empty query+reflection, skipping")
                continue

            try:
                embedding = get_embedding(client, combined_text)

                if not dry_run:
                    cursor.execute(
                        "UPDATE episode_memory SET embedding = %s WHERE id = %s",
                        (embedding, ep_id),
                    )

                    # Commit in batches
                    if (idx + 1) % batch_size == 0:
                        conn.commit()
                        logger.info(f"Committed batch at {idx + 1}/{total}")

                success_count += 1

                if (idx + 1) % 10 == 0 or idx == 0:
                    logger.info(
                        f"[{idx + 1}/{total}] Reindexed episode {ep_id} "
                        f"({len(combined_text)} chars)"
                    )

            except Exception as e:
                error_count += 1
                logger.error(f"Failed to reindex episode {ep_id}: {e}")
                conn.rollback()

        # Final commit
        if not dry_run:
            conn.commit()

        logger.info(
            f"\nDone. Success: {success_count}, Errors: {error_count}, "
            f"Total: {total}, Dry run: {dry_run}"
        )

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Reindex episode embeddings with combined query+reflection"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without making changes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Commit after N episodes (default: 50)",
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default="io",
        help="Project ID to reindex (default: io)",
    )

    args = parser.parse_args()
    reindex_episodes(
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        project_id=args.project_id,
    )


if __name__ == "__main__":
    main()
