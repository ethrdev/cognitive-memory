"""
MCP Server Error Handling Tests

Tests error handling for invalid requests and malformed inputs.
Story 1.3: E2E MCP Error handling functionality
"""

from __future__ import annotations

import pytest

from tests.e2e.mcp_server.conftest import MCPServerTester


class TestErrorHandling_1_3_E2E:
    """Test MCP error handling (Story 1.3, E2E Tests)."""

    @pytest.mark.id("1.3-E2E-009")
    @pytest.mark.P1
    def test_invalid_tool_call(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #1: Invalid tool call returns error result.

        GIVEN: MCP server is initialized
        WHEN: tools/call request is sent for non-existent tool
        THEN: Response contains error result
        """
        # GIVEN: Initialize the server
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        mcp_tester.read_mcp_response()

        # WHEN: Call non-existent tool
        mcp_tester.write_mcp_request(
            "tools/call", {"name": "non_existent_tool", "arguments": {}}
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Response contains error
        assert response["jsonrpc"] == "2.0"
        # Should return an error result (not an MCP protocol error)
        assert "result" in response
        result = response["result"]
        assert "error" in result

    @pytest.mark.id("1.3-E2E-010")
    @pytest.mark.P1
    def test_invalid_resource_uri(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #2: Invalid resource URI returns error result.

        GIVEN: MCP server is initialized
        WHEN: resources/read request is sent for non-existent resource
        THEN: Response contains error result
        """
        # GIVEN: Initialize the server
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"resources": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        mcp_tester.read_mcp_response()

        # WHEN: Read non-existent resource
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://non_existent_resource"}
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Response contains error
        assert response["jsonrpc"] == "2.0"
        # Should return an error result (not an MCP protocol error)
        assert "result" in response
        result = response["result"]
        assert "error" in result
