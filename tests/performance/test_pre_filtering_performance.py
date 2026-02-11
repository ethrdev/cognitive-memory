"""
Performance validation tests for pre-filtering in hybrid_search.

Story 9.3.1: Validate that pre-filtering improves query performance.
"""

import pytest
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_pre_filtering_reduces_search_space(conn, sample_l2_insights_large):
    """
    Test that pre-filtering with tags reduces the vector search space.

    Story 9.3.1 NFR4: Pre-filtering should add <50ms overhead but
    save >100ms of vector search on large datasets.
    """
    from mcp_server.tools import handle_hybrid_search
    import time

    # Query without filter (searches entire dataset)
    start_unfiltered = time.perf_counter()
    result_unfiltered = await handle_hybrid_search({
        "query_text": "programming",
        "top_k": 10,
    })
    time_unfiltered = (time.perf_counter() - start_unfiltered) * 1000  # ms

    # Query with restrictive tag filter (searches subset)
    start_filtered = time.perf_counter()
    result_filtered = await handle_hybrid_search({
        "query_text": "programming",
        "top_k": 10,
        "tags_filter": ["rare_tag"],  # Should match few results
    })
    time_filtered = (time.perf_counter() - start_filtered) * 1000  # ms

    assert result_unfiltered["status"] == "success"
    assert result_filtered["status"] == "success"

    # Pre-filtered query should not be significantly slower
    # (may be faster due to reduced vector search space)
    # Allow 20% tolerance for variance
    assert time_filtered <= time_unfiltered * 1.2, (
        f"Filtered query ({time_filtered:.2f}ms) took longer than "
        f"unfiltered ({time_unfiltered:.2f}ms)"
    )


@pytest.mark.asyncio
async def test_pre_filtering_date_range_efficiency(conn):
    """
    Test that date range pre-filtering is efficient using B-tree index.

    Story 9.3.1: Date filtering should use B-tree index on created_at.
    """
    from mcp_server.tools import handle_hybrid_search
    import time

    # Narrow date range (should use index efficiently)
    start = time.perf_counter()
    result = await handle_hybrid_search({
        "query_text": "test",
        "top_k": 10,
        "date_from": datetime(2024, 1, 1),
        "date_to": datetime(2024, 1, 31),  # Single month
    })
    query_time = (time.perf_counter() - start) * 1000  # ms

    assert result["status"] == "success"
    # Date filter should be fast (<100ms for reasonable dataset)
    assert query_time < 100, f"Date range filter took {query_time:.2f}ms (expected <100ms)"


@pytest.mark.asyncio
async def test_pre_filtering_combined_overhead(conn):
    """
    Test that combined pre-filters don't add excessive overhead.

    Story 9.3.1: Pre-filtering should add <50ms overhead.
    """
    from mcp_server.tools import handle_hybrid_search
    import time

    start = time.perf_counter()
    result = await handle_hybrid_search({
        "query_text": "test query",
        "top_k": 10,
        "tags_filter": ["test"],
        "date_from": datetime(2024, 1, 1),
        "date_to": datetime(2024, 12, 31),
        "source_type_filter": ["l2_insight"],
    })
    query_time = (time.perf_counter() - start) * 1000  # ms

    assert result["status"] == "success"
    # Combined filters should not add excessive overhead
    assert query_time < 200, f"Combined filters took {query_time:.2f}ms (expected <200ms)"


@pytest.mark.asyncio
async def test_hybrid_search_latency_target_nfr4(conn):
    """
    Test that hybrid_search meets <1s latency target (NFR4).

    Story 9.3.1 NFR4: No significant performance overhead.
    """
    from mcp_server.tools import handle_hybrid_search
    import time

    start = time.perf_counter()
    result = await handle_hybrid_search({
        "query_text": "test query for latency measurement",
        "top_k": 10,
        "tags_filter": ["python"],
    })
    query_time = (time.perf_counter() - start) * 1000  # ms

    assert result["status"] == "success"
    # NFR4: <1s latency target
    assert query_time < 1000, f"Query took {query_time:.2f}ms (expected <1000ms per NFR4)"


@pytest.mark.asyncio
async def test_empty_filter_results_fast(conn):
    """
    Test that queries returning empty results are still fast.

    Story 9.3.1: Early exit for empty filter results.
    """
    from mcp_server.tools import handle_hybrid_search
    import time

    start = time.perf_counter()
    result = await handle_hybrid_search({
        "query_text": "test",
        "top_k": 10,
        "tags_filter": ["nonexistent_tag_xyz123"],
    })
    query_time = (time.perf_counter() - start) * 1000  # ms

    assert result["status"] == "success"
    assert result["final_results_count"] == 0
    # Empty results should be fast (early exit)
    assert query_time < 500, f"Empty result query took {query_time:.2f}ms (expected <500ms)"


@pytest.mark.asyncio
async def test_pre_filtering_statistics_logging(conn, caplog):
    """
    Test that pre-filter statistics are logged correctly.

    Story 9.3.1: Add logging for pre-filter statistics.
    """
    from mcp_server.tools import handle_hybrid_search
    import logging

    with caplog.at_level(logging.DEBUG, logger="mcp_server.tools"):
        result = await handle_hybrid_search({
            "query_text": "test",
            "top_k": 5,
            "tags_filter": ["test_tag"],
        })

        assert result["status"] == "success"
        # Check that pre-filter logging occurred
        assert any("Pre-filter applied" in record.message for record in caplog.records)


# Performance benchmarks (not asserts, just measurements)
@pytest.mark.asyncio
async def test_benchmark_filter_combinations(conn):
    """
    Benchmark various filter combinations for performance analysis.

    Story 9.3.1: Performance validation tests.
    This test measures but does not assert specific times.
    """
    from mcp_server.tools import handle_hybrid_search
    import time

    base_query = {
        "query_text": "programming test",
        "top_k": 10,
    }

    filter_combinations = [
        {"name": "no_filters", "filters": {}},
        {"name": "tags_only", "filters": {"tags_filter": ["python"]}},
        {"name": "date_from_only", "filters": {"date_from": datetime(2024, 1, 1)}},
        {"name": "date_range", "filters": {
            "date_from": datetime(2024, 1, 1),
            "date_to": datetime(2024, 12, 31)
        }},
        {"name": "source_type_only", "filters": {"source_type_filter": ["l2_insight"]}},
        {"name": "tags_and_date", "filters": {
            "tags_filter": ["python"],
            "date_from": datetime(2024, 1, 1),
        }},
        {"name": "all_filters", "filters": {
            "tags_filter": ["python"],
            "date_from": datetime(2024, 1, 1),
            "date_to": datetime(2024, 12, 31),
            "source_type_filter": ["l2_insight"],
        }},
    ]

    results = []
    for combo in filter_combinations:
        args = {**base_query, **combo["filters"]}
        start = time.perf_counter()
        result = await handle_hybrid_search(args)
        query_time = (time.perf_counter() - start) * 1000  # ms

        results.append({
            "combination": combo["name"],
            "time_ms": query_time,
            "result_count": result.get("final_results_count", 0),
            "status": result.get("status"),
        })

    # Log results for analysis (non-asserting test)
    print("\n=== Pre-Filter Performance Benchmarks ===")
    for r in results:
        print(f"{r['combination']:20s}: {r['time_ms']:6.2f}ms ({r['result_count']} results)")

    # Test always passes (just benchmarking)
    assert True
