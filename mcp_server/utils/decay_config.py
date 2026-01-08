"""
Decay configuration module for sector-specific memory decay.

This module provides:
- SectorDecay dataclass for decay parameters
- DEFAULT_DECAY_CONFIG fallback
- get_decay_config() singleton for loading YAML config

Usage:
    from mcp_server.utils.decay_config import get_decay_config, SectorDecay
    from mcp_server.utils.sector_classifier import MemorySector

    config = get_decay_config()
    emotional_decay = config["emotional"]
    S = emotional_decay.S_base * (1 + log(1 + access_count))
"""

from dataclasses import dataclass
from pathlib import Path
import logging
from typing import Literal

import yaml

from mcp_server.utils.sector_classifier import MemorySector

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SectorDecay:
    """Decay parameters for a memory sector.

    Attributes:
        S_base: Base memory strength - higher values = slower decay
        S_floor: Minimum memory strength (null = can decay to zero)
    """

    S_base: float
    S_floor: float | None = None


# Default decay configuration - used as fallback when config file is missing/invalid
DEFAULT_DECAY_CONFIG: dict[MemorySector, SectorDecay] = {
    "emotional": SectorDecay(S_base=200.0, S_floor=150.0),
    "semantic": SectorDecay(S_base=100.0, S_floor=None),
    "episodic": SectorDecay(S_base=150.0, S_floor=100.0),
    "procedural": SectorDecay(S_base=120.0, S_floor=None),
    "reflective": SectorDecay(S_base=180.0, S_floor=120.0),
}

# Module-level cache for singleton pattern
_config_cache: dict[MemorySector, SectorDecay] | None = None


def _get_config_path() -> Path:
    """Get the path to the decay configuration file."""
    # Path: mcp_server/utils/decay_config.py -> go up 3 levels -> config/decay_config.yaml
    return Path(__file__).parent.parent.parent / "config" / "decay_config.yaml"


def _load_yaml_config() -> dict[MemorySector, SectorDecay]:
    """Load decay configuration from YAML file.

    Returns:
        Dict mapping sector names to SectorDecay dataclasses

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid (missing keys or sectors)
    """
    config_path = _get_config_path()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    if "decay_config" not in raw:
        raise ValueError("Invalid config: missing 'decay_config' key")

    # Parse each sector
    result: dict[MemorySector, SectorDecay] = {}
    for sector, values in raw["decay_config"].items():
        result[sector] = SectorDecay(
            S_base=float(values["S_base"]),
            S_floor=values.get("S_floor"),  # None if missing
        )

    # CRITICAL: Validate all required sectors present
    required_sectors = {"emotional", "episodic", "semantic", "procedural", "reflective"}
    missing = required_sectors - set(result.keys())
    if missing:
        raise ValueError(f"Config missing sectors: {missing}")

    return result


def get_decay_config() -> dict[MemorySector, SectorDecay]:
    """Get decay configuration, loading from YAML or using defaults.

    This function implements the singleton pattern - the config is loaded once
    and cached for subsequent calls.

    Returns:
        Dict mapping sector names to SectorDecay dataclasses

    Behavior:
        - First call: Loads from config/decay_config.yaml if valid, otherwise uses DEFAULT_DECAY_CONFIG
        - Subsequent calls: Returns cached config
        - If YAML is missing/invalid: Logs warning and uses DEFAULT_DECAY_CONFIG
    """
    global _config_cache

    # Return cached config if already loaded (singleton pattern)
    if _config_cache is not None:
        return _config_cache

    try:
        # Load from YAML
        _config_cache = _load_yaml_config()
    except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
        # Fallback to default config on any error
        logger.warning(
            "Falling back to default decay config",
            extra={
                "fallback_reason": type(e).__name__,
                "error": str(e),
                "config_path": str(_get_config_path()),
            },
        )
        _config_cache = DEFAULT_DECAY_CONFIG

    return _config_cache
