"""
Budget Monitoring Package

Provides budget monitoring, cost tracking, and alerting functionality
for NFR003 compliance (€5-10/mo budget target).
"""

from mcp_server.budget.budget_alerts import check_and_send_alerts
from mcp_server.budget.budget_monitor import (
    check_budget_threshold,
    get_daily_costs,
    get_monthly_cost,
    get_monthly_cost_by_api,
    project_monthly_cost,
)
from mcp_server.budget.cost_optimization import (
    calculate_potential_savings,
    get_cost_breakdown_insights,
    get_optimization_recommendations,
    validate_staged_dual_judge_transition,
)

__all__ = [
    "get_monthly_cost",
    "get_monthly_cost_by_api",
    "project_monthly_cost",
    "check_budget_threshold",
    "get_daily_costs",
    "check_and_send_alerts",
    "get_cost_breakdown_insights",
    "get_optimization_recommendations",
    "calculate_potential_savings",
    "validate_staged_dual_judge_transition",
]
