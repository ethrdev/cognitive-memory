"""
Reflexion Utilities Module

Provides utility functions for reflexion trigger logic and configuration.
Story 2.5: Implements should_trigger_reflection() for Story 2.6 integration.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(__name__)

# Cache for config to avoid repeated file reads
_config_cache: Dict[str, Any] | None = None


def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.yaml.

    Returns:
        Configuration dictionary with nested structure

    Raises:
        FileNotFoundError: If config.yaml not found
        yaml.YAMLError: If config.yaml is invalid
    """
    global _config_cache

    # Return cached config if available
    if _config_cache is not None:
        return _config_cache

    # Find config.yaml (project root / config / config.yaml)
    config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"

    if not config_path.exists():
        # Try alternative path
        config_path = Path(os.getcwd()) / "config" / "config.yaml"

    if not config_path.exists():
        logger.error(f"config.yaml not found at {config_path}")
        raise FileNotFoundError(f"config.yaml not found at {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        _config_cache = config
        logger.info(f"Configuration loaded from {config_path}")
        return config

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse config.yaml: {e}")
        raise


def get_reward_threshold() -> float:
    """
    Get reward threshold for reflexion trigger from config.

    Returns reward threshold from config.yaml:
    - base.memory.evaluation.reward_threshold (default: 0.3)

    Returns:
        Reward threshold value (float, default 0.3)

    Example:
        >>> threshold = get_reward_threshold()
        >>> print(f"Threshold: {threshold}")
        Threshold: 0.3
    """
    try:
        config = load_config()

        # Navigate nested structure: base -> memory -> evaluation -> reward_threshold
        threshold = config.get("base", {}).get("memory", {}).get("evaluation", {}).get(
            "reward_threshold", 0.3
        )

        # Validate threshold is a valid float
        threshold = float(threshold)

        logger.debug(f"Reward threshold loaded: {threshold}")
        return threshold

    except Exception as e:
        logger.warning(
            f"Failed to load reward_threshold from config, using default 0.3: {e}"
        )
        return 0.3  # Fallback default


def should_trigger_reflection(
    reward_score: float, threshold: float | None = None
) -> bool:
    """
    Determine if reflexion should be triggered based on reward score.

    Reflexion is triggered when reward_score < threshold.

    Integration Point for Story 2.6:
    - When this function returns True, Story 2.6 will call generate_reflection()
    - When False, only evaluation logging occurs (no reflexion)

    Args:
        reward_score: Reward score from evaluation (-1.0 to +1.0)
        threshold: Optional threshold override (default: load from config.yaml)

    Returns:
        True if reflexion should be triggered, False otherwise

    Example:
        >>> should_trigger_reflection(0.85)  # High quality answer
        False
        >>> should_trigger_reflection(0.25)  # Low quality answer
        True
        >>> should_trigger_reflection(0.30)  # Exactly at threshold
        False
        >>> should_trigger_reflection(0.29)  # Just below threshold
        True
    """
    # Load threshold from config if not provided
    if threshold is None:
        threshold = get_reward_threshold()

    # Trigger reflexion if reward score is below threshold
    should_trigger = reward_score < threshold

    logger.debug(
        f"Reflexion trigger check: reward={reward_score:.3f}, "
        f"threshold={threshold:.3f}, trigger={should_trigger}"
    )

    return should_trigger


def get_reflexion_stats(reward_scores: list[float]) -> Dict[str, Any]:
    """
    Calculate reflexion trigger statistics for a list of reward scores.

    Useful for analytics and monitoring reflexion trigger rates.

    Args:
        reward_scores: List of reward scores to analyze

    Returns:
        Dictionary with:
        - total: Total number of evaluations
        - triggered: Number of reflexion triggers
        - trigger_rate: Percentage of evaluations that triggered reflexion
        - avg_reward: Average reward score
        - threshold: Current threshold value

    Example:
        >>> scores = [0.85, 0.25, 0.50, 0.15, 0.90]
        >>> stats = get_reflexion_stats(scores)
        >>> print(f"Trigger rate: {stats['trigger_rate']:.1f}%")
        Trigger rate: 40.0%
    """
    if not reward_scores:
        return {
            "total": 0,
            "triggered": 0,
            "trigger_rate": 0.0,
            "avg_reward": 0.0,
            "threshold": get_reward_threshold(),
        }

    threshold = get_reward_threshold()
    total = len(reward_scores)
    triggered = sum(1 for score in reward_scores if score < threshold)
    trigger_rate = (triggered / total * 100.0) if total > 0 else 0.0
    avg_reward = sum(reward_scores) / total if total > 0 else 0.0

    return {
        "total": total,
        "triggered": triggered,
        "trigger_rate": round(trigger_rate, 1),
        "avg_reward": round(avg_reward, 3),
        "threshold": threshold,
    }
