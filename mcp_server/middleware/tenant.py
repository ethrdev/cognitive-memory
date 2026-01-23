"""
TenantMiddleware for project context extraction and validation.

Story 11.4.1: FastMCP Migration und Middleware-Infrastruktur

Extracts project_id from HTTP headers or stdio _meta, validates against
project_registry, and sets RLS context for tenant isolation.
"""

from __future__ import annotations

import logging
from typing import Any

import mcp.types as mt
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

from mcp_server.middleware.context import (
    allowed_projects_context,
    project_context,
)

logger = logging.getLogger(__name__)


class TenantMiddleware(Middleware):
    """
    Extracts project context from HTTP headers or stdio _meta.

    For HTTP transport (production):
    - Extracts X-Project-ID header
    - Falls back to query parameter if needed

    For stdio transport (development):
    - Extracts from _meta.project_id in request arguments

    Validation:
    - Validates project_id against registered projects (stub for Story 11.4.2)
    - Sets contextvars for downstream access
    """

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, Any],
    ) -> Any:
        """Extract project context before tool execution."""
        # Extract project_id from transport-specific location
        project_id = await self._extract_project_id(context)

        # Validate against registry (stub for Story 11.4.2)
        # For now, just extract and set context
        # TODO: Story 11.4.2 will implement full validation
        # if not await self._validate_project(project_id):
        #     raise ValueError(f"Unknown project: {project_id}")

        # Set contextvars for downstream access
        project_context.set(project_id)

        logger.debug(f"TenantMiddleware: Set project_id={project_id}")

        # Continue to tool handler
        return await call_next(context)

    async def _extract_project_id(
        self, context: MiddlewareContext[mt.CallToolRequestParams]
    ) -> str:
        """
        Hybrid extraction: HTTP header > _meta > Error

        Args:
            context: The middleware context containing request information

        Returns:
            The extracted project ID

        Raises:
            ValueError: If no project context can be found
        """
        # Try HTTP header first (production)
        try:
            headers = get_http_headers()
            if project_id := headers.get("x-project-id"):
                logger.debug(f"Extracted project_id from HTTP header: {project_id}")
                return project_id
        except RuntimeError:
            # No HTTP request context - fall through to stdio handling
            pass

        # Try _meta from arguments (stdio development)
        # In FastMCP 3.x, arguments are in context.message.params.arguments
        if hasattr(context, "message") and hasattr(context.message, "params"):
            arguments = context.message.params.arguments or {}
            if meta := arguments.get("_meta", {}):
                if project_id := meta.get("project_id"):
                    logger.debug(f"Extracted project_id from _meta: {project_id}")
                    return project_id

        # No context found - strict error (Decision 1 from Story 11.4.1)
        raise ValueError(
            "Missing project context. Provide X-Project-ID header (HTTP) "
            "or _meta.project_id (stdio)."
        )

    async def _validate_project(self, project_id: str) -> bool:
        """
        Validate project_id against registered projects.

        Story 11.4.2: Project Context Validation

        Args:
            project_id: The project identifier to validate

        Returns:
            True if project is registered and accessible, False otherwise
        """
        # TODO: Story 11.4.2 will implement this
        # For now, accept any project_id
        return True
