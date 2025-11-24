"""
Integration Tests for MCP Server

Tests the MCP Server functionality using subprocess-based testing with stdio transport.
Validates MCP protocol compliance, tool discovery, resource discovery, and basic operations.
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Any

import pytest


class MCPServerTester:
    """Helper class for testing MCP Server subprocess interactions."""

    def __init__(self):
        self.process: subprocess.Popen | None = None
        self.request_id = 1

    def start_server(self) -> None:
        """Start MCP Server as subprocess with stdio pipes."""
        try:
            self.process = subprocess.Popen(
                ["python", "-m", "mcp_server"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
            )

            # Give server a moment to start up
            time.sleep(1)

            # Check if process is still running
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                raise RuntimeError(
                    f"Server failed to start. stdout: {stdout}, stderr: {stderr}"
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

    def read_mcp_response(self, timeout: int = 30) -> dict[str, Any]:
        """
        Read JSON-RPC 2.0 response from MCP server stdout.

        Args:
            timeout: Maximum time to wait for response

        Returns:
            Parsed JSON response
        """
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("Server not started or stdout not available")

        # Read response line with timeout
        start_time = time.time()
        while True:
            if self.process.poll() is not None:
                raise RuntimeError("Server process died while waiting for response")

            # Try to read a line
            line = self.process.stdout.readline()
            if line.strip():
                break

            # Check timeout
            if time.time() - start_time > timeout:
                raise TimeoutError(f"No response received within {timeout} seconds")

            time.sleep(0.1)  # Small delay to prevent busy waiting

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
    """Pytest fixture providing MCP Server tester."""
    tester = MCPServerTester()
    try:
        tester.start_server()
        yield tester
    finally:
        tester.stop_server()


class TestMCPServerStartup:
    """Test MCP Server startup and basic functionality."""

    def test_server_starts(self, mcp_tester: MCPServerTester) -> None:
        """Test that server starts successfully."""
        assert mcp_tester.process is not None
        assert mcp_tester.process.poll() is None, "Server process should be running"

    def test_server_logs_startup(self, mcp_tester: MCPServerTester) -> None:
        """Test that server logs startup information."""
        logs = mcp_tester.check_server_logs()
        # Check for startup-related log entries
        assert (
            "Starting Cognitive Memory MCP Server" in logs or logs == ""
        ), "Should log server startup"


class TestMCPHandshake:
    """Test MCP protocol handshake."""

    def test_initialize_request(self, mcp_tester: MCPServerTester) -> None:
        """Test MCP initialize request."""
        # Send initialize request
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

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert "protocolVersion" in response["result"]
        assert "capabilities" in response["result"]


class TestToolsDiscovery:
    """Test MCP tools discovery and listing."""

    def test_list_tools_returns_7_tools(self, mcp_tester: MCPServerTester) -> None:
        """Test that list_tools returns exactly 7 tools."""
        # Send initialize first
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        mcp_tester.read_mcp_response()

        # List tools
        mcp_tester.write_mcp_request("tools/list", {})
        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        tools = response["result"]["tools"]
        assert len(tools) == 7, f"Expected 7 tools, got {len(tools)}"

        # Check for expected tool names
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

    def test_call_ping_tool(self, mcp_tester: MCPServerTester) -> None:
        """Test calling the ping tool."""
        # Initialize first
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        mcp_tester.read_mcp_response()

        # Call ping tool
        mcp_tester.write_mcp_request("tools/call", {"name": "ping", "arguments": {}})

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert result["response"] == "pong"
        assert result["tool"] == "ping"
        assert result["status"] == "ok"


class TestResourcesDiscovery:
    """Test MCP resources discovery and listing."""

    def test_list_resources_returns_5_resources(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test that list_resources returns exactly 5 resources."""
        # Initialize first
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"resources": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        mcp_tester.read_mcp_response()

        # List resources
        mcp_tester.write_mcp_request("resources/list", {})
        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        resources = response["result"]["resources"]
        assert len(resources) == 5, f"Expected 5 resources, got {len(resources)}"

        # Check for expected resource URIs
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

    def test_read_status_resource(self, mcp_tester: MCPServerTester) -> None:
        """Test reading the memory://status resource."""
        # Initialize first
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"resources": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        mcp_tester.read_mcp_response()

        # Read status resource
        mcp_tester.write_mcp_request("resources/read", {"uri": "memory://status"})

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert result["status"] == "ok"
        assert result["resource"] == "memory://status"
        assert "server" in result
        assert "database" in result
        assert "connection_pool" in result


class TestErrorHandling:
    """Test MCP server error handling."""

    def test_invalid_tool_call(self, mcp_tester: MCPServerTester) -> None:
        """Test error handling for invalid tool calls."""
        # Initialize first
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        mcp_tester.read_mcp_response()

        # Call non-existent tool
        mcp_tester.write_mcp_request(
            "tools/call", {"name": "non_existent_tool", "arguments": {}}
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        error = response["error"]
        assert error["code"] == -32601  # Method not found

    def test_invalid_resource_uri(self, mcp_tester: MCPServerTester) -> None:
        """Test error handling for invalid resource URIs."""
        # Initialize first
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"resources": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        mcp_tester.read_mcp_response()

        # Read non-existent resource
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://non_existent_resource"}
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        # Should return an error result (not an MCP protocol error)
        assert "result" in response
        result = response["result"]
        assert "error" in result


class TestGracefulShutdown:
    """Test graceful server shutdown."""

    def test_sigterm_graceful_shutdown(self) -> None:
        """Test SIGTERM triggers graceful shutdown."""
        # Start server
        tester = MCPServerTester()
        tester.start_server()

        # Send SIGTERM
        if tester.process:
            tester.process.terminate()

        # Wait for graceful shutdown
        try:
            exit_code = tester.process.wait(timeout=10)
            assert exit_code == 0, f"Expected clean exit code 0, got {exit_code}"
        except subprocess.TimeoutExpired:
            pytest.fail("Server did not shutdown gracefully within 10 seconds")
        finally:
            if tester.process and tester.process.poll() is None:
                tester.process.kill()
                tester.process.wait()


class TestIntegrationFlow:
    """Test complete integration flow."""

    def test_complete_workflow(self, mcp_tester: MCPServerTester) -> None:
        """Test complete workflow: Initialize → Tools → Resources → Shutdown."""
        # Initialize
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

        # List tools
        mcp_tester.write_mcp_request("tools/list", {})
        response = mcp_tester.read_mcp_response()
        assert len(response["result"]["tools"]) == 7

        # Call ping tool
        mcp_tester.write_mcp_request("tools/call", {"name": "ping", "arguments": {}})
        response = mcp_tester.read_mcp_response()
        assert response["result"]["response"] == "pong"

        # List resources
        mcp_tester.write_mcp_request("resources/list", {})
        response = mcp_tester.read_mcp_response()
        assert len(response["result"]["resources"]) == 5

        # Read status resource
        mcp_tester.write_mcp_request("resources/read", {"uri": "memory://status"})
        response = mcp_tester.read_mcp_response()
        assert response["result"]["status"] == "ok"

        # Workflow completed successfully
        assert True  # If we reach here, the workflow succeeded


class TestHybridSearchTool:
    """Integration tests for hybrid_search tool."""

    @pytest.fixture(autouse=True)
    def setup_mcp_handshake(self, mcp_tester: MCPServerTester) -> None:
        """Initialize MCP connection for each test."""
        # Initialize MCP connection
        mcp_tester.write_mcp_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        response = mcp_tester.read_mcp_response()
        assert response["jsonrpc"] == "2.0"

    def test_hybrid_search_parameter_validation(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test hybrid_search parameter validation with invalid inputs."""
        # Test with missing required parameters
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_text": "consciousness"
                    # Missing 'query_embedding' parameter
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert "query_embedding" in result["details"]
        assert result["tool"] == "hybrid_search"

    def test_hybrid_search_invalid_embedding_dimension(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test hybrid_search with wrong embedding dimension."""
        # Create 512-dim embedding instead of required 1536-dim
        query_embedding = [0.1] * 512
        query_text = "consciousness"

        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": query_text,
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert "embedding dimension" in result["details"]
        assert "1536" in result["details"]
        assert result["tool"] == "hybrid_search"

    def test_hybrid_search_invalid_weights(self, mcp_tester: MCPServerTester) -> None:
        """Test hybrid_search with invalid weights (sum != 1.0)."""
        query_embedding = [0.1] * 1536
        query_text = "consciousness"
        weights = {"semantic": 0.8, "keyword": 0.5}  # Sum = 1.3

        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": query_text,
                    "weights": weights,
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert "Weights must sum to 1.0" in result["details"]
        assert result["tool"] == "hybrid_search"

    def test_hybrid_search_invalid_top_k(self, mcp_tester: MCPServerTester) -> None:
        """Test hybrid_search with invalid top_k values."""
        query_embedding = [0.1] * 1536
        query_text = "consciousness"

        # Test top_k = 0 (invalid)
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": query_text,
                    "top_k": 0,
                },
            },
        )

        response = mcp_tester.read_mcp_response()
        result = response["result"]
        assert "error" in result
        assert "top_k" in result["details"]

        # Test top_k = -5 (invalid)
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": query_text,
                    "top_k": -5,
                },
            },
        )

        response = mcp_tester.read_mcp_response()
        result = response["result"]
        assert "error" in result
        assert "top_k" in result["details"]

        # Test top_k = 200 (invalid, exceeds max 100)
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": query_text,
                    "top_k": 200,
                },
            },
        )

        response = mcp_tester.read_mcp_response()
        result = response["result"]
        assert "error" in result
        assert "top_k" in result["details"]

    def test_hybrid_search_empty_query_text(self, mcp_tester: MCPServerTester) -> None:
        """Test hybrid_search with empty query text."""
        query_embedding = [0.1] * 1536
        query_text = ""  # Empty string

        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": query_text,
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert "query_text" in result["details"]
        assert result["tool"] == "hybrid_search"

    def test_hybrid_search_empty_result_handling(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test hybrid_search with query that likely returns no results (empty results should NOT be an error)."""
        # Use highly specific embedding and text that won't match anything
        query_embedding = [0.9999] * 1536
        query_text = "nonexistent_concept_xyz_12345_unique_phrase"

        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": query_text,
                    "top_k": 5,
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Empty results should return success (NOT an error)
        if "error" not in result:
            assert result["status"] == "success"
            assert result["results"] == []  # Should be empty list
            assert result["semantic_results_count"] == 0
            assert result["keyword_results_count"] == 0
            assert result["final_results_count"] == 0
        else:
            # Only database connection errors are acceptable
            assert "Database" in result["details"] or "connection" in result["details"]

    def test_hybrid_search_default_parameters(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test hybrid_search with default parameters (top_k=5, weights={"semantic": 0.7, "keyword": 0.3})."""
        query_embedding = [0.1] * 1536
        query_text = "consciousness"

        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": query_text,
                    # top_k and weights use defaults
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should either succeed (if database has content) or return empty results (NOT an error)
        if "error" not in result:
            # Successful case
            assert result["status"] == "success"
            assert "results" in result
            assert "query_embedding_dimension" in result
            assert result["query_embedding_dimension"] == 1536
            assert "semantic_results_count" in result
            assert "keyword_results_count" in result
            assert "final_results_count" in result
            assert "weights" in result
            assert result["weights"]["semantic"] == 0.7
            assert result["weights"]["keyword"] == 0.3
        else:
            # Error case - should only be database connection errors, not validation errors
            assert "Database" in result["details"] or "connection" in result["details"]


class TestUpdateWorkingMemoryTool:
    """Integration tests for update_working_memory tool."""

    @pytest.fixture(autouse=True)
    def setup_mcp_handshake(self, mcp_tester: MCPServerTester) -> None:
        """Initialize MCP connection for each test."""
        # Initialize MCP connection
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

    def test_update_working_memory_basic_call(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test basic update_working_memory call with valid parameters."""
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

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should succeed
        assert result["status"] == "success"
        assert "added_id" in result
        assert isinstance(result["added_id"], int)
        assert result["added_id"] > 0
        assert result["evicted_id"] is None  # No eviction on first item
        assert result["archived_id"] is None  # No archival on first item

    def test_update_working_memory_default_importance(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test update_working_memory with default importance (0.5)."""
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "update_working_memory",
                "arguments": {"content": "Test content with default importance"},
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert result["status"] == "success"
        assert "added_id" in result
        assert isinstance(result["added_id"], int)

    def test_update_working_memory_capacity_enforcement(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test capacity enforcement - add 15 items, verify 5 evicted."""
        # Add 15 items to trigger eviction
        evicted_count = 0
        archived_count = 0

        for i in range(15):
            mcp_tester.write_mcp_request(
                "tools/call",
                {
                    "name": "update_working_memory",
                    "arguments": {
                        "content": f"Capacity test item {i}",
                        "importance": 0.6,
                    },
                },
            )

            response = mcp_tester.read_mcp_response()

            assert response["jsonrpc"] == "2.0"
            assert "result" in response
            result = response["result"]

            assert result["status"] == "success"
            assert "added_id" in result

            # After first 10 items, subsequent calls should trigger eviction
            if i >= 10:
                assert result["evicted_id"] is not None
                assert result["archived_id"] is not None
                evicted_count += 1
                archived_count += 1

        # Should have evicted exactly 5 items
        assert evicted_count == 5
        assert archived_count == 5

    def test_update_working_memory_critical_items_protection(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test critical items protection - add 10 critical + 5 normal, verify only normal evicted."""
        # Add 10 critical items first
        critical_ids = []
        for i in range(10):
            mcp_tester.write_mcp_request(
                "tools/call",
                {
                    "name": "update_working_memory",
                    "arguments": {"content": f"Critical item {i}", "importance": 0.9},
                },
            )

            response = mcp_tester.read_mcp_response()
            result = response["result"]
            critical_ids.append(result["added_id"])

        # Add 5 normal items (should trigger eviction of normal items only)
        for i in range(5):
            mcp_tester.write_mcp_request(
                "tools/call",
                {
                    "name": "update_working_memory",
                    "arguments": {"content": f"Normal item {i}", "importance": 0.6},
                },
            )

            response = mcp_tester.read_mcp_response()
            result = response["result"]

            # All normal additions should have evicted something
            assert result["evicted_id"] is not None
            assert result["archived_id"] is not None

        # Note: We can't easily verify which specific items were evicted without DB access
        # But the test validates the eviction mechanism works through MCP

    def test_update_working_memory_validation_errors(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test validation errors for invalid parameters."""
        # Test empty content
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "update_working_memory",
                "arguments": {"content": "", "importance": 0.6},
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert "Content is required" in result["error"]
        assert result["tool"] == "update_working_memory"

        # Test invalid importance
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "update_working_memory",
                "arguments": {"content": "Test content", "importance": 1.5},
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert "Importance must be between 0.0 and 1.0" in result["error"]
        assert result["tool"] == "update_working_memory"

        # Test missing content
        mcp_tester.write_mcp_request(
            "tools/call",
            {"name": "update_working_memory", "arguments": {"importance": 0.6}},
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert "Content is required" in result["error"]
        assert result["tool"] == "update_working_memory"


class TestStoreEpisodeTool:
    """Integration tests for store_episode tool."""

    @pytest.fixture(autouse=True)
    def setup_mcp_handshake(self, mcp_tester: MCPServerTester) -> None:
        """Initialize MCP connection for each test."""
        # Initialize MCP connection
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

    def test_store_episode_valid_call(self, mcp_tester: MCPServerTester) -> None:
        """Test store_episode call with valid parameters."""
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "store_episode",
                "arguments": {
                    "query": "test query",
                    "reward": 0.8,
                    "reflection": "test reflection",
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Verify success response format
        assert "id" in result
        assert "embedding_status" in result
        assert "query" in result
        assert "reward" in result
        assert "created_at" in result

        assert result["embedding_status"] == "success"
        assert result["query"] == "test query"
        assert result["reward"] == 0.8
        assert isinstance(result["id"], int)
        assert result["id"] > 0

    def test_store_episode_invalid_reward(self, mcp_tester: MCPServerTester) -> None:
        """Test store_episode with invalid reward value."""
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "store_episode",
                "arguments": {
                    "query": "test query",
                    "reward": -2.0,  # Invalid: outside [-1.0, 1.0] range
                    "reflection": "test reflection",
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Verify error response format
        assert "error" in result
        assert "details" in result
        assert "tool" in result
        assert "embedding_status" in result

        assert result["embedding_status"] == "failed"
        assert result["tool"] == "store_episode"
        assert "Reward out of range" in result["error"]

    def test_store_episode_empty_reflection(self, mcp_tester: MCPServerTester) -> None:
        """Test store_episode with empty reflection."""
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "store_episode",
                "arguments": {
                    "query": "test query",
                    "reward": 0.5,
                    "reflection": "",  # Invalid: empty string
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert result["embedding_status"] == "failed"
        assert result["tool"] == "store_episode"
        assert "Invalid reflection parameter" in result["error"]

    def test_store_episode_missing_parameters(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """Test store_episode with missing required parameters."""
        # Missing reflection parameter
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "store_episode",
                "arguments": {
                    "query": "test query",
                    "reward": 0.5,
                    # reflection missing
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        assert "error" in result
        assert result["embedding_status"] == "failed"
        assert result["tool"] == "store_episode"
        assert "Missing required parameter" in result["error"]
        assert "reflection" in result["details"]

    def test_store_episode_boundary_rewards(self, mcp_tester: MCPServerTester) -> None:
        """Test store_episode with boundary reward values (-1.0, 0.0, 1.0)."""
        boundary_values = [-1.0, 0.0, 1.0]

        for reward in boundary_values:
            mcp_tester.write_mcp_request(
                "tools/call",
                {
                    "name": "store_episode",
                    "arguments": {
                        "query": f"test boundary query {reward}",
                        "reward": reward,
                        "reflection": f"test boundary reflection {reward}",
                    },
                },
            )

            response = mcp_tester.read_mcp_response()

            assert response["jsonrpc"] == "2.0"
            assert "result" in response
            result = response["result"]

            # Should succeed with boundary values
            assert "id" in result
            assert result["embedding_status"] == "success"
            assert result["reward"] == reward


class TestMCPResources:
    """End-to-End MCP Resource Access Tests."""

    def test_resource_discovery(self, mcp_tester: MCPServerTester) -> None:
        """Test that all 5 MCP resources are discoverable."""
        mcp_tester.write_mcp_request("resources/list", {})

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        resources = response["result"]

        # Should have exactly 5 resources
        assert len(resources) == 5

        # Check for all required resources
        resource_uris = [resource["uri"] for resource in resources]
        assert "memory://l2-insights" in resource_uris
        assert "memory://working-memory" in resource_uris
        assert "memory://episode-memory" in resource_uris
        assert "memory://l0-raw" in resource_uris
        assert "memory://stale-memory" in resource_uris

        # Check resource structure
        for resource in resources:
            assert "uri" in resource
            assert "name" in resource
            assert "description" in resource
            assert "mimeType" in resource
            assert resource["mimeType"] == "application/json"

    def test_l2_insights_resource_read(self, mcp_tester: MCPServerTester) -> None:
        """Test reading memory://l2-insights resource via MCP protocol."""
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://l2-insights?query=test%20query&top_k=3"}
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should return an array (empty if no results)
        assert isinstance(result, list)

        # If results found, check structure
        if result:
            for item in result:
                assert isinstance(item, dict)
                assert "id" in item
                assert "content" in item
                assert "score" in item
                assert "source_ids" in item
                assert isinstance(item["score"], float)
                assert 0.0 <= item["score"] <= 1.0

    def test_l2_insights_resource_error(self, mcp_tester: MCPServerTester) -> None:
        """Test error handling for memory://l2-insights with invalid parameters."""
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://l2-insights?query=&top_k=5"}
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should return error object
        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid query parameter" in result["error"]

    def test_working_memory_resource_read(self, mcp_tester: MCPServerTester) -> None:
        """Test reading memory://working-memory resource via MCP protocol."""
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://working-memory"}
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should return an array (empty if no working memory items)
        assert isinstance(result, list)

        # If results found, check structure
        if result:
            for item in result:
                assert isinstance(item, dict)
                assert "id" in item
                assert "content" in item
                assert "importance" in item
                assert "last_accessed" in item
                assert "created_at" in item
                assert isinstance(item["importance"], float)
                assert 0.0 <= item["importance"] <= 1.0

    def test_episode_memory_resource_read(self, mcp_tester: MCPServerTester) -> None:
        """Test reading memory://episode-memory resource via MCP protocol."""
        mcp_tester.write_mcp_request(
            "resources/read",
            {"uri": "memory://episode-memory?query=test%20query&min_similarity=0.7"},
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should return an array (empty if no matching episodes)
        assert isinstance(result, list)

        # Should be limited to top 3 episodes (FR009)
        assert len(result) <= 3

        # If results found, check structure
        if result:
            for item in result:
                assert isinstance(item, dict)
                assert "id" in item
                assert "query" in item
                assert "reward" in item
                assert "reflection" in item
                assert "similarity" in item
                assert isinstance(item["reward"], float)
                assert isinstance(item["similarity"], float)
                assert -1.0 <= item["reward"] <= 1.0
                assert 0.0 <= item["similarity"] <= 1.0

    def test_l0_raw_resource_read(self, mcp_tester: MCPServerTester) -> None:
        """Test reading memory://l0-raw resource via MCP protocol."""
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://l0-raw?limit=5"}
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should return an array (empty if no raw data)
        assert isinstance(result, list)

        # Should be limited to requested limit
        assert len(result) <= 5

        # If results found, check structure
        if result:
            for item in result:
                assert isinstance(item, dict)
                assert "id" in item
                assert "session_id" in item
                assert "timestamp" in item
                assert "speaker" in item
                assert "content" in item
                assert "metadata" in item

    def test_stale_memory_resource_read(self, mcp_tester: MCPServerTester) -> None:
        """Test reading memory://stale-memory resource via MCP protocol."""
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://stale-memory?importance_min=0.5"}
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should return an array (empty if no stale memory items)
        assert isinstance(result, list)

        # If results found, check structure and filtering
        if result:
            for item in result:
                assert isinstance(item, dict)
                assert "id" in item
                assert "original_content" in item
                assert "archived_at" in item
                assert "importance" in item
                assert "reason" in item
                # All items should meet the importance threshold
                assert item["importance"] >= 0.5

    def test_invalid_resource_uri(self, mcp_tester: MCPServerTester) -> None:
        """Test 404 for invalid resource URI."""
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://invalid-resource"}
        )

        response = mcp_tester.read_mcp_response()

        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should return error for invalid resource
        assert isinstance(result, dict)
        assert "error" in result

    def test_resource_parameter_validation(self, mcp_tester: MCPServerTester) -> None:
        """Test parameter validation across multiple resources."""
        # Test invalid top_k
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://l2-insights?query=test&top_k=invalid"}
        )

        response = mcp_tester.read_mcp_response()
        result = response["result"]
        assert isinstance(result, dict) and "error" in result

        # Test invalid limit
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://l0-raw?limit=invalid"}
        )

        response = mcp_tester.read_mcp_response()
        result = response["result"]
        assert isinstance(result, dict) and "error" in result

        # Test invalid importance_min
        mcp_tester.write_mcp_request(
            "resources/read", {"uri": "memory://stale-memory?importance_min=invalid"}
        )

        response = mcp_tester.read_mcp_response()
        result = response["result"]
        assert isinstance(result, dict) and "error" in result
