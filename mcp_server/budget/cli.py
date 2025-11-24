#!/usr/bin/env python3
"""
Budget Monitoring CLI Dashboard

Provides command-line interface for viewing budget status, cost breakdowns,
and optimization recommendations.

Usage:
    python -m mcp_server.budget.cli dashboard     # Overview
    python -m mcp_server.budget.cli breakdown     # Detailed breakdown
    python -m mcp_server.budget.cli optimize      # Recommendations
    python -m mcp_server.budget.cli alerts        # Check alerts
    python -m mcp_server.budget.cli daily         # Daily costs
"""

import argparse
import sys
from datetime import date
from typing import Any, Dict, List

try:
    from tabulate import tabulate
except ImportError:
    print("Error: tabulate package not installed")
    print("Install with: pip install tabulate")
    sys.exit(1)

from mcp_server.budget import (
    calculate_potential_savings,
    check_and_send_alerts,
    check_budget_threshold,
    get_cost_breakdown_insights,
    get_daily_costs,
    get_monthly_cost,
    get_monthly_cost_by_api,
    get_optimization_recommendations,
    project_monthly_cost,
    validate_staged_dual_judge_transition,
)


def print_header(title: str) -> None:
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_section(title: str) -> None:
    """Print formatted section title."""
    print(f"\n{title}")
    print("-" * len(title))


def format_currency(amount: float) -> str:
    """Format amount as EUR currency."""
    return f"€{amount:.2f}"


def format_percentage(pct: float) -> str:
    """Format percentage."""
    return f"{pct:.1f}%"


def cmd_dashboard(args: argparse.Namespace) -> None:
    """Display budget dashboard overview."""
    print_header("Budget Monitoring Dashboard")

    # Get budget status
    status = check_budget_threshold()

    # Budget Status Section
    print_section("Budget Status")

    budget_data = [
        ["Current Cost (MTD)", format_currency(status["current_cost"])],
        ["Projected Monthly Cost", format_currency(status["projected_cost"])],
        ["Monthly Budget Limit", format_currency(status["budget_limit"])],
        ["Alert Threshold", format_currency(status["alert_threshold"])],
        ["Budget Utilization", format_percentage(status["utilization_pct"])],
    ]

    print(tabulate(budget_data, tablefmt="simple"))

    # Status indicator
    if status["budget_exceeded"]:
        print("\n❌ BUDGET EXCEEDED - Immediate action required!")
    elif status["alert_triggered"]:
        print("\n⚠️  BUDGET ALERT - Monitor usage closely")
    else:
        print("\n✓ Budget status: OK")

    # Month Progress Section
    print_section("Month Progress")

    progress_data = [
        ["Days Elapsed", f"{status['days_elapsed']} / {status['days_in_month']}"],
        ["Days Remaining", status["days_remaining"]],
        ["Average Daily Cost", format_currency(status["avg_daily_cost"])],
    ]

    print(tabulate(progress_data, tablefmt="simple"))

    # Cost Breakdown Section
    print_section("Cost Breakdown by API")

    breakdown = get_monthly_cost_by_api()

    if breakdown:
        breakdown_data = [
            [
                api["api_name"],
                format_currency(api["total_cost"]),
                api["num_calls"],
                f"{api['total_tokens']:,}",
            ]
            for api in breakdown
        ]

        print(
            tabulate(
                breakdown_data,
                headers=["API", "Cost", "Calls", "Tokens"],
                tablefmt="grid",
            )
        )
    else:
        print("No cost data available for current month")

    # Quick Recommendations
    print_section("Quick Insights")

    insights = get_cost_breakdown_insights()
    if insights["most_expensive"]:
        print(f"• Most expensive API: {insights['most_expensive']}")

    # Check dual judge transition
    dual_judge_status = validate_staged_dual_judge_transition()
    if dual_judge_status["transition_ready"]:
        print(
            f"• ✓ Ready for Staged Dual Judge transition "
            f"(Kappa: {dual_judge_status['current_kappa']:.3f})"
        )

    print("\nFor detailed recommendations, run: python -m mcp_server.budget.cli optimize")


def cmd_breakdown(args: argparse.Namespace) -> None:
    """Display detailed cost breakdown."""
    print_header("Detailed Cost Breakdown")

    # Monthly breakdown by API
    print_section("Monthly Cost by API")

    breakdown = get_monthly_cost_by_api()

    if breakdown:
        insights = get_cost_breakdown_insights()
        total_cost = insights["total_cost"]

        breakdown_data = [
            [
                api["api_name"],
                format_currency(api["total_cost"]),
                format_percentage(insights["cost_distribution"].get(api["api_name"], 0.0)),
                api["num_calls"],
                f"{api['total_tokens']:,}",
                format_currency(api["total_cost"] / api["num_calls"]) if api["num_calls"] > 0 else "€0.00",
            ]
            for api in breakdown
        ]

        print(
            tabulate(
                breakdown_data,
                headers=["API", "Total Cost", "% of Total", "Calls", "Tokens", "Cost/Call"],
                tablefmt="grid",
            )
        )

        print(f"\nTotal Monthly Cost: {format_currency(total_cost)}")
    else:
        print("No cost data available for current month")

    # Daily costs (last 7 days)
    if args.days:
        print_section(f"Daily Costs (Last {args.days} Days)")

        daily = get_daily_costs(days=args.days)

        if daily:
            daily_data = [
                [
                    entry["date"],
                    format_currency(entry["total_cost"]),
                    entry["num_calls"],
                    f"{entry['total_tokens']:,}",
                ]
                for entry in daily
            ]

            print(
                tabulate(
                    daily_data,
                    headers=["Date", "Cost", "Calls", "Tokens"],
                    tablefmt="grid",
                )
            )
        else:
            print("No daily cost data available")


def cmd_optimize(args: argparse.Namespace) -> None:
    """Display cost optimization recommendations."""
    print_header("Cost Optimization Recommendations")

    # Overall savings potential
    savings = calculate_potential_savings()

    print_section("Savings Potential")

    savings_data = [
        ["Current Monthly Cost", format_currency(savings["current_monthly_cost"])],
        ["Potential Savings", format_currency(savings["total_potential_savings"])],
        ["Optimized Monthly Cost", format_currency(savings["optimized_monthly_cost"])],
        ["Savings Percentage", format_percentage(savings["savings_pct"])],
    ]

    print(tabulate(savings_data, tablefmt="simple"))

    # Recommendations
    recommendations = get_optimization_recommendations()

    if recommendations:
        print_section(f"Recommendations ({len(recommendations)} found)")

        for i, rec in enumerate(recommendations, 1):
            print(f"\n{i}. {rec['category'].upper()} - {rec['impact'].upper()} Impact")
            print(f"   Recommendation: {rec['recommendation']}")
            print(f"   Savings: {format_currency(rec['estimated_savings_eur'])}/mo ({format_percentage(rec['estimated_savings_pct'])})")
            print(f"   Trade-off: {rec['trade_off']}")

    else:
        print("\nNo optimization recommendations available (system already optimized)")

    # Staged Dual Judge Transition Status
    print_section("Staged Dual Judge Transition ()")

    dual_judge_status = validate_staged_dual_judge_transition()

    dj_data = [
        ["Current Mode", dual_judge_status["current_mode"].replace("_", " ").title()],
        ["Cohen's Kappa", f"{dual_judge_status['current_kappa']:.3f}"],
        ["Kappa Threshold", f"{dual_judge_status['kappa_threshold']:.3f}"],
        ["Ground Truth Count", dual_judge_status["ground_truth_count"]],
        ["Transition Ready", "✓ Yes" if dual_judge_status["transition_ready"] else "✗ No"],
    ]

    print(tabulate(dj_data, tablefmt="simple"))

    print(f"\nRecommendation: {dual_judge_status['recommendation']}")


def cmd_alerts(args: argparse.Namespace) -> None:
    """Check budget alerts and send notifications if needed."""
    print_header("Budget Alerts")

    if args.send:
        # Trigger alert check and send notifications
        result = check_and_send_alerts()

        print("Alert Check Results:")
        print(f"  Alert Sent: {'Yes' if result['alert_sent'] else 'No'}")

        if result["alert_sent"]:
            print(f"  Alert Type: {result['alert_type']}")
            print(f"  Notification Methods: {', '.join(result['notification_methods'])}")
        elif result.get("reason") == "duplicate_prevention":
            print(f"  Reason: Alert already sent today ({result['alert_type']})")
        else:
            print("  Reason: Budget status OK, no alerts needed")

        print("\nBudget Status:")
    else:
        # Just show budget status without sending alerts
        result = check_budget_threshold()
        print("Budget Status (no alerts sent):")

    status = result.get("budget_status", result)

    status_data = [
        ["Current Cost", format_currency(status["current_cost"])],
        ["Projected Cost", format_currency(status["projected_cost"])],
        ["Budget Limit", format_currency(status["budget_limit"])],
        ["Utilization", format_percentage(status["utilization_pct"])],
        ["Alert Threshold", format_currency(status["alert_threshold"])],
    ]

    print(tabulate(status_data, tablefmt="simple"))

    # Status indicator
    if status["budget_exceeded"]:
        print("\n❌ BUDGET EXCEEDED")
    elif status["alert_triggered"]:
        print("\n⚠️  BUDGET ALERT TRIGGERED")
    else:
        print("\n✓ Budget OK")

    if not args.send:
        print("\nTo trigger alert notifications, run with --send flag:")
        print("  python -m mcp_server.budget.cli alerts --send")


def cmd_daily(args: argparse.Namespace) -> None:
    """Display daily cost summary."""
    print_header(f"Daily Costs (Last {args.days} Days)")

    daily = get_daily_costs(days=args.days)

    if daily:
        daily_data = [
            [
                entry["date"],
                format_currency(entry["total_cost"]),
                entry["num_calls"],
                f"{entry['total_tokens']:,}",
            ]
            for entry in daily
        ]

        print(
            tabulate(
                daily_data,
                headers=["Date", "Total Cost", "API Calls", "Total Tokens"],
                tablefmt="grid",
            )
        )

        # Calculate totals
        total_cost = sum(entry["total_cost"] for entry in daily)
        total_calls = sum(entry["num_calls"] for entry in daily)
        total_tokens = sum(entry["total_tokens"] for entry in daily)
        avg_daily_cost = total_cost / len(daily) if daily else 0.0

        print(f"\nSummary:")
        print(f"  Total Cost: {format_currency(total_cost)}")
        print(f"  Total Calls: {total_calls:,}")
        print(f"  Total Tokens: {total_tokens:,}")
        print(f"  Average Daily Cost: {format_currency(avg_daily_cost)}")

    else:
        print("No daily cost data available")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Budget Monitoring CLI Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m mcp_server.budget.cli dashboard          # Budget overview
  python -m mcp_server.budget.cli breakdown          # Detailed breakdown
  python -m mcp_server.budget.cli breakdown --days 7 # Last 7 days
  python -m mcp_server.budget.cli optimize           # Cost optimization recommendations
  python -m mcp_server.budget.cli alerts             # Check alerts (no send)
  python -m mcp_server.budget.cli alerts --send      # Check and send alerts
  python -m mcp_server.budget.cli daily              # Daily costs (default 30 days)
  python -m mcp_server.budget.cli daily --days 7     # Last 7 days
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Dashboard command
    parser_dashboard = subparsers.add_parser(
        "dashboard",
        help="Display budget dashboard overview",
    )
    parser_dashboard.set_defaults(func=cmd_dashboard)

    # Breakdown command
    parser_breakdown = subparsers.add_parser(
        "breakdown",
        help="Display detailed cost breakdown",
    )
    parser_breakdown.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days for daily breakdown (default: 7)",
    )
    parser_breakdown.set_defaults(func=cmd_breakdown)

    # Optimize command
    parser_optimize = subparsers.add_parser(
        "optimize",
        help="Display cost optimization recommendations",
    )
    parser_optimize.set_defaults(func=cmd_optimize)

    # Alerts command
    parser_alerts = subparsers.add_parser(
        "alerts",
        help="Check budget alerts and send notifications",
    )
    parser_alerts.add_argument(
        "--send",
        action="store_true",
        help="Send alert notifications if thresholds exceeded",
    )
    parser_alerts.set_defaults(func=cmd_alerts)

    # Daily command
    parser_daily = subparsers.add_parser(
        "daily",
        help="Display daily cost summary",
    )
    parser_daily.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to display (default: 30)",
    )
    parser_daily.set_defaults(func=cmd_daily)

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if hasattr(args, "func"):
        try:
            args.func(args)
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
