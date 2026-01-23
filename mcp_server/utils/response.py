"""
Response metadata helper for MCP tools.

Story 11.4.3: Tool Handler Refactoring
Provides utility function for adding project_id metadata to tool responses.

FR29: All tool responses MUST include project_id in metadata.
Format: {"result": ..., "metadata": {"project_id": "aa"}}
"""

from __future__ import annotations

from typing import Any


def add_response_metadata(result: dict[str, Any], project_id: str) -> dict[str, Any]:
    """Add project_id metadata to a tool response.

    Story 11.4.3: Tool Handler Refactoring
    This helper function adds the required project_id metadata to both success
    and error responses, ensuring FR29 compliance across all MCP tools.

    Args:
        result: The tool result dict (success or error response). Will be modified in-place.
        project_id: The current project ID from context (obtained via get_current_project()).

    Returns:
        The same result dict with metadata added (modified in-place for convenience).

    Example:
        from mcp_server.middleware.context import get_current_project
        from mcp_server.utils.response import add_response_metadata

        async def handle_tool(arguments: dict) -> dict:
            project_id = get_current_project()
            data = await some_operation()
            response = {"result": data, "status": "success"}
            return add_response_metadata(response, project_id)

    Example (error case):
        async def handle_tool(arguments: dict) -> dict:
            try:
                project_id = get_current_project()
                # ... operation ...
            except Exception as e:
                response = {"error": str(e), "details": "Operation failed"}
                return add_response_metadata(response, project_id)
    """
    result["metadata"] = {"project_id": project_id}
    return result
