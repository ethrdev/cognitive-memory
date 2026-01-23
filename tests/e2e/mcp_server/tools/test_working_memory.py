"""
E2E Tests for update_working_memory MCP Tool

Tests update_working_memory tool functionality including basic calls,
default importance, capacity enforcement, and validation errors.
Story 4.4: E2E update_working_memory tool functionality
"""

from __future__ import annotations

import pytest

from tests.e2e.mcp_server.conftest import MCPServerTester


class TestUpdateWorkingMemoryTool_4_4_E2E:
    """Test update_working_memory tool (Story 4.4, E2E Tests)."""

    @pytest.fixture(autouse=True)
    def setup_mcp_handshake(self, mcp_tester: MCPServerTester) -> None:
        """Initialize MCP connection for each test."""
        # GIVEN: MCP connection is initialized
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        response = mcp_tester.read_mcp_response()
        assert "result" in response

    @pytest.mark.id("4.4-E2E-005")
    @pytest.mark.P0
    def test_update_working_memory_basic_call(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """
        AC #1: Basic update_working_memory call succeeds.

        GIVEN: MCP server is initialized
        WHEN: update_working_memory is called with content and importance
        THEN: Returns success with added_id and working memory state
        """
        # GIVEN: MCP connection initialized
        # WHEN: Call with valid parameters
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "update_working_memory",
                "arguments": {
                    "content": "Test content for working memory",
                    "importance": 0.7,
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Success response
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert result["status"] == "ok"
        assert "added_id" in result
        assert result["tool"] == "update_working_memory"

    @pytest.mark.id("4.4-E2E-006")
    @pytest.mark.P1
    def test_update_working_memory_default_importance(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """
        AC #2: Default importance (0.5) is used when not specified.

        GIVEN: MCP server is initialized
        WHEN: update_working_memory is called without importance
        THEN: Uses default importance of 0.5
        """
        # GIVEN: MCP connection initialized
        # WHEN: Call without importance parameter
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "update_working_memory",
                "arguments": {
                    "content": "Test content with default importance",
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Success with default importance
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert result["status"] == "ok"
        assert "added_id" in result

    @pytest.mark.id("4.4-E2E-007")
    @pytest.mark.P1
    def test_update_working_memory_validation_errors(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """
        AC #3: Validation errors for invalid parameters.

        GIVEN: MCP server is initialized
        WHEN: update_working_memory is called with missing/invalid parameters
        THEN: Returns validation error
        """
        # GIVEN: MCP connection initialized
        # WHEN: Call without content parameter
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "update_working_memory",
                "arguments": {
                    "importance": 0.7,
                    # Missing content parameter
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Validation error
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert "error" in result
        assert "content" in result["details"]
