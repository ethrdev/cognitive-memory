"""
Cost Logger Module

Provides CRUD operations for api_cost_log table to support budget monitoring.
Used by API clients (OpenAI, Anthropic) and budget monitoring utilities.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


def insert_cost_log(
    api_name: str,
    num_calls: int,
    token_count: int,
    estimated_cost: float,
    log_date: date | None = None,
) -> bool:
    """
    Insert API cost entry into api_cost_log table.

    Args:
        api_name: API identifier (e.g., 'openai_embeddings', 'gpt4o_judge',
                  'haiku_eval', 'haiku_reflection')
        num_calls: Number of API calls (usually 1)
        token_count: Total tokens used (input + output)
        estimated_cost: Cost in EUR
        log_date: Date for cost entry (defaults to today)

    Returns:
        bool: True if insertion successful, False otherwise

    Example:
        >>> insert_cost_log(
        ...     api_name='openai_embeddings',
        ...     num_calls=1,
        ...     token_count=1536,
        ...     estimated_cost=0.00002
        ... )
        True
    """
    if log_date is None:
        log_date = date.today()

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO api_cost_log (
                    date, api_name, num_calls, token_count, estimated_cost
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (log_date, api_name, num_calls, token_count, estimated_cost),
            )

            conn.commit()

            logger.info(
                f"API cost logged: {api_name} - €{estimated_cost:.6f} "
                f"({token_count} tokens, {num_calls} calls)"
            )

            return True

    except Exception as e:
        logger.error(
            f"Failed to insert cost log for {api_name}: {type(e).__name__}: {e}"
        )
        return False


def get_costs_by_date_range(
    start_date: date,
    end_date: date,
    api_name: str | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve API cost entries within a date range.

    Args:
        start_date: Start of date range (inclusive)
        end_date: End of date range (inclusive)
        api_name: Optional API filter (returns all APIs if None)

    Returns:
        List of dicts with keys: id, date, api_name, num_calls, token_count,
                                  estimated_cost, created_at

    Example:
        >>> from datetime import date, timedelta
        >>> end = date.today()
        >>> start = end - timedelta(days=30)
        >>> costs = get_costs_by_date_range(start, end)
        >>> len(costs) > 0
        True
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            if api_name is not None:
                query = """
                    SELECT id, date, api_name, num_calls, token_count,
                           estimated_cost, created_at
                    FROM api_cost_log
                    WHERE date >= %s AND date <= %s AND api_name = %s
                    ORDER BY date DESC, api_name
                """
                cursor.execute(query, (start_date, end_date, api_name))
            else:
                query = """
                    SELECT id, date, api_name, num_calls, token_count,
                           estimated_cost, created_at
                    FROM api_cost_log
                    WHERE date >= %s AND date <= %s
                    ORDER BY date DESC, api_name
                """
                cursor.execute(query, (start_date, end_date))

            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "id": row[0],
                        "date": row[1],
                        "api_name": row[2],
                        "num_calls": row[3],
                        "token_count": row[4],
                        "estimated_cost": row[5],
                        "created_at": row[6],
                    }
                )

            logger.info(
                f"Retrieved {len(results)} cost entries "
                f"({start_date} to {end_date}"
                f"{f', api={api_name}' if api_name else ''})"
            )

            return results

    except Exception as e:
        logger.error(f"Failed to retrieve cost logs: {type(e).__name__}: {e}")
        return []


def get_total_cost(days: int = 30) -> float:
    """
    Get total API cost over last N days.

    Args:
        days: Number of days to look back (default 30)

    Returns:
        float: Total cost in EUR

    Raises:
        ValueError: If days is not between 1 and 365

    Example:
        >>> total = get_total_cost(days=7)
        >>> isinstance(total, float)
        True
    """
    # Input validation (Story 3.10: Prevent invalid day ranges)
    if not isinstance(days, int) or days <= 0 or days > 365:
        raise ValueError(f"days must be an integer between 1 and 365, got {days}")

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Calculate start_date using Python timedelta (Story 3.10: SQL injection fix)
            start_date = date.today() - timedelta(days=days)

            query = """
                SELECT COALESCE(SUM(estimated_cost), 0.0)
                FROM api_cost_log
                WHERE date >= %s
            """
            cursor.execute(query, (start_date,))

            result = cursor.fetchone()
            total_cost = float(result[0]) if result else 0.0

            logger.debug(f"Total cost (last {days} days): €{total_cost:.4f}")

            return total_cost

    except Exception as e:
        logger.error(f"Failed to calculate total cost: {type(e).__name__}: {e}")
        return 0.0


def get_cost_by_api(days: int = 30) -> list[dict[str, Any]]:
    """
    Get cost breakdown by API over last N days.

    Args:
        days: Number of days to look back (default 30)

    Returns:
        List of dicts with keys: api_name, total_cost, num_calls, total_tokens

    Raises:
        ValueError: If days is not between 1 and 365

    Example:
        >>> breakdown = get_cost_by_api(days=30)
        >>> isinstance(breakdown, list)
        True
    """
    # Input validation (Story 3.10: Prevent invalid day ranges)
    if not isinstance(days, int) or days <= 0 or days > 365:
        raise ValueError(f"days must be an integer between 1 and 365, got {days}")

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Calculate start_date using Python timedelta (Story 3.10: SQL injection fix)
            start_date = date.today() - timedelta(days=days)

            query = """
                SELECT
                    api_name,
                    SUM(estimated_cost) as total_cost,
                    SUM(num_calls) as num_calls,
                    SUM(token_count) as total_tokens
                FROM api_cost_log
                WHERE date >= %s
                GROUP BY api_name
                ORDER BY total_cost DESC
            """
            cursor.execute(query, (start_date,))

            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "api_name": row[0],
                        "total_cost": float(row[1]) if row[1] else 0.0,
                        "num_calls": int(row[2]) if row[2] else 0,
                        "total_tokens": int(row[3]) if row[3] else 0,
                    }
                )

            logger.debug(
                f"Cost breakdown (last {days} days): {len(results)} APIs tracked"
            )

            return results

    except Exception as e:
        logger.error(f"Failed to get cost breakdown: {type(e).__name__}: {e}")
        return []


def delete_old_costs(days_to_keep: int = 365) -> int:
    """
    Delete cost entries older than specified number of days.

    Note: By default, Story 3.10 specifies unlimited retention for historical
    trend analysis. This function is provided for future use if retention
    policy changes.

    Args:
        days_to_keep: Number of days of data to retain (default 365)

    Returns:
        int: Number of rows deleted

    Example:
        >>> # Delete entries older than 2 years
        >>> deleted = delete_old_costs(days_to_keep=730)
        >>> deleted >= 0
        True
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            cutoff_date = date.today() - timedelta(days=days_to_keep)

            cursor.execute(
                """
                DELETE FROM api_cost_log
                WHERE date < %s
                """,
                (cutoff_date,),
            )

            deleted_count = cursor.rowcount
            conn.commit()

            logger.info(
                f"Deleted {deleted_count} cost entries older than {cutoff_date}"
            )

            return deleted_count

    except Exception as e:
        logger.error(f"Failed to delete old costs: {type(e).__name__}: {e}")
        return 0
