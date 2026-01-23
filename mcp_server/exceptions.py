"""
Custom exceptions for Cognitive Memory MCP Server.

Story 11.4.2: Project Context Validation

Defines domain-specific exceptions for project validation and RLS context errors.
"""


class ProjectNotFoundError(ValueError):
    """
    Raised when a project_id is not found in the project_registry.

    Error Code: ERR_PROJECT_NOT_FOUND

    This exception indicates that the provided project_id does not exist
    in the project_registry table. The middleware will raise this before
    any database operations are performed with the invalid project context.

    Attributes:
        project_id: The invalid project identifier
        message: Human-readable error message

    Example:
        raise ProjectNotFoundError("unknown-project")
        # ValueError: Unknown project: unknown-project
    """

    def __init__(self, project_id: str) -> None:
        """
        Initialize ProjectNotFoundError.

        Args:
            project_id: The invalid project identifier
        """
        self.project_id = project_id
        self.message = f"Unknown project: {project_id}"
        super().__init__(self.message)


class ProjectContextRequiredError(ValueError):
    """
    Raised when project context is required but not provided.

    Error Code: ERR_PROJECT_CONTEXT_REQUIRED

    This exception indicates that a tool call requires project context
    (project_id) but none was provided via HTTP headers or _meta.

    Attributes:
        message: Human-readable error message with instructions

    Example:
        raise ProjectContextRequiredError()
        # ValueError: Missing project context. Provide X-Project-ID header (HTTP)
        # or _meta.project_id (stdio).
    """

    def __init__(self) -> None:
        """Initialize ProjectContextRequiredError."""
        self.message = (
            "Missing project context. Provide X-Project-ID header (HTTP) "
            "or _meta.project_id (stdio)."
        )
        super().__init__(self.message)


class RLSContextError(RuntimeError):
    """
    Raised when RLS context cannot be set or is invalid.

    Error Code: ERR_RLS_CONTEXT

    This exception indicates a failure in setting RLS session variables
    or validating the RLS context for a connection.

    Attributes:
        reason: The specific reason for the RLS context error
        message: Human-readable error message

    Example:
        raise RLSContextError("Failed to set app.current_project")
    """

    def __init__(self, reason: str) -> None:
        """
        Initialize RLSContextError.

        Args:
            reason: The specific reason for the RLS context error
        """
        self.reason = reason
        self.message = f"RLS context error: {reason}"
        super().__init__(self.message)
