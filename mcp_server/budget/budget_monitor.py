"""
Budget Monitoring Module

Provides monthly cost aggregation, budget threshold checks, and cost projections
for NFR003 compliance (€5-10/mo budget target).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from mcp_server.config import get_config
from mcp_server.db.connection import get_connection_sync

logger = logging.getLogger(__name__)


def get_monthly_cost(year: int | None = None, month: int | None = None) -> float:
    """
    Get total API cost for a specific month.

    Args:
        year: Year (defaults to current year)
        month: Month (1-12, defaults to current month)

    Returns:
        float: Total cost in EUR for the specified month

    Example:
        >>> # Get cost for current month
        >>> cost = get_monthly_cost()
        >>> print(f"Current month: €{cost:.2f}")

        >>> # Get cost for specific month
        >>> cost = get_monthly_cost(year=2025, month=11)
        >>> print(f"November 2025: €{cost:.2f}")
    """
    today = date.today()
    target_year = year if year is not None else today.year
    target_month = month if month is not None else today.month

    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            query = """
                SELECT COALESCE(SUM(estimated_cost), 0.0)
                FROM api_cost_log
                WHERE EXTRACT(YEAR FROM date) = %s
                  AND EXTRACT(MONTH FROM date) = %s
            """
            cursor.execute(query, (target_year, target_month))

            result = cursor.fetchone()
            total_cost = float(result[0]) if result else 0.0

            logger.debug(
                f"Monthly cost for {target_year}-{target_month:02d}: €{total_cost:.4f}"
            )

            return total_cost

    except Exception as e:
        logger.error(f"Failed to calculate monthly cost: {type(e).__name__}: {e}")
        return 0.0


def get_monthly_cost_by_api(
    year: int | None = None, month: int | None = None
) -> list[dict[str, Any]]:
    """
    Get monthly cost breakdown by API for a specific month.

    Args:
        year: Year (defaults to current year)
        month: Month (1-12, defaults to current month)

    Returns:
        List of dicts with keys: api_name, total_cost, num_calls, total_tokens
        Sorted by total_cost descending

    Example:
        >>> breakdown = get_monthly_cost_by_api()
        >>> for api in breakdown:
        ...     print(f"{api['api_name']}: €{api['total_cost']:.4f}")
        openai_embeddings: €2.3450
        gpt4o_judge: €1.2345
        haiku_eval: €0.5678
    """
    today = date.today()
    target_year = year if year is not None else today.year
    target_month = month if month is not None else today.month

    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    api_name,
                    SUM(estimated_cost) as total_cost,
                    SUM(num_calls) as num_calls,
                    SUM(token_count) as total_tokens
                FROM api_cost_log
                WHERE EXTRACT(YEAR FROM date) = %s
                  AND EXTRACT(MONTH FROM date) = %s
                GROUP BY api_name
                ORDER BY total_cost DESC
            """
            cursor.execute(query, (target_year, target_month))

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
                f"Monthly cost breakdown for {target_year}-{target_month:02d}: "
                f"{len(results)} APIs tracked"
            )

            return results

    except Exception as e:
        logger.error(f"Failed to get monthly cost breakdown: {type(e).__name__}: {e}")
        return []


def project_monthly_cost() -> dict[str, Any]:
    """
    Project total monthly cost based on current spending rate.

    Calculates projected monthly cost by:
    1. Getting total cost so far this month
    2. Calculating daily average spending rate
    3. Projecting to end of month based on average rate

    Returns:
        Dict with:
        - current_cost: float (cost so far this month in EUR)
        - projected_cost: float (projected monthly cost in EUR)
        - days_elapsed: int (days elapsed in current month)
        - days_remaining: int (days remaining in current month)
        - avg_daily_cost: float (average daily cost in EUR)

    Example:
        >>> projection = project_monthly_cost()
        >>> print(f"Current: €{projection['current_cost']:.2f}")
        >>> print(f"Projected: €{projection['projected_cost']:.2f}")
        Current: €3.45
        Projected: €8.67
    """
    today = date.today()

    # Get first day of current month
    first_day = date(today.year, today.month, 1)

    # Get last day of current month
    if today.month == 12:
        last_day = date(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(today.year, today.month + 1, 1) - timedelta(days=1)

    # Calculate days elapsed and remaining
    days_elapsed = (today - first_day).days + 1  # Include today
    days_in_month = (last_day - first_day).days + 1
    days_remaining = days_in_month - days_elapsed

    # Get current month's cost
    current_cost = get_monthly_cost()

    # Calculate average daily cost
    avg_daily_cost = current_cost / days_elapsed if days_elapsed > 0 else 0.0

    # Project monthly cost
    projected_cost = current_cost + (avg_daily_cost * days_remaining)

    logger.debug(
        f"Cost projection: current=€{current_cost:.4f}, "
        f"projected=€{projected_cost:.4f}, "
        f"avg_daily=€{avg_daily_cost:.4f}"
    )

    return {
        "current_cost": current_cost,
        "projected_cost": projected_cost,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "avg_daily_cost": avg_daily_cost,
        "days_in_month": days_in_month,
    }


def check_budget_threshold() -> dict[str, Any]:
    """
    Check if projected monthly cost exceeds budget threshold.

    Reads budget configuration from config.yaml:
    - budget.monthly_limit_eur: Monthly budget limit (default €10.00)
    - budget.alert_threshold_pct: Alert threshold percentage (default 80%)

    Returns:
        Dict with:
        - projected_cost: float (projected monthly cost in EUR)
        - budget_limit: float (monthly budget limit in EUR)
        - alert_threshold: float (alert threshold in EUR)
        - budget_exceeded: bool (True if projected > limit)
        - alert_triggered: bool (True if projected > alert threshold)
        - utilization_pct: float (projected / limit * 100)

    Example:
        >>> status = check_budget_threshold()
        >>> if status['alert_triggered']:
        ...     print(f"⚠️ Budget alert: {status['utilization_pct']:.1f}% of limit")
        >>> if status['budget_exceeded']:
        ...     print(f"❌ Budget exceeded: €{status['projected_cost']:.2f} > €{status['budget_limit']:.2f}")
    """
    # Get projection
    projection = project_monthly_cost()
    projected_cost = projection["projected_cost"]

    # Load budget configuration
    try:
        config = get_config()
        budget_config = config.get("budget", {})
        monthly_limit = float(budget_config.get("monthly_limit_eur", 10.0))
        alert_threshold_pct = float(budget_config.get("alert_threshold_pct", 80))
    except Exception as e:
        logger.warning(f"Failed to load budget config, using defaults: {e}")
        monthly_limit = 10.0
        alert_threshold_pct = 80.0

    # Calculate alert threshold
    alert_threshold = monthly_limit * (alert_threshold_pct / 100.0)

    # Calculate utilization percentage
    utilization_pct = (
        (projected_cost / monthly_limit * 100.0) if monthly_limit > 0 else 0.0
    )

    # Check thresholds
    budget_exceeded = projected_cost > monthly_limit
    alert_triggered = projected_cost > alert_threshold

    logger.debug(
        f"Budget check: projected=€{projected_cost:.2f}, "
        f"limit=€{monthly_limit:.2f}, "
        f"utilization={utilization_pct:.1f}%, "
        f"alert={alert_triggered}, "
        f"exceeded={budget_exceeded}"
    )

    return {
        "projected_cost": projected_cost,
        "budget_limit": monthly_limit,
        "alert_threshold": alert_threshold,
        "budget_exceeded": budget_exceeded,
        "alert_triggered": alert_triggered,
        "utilization_pct": utilization_pct,
        **projection,  # Include projection details
    }


def get_daily_costs(days: int = 30) -> list[dict[str, Any]]:
    """
    Get daily cost totals for the last N days.

    Args:
        days: Number of days to retrieve (default 30)

    Returns:
        List of dicts with keys: date, total_cost, num_calls, total_tokens
        Sorted by date descending (most recent first)

    Raises:
        ValueError: If days is not between 1 and 365

    Example:
        >>> daily = get_daily_costs(days=7)
        >>> for day in daily:
        ...     print(f"{day['date']}: €{day['total_cost']:.4f}")
        2025-11-20: €0.3456
        2025-11-19: €0.4123
        2025-11-18: €0.2987
    """
    # Input validation (: Prevent invalid day ranges)
    if not isinstance(days, int) or days <= 0 or days > 365:
        raise ValueError(f"days must be an integer between 1 and 365, got {days}")

    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            # Calculate start_date using Python timedelta (: SQL injection fix)
            start_date = date.today() - timedelta(days=days)

            query = """
                SELECT
                    date,
                    SUM(estimated_cost) as total_cost,
                    SUM(num_calls) as num_calls,
                    SUM(token_count) as total_tokens
                FROM api_cost_log
                WHERE date >= %s
                GROUP BY date
                ORDER BY date DESC
            """
            cursor.execute(query, (start_date,))

            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(
                    {
                        "date": row[0],
                        "total_cost": float(row[1]) if row[1] else 0.0,
                        "num_calls": int(row[2]) if row[2] else 0,
                        "total_tokens": int(row[3]) if row[3] else 0,
                    }
                )

            logger.debug(
                f"Retrieved {len(results)} daily cost entries (last {days} days)"
            )

            return results

    except Exception as e:
        logger.error(f"Failed to retrieve daily costs: {type(e).__name__}: {e}")
        return []
