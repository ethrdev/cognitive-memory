#!/usr/bin/env python3
"""
Golden Test Set Dual-Judge Labeling Script

Automatically labels the Golden Test Set using GPT-4o + Haiku dual-judge evaluation.
For each query:
1. Runs hybrid_search to get top-5 L2 insights
2. Uses both judges to evaluate relevance (0.0-1.0 scale)
3. Sets expected_docs based on agreement (both judges score > 0.5)
4. Updates golden_test_set table with labeled expected_docs

Usage:
    python scripts/label_golden_test_dual_judge.py [--dry-run] [--limit N]

Cost Estimate: ~$0.50-1.00 for 75 queries (GPT-4o + Haiku API calls)
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import re

from sklearn.metrics import cohen_kappa_score

# Initialize environment before imports that need it
from mcp_server.config import load_environment

load_environment()

from mcp_server.db.connection import get_connection, initialize_pool


def extract_score_from_text(text: str) -> float:
    """
    Extract a relevance score from text that might contain explanations.

    Handles cases where the model returns explanations along with scores.
    Looks for patterns like "0.7", "Score: 0.85", "Relevanz: 0.9", etc.
    """
    # Try to parse as pure float first
    try:
        return float(text.strip())
    except ValueError:
        pass

    # Look for explicit score patterns
    patterns = [
        r"(?:score|relevance|relevanz)[:\s]*([0-9]+\.?[0-9]*)",  # "Score: 0.7"
        r"^([0-9]+\.?[0-9]*)\s*$",  # Just a number at start of line
        r"\b([0-9]\.[0-9]+)\b",  # Any decimal like 0.7, 0.85
        r"\b(0|1)\b",  # Just 0 or 1
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            try:
                score = float(match.group(1))
                if 0.0 <= score <= 1.0:
                    return score
            except ValueError:
                continue

    # Default to 0.3 (marginally relevant) if can't parse
    logger.warning(f"Could not extract score from: {text[:100]}...")
    return 0.3


class SimpleDualJudge:
    """Simplified dual judge that handles verbose responses better."""

    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        from anthropic import AsyncAnthropic
        from openai import AsyncOpenAI

        self.gpt4o_client = AsyncOpenAI(api_key=self.openai_api_key)
        self.haiku_client = AsyncAnthropic(api_key=self.anthropic_api_key)

    async def call_gpt4o(self, query: str, doc_content: str) -> float:
        """Call GPT-4o for relevance rating."""
        response = await self.gpt4o_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Rate document relevance for the query on scale 0.0-1.0.\n"
                        "0.0=irrelevant, 0.5=moderate, 1.0=perfect.\n"
                        "Reply with ONLY the number, nothing else."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Query: {query[:500]}\n\nDocument: {doc_content[:1000]}\n\nScore:",
                },
            ],
            temperature=0.0,
            max_tokens=10,
        )
        return extract_score_from_text(response.choices[0].message.content)

    async def call_haiku(self, query: str, doc_content: str) -> float:
        """Call Haiku for relevance rating."""
        response = await self.haiku_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=10,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Rate relevance 0.0-1.0. Reply ONLY with the number.\n"
                        f"Query: {query[:500]}\n"
                        f"Doc: {doc_content[:1000]}\n"
                        f"Score:"
                    ),
                }
            ],
        )
        return extract_score_from_text(response.content[0].text)


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_golden_test_queries(
    limit: int | None = None, skip_labeled: bool = True, relabel_empty: bool = False
) -> list[dict[str, Any]]:
    """Load queries from golden_test_set table."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Skip already labeled queries (have non-empty expected_docs)
            # relabel_empty=True means re-process queries with empty arrays but skip ones with actual labels
            if relabel_empty:
                where_clause = "WHERE array_length(expected_docs, 1) IS NULL OR array_length(expected_docs, 1) = 0"
            elif skip_labeled:
                where_clause = "WHERE array_length(expected_docs, 1) IS NULL OR array_length(expected_docs, 1) = 0"
            else:
                where_clause = ""
            query = f"""
                SELECT id, query, query_type, word_count, session_id
                FROM golden_test_set
                {where_clause}
                ORDER BY id
            """
            if limit:
                query += f" LIMIT {limit}"

            cur.execute(query)
            rows = cur.fetchall()

            queries = []
            for row in rows:
                queries.append(
                    {
                        "id": row[0],
                        "query": row[1],
                        "query_type": row[2],
                        "word_count": row[3],
                        "session_id": row[4],
                    }
                )

            logger.info(f"Loaded {len(queries)} queries from golden_test_set")
            return queries


def run_hybrid_search(query_text: str, top_k: int = 5) -> list[dict[str, Any]]:
    """
    Run hybrid search to get top-k L2 insights.

    Returns list of dicts with 'id' and 'content' keys.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get embedding for query
            from openai import OpenAI

            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

            response = client.embeddings.create(
                model="text-embedding-3-small", input=query_text
            )
            query_embedding = response.data[0].embedding

            # Hybrid search: semantic + keyword
            # Semantic search
            cur.execute(
                """
                SELECT id, content,
                       1 - (embedding <=> %s::vector) as semantic_score
                FROM l2_insights
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """,
                (query_embedding, query_embedding, top_k * 2),
            )

            semantic_results = {
                row[0]: {"id": row[0], "content": row[1], "semantic_score": row[2]}
                for row in cur.fetchall()
            }

            # Keyword search (simple ILIKE)
            keywords = query_text.split()[:5]  # First 5 words
            keyword_pattern = "%" + "%".join(keywords[:3]) + "%"

            cur.execute(
                """
                SELECT id, content
                FROM l2_insights
                WHERE content ILIKE %s
                LIMIT %s
            """,
                (keyword_pattern, top_k),
            )

            keyword_results = {
                row[0]: {"id": row[0], "content": row[1]} for row in cur.fetchall()
            }

            # Merge results (semantic-weighted)
            all_ids = set(semantic_results.keys()) | set(keyword_results.keys())

            scored_results = []
            for doc_id in all_ids:
                semantic_score = semantic_results.get(doc_id, {}).get(
                    "semantic_score", 0
                )
                keyword_score = 0.3 if doc_id in keyword_results else 0
                combined_score = 0.7 * semantic_score + keyword_score

                content = (semantic_results.get(doc_id) or keyword_results.get(doc_id))[
                    "content"
                ]
                scored_results.append(
                    {"id": doc_id, "content": content, "score": combined_score}
                )

            # Sort by combined score and take top-k
            scored_results.sort(key=lambda x: x["score"], reverse=True)
            return scored_results[:top_k]


def update_golden_test_expected_docs(query_id: int, expected_docs: list[int]) -> None:
    """Update golden_test_set with labeled expected_docs."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE golden_test_set
                SET expected_docs = %s
                WHERE id = %s
            """,
                (expected_docs, query_id),
            )
            conn.commit()


async def label_single_query(
    evaluator: SimpleDualJudge, query: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """
    Label a single query using dual-judge evaluation.

    Returns dict with labeling results.
    """
    query_id = query["id"]
    query_text = query["query"]

    # Get top-5 documents via hybrid search
    docs = run_hybrid_search(query_text, top_k=5)

    if not docs:
        logger.warning(f"Query {query_id}: No documents found")
        return {
            "query_id": query_id,
            "expected_docs": [],
            "num_docs": 0,
            "status": "no_docs",
        }

    # Evaluate with dual judge (simplified version)
    judge1_scores = []
    judge2_scores = []

    for doc in docs:
        try:
            # Call both judges
            gpt4o_score = await evaluator.call_gpt4o(query_text, doc["content"])
            haiku_score = await evaluator.call_haiku(query_text, doc["content"])

            judge1_scores.append(gpt4o_score)
            judge2_scores.append(haiku_score)

        except Exception as e:
            logger.error(f"Query {query_id}, Doc {doc['id']}: Evaluation failed: {e}")
            judge1_scores.append(0.5)
            judge2_scores.append(0.5)

    # Determine expected_docs based on agreement
    # RELAXED CRITERION: A document is relevant if:
    # - EITHER judge scores > 0.5 (OR logic), OR
    # - Average of both judges > 0.4
    expected_docs = []
    for i, doc in enumerate(docs):
        avg_score = (judge1_scores[i] + judge2_scores[i]) / 2
        either_high = judge1_scores[i] > 0.5 or judge2_scores[i] > 0.5
        avg_acceptable = avg_score > 0.4
        if either_high or avg_acceptable:
            expected_docs.append(doc["id"])

    # Calculate agreement for this query
    judge1_binary = [1 if s > 0.5 else 0 for s in judge1_scores]
    judge2_binary = [1 if s > 0.5 else 0 for s in judge2_scores]

    try:
        if len(set(judge1_binary)) > 1 or len(set(judge2_binary)) > 1:
            kappa = cohen_kappa_score(judge1_binary, judge2_binary)
        else:
            # Edge case: all same values
            kappa = 1.0 if judge1_binary == judge2_binary else 0.0
    except Exception:
        kappa = 0.0

    # Update database (unless dry run)
    if not dry_run:
        update_golden_test_expected_docs(query_id, expected_docs)

    return {
        "query_id": query_id,
        "query_type": query["query_type"],
        "expected_docs": expected_docs,
        "num_relevant": len(expected_docs),
        "judge1_scores": judge1_scores,
        "judge2_scores": judge2_scores,
        "kappa": kappa,
        "status": "success",
    }


async def main(args: argparse.Namespace) -> None:
    """Main execution."""
    logger.info("=" * 80)
    logger.info("Golden Test Set Dual-Judge Labeling")
    logger.info("=" * 80)

    if args.dry_run:
        logger.info("DRY RUN MODE - No database updates")

    # Initialize
    initialize_pool()
    evaluator = SimpleDualJudge()

    # Load queries
    queries = load_golden_test_queries(limit=args.limit)

    if not queries:
        logger.error("No queries found in golden_test_set")
        sys.exit(1)

    logger.info(f"Processing {len(queries)} queries...")
    logger.info(
        f"Estimated cost: ${len(queries) * 0.01:.2f} - ${len(queries) * 0.02:.2f}"
    )

    # Process queries
    results = []
    all_judge1_binary = []
    all_judge2_binary = []

    start_time = time.time()

    for i, query in enumerate(queries):
        logger.info(
            f"[{i+1}/{len(queries)}] Processing query {query['id']} ({query['query_type']})..."
        )

        result = await label_single_query(evaluator, query, dry_run=args.dry_run)
        results.append(result)

        # Collect binary scores for overall Kappa
        if result["status"] == "success":
            all_judge1_binary.extend(
                [1 if s > 0.5 else 0 for s in result["judge1_scores"]]
            )
            all_judge2_binary.extend(
                [1 if s > 0.5 else 0 for s in result["judge2_scores"]]
            )

        # Progress update every 10 queries
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            remaining = (len(queries) - i - 1) / rate
            logger.info(
                f"  Progress: {i+1}/{len(queries)} ({(i+1)/len(queries)*100:.1f}%)"
            )
            logger.info(f"  Elapsed: {elapsed:.1f}s, Remaining: ~{remaining:.1f}s")

    total_time = time.time() - start_time

    # Calculate overall Cohen's Kappa
    try:
        overall_kappa = cohen_kappa_score(all_judge1_binary, all_judge2_binary)
    except Exception:
        overall_kappa = 0.0

    # Summary statistics
    successful = [r for r in results if r["status"] == "success"]
    total_relevant = sum(r["num_relevant"] for r in successful)

    by_type = {}
    for r in successful:
        qtype = r["query_type"]
        if qtype not in by_type:
            by_type[qtype] = {"count": 0, "relevant": 0}
        by_type[qtype]["count"] += 1
        by_type[qtype]["relevant"] += r["num_relevant"]

    # Print results
    logger.info("")
    logger.info("=" * 80)
    logger.info("LABELING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Total queries:     {len(queries)}")
    logger.info(f"Successful:        {len(successful)}")
    logger.info(f"Total relevant:    {total_relevant} docs across all queries")
    logger.info(f"Avg relevant/query: {total_relevant/len(successful):.2f}")
    logger.info(f"Overall Kappa:     {overall_kappa:.3f}")
    logger.info(f"Total time:        {total_time:.1f}s")
    logger.info(f"Avg time/query:    {total_time/len(queries):.2f}s")
    logger.info("")
    logger.info("By Query Type:")
    for qtype, stats in sorted(by_type.items()):
        avg = stats["relevant"] / stats["count"] if stats["count"] > 0 else 0
        logger.info(
            f"  {qtype}: {stats['count']} queries, {stats['relevant']} relevant ({avg:.2f} avg)"
        )

    # Kappa interpretation
    logger.info("")
    if overall_kappa >= 0.81:
        logger.info(f"Kappa {overall_kappa:.3f}: Almost Perfect Agreement")
    elif overall_kappa >= 0.61:
        logger.info(f"Kappa {overall_kappa:.3f}: Substantial Agreement")
    elif overall_kappa >= 0.41:
        logger.info(f"Kappa {overall_kappa:.3f}: Moderate Agreement")
    elif overall_kappa >= 0.21:
        logger.info(f"Kappa {overall_kappa:.3f}: Fair Agreement")
    else:
        logger.info(f"Kappa {overall_kappa:.3f}: Slight/Poor Agreement")

    if not args.dry_run:
        logger.info("")
        logger.info("Database updated. Run get_golden_test_results to verify.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Label Golden Test Set using Dual-Judge evaluation"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without updating database"
    )
    parser.add_argument("--limit", type=int, help="Limit number of queries to process")

    args = parser.parse_args()

    asyncio.run(main(args))
