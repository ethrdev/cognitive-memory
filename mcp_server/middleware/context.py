"""
Request-scoped context variables for tenant isolation.

Story 11.4.1: FastMCP Migration und Middleware-Infrastruktur

Uses Python contextvars to ensure thread-safe, request-scoped data
that is automatically isolated between concurrent requests.
"""

import contextvars
from typing import Any

# Request-scoped context for project_id
# This ContextVar holds the current project identifier for the request
project_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "project_id",
    default=None,
)

# Request-scoped context for allowed projects list
# This ContextVar holds the list of projects the current request can access
allowed_projects_context: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar(
    "allowed_projects",
    default=None,
)


def get_project_id() -> str | None:
    """Get the current project ID from context.

    Returns:
        The project ID for the current request, or None if not set.
    """
    return project_context.get()


def set_project_id(project_id: str) -> None:
    """Set the project ID for the current request.

    Args:
        project_id: The project identifier to set.
    """
    project_context.set(project_id)


def get_allowed_projects() -> list[str] | None:
    """Get the list of allowed projects for the current request.

    Returns:
        List of project IDs the request can access, or None if not set.
    """
    return allowed_projects_context.get()


def set_allowed_projects(projects: list[str]) -> None:
    """Set the list of allowed projects for the current request.

    Args:
        projects: List of project identifiers the request can access.
    """
    allowed_projects_context.set(projects)


def clear_context() -> None:
    """Clear all request-scoped context variables.

    This is primarily used for testing and ensuring isolation between test cases.
    In normal operation, FastMCP handles context cleanup automatically.
    """
    project_context.set(None)
    allowed_projects_context.set(None)
