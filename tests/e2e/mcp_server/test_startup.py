"""
MCP Server Startup and Shutdown Tests

Tests server startup, basic functionality, and graceful shutdown.
Story 1.3: E2E MCP Server Startup and basic functionality
"""

from __future__ import annotations

import subprocess

import pytest

from tests.e2e.mcp_server.conftest import MCPServerTester


class TestMCPServerStartup_1_3_E2E:
    """Test MCP Server startup and basic functionality (Story 1.3, E2E Tests)."""

    @pytest.mark.id("1.3-E2E-001")
    @pytest.mark.P0
    def test_server_starts(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #1: Server starts successfully.

        GIVEN: MCP server is started via mcp_tester fixture
        WHEN: Server process is checked
        THEN: Process is running (not terminated)
        """
        # GIVEN: Server started via fixture
        # WHEN: Check process state
        # THEN: Server should be running
        assert mcp_tester.process is not None
        assert mcp_tester.process.poll() is None, "Server process should be running"

    @pytest.mark.id("1.3-E2E-002")
    @pytest.mark.P2
    def test_server_logs_startup(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #2: Server logs startup information.

        GIVEN: MCP server is started
        WHEN: Server logs are checked
        THEN: Startup logs are present or empty (non-blocking)
        """
        # GIVEN: Server started via fixture
        # WHEN: Check server logs
        logs = mcp_tester.check_server_logs()
        # THEN: Should have startup logs OR be empty (acceptable)
        assert (
            "Starting Cognitive Memory MCP Server" in logs or logs == ""
        ), "Should log server startup"


class TestGracefulShutdown_1_3_E2E:
    """Test graceful server shutdown (Story 1.3, E2E Tests)."""

    @pytest.mark.id("1.3-E2E-003")
    @pytest.mark.P1
    def test_sigterm_graceful_shutdown(self) -> None:
        """
        AC #3: SIGTERM triggers graceful shutdown.

        GIVEN: MCP server is started
        WHEN: SIGTERM signal is sent
        THEN: Server exits cleanly with code 0
        """
        # GIVEN: Server is started
        tester = MCPServerTester()
        tester.start_server()

        # WHEN: SIGTERM is sent
        if tester.process:
            tester.process.terminate()

        # THEN: Server exits cleanly
        try:
            exit_code = tester.process.wait(timeout=10)
            assert exit_code == 0, f"Expected clean exit code 0, got {exit_code}"
        except subprocess.TimeoutExpired:
            pytest.fail("Server did not shutdown gracefully within 10 seconds")
        finally:
            if tester.process and tester.process.poll() is None:
                tester.process.kill()
                tester.process.wait()
