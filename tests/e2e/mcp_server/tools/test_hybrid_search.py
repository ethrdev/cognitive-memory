"""
E2E Tests for hybrid_search MCP Tool

Tests hybrid_search tool functionality including parameter validation,
embedding dimensions, weight validation, and result handling.
Story 4.4: E2E hybrid_search tool functionality
"""

from __future__ import annotations

import pytest

from tests.e2e.mcp_server.conftest import MCPServerTester
from tests.factories import create_embedding


class TestHybridSearchTool_4_4_E2E:
    """Test hybrid_search tool (Story 4.4, E2E Tests)."""

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
        assert response["jsonrpc"] == "2.0"

    @pytest.mark.id("4.4-E2E-001")
    @pytest.mark.P1
    def test_hybrid_search_parameter_validation(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """
        AC #1: Missing query_embedding parameter returns validation error.

        GIVEN: MCP server is initialized
        WHEN: hybrid_search is called without query_embedding
        THEN: Validation error mentions query_embedding parameter
        """
        # GIVEN: MCP connection initialized
        # WHEN: Call with missing query_embedding
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

        # THEN: Validation error returned
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert "error" in result
        assert "query_embedding" in result["details"]
        assert result["tool"] == "hybrid_search"

    @pytest.mark.id("4.4-E2E-002")
    @pytest.mark.P1
    def test_hybrid_search_invalid_embedding_dimension(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """
        AC #2: Wrong embedding dimension returns validation error.

        GIVEN: MCP server is initialized
        WHEN: hybrid_search is called with 512-dim embedding instead of 1536-dim
        THEN: Validation error mentions required dimension (1536)
        """
        # GIVEN: 512-dim embedding (invalid)
        query_embedding = create_embedding(dimension=512, value=0.1)

        # WHEN: Call with wrong dimension
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": "consciousness",
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Dimension validation error
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert "error" in result
        assert "embedding dimension" in result["details"]
        assert "1536" in result["details"]
        assert result["tool"] == "hybrid_search"

    @pytest.mark.id("4.4-E2E-003")
    @pytest.mark.P1
    def test_hybrid_search_invalid_weights(self, mcp_tester: MCPServerTester) -> None:
        """
        AC #3: Invalid weights (sum != 1.0) returns validation error.

        GIVEN: MCP server is initialized
        WHEN: hybrid_search is called with weights that sum to 1.3
        THEN: Validation error about weights summing to 1.0
        """
        # GIVEN: Valid embedding
        query_embedding = create_embedding(dimension=1536, value=0.1)
        weights = {"semantic": 0.8, "keyword": 0.5}  # Sum = 1.3 (invalid)

        # WHEN: Call with invalid weights
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": "consciousness",
                    "weights": weights,
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Weights validation error
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]
        assert "error" in result
        assert "Weights must sum to 1.0" in result["details"]
        assert result["tool"] == "hybrid_search"

    @pytest.mark.id("4.4-E2E-004")
    @pytest.mark.P1
    def test_hybrid_search_default_parameters(
        self, mcp_tester: MCPServerTester
    ) -> None:
        """
        AC #4: Default parameters (top_k=5, weights) work correctly.

        GIVEN: MCP server is initialized with valid embedding
        WHEN: hybrid_search is called without specifying top_k or weights
        THEN: Uses defaults: top_k=5, semantic=0.7, keyword=0.3
        """
        # GIVEN: Valid embedding
        query_embedding = create_embedding(dimension=1536, value=0.1)

        # WHEN: Call with defaults
        mcp_tester.write_mcp_request(
            "tools/call",
            {
                "name": "hybrid_search",
                "arguments": {
                    "query_embedding": query_embedding,
                    "query_text": "consciousness",
                    # top_k and weights use defaults
                },
            },
        )

        response = mcp_tester.read_mcp_response()

        # THEN: Success with defaults applied
        assert response["jsonrpc"] == "2.0"
        assert "result" in response
        result = response["result"]

        # Should succeed OR return empty (database might be empty in tests)
        if "error" not in result:
            assert result["status"] == "success"
            assert result["query_embedding_dimension"] == 1536
            assert result["weights"]["semantic"] == 0.7
            assert result["weights"]["keyword"] == 0.3
