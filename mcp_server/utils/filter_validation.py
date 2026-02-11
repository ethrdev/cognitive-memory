"""
Filter parameter validation utilities for hybrid_search.

Story 9.3.1: Extended filter parameters for pre-filtering support.
"""

from datetime import datetime
from typing import Any

# Allowed source types for source_type_filter
ALLOWED_SOURCE_TYPES = {"l2_insight", "episode_memory", "graph"}


def validate_filter_params(
    tags_filter: list[str] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    source_type_filter: list[str] | None = None,
) -> dict[str, Any]:
    """
    Validate filter parameters with clear error messages.

    Story 9.3.1: Filter parameter validation for hybrid_search.

    Args:
        tags_filter: Optional list of tag names to filter by
        date_from: Optional start date for filtering (inclusive)
        date_to: Optional end date for filtering (inclusive)
        source_type_filter: Optional list of source types to include

    Returns:
        Dict with:
        - "status": "validation_passed" if valid
        - "error": error message if invalid
        - "details": detailed error information if invalid
    """
    errors = []

    # Validate date range logic
    if date_from is not None and date_to is not None:
        if date_from > date_to:
            errors.append("date_from must be <= date_to")

    # Validate source types
    if source_type_filter is not None:
        if not isinstance(source_type_filter, list):
            errors.append("source_type_filter must be a list")
        else:
            invalid = set(source_type_filter) - ALLOWED_SOURCE_TYPES
            if invalid:
                errors.append(
                    f"Invalid source types: {invalid}. "
                    f"Must be one of: {ALLOWED_SOURCE_TYPES}"
                )

    # Validate tags_filter
    if tags_filter is not None:
        if not isinstance(tags_filter, list):
            errors.append("tags_filter must be a list")
        elif not all(isinstance(tag, str) for tag in tags_filter):
            errors.append("All items in tags_filter must be strings")

    if errors:
        return {
            "error": "Filter validation failed",
            "details": "; ".join(errors),
            "tool": "hybrid_search",
        }

    return {"status": "validation_passed"}


def should_include_source_type(
    source_type: str,
    source_type_filter: list[str] | None = None,
) -> bool:
    """
    Determine if a source type should be included in results.

    Story 9.3.1: Helper for source_type_filter application.

    Args:
        source_type: The source type to check (e.g., "l2_insight", "episode_memory")
        source_type_filter: Optional list of allowed source types

    Returns:
        True if source_type should be included, False otherwise
    """
    if source_type_filter is None:
        return True  # No filter applied
    return source_type in source_type_filter
