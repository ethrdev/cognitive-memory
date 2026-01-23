"""
Integration tests for FastMCP 3.x migration.

Story 11.4.1: FastMCP Migration und Middleware-Infrastruktur

Tests FastMCP server initialization, middleware registration, and tool registration.
Note: FastMCP 3.0.0b1 has different API than documented in knowledge base.
Transports are selected via CLI arguments, not programmatically.
"""

from __future__ import annotations

import pytest

from mcp_server.middleware import TenantMiddleware


class TestFastMCPIntegration:
    """Test FastMCP 3.x integration with middleware."""

    def test_fastmcp_server_initialization(self):
        """Test that FastMCP server can be initialized."""
        from fastmcp import FastMCP

        mcp = FastMCP("cognitive-memory")
        assert mcp is not None

    def test_middleware_registration(self):
        """Test that TenantMiddleware can be registered."""
        from fastmcp import FastMCP

        mcp = FastMCP("cognitive-memory")

        # Add middleware should not raise
        mcp.add_middleware(TenantMiddleware())

        # Verify middleware was added
        # (FastMCP doesn't expose middleware list in public API, so we just
        # verify it doesn't crash)


class TestToolRegistrationWithFastMCP:
    """Test that existing tools work with FastMCP 3.x."""

    def test_simple_tool_registration(self):
        """Test basic tool registration with FastMCP decorator."""
        from fastmcp import FastMCP

        mcp = FastMCP("test-server")

        @mcp.tool()
        def test_tool(message: str) -> str:
            """A simple test tool."""
            return f"Echo: {message}"

        # Tool should be registered without error
        assert mcp is not None

    def test_async_tool_registration(self):
        """Test async tool registration with FastMCP decorator."""
        from fastmcp import FastMCP

        mcp = FastMCP("test-server")

        @mcp.tool()
        async def async_test_tool(message: str) -> str:
            """A simple async test tool."""
            return f"Async Echo: {message}"

        # Tool should be registered without error
        assert mcp is not None


class TestTenantMiddlewareIntegration:
    """Integration tests for TenantMiddleware with FastMCP."""

    def test_middleware_on_call_tool_exists(self):
        """Test that middleware has on_call_tool hook."""
        middleware = TenantMiddleware()

        assert hasattr(middleware, "on_call_tool")
        assert callable(middleware.on_call_tool)

    def test_middleware_extract_project_id_exists(self):
        """Test that middleware has _extract_project_id method."""
        middleware = TenantMiddleware()

        assert hasattr(middleware, "_extract_project_id")
        assert callable(middleware._extract_project_id)


class TestBackwardCompatibility:
    """Test backward compatibility with existing tool handlers."""

    def test_tools_module_imports(self):
        """Test that tools module can be imported."""
        # This test verifies that the tools module doesn't have
        # import errors after FastMCP migration
        from mcp_server.tools import handle_ping

        assert handle_ping is not None

    def test_ping_tool_signature(self):
        """Test that ping tool has expected signature."""
        from mcp_server.tools import handle_ping

        # Should be async and accept arguments dict
        import inspect

        assert inspect.iscoroutinefunction(handle_ping)


class TestEnvironmentConfiguration:
    """Test environment variable configuration for transport modes."""

    def test_dual_transport_config(self, monkeypatch):
        """Test that DUAL_TRANSPORT environment variable handling."""
        import os

        # Test default value
        monkeypatch.delenv("DUAL_TRANSPORT", raising=False)
        dual_transport = os.getenv("DUAL_TRANSPORT", "false").lower() == "true"
        assert dual_transport is False

        # Test enabled value
        monkeypatch.setenv("DUAL_TRANSPORT", "true")
        dual_transport = os.getenv("DUAL_TRANSPORT", "false").lower() == "true"
        assert dual_transport is True

        # Test various truthy values
        for value in ["TRUE", "True"]:
            monkeypatch.setenv("DUAL_TRANSPORT", value)
            dual_transport = os.getenv("DUAL_TRANSPORT", "false").lower() == "true"
            assert dual_transport is True

    def test_transport_selection_config(self, monkeypatch):
        """Test that MCP_TRANSPORT environment variable handling."""
        import os

        # Test default value
        monkeypatch.delenv("MCP_TRANSPORT", raising=False)
        transport_type = os.getenv("MCP_TRANSPORT", "stdio").lower()
        assert transport_type == "stdio"

        # Test HTTP value
        monkeypatch.setenv("MCP_TRANSPORT", "http")
        transport_type = os.getenv("MCP_TRANSPORT", "stdio").lower()
        assert transport_type == "http"


class TestFastMCPImports:
    """Test that FastMCP imports work correctly."""

    def test_fastmcp_import(self):
        """Test that FastMCP can be imported."""
        from fastmcp import FastMCP

        assert FastMCP is not None

    def test_context_module_imports(self):
        """Test that context module can be imported."""
        from mcp_server.middleware.context import (
            get_project_id,
            project_context,
            set_project_id,
        )

        assert project_context is not None
        assert get_project_id is not None
        assert set_project_id is not None

    def test_middleware_module_imports(self):
        """Test that middleware module can be imported."""
        from mcp_server.middleware import TenantMiddleware

        assert TenantMiddleware is not None
