"""
Configuration Management for Cognitive Memory System

: Production Configuration & Environment Setup
Handles environment-specific configuration loading with validation and error handling.

Environment Loading Order:
1. Check ENVIRONMENT variable (default: development)
2. Load .env.{ENVIRONMENT} file
3. Load and merge config.yaml (base + environment-specific)
4. Validate required variables
5. Log environment loaded

Security:
- No secrets in logs (API keys, passwords scrubbed)
- Validates required variables before startup
- Clear error messages for missing configuration
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or incomplete."""

    pass


def get_project_root() -> Path:
    """
    Get the project root directory.

    Returns:
        Path to project root (parent of mcp_server directory)
    """
    return Path(__file__).parent.parent


def load_environment() -> dict[str, Any]:
    """
    Load environment-specific configuration.

    Loading Order:
        1. Determine environment from ENVIRONMENT variable (default: development)
        2. Load .env.{environment} file from config/ directory
        3. Load config.yaml and merge base + environment-specific sections
        4. Validate required environment variables
        5. Log loaded environment

    Returns:
        dict: Merged configuration (base + environment-specific)

    Raises:
        ConfigurationError: If required environment variables are missing
        FileNotFoundError: If .env.{environment} file not found
        yaml.YAMLError: If config.yaml is invalid

    Example:
        >>> config = load_environment()
        >>> print(config['database']['name'])
        'cognitive_memory_dev'
    """
    # Step 1: Determine environment (default: development for safety)
    environment = os.getenv("ENVIRONMENT", "development")

    # Validate environment value
    valid_environments = ["development", "production"]
    if environment not in valid_environments:
        raise ConfigurationError(
            f"Invalid ENVIRONMENT value: '{environment}'. "
            f"Must be one of: {', '.join(valid_environments)}"
        )

    # Step 2: Load .env.{environment} file
    project_root = get_project_root()
    env_file = project_root / "config" / f".env.{environment}"

    if not env_file.exists():
        raise FileNotFoundError(
            f"Environment file not found: {env_file}\n"
            f"Expected location: config/.env.{environment}\n"
            f"Please create this file using config/.env.template as a guide."
        )

    # Load environment variables from file
    load_dotenv(env_file)
    logger.info(f"Loaded environment variables from: {env_file}")

    # Step 3: Load config.yaml and merge sections
    config_file = project_root / "config" / "config.yaml"

    if not config_file.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_file}\n"
            "Expected location: config/config.yaml"
        )

    with open(config_file, "r") as f:
        config_data = yaml.safe_load(f)

    # Merge base configuration with environment-specific overrides
    base_config = config_data.get("base", {})
    env_config = config_data.get(environment, {})

    # Deep merge: environment-specific overrides base
    merged_config = _deep_merge(base_config, env_config)
    merged_config["environment"] = environment  # Add environment name to config

    logger.info(f"Loaded configuration from: {config_file}")
    logger.info(f"Active environment: {environment}")

    # Step 4: Validate required environment variables
    _validate_required_variables(environment)

    # Step 5: Log environment details (without secrets)
    _log_environment_details(environment, merged_config)

    return merged_config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries. Override values take precedence.

    Args:
        base: Base dictionary
        override: Override dictionary (takes precedence)

    Returns:
        Merged dictionary
    """
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            result[key] = _deep_merge(result[key], value)
        else:
            # Override takes precedence
            result[key] = value

    return result


def _validate_required_variables(environment: str) -> None:
    """
    Validate that all required environment variables are set.

    Args:
        environment: Current environment (development or production)

    Raises:
        ConfigurationError: If required variables are missing
    """
    required_vars = [
        "DATABASE_URL",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    ]

    missing_vars = []

    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith("your-") or value.endswith("-here"):
            # Placeholder values are considered missing
            missing_vars.append(var)

    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables in .env.{environment}:\n"
            + "\n".join(f"  - {var}" for var in missing_vars)
            + "\n\nPlease update config/.env.{environment} with real values.\n"
            + "Use config/.env.template as a guide."
        )

    logger.info("✓ All required environment variables validated")


def _log_environment_details(environment: str, config: dict[str, Any]) -> None:
    """
    Log environment details (without exposing secrets).

    Args:
        environment: Current environment
        config: Merged configuration
    """
    # Get database name (safe to log)
    db_name = config.get("database", {}).get("name", "unknown")

    # Log configuration details (NO SECRETS)
    logger.info("Environment Configuration:")
    logger.info(f"  Environment: {environment}")
    logger.info(f"  Database: {db_name}")
    logger.info(
        f"  Log Level: {config.get('logging', {}).get('level', 'INFO')}"
    )
    logger.info(
        f"  Debug Mode: {config.get('features', {}).get('debug_mode', False)}"
    )

    # Confirm API keys are configured (but don't log the keys!)
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    logger.info(f"  OpenAI API Key: {'✓ configured' if has_openai else '✗ missing'}")
    logger.info(
        f"  Anthropic API Key: {'✓ configured' if has_anthropic else '✗ missing'}"
    )


def get_database_url() -> str:
    """
    Get the PostgreSQL database URL from environment.

    Returns:
        Database connection string

    Raises:
        ConfigurationError: If DATABASE_URL is not set
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ConfigurationError(
            "DATABASE_URL not set in environment. "
            "Run load_environment() first or set manually."
        )
    return db_url


def get_api_key(provider: str) -> str:
    """
    Get API key for specified provider.

    Args:
        provider: API provider (openai or anthropic)

    Returns:
        API key

    Raises:
        ConfigurationError: If API key is not set
    """
    var_name = f"{provider.upper()}_API_KEY"
    api_key = os.getenv(var_name)

    if not api_key:
        raise ConfigurationError(
            f"{var_name} not set in environment. "
            "Run load_environment() first or set manually."
        )

    return api_key


# Global configuration instance (loaded once at module level)
_config: dict[str, Any] | None = None


def get_config() -> dict[str, Any]:
    """
    Get the loaded configuration.

    Returns:
        Configuration dictionary

    Note:
        Configuration is loaded once at first access and cached.
        Call load_environment() manually if you need to reload.
    """
    global _config
    if _config is None:
        _config = load_environment()
    return _config


def get_api_cost_rate(api_name: str) -> float:
    """
    Get cost rate for specified API from configuration.

    Args:
        api_name: API rate identifier (e.g., 'openai_embeddings', 'gpt4o_input',
                  'gpt4o_output', 'haiku_input', 'haiku_output')

    Returns:
        Cost in EUR per token

    Raises:
        ConfigurationError: If cost rate is not configured

    Example:
        >>> rate = get_api_cost_rate('openai_embeddings')
        >>> rate == 0.00000002  # €0.02 per 1M tokens
        True
    """
    config = get_config()
    cost_rates = config.get("api_cost_rates", {})

    if api_name not in cost_rates:
        raise ConfigurationError(
            f"Cost rate not configured for API: {api_name}\n"
            f"Available rates: {', '.join(cost_rates.keys())}\n"
            "Update config/config.yaml with missing rate."
        )

    return float(cost_rates[api_name])


def calculate_api_cost(api_name: str, input_tokens: int, output_tokens: int = 0) -> float:
    """
    Calculate API cost for a given token usage.

    Args:
        api_name: API identifier for rate lookup ('openai_embeddings', 'gpt4o', 'haiku')
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens (default 0, used for completion APIs)

    Returns:
        Total cost in EUR

    Example:
        >>> # OpenAI embeddings (1536 tokens, no output)
        >>> cost = calculate_api_cost('openai_embeddings', 1536)
        >>> cost == 0.00003072  # 1536 × €0.00000002
        True

        >>> # GPT-4o (100 input, 200 output)
        >>> cost = calculate_api_cost('gpt4o', 100, 200)
        >>> cost == 0.00225  # (100 × €0.0000025) + (200 × €0.00001)
        True
    """
    if api_name == 'openai_embeddings':
        # Embeddings: single rate for all tokens
        rate = get_api_cost_rate('openai_embeddings')
        return input_tokens * rate

    elif api_name == 'gpt4o':
        # GPT-4o: separate input/output rates
        input_rate = get_api_cost_rate('gpt4o_input')
        output_rate = get_api_cost_rate('gpt4o_output')
        return (input_tokens * input_rate) + (output_tokens * output_rate)

    elif api_name == 'haiku':
        # Haiku: separate input/output rates
        input_rate = get_api_cost_rate('haiku_input')
        output_rate = get_api_cost_rate('haiku_output')
        return (input_tokens * input_rate) + (output_tokens * output_rate)

    else:
        raise ConfigurationError(
            f"Unknown API name for cost calculation: {api_name}\n"
            "Supported APIs: openai_embeddings, gpt4o, haiku"
        )


# =============================================================================
# Story 4.6: Hybrid Search Configuration
# =============================================================================


def get_hybrid_search_weights() -> dict[str, float]:
    """
    Get hybrid search weights from configuration.

    Story 4.6: Three-source hybrid search weights (semantic, keyword, graph).

    Returns:
        Dictionary with weights for semantic, keyword, and graph search.
        Defaults to {"semantic": 0.6, "keyword": 0.2, "graph": 0.2} if not configured.

    Example:
        >>> weights = get_hybrid_search_weights()
        >>> weights == {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}
        True
    """
    config = get_config()
    memory_config = config.get("memory", {})
    weights = memory_config.get("hybrid_search_weights", {})

    return {
        "semantic": float(weights.get("semantic", 0.6)),
        "keyword": float(weights.get("keyword", 0.2)),
        "graph": float(weights.get("graph", 0.2)),
    }


def get_query_routing_config() -> dict[str, Any]:
    """
    Get query routing configuration from config.yaml.

    Story 4.6: Query routing for relational vs. standard queries.

    Returns:
        Dictionary with relational_keywords and relational_weights.
        Defaults to hardcoded values if not configured.

    Example:
        >>> routing = get_query_routing_config()
        >>> "relational_keywords" in routing
        True
        >>> "relational_weights" in routing
        True
    """
    config = get_config()
    memory_config = config.get("memory", {})
    query_routing = memory_config.get("query_routing", {})

    # Default relational keywords if not configured
    default_keywords = {
        "de": [
            "nutzt", "verwendet", "verbunden", "abhängig", "Projekt", "Technologie",
            "gehört zu", "hat", "benutzt", "verknüpft", "zusammenhängt", "basiert auf"
        ],
        "en": [
            "uses", "connected", "dependent", "project", "technology", "belongs to",
            "has", "relates to", "linked", "associated", "based on", "depends on"
        ],
    }

    # Default relational weights if not configured
    default_relational_weights = {
        "semantic": 0.4,
        "keyword": 0.2,
        "graph": 0.4,
    }

    keywords = query_routing.get("relational_keywords", default_keywords)
    relational_weights = query_routing.get("relational_weights", default_relational_weights)

    return {
        "relational_keywords": keywords,
        "relational_weights": {
            "semantic": float(relational_weights.get("semantic", 0.4)),
            "keyword": float(relational_weights.get("keyword", 0.2)),
            "graph": float(relational_weights.get("graph", 0.4)),
        },
    }
