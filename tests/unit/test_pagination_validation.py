"""
Unit Tests for Pagination Validation Utilities

Tests for Story 9.2.3: pagination-validation.
Covers all edge cases for pagination parameter validation.

Author: Epic 9 Implementation
Story: 9.2.3 - pagination-validation
"""

import pytest

from mcp_server.utils.pagination import (
    validate_pagination_params,
    calculate_next_offset,
    has_next_page,
    build_pagination_response,
    validate_limit_only,
    validate_offset_only,
    LimitValidationError,
    OffsetValidationError,
    ERR_LIMIT_TYPE,
    ERR_LIMIT_RANGE,
    ERR_LIMIT_ZERO,
    ERR_OFFSET_TYPE,
    ERR_OFFSET_NEGATIVE,
    DEFAULT_LIMIT,
    DEFAULT_OFFSET,
)


# =============================================================================
# validate_pagination_params Tests
# =============================================================================

class TestValidatePaginationParams:
    """Test suite for validate_pagination_params function."""

    def test_default_values(self):
        """Test default limit and offset when None is passed."""
        result = validate_pagination_params()

        assert result["is_valid"] is True
        assert result["error"] is None
        assert result["limit"] == DEFAULT_LIMIT
        assert result["offset"] == DEFAULT_OFFSET

    def test_custom_limit_and_offset(self):
        """Test custom limit and offset values."""
        result = validate_pagination_params(limit=25, offset=10)

        assert result["is_valid"] is True
        assert result["limit"] == 25
        assert result["offset"] == 10

    def test_limit_minimum_boundary(self):
        """Test limit = 1 is valid (minimum allowed)."""
        result = validate_pagination_params(limit=1, offset=0)

        assert result["is_valid"] is True
        assert result["limit"] == 1

    def test_limit_maximum_boundary(self):
        """Test limit = 100 is valid (maximum allowed)."""
        result = validate_pagination_params(limit=100, offset=0)

        assert result["is_valid"] is True
        assert result["limit"] == 100

    def test_limit_zero_raises_error(self):
        """Test limit = 0 raises validation error."""
        with pytest.raises(LimitValidationError) as exc_info:
            validate_pagination_params(limit=0, offset=0)

        assert ERR_LIMIT_ZERO in str(exc_info.value)

    def test_limit_zero_allowed_with_flag(self):
        """Test limit = 0 is allowed when allow_zero_limit=True."""
        result = validate_pagination_params(limit=0, offset=0, allow_zero_limit=True)

        assert result["is_valid"] is True
        assert result["limit"] == 0

    def test_limit_negative_raises_error(self):
        """Test negative limit raises validation error."""
        with pytest.raises(LimitValidationError) as exc_info:
            validate_pagination_params(limit=-1, offset=0)

        assert ERR_LIMIT_RANGE in str(exc_info.value)

    def test_limit_exceeds_maximum_raises_error(self):
        """Test limit > 100 raises validation error."""
        with pytest.raises(LimitValidationError) as exc_info:
            validate_pagination_params(limit=101, offset=0)

        assert ERR_LIMIT_RANGE in str(exc_info.value)

    def test_limit_far_exceeds_maximum_raises_error(self):
        """Test limit >> 100 raises validation error."""
        with pytest.raises(LimitValidationError) as exc_info:
            validate_pagination_params(limit=1000, offset=0)

        assert ERR_LIMIT_RANGE in str(exc_info.value)

    def test_limit_not_integer_raises_error(self):
        """Test non-integer limit raises validation error."""
        with pytest.raises(LimitValidationError) as exc_info:
            validate_pagination_params(limit="50", offset=0)

        assert ERR_LIMIT_TYPE in str(exc_info.value)

    def test_limit_float_raises_error(self):
        """Test float limit raises validation error."""
        with pytest.raises(LimitValidationError) as exc_info:
            validate_pagination_params(limit=50.5, offset=0)

        assert ERR_LIMIT_TYPE in str(exc_info.value)

    def test_offset_zero_is_valid(self):
        """Test offset = 0 is valid (minimum allowed)."""
        result = validate_pagination_params(limit=50, offset=0)

        assert result["is_valid"] is True
        assert result["offset"] == 0

    def test_offset_positive_is_valid(self):
        """Test positive offset is valid."""
        result = validate_pagination_params(limit=50, offset=100)

        assert result["is_valid"] is True
        assert result["offset"] == 100

    def test_offset_negative_raises_error(self):
        """Test negative offset raises validation error."""
        with pytest.raises(OffsetValidationError) as exc_info:
            validate_pagination_params(limit=50, offset=-1)

        assert ERR_OFFSET_NEGATIVE in str(exc_info.value)

    def test_offset_far_negative_raises_error(self):
        """Test far negative offset raises validation error."""
        with pytest.raises(OffsetValidationError) as exc_info:
            validate_pagination_params(limit=50, offset=-100)

        assert ERR_OFFSET_NEGATIVE in str(exc_info.value)

    def test_offset_not_integer_raises_error(self):
        """Test non-integer offset raises validation error."""
        with pytest.raises(OffsetValidationError) as exc_info:
            validate_pagination_params(limit=50, offset="10")

        assert ERR_OFFSET_TYPE in str(exc_info.value)

    def test_offset_float_raises_error(self):
        """Test float offset raises validation error."""
        with pytest.raises(OffsetValidationError) as exc_info:
            validate_pagination_params(limit=50, offset=10.5)

        assert ERR_OFFSET_TYPE in str(exc_info.value)

    def test_offset_exceeds_total_count_allowed(self):
        """Test offset >= total_count is allowed (returns empty results)."""
        result = validate_pagination_params(limit=50, offset=100, total_count=50)

        # This is valid - will just return empty results
        assert result["is_valid"] is True
        assert result["offset"] == 100

    def test_offset_equals_total_count_allowed(self):
        """Test offset == total_count is allowed (returns empty results)."""
        result = validate_pagination_params(limit=50, offset=50, total_count=50)

        # This is valid - will just return empty results
        assert result["is_valid"] is True


# =============================================================================
# calculate_next_offset Tests
# =============================================================================

class TestCalculateNextOffset:
    """Test suite for calculate_next_offset function."""

    def test_full_page_has_next(self):
        """Test full page (returned_count == limit) has next page."""
        next_offset = calculate_next_offset(0, 10, 10, total_count=25)

        assert next_offset == 10

    def test_partial_page_no_next(self):
        """Test partial page (returned_count < limit) has no next page."""
        next_offset = calculate_next_offset(20, 10, 5, total_count=25)

        assert next_offset is None

    def test_empty_results_no_next(self):
        """Test empty results (returned_count == 0) has no next page."""
        next_offset = calculate_next_offset(0, 10, 0, total_count=0)

        assert next_offset is None

    def test_last_page_no_next(self):
        """Test last page where offset >= total_count has no next page."""
        next_offset = calculate_next_offset(20, 10, 10, total_count=30)

        # next_offset would be 30, which is >= total_count (30)
        assert next_offset is None

    def test_pagination_sequence(self):
        """Test sequential pagination through pages."""
        total = 45
        limit = 10

        # Page 1 -> Page 2
        offset1 = 0
        next1 = calculate_next_offset(offset1, limit, 10, total)
  # Changed tab to spaces
        assert next1 == 10

        # Page 2 -> Page 3
        offset2 = 10
        next2 = calculate_next_offset(offset2, limit, 10, total)
  # Changed tab to spaces
        assert next2 == 20

        # Page 3 -> Page 4
        offset3 = 20
        next3 = calculate_next_offset(offset3, limit, 10, total)
  # Changed tab to spaces
        assert next3 == 30

        # Page 4 -> Page 5 (partial page)
        offset4 = 30
        next4 = calculate_next_offset(offset4, limit, 5, total)
  # Changed tab to spaces
        assert next4 is None

    def test_without_total_count(self):
        """Test calculation without total_count (optimistic)."""
        # Without total_count, we assume there's a next page if returned_count == limit
        next_offset = calculate_next_offset(0, 10, 10, total_count=None)

        assert next_offset == 10

    def test_large_offset(self):
        """Test with large offset values."""
        next_offset = calculate_next_offset(1000, 50, 50, total_count=2000)

        assert next_offset == 1050


# =============================================================================
# has_next_page Tests
# =============================================================================

class TestHasNextPage:
    """Test suite for has_next_page function."""

    def test_full_page_has_next_true(self):
        """Test full page returns True."""
        assert has_next_page(0, 10, 10, total_count=25) is True

    def test_partial_page_has_next_false(self):
        """Test partial page returns False."""
        assert has_next_page(20, 10, 5, total_count=25) is False

    def test_empty_results_has_next_false(self):
        """Test empty results returns False."""
        assert has_next_page(0, 10, 0, total_count=0) is False

    def test_exact_boundary_has_next_false(self):
        """Test offset + limit == total_count returns False."""
        assert has_next_page(20, 10, 10, total_count=30) is False


# =============================================================================
# build_pagination_response Tests
# =============================================================================

class TestBuildPaginationResponse:
    """Test suite for build_pagination_response function."""

    def test_default_items_key(self):
        """Test response with default 'items' key."""
        items = [{"id": i} for i in range(1, 11)]  # 10 items (full page)
        response = build_pagination_response(items, total_count=45, limit=10, offset=0)

        assert response["items"] == items
        assert response["total_count"] == 45
        assert response["limit"] == 10
        assert response["offset"] == 0
        assert response["has_next_page"] is True
        assert response["status"] == "success"

    def test_custom_items_key(self):
        """Test response with custom items key (e.g., 'episodes')."""
        items = [{"id": 1}, {"id": 2}]
        response = build_pagination_response(
            items, total_count=45, limit=10, offset=0, items_key="episodes"
        )

        assert response["episodes"] == items
        assert "items" not in response
        assert response["total_count"] == 45

    def test_insights_key(self):
        """Test response with 'insights' key."""
        items = [{"id": 1, "content": "test"}]
        response = build_pagination_response(
            items, total_count=100, limit=50, offset=0, items_key="insights"
        )

        assert response["insights"] == items
        assert response["total_count"] == 100

    def test_empty_results(self):
        """Test response with empty results."""
        response = build_pagination_response(
            [], total_count=0, limit=10, offset=0, items_key="episodes"
        )

        assert response["episodes"] == []
        assert response["total_count"] == 0
        assert response["has_next_page"] is False

    def test_last_page_no_next(self):
        """Test response for last page (no next page)."""
        items = [{"id": i} for i in range(1, 6)]  # 5 items
        response = build_pagination_response(
            items, total_count=25, limit=10, offset=20, items_key="episodes"
        )

        assert response["has_next_page"] is False
        assert response["offset"] == 20

    def test_first_page_has_next(self):
        """Test response for first page with next page."""
        items = [{"id": i} for i in range(1, 11)]  # 10 items
        response = build_pagination_response(
            items, total_count=45, limit=10, offset=0, items_key="episodes"
        )

        assert response["has_next_page"] is True


# =============================================================================
# validate_limit_only Tests
# =============================================================================

class TestValidateLimitOnly:
    """Test suite for validate_limit_only function."""

    def test_valid_limit(self):
        """Test valid limit returns True."""
        is_valid, error = validate_limit_only(50)

        assert is_valid is True
        assert error is None

    def test_none_limit(self):
        """Test None limit returns True (use default)."""
        is_valid, error = validate_limit_only(None)

        assert is_valid is True
        assert error is None

    def test_invalid_limit_too_low(self):
        """Test invalid limit (< 1) returns False."""
        is_valid, error = validate_limit_only(0)

        assert is_valid is False
        assert error is not None
        assert "limit" in error.lower()

    def test_invalid_limit_too_high(self):
        """Test invalid limit (> 100) returns False."""
        is_valid, error = validate_limit_only(101)

        assert is_valid is False
        assert error is not None
        assert "limit" in error.lower()


# =============================================================================
# validate_offset_only Tests
# =============================================================================

class TestValidateOffsetOnly:
    """Test suite for validate_offset_only function."""

    def test_valid_offset(self):
        """Test valid offset returns True."""
        is_valid, error = validate_offset_only(100)

        assert is_valid is True
        assert error is None

    def test_none_offset(self):
        """Test None offset returns True (use default)."""
        is_valid, error = validate_offset_only(None)

        assert is_valid is True
        assert error is None

    def test_zero_offset_valid(self):
        """Test offset = 0 returns True."""
        is_valid, error = validate_offset_only(0)

        assert is_valid is True
        assert error is None

    def test_invalid_offset_negative(self):
        """Test invalid negative offset returns False."""
        is_valid, error = validate_offset_only(-1)

        assert is_valid is False
        assert error is not None
        assert "offset" in error.lower()


# =============================================================================
# Edge Cases from Story 9.2.3 Acceptance Criteria
# =============================================================================

class TestStoryEdgeCases:
    """Test suite for specific edge cases mentioned in Story 9.2.3."""

    def test_edge_case_limit_zero(self):
        """AC-3: limit = 0 returns empty results (not error) when allow_zero_limit=True."""
        result = validate_pagination_params(limit=0, offset=0, allow_zero_limit=True)

        assert result["is_valid"] is True
        assert result["limit"] == 0

    def test_edge_case_limit_zero_without_flag_raises_error(self):
        """AC-3: limit = 0 raises error when allow_zero_limit=False (default)."""
        with pytest.raises(LimitValidationError):
            validate_pagination_params(limit=0, offset=0)

    def test_edge_case_limit_greater_than_total_count(self):
        """AC-3: limit > total_count - validation should pass (returns available records)."""
        result = validate_pagination_params(limit=100, offset=0, total_count=10)

        # This is valid - database will just return all 10 records
        assert result["is_valid"] is True
        assert result["limit"] == 100

    def test_edge_case_offset_equals_total_count(self):
        """AC-3: offset >= total_count returns empty results (not error)."""
        result = validate_pagination_params(limit=10, offset=50, total_count=50)

        # This is valid - will return empty results
        assert result["is_valid"] is True
        assert result["offset"] == 50

    def test_edge_case_offset_exceeds_total_count(self):
        """AC-3: offset > total_count returns empty results (not error)."""
        result = validate_pagination_params(limit=10, offset=100, total_count=50)

        # This is valid - will return empty results
        assert result["is_valid"] is True
        assert result["offset"] == 100

    def test_edge_case_offset_plus_limit_beyond_dataset(self):
        """AC-3: offset + limit beyond dataset returns partial results (not error)."""
        result = validate_pagination_params(limit=50, offset=25, total_count=30)

        # This is valid - will return 5 items (offset 25-30)
        assert result["is_valid"] is True

    def test_edge_case_negative_limit_raises_error(self):
        """AC-3: Negative limit rejected with validation error."""
        with pytest.raises(LimitValidationError):
            validate_pagination_params(limit=-10, offset=0)

    def test_edge_case_negative_offset_raises_error(self):
        """AC-3: Negative offset rejected with validation error."""
        with pytest.raises(OffsetValidationError):
            validate_pagination_params(limit=10, offset=-5)

    def test_edge_case_empty_result_set(self):
        """AC-3: Empty result set (total_count = 0) is handled correctly."""
        result = validate_pagination_params(limit=10, offset=0, total_count=0)

        assert result["is_valid"] is True

        # Build response to verify empty results
        response = build_pagination_response(
            [], total_count=0, limit=10, offset=0, items_key="items"
        )
        assert response["total_count"] == 0
        assert response["items"] == []
        assert response["has_next_page"] is False
