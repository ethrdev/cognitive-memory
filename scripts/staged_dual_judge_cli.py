#!/usr/bin/env python3
"""
Staged Dual Judge CLI Tool (Story 3.9)

Command-line interface for managing Staged Dual Judge transition between
Full Dual Judge Mode and Single Judge + Spot Checks Mode.

Commands:
- --evaluate: Check current Kappa and transition eligibility
- --transition: Execute transition to Single Judge Mode (with confirmation)
- --status: Display current mode and spot check Kappa
- --validate-spot-checks: Monthly validation (used by cron job)

Usage:
    python staged_dual_judge_cli.py --evaluate
    python staged_dual_judge_cli.py --transition
    python staged_dual_judge_cli.py --status
    python staged_dual_judge_cli.py --validate-spot-checks

Output Formats:
- Default: Human-readable table format
- --format json: JSON output for automation

Examples:
    # Check transition eligibility
    python staged_dual_judge_cli.py --evaluate

    # Execute transition (with confirmation)
    python staged_dual_judge_cli.py --transition

    # View current status
    python staged_dual_judge_cli.py --status --format json

    # Monthly validation (cron job)
    python staged_dual_judge_cli.py --validate-spot-checks
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from mcp_server.config import load_environment
from mcp_server.utils.staged_dual_judge import (
    calculate_macro_kappa,
    continue_dual_judge,
    evaluate_transition,
    execute_transition,
    validate_spot_check_kappa,
)

try:
    from tabulate import tabulate
    TABULATE_AVAILABLE = True
except ImportError:
    TABULATE_AVAILABLE = False


def print_table(data, headers=None, format_type="table"):
    """Print data in table or JSON format."""
    if format_type == "json":
        print(json.dumps(data, indent=2))
    elif TABULATE_AVAILABLE and format_type == "table":
        if isinstance(data, dict):
            # Convert dict to list of lists
            table_data = [[k, v] for k, v in data.items()]
            print(tabulate(table_data, headers=headers or ["Key", "Value"], tablefmt="grid"))
        else:
            print(tabulate(data, headers=headers, tablefmt="grid"))
    else:
        # Fallback: simple text output
        if isinstance(data, dict):
            for k, v in data.items():
                print(f"{k}: {v}")
        else:
            print(data)


def cmd_evaluate(args):
    """
    Evaluate current Kappa and transition eligibility.

    Displays:
    - Current Kappa score
    - Number of queries evaluated
    - Transition recommendation (Ready/Not Ready)
    - Cost projection
    """
    try:
        # Calculate current Kappa
        kappa_result = calculate_macro_kappa()

        # Evaluate transition eligibility
        transition_result = evaluate_transition()

        # Load config for cost projections
        config = load_environment()
        staged_config = config.get('staged_dual_judge', {})
        dual_cost = staged_config.get('cost_dual_judge_eur_per_month', 7.5)
        single_cost = staged_config.get('cost_single_judge_eur_per_month', 2.5)
        savings_pct = staged_config.get('cost_savings_percentage', 40)

        # Prepare output data
        output = {
            "Current Kappa": f"{kappa_result['kappa']:.3f}",
            "Queries Evaluated": kappa_result['num_queries'],
            "Agreement Level": kappa_result['message'].split('(')[1].split(' agreement')[0] if '(' in kappa_result['message'] else "N/A",
            "Transition Status": "✅ READY" if transition_result['ready'] else "❌ NOT READY",
            "Kappa Threshold": f"≥ 0.85",
            "Current Cost": f"€{dual_cost:.2f}/mo (Full Dual Judge)",
            "Projected Cost": f"€{single_cost:.2f}/mo (Single Judge + Spot Checks)",
            "Savings": f"-{savings_pct}% (-€{dual_cost - single_cost:.2f}/mo)",
            "Recommendation": transition_result['recommendation']
        }

        print("\n🔍 Staged Dual Judge Evaluation\n")
        print_table(output, format_type=args.format)

        if transition_result['ready']:
            print("\n✅ System is ready for transition!")
            print("   Run: python staged_dual_judge_cli.py --transition")
        else:
            print(f"\n⚠️ Not ready for transition")
            print(f"   Reason: {transition_result['rationale']}")

        sys.exit(0)

    except Exception as e:
        print(f"❌ Error during evaluation: {e}", file=sys.stderr)
        sys.exit(2)


def cmd_transition(args):
    """
    Execute transition to Single Judge Mode (with confirmation).

    Steps:
    1. Evaluate transition eligibility
    2. Confirm with user (unless --yes flag)
    3. Execute transition (update config.yaml)
    4. Display success message
    """
    try:
        # Evaluate transition eligibility
        transition_result = evaluate_transition()

        if not transition_result['ready']:
            print(f"❌ Transition not recommended")
            print(f"   Kappa: {transition_result['kappa']:.3f} < 0.85")
            print(f"   Reason: {transition_result['rationale']}")
            sys.exit(1)

        # Confirm with user (unless --yes flag)
        if not args.yes:
            print(f"\n⚠️ Confirm Transition to Single Judge Mode")
            print(f"   Current Kappa: {transition_result['kappa']:.3f} ≥ 0.85")
            print(f"   This will update config.yaml:")
            print(f"     - dual_judge_enabled: true → false")
            print(f"     - primary_judge: gpt-4o")
            print(f"     - spot_check_rate: 0.05 (5%)")
            print(f"\n   Cost reduction: €5-10/mo → €2-3/mo (-40%)")

            response = input("\n   Proceed with transition? (y/n): ").strip().lower()
            if response not in ['y', 'yes']:
                print("   Transition cancelled.")
                sys.exit(0)

        # Execute transition
        execute_transition()

        # Load config for display
        config = load_environment()
        staged_config = config.get('staged_dual_judge', {})

        # Success output
        output = {
            "Status": "✅ Transitioned to Single Judge Mode",
            "Kappa": f"{transition_result['kappa']:.3f} ≥ 0.85",
            "Config Updated": "dual_judge_enabled: false",
            "Primary Judge": staged_config.get('primary_judge', 'gpt-4o'),
            "Spot Check Rate": f"{staged_config.get('spot_check_rate', 0.05):.0%}",
            "Cost": "€2-3/mo (down from €5-10/mo, -40%)"
        }

        print("\n✅ Transition Complete!\n")
        print_table(output, format_type=args.format)

        print("\n📊 Next Steps:")
        print("   1. Monitor spot check Kappa monthly")
        print("   2. Run: python staged_dual_judge_cli.py --status")
        print("   3. Check api_cost_log for cost reduction verification")

        sys.exit(0)

    except Exception as e:
        print(f"❌ Error during transition: {e}", file=sys.stderr)
        sys.exit(2)


def cmd_status(args):
    """
    Display current mode and spot check Kappa (if applicable).

    Shows:
    - Current mode (Dual Judge or Single Judge + Spot Checks)
    - Primary judge
    - Spot check rate (if Single Judge Mode)
    - Spot check Kappa (last 30 days, if available)
    - Status (HEALTHY or REVERTING)
    """
    try:
        # Load config
        config = load_environment()
        staged_config = config.get('staged_dual_judge', {})
        dual_judge_enabled = staged_config.get('dual_judge_enabled', True)

        if dual_judge_enabled:
            # Full Dual Judge Mode
            output = {
                "Current Mode": "Full Dual Judge",
                "Judge 1": "GPT-4o",
                "Judge 2": "Claude 3.5 Haiku",
                "All Queries": "Both judges evaluate all queries",
                "Cost": "€5-10/mo",
                "Status": "Active"
            }

            print("\n📊 Staged Dual Judge Status\n")
            print_table(output, format_type=args.format)

            print("\n💡 Tip: Run --evaluate to check transition eligibility")

        else:
            # Single Judge + Spot Checks Mode
            from mcp_server.db.connection import get_connection
            from sklearn.metrics import cohen_kappa_score

            # Query spot check Kappa (last 30 days)
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT judge1_score, judge2_score
                    FROM ground_truth
                    WHERE metadata->>'spot_check' = 'true'
                      AND created_at >= NOW() - INTERVAL '30 days'
                      AND judge1_score IS NOT NULL
                      AND judge2_score IS NOT NULL
                """)
                rows = cursor.fetchall()

                if rows and len(rows) >= 5:
                    # Calculate spot check Kappa
                    judge1_binary = [1 if score > 0.5 else 0 for score, _ in rows]
                    judge2_binary = [1 if score > 0.5 else 0 for _, score in rows]
                    spot_check_kappa = cohen_kappa_score(judge1_binary, judge2_binary)
                    spot_check_count = len(rows)

                    # Determine health status
                    threshold = staged_config.get('spot_check_kappa_threshold', 0.70)
                    if spot_check_kappa >= threshold:
                        health_status = "✅ HEALTHY"
                    else:
                        health_status = f"⚠️ LOW (< {threshold:.2f}) - May Revert"

                    output = {
                        "Current Mode": "Single Judge + Spot Checks",
                        "Primary Judge": staged_config.get('primary_judge', 'gpt-4o'),
                        "Spot Check Rate": f"{staged_config.get('spot_check_rate', 0.05):.0%}",
                        "Spot Check Kappa (30 Days)": f"{spot_check_kappa:.3f} ({spot_check_count} spot checks)",
                        "Kappa Threshold": f"≥ {threshold:.2f}",
                        "Status": health_status,
                        "Cost": "€2-3/mo (down from €5-10/mo)"
                    }
                else:
                    # Insufficient spot check data
                    output = {
                        "Current Mode": "Single Judge + Spot Checks",
                        "Primary Judge": staged_config.get('primary_judge', 'gpt-4o'),
                        "Spot Check Rate": f"{staged_config.get('spot_check_rate', 0.05):.0%}",
                        "Spot Check Kappa (30 Days)": f"N/A ({len(rows) if rows else 0} spot checks, need ≥5)",
                        "Status": "⏳ Collecting Data",
                        "Cost": "€2-3/mo (down from €5-10/mo)"
                    }

            except Exception as e:
                # Error querying spot checks
                output = {
                    "Current Mode": "Single Judge + Spot Checks",
                    "Primary Judge": staged_config.get('primary_judge', 'gpt-4o'),
                    "Spot Check Rate": f"{staged_config.get('spot_check_rate', 0.05):.0%}",
                    "Spot Check Kappa": f"Error: {e}",
                    "Status": "⚠️ Cannot Determine",
                    "Cost": "€2-3/mo (down from €5-10/mo)"
                }

            print("\n📊 Staged Dual Judge Status\n")
            print_table(output, format_type=args.format)

            print("\n💡 Tip: Monitor spot check Kappa monthly to ensure quality")

        sys.exit(0)

    except Exception as e:
        print(f"❌ Error getting status: {e}", file=sys.stderr)
        sys.exit(2)


def cmd_validate_spot_checks(args):
    """
    Validate spot check Kappa and revert if below threshold (cron job).

    Monthly validation:
    1. Query spot checks from last 30 days
    2. Calculate Kappa on spot check sample
    3. If Kappa < 0.70: Revert to Dual Judge Mode
    4. If Kappa ≥ 0.70: Continue Single Judge Mode

    Exit codes:
    - 0: Validation passed, continuing Single Judge Mode
    - 1: Validation failed, reverted to Dual Judge Mode
    - 2: Error during validation
    """
    try:
        # Validate spot check Kappa
        validate_spot_check_kappa()

        # If we get here, validation passed (no revert)
        print("✅ Spot check validation passed. Continuing Single Judge Mode.")
        sys.exit(0)

    except Exception as e:
        print(f"❌ Error during validation: {e}", file=sys.stderr)
        sys.exit(2)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Staged Dual Judge CLI - Transition management tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --evaluate                 # Check transition eligibility
  %(prog)s --transition               # Execute transition (with confirmation)
  %(prog)s --transition --yes         # Execute transition (no confirmation)
  %(prog)s --status                   # View current mode and spot check Kappa
  %(prog)s --status --format json     # JSON output
  %(prog)s --validate-spot-checks     # Monthly validation (cron job)

For more information, see: docs/staged-dual-judge.md
        """
    )

    # Command selection (mutually exclusive)
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument('--evaluate', action='store_true',
                          help='Evaluate current Kappa and transition eligibility')
    commands.add_argument('--transition', action='store_true',
                          help='Execute transition to Single Judge Mode (with confirmation)')
    commands.add_argument('--status', action='store_true',
                          help='Display current mode and spot check Kappa')
    commands.add_argument('--validate-spot-checks', action='store_true',
                          help='Validate spot check Kappa (monthly cron job)')

    # Optional arguments
    parser.add_argument('--format', choices=['table', 'json'], default='table',
                        help='Output format (default: table)')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompts (for --transition)')

    args = parser.parse_args()

    # Route to appropriate command
    if args.evaluate:
        cmd_evaluate(args)
    elif args.transition:
        cmd_transition(args)
    elif args.status:
        cmd_status(args)
    elif args.validate_spot_checks:
        cmd_validate_spot_checks(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
