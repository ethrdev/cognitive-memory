"""
Regression Tests for Story 26.1 (Memory Strength)

Tests ensure backward compatibility and that existing functionality
is not broken by the memory_strength feature.

Author: Epic 26 Implementation
Story: 26.1 - Memory Strength Field für I/O's Bedeutungszuweisung
"""

import pytest


@pytest.mark.asyncio
async def test_io_save_still_works(conn):
    """Test that existing /io-save calls (compress without memory_strength) don't break."""
    from mcp_server.tools import handle_compress_to_l2_insight
    from unittest.mock import patch, AsyncMock

    # Mock OpenAI client (module-level import)
    with patch("mcp_server.tools.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        # Mock embedding generation (module-level import)
        with patch(
            "mcp_server.tools.get_embedding_with_retry",
            return_value=[0.1] * 1536
        ):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
             patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                # Use real connection
                mock_get_conn.return_value.__enter__.return_value = conn

                # Call exactly as /io-save does (WITHOUT memory_strength parameter)
                result = await handle_compress_to_l2_insight({
                    "content": "Test backward compatibility with /io-save",
                    "source_ids": [1, 2, 3]
                })

                assert "error" not in result, f"/io-save call should succeed, got: {result.get('details')}"
                assert "id" in result, "Should return insight ID"
                assert result["memory_strength"] == 0.5, "Should use default 0.5"

                # Verify in database
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT memory_strength FROM l2_insights WHERE id = %s",
                    (result["id"],)
                )
                row = cursor.fetchone()
                cursor.close()

                assert row["memory_strength"] == 0.5


@pytest.mark.asyncio
async def test_existing_insights_unaffected(conn):
    """Test that insights created before Migration 023 still work correctly."""
    from mcp_server.tools import hybrid_search

    # Create an insight without explicit memory_strength (simulating old behavior)
    from mcp_server.tools import compress_to_l2_insight
    from unittest.mock import patch, AsyncMock

    with patch("mcp_server.tools.handle_compress_to_l2_insight.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        with patch(
            "mcp_server.tools.handle_compress_to_l2_insight.get_embedding_with_retry",
            return_value=[0.1] * 1536
        ):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
             patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                mock_get_conn.return_value.__enter__.return_value = conn

                result = await handle_compress_to_l2_insight({
                    "content": "Old insight created before Migration 023",
                    "source_ids": [1]
                })

                assert "error" not in result
                insight_id = result["id"]

    # Verify the insight appears in search results with correct memory_strength
    search_result = await hybrid_search({
        "query_text": "old insight created",
        "top_k": 10
    })

    assert "error" not in search_result

    # Find our insight in results
    our_insight = None
    for r in search_result["results"]:
        if r.get("id") == insight_id:
            our_insight = r
            break

    assert our_insight is not None, "Old insight should appear in search results"
    assert our_insight.get("memory_strength") == 0.5, "Old insight should have default memory_strength=0.5"


@pytest.mark.asyncio
async def test_hybrid_search_still_works_without_memory_strength(conn):
    """Test that hybrid_search works even if some insights don't have memory_strength set."""
    from mcp_server.tools import handle_hybrid_search

    # Perform a search
    result = await handle_hybrid_search({
        "query_text": "test query",
        "top_k": 5
    })

    assert "error" not in result
    assert "results" in result
    assert isinstance(result["results"], list)


@pytest.mark.asyncio
async def test_metadata_includes_memory_strength(conn):
    """Test that metadata JSONB field includes memory_strength."""
    from mcp_server.tools import compress_to_l2_insight
    from unittest.mock import patch, AsyncMock
    import json

    with patch("mcp_server.tools.handle_compress_to_l2_insight.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        with patch(
            "mcp_server.tools.handle_compress_to_l2_insight.get_embedding_with_retry",
            return_value=[0.1] * 1536
        ):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
             patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                mock_get_conn.return_value.__enter__.return_value = conn

                result = await handle_compress_to_l2_insight({
                    "content": "Test metadata includes memory_strength",
                    "source_ids": [1],
                    "memory_strength": 0.7
                })

                assert "error" not in result

                # Verify metadata in database
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT metadata FROM l2_insights WHERE id = %s",
                    (result["id"],)
                )
                row = cursor.fetchone()
                cursor.close()

                assert row is not None
                metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]

                # Memory strength should be in both metadata column and dedicated column
                assert "memory_strength" in metadata, "metadata should include memory_strength"
                assert metadata["memory_strength"] == 0.7


@pytest.mark.asyncio
async def test_multiple_insights_different_strengths(conn):
    """Test creating multiple insights with different memory_strength values."""
    from mcp_server.tools import compress_to_l2_insight
    from unittest.mock import patch, AsyncMock

    strengths = [0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    created_ids = []

    with patch("mcp_server.tools.handle_compress_to_l2_insight.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        with patch(
            "mcp_server.tools.handle_compress_to_l2_insight.get_embedding_with_retry",
            return_value=[0.1] * 1536
        ):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
             patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                mock_get_conn.return_value.__enter__.return_value = conn

                for strength in strengths:
                    result = await handle_compress_to_l2_insight({
                        "content": f"Insight with strength {strength}",
                        "source_ids": [1],
                        "memory_strength": strength
                    })

                    assert "error" not in result, f"Should succeed with strength={strength}"
                    assert result["memory_strength"] == strength
                    created_ids.append(result["id"])

    # Verify all in database
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, memory_strength FROM l2_insights WHERE id = ANY(%s)",
        (created_ids,)
    )
    rows = cursor.fetchall()
    cursor.close()

    assert len(rows) == len(strengths), "All insights should be in database"

    for row in rows:
        assert row["id"] in created_ids
        assert row["memory_strength"] in strengths


def test_migration_does_not_affect_other_tables(conn):
    """Test that Migration 023 only modifies l2_insights table."""
    cursor = conn.cursor()

    # Verify other tables are untouched
    tables_to_check = [
        "l0_raw",
        "working_memory",
        "episode_memory",
        "edges",
        "nodes"
    ]

    for table in tables_to_check:
        cursor.execute(
            f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{table}' AND column_name = 'memory_strength'
            """
        )
        row = cursor.fetchone()

        # memory_strength should NOT be in these tables
        assert row is None, f"Table {table} should not have memory_strength column"

    cursor.close()


@pytest.mark.asyncio
async def test_search_performance_with_memory_strength(conn):
    """Test that hybrid_search performance is not significantly impacted."""
    import time
    from mcp_server.tools import hybrid_search

    # Measure search time
    start_time = time.time()
    result = await hybrid_search({
        "query_text": "performance test",
        "top_k": 10
    })
    end_time = time.time()

    search_time = end_time - start_time

    assert "error" not in result
    # Search should complete in reasonable time (< 5 seconds for small dataset)
    assert search_time < 5.0, f"Search took {search_time:.2f}s, should be < 5s"


@pytest.mark.asyncio
async def test_memory_strength_boundary_values(conn):
    """Test that boundary values (0.0 and 1.0) work correctly."""
    from mcp_server.tools import compress_to_l2_insight
    from unittest.mock import patch, AsyncMock

    with patch("mcp_server.tools.handle_compress_to_l2_insight.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        with patch(
            "mcp_server.tools.handle_compress_to_l2_insight.get_embedding_with_retry",
            return_value=[0.1] * 1536
        ):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
             patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                mock_get_conn.return_value.__enter__.return_value = conn

                # Test 0.0 (weakest)
                result_0 = await handle_compress_to_l2_insight({
                    "content": "Weakest possible insight",
                    "source_ids": [1],
                    "memory_strength": 0.0
                })
                assert "error" not in result_0
                assert result_0["memory_strength"] == 0.0

                # Test 1.0 (strongest)
                result_1 = await handle_compress_to_l2_insight({
                    "content": "Strongest possible insight",
                    "source_ids": [1],
                    "memory_strength": 1.0
                })
                assert "error" not in result_1
                assert result_1["memory_strength"] == 1.0
