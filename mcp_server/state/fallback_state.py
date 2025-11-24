"""
Global Fallback State Management

Manages in-memory fallback state for external API services (Haiku Evaluation, Haiku Reflexion).
Provides thread-safe state management for degraded mode activation and recovery.

: Claude Code Fallback für Haiku API Ausfall (Degraded Mode)
"""

import asyncio
import logging
from typing import Dict

logger = logging.getLogger(__name__)

# =============================================================================
# Global State (Module-Level)
# =============================================================================

# In-memory fallback state for each service
# Keys: 'haiku_evaluation' | 'haiku_reflexion'
# Values: True (fallback active) | False (normal operation)
_fallback_state: Dict[str, bool] = {
    "haiku_evaluation": False,
    "haiku_reflexion": False,
}

# Thread-safe lock for concurrent access protection
_state_lock = asyncio.Lock()

# =============================================================================
# Public Interface
# =============================================================================


async def activate_fallback(service_name: str) -> None:
    """
    Activate fallback mode for specified service.

    Sets the fallback flag to True, indicating the service should use degraded mode
    (Claude Code evaluation instead of external API).

    Args:
        service_name: Service identifier ('haiku_evaluation' | 'haiku_reflexion')

    Raises:
        ValueError: If service_name is not recognized

    Example:
        >>> await activate_fallback('haiku_evaluation')
        >>> # Subsequent calls will use Claude Code evaluation
    """
    if service_name not in _fallback_state:
        raise ValueError(
            f"Unknown service: {service_name}. "
            f"Valid services: {list(_fallback_state.keys())}"
        )

    async with _state_lock:
        previous_state = _fallback_state[service_name]
        _fallback_state[service_name] = True

        if not previous_state:
            logger.warning(
                f"Fallback activated for {service_name}. "
                f"System entering degraded mode."
            )
        else:
            logger.info(f"Fallback already active for {service_name}. No change.")


async def deactivate_fallback(service_name: str) -> None:
    """
    Deactivate fallback mode for specified service (normal operation restored).

    Sets the fallback flag to False, indicating the external API is available again
    and the service should resume normal operation.

    Args:
        service_name: Service identifier ('haiku_evaluation' | 'haiku_reflexion')

    Raises:
        ValueError: If service_name is not recognized

    Example:
        >>> await deactivate_fallback('haiku_evaluation')
        >>> # Subsequent calls will use Haiku API evaluation
    """
    if service_name not in _fallback_state:
        raise ValueError(
            f"Unknown service: {service_name}. "
            f"Valid services: {list(_fallback_state.keys())}"
        )

    async with _state_lock:
        previous_state = _fallback_state[service_name]
        _fallback_state[service_name] = False

        if previous_state:
            logger.info(
                f"Fallback deactivated for {service_name}. "
                f"Degraded mode disabled, normal operation restored."
            )
        else:
            logger.info(f"Fallback already inactive for {service_name}. No change.")


async def is_fallback_active(service_name: str) -> bool:
    """
    Check if fallback mode is currently active for specified service.

    Args:
        service_name: Service identifier ('haiku_evaluation' | 'haiku_reflexion')

    Returns:
        True if fallback mode active (degraded mode), False if normal operation

    Raises:
        ValueError: If service_name is not recognized

    Example:
        >>> if await is_fallback_active('haiku_evaluation'):
        ...     # Use Claude Code fallback
        ... else:
        ...     # Use Haiku API
    """
    if service_name not in _fallback_state:
        raise ValueError(
            f"Unknown service: {service_name}. "
            f"Valid services: {list(_fallback_state.keys())}"
        )

    async with _state_lock:
        return _fallback_state[service_name]


async def get_all_fallback_status() -> Dict[str, bool]:
    """
    Get fallback status for all services.

    Returns:
        Dictionary mapping service names to fallback status
        Example: {'haiku_evaluation': False, 'haiku_reflexion': False}

    Example:
        >>> status = await get_all_fallback_status()
        >>> print(f"Haiku Evaluation: {status['haiku_evaluation']}")
    """
    async with _state_lock:
        return _fallback_state.copy()


# =============================================================================
# Testing / Debug Utilities
# =============================================================================


async def reset_all_fallback_state() -> None:
    """
    Reset all fallback states to False (normal operation).

    Used for testing and emergency recovery. Should NOT be called during normal operation.

    Warning:
        This is a testing utility. Use deactivate_fallback() for production recovery.
    """
    async with _state_lock:
        for service_name in _fallback_state:
            _fallback_state[service_name] = False

        logger.warning(
            "All fallback states reset to False. "
            "This should only happen in testing or emergency recovery."
        )
