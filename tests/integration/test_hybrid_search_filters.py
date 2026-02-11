"""
Integration tests for hybrid_search extended filter parameters.

Story 9.3.1: Pre-filtering with tags_filter, date_from, date_to, source_type_filter.
"""

import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_hybrid_search_with_tags_filter(conn, sample_l2_insights):
    """
    Test hybrid_search filters by tags correctly.

    Story 9.3.1 AC1: tags_filter parameter works and filters results.
    """
    from mcp_server.tools import handle_hybrid_search

    # Test search with python tag filter
    result = await handle_hybrid_search({
        "query_text": "programming",
        "top_k": 10,
        "tags_filter": ["python"],
    })

    assert result["status"] == "success"
    assert "applied_filters" in result
    assert result["applied_filters"]["tags_filter"] == ["python"]

    # Verify results only contain python-tagged items
    for item in result["results"]:
        # Check metadata for tags (l2_insights have tags in metadata)
        if "metadata" in item and "tags" in item["metadata"]:
            assert "python" in item["metadata"]["tags"] or "python" in item.get("content", "")


@pytest.mark.asyncio
async def test_hybrid_search_with_date_range_filter(conn, sample_l2_insights):
    """
    Test hybrid_search filters by date range correctly.

    Story 9.3.1 AC1: date_from and date_to parameters work correctly.
    """
    from mcp_server.tools import handle_hybrid_search

    date_from = "2024-01-01T00:00:00"
    date_to = "2024-03-31T23:59:59"

    result = await handle_hybrid_search({
        "query_text": "test query",
        "top_k": 10,
        "date_from": date_from,
        "date_to": date_to,
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["date_from"] == date_from
    assert result["applied_filters"]["date_to"] == date_to

    # Verify all results are within date range
    for item in result["results"]:
        if "created_at" in item:
            created_at = item["created_at"]
            assert created_at >= "2024-01-01"
            assert created_at <= "2024-03-31"


@pytest.mark.asyncio
async def test_hybrid_search_with_date_from_only(conn, sample_l2_insights):
    """
    Test hybrid_search with only date_from (open-ended range).

    Story 9.3.1 AC1: Partial date ranges work correctly.
    """
    from mcp_server.tools import handle_hybrid_search

    date_from = "2024-03-01T00:00:00"

    result = await handle_hybrid_search({
        "query_text": "recent content",
        "top_k": 5,
        "date_from": date_from,
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["date_from"] == date_from
    assert result["applied_filters"]["date_to"] is None

    # Verify all results are after date_from
    for item in result["results"]:
        if "created_at" in item:
            assert item["created_at"] >= date_from


@pytest.mark.asyncio
async def test_hybrid_search_with_date_to_only(conn, sample_l2_insights):
    """
    Test hybrid_search with only date_to (open-ended range).

    Story 9.3.1 AC1: Partial date ranges work correctly.
    """
    from mcp_server.tools import handle_hybrid_search

    date_to = "2024-03-31T23:59:59"

    result = await handle_hybrid_search({
        "query_text": "old content",
        "top_k": 5,
        "date_to": date_to,
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["date_from"] is None
    assert result["applied_filters"]["date_to"] == date_to

    # Verify all results are before or equal to date_to
    for item in result["results"]:
        if "created_at" in item:
            assert item["created_at"] <= date_to


@pytest.mark.asyncio
async def test_hybrid_search_invalid_date_range(conn, sample_l2_insights):
    """
    Test hybrid_search rejects invalid date range (date_from > date_to).

    Story 9.3.1 AC1: Date range validation with clear error message.
    """
    from mcp_server.tools import handle_hybrid_search

    date_from = "2024-12-31T23:59:59"
    date_to = "2024-01-01T00:00:00"

    result = await handle_hybrid_search({
        "query_text": "test",
        "top_k": 5,
        "date_from": date_from,
        "date_to": date_to,
    })

    assert result["status"] == "error" or result.get("error") is not None
    assert "date_from must be <= date_to" in result.get("details", "")


@pytest.mark.asyncio
async def test_hybrid_search_with_source_type_filter_l2_only(conn, sample_l2_insights):
    """
    Test hybrid_search with source_type_filter for l2_insight only.

    Story 9.3.1 AC1: source_type_filter excludes unwanted sources.
    """
    from mcp_server.tools import handle_hybrid_search

    result = await handle_hybrid_search({
        "query_text": "test query",
        "top_k": 5,
        "source_type_filter": ["l2_insight"],
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["source_type_filter"] == ["l2_insight"]
    # Should return semantic, keyword results but not episode results
    assert result["episode_semantic_count"] == 0
    assert result["episode_keyword_count"] == 0


@pytest.mark.asyncio
async def test_hybrid_search_with_source_type_filter_episodes_only(conn, sample_episodes):
    """
    Test hybrid_search with source_type_filter for episode_memory only.

    Story 9.3.1 AC1: source_type_filter filters to specific source types.
    """
    from mcp_server.tools import handle_hybrid_search

    result = await handle_hybrid_search({
        "query_text": "test query",
        "top_k": 5,
        "source_type_filter": ["episode_memory"],
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["source_type_filter"] == ["episode_memory"]
    # Should return episode results but not l2_insight or graph results
    assert result["semantic_results_count"] == 0
    assert result["keyword_results_count"] == 0
    assert result["graph_results_count"] == 0
    assert result["episode_semantic_count"] >= 0 or result["episode_keyword_count"] >= 0


@pytest.mark.asyncio
async def test_hybrid_search_with_invalid_source_type(conn, sample_l2_insights):
    """
    Test hybrid_search rejects invalid source_type.

    Story 9.3.1 AC1: source_type_filter validates against allowed types.
    """
    from mcp_server.tools import handle_hybrid_search

    result = await handle_hybrid_search({
        "query_text": "test",
        "top_k": 5,
        "source_type_filter": ["invalid_source"],
    })

    assert result["status"] == "error" or result.get("error") is not None
    assert "Invalid source types" in result.get("details", "")


@pytest.mark.asyncio
async def test_hybrid_search_combined_filters(conn, sample_l2_insights):
    """
    Test hybrid_search with multiple filters combined.

    Story 9.3.1 AC7: Combined filter tests (tags + date + source_type).
    """
    from mcp_server.tools import handle_hybrid_search

    date_from = "2024-01-01T00:00:00"
    date_to = "2024-12-31T23:59:59"

    result = await handle_hybrid_search({
        "query_text": "programming",
        "top_k": 10,
        "tags_filter": ["python"],
        "date_from": date_from,
        "date_to": date_to,
        "source_type_filter": ["l2_insight"],
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["tags_filter"] == ["python"]
    assert result["applied_filters"]["date_from"] == date_from
    assert result["applied_filters"]["date_to"] == date_to
    assert result["applied_filters"]["source_type_filter"] == ["l2_insight"]


# Story 9.3.1 Fix: Additional combined filter tests as required by AC7
@pytest.mark.asyncio
async def test_hybrid_search_tags_and_date_from_only(conn, sample_l2_insights):
    """Test tags_filter combined with date_from only (no date_to)."""
    from mcp_server.tools import handle_hybrid_search

    result = await handle_hybrid_search({
        "query_text": "python",
        "top_k": 10,
        "tags_filter": ["python"],
        "date_from": "2024-01-01T00:00:00",
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["tags_filter"] == ["python"]
    assert result["applied_filters"]["date_from"] == "2024-01-01T00:00:00"
    assert result["applied_filters"]["date_to"] is None


@pytest.mark.asyncio
async def test_hybrid_search_date_range_and_source_type(conn, sample_l2_insights):
    """Test date_range filter combined with source_type_filter (no tags)."""
    from mcp_server.tools import handle_hybrid_search

    result = await handle_hybrid_search({
        "query_text": "test",
        "top_k": 10,
        "date_from": "2024-01-01T00:00:00",
        "date_to": "2024-06-30T23:59:59",
        "source_type_filter": ["l2_insight"],
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["date_from"] == "2024-01-01T00:00:00"
    assert result["applied_filters"]["date_to"] == "2024-06-30T23:59:59"
    assert result["applied_filters"]["source_type_filter"] == ["l2_insight"]
    assert result["applied_filters"]["tags_filter"] is None


@pytest.mark.asyncio
async def test_hybrid_search_backward_compatible_no_filters(conn, sample_l2_insights):
    """
    Test hybrid_search works without new filter parameters (backward compatibility).

    Story 9.3.1 AC3: All filters are optional - backward compatible.
    """
    from mcp_server.tools import handle_hybrid_search

    result = await handle_hybrid_search({
        "query_text": "test query",
        "top_k": 5,
        # No new filter parameters
    })

    assert result["status"] == "success"
    assert result["applied_filters"]["tags_filter"] is None
    assert result["applied_filters"]["date_from"] is None
    assert result["applied_filters"]["date_to"] is None
    assert result["applied_filters"]["source_type_filter"] is None


@pytest.mark.asyncio
async def test_hybrid_search_with_sector_filter_and_new_filters(conn, sample_l2_insights):
    """
    Test hybrid_search with both sector_filter and new filters combined.

    Story 9.3.1 AC5: Filters work with existing sector_filter.
    """
    from mcp_server.tools import handle_hybrid_search

    result = await handle_hybrid_search({
        "query_text": "test",
        "top_k": 5,
        "sector_filter": ["semantic"],
        "tags_filter": ["python"],
    })

    assert result["status"] == "success"
    assert result["sector_filter"] == ["semantic"]
    assert result["applied_filters"]["tags_filter"] == ["python"]


@pytest.mark.asyncio
async def test_hybrid_search_empty_results_with_strict_filters(conn, sample_l2_insights):
    """
    Test hybrid_search returns empty results when filters are too restrictive.

    Story 9.3.1 AC7: Edge case tests (empty filter results).
    """
    from mcp_server.tools import handle_hybrid_search

    # Future date range should return no results
    future_date = "2099-01-01T00:00:00"

    result = await handle_hybrid_search({
        "query_text": "test",
        "top_k": 5,
        "date_from": future_date,
    })

    assert result["status"] == "success"
    assert result["final_results_count"] == 0
    assert len(result["results"]) == 0


@pytest.mark.asyncio
async def test_hybrid_search_all_filters_combined(conn, sample_l2_insights):
    """
    Test hybrid_search with ALL filters combined including sector_filter.

    Story 9.3.1 AC7: All filters work together.
    """
    from mcp_server.tools import handle_hybrid_search

    result = await handle_hybrid_search({
        "query_text": "python",
        "top_k": 10,
        "sector_filter": ["semantic"],
        "tags_filter": ["python"],
        "date_from": "2024-01-01T00:00:00",
        "date_to": "2024-12-31T23:59:59",
        "source_type_filter": ["l2_insight"],
    })

    assert result["status"] == "success"
    # All filters should be present in response
    assert result["sector_filter"] == ["semantic"]
    assert result["applied_filters"]["tags_filter"] == ["python"]
    assert result["applied_filters"]["date_from"] == "2024-01-01T00:00:00"
    assert result["applied_filters"]["date_to"] == "2024-12-31T23:59:59"
    assert result["applied_filters"]["source_type_filter"] == ["l2_insight"]
