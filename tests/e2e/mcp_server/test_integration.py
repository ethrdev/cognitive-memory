"""
MCP Server Integration Flow Tests

Tests complete integration flow from initialize through tools/resources to shutdown.
Story 1.3: E2E MCP Integration flow
"""

from __future__ import annotations

import pytest

from tests.e2e.mcp_server.conftest import MCPServerTester


class TestIntegrationFlow_1_3_E2E:
    """Test complete integration flow (Story 1.3, E2E Tests)."""

    @pytest.mark.id("1.3-E2E-011")
    @pytest.mark.P0
    def test_complete_workflow(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #1: Complete workflow: Initialize → Tools → Resources → Verify.

        GIVEN: MCP server is started
        WHEN: Initialize, list tools, and list resources requests are sent sequentially
        THEN: All responses succeed and contain expected data
        """
        # GIVEN: Server started via fixture

        # WHEN: Initialize
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        response = mcp_tester.read_mcp_response()
        assert "result" in response

        # AND: List tools
        mcp_tester.write_mcp_request("tools/list", {})
        response = mcp_tester.read_mcp_response()
        assert "result" in response
        tools = response["result"]["tools"]
        assert len(tools) > 0

        # AND: List resources
        mcp_tester.write_mcp_request("resources/list", {})
        response = mcp_tester.read_mcp_response()
        assert "result" in response
        resources = response["result"]["resources"]
        assert len(resources) > 0

        # THEN: All requests succeeded
        assert True, "Complete workflow successful"
