"""
Evaluation Logger Module

Handles logging of evaluation results to PostgreSQL database.
Logs to both evaluation_log (detailed results) and api_cost_log (cost tracking).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


async def log_evaluation(
    query: str,
    context: List[str],
    answer: str,
    reward_score: float,
    reasoning: str,
    token_count: int,
    cost_eur: float,
    api_name: str = "haiku_eval",
) -> None:
    """
    Log evaluation results to database.

    Logs to:
    1. evaluation_log: Detailed evaluation results (query, answer, reward, reasoning)
    2. api_cost_log: Cost tracking for budget monitoring

    Args:
        query: User query that was evaluated
        context: Retrieved L2 Insights (Top-5 from Hybrid Search)
        answer: Generated answer that was evaluated
        reward_score: Reward score (-1.0 to +1.0)
        reasoning: Haiku's evaluation reasoning
        token_count: Total tokens used (input + output)
        cost_eur: Estimated cost in EUR
        api_name: API name for cost tracking (default: "haiku_eval")
                  Use "haiku_reflexion" for reflexion calls ()

    Example:
        >>> await log_evaluation(
        ...     query="What is consciousness?",
        ...     context=["Context 1...", "Context 2..."],
        ...     answer="Consciousness is...",
        ...     reward_score=0.85,
        ...     reasoning="Answer is relevant and accurate...",
        ...     token_count=450,
        ...     cost_eur=0.00125
        ... )
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Insert into evaluation_log (detailed results)
            cursor.execute(
                """
                INSERT INTO evaluation_log (
                    query, context, answer, reward_score, reasoning, token_count, cost_eur
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (query, context, answer, reward_score, reasoning, token_count, cost_eur),
            )

            # Insert into api_cost_log (cost tracking)
            today = date.today()
            cursor.execute(
                """
                INSERT INTO api_cost_log (
                    date, api_name, num_calls, token_count, estimated_cost
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (today, api_name, 1, token_count, cost_eur),
            )

            conn.commit()

            logger.info(
                f"Evaluation logged ({api_name}): reward={reward_score:.3f}, "
                f"tokens={token_count}, cost=€{cost_eur:.6f}"
            )

    except Exception as e:
        logger.error(f"Failed to log evaluation to database: {type(e).__name__}: {e}")
        # Don't raise - logging failure shouldn't block evaluation
        # Evaluation result is still valid and returned to caller


async def get_recent_evaluations(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve recent evaluations from database.

    Args:
        limit: Maximum number of evaluations to retrieve (default: 10)

    Returns:
        List of evaluation dictionaries with keys:
        - id, timestamp, query, answer, reward_score, reasoning, token_count, cost_eur

    Example:
        >>> recent = await get_recent_evaluations(limit=5)
        >>> for eval in recent:
        ...     print(f"Reward: {eval['reward_score']}, Query: {eval['query'][:50]}")
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, query, answer, reward_score, reasoning, token_count, cost_eur
                FROM evaluation_log
                ORDER BY timestamp DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()

            # Convert to list of dicts
            evaluations = []
            for row in rows:
                evaluations.append(
                    {
                        "id": row["id"],
                        "timestamp": row["timestamp"],
                        "query": row["query"],
                        "answer": row["answer"],
                        "reward_score": row["reward_score"],
                        "reasoning": row["reasoning"],
                        "token_count": row["token_count"],
                        "cost_eur": row["cost_eur"],
                    }
                )

            return evaluations

    except Exception as e:
        logger.error(f"Failed to retrieve recent evaluations: {type(e).__name__}: {e}")
        return []


async def get_evaluation_stats(days: int = 30) -> Dict[str, Any]:
    """
    Get evaluation statistics for the last N days.

    Args:
        days: Number of days to analyze (default: 30)

    Returns:
        Dictionary with statistics:
        - total_evaluations: Total number of evaluations
        - avg_reward: Average reward score
        - low_quality_count: Evaluations below threshold (0.3)
        - low_quality_pct: Percentage of low quality evaluations
        - total_cost: Total cost in EUR

    Example:
        >>> stats = await get_evaluation_stats(days=7)
        >>> print(f"Avg reward: {stats['avg_reward']:.3f}")
        >>> print(f"Low quality: {stats['low_quality_pct']:.1f}%")
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total_evaluations,
                    ROUND(AVG(reward_score)::numeric, 3) as avg_reward,
                    ROUND(MIN(reward_score)::numeric, 3) as min_reward,
                    ROUND(MAX(reward_score)::numeric, 3) as max_reward,
                    COUNT(CASE WHEN reward_score < 0.3 THEN 1 END) as low_quality_count,
                    ROUND(SUM(cost_eur)::numeric, 6) as total_cost
                FROM evaluation_log
                WHERE timestamp >= NOW() - INTERVAL '%s days'
                """,
                (days,),
            )
            row = cursor.fetchone()

            if row is None or row["total_evaluations"] == 0:
                return {
                    "total_evaluations": 0,
                    "avg_reward": 0.0,
                    "min_reward": 0.0,
                    "max_reward": 0.0,
                    "low_quality_count": 0,
                    "low_quality_pct": 0.0,
                    "total_cost": 0.0,
                }

            total = row["total_evaluations"]
            low_quality = row["low_quality_count"]
            low_quality_pct = (low_quality / total * 100.0) if total > 0 else 0.0

            return {
                "total_evaluations": total,
                "avg_reward": float(row["avg_reward"] or 0.0),
                "min_reward": float(row["min_reward"] or 0.0),
                "max_reward": float(row["max_reward"] or 0.0),
                "low_quality_count": low_quality,
                "low_quality_pct": round(low_quality_pct, 1),
                "total_cost": float(row["total_cost"] or 0.0),
            }

    except Exception as e:
        logger.error(f"Failed to get evaluation stats: {type(e).__name__}: {e}")
        return {
            "total_evaluations": 0,
            "avg_reward": 0.0,
            "min_reward": 0.0,
            "max_reward": 0.0,
            "low_quality_count": 0,
            "low_quality_pct": 0.0,
            "total_cost": 0.0,
        }
