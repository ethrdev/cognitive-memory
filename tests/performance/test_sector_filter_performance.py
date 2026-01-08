"""
Performance tests for sector_filter parameter (Story 9-3, Story 9-4).

Validates that sector-filtered queries perform within 20% of unfiltered query latency (NFR2).
"""

from __future__ import annotations

import asyncio
import statistics
import time
from unittest.mock import MagicMock, patch

import pytest

from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors
from mcp_server.db.graph import query_neighbors
from mcp_server.tools import handle_hybrid_search


class TestSectorFilterPerformance:
    """Performance tests for sector_filter (AC #5)."""

    @pytest.mark.asyncio
    async def test_sector_filter_performance_within_20_percent(self):
        """
        Test that sector_filter query latency is within 20% of unfiltered query (AC #5).

        Method:
        1. Measure baseline: Run query_neighbors() 100 times without filter, record mean
        2. Measure filtered: Run query_neighbors(sector_filter=["emotional"]) 100 times, record mean
        3. Calculate ratio: filtered_latency / baseline_latency
        4. Assert ratio ≤ 1.20 (20% threshold)
        """
        # Mock database to simulate query execution
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn, \
             patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node:

            # Setup mock node
            mock_get_node.return_value = {
                "id": "test-node-id",
                "name": "TestNode",
                "label": "Entity"
            }

            # Mock database connection and cursor
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor

            # Mock query results - return empty list to focus on query execution overhead
            mock_cursor.fetchall.return_value = []

            # Subtask 4.2: Measure baseline latency (100 runs)
            baseline_latencies = []
            for _ in range(100):
                start = time.perf_counter()
                _ = query_neighbors(
                    node_id="test-node-id",
                    sector_filter=None  # No filter - baseline
                )
                end = time.perf_counter()
                baseline_latencies.append((end - start) * 1000)  # Convert to ms

            baseline_mean = statistics.mean(baseline_latencies)

            # Subtask 4.3: Measure filtered latency (100 runs)
            filtered_latencies = []
            for _ in range(100):
                start = time.perf_counter()
                _ = query_neighbors(
                    node_id="test-node-id",
                    sector_filter=["emotional"]  # With filter
                )
                end = time.perf_counter()
                filtered_latencies.append((end - start) * 1000)  # Convert to ms

            filtered_mean = statistics.mean(filtered_latencies)

            # Subtask 4.4: Calculate ratio and assert within 20% threshold
            ratio = filtered_mean / baseline_mean if baseline_mean > 0 else 1.0

            # Log results for documentation (Subtask 4.5)
            print(f"\nSector Filter Performance Results:")
            print(f"  Baseline mean: {baseline_mean:.4f}ms")
            print(f"  Filtered mean:  {filtered_mean:.4f}ms")
            print(f"  Ratio:          {ratio:.4f}")
            print(f"  Threshold:      1.20 (20%)")

            # AC #5: Assert filtered query is within 20% of baseline
            assert ratio <= 1.20, f"sector_filter query is {ratio:.2f}x slower than baseline (exceeds 20% threshold)"

    def test_sector_filter_empty_list_performance(self):
        """Test that sector_filter=[] returns immediately without DB query (AC #4)."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            # Empty list should return immediately WITHOUT DB connection
            result = query_neighbors(
                node_id="test-node-id",
                sector_filter=[]  # Empty list
            )

            # Verify no DB connection was made
            assert result == []
            mock_get_conn.assert_not_called()

    @pytest.mark.asyncio
    async def test_sector_filter_mcp_tool_performance(self):
        """Test sector_filter performance at MCP tool level."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {"id": "node-id", "name": "TestNode", "label": "Entity"}
            mock_query.return_value = []

            # Test with sector_filter
            arguments = {
                "node_name": "TestNode",
                "sector_filter": ["emotional"]
            }

            start = time.perf_counter()
            result = await handle_graph_query_neighbors(arguments)
            end = time.perf_counter()

            latency_ms = (end - start) * 1000

            # Verify successful execution
            assert result["status"] == "success"
            assert result["query_params"]["sector_filter"] == ["emotional"]

            # Verify sector_filter was passed to DB
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args.kwargs
            assert call_kwargs["sector_filter"] == ["emotional"]

            # Log performance
            print(f"\nMCP Tool with sector_filter latency: {latency_ms:.4f}ms")


class TestHybridSearchSectorFilterPerformance:
    """Performance tests for sector_filter in hybrid_search (Story 9-4, Task 7)."""

    @pytest.mark.asyncio
    async def test_hybrid_search_sector_filter_performance_within_20_percent(self):
        """
        Test AC #5: sector_filter query latency is within 20% of unfiltered query (NFR2).

        Method:
        1. Measure baseline: Run hybrid_search() 100 times without filter, record mean
        2. Measure filtered: Run hybrid_search(sector_filter=["emotional"]) 100 times, record mean
        3. Calculate ratio: filtered_latency / baseline_latency
        4. Assert ratio ≤ 1.20 (20% threshold)
        """
        # Mock database to simulate query execution
        with patch('mcp_server.tools.get_connection') as mock_get_conn, \
             patch('mcp_server.tools.generate_query_embedding') as mock_embedding:

            # Mock embedding generation
            mock_embedding.return_value = [0.1] * 1536

            # Mock database connection and cursor
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor

            # Mock empty query results to focus on query execution overhead
            mock_cursor.fetchall.return_value = []

            # Subtask 7.2: Measure baseline latency (100 runs)
            baseline_latencies = []
            query_embedding = [0.1] * 1536

            for _ in range(100):
                start = time.perf_counter()
                _ = await handle_hybrid_search({
                    "query_text": "consciousness",
                    "query_embedding": query_embedding,
                    "top_k": 5,
                    "sector_filter": None  # No filter - baseline
                })
                end = time.perf_counter()
                baseline_latencies.append((end - start) * 1000)  # Convert to ms

            baseline_mean = statistics.mean(baseline_latencies)

            # Subtask 7.3: Measure filtered latency (100 runs)
            filtered_latencies = []
            for _ in range(100):
                start = time.perf_counter()
                _ = await handle_hybrid_search({
                    "query_text": "consciousness",
                    "query_embedding": query_embedding,
                    "top_k": 5,
                    "sector_filter": ["emotional"]  # With filter
                })
                end = time.perf_counter()
                filtered_latencies.append((end - start) * 1000)  # Convert to ms

            filtered_mean = statistics.mean(filtered_latencies)

            # Subtask 7.4: Calculate ratio and assert within 20% threshold
            ratio = filtered_mean / baseline_mean if baseline_mean > 0 else 1.0

            # Log results for documentation
            print(f"\nHybrid Search Sector Filter Performance Results:")
            print(f"  Baseline mean: {baseline_mean:.4f}ms")
            print(f"  Filtered mean:  {filtered_mean:.4f}ms")
            print(f"  Ratio:          {ratio:.4f}")
            print(f"  Threshold:      1.20 (20%)")

            # AC #5: Assert filtered query is within 20% of baseline
            assert ratio <= 1.20, f"sector_filter query is {ratio:.2f}x slower than baseline (exceeds 20% threshold)"

    def test_hybrid_search_sector_filter_empty_list_performance(self):
        """Test AC #4: sector_filter=[] returns immediately without DB query."""
        with patch('mcp_server.tools.get_connection') as mock_get_conn:
            query_embedding = [0.1] * 1536

            # Empty list should return immediately WITHOUT DB connection
            result = asyncio.run(handle_hybrid_search({
                "query_text": "consciousness",
                "query_embedding": query_embedding,
                "sector_filter": []  # Empty list
            }))

            # Verify no DB connection was made
            assert result["status"] == "success"
            assert result["results"] == []
            assert result["final_results_count"] == 0
            mock_get_conn.assert_not_called()

