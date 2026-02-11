"""
Pagination Validation Utilities

Provides reusable validation functions for pagination parameters
across all list-type MCP tools (list_episodes, list_insights, etc.).

Story 9.2.3: pagination-validation
"""

from __future__ import annotations

from typing import Any


# =============================================================================
# Error Constants
# =============================================================================

class PaginationError(ValueError):
    """Base exception for pagination validation errors."""
    pass


class LimitValidationError(PaginationError):
    """Raised when limit parameter is invalid."""
    pass


class OffsetValidationError(PaginationError):
    """Raised when offset parameter is invalid."""
    pass


# Error message constants
ERR_LIMIT_TYPE = "limit must be an integer"
ERR_LIMIT_RANGE = "limit must be between 1 and 100"
ERR_LIMIT_ZERO = "limit must be at least 1 (use limit >= 1 for results)"
ERR_OFFSET_TYPE = "offset must be an integer"
ERR_OFFSET_NEGATIVE = "offset must be >= 0"
ERR_OFFSET_EXCEEDS_TOTAL = "offset ({offset}) exceeds total_count ({total_count}) - use offset < total_count"


# =============================================================================
# Validation Constants
# =============================================================================

DEFAULT_LIMIT = 50
MIN_LIMIT = 1
MAX_LIMIT = 100

DEFAULT_OFFSET = 0
MIN_OFFSET = 0


# =============================================================================
# Validation Functions
# =============================================================================

def validate_pagination_params(
    limit: int | None = None,
    offset: int | None = None,
    total_count: int | None = None,
    allow_zero_limit: bool = False,
) -> dict[str, Any]:
    """
    Validate pagination parameters (limit, offset) with detailed error messages.

    Story 9.2.3: Pagination validation function for all list endpoints.

    Args:
        limit: Maximum number of items to return (default: DEFAULT_LIMIT)
        offset: Number of items to skip (default: DEFAULT_OFFSET)
        total_count: Optional total count for offset validation
        allow_zero_limit: If True, limit=0 is allowed (returns empty results)

    Returns:
        Dict with validated and normalized parameters:
        {
            "limit": int (validated),
            "offset": int (validated),
            "is_valid": bool,
            "error": str | None (if validation failed)
        }

    Raises:
        LimitValidationError: If limit parameter is invalid
        OffsetValidationError: If offset parameter is invalid

    Examples:
        >>> validate_pagination_params(limit=50, offset=0)
        {'limit': 50, 'offset': 0, 'is_valid': True, 'error': None}

        >>> validate_pagination_params(limit=0, offset=0)
        LimitValidationError: limit must be at least 1

        >>> validate_pagination_params(limit=101, offset=0)
        LimitValidationError: limit must be between 1 and 100

        >>> validate_pagination_params(limit=10, offset=-1)
        OffsetValidationError: offset must be >= 0
    """
    # Apply defaults
    validated_limit = limit if limit is not None else DEFAULT_LIMIT
    validated_offset = offset if offset is not None else DEFAULT_OFFSET

    # Validate limit parameter
    if not isinstance(validated_limit, int):
        raise LimitValidationError(ERR_LIMIT_TYPE)

    if allow_zero_limit and validated_limit == 0:
        # Special case: limit=0 is allowed (returns empty results)
        pass
    elif validated_limit < MIN_LIMIT:
        if validated_limit == 0:
            raise LimitValidationError(ERR_LIMIT_ZERO)
        else:
            raise LimitValidationError(ERR_LIMIT_RANGE)
    elif validated_limit > MAX_LIMIT:
        raise LimitValidationError(ERR_LIMIT_RANGE)

    # Validate offset parameter
    if not isinstance(validated_offset, int):
        raise OffsetValidationError(ERR_OFFSET_TYPE)

    if validated_offset < MIN_OFFSET:
        raise OffsetValidationError(ERR_OFFSET_NEGATIVE)

    # Validate offset < total_count if total_count is provided
    # This is a warning, not an error - returns empty results
    if total_count is not None and isinstance(total_count, int) and validated_offset >= total_count:
        # This is acceptable - just returns empty results
        # But we can note it in the response for logging/debugging
        pass

    return {
        "limit": validated_limit,
        "offset": validated_offset,
        "is_valid": True,
        "error": None,
    }


def calculate_next_offset(
    current_offset: int,
    limit: int,
    returned_count: int,
    total_count: int | None = None,
) -> int | None:
    """
    Calculate the next offset for pagination.

    Story 9.2.3: Helper for "next page" calculation.

    Args:
        current_offset: The offset used for the current page
        limit: The limit used for the current page
        returned_count: Number of items actually returned (may be < limit)
        total_count: Total number of items (optional, for validation)

    Returns:
        Next offset value, or None if there is no next page

    Examples:
        >>> calculate_next_offset(0, 10, 10, 25)
        10  # Has next page

        >>> calculate_next_offset(10, 10, 10, 20)
        20  # Last page offset (but no next page since 20 >= 20)

        >>> calculate_next_offset(20, 10, 5, 25)
        None  # No next page (returned_count < limit)

        >>> calculate_next_offset(0, 10, 0, 0)
        None  # Empty result set, no next page
    """
    # If returned less than limit, we're on the last page
    if returned_count < limit:
        return None

    # If nothing returned, no next page
    if returned_count == 0:
        return None

    # Calculate potential next offset
    next_offset = current_offset + limit

    # If total_count is provided, check if we're past the end
    if total_count is not None and next_offset >= total_count:
        return None

    return next_offset


def has_next_page(
    current_offset: int,
    limit: int,
    returned_count: int,
    total_count: int | None = None,
) -> bool:
    """
    Determine if there is a next page available.

    Story 9.2.3: Helper for pagination metadata.

    Args:
        current_offset: The offset used for the current page
        limit: The limit used for the current page
        returned_count: Number of items actually returned
        total_count: Total number of items (optional)

    Returns:
        True if there is a next page, False otherwise

    Examples:
        >>> has_next_page(0, 10, 10, 25)
        True

        >>> has_next_page(20, 10, 5, 25)
        False
    """
    next_offset = calculate_next_offset(current_offset, limit, returned_count, total_count)
    return next_offset is not None


def build_pagination_response(
    items: list[Any],
    total_count: int,
    limit: int,
    offset: int,
    items_key: str = "items",
) -> dict[str, Any]:
    """
    Build a standardized pagination response.

    Story 9.2.3: Consistent pagination metadata across endpoints.

    Args:
        items: The list of items to return
        total_count: Total number of matching items (ignoring pagination)
        limit: The limit that was applied
        offset: The offset that was applied
        items_key: The key name for the items list (default: "items")

    Returns:
        Dict with standardized pagination response format:
        {
            items_key: [...],
            "total_count": int,
            "limit": int,
            "offset": int,
            "has_next_page": bool,
            "status": "success"
        }

    Examples:
        >>> build_pagination_response(
        ...     items=[{"id": 1}, {"id": 2}],
        ...     total_count=45,
        ...     limit=10,
        ...     offset=0,
        ...     items_key="episodes"
        ... )
        {
            'episodes': [{'id': 1}, {'id': 2}],
            'total_count': 45,
            'limit': 10,
            'offset': 0,
            'has_next_page': True,
            'status': 'success'
        }
    """
    returned_count = len(items)
    next_page = has_next_page(offset, limit, returned_count, total_count)

    response = {
        items_key: items,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "has_next_page": next_page,
        "status": "success",
    }

    return response


def validate_limit_only(limit: int | None) -> tuple[bool, str | None]:
    """
    Quick validation for limit parameter only.

    Useful for tool handlers that need to validate limit
    before making database calls.

    Args:
        limit: The limit value to validate

    Returns:
        Tuple of (is_valid: bool, error_message: str | None)
    """
    if limit is None:
        return True, None

    try:
        validate_pagination_params(limit=limit, offset=0)
        return True, None
    except LimitValidationError as e:
        return False, str(e)


def validate_offset_only(offset: int | None) -> tuple[bool, str | None]:
    """
    Quick validation for offset parameter only.

    Useful for tool handlers that need to validate offset
    before making database calls.

    Args:
        offset: The offset value to validate

    Returns:
        Tuple of (is_valid: bool, error_message: str | None)
    """
    if offset is None:
        return True, None

    try:
        validate_pagination_params(limit=1, offset=offset)
        return True, None
    except OffsetValidationError as e:
        return False, str(e)
