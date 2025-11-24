"""
Haiku API Health Check and Auto-Recovery

Periodic background task that monitors Haiku API availability and automatically
deactivates fallback mode when the API recovers.

: Claude Code Fallback für Haiku API Ausfall (Degraded Mode)
"""

import asyncio
import logging
import os
from typing import Optional

from anthropic import AsyncAnthropic

from mcp_server.state.fallback_state import deactivate_fallback, is_fallback_active
from mcp_server.utils.fallback_logger import log_fallback_recovery

logger = logging.getLogger(__name__)

# Health check configuration
HEALTH_CHECK_INTERVAL_SECONDS = 900  # 15 minutes (900 seconds)
HEALTH_CHECK_TIMEOUT_SECONDS = 10   # Timeout for health check API call


async def _lightweight_haiku_ping() -> bool:
    """
    Perform lightweight Haiku API health check.

    Makes a minimal API call to verify the service is responding.
    Uses a very simple prompt to minimize token usage and cost.

    Returns:
        True if API is healthy (successful response), False otherwise

    Note:
        This is a minimal health check, not a full evaluation test.
        Cost: ~€0.0001 per ping (negligible)
    """
    try:
        # Get API key from environment
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key or api_key == "sk-ant-your-anthropic-api-key-here":
            logger.warning(
                "Anthropic API key not configured. Health check cannot proceed."
            )
            return False

        # Initialize client for health check
        client = AsyncAnthropic(api_key=api_key)

        # Minimal API call (cheapest possible health check)
        response = await asyncio.wait_for(
            client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            ),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )

        # If we got a response, API is healthy
        if response and response.content:
            logger.debug("Haiku API health check: ✅ SUCCESS")
            return True
        else:
            logger.warning("Haiku API health check: ❌ FAILED (empty response)")
            return False

    except asyncio.TimeoutError:
        logger.warning(
            f"Haiku API health check: ❌ TIMEOUT "
            f"(exceeded {HEALTH_CHECK_TIMEOUT_SECONDS}s)"
        )
        return False

    except Exception as e:
        logger.warning(
            f"Haiku API health check: ❌ FAILED "
            f"({type(e).__name__}: {str(e)})"
        )
        return False


async def periodic_health_check() -> None:
    """
    Background task that runs periodic health checks for Haiku API.

    Runs every 15 minutes (configurable via HEALTH_CHECK_INTERVAL_SECONDS).
    If fallback mode is active and health check succeeds, automatically
    deactivates fallback and logs recovery.

    Health Check Flow:
    1. Wait 15 minutes (don't check immediately on startup)
    2. If fallback active → perform lightweight API ping
    3. If ping succeeds → deactivate fallback, log recovery
    4. If ping fails → log warning, continue (don't trigger new fallback)
    5. Repeat indefinitely

    Never raises exceptions - catches all errors internally to ensure
    the background task continues running.

    Note:
        This function is designed to run as a background task:
        asyncio.create_task(periodic_health_check())
    """
    logger.info(
        f"Health check background task started. "
        f"Checking every {HEALTH_CHECK_INTERVAL_SECONDS}s (15 minutes)."
    )

    while True:
        try:
            # Wait for next health check interval
            await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)

            # Check if fallback is currently active for haiku_evaluation
            service_name = "haiku_evaluation"
            fallback_active = await is_fallback_active(service_name)

            if not fallback_active:
                logger.debug(
                    f"Health check: Fallback not active for {service_name}. "
                    f"Skipping API ping."
                )
                continue

            # Fallback is active - perform health check
            logger.info(
                f"Health check: Fallback active for {service_name}. "
                f"Pinging Haiku API..."
            )

            api_healthy = await _lightweight_haiku_ping()

            if api_healthy:
                # API recovered - deactivate fallback
                logger.info(
                    f"✅ Haiku API recovered! Deactivating fallback for {service_name}."
                )

                await deactivate_fallback(service_name)
                await log_fallback_recovery(
                    service_name=service_name,
                    recovery_method="health_check_success",
                )

                logger.info(
                    f"✅ Degraded mode disabled. Normal operation restored for {service_name}."
                )

            else:
                # API still unavailable - log warning but don't re-trigger fallback
                logger.warning(
                    f"⚠️ Health check failed. Haiku API still unavailable. "
                    f"Degraded mode remains active for {service_name}."
                )
                # IMPORTANT: Don't trigger new fallback - this would cause infinite loop

        except Exception as e:
            # Catch all exceptions to ensure background task continues running
            logger.error(
                f"Error in periodic health check: {type(e).__name__}: {e}",
                exc_info=True,
            )
            # Continue loop - don't let one failure stop health checks


async def manual_health_check(service_name: str = "haiku_evaluation") -> dict:
    """
    Perform one-time manual health check (for testing/debugging).

    Args:
        service_name: Service to check ('haiku_evaluation' | 'haiku_reflexion')

    Returns:
        Dict with:
        - api_healthy: bool (True if API responding)
        - fallback_active: bool (current fallback status)
        - action_taken: str (what happened)

    Example:
        >>> result = await manual_health_check('haiku_evaluation')
        >>> print(f"API Healthy: {result['api_healthy']}")
        >>> print(f"Fallback Active: {result['fallback_active']}")
    """
    try:
        # Check current fallback status
        fallback_active = await is_fallback_active(service_name)

        # Perform health check
        api_healthy = await _lightweight_haiku_ping()

        action_taken = "none"

        if api_healthy and fallback_active:
            # Recover from fallback
            await deactivate_fallback(service_name)
            await log_fallback_recovery(
                service_name=service_name,
                recovery_method="manual_health_check",
            )
            action_taken = "fallback_deactivated"
            logger.info(f"Manual health check: Recovered {service_name}")

        elif not api_healthy and fallback_active:
            action_taken = "still_in_fallback"
            logger.warning(f"Manual health check: {service_name} still in fallback")

        elif api_healthy and not fallback_active:
            action_taken = "already_healthy"
            logger.info(f"Manual health check: {service_name} already healthy")

        else:  # not api_healthy and not fallback_active
            action_taken = "api_unhealthy_no_fallback"
            logger.warning(
                f"Manual health check: {service_name} API unhealthy but fallback not active"
            )

        return {
            "api_healthy": api_healthy,
            "fallback_active": fallback_active,
            "action_taken": action_taken,
        }

    except Exception as e:
        logger.error(f"Manual health check failed: {e}", exc_info=True)
        return {
            "api_healthy": False,
            "fallback_active": False,
            "action_taken": "error",
            "error": str(e),
        }
