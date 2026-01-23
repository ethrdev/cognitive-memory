"""
MCP Tools and Resources Discovery Tests

Tests MCP tools discovery, resources discovery, and listing functionality.
Story 1.3: E2E MCP Discovery functionality
"""

from __future__ import annotations

import pytest

from tests.e2e.mcp_server.conftest import MCPServerTester


class TestToolsDiscovery_1_3_E2E:
    """Test MCP tools discovery and listing (Story 1.3, E2E Tests)."""

    @pytest.mark.id("1.3-E2E-005")
    @pytest.mark.P0
    def test_list_tools_returns_7_tools(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #1: tools/list returns exactly 7 tools.

        GIVEN: MCP server is initialized
        WHEN: tools/list request is sent
        THEN: Response contains 7 tools with expected names
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

        # WHEN: List tools
        mcp_tester.write_mcp_request("tools/list", {})
        response = mcp_tester.read_mcp_response()

        # THEN: Response contains 7 tools
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        tools = response["result"]["tools"]
        assert len(tools) == 7, f"Expected 7 tools, got {len(tools)}"

        # AND: Check for expected tool names
        tool_names = [tool["name"] for tool in tools]
        expected_tools = [
            "store_raw_dialogue",
            "compress_to_l2_insight",
            "hybrid_search",
            "update_working_memory",
            "store_episode",
            "store_dual_judge_scores",
            "ping",
        ]
        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"Missing tool: {expected_tool}"

    @pytest.mark.id("1.3-E2E-006")
    @pytest.mark.P1
    def test_call_ping_tool(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #2: tools/call with ping tool returns pong.

        GIVEN: MCP server is initialized
        WHEN: tools/call request is sent for ping tool
        THEN: Response contains "pong" and success status
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

        # WHEN: Call ping tool
        mcp_tester.write_mcp_request("tools/call", {"name": "ping", "arguments": {}})

        response = mcp_tester.read_mcp_response()

        # THEN: Response is successful
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert result["response"] == "pong"
        assert result["tool"] == "ping"
        assert result["status"] == "ok"


class TestResourcesDiscovery_1_3_E2E:
    """Test MCP resources discovery and listing (Story 1.3, E2E Tests)."""

    @pytest.mark.id("1.3-E2E-007")
    @pytest.mark.P0
    def test_list_resources_returns_5_resources(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """
        AC #1: resources/list returns exactly 5 resources.

        GIVEN: MCP server is initialized
        WHEN: resources/list request is sent
        THEN: Response contains 5 resources with expected URIs
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

        # WHEN: List resources
        mcp_tester.write_mcp_request("resources/list", {})
        response = mcp_tester.read_mcp_response()

        # THEN: Response contains 5 resources
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        resources = response["result"]["resources"]
        assert len(resources) == 5, f"Expected 5 resources, got {len(resources)}"

        # AND: Check for expected resource URIs
        resource_uris = [resource["uri"] for resource in resources]
        expected_resources = [
            "memory://l2-insights",
            "memory://working-memory",
            "memory://episode-memory",
            "memory://l0-raw",
            "memory://status",
        ]
        for expected_resource in expected_resources:
            assert (
                expected_resource in resource_uris
            ), f"Missing resource: {expected_resource}"

    @pytest.mark.id("1.3-E2E-008")
    @pytest.mark.P1
    def test_read_status_resource(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #2: resources/read with memory://status returns server status.

        GIVEN: MCP server is initialized
        WHEN: resources/read request is sent for memory://status
        THEN: Response contains server, database, and connection_pool status
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

        # WHEN: Read status resource
        mcp_tester.write_mcp_request("resources/read", {"uri": "memory://status"})

        response = mcp_tester.read_mcp_response()

        # THEN: Response contains status information
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert result["status"] == "ok"
        assert result["resource"] == "memory://status"
        assert "server" in result
        assert "database" in result
        assert "connection_pool" in result
