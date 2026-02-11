"""
Unit tests for filter validation utilities.

Story 9.3.1: Filter parameter validation tests.
"""

from datetime import datetime

from mcp_server.utils.filter_validation import (
    ALLOWED_SOURCE_TYPES,
    should_include_source_type,
    validate_filter_params,
)


class TestValidateFilterParams:
    """Tests for validate_filter_params function."""

    def test_valid_no_filters(self):
        """Test validation passes with no filters."""
        result = validate_filter_params()
        assert result["status"] == "validation_passed"

    def test_valid_tags_filter_only(self):
        """Test validation passes with tags_filter only."""
        result = validate_filter_params(tags_filter=["python", "testing"])
        assert result["status"] == "validation_passed"

    def test_valid_date_range(self):
        """Test validation passes with valid date range."""
        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 12, 31)
        result = validate_filter_params(date_from=date_from, date_to=date_to)
        assert result["status"] == "validation_passed"

    def test_valid_source_type_filter(self):
        """Test validation passes with valid source types."""
        result = validate_filter_params(
            source_type_filter=["l2_insight", "episode_memory"]
        )
        assert result["status"] == "validation_passed"

    def test_valid_combined_filters(self):
        """Test validation passes with all valid filters combined."""
        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 12, 31)
        result = validate_filter_params(
            tags_filter=["python"],
            date_from=date_from,
            date_to=date_to,
            source_type_filter=["l2_insight"],
        )
        assert result["status"] == "validation_passed"

    def test_invalid_date_range(self):
        """Test validation fails when date_from > date_to."""
        date_from = datetime(2024, 12, 31)
        date_to = datetime(2024, 1, 1)
        result = validate_filter_params(date_from=date_from, date_to=date_to)
        assert "error" in result
        assert "date_from must be <= date_to" in result["details"]

    def test_invalid_source_type(self):
        """Test validation fails with invalid source type."""
        result = validate_filter_params(source_type_filter=["invalid_type"])
        assert "error" in result
        assert "Invalid source types" in result["details"]

    def test_multiple_invalid_source_types(self):
        """Test validation fails with multiple invalid source types."""
        result = validate_filter_params(
            source_type_filter=["invalid_type1", "invalid_type2"]
        )
        assert "error" in result
        assert "Invalid source types" in result["details"]

    def test_tags_filter_must_be_list(self):
        """Test validation fails when tags_filter is not a list."""
        result = validate_filter_params(tags_filter="not_a_list")  # type: ignore
        assert "error" in result
        assert "tags_filter must be a list" in result["details"]

    def test_tags_filter_items_must_be_strings(self):
        """Test validation fails when tags_filter contains non-strings."""
        result = validate_filter_params(tags_filter=["valid", 123, "also_valid"])  # type: ignore
        assert "error" in result
        assert "All items in tags_filter must be strings" in result["details"]

    def test_source_type_filter_must_be_list(self):
        """Test validation fails when source_type_filter is not a list."""
        result = validate_filter_params(source_type_filter="not_a_list")  # type: ignore
        assert "error" in result
        assert "source_type_filter must be a list" in result["details"]

    def test_all_valid_source_types(self):
        """Test all allowed source types are valid."""
        for source_type in ALLOWED_SOURCE_TYPES:
            result = validate_filter_params(source_type_filter=[source_type])
            assert result["status"] == "validation_passed"

    def test_empty_filter_lists_are_valid(self):
        """Test empty filter lists are valid (will return no results)."""
        result = validate_filter_params(
            tags_filter=[],
            source_type_filter=[],
        )
        # Empty lists are structurally valid - business logic handles empty results
        assert result["status"] == "validation_passed"

    def test_none_date_values_are_valid(self):
        """Test None values for dates are valid (no date filter applied)."""
        result = validate_filter_params(
            date_from=None,
            date_to=None,
        )
        assert result["status"] == "validation_passed"

    def test_partial_date_range_valid(self):
        """Test partial date ranges are valid."""
        # Only date_from
        result1 = validate_filter_params(date_from=datetime(2024, 1, 1))
        assert result1["status"] == "validation_passed"

        # Only date_to
        result2 = validate_filter_params(date_to=datetime(2024, 12, 31))
        assert result2["status"] == "validation_passed"


class TestShouldIncludeSourceType:
    """Tests for should_include_source_type function."""

    def test_include_when_no_filter(self):
        """Test all sources included when no filter applied."""
        assert should_include_source_type("l2_insight", None) is True
        assert should_include_source_type("episode_memory", None) is True
        assert should_include_source_type("graph", None) is True

    def test_include_when_in_filter(self):
        """Test source included when in filter list."""
        filter_list = ["l2_insight", "episode_memory"]
        assert should_include_source_type("l2_insight", filter_list) is True
        assert should_include_source_type("episode_memory", filter_list) is True

    def test_exclude_when_not_in_filter(self):
        """Test source excluded when not in filter list."""
        filter_list = ["l2_insight"]
        assert should_include_source_type("l2_insight", filter_list) is True
        assert should_include_source_type("episode_memory", filter_list) is False
        assert should_include_source_type("graph", filter_list) is False

    def test_single_source_filter(self):
        """Test filtering to single source type."""
        filter_list = ["l2_insight"]
        assert should_include_source_type("l2_insight", filter_list) is True
        assert should_include_source_type("episode_memory", filter_list) is False
        assert should_include_source_type("graph", filter_list) is False

    def test_all_sources_in_filter(self):
        """Test all sources included when filter contains all types."""
        filter_list = list(ALLOWED_SOURCE_TYPES)
        for source_type in ALLOWED_SOURCE_TYPES:
            assert should_include_source_type(source_type, filter_list) is True
