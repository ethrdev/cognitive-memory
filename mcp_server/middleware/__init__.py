"""
MCP Server Middleware Module

Story 11.4.1: FastMCP Migration und Middleware-Infrastruktur

This module provides middleware components for project context extraction and validation.
"""

from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import (
    CallNext,
    Middleware,
    MiddlewareContext,
)

from mcp_server.middleware.context import project_context, allowed_projects_context
from mcp_server.middleware.tenant import TenantMiddleware

__all__ = [
    "TenantMiddleware",
    "project_context",
    "allowed_projects_context",
    "CallNext",
    "Middleware",
    "MiddlewareContext",
]
