"""
TenantMiddleware for project context extraction and validation.

Story 11.4.1: FastMCP Migration und Middleware-Infrastruktur
Story 11.4.2: Project Context Validation and RLS Integration

Extracts project_id from HTTP headers or stdio _meta, validates against
project_registry, and sets RLS context for tenant isolation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import mcp.types as mt
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext

from mcp_server.exceptions import (
    ProjectContextRequiredError,
    ProjectNotFoundError,
)
from mcp_server.middleware.context import project_context

logger = logging.getLogger(__name__)


@dataclass
class ProjectMetadata:
    """
    Validated project metadata from project_registry.

    Attributes:
        project_id: The project identifier
        access_level: Access level (super/shared/isolated)
        name: Human-readable project name
    """

    project_id: str
    access_level: str
    name: str


class TenantMiddleware(Middleware):
    """
    Extracts project context from HTTP headers or stdio _meta.

    For HTTP transport (production):
    - Extracts X-Project-ID header
    - Falls back to query parameter if needed

    For stdio transport (development):
    - Extracts from _meta.project_id in request arguments

    Validation (Story 11.4.2):
    - Validates project_id against project_registry table
    - Caches validation result per request
    - Stores project metadata (access_level) in contextvar for downstream use
    - Sets contextvars for downstream access
    """

    # Per-request validation cache (instance variable, auto-cleared per request)
    _validation_cache: dict[str, ProjectMetadata]

    def __init__(self) -> None:
        """Initialize TenantMiddleware with empty validation cache."""
        self._validation_cache = {}

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, Any],
    ) -> Any:
        """Extract and validate project context before tool execution."""
        # Clear cache at start of each request (FastMCP creates new instance per request)
        self._validation_cache.clear()

        # Extract project_id from transport-specific location
        project_id = await self._extract_project_id(context)

        # Validate against registry and get metadata
        try:
            metadata = await self._validate_project(project_id)

            # Set contextvars for downstream access
            project_context.set(metadata.project_id)

            logger.debug(
                f"TenantMiddleware: Validated and set project_id={metadata.project_id}, "
                f"access_level={metadata.access_level}"
            )

            # Continue to tool handler
            return await call_next(context)

        except ProjectNotFoundError as e:
            # Map to HTTP 400 response
            logger.warning(f"Project validation failed: {e.message}")
            raise mt.JsonRpcError(
                code=mt.ErrorCode.InvalidParams,
                message=e.message,
                data={"error_code": "ERR_PROJECT_NOT_FOUND", "project_id": e.project_id}
            ) from e

        except ProjectContextRequiredError as e:
            # Map to HTTP 400 response
            logger.warning(f"Project context missing: {e.message}")
            raise mt.JsonRpcError(
                code=mt.ErrorCode.InvalidParams,
                message=e.message,
                data={"error_code": "ERR_PROJECT_CONTEXT_REQUIRED"}
            ) from e

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

    async def _validate_project(self, project_id: str) -> ProjectMetadata:
        """
        Validate project_id against registered projects.

        Story 11.4.2: Project Context Validation

        Queries the project_registry table to validate the project exists
        and retrieves its metadata. Results are cached per-request to avoid
        redundant database queries within the same tool call.

        Args:
            project_id: The project identifier to validate

        Returns:
            ProjectMetadata containing project_id, access_level, and name

        Raises:
            ProjectNotFoundError: If project_id is not in project_registry
        """
        # Check cache first (per-request caching)
        if project_id in self._validation_cache:
            logger.debug(f"Project validation cache hit for {project_id}")
            return self._validation_cache[project_id]

        # Import here to avoid circular dependency
        from mcp_server.db.connection import get_connection_sync

        try:
            with get_connection_sync() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT project_id, access_level, name
                    FROM project_registry
                    WHERE project_id = %s
                    """,
                    (project_id,),
                )
                result = cursor.fetchone()

                if result is None:
                    logger.warning(f"Project not found in registry: {project_id}")
                    raise ProjectNotFoundError(project_id)

                metadata = ProjectMetadata(
                    project_id=result["project_id"],
                    access_level=result["access_level"],
                    name=result["name"],
                )

                # Cache result for this request
                self._validation_cache[project_id] = metadata

                logger.debug(
                    f"Project validated: {project_id} (access_level={metadata.access_level})"
                )
                return metadata

        except ProjectNotFoundError:
            # Re-raise our custom exception
            raise
        except Exception as e:
            logger.error(f"Database error during project validation: {e}")
            # Treat database errors as validation failures for security
            raise ProjectNotFoundError(project_id) from e
