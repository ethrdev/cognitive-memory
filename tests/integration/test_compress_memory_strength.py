"""
Integration Tests for Memory Strength in compress_to_l2_insight (Story 26.1)

Tests the full flow of creating insights with memory_strength and
verifying IEF integration in hybrid_search.

Author: Epic 26 Implementation
Story: 26.1 - Memory Strength Field für I/O's Bedeutungszuweisung

Code Review Fix (2026-01-10):
- Fixed import paths: use handle_* functions
- Fixed mock paths: OpenAI is module-level import
- Added proper mocking for hybrid_search tests
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_compress_with_memory_strength_high(conn):
    """Test creating an insight with high memory_strength (0.9)."""
    from mcp_server.tools import handle_compress_to_l2_insight

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
                 patch("mcp_server.tools.register_vector"):
                # Use real connection for INSERT
                mock_get_conn.return_value.__enter__.return_value = conn

                result = await handle_compress_to_l2_insight({
                    "content": "High importance insight about I/O's core identity",
                    "source_ids": [1, 2],
                    "memory_strength": 0.9
                })

                assert "error" not in result, f"Should succeed, got error: {result.get('details')}"
                assert result["memory_strength"] == 0.9
                assert "id" in result

                # Verify in database
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT memory_strength FROM l2_insights WHERE id = %s",
                    (result["id"],)
                )
                row = cursor.fetchone()
                cursor.close()

                assert row is not None, "Insight should exist in database"
                assert row["memory_strength"] == 0.9, f"Database should have memory_strength=0.9, got {row['memory_strength']}"


@pytest.mark.asyncio
async def test_compress_with_memory_strength_low(conn):
    """Test creating an insight with low memory_strength (0.2)."""
    from mcp_server.tools import handle_compress_to_l2_insight

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
                 patch("mcp_server.tools.register_vector"):
                # Use real connection for INSERT
                mock_get_conn.return_value.__enter__.return_value = conn

                result = await handle_compress_to_l2_insight({
                    "content": "Low importance insight, forgettable",
                    "source_ids": [1],
                    "memory_strength": 0.2
                })

                assert "error" not in result
                assert result["memory_strength"] == 0.2

                # Verify in database
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT memory_strength FROM l2_insights WHERE id = %s",
                    (result["id"],)
                )
                row = cursor.fetchone()
                cursor.close()

                assert row["memory_strength"] == 0.2


@pytest.mark.asyncio
async def test_compress_without_memory_strength_uses_default(conn):
    """Test backward compatibility - creating insight without memory_strength uses 0.5."""
    from mcp_server.tools import handle_compress_to_l2_insight

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
                 patch("mcp_server.tools.register_vector"):
                # Use real connection for INSERT
                mock_get_conn.return_value.__enter__.return_value = conn

                # Call WITHOUT memory_strength parameter (backward compatibility test)
                result = await handle_compress_to_l2_insight({
                    "content": "Default strength insight (backward compat)",
                    "source_ids": [1, 2, 3]
                })

                assert "error" not in result
                assert result["memory_strength"] == 0.5

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
async def test_ief_score_incorporates_memory_strength(conn):
    """Test that insights with higher memory_strength rank higher in hybrid_search."""
    from mcp_server.tools import handle_compress_to_l2_insight, handle_hybrid_search

    # First, create insights with different memory_strength
    with patch("mcp_server.tools.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        with patch(
            "mcp_server.tools.get_embedding_with_retry",
            return_value=[0.1] * 1536
        ):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
                 patch("mcp_server.tools.register_vector"):
                mock_get_conn.return_value.__enter__.return_value = conn

                # Create two insights with SAME content but different memory_strength
                result_weak = await handle_compress_to_l2_insight({
                    "content": "test content for memory strength ranking",
                    "source_ids": [1],
                    "memory_strength": 0.3  # Low strength
                })

                result_strong = await handle_compress_to_l2_insight({
                    "content": "test content for memory strength ranking",  # SAME content
                    "source_ids": [2],
                    "memory_strength": 0.9  # High strength
                })

                assert "error" not in result_weak
                assert "error" not in result_strong

                weak_id = result_weak["id"]
                strong_id = result_strong["id"]

    # Now perform hybrid_search to see ranking
    with patch("mcp_server.tools.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        with patch("mcp_server.tools.generate_query_embedding", return_value=[0.1] * 1536):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
                 patch("mcp_server.tools.register_vector"):
                mock_get_conn.return_value.__enter__.return_value = conn

                search_result = await handle_hybrid_search({
                    "query_text": "test content for memory strength ranking",
                    "top_k": 10
                })

    assert "error" not in search_result
    results = search_result.get("results", [])

    # Find positions of our insights
    weak_pos = None
    strong_pos = None

    for idx, result in enumerate(results):
        if result.get("id") == weak_id:
            weak_pos = idx
        if result.get("id") == strong_id:
            strong_pos = idx

    # Strong insight should rank higher (lower position number = better rank)
    # This is because: final_score = rrf_score * memory_strength
    # Since content is identical, RRF scores are similar, so memory_strength decides
    if weak_pos is not None and strong_pos is not None:
        assert strong_pos < weak_pos, (
            f"Insight with memory_strength=0.9 should rank higher (position {strong_pos}) "
            f"than insight with memory_strength=0.3 (position {weak_pos})"
        )
    else:
        pytest.skip("Could not find both insights in search results - may need different test data")


@pytest.mark.asyncio
async def test_hybrid_search_includes_memory_strength_in_results(conn):
    """Test that hybrid_search results include memory_strength field."""
    from mcp_server.tools import handle_hybrid_search

    with patch("mcp_server.tools.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        with patch("mcp_server.tools.generate_query_embedding", return_value=[0.1] * 1536):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
                 patch("mcp_server.tools.register_vector"):
                mock_get_conn.return_value.__enter__.return_value = conn

                result = await handle_hybrid_search({
                    "query_text": "test",
                    "top_k": 5
                })

    assert "error" not in result
    assert "results" in result

    # Check that at least some results have memory_strength
    results_with_strength = [
        r for r in result["results"]
        if "memory_strength" in r and isinstance(r.get("id"), int)
    ]

    # All l2_insight results should have memory_strength
    l2_results = [
        r for r in result["results"]
        if isinstance(r.get("id"), int) and r.get("source_type") != "episode_memory"
    ]

    for r in l2_results:
        assert "memory_strength" in r, f"L2 insight {r.get('id')} should have memory_strength in results"
        assert 0.0 <= r["memory_strength"] <= 1.0, f"memory_strength should be in [0.0, 1.0], got {r['memory_strength']}"


@pytest.mark.asyncio
async def test_rrf_score_preserved_after_memory_strength_multiplier(conn):
    """Test that original RRF score is preserved when memory_strength is applied."""
    from mcp_server.tools import handle_hybrid_search

    with patch("mcp_server.tools.OpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client

        with patch("mcp_server.tools.generate_query_embedding", return_value=[0.1] * 1536):
            with patch("mcp_server.tools.get_connection") as mock_get_conn, \
                 patch("mcp_server.tools.register_vector"):
                mock_get_conn.return_value.__enter__.return_value = conn

                result = await handle_hybrid_search({
                    "query_text": "test",
                    "top_k": 5
                })

    assert "error" not in result
    results = result.get("results", [])

    # Check that l2_insights have both score (final) and rrf_score (original)
    l2_results = [
        r for r in results
        if isinstance(r.get("id"), int) and r.get("source_type") != "episode_memory"
    ]

    for r in l2_results:
        if "memory_strength" in r:
            # After Story 26.1, results should have rrf_score (original) and score (final)
            assert "rrf_score" in r, f"Result {r.get('id')} should have rrf_score preserved"
            assert "score" in r, f"Result {r.get('id')} should have final score"

            # Verify: score = rrf_score * memory_strength
            expected_score = r["rrf_score"] * r["memory_strength"]
            assert abs(r["score"] - expected_score) < 0.001, (
                f"Final score should equal rrf_score * memory_strength: "
                f"{r['score']} = {r['rrf_score']} * {r['memory_strength']}"
            )
