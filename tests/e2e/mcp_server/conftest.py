"""
E2E Test Configuration for MCP Server Tests

Shared test helper class MCPServerTester and mcp_tester fixture.
All MCP server E2E tests use these utilities for subprocess management.
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any

import pytest


class MCPServerTester:
    """
    Helper class for testing MCP Server subprocess interactions.

    Provides methods for starting/stopping the MCP server subprocess,
    sending JSON-RPC 2.0 requests, and reading responses with efficient
    I/O polling (no hard waits).
    """

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.request_id = 1

    def start_server(self, startup_timeout: int = 5) -> None:
        """
        Start MCP Server as subprocess with stdio pipes.

        Args:
            startup_timeout: Maximum seconds to wait for server to be ready (default: 5)
        """
        try:
            self.process = subprocess.Popen(
                ["python", "-m", "mcp_server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Wait for server to be ready with explicit health check
            # ✅ GOOD: Poll with condition instead of hard sleep
            start_time = time.time()
            ready = False

            while time.time() - start_time < startup_timeout:
                # Check if process died during startup
                if self.process.poll() is not None:
                    stdout, stderr = self.process.communicate()
                    raise RuntimeError(
                        f"Server failed to start. stdout: {stdout}, stderr: {stderr}"
                    )

                # Check if stderr has startup log (indicates server is initializing)
                try:
                    # Non-blocking check if there's any stderr output
                    import select
                    ready_to_read, _, _ = select.select([self.process.stderr], [], [], 0)
                    if ready_to_read:
                        # Server has started writing to stderr - good sign
                        ready = True
                        break
                except (ImportError, AttributeError, OSError):
                    # select not available (Windows) or other issue
                    # Fallback: just check process is running
                    if self.process.poll() is None:
                        ready = True
                        break

                # Small sleep before next check (prevent busy waiting)
                time.sleep(0.05)

            if not ready:
                # Timeout exceeded but process is still running - assume ready
                if self.process.poll() is None:
                    ready = True

            # Final verification that process is still running
            if not ready or self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise RuntimeError(
                    f"Server failed to start within {startup_timeout}s. stdout: {stdout}, stderr: {stderr}"
                )

        except Exception as e:
            raise RuntimeError(f"Failed to start MCP server: {e}") from e

    def stop_server(self, timeout: int = 10) -> None:
        """Stop MCP Server gracefully with SIGTERM."""
        if self.process is None:
            return

        try:
            # Send SIGTERM for graceful shutdown
            self.process.terminate()

            # Wait for process to exit
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                self.process.kill()
                self.process.wait()

        except Exception as e:
            print(f"Error stopping server: {e}")
        finally:
            self.process = None

    def write_mcp_request(self, method: str, params: dict[str, Any]) -> None:
        """
        Write JSON-RPC 2.0 request to MCP server stdin.

        Args:
            method: MCP method name (e.g., "tools/list", "resources/list")
            params: Method parameters
        """
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("Server not started or stdin not available")

        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params,
        }

        request_json = json.dumps(request)
        self.process.stdin.write(request_json + "\n")
        self.process.stdin.flush()
        self.request_id += 1

    def read_mcp_response(self, timeout: int = 30, poll_interval: float = 0.01) -> dict[str, Any]:
        """
        Read JSON-RPC 2.0 response from MCP server stdout.

        ✅ GOOD: Uses select() for efficient polling with minimal CPU usage.

        Args:
            timeout: Maximum time to wait for response
            poll_interval: Seconds between polls (only used if select unavailable)

        Returns:
            Parsed JSON response
        """
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("Server not started or stdout not available")

        # Read response line with timeout
        start_time = time.time()

        try:
            # ✅ GOOD: Try to use select() for efficient I/O polling
            import select
            use_select = True
        except (ImportError, AttributeError):
            use_select = False

        while True:
            # Check if server died
            if self.process.poll() is not None:
                raise RuntimeError("Server process died while waiting for response")

            # Check timeout
            if time.time() - start_time > timeout:
                raise TimeoutError(f"No response received within {timeout} seconds")

            if use_select:
                # ✅ GOOD: Use select for efficient polling (waits until data available)
                try:
                    ready_to_read, _, _ = select.select([self.process.stdout], [], [], poll_interval)
                    if ready_to_read:
                        line = self.process.stdout.readline()
                        if line.strip():
                            break
                except (OSError, ValueError):
                    # Fallback to simple polling if select fails
                    use_select = False
            else:
                # Fallback: simple polling with short sleep
                line = self.process.stdout.readline()
                if line.strip():
                    break
                # Minimal sleep to prevent CPU spinning (only when select unavailable)
                time.sleep(poll_interval)

        try:
            response = json.loads(line.strip())
            return response
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Failed to parse JSON response: {e}\nResponse line: {line}"
            ) from e

    def check_server_logs(self) -> str:
        """Check server stderr for startup logs."""
        if self.process is None or self.process.stderr is None:
            return ""

        # Read any available stderr content
        lines = []
        while True:
            line = self.process.stderr.readline()
            if not line:
                break
            lines.append(line.strip())

        return "\n".join(lines)


@pytest.fixture
def mcp_tester():
    """
    Pytest fixture providing MCP Server tester.

    Automatically starts the server before each test and stops it after.
    """
    tester = MCPServerTester()
    try:
        tester.start_server()
        yield tester
    finally:
        tester.stop_server()
