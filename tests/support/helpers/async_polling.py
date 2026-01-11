"""
Async Polling and Wait Utilities for Tests

Helper functions for explicit waits and polling in tests.
Use these instead of hardcoded time.sleep() calls.

## Patterns

GOOD - Explicit wait with condition:
    result = wait_for_condition(
        condition=lambda: conn.fetchrow("SELECT status FROM jobs")["status"] == "done",
        timeout=5.0,
        description="Job completion"
    )

GOOD - Poll with check interval:
    wait_for_server_ready(process, timeout=10, poll_interval=0.05)

BAD - Hard sleep without condition:
    time.sleep(1)  # ❌ Don't do this - arbitrary wait

## Legitimate Uses of time.sleep()

1. **Performance Tests**: Simulating slow operations
   Example: asyncio.sleep(0.01) to simulate API latency

2. **Process Control**: subprocess.wait(timeout=X) - OS API for process management

3. **Minimal Backoff**: When select() unavailable, 0.01-0.05s to prevent CPU spinning

See tests/support/documentation/test_wait_patterns.md for detailed guide.
"""

import time
import subprocess
from typing import Callable, TypeVar, Optional
from dataclasses import dataclass


T = TypeVar("T")


@dataclass
class WaitResult:
    """Result of a wait operation."""
    success: bool
    value: Optional[T] = None
    elapsed_seconds: float = 0.0
    error: Optional[str] = None


def wait_for_condition(
    condition: Callable[[], T],
    timeout: float = 5.0,
    poll_interval: float = 0.05,
    description: str = "condition"
) -> WaitResult:
    """
    Poll until a condition is true or timeout expires.

    ✅ GOOD: Explicit wait with condition - use instead of time.sleep()

    Args:
        condition: Callable that returns truthy value when condition met
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls (use 0.01-0.1 for responsiveness)
        description: Human-readable description for error messages

    Returns:
        WaitResult with success=True and value when condition met

    Raises:
        TimeoutError: If timeout expires before condition is met

    Example:
        def is_server_ready():
            return subprocess.poll() is not None

        result = wait_for_condition(is_server_ready, timeout=5)
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            result = condition()
            if result:
                elapsed = time.time() - start_time
                return WaitResult(success=True, value=result, elapsed_seconds=elapsed)
        except Exception as e:
            # Condition raised exception - treat as not ready
            pass

        time.sleep(poll_interval)

    elapsed = time.time() - start_time
    raise TimeoutError(
        f"Condition '{description}' not met within {timeout}s "
        f"(waited {elapsed:.2f}s, poll interval {poll_interval}s)"
    )


def wait_for_process_ready(
    process: subprocess.Popen,
    timeout: float = 10.0,
    poll_interval: float = 0.05
) -> WaitResult:
    """
    Wait for subprocess to be ready (process is running and not crashed).

    ✅ GOOD: Explicit health check instead of time.sleep(1)

    Args:
        process: subprocess.Popen instance to wait for
        timeout: Maximum seconds to wait
        poll_interval: Seconds between health checks

    Returns:
        WaitResult with success=True when process is ready

    Raises:
        RuntimeError: If process dies during startup
        TimeoutError: If timeout expires
    """
    def check_process():
        if process.poll() is not None:
            raise RuntimeError(f"Process died with exit code {process.returncode}")
        return True  # Process is running

    return wait_for_condition(
        check_process,
        timeout=timeout,
        poll_interval=poll_interval,
        description="Process ready and running"
    )


def wait_for_process_output(
    process: subprocess.Popen,
    stream: str = "stdout",  # or "stderr"
    timeout: float = 30.0,
    poll_interval: float = 0.01
) -> str:
    """
    Wait for subprocess to output to a stream.

    ✅ GOOD: Efficient I/O polling with select() when available

    Args:
        process: subprocess.Popen instance
        stream: "stdout" or "stderr" to read from
        timeout: Maximum seconds to wait
        poll_interval: Seconds between polls (fallback only)

    Returns:
        First line of output from the stream

    Raises:
        RuntimeError: If process dies while waiting
        TimeoutError: If timeout expires
    """
    stream_obj = getattr(process, stream, None)
    if stream_obj is None:
        raise ValueError(f"Process has no {stream} stream")

    start_time = time.time()

    # Try to use select for efficient polling
    try:
        import select
        use_select = True
    except (ImportError, AttributeError):
        use_select = False

    while time.time() - start_time < timeout:
        if process.poll() is not None:
            raise RuntimeError("Process died while waiting for output")

        if time.time() - start_time > timeout:
            raise TimeoutError(f"No output within {timeout}s")

        if use_select:
            try:
                ready_to_read, _, _ = select.select([stream_obj], [], [], poll_interval)
                if ready_to_read:
                    line = stream_obj.readline()
                    if line.strip():
                        return line.strip()
            except (OSError, ValueError):
                use_select = False
        else:
            line = stream_obj.readline()
            if line.strip():
                return line.strip()
            time.sleep(poll_interval)

    raise TimeoutError(f"No output received within {timeout}s")


def create_polling_wait(description: str = "poll"):
    """
    Create a reusable polling wait function with custom parameters.

    Useful for common wait patterns in a test suite.

    Example:
        wait_for_db = create_polling_wait("DB ready")
        wait_for_db(lambda: check_db_connection(), timeout=10)
    """
    def _wait(
        condition: Callable[[], T],
        timeout: float = 5.0,
        poll_interval: float = 0.05
    ) -> WaitResult:
        return wait_for_condition(
            condition,
            timeout=timeout,
            poll_interval=poll_interval,
            description=description
        )
    return _wait


# Pre-configured wait functions for common scenarios
wait_for_db_ready = create_polling_wait("Database ready")
wait_for_api_ready = create_polling_wait("API ready")
wait_for_server_ready = create_polling_wait("Server ready")
