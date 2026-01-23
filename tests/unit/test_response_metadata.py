"""
Unit tests for response metadata helper function.

Story 11.4.3: Tool Handler Refactoring - Tests for add_response_metadata() function.
Tests that project_id metadata is correctly added to success and error responses.
"""

import pytest

from mcp_server.utils.response import add_response_metadata


class TestAddResponseMetadata:
    """Tests for add_response_metadata() function."""

    def test_add_metadata_to_success_response(self):
        """Test that metadata is added to a successful response."""
        # Arrange
        result = {"data": {"key": "value"}, "status": "success"}
        project_id = "test-project-aa"

        # Act
        response = add_response_metadata(result, project_id)

        # Assert
        assert response == result  # Returns modified original dict
        assert "metadata" in response
        assert response["metadata"]["project_id"] == project_id

    def test_add_metadata_to_error_response(self):
        """Test that metadata is added to an error response."""
        # Arrange
        result = {"error": "Something went wrong", "details": "Error details"}
        project_id = "test-project-bb"

        # Act
        response = add_response_metadata(result, project_id)

        # Assert
        assert "metadata" in response
        assert response["metadata"]["project_id"] == project_id
        # Original error fields preserved
        assert response["error"] == "Something went wrong"
        assert response["details"] == "Error details"

    def test_add_metadata_overwrites_existing_metadata(self):
        """Test that existing metadata field is overwritten."""
        # Arrange
        result = {"data": "value", "metadata": {"old": "data"}}
        project_id = "test-project-cc"

        # Act
        response = add_response_metadata(result, project_id)

        # Assert
        assert response["metadata"]["project_id"] == project_id
        assert "old" not in response["metadata"]

    def test_add_metadata_to_empty_dict(self):
        """Test that metadata is added to an empty dict."""
        # Arrange
        result = {}
        project_id = "test-project-dd"

        # Act
        response = add_response_metadata(result, project_id)

        # Assert
        assert response["metadata"]["project_id"] == project_id

    def test_add_metadata_returns_same_dict_object(self):
        """Test that the same dict object is returned (modified in-place)."""
        # Arrange
        result = {"data": "value"}
        project_id = "test-project-ee"

        # Act
        response = add_response_metadata(result, project_id)

        # Assert - Same object returned
        assert response is result

    def test_add_metadata_with_complex_response(self):
        """Test metadata addition to a complex nested response."""
        # Arrange
        result = {
            "neighbors": [
                {"node_id": 1, "label": "Node1"},
                {"node_id": 2, "label": "Node2"},
            ],
            "start_node": {"node_id": 1, "label": "Start"},
            "query_params": {"depth": 2, "direction": "both"},
            "execution_time_ms": 45.5,
            "neighbor_count": 2,
            "status": "success",
        }
        project_id = "project-ff"

        # Act
        response = add_response_metadata(result, project_id)

        # Assert
        assert response["metadata"]["project_id"] == project_id
        # All other fields preserved
        assert response["neighbor_count"] == 2
        assert response["status"] == "success"

    def test_add_metadata_preserves_all_original_keys(self):
        """Test that all original keys are preserved when adding metadata."""
        # Arrange
        result = {
            "key1": "value1",
            "key2": 123,
            "key3": None,
            "key4": [1, 2, 3],
            "key5": {"nested": "dict"},
        }
        project_id = "project-gg"

        # Act
        response = add_response_metadata(result, project_id)

        # Assert
        assert response["key1"] == "value1"
        assert response["key2"] == 123
        assert response["key3"] is None
        assert response["key4"] == [1, 2, 3]
        assert response["key5"] == {"nested": "dict"}
        assert "metadata" in response
        assert len(response) == 6  # 5 original keys + metadata

    def test_add_metadata_with_unicode_project_id(self):
        """Test metadata with unicode project_id."""
        # Arrange
        result = {"data": "value"}
        project_id = "project-ünïcödë-测试"

        # Act
        response = add_response_metadata(result, project_id)

        # Assert
        assert response["metadata"]["project_id"] == project_id
