"""
E2E Tests for store_episode MCP Tool

Tests store_episode tool functionality including valid calls,
reward validation, reflection validation, and boundary tests.
Story 4.4: E2E store_episode tool functionality
"""

from __future__ import annotations

import pytest

from tests.e2e.mcp_server.conftest import MCPServerTester
from tests.factories import create_episode_data


class TestStoreEpisodeTool_4_4_E2E:
    """Test store_episode tool (Story 4.4, E2E Tests)."""

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

    @pytest.mark.id("4.4-E2E-008")
    @pytest.mark.P0
    def test_store_episode_valid_call(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #1: Valid store_episode call succeeds.

        GIVEN: MCP server is initialized
        WHEN: store_episode is called with valid query, reward, and reflection
        THEN: Returns success with episode_id
        """
        # GIVEN: Valid episode data
        episode_data = create_episode_data(
            query="test query about memory",
            reward=0.8,
            reflection="Problem: User query failed. Lesson: Need better indexing."
        )

        # WHEN: Call with valid parameters
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "store_episode",
                "arguments": episode_data,
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Success response
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert result["status"] == "ok"
        assert "episode_id" in result
        assert result["tool"] == "store_episode"

    @pytest.mark.id("4.4-E2E-009")
    @pytest.mark.P1
    def test_store_episode_invalid_reward(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #2: Invalid reward values return validation error.

        GIVEN: MCP server is initialized
        WHEN: store_episode is called with reward > 1.0
        THEN: Returns validation error about reward range (-1.0 to 1.0)
        """
        # GIVEN: Episode data with invalid reward
        episode_data = create_episode_data(
            query="test query",
            reward=1.5,  # Invalid: > 1.0
            reflection="test reflection"
        )

        # WHEN: Call with invalid reward
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "store_episode",
                "arguments": episode_data,
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Validation error
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert "error" in result
        assert "reward" in result["details"]

    @pytest.mark.id("4.4-E2E-010")
    @pytest.mark.P1
    def test_store_episode_missing_parameters(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """
        AC #3: Missing required parameters return validation error.

        GIVEN: MCP server is initialized
        WHEN: store_episode is called without reflection parameter
        THEN: Returns validation error about missing reflection
        """
        # GIVEN: Episode data missing reflection
        episode_data = create_episode_data(
            query="test query",
            reward=0.5,
            # Missing reflection parameter
        )
        del episode_data["reflection"]

        # WHEN: Call with missing parameter
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "store_episode",
                "arguments": episode_data,
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Validation error
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert "error" in result
        assert "reflection" in result["details"]
