"""
Integration tests for MCP Resources.

Tests all 5 MCP resources with real PostgreSQL database operations.
Validates functionality, error handling, and read-only behavior.
"""

import os
import uuid
from datetime import datetime, timedelta

import pytest
from openai import OpenAI

from mcp_server.db.connection import get_connection
from mcp_server.resources import (
    handle_episode_memory,
    handle_l0_raw,
    handle_l2_insights,
    handle_stale_memory,
    handle_working_memory,
)
from mcp_server.tools import get_embedding_with_retry


@pytest.fixture
async def setup_test_data():
    """Set up test data for all resources."""
    # Initialize OpenAI client for embeddings
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        pytest.skip("OpenAI API key not configured for integration tests")

    client = OpenAI(api_key=api_key)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Clear existing test data
        cursor.execute("DELETE FROM stale_memory")
        cursor.execute("DELETE FROM l0_raw")
        cursor.execute("DELETE FROM episode_memory")
        cursor.execute("DELETE FROM working_memory")
        cursor.execute("DELETE FROM l2_insights")
        conn.commit()

        # Insert test L2 insights
        embedding_1 = await get_embedding_with_retry(
            client, "machine learning algorithms"
        )
        embedding_2 = await get_embedding_with_retry(
            client, "neural network architectures"
        )
        embedding_3 = await get_embedding_with_retry(
            client, "data preprocessing techniques"
        )

        cursor.execute(
            """
            INSERT INTO l2_insights (content, embedding, source_ids)
            VALUES (%s, %s, %s), (%s, %s, %s), (%s, %s, %s)
            RETURNING id
        """,
            (
                "Machine learning requires careful feature engineering and model selection.",
                embedding_1,
                [1, 2],
                "Deep learning neural networks excel at pattern recognition tasks.",
                embedding_2,
                [3, 4],
                "Data preprocessing is crucial for successful machine learning pipelines.",
                embedding_3,
                [5, 6],
            ),
        )
        l2_ids = [row[0] for row in cursor.fetchall()]

        # Insert test working memory items (different timestamps)
        base_time = datetime.utcnow()
        cursor.execute(
            """
            INSERT INTO working_memory (content, importance, last_accessed, created_at)
            VALUES
                (%s, %s, %s, %s),
                (%s, %s, %s, %s),
                (%s, %s, %s, %s)
            RETURNING id
        """,
            (
                "Current task: Implement MCP resources",
                0.8,
                base_time - timedelta(hours=1),
                base_time - timedelta(hours=2),
                "Note: Test all error conditions",
                0.6,
                base_time - timedelta(minutes=30),
                base_time - timedelta(hours=1),
                "Priority: Complete Story 1.9",
                0.9,
                base_time,
                base_time - timedelta(minutes=15),
            ),
        )
        wm_ids = [row[0] for row in cursor.fetchall()]

        # Insert test episode memories
        query_embedding = await get_embedding_with_retry(
            client, "how to implement mcp resources"
        )
        cursor.execute(
            """
            INSERT INTO episode_memory (query, reward, reflection, embedding)
            VALUES
                (%s, %s, %s, %s),
                (%s, %s, %s, %s),
                (%s, %s, %s, %s)
            RETURNING id
        """,
            (
                "How to implement MCP server resources?",
                0.8,
                "Use @server.read_resource() decorator and register resource handlers",
                query_embedding,
                "What's the best way to handle database connections?",
                0.7,
                "Use context managers for proper connection pooling",
                await get_embedding_with_retry(
                    client, "database connection management"
                ),
                "How to test MCP resources effectively?",
                0.9,
                "Write integration tests with real database and mock external APIs",
                await get_embedding_with_retry(client, "testing mcp resources"),
            ),
        )
        episode_ids = [row[0] for row in cursor.fetchall()]

        # Insert test L0 raw data
        session_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO l0_raw (session_id, timestamp, speaker, content, metadata)
            VALUES
                (%s, %s, %s, %s, %s),
                (%s, %s, %s, %s, %s),
                (%s, %s, %s, %s, %s)
            RETURNING id
        """,
            (
                session_id,
                datetime.utcnow() - timedelta(hours=2),
                "user",
                "I need help implementing MCP resources",
                {"type": "question"},
                session_id,
                datetime.utcnow() - timedelta(hours=1, minutes=50),
                "assistant",
                "I'll help you implement the 5 required MCP resources",
                {"type": "response"},
                session_id,
                datetime.utcnow() - timedelta(hours=1, minutes=45),
                "user",
                "What are the 5 resources I need to implement?",
                {"type": "followup"},
            ),
        )
        l0_ids = [row[0] for row in cursor.fetchall()]

        # Insert test stale memory items
        cursor.execute(
            """
            INSERT INTO stale_memory (original_content, archived_at, importance, reason)
            VALUES
                (%s, %s, %s, %s),
                (%s, %s, %s, %s),
                (%s, %s, %s, %s)
            RETURNING id
        """,
            (
                "Old todo: Set up development environment",
                datetime.utcnow() - timedelta(days=7),
                0.3,
                "LRU_EVICTION",
                "Completed task: Database schema design",
                datetime.utcnow() - timedelta(days=5),
                0.8,
                "MANUAL_ARCHIVE",
                "Deprecated note: Use different approach",
                datetime.utcnow() - timedelta(days=3),
                0.5,
                "LRU_EVICTION",
            ),
        )
        stale_ids = [row[0] for row in cursor.fetchall()]

        conn.commit()

        yield {
            "l2_ids": l2_ids,
            "wm_ids": wm_ids,
            "episode_ids": episode_ids,
            "l0_ids": l0_ids,
            "stale_ids": stale_ids,
            "session_id": session_id,
        }

        # Cleanup
        cursor.execute("DELETE FROM stale_memory")
        cursor.execute("DELETE FROM l0_raw")
        cursor.execute("DELETE FROM episode_memory")
        cursor.execute("DELETE FROM working_memory")
        cursor.execute("DELETE FROM l2_insights")
        conn.commit()


class TestL2InsightsResource:
    """Test memory://l2-insights resource."""

    @pytest.mark.asyncio
    async def test_l2_insights_basic_search(self, setup_test_data):
        """Test basic L2 insights search with query."""
        result = await handle_l2_insights(
            "memory://l2-insights?query=machine%20learning&top_k=3"
        )

        assert isinstance(result, list)
        assert len(result) <= 3
        assert all(isinstance(item, dict) for item in result)

        if result:  # If results found
            assert all("id" in item for item in result)
            assert all("content" in item for item in result)
            assert all("score" in item for item in result)
            assert all("source_ids" in item for item in result)
            assert all(isinstance(item["score"], float) for item in result)
            assert all(0.0 <= item["score"] <= 1.0 for item in result)

    @pytest.mark.asyncio
    async def test_l2_insights_empty_query_error(self):
        """Test error handling for empty query."""
        result = await handle_l2_insights("memory://l2-insights?query=&top_k=5")

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid query parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_l2_insights_invalid_top_k_error(self):
        """Test error handling for invalid top_k parameter."""
        result = await handle_l2_insights(
            "memory://l2-insights?query=test&top_k=invalid"
        )

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid top_k parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_l2_insights_no_results(self, setup_test_data):
        """Test search query with no matching results."""
        result = await handle_l2_insights(
            "memory://l2-insights?query=quantum%20physics%20theory&top_k=5"
        )

        assert result == []  # Empty array for no results, not 404


class TestWorkingMemoryResource:
    """Test memory://working-memory resource."""

    @pytest.mark.asyncio
    async def test_working_memory_basic_read(self, setup_test_data):
        """Test basic working memory read."""
        result = await handle_working_memory("memory://working-memory")

        assert isinstance(result, list)
        assert len(result) >= 3  # We inserted 3 items

        # Check sorting by last_accessed DESC
        timestamps = [item["last_accessed"] for item in result]
        assert timestamps == sorted(timestamps, reverse=True)

        # Check required fields
        assert all(isinstance(item, dict) for item in result)
        assert all("id" in item for item in result)
        assert all("content" in item for item in result)
        assert all("importance" in item for item in result)
        assert all("last_accessed" in item for item in result)
        assert all("created_at" in item for item in result)
        assert all(isinstance(item["importance"], float) for item in result)
        assert all(0.0 <= item["importance"] <= 1.0 for item in result)

    @pytest.mark.asyncio
    async def test_working_memory_empty_state(self):
        """Test working memory when empty (after cleanup)."""
        result = await handle_working_memory("memory://working-memory")

        assert result == []  # Empty array for no results


class TestEpisodeMemoryResource:
    """Test memory://episode-memory resource."""

    @pytest.mark.asyncio
    async def test_episode_memory_basic_search(self, setup_test_data):
        """Test basic episode memory search."""
        result = await handle_episode_memory(
            "memory://episode-memory?query=mcp%20resources&min_similarity=0.5"
        )

        assert isinstance(result, list)
        assert len(result) <= 3  # FR009: Top-3 limit

        if result:  # If results found
            assert all(isinstance(item, dict) for item in result)
            assert all("id" in item for item in result)
            assert all("query" in item for item in result)
            assert all("reward" in item for item in result)
            assert all("reflection" in item for item in result)
            assert all("similarity" in item for item in result)
            assert all(isinstance(item["reward"], float) for item in result)
            assert all(isinstance(item["similarity"], float) for item in result)
            assert all(-1.0 <= item["reward"] <= 1.0 for item in result)
            assert all(0.0 <= item["similarity"] <= 1.0 for item in result)

    @pytest.mark.asyncio
    async def test_episode_memory_similarity_filtering(self, setup_test_data):
        """Test min_similarity filtering."""
        # High threshold - should return fewer or no results
        result_high = await handle_episode_memory(
            "memory://episode-memory?query=mcp%20resources&min_similarity=0.95"
        )

        # Low threshold - should return more results
        result_low = await handle_episode_memory(
            "memory://episode-memory?query=mcp%20resources&min_similarity=0.5"
        )

        assert isinstance(result_high, list)
        assert isinstance(result_low, list)
        assert len(result_high) <= len(result_low)

    @pytest.mark.asyncio
    async def test_episode_memory_empty_query_error(self):
        """Test error handling for empty query."""
        result = await handle_episode_memory(
            "memory://episode-memory?query=&min_similarity=0.7"
        )

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid query parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_episode_memory_invalid_min_similarity_error(self):
        """Test error handling for invalid min_similarity parameter."""
        result = await handle_episode_memory(
            "memory://episode-memory?query=test&min_similarity=invalid"
        )

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid min_similarity parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_episode_memory_no_results(self, setup_test_data):
        """Test search with no results above threshold."""
        result = await handle_episode_memory(
            "memory://episode-memory?query=unrelated%20query&min_similarity=0.99"
        )

        assert result == []  # Empty array for no results


class TestL0RawResource:
    """Test memory://l0-raw resource."""

    @pytest.mark.asyncio
    async def test_l0_raw_basic_read(self, setup_test_data):
        """Test basic L0 raw read."""
        result = await handle_l0_raw("memory://l0-raw")

        assert isinstance(result, list)
        assert len(result) >= 3  # We inserted 3 items

        # Check sorting by timestamp DESC
        timestamps = [item["timestamp"] for item in result]
        assert timestamps == sorted(timestamps, reverse=True)

        # Check required fields
        assert all(isinstance(item, dict) for item in result)
        assert all("id" in item for item in result)
        assert all("session_id" in item for item in result)
        assert all("timestamp" in item for item in result)
        assert all("speaker" in item for item in result)
        assert all("content" in item for item in result)
        assert all("metadata" in item for item in result)

    @pytest.mark.asyncio
    async def test_l0_raw_session_filter(self, setup_test_data):
        """Test filtering by session_id."""
        session_id = setup_test_data["session_id"]

        result = await handle_l0_raw(f"memory://l0-raw?session_id={session_id}")

        assert isinstance(result, list)
        assert len(result) == 3  # All 3 items belong to this session
        assert all(item["session_id"] == session_id for item in result)

    @pytest.mark.asyncio
    async def test_l0_raw_date_range_filter(self, setup_test_data):
        """Test filtering by date range."""
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)

        result = await handle_l0_raw(f"memory://l0-raw?date_range={yesterday}:{today}")

        assert isinstance(result, list)
        assert len(result) == 3  # All 3 items are from today

    @pytest.mark.asyncio
    async def test_l0_raw_limit_parameter(self, setup_test_data):
        """Test limit parameter."""
        result = await handle_l0_raw("memory://l0-raw?limit=2")

        assert isinstance(result, list)
        assert len(result) == 2  # Limited to 2 items

    @pytest.mark.asyncio
    async def test_l0_raw_invalid_session_id_error(self):
        """Test error handling for invalid session_id."""
        result = await handle_l0_raw("memory://l0-raw?session_id=invalid-uuid")

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid session_id parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_l0_raw_invalid_date_range_error(self):
        """Test error handling for invalid date range."""
        result = await handle_l0_raw("memory://l0-raw?date_range=invalid-format")

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid date_range parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_l0_raw_invalid_limit_error(self):
        """Test error handling for invalid limit."""
        result = await handle_l0_raw("memory://l0-raw?limit=invalid")

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid limit parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_l0_raw_no_results(self, setup_test_data):
        """Test with filters that return no results."""
        future_date = datetime.utcnow().date() + timedelta(days=1)
        result = await handle_l0_raw(
            f"memory://l0-raw?date_range={future_date}:{future_date}"
        )

        assert result == []  # Empty array for no results


class TestStaleMemoryResource:
    """Test memory://stale-memory resource."""

    @pytest.mark.asyncio
    async def test_stale_memory_basic_read(self, setup_test_data):
        """Test basic stale memory read."""
        result = await handle_stale_memory("memory://stale-memory")

        assert isinstance(result, list)
        assert len(result) >= 3  # We inserted 3 items

        # Check sorting by archived_at DESC
        timestamps = [item["archived_at"] for item in result]
        assert timestamps == sorted(timestamps, reverse=True)

        # Check required fields
        assert all(isinstance(item, dict) for item in result)
        assert all("id" in item for item in result)
        assert all("original_content" in item for item in result)
        assert all("archived_at" in item for item in result)
        assert all("importance" in item for item in result)
        assert all("reason" in item for item in result)

    @pytest.mark.asyncio
    async def test_stale_memory_importance_filter(self, setup_test_data):
        """Test filtering by importance_min."""
        # High threshold - should return fewer results
        result_high = await handle_stale_memory(
            "memory://stale-memory?importance_min=0.8"
        )

        # No threshold - should return all results
        result_all = await handle_stale_memory("memory://stale-memory")

        assert isinstance(result_high, list)
        assert isinstance(result_all, list)
        assert len(result_high) <= len(result_all)

        # All returned items should meet the threshold
        if result_high:
            assert all(item["importance"] >= 0.8 for item in result_high)

    @pytest.mark.asyncio
    async def test_stale_memory_invalid_importance_error(self):
        """Test error handling for invalid importance_min."""
        result = await handle_stale_memory(
            "memory://stale-memory?importance_min=invalid"
        )

        assert isinstance(result, dict)
        assert "error" in result
        assert "Invalid importance_min parameter" in result["error"]

    @pytest.mark.asyncio
    async def test_stale_memory_no_results(self, setup_test_data):
        """Test with importance threshold higher than any items."""
        result = await handle_stale_memory("memory://stale-memory?importance_min=1.0")

        assert result == []  # Empty array for no results


class TestReadOnlyVerification:
    """Critical test: Verify resources do NOT mutate database state."""

    @pytest.mark.asyncio
    async def test_read_only_verification(self, setup_test_data):
        """Test that all resources are read-only (no database mutations)."""
        with get_connection() as conn:
            cursor = conn.cursor()

            # Count rows before resource calls
            cursor.execute("SELECT COUNT(*) FROM l2_insights")
            l2_count_before = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM working_memory")
            wm_count_before = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM episode_memory")
            episode_count_before = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM l0_raw")
            l0_count_before = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stale_memory")
            stale_count_before = cursor.fetchone()[0]

        # Call all resources with various parameters
        await handle_l2_insights("memory://l2-insights?query=test&top_k=5")
        await handle_working_memory("memory://working-memory")
        await handle_episode_memory(
            "memory://episode-memory?query=test&min_similarity=0.7"
        )
        await handle_l0_raw("memory://l0-raw?limit=10")
        await handle_stale_memory("memory://stale-memory?importance_min=0.5")

        with get_connection() as conn:
            cursor = conn.cursor()

            # Count rows after resource calls
            cursor.execute("SELECT COUNT(*) FROM l2_insights")
            l2_count_after = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM working_memory")
            wm_count_after = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM episode_memory")
            episode_count_after = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM l0_raw")
            l0_count_after = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stale_memory")
            stale_count_after = cursor.fetchone()[0]

        # Assert no changes in row counts
        assert l2_count_before == l2_count_after, "L2 insights count changed"
        assert wm_count_before == wm_count_after, "Working memory count changed"
        assert (
            episode_count_before == episode_count_after
        ), "Episode memory count changed"
        assert l0_count_before == l0_count_after, "L0 raw count changed"
        assert stale_count_before == stale_count_after, "Stale memory count changed"


class TestErrorHandlingConsistency:
    """Test consistent error handling across all resources."""

    @pytest.mark.asyncio
    async def test_invalid_uri_format(self):
        """Test 404 for invalid resource URIs."""
        # This would be handled by the resource router, but we can test the pattern
        from mcp_server.resources import parse_resource_uri

        # Valid URI
        path, params = parse_resource_uri("memory://l2-insights?query=test")
        assert path == "memory://l2-insights"

        # Invalid URI (would return 404 at router level)
        path, params = parse_resource_uri("memory://invalid-resource")
        assert path == "memory://invalid-resource"

    @pytest.mark.asyncio
    async def test_parameter_validation_consistency(self):
        """Test that all resources validate parameters consistently."""
        # Test empty queries for resources that require them
        l2_result = await handle_l2_insights("memory://l2-insights?query=")
        episode_result = await handle_episode_memory("memory://episode-memory?query=")

        # Both should return 400-style errors
        assert isinstance(l2_result, dict) and "error" in l2_result
        assert isinstance(episode_result, dict) and "error" in episode_result

        # Test invalid numeric parameters
        l2_invalid_k = await handle_l2_insights(
            "memory://l2-insights?query=test&top_k=invalid"
        )
        episode_invalid_sim = await handle_episode_memory(
            "memory://episode-memory?query=test&min_similarity=invalid"
        )
        l0_invalid_limit = await handle_l0_raw("memory://l0-raw?limit=invalid")
        stale_invalid_imp = await handle_stale_memory(
            "memory://stale-memory?importance_min=invalid"
        )

        # All should return 400-style errors
        for result in [
            l2_invalid_k,
            episode_invalid_sim,
            l0_invalid_limit,
            stale_invalid_imp,
        ]:
            assert isinstance(result, dict) and "error" in result

    @pytest.mark.asyncio
    async def test_no_results_consistency(self):
        """Test that all resources return empty arrays for no results."""
        # These should all return empty arrays, not 404s
        l2_result = await handle_l2_insights(
            "memory://l2-insights?query=nonexistent-topic"
        )
        wm_result = await handle_working_memory(
            "memory://working-memory"
        )  # After cleanup
        episode_result = await handle_episode_memory(
            "memory://episode-memory?query=nonexistent-topic&min_similarity=0.99"
        )

        # All should be empty arrays
        assert l2_result == []
        assert wm_result == []  # Assuming cleanup
        assert episode_result == []
