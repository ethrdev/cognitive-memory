"""
Unit tests for get_current_project() context helper.

Story 11.4.3: Tool Handler Refactoring - Tests for get_current_project() function.
Tests that RuntimeError is raised when project context is not set (middleware bypass).
"""

import pytest

from mcp_server.middleware.context import (
    clear_context,
    get_current_project,
    set_project_id,
)


class TestGetCurrentProject:
    """Tests for get_current_project() function."""

    def test_get_current_project_returns_project_id_when_set(self):
        """Test that get_current_project() returns project_id when context is set."""
        # Arrange
        expected_project_id = "test-project-aa"
        set_project_id(expected_project_id)

        # Act
        result = get_current_project()

        # Assert
        assert result == expected_project_id

        # Cleanup
        clear_context()

    def test_get_current_project_raises_runtime_error_when_not_set(self):
        """Test that get_current_project() raises RuntimeError when context is not set."""
        # Arrange - Clear context to simulate middleware bypass
        clear_context()

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            get_current_project()

        assert "No project context available" in str(exc_info.value)
        assert "TenantMiddleware" in str(exc_info.value)

    def test_get_current_project_raises_runtime_error_when_set_to_none(self):
        """Test that get_current_project() raises RuntimeError when context is None."""
        # Arrange
        set_project_id("test-project")
        clear_context()  # Set to None

        # Act & Assert
        with pytest.raises(RuntimeError) as exc_info:
            get_current_project()

        assert "No project context available" in str(exc_info.value)

    def test_get_current_project_returns_correct_project_after_multiple_sets(self):
        """Test that get_current_project() returns the most recently set project_id."""
        # Arrange
        set_project_id("project-1")
        set_project_id("project-2")
        set_project_id("project-3")

        # Act
        result = get_current_project()

        # Assert
        assert result == "project-3"

        # Cleanup
        clear_context()
