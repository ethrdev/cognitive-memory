"""
Exponential Backoff Retry Logic for External API Calls.

Implements retry decorator with:
- Exponential backoff delays: [1s, 2s, 4s, 8s]
- Jitter: ±20% randomization (prevents Thundering Herd)
- Max 4 retries
- Retry conditions: Rate Limit (429), Service Unavailable (503), Timeout
- Logging to api_retry_log table ()
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime
from functools import wraps
from typing import Any, Callable, List, TypeVar

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)

# Type variable for decorated async functions
F = TypeVar("F", bound=Callable[..., Any])


def retry_with_backoff(
    max_retries: int = 4,
    base_delays: List[float] | None = None,
    jitter: bool = True,
) -> Callable[[F], F]:
    """
    Decorator for exponential backoff retry logic with jitter.

    Configuration (from config.yaml):
    - api_limits.anthropic.retry_attempts: 4
    - api_limits.anthropic.retry_delays: [1, 2, 4, 8]

    Retry Conditions:
    - HTTP 429 (Rate Limit): Anthropic API rate limit reached (1000 RPM)
    - HTTP 503 (Service Unavailable): Transient API failures
    - Timeout: Network glitches

    Jitter Strategy:
    - Applies ±20% randomization to delay times
    - Prevents Thundering Herd problem (multiple clients retrying simultaneously)
    - Example: 2s base delay → 1.6s to 2.4s actual delay

    Args:
        max_retries: Maximum number of retry attempts (default: 4)
        base_delays: Base delay times in seconds (default: [1, 2, 4, 8])
        jitter: Apply ±20% jitter to delays (default: True)

    Returns:
        Decorated async function with retry logic

    Example:
        >>> @retry_with_backoff(max_retries=4, base_delays=[1, 2, 4, 8])
        ... async def call_haiku_api():
        ...     # API call that might fail with 429 or 503
        ...     response = await client.messages.create(...)
        ...     return response
        ...
        >>> result = await call_haiku_api()  # Retries automatically on failure

    Implementation Notes:
    - Retry logging to api_retry_log table will be added in  Task 4
    - Fallback to Claude Code Evaluation (degraded mode) handled by caller
    - Only retries on specific exception types (Rate Limit, Service Unavailable, Timeout)
    """
    if base_delays is None:
        base_delays = [1.0, 2.0, 4.0, 8.0]

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            retry_count = 0  # Track actual retry attempts

            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    result = await func(*args, **kwargs)

                    # Log successful retry recovery (if retries occurred)
                    if attempt > 0:
                        error_type = type(last_exception).__name__ if last_exception else "Unknown"
                        logger.info(
                            f"{func.__name__} recovered after {attempt} retries. "
                            f"Last error was: {error_type}"
                        )
                        # Log successful retry to database
                        await _log_retry_success(
                            api_name=_extract_api_name(func),
                            error_type=error_type,
                            retry_count=attempt,
                        )

                    return result

                except Exception as e:
                    last_exception = e
                    error_type = type(e).__name__

                    # Check if exception is retryable
                    if not _is_retryable_error(e):
                        # Non-retryable error - fail immediately
                        logger.error(
                            f"{func.__name__} failed with non-retryable error: {error_type}: {e}"
                        )
                        raise

                    # Check if this was the last attempt
                    if attempt == max_retries:
                        # All retries exhausted
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries. "
                            f"Last error: {error_type}: {e}"
                        )
                        # Log final failure to database
                        await _log_retry_failure(
                            api_name=_extract_api_name(func),
                            error_type=error_type,
                            retry_count=max_retries,
                        )
                        raise

                    # Calculate delay with optional jitter
                    delay = base_delays[min(attempt, len(base_delays) - 1)]
                    if jitter:
                        # Apply ±20% jitter (0.8 to 1.2 multiplier)
                        delay *= random.uniform(0.8, 1.2)

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed "
                        f"({error_type}). Retrying in {delay:.2f}s..."
                    )

                    # Wait before retrying
                    await asyncio.sleep(delay)

            # Should never reach here, but handle gracefully
            if last_exception:
                raise last_exception
            raise RuntimeError(f"{func.__name__} failed without exception details")

        return wrapper  # type: ignore

    return decorator


def _is_retryable_error(error: Exception) -> bool:
    """
    Determine if an exception is retryable.

    Retryable Errors:
    - Rate Limit (HTTP 429): Anthropic API rate limit
    - Service Unavailable (HTTP 503): Transient API failures
    - Timeout: Network glitches
    - Connection Errors: Network issues

    Args:
        error: Exception to check

    Returns:
        True if error is retryable, False otherwise
    """
    error_type = type(error).__name__
    error_message = str(error).lower()

    # Check for HTTP status codes in error message
    retryable_statuses = ["429", "503", "504"]  # Rate Limit, Service Unavailable, Gateway Timeout
    if any(status in error_message for status in retryable_statuses):
        return True

    # Check for specific exception types
    retryable_types = [
        "RateLimitError",
        "ServiceUnavailableError",
        "TimeoutError",
        "ConnectionError",
        "APIConnectionError",
        "APITimeoutError",
    ]
    if error_type in retryable_types:
        return True

    # Check for timeout-related keywords in message
    timeout_keywords = ["timeout", "timed out", "connection reset"]
    if any(keyword in error_message for keyword in timeout_keywords):
        return True

    return False


def _extract_api_name(func: Callable) -> str:
    """
    Extract API name from function for logging.

    Args:
        func: Function being decorated

    Returns:
        API name string (e.g., "haiku_eval", "haiku_refl")
    """
    func_name = func.__name__

    # Map function names to API names for logging
    api_name_mapping = {
        "evaluate_answer": "haiku_eval",
        "generate_reflection": "haiku_refl",
        "_call_haiku_judge": "haiku_judge",
        "_call_gpt4o_judge": "gpt4o_judge",
        "create_embedding": "openai_embeddings",
    }

    return api_name_mapping.get(func_name, func_name)


async def _log_retry_success(
    api_name: str,
    error_type: str,
    retry_count: int,
) -> None:
    """
    Log successful retry recovery to database.

    Called when a retry attempt succeeds after 1+ failed attempts.
    Records that the API call recovered from transient failures.

    Args:
        api_name: API being called (e.g., "haiku_eval", "openai_embeddings")
        error_type: Type of error that was recovered from
        retry_count: Number of retry attempts before success (1-4)
    """
    try:
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO api_retry_log (api_name, error_type, retry_count, success)
                VALUES (%s, %s, %s, %s)
                """,
                (api_name, error_type, retry_count, True),
            )
            conn.commit()
            logger.debug(
                f"Retry success logged to database: api={api_name}, "
                f"error={error_type}, retries={retry_count}"
            )
    except Exception as e:
        # Log database error but don't fail the API call
        logger.warning(
            f"Failed to log retry success to database: {e}. "
            f"API call succeeded but logging failed."
        )


async def _log_retry_failure(
    api_name: str,
    error_type: str,
    retry_count: int,
) -> None:
    """
    Log final retry failure to database.

    Called when all retry attempts (max 4) have been exhausted.
    Records that the API call failed permanently after all retries.

    Args:
        api_name: API being called (e.g., "haiku_eval", "openai_embeddings")
        error_type: Type of error encountered
        retry_count: Total retry attempts made (should be 4)
    """
    try:
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO api_retry_log (api_name, error_type, retry_count, success)
                VALUES (%s, %s, %s, %s)
                """,
                (api_name, error_type, retry_count, False),
            )
            conn.commit()
            logger.debug(
                f"Retry failure logged to database: api={api_name}, "
                f"error={error_type}, retries={retry_count}"
            )
    except Exception as e:
        # Log database error but don't fail the API call
        # (it already failed, don't mask the original error)
        logger.warning(
            f"Failed to log retry failure to database: {e}. "
            f"Original API error will be raised."
        )
