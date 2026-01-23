"""
MCP Protocol Handshake Tests

Tests MCP protocol initialize request and response handling.
Story 1.3: E2E MCP Handshake functionality
"""

from __future__ import annotations

import pytest

from tests.e2e.mcp_server.conftest import MCPServerTester


class TestMCPHandshake_1_3_E2E:
    """Test MCP protocol handshake (Story 1.3, E2E Tests)."""

    @pytest.mark.id("1.3-E2E-004")
    @pytest.mark.P0
    def test_initialize_request(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #1: MCP initialize request succeeds.

        GIVEN: MCP server is started
        WHEN: Initialize request is sent with protocol version and capabilities
        THEN: Response contains protocol version and server capabilities
        """
        # GIVEN: Server started via fixture
        # WHEN: Initialize request is sent
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )

        # Read response
        response = mcp_tester.read_mcp_response()

        # THEN: Response contains required fields
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "protocolVersion" in response["result"]
        assert "capabilities" in response["result"]
