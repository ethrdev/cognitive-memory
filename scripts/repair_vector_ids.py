#!/usr/bin/env python3
"""
Vector ID Repair Script for Cognitive Memory System

Identifies graph nodes without vector_id and suggests matching L2 insights
based on semantic similarity. Can automatically link nodes to insights.

Problem Context:
- Graph nodes are often created without vector_id
- This disconnects them from semantic search (hybrid_search)
- Many nodes SHOULD have vector_id linking to their L2 insight

Solution:
1. Query all nodes where vector_id IS NULL
2. For each node, generate embedding and search L2 insights
3. Suggest matches based on cosine similarity threshold
4. Apply matches with --apply flag

Usage:
  python scripts/repair_vector_ids.py              # Dry-run: show recommendations
  python scripts/repair_vector_ids.py --apply      # Apply matches above threshold
  python scripts/repair_vector_ids.py --threshold 0.4  # Custom threshold (default: 0.5)
  python scripts/repair_vector_ids.py --limit 10   # Process first N nodes only
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI
from psycopg2.extras import DictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Represents a potential node-to-L2 match."""
    node_name: str
    node_id: str
    l2_id: int
    l2_content_preview: str
    similarity: float
    recommendation: str  # "auto", "review", "skip"


class VectorIdRepairTool:
    """Repairs missing vector_id links between nodes and L2 insights."""

    def __init__(
        self,
        threshold_auto: float = 0.5,
        threshold_review: float = 0.35,
        apply: bool = False,
        limit: int | None = None,
    ) -> None:
        """
        Initialize repair tool.

        Args:
            threshold_auto: Similarity threshold for auto-linking (default: 0.5)
            threshold_review: Similarity threshold for review suggestions (default: 0.35)
            apply: If True, apply auto-matches to database
            limit: Maximum number of nodes to process (None = all)
        """
        self.threshold_auto = threshold_auto
        self.threshold_review = threshold_review
        self.apply = apply
        self.limit = limit
        self.client: OpenAI | None = None
        self.database_url: str | None = None
        self.results: list[MatchResult] = []

    def load_credentials(self) -> None:
        """Load database and OpenAI credentials from environment."""
        # Prefer .env.development (has cloud DB) over .env (has localhost)
        env_file = Path(__file__).parent.parent / ".env.development"
        if not env_file.exists():
            env_file = Path(__file__).parent.parent / ".env"

        if env_file.exists():
            logger.info(f"Loading environment from {env_file}")
            load_dotenv(env_file)

        self.database_url = os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL not found in environment")

        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise ValueError("OPENAI_API_KEY not found in environment")

        self.client = OpenAI(api_key=openai_key)
        logger.info("Credentials loaded successfully")

    def get_embedding(self, text: str) -> list[float]:
        """Generate embedding for text using OpenAI."""
        if not self.client:
            raise RuntimeError("OpenAI client not initialized")

        response = self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        return response.data[0].embedding

    def parse_pg_vector(self, vec: str | list[float]) -> list[float]:
        """Parse PostgreSQL vector string to list of floats."""
        if isinstance(vec, list):
            return vec
        # PostgreSQL vector format: "[0.1,0.2,0.3,...]"
        vec_str = str(vec).strip("[]")
        return [float(x) for x in vec_str.split(",")]

    def cosine_similarity(self, a: list[float], b: str | list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a_np = np.array(a)
        b_parsed = self.parse_pg_vector(b)
        b_np = np.array(b_parsed)
        return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))

    def get_nodes_without_vector_id(self) -> list[dict[str, Any]]:
        """Query all nodes where vector_id is NULL."""
        if not self.database_url:
            raise RuntimeError("Database URL not loaded")

        with psycopg2.connect(self.database_url, cursor_factory=DictCursor) as conn:
            with conn.cursor() as cursor:
                query = """
                    SELECT id, name, label, properties, created_at
                    FROM nodes
                    WHERE vector_id IS NULL
                    ORDER BY created_at DESC
                """
                if self.limit:
                    query += f" LIMIT {self.limit}"

                cursor.execute(query)
                nodes = cursor.fetchall()

                logger.info(f"Found {len(nodes)} nodes without vector_id")
                return [dict(row) for row in nodes]

    def get_l2_insights_with_embeddings(self) -> list[dict[str, Any]]:
        """Query all L2 insights with their embeddings."""
        if not self.database_url:
            raise RuntimeError("Database URL not loaded")

        with psycopg2.connect(self.database_url, cursor_factory=DictCursor) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT id, content, embedding
                    FROM l2_insights
                    WHERE embedding IS NOT NULL
                    ORDER BY id
                """)
                insights = cursor.fetchall()

                logger.info(f"Loaded {len(insights)} L2 insights with embeddings")
                return [dict(row) for row in insights]

    def find_best_match(
        self,
        node_name: str,
        node_embedding: list[float],
        l2_insights: list[dict[str, Any]],
    ) -> tuple[int | None, str | None, float]:
        """
        Find best matching L2 insight for a node.

        Returns:
            Tuple of (l2_id, content_preview, similarity)
        """
        best_id = None
        best_content = None
        best_similarity = 0.0

        for insight in l2_insights:
            l2_embedding = insight["embedding"]
            if not l2_embedding:
                continue

            similarity = self.cosine_similarity(node_embedding, l2_embedding)

            if similarity > best_similarity:
                best_similarity = similarity
                best_id = insight["id"]
                best_content = insight["content"][:200] + "..." if len(insight["content"]) > 200 else insight["content"]

        return best_id, best_content, best_similarity

    def classify_match(self, similarity: float) -> str:
        """Classify match based on similarity thresholds."""
        if similarity >= self.threshold_auto:
            return "auto"
        elif similarity >= self.threshold_review:
            return "review"
        else:
            return "skip"

    def apply_match(self, node_id: str, vector_id: int, node_name: str) -> bool:
        """Apply vector_id to node in database."""
        if not self.database_url:
            raise RuntimeError("Database URL not loaded")

        try:
            with psycopg2.connect(self.database_url, cursor_factory=DictCursor) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE nodes
                        SET vector_id = %s,
                            properties = properties || %s::jsonb
                        WHERE id = %s::uuid
                        RETURNING id
                        """,
                        (
                            vector_id,
                            json.dumps({"vector_id_linked_at": datetime.now().isoformat()}),
                            node_id,
                        ),
                    )
                    result = cursor.fetchone()
                    conn.commit()

                    if result:
                        logger.info(f"  ✓ Applied: {node_name} → L2#{vector_id}")
                        return True
                    return False

        except Exception as e:
            logger.error(f"  ✗ Failed to apply: {node_name} - {e}")
            return False

    def run(self) -> None:
        """Execute the repair process."""
        logger.info("=" * 60)
        logger.info("Vector ID Repair Tool Started")
        logger.info(f"Mode: {'APPLY' if self.apply else 'DRY-RUN'}")
        logger.info(f"Auto-link threshold: {self.threshold_auto}")
        logger.info(f"Review threshold: {self.threshold_review}")
        logger.info("=" * 60)

        # Load credentials
        self.load_credentials()

        # Get nodes without vector_id
        nodes = self.get_nodes_without_vector_id()
        if not nodes:
            logger.info("No nodes without vector_id found. Nothing to repair.")
            return

        # Get L2 insights with embeddings
        l2_insights = self.get_l2_insights_with_embeddings()
        if not l2_insights:
            logger.warning("No L2 insights with embeddings found. Cannot proceed.")
            return

        # Process each node
        auto_count = 0
        review_count = 0
        skip_count = 0
        applied_count = 0

        logger.info(f"\nProcessing {len(nodes)} nodes...")
        logger.info("-" * 60)

        for i, node in enumerate(nodes):
            node_name = node["name"]
            node_id = str(node["id"])

            # Generate embedding for node name + label
            search_text = f"{node_name} {node.get('label', '')}"
            try:
                node_embedding = self.get_embedding(search_text)
            except Exception as e:
                logger.warning(f"  [{i+1}/{len(nodes)}] Skipping {node_name}: embedding failed - {e}")
                skip_count += 1
                continue

            # Find best match
            l2_id, l2_content, similarity = self.find_best_match(
                node_name, node_embedding, l2_insights
            )

            # Classify
            recommendation = self.classify_match(similarity)

            if recommendation == "auto":
                auto_count += 1
                logger.info(f"  [{i+1}/{len(nodes)}] AUTO: {node_name}")
                logger.info(f"       → L2#{l2_id} (similarity: {similarity:.3f})")
                logger.info(f"       → {l2_content[:80]}...")

                if self.apply and l2_id:
                    if self.apply_match(node_id, l2_id, node_name):
                        applied_count += 1

            elif recommendation == "review":
                review_count += 1
                logger.info(f"  [{i+1}/{len(nodes)}] REVIEW: {node_name}")
                logger.info(f"       → L2#{l2_id} (similarity: {similarity:.3f})")

            else:
                skip_count += 1
                if similarity > 0.2:  # Only log if there was some match
                    logger.debug(f"  [{i+1}/{len(nodes)}] SKIP: {node_name} (best: {similarity:.3f})")

            # Store result
            if l2_id and l2_content:
                self.results.append(MatchResult(
                    node_name=node_name,
                    node_id=node_id,
                    l2_id=l2_id,
                    l2_content_preview=l2_content,
                    similarity=similarity,
                    recommendation=recommendation,
                ))

        # Summary
        logger.info("-" * 60)
        logger.info("SUMMARY")
        logger.info("-" * 60)
        logger.info(f"Total nodes processed: {len(nodes)}")
        logger.info(f"  AUTO (similarity >= {self.threshold_auto}): {auto_count}")
        logger.info(f"  REVIEW (>= {self.threshold_review}): {review_count}")
        logger.info(f"  SKIP (< {self.threshold_review}): {skip_count}")
        if self.apply:
            logger.info(f"  Applied: {applied_count}")
        else:
            logger.info(f"\nRe-run with --apply to link {auto_count} auto-matches")

        logger.info("=" * 60)
        logger.info("Vector ID Repair Tool Completed")
        logger.info("=" * 60)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Repair missing vector_id links between nodes and L2 insights"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply auto-matches to database (default: dry-run)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Similarity threshold for auto-linking (default: 0.5)",
    )
    parser.add_argument(
        "--review-threshold",
        type=float,
        default=0.35,
        help="Similarity threshold for review suggestions (default: 0.35)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of nodes to process (default: all)",
    )

    args = parser.parse_args()

    try:
        tool = VectorIdRepairTool(
            threshold_auto=args.threshold,
            threshold_review=args.review_threshold,
            apply=args.apply,
            limit=args.limit,
        )
        tool.run()
        return 0

    except Exception as e:
        logger.error(f"Repair tool failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
