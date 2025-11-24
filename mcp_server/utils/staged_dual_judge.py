"""
Staged Dual Judge Transition Logic for Budget Optimization.

: Staged Dual Judge Implementation (Enhancement E8)

Implements data-driven transition from Full Dual Judge (GPT-4o + Haiku) to
Single Judge + 5% Spot Checks based on IRR stability (Kappa ≥0.85).

Cost Optimization:
- Phase 1 (Dual Judge): €5-10/mo (both judges on all queries)
- Phase 2 (Single Judge + Spot Checks): €2-3/mo (GPT-4o all + Haiku 5%)
- Savings: -40% budget reduction

Key Features:
- IRR-Stabilität Check: Calculates Kappa over last 100 Ground Truth queries
- Transition Decision: Activates Single Judge Mode when Kappa ≥0.85
- Spot Check Mechanism: 5% random sampling with both judges after transition
- Automatic Revert: Falls back to Dual Judge if spot check Kappa <0.70
- Config Management: Updates config.yaml while preserving structure (ruamel.yaml)

Functions:
- calculate_macro_kappa(): Evaluates IRR over Ground Truth queries
- evaluate_transition(): Decision engine for transition eligibility
- execute_transition(): Activates Single Judge Mode
- continue_dual_judge(): Logs decision to remain in Dual Judge Mode
- validate_spot_check_kappa(): Monthly spot check validation
- revert_to_dual_judge(): Restores Full Dual Judge Mode

References:
- Enhancement E8: Budget optimization via staged approach
- NFR003: Budget target €5-10/mo → €2-3/mo
- : Dual Judge Implementation (prerequisite)
- : IRR Validation (prerequisite)
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

from ruamel.yaml import YAML
from sklearn.metrics import cohen_kappa_score

from mcp_server.config import get_project_root
from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


def _manual_cohen_kappa(judge1_binary: List[int], judge2_binary: List[int]) -> float:
    """
    Manually calculate Cohen's Kappa for edge cases where sklearn fails.

    Args:
        judge1_binary: Binary scores from judge 1
        judge2_binary: Binary scores from judge 2

    Returns:
        Cohen's Kappa score

    Note:
        This is a fallback for edge cases where sklearn returns NaN or raises ValueError.
        Based on the same logic as dual_judge.py:_manual_cohen_kappa.
    """
    n = len(judge1_binary)
    if n == 0:
        return 0.0

    # Calculate observed agreement (P_o)
    agreement = sum(1 for j1, j2 in zip(judge1_binary, judge2_binary, strict=False) if j1 == j2)
    P_o = agreement / n

    # Calculate expected agreement (P_e)
    # Count number of 1s and 0s for each judge
    judge1_ones = sum(judge1_binary)
    judge1_zeros = n - judge1_ones
    judge2_ones = sum(judge2_binary)
    judge2_zeros = n - judge2_ones

    # Probability both say 1 by chance
    p_both_1 = (judge1_ones / n) * (judge2_ones / n)
    # Probability both say 0 by chance
    p_both_0 = (judge1_zeros / n) * (judge2_zeros / n)

    P_e = p_both_1 + p_both_0

    # Calculate Kappa
    if P_e == 1.0:
        # Perfect chance agreement, undefined Kappa, return 0
        return 0.0

    kappa = (P_o - P_e) / (1 - P_e)
    return kappa


def calculate_macro_kappa(num_queries: int = 100) -> Dict[str, Union[float, int, bool]]:
    """
    Calculate Macro-Average Cohen's Kappa over last N Ground Truth queries.

    IRR Measurement Strategy:
    - Load last N queries from ground_truth table ()
    - Binary conversion: Score >0.5 = Relevant (1), ≤0.5 = Not Relevant (0)
    - Calculate Cohen's Kappa using sklearn.metrics.cohen_kappa_score()
    - Transition eligibility: Kappa ≥0.85 ("Almost Perfect Agreement")

    Args:
        num_queries: Number of recent queries to evaluate (default: 100)
                     Minimum 10 queries required for meaningful Kappa

    Returns:
        dict with keys:
            - kappa (float): Macro-Average Kappa score (-1.0 to 1.0)
            - num_queries (int): Actual number of queries evaluated
            - transition_eligible (bool): True if Kappa ≥0.85
            - message (str): Human-readable result description

    Raises:
        ValueError: If <10 queries available (insufficient data)
        DatabaseError: If database query fails

    Kappa Interpretation (Landis & Koch, 1977):
        - <0.00: Poor agreement
        - 0.00-0.20: Slight agreement
        - 0.21-0.40: Fair agreement
        - 0.41-0.60: Moderate agreement
        - 0.61-0.80: Substantial agreement
        - 0.81-1.00: Almost perfect agreement

    Example:
        >>> result = calculate_macro_kappa(num_queries=100)
        >>> print(f"Kappa: {result['kappa']:.3f}, Eligible: {result['transition_eligible']}")
        Kappa: 0.872, Eligible: True
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Query: Load last N Ground Truth entries with both judge scores
        # Filters: judge1_score IS NOT NULL AND judge2_score IS NOT NULL
        # Order: Most recent first (ORDER BY created_at DESC)
        query = """
            SELECT judge1_score, judge2_score
            FROM ground_truth
            WHERE judge1_score IS NOT NULL
              AND judge2_score IS NOT NULL
            ORDER BY created_at DESC
            LIMIT %s
        """
        cursor.execute(query, (num_queries,))
        rows = cursor.fetchall()

        if not rows:
            raise ValueError(
                "No Ground Truth data available. "
                "Cannot calculate Kappa without judge scores. "
                "Run Ground Truth collection () first."
            )

        actual_count = len(rows)

        # Minimum sample size check (10 queries minimum for statistical validity)
        if actual_count < 10:
            raise ValueError(
                f"Insufficient Ground Truth data: {actual_count} queries found, "
                f"minimum 10 required for meaningful Kappa calculation. "
                f"Continue collecting Ground Truth data."
            )

        # Binary conversion: Score >0.5 = Relevant (1), ≤0.5 = Not Relevant (0)
        judge1_binary = [1 if score > 0.5 else 0 for score, _ in rows]
        judge2_binary = [1 if score > 0.5 else 0 for _, score in rows]

        # Calculate Cohen's Kappa using sklearn
        try:
            kappa = cohen_kappa_score(judge1_binary, judge2_binary)

            # Handle NaN results (occurs when all predictions are identical)
            if kappa != kappa:  # NaN check (NaN != NaN is True)
                if judge1_binary == judge2_binary:
                    # Perfect agreement edge case
                    kappa = 1.0
                else:
                    # Calculate manually for other edge cases
                    kappa = _manual_cohen_kappa(judge1_binary, judge2_binary)
        except ValueError:
            # sklearn can raise ValueError for certain edge cases
            if judge1_binary == judge2_binary:
                # Perfect agreement
                kappa = 1.0
            else:
                # Calculate manually
                kappa = _manual_cohen_kappa(judge1_binary, judge2_binary)

        # Transition eligibility: Kappa ≥0.85 threshold
        transition_eligible = kappa >= 0.85

        # Interpret Kappa value (Landis & Koch classification)
        if kappa < 0.0:
            agreement_level = "Poor"
        elif kappa < 0.21:
            agreement_level = "Slight"
        elif kappa < 0.41:
            agreement_level = "Fair"
        elif kappa < 0.61:
            agreement_level = "Moderate"
        elif kappa < 0.81:
            agreement_level = "Substantial"
        else:
            agreement_level = "Almost Perfect"

        message = (
            f"Kappa: {kappa:.3f} ({agreement_level} agreement) "
            f"over {actual_count} queries. "
            f"{'✅ Eligible for Single Judge Mode' if transition_eligible else '❌ Not ready for transition'}"
        )

        # Log result
        logger.info(
            f"Kappa evaluation completed: kappa={kappa:.3f}, "
            f"num_queries={actual_count}, "
            f"transition_eligible={transition_eligible}, "
            f"agreement_level={agreement_level}"
        )

        return {
            "kappa": round(kappa, 3),
            "num_queries": actual_count,
            "transition_eligible": transition_eligible,
            "message": message
        }

    except Exception as e:
        logger.error(f"Failed to calculate Kappa: {e}")
        raise


def evaluate_transition(kappa_threshold: float = 0.85) -> Dict[str, Union[str, float, bool]]:
    """
    Evaluate whether system is ready to transition from Dual to Single Judge Mode.

    Decision Logic:
    - Call calculate_macro_kappa() to get IRR score
    - If Kappa ≥threshold: Recommend transition (ready=True)
    - If Kappa <threshold: Recommend continue Dual Judge (ready=False)

    Args:
        kappa_threshold: Minimum Kappa for transition (default: 0.85)
                         Valid range: 0.0-1.0

    Returns:
        dict with keys:
            - decision (str): "transition" | "continue_dual"
            - kappa (float): Current Kappa score
            - ready (bool): True if eligible for transition
            - rationale (str): Explanation of decision
            - recommendation (str): Action to take

    Raises:
        ValueError: If kappa_threshold out of valid range [0.0, 1.0]
        DatabaseError: If database query fails

    Example:
        >>> result = evaluate_transition(kappa_threshold=0.85)
        >>> if result['ready']:
        ...     print(f"Ready to transition! Kappa: {result['kappa']}")
        ... else:
        ...     print(f"Not ready: {result['rationale']}")
    """
    # Validate threshold
    if not 0.0 <= kappa_threshold <= 1.0:
        raise ValueError(
            f"Invalid kappa_threshold: {kappa_threshold}. "
            f"Must be between 0.0 and 1.0."
        )

    # Calculate current Kappa
    kappa_result = calculate_macro_kappa()
    kappa = kappa_result['kappa']
    num_queries = kappa_result['num_queries']

    # Decision logic
    if kappa >= kappa_threshold:
        decision = "transition"
        ready = True
        rationale = (
            f"Kappa ({kappa:.3f}) ≥ threshold ({kappa_threshold:.2f}). "
            f"Judges show 'Almost Perfect Agreement' over {num_queries} queries. "
            f"Safe to transition to Single Judge + Spot Checks."
        )
        recommendation = "Run 'mcp-server staged-dual-judge --transition' to proceed."
    else:
        decision = "continue_dual"
        ready = False
        gap = kappa_threshold - kappa
        rationale = (
            f"Kappa ({kappa:.3f}) < threshold ({kappa_threshold:.2f}). "
            f"Gap: {gap:.3f}. "
            f"Judges disagree too often for Single Judge Mode. "
            f"Continue collecting Ground Truth data or improve judge prompts."
        )
        recommendation = "Continue Dual Judge Mode for another month, then re-evaluate."

    logger.info(
        f"Transition evaluation: decision={decision}, kappa={kappa:.3f}, "
        f"threshold={kappa_threshold:.2f}, ready={ready}"
    )

    return {
        "decision": decision,
        "kappa": kappa,
        "ready": ready,
        "rationale": rationale,
        "recommendation": recommendation
    }


def execute_transition() -> None:
    """
    Execute transition from Dual Judge to Single Judge Mode.

    Configuration Updates (config/config.yaml):
    - dual_judge_enabled: true → false
    - primary_judge: "gpt-4o" (added if not present)
    - spot_check_rate: 0.05 (5% random sampling)

    Uses ruamel.yaml to preserve YAML structure:
    - Comments preserved
    - Formatting preserved
    - Indentation preserved

    Side Effects:
    - Updates config/config.yaml file
    - Logs transition event (INFO level)
    - Optional: Could insert transition_log entry (not implemented yet)

    Raises:
        FileNotFoundError: If config/config.yaml not found
        PermissionError: If config file not writable
        yaml.YAMLError: If config file has invalid YAML syntax

    Example:
        >>> execute_transition()
        # config.yaml updated:
        # staged_dual_judge:
        #   dual_judge_enabled: false  # Was: true
        #   primary_judge: "gpt-4o"
        #   spot_check_rate: 0.05
    """
    backup_path = None
    try:
        # Load current Kappa for logging
        kappa_result = calculate_macro_kappa()
        kappa = kappa_result['kappa']

        # Load config.yaml using ruamel.yaml (preserves structure)
        project_root = get_project_root()
        config_path = project_root / "config" / "config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Expected location: config/config.yaml"
            )

        # Validate file permissions before attempting write
        if not os.access(config_path, os.W_OK):
            raise PermissionError(
                f"Config file not writable: {config_path}\n"
                f"Check file permissions: chmod 644 config/config.yaml"
            )

        # Backup config file before modification (transaction safety)
        backup_fd, backup_path = tempfile.mkstemp(suffix='.yaml', prefix='config_backup_')
        os.close(backup_fd)  # Close file descriptor, we'll use path
        shutil.copy2(config_path, backup_path)
        logger.debug(f"Config backup created: {backup_path}")

        # Use ruamel.yaml to preserve structure
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.default_flow_style = False

        with open(config_path, 'r') as f:
            config = yaml.load(f)

        # Update staged_dual_judge section
        if 'staged_dual_judge' not in config:
            # Create section if it doesn't exist
            config['staged_dual_judge'] = {}

        config['staged_dual_judge']['dual_judge_enabled'] = False
        config['staged_dual_judge']['primary_judge'] = 'gpt-4o'
        config['staged_dual_judge']['spot_check_rate'] = 0.05

        # Save config with preserved structure
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        # Log transition event (if this fails, config is already updated)
        logger.info(
            f"✅ Transitioned to Single Judge Mode. "
            f"Kappa: {kappa:.3f} ≥ 0.85. "
            f"Config updated: dual_judge_enabled=false, "
            f"primary_judge=gpt-4o, spot_check_rate=0.05. "
            f"Cost projection: €2-3/mo (down from €5-10/mo, -40% savings)"
        )

        # Optional: Insert transition_log entry
        # Could track: timestamp, kappa, decision='transition', cost_before, cost_after
        # Not implemented yet (marked as optional in AC 3.9.2)

        # Transaction successful - clean up backup
        if backup_path and os.path.exists(backup_path):
            os.remove(backup_path)
            logger.debug("Config backup removed (transaction complete)")

    except Exception as e:
        # Transaction failed - restore from backup
        if backup_path and os.path.exists(backup_path):
            logger.error(f"Transition failed, restoring config from backup: {e}")
            try:
                shutil.copy2(backup_path, config_path)
                logger.info(f"Config restored from backup: {backup_path}")
                os.remove(backup_path)
            except Exception as restore_error:
                logger.critical(
                    f"Failed to restore config from backup! "
                    f"Manual restore required from: {backup_path}. "
                    f"Error: {restore_error}"
                )
        logger.error(f"Failed to execute transition: {e}")
        raise


def continue_dual_judge(kappa: float) -> None:
    """
    Log decision to continue Dual Judge Mode (Kappa below threshold).

    No configuration changes are made - dual_judge_enabled stays true.

    Side Effects:
    - Logs warning message (WARN level)
    - No config.yaml changes
    - Optional: Could schedule re-evaluation reminder (not implemented)

    Args:
        kappa: Current Kappa score (for logging context)

    Example:
        >>> continue_dual_judge(kappa=0.78)
        # Logs: WARNING: IRR below threshold (Kappa: 0.780 < 0.85)
    """
    logger.warning(
        f"⚠️ IRR below threshold for Single Judge transition. "
        f"Kappa: {kappa:.3f} < 0.85. "
        f"Judges disagree too often - Single Judge Mode would reduce quality. "
        f"Continue Dual Judge for another month, then re-evaluate. "
        f"Consider: (1) Collect more Ground Truth data, or (2) Improve judge prompts."
    )

    # Optional: Schedule re-evaluation reminder
    # Could add cron job entry or calendar event
    # Not implemented yet (marked as optional in AC 3.9.3)


def validate_spot_check_kappa() -> None:
    """
    Validate Spot Check Kappa and revert if below threshold.

    Monthly validation workflow:
    1. Query all spot check entries from last 30 days
    2. Calculate Kappa on spot check sample
    3. If Kappa <0.70: Call revert_to_dual_judge()
    4. If Kappa ≥0.70: Log healthy status

    Threshold Rationale:
    - Kappa <0.70 = "Fair Agreement" boundary (Landis & Koch)
    - Lower than initial transition threshold (0.85) to provide buffer
    - Prevents frequent flip-flopping between modes

    Side Effects:
    - May call revert_to_dual_judge() if Kappa <0.70
    - Logs validation result (INFO or WARN level)

    Raises:
        ValueError: If <5 spot checks found (insufficient sample)
        DatabaseError: If database query fails

    Example:
        >>> validate_spot_check_kappa()
        # Spot Check Kappa: 0.82 (15 checks) - HEALTHY
        # OR:
        # Spot Check Kappa: 0.65 (12 checks) - REVERTING to Dual Judge
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Query: Load all spot check entries from last 30 days
        query = """
            SELECT judge1_score, judge2_score
            FROM ground_truth
            WHERE metadata->>'spot_check' = 'true'
              AND created_at >= NOW() - INTERVAL '30 days'
              AND judge1_score IS NOT NULL
              AND judge2_score IS NOT NULL
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        if not rows:
            logger.warning(
                "⚠️ No spot check data found in last 30 days. "
                "Cannot validate spot check Kappa. "
                "Spot checks may not be running or insufficient time has passed."
            )
            return

        num_spot_checks = len(rows)

        # Minimum sample size for Kappa (5 spot checks minimum)
        if num_spot_checks < 5:
            logger.warning(
                f"⚠️ Insufficient spot checks for Kappa validation: "
                f"{num_spot_checks} found, minimum 5 required. "
                f"Continue collecting spot check data."
            )
            return

        # Binary conversion for spot checks
        judge1_binary = [1 if score > 0.5 else 0 for score, _ in rows]
        judge2_binary = [1 if score > 0.5 else 0 for _, score in rows]

        # Calculate Kappa on spot check sample
        spot_check_kappa = cohen_kappa_score(judge1_binary, judge2_binary)

        # Threshold: Kappa <0.70 triggers revert
        if spot_check_kappa < 0.70:
            logger.warning(
                f"⚠️ Spot Check Kappa below threshold: {spot_check_kappa:.3f} < 0.70 "
                f"({num_spot_checks} spot checks). "
                f"Judges are diverging - reverting to Full Dual Judge Mode."
            )
            revert_to_dual_judge(spot_check_kappa)
        else:
            logger.info(
                f"✅ Spot Check Kappa healthy: {spot_check_kappa:.3f} ≥ 0.70 "
                f"({num_spot_checks} spot checks). "
                f"Continuing Single Judge Mode."
            )

    except Exception as e:
        logger.error(f"Failed to validate spot check Kappa: {e}")
        raise


def revert_to_dual_judge(spot_check_kappa: float) -> None:
    """
    Revert from Single Judge Mode back to Full Dual Judge Mode.

    Configuration Updates (config/config.yaml):
    - dual_judge_enabled: false → true
    - primary_judge: (removed or commented out)
    - spot_check_rate: (removed or commented out)

    Uses ruamel.yaml to preserve YAML structure.

    Trigger Condition:
    - Spot Check Kappa <0.70 (from validate_spot_check_kappa)
    - Indicates judges are diverging too much

    Side Effects:
    - Updates config/config.yaml file
    - Logs revert event (WARN level)
    - Optional: Email/Slack alert (not implemented)
    - Optional: Insert revert event in transition_log (not implemented)

    Args:
        spot_check_kappa: Spot check Kappa that triggered revert (for logging)

    Raises:
        FileNotFoundError: If config/config.yaml not found
        PermissionError: If config file not writable
        yaml.YAMLError: If config file has invalid YAML syntax

    Example:
        >>> revert_to_dual_judge(spot_check_kappa=0.65)
        # config.yaml updated:
        # staged_dual_judge:
        #   dual_judge_enabled: true  # Was: false
        #   # primary_judge: "gpt-4o"  # Commented out
        #   # spot_check_rate: 0.05     # Commented out
    """
    backup_path = None
    try:
        # Load config.yaml using ruamel.yaml
        project_root = get_project_root()
        config_path = project_root / "config" / "config.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Expected location: config/config.yaml"
            )

        # Validate file permissions before attempting write
        if not os.access(config_path, os.W_OK):
            raise PermissionError(
                f"Config file not writable: {config_path}\n"
                f"Check file permissions: chmod 644 config/config.yaml"
            )

        # Backup config file before modification (transaction safety)
        backup_fd, backup_path = tempfile.mkstemp(suffix='.yaml', prefix='config_backup_')
        os.close(backup_fd)  # Close file descriptor, we'll use path
        shutil.copy2(config_path, backup_path)
        logger.debug(f"Config backup created: {backup_path}")

        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.default_flow_style = False

        with open(config_path, 'r') as f:
            config = yaml.load(f)

        # Revert staged_dual_judge section
        if 'staged_dual_judge' in config:
            config['staged_dual_judge']['dual_judge_enabled'] = True
            # Remove Single Judge-specific settings
            # Note: Could also comment them out, but deleting is simpler
            if 'primary_judge' in config['staged_dual_judge']:
                del config['staged_dual_judge']['primary_judge']
            if 'spot_check_rate' in config['staged_dual_judge']:
                del config['staged_dual_judge']['spot_check_rate']

        # Save config with preserved structure
        with open(config_path, 'w') as f:
            yaml.dump(config, f)

        # Log revert event
        logger.warning(
            f"⚠️ Reverted to Full Dual Judge Mode. "
            f"Spot Check Kappa: {spot_check_kappa:.3f} < 0.70. "
            f"Config updated: dual_judge_enabled=true. "
            f"Cost will increase back to €5-10/mo. "
            f"Investigate: Why are judges diverging? "
            f"Action: Review Ground Truth quality or judge prompts."
        )

        # Optional: Send alert (Email/Slack)
        # Not implemented yet (marked as optional in AC 3.9.4)
        # Could use: send_alert("Staged Dual Judge reverted", spot_check_kappa)

        # Optional: Insert transition_log entry
        # Could track: timestamp, kappa=spot_check_kappa, decision='revert'
        # Not implemented yet

        # Transaction successful - clean up backup
        if backup_path and os.path.exists(backup_path):
            os.remove(backup_path)
            logger.debug("Config backup removed (transaction complete)")

    except Exception as e:
        # Transaction failed - restore from backup
        if backup_path and os.path.exists(backup_path):
            logger.error(f"Revert failed, restoring config from backup: {e}")
            try:
                shutil.copy2(backup_path, config_path)
                logger.info(f"Config restored from backup: {backup_path}")
                os.remove(backup_path)
            except Exception as restore_error:
                logger.critical(
                    f"Failed to restore config from backup! "
                    f"Manual restore required from: {backup_path}. "
                    f"Error: {restore_error}"
                )
        logger.error(f"Failed to revert to Dual Judge Mode: {e}")
        raise
