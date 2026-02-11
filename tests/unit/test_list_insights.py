"""
Unit Tests for list_insights MCP Tool

Tests for Story 9.2.2: list_insights New Endpoint.
Covers all acceptance criteria (AC-1 through AC-9).

Author: Epic 9 Implementation
Story: 9.2.2 - list_insights New Endpoint
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from mcp_server.tools.list_insights import handle_list_insights


# =============================================================================
# AC-1: Tool Parameters Tests
# =============================================================================

@pytest.mark.asyncio
async def test_all_parameters_optional(with_project_context):
    """AC-1: All filter parameters are optional - returns empty list when no insights."""
    # Mock database to return empty list
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [],
            "total_count": 0,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({})

        assert result["status"] == "success"
        assert result["insights"] == []
        assert result["total_count"] == 0
        assert result["limit"] == 50
        assert result["offset"] == 0


@pytest.mark.asyncio
async def test_default_limit_and_offset(with_project_context):
    """AC-1: Default limit is 50, default offset is 0."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({})

        mock_list.assert_called_once_with(
            limit=50,
            offset=0,
            tags=None,
            date_from=None,
            date_to=None,
            io_category=None,
            is_identity=None,
            memory_sector=None,
        )


@pytest.mark.asyncio
async def test_custom_limit_and_offset(with_project_context):
    """AC-1: Custom limit and offset can be set."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1}],
            "total_count": 100,
            "limit": 10,
            "offset": 20,
        }

        result = await handle_list_insights({"limit": 10, "offset": 20})

        mock_list.assert_called_once_with(
            limit=10,
            offset=20,
            tags=None,
            date_from=None,
            date_to=None,
            io_category=None,
            is_identity=None,
            memory_sector=None,
        )
        assert result["limit"] == 10
        assert result["offset"] == 20
        assert result["total_count"] == 100


# =============================================================================
# AC-2: Tags Filter Tests
# =============================================================================

@pytest.mark.asyncio
async def test_tags_single_filter(with_project_context):
    """AC-2: Single tag filter uses array-contains operator."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [
                {"id": 1, "tags": ["dark-romance", "relationship"]},
            ],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"tags": ["dark-romance"]})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["tags"] == ["dark-romance"]


@pytest.mark.asyncio
async def test_tags_multiple_filter_and_logic(with_project_context):
    """AC-2: Multiple tags require ALL tags to be present (AND logic)."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [
                {"id": 1, "tags": ["dark-romance", "relationship", "emotional"]},
            ],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"tags": ["dark-romance", "relationship"]})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        # AND logic means database gets both tags
        assert call_kwargs["tags"] == ["dark-romance", "relationship"]


@pytest.mark.asyncio
async def test_tags_empty_array_treated_as_none(with_project_context):
    """AC-2: Empty tags array should be treated as no filter."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [],
            "total_count": 0,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"tags": []})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        # Empty array becomes None (no filter)
        assert call_kwargs["tags"] is None


@pytest.mark.asyncio
async def test_tags_must_be_array_of_strings(with_project_context):
    """AC-2: Tags parameter validation - must be array of strings."""
    result = await handle_list_insights({"tags": "not-an-array"})

    assert "error" in result
    assert result["details"] == "tags must be an array of strings"


@pytest.mark.asyncio
async def test_tags_array_items_must_be_strings(with_project_context):
    """AC-2: Tags parameter validation - array items must be strings."""
    result = await handle_list_insights({"tags": [123, "valid-tag"]})

    assert "error" in result
    assert result["details"] == "tags must be an array of strings"


# =============================================================================
# AC-3: Date Range Filter Tests
# =============================================================================

@pytest.mark.asyncio
async def test_date_from_filter(with_project_context):
    """AC-3: date_from filters insights created on or after this date."""
    test_date = "2026-02-01T00:00:00Z"

    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1, "created_at": "2026-02-01T12:00:00Z"}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"date_from": test_date})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["date_from"] == datetime.fromisoformat("2026-02-01T00:00:00+00:00")


@pytest.mark.asyncio
async def test_date_to_filter(with_project_context):
    """AC-3: date_to filters insights created before or on this date."""
    test_date = "2026-02-28T23:59:59Z"

    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1, "created_at": "2026-02-15T12:00:00Z"}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"date_to": test_date})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["date_to"] == datetime.fromisoformat("2026-02-28T23:59:59+00:00")


@pytest.mark.asyncio
async def test_date_range_filter_combined(with_project_context):
    """AC-3: date_from and date_to can be combined."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1, "created_at": "2026-02-15T12:00:00Z"}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({
            "date_from": "2026-02-01T00:00:00Z",
            "date_to": "2026-02-28T23:59:59Z",
        })

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["date_from"] == datetime.fromisoformat("2026-02-01T00:00:00+00:00")
        assert call_kwargs["date_to"] == datetime.fromisoformat("2026-02-28T23:59:59+00:00")


@pytest.mark.asyncio
async def test_invalid_iso8601_timestamp(with_project_context):
    """AC-3: Invalid ISO 8601 timestamp returns validation error."""
    result = await handle_list_insights({"date_from": "invalid-timestamp"})

    assert "error" in result
    assert "Invalid ISO 8601 timestamp" in result["details"]


# =============================================================================
# AC-4: io_category Filter Tests
# =============================================================================

@pytest.mark.asyncio
async def test_io_category_filter(with_project_context):
    """AC-4: io_category filter by exact match."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1, "io_category": "ethr"}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"io_category": "ethr"})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["io_category"] == "ethr"


@pytest.mark.asyncio
async def test_io_category_must_be_string(with_project_context):
    """AC-4: io_category parameter validation - must be string."""
    result = await handle_list_insights({"io_category": 123})

    assert "error" in result
    assert result["details"] == "io_category must be a string"


@pytest.mark.asyncio
async def test_io_category_must_be_valid_value(with_project_context):
    """AC-4: io_category parameter validation - must be valid category value."""
    result = await handle_list_insights({"io_category": "invalid-category"})

    assert "error" in result
    assert "io_category must be one of" in result["details"]


@pytest.mark.asyncio
async def test_io_category_valid_values(with_project_context):
    """AC-4: Valid io_category values: 'self', 'ethr', 'shared', 'relationship'."""
    for category in ["self", "ethr", "shared", "relationship"]:
        with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
            mock_list.return_value = {
                "insights": [],
                "total_count": 0,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_insights({"io_category": category})
            assert result["status"] == "success"


# =============================================================================
# AC-5: is_identity Filter Tests
# =============================================================================

@pytest.mark.asyncio
async def test_is_identity_true_filter(with_project_context):
    """AC-5: is_identity filter for TRUE."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1, "is_identity": True}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"is_identity": True})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["is_identity"] is True


@pytest.mark.asyncio
async def test_is_identity_false_filter(with_project_context):
    """AC-5: is_identity filter for FALSE."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1, "is_identity": False}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"is_identity": False})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["is_identity"] is False


@pytest.mark.asyncio
async def test_is_identity_must_be_boolean(with_project_context):
    """AC-5: is_identity parameter validation - must be boolean."""
    result = await handle_list_insights({"is_identity": "true"})

    assert "error" in result
    assert result["details"] == "is_identity must be a boolean"


# =============================================================================
# AC-6: memory_sector Filter Tests
# =============================================================================

@pytest.mark.asyncio
async def test_memory_sector_filter(with_project_context):
    """AC-6: memory_sector filter by exact match (from metadata)."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1, "memory_sector": "emotional"}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({"memory_sector": "emotional"})

        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["memory_sector"] == "emotional"


@pytest.mark.asyncio
async def test_memory_sector_must_be_string(with_project_context):
    """AC-6: memory_sector parameter validation - must be string."""
    result = await handle_list_insights({"memory_sector": 123})

    assert "error" in result
    assert result["details"] == "memory_sector must be a string"


@pytest.mark.asyncio
async def test_memory_sector_must_be_valid_value(with_project_context):
    """AC-6: memory_sector parameter validation - must be valid sector value."""
    result = await handle_list_insights({"memory_sector": "invalid-sector"})

    assert "error" in result
    assert "memory_sector must be one of" in result["details"]


@pytest.mark.asyncio
async def test_memory_sector_valid_values(with_project_context):
    """AC-6: Valid memory_sector values."""
    for sector in ["emotional", "episodic", "semantic", "procedural", "reflective"]:
        with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
            mock_list.return_value = {
                "insights": [],
                "total_count": 0,
                "limit": 50,
                "offset": 0,
            }

            result = await handle_list_insights({"memory_sector": sector})
            assert result["status"] == "success"


# =============================================================================
# AC-7: Soft-Delete Exclusion Tests
# =============================================================================

@pytest.mark.asyncio
async def test_soft_deleted_insights_excluded(with_project_context):
    """AC-7: Soft-deleted insights (is_deleted=TRUE) are excluded from results.

    Note: This unit test verifies the handler passes parameters correctly.
    The actual SQL WHERE is_deleted = FALSE clause is tested in
    integration tests with real database queries.

    Note: The response does NOT include is_deleted field - it's filtered by the database.
    This test verifies the handler correctly calls the database function.
    """
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        # The database function returns insights without is_deleted field
        # (it's filtered by SQL WHERE is_deleted = FALSE)
        mock_list.return_value = {
            "insights": [{"id": 1, "content": "Active insight"}],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({})

        assert result["status"] == "success"
        # Verify the database function was called
        mock_list.assert_called_once()
        # Verify insights were returned (soft-deleted ones excluded by DB)
        assert len(result["insights"]) == 1
        assert result["insights"][0]["id"] == 1


# =============================================================================
# AC-8: Pagination with total_count Tests
# =============================================================================

@pytest.mark.asyncio
async def test_total_count_includes_all_filters(with_project_context):
    """AC-8: Count query includes all active filters."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1}],
            "total_count": 100,  # Total matching all filters
            "limit": 10,
            "offset": 0,
        }

        result = await handle_list_insights({
            "limit": 10,
            "tags": ["dark-romance"],
            "io_category": "ethr",
        })

        # total_count should reflect ALL matching insights, not just returned
        assert result["total_count"] == 100
        assert len(result["insights"]) == 1  # Only 1 returned due to limit


@pytest.mark.asyncio
async def test_pagination_accurate_count(with_project_context):
    """AC-8: Pagination enables accurate navigation."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        # First page
        mock_list.return_value = {
            "insights": [{"id": i} for i in range(1, 11)],
            "total_count": 45,
            "limit": 10,
            "offset": 0,
        }

        result = await handle_list_insights({"limit": 10, "offset": 0})

        assert len(result["insights"]) == 10
        assert result["total_count"] == 45
        assert result["limit"] == 10
        assert result["offset"] == 0


# =============================================================================
# AC-9: Response Format Tests
# =============================================================================

@pytest.mark.asyncio
async def test_response_format_matches_list_episodes(with_project_context):
    """AC-9: Response format matches list_episodes pattern."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [
                {
                    "id": 123,
                    "content": "Test insight content",
                    "io_category": "ethr",
                    "is_identity": False,
                    "memory_sector": "semantic",
                    "tags": ["dark-romance", "relationship"],
                    "metadata": {"key": "value"},
                    "memory_strength": 0.7,
                    "created_at": "2026-02-11T14:30:00Z",
                }
            ],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({})

        # Verify all expected fields
        assert "insights" in result
        assert "total_count" in result
        assert "limit" in result
        assert "offset" in result
        assert result["status"] == "success"

        # Verify insight object structure
        insight = result["insights"][0]
        assert insight["id"] == 123
        assert insight["content"] == "Test insight content"
        assert insight["io_category"] == "ethr"
        assert insight["is_identity"] is False
        assert insight["memory_sector"] == "semantic"
        assert insight["tags"] == ["dark-romance", "relationship"]
        assert insight["metadata"] == {"key": "value"}
        assert insight["memory_strength"] == 0.7
        assert insight["created_at"] == "2026-02-11T14:30:00Z"


# =============================================================================
# Parameter Validation Tests
# =============================================================================

@pytest.mark.asyncio
async def test_limit_minimum_validation(with_project_context):
    """Limit must be at least 1."""
    result = await handle_list_insights({"limit": 0})

    assert "error" in result
    # Story 9.2.3: New pagination utility provides more specific error message
    assert "limit" in result["details"].lower()


@pytest.mark.asyncio
async def test_limit_maximum_validation(with_project_context):
    """Limit must be at most 100."""
    result = await handle_list_insights({"limit": 101})

    assert "error" in result
    assert "limit must be between 1 and 100" in result["details"]


@pytest.mark.asyncio
async def test_limit_type_validation(with_project_context):
    """Limit must be an integer."""
    result = await handle_list_insights({"limit": "fifty"})

    assert "error" in result
    # Story 9.2.3: New pagination utility provides more specific error message
    assert "limit" in result["details"].lower()


@pytest.mark.asyncio
async def test_offset_minimum_validation(with_project_context):
    """Offset must be >= 0."""
    result = await handle_list_insights({"offset": -1})

    assert "error" in result
    assert "offset must be >= 0" in result["details"]


@pytest.mark.asyncio
async def test_offset_type_validation(with_project_context):
    """Offset must be an integer."""
    result = await handle_list_insights({"offset": "ten"})

    assert "error" in result
    # Story 9.2.3: New pagination utility provides more specific error message
    assert "offset" in result["details"].lower()


# =============================================================================
# Error Handling Tests
# =============================================================================

@pytest.mark.asyncio
async def test_database_operation_failed(with_project_context):
    """Handles database errors gracefully."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.side_effect = Exception("Database connection failed")

        result = await handle_list_insights({})

        assert "error" in result
        assert result["details"] == "Database connection failed"


@pytest.mark.asyncio
async def test_tool_execution_failed(with_project_context):
    """Handles unexpected errors gracefully."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        # Trigger an unexpected error
        mock_list.side_effect = RuntimeError("Unexpected failure")

        result = await handle_list_insights({})

        assert "error" in result
        assert result["details"] == "Unexpected failure"


# =============================================================================
# Combined Filters Tests
# =============================================================================

@pytest.mark.asyncio
async def test_combined_filters_all_together(with_project_context):
    """All filters can be applied together."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [
                {
                    "id": 1,
                    "tags": ["dark-romance", "relationship"],
                    "io_category": "ethr",
                    "is_identity": False,
                    "memory_sector": "emotional",
                }
            ],
            "total_count": 1,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({
            "tags": ["dark-romance", "relationship"],
            "date_from": "2026-02-01T00:00:00Z",
            "date_to": "2026-02-28T23:59:59Z",
            "io_category": "ethr",
            "is_identity": False,
            "memory_sector": "emotional",
        })

        assert result["status"] == "success"
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args.kwargs
        assert call_kwargs["tags"] == ["dark-romance", "relationship"]
        assert call_kwargs["io_category"] == "ethr"
        assert call_kwargs["is_identity"] is False
        assert call_kwargs["memory_sector"] == "emotional"


@pytest.mark.asyncio
async def test_backward_compatibility_no_filters(with_project_context):
    """Backward compatibility - no filters returns all insights."""
    with patch('mcp_server.tools.list_insights.list_insights') as mock_list:
        mock_list.return_value = {
            "insights": [{"id": 1}, {"id": 2}],
            "total_count": 2,
            "limit": 50,
            "offset": 0,
        }

        result = await handle_list_insights({})

        assert result["status"] == "success"
        assert len(result["insights"]) == 2
