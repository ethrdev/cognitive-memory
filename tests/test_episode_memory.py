"""
Unit tests for store_episode tool and add_episode function.

Tests cover:
- Valid episode insertion with all fields
- Reward validation (boundary values and invalid values)
- Empty query/reflection validation
- Embedding generation and verification
- Similarity search preparation with multiple episodes
- OpenAI API failure handling with retry logic
- Database constraint validation
- Cleanup and test data management
"""

import asyncio
import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add the mcp_server directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp_server.db.connection import (
    close_all_connections,
    get_connection,
    initialize_pool,
)
from mcp_server.tools import add_episode, handle_store_episode


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Initialize database connection pool for tests."""
    # Load environment variables
    from dotenv import load_dotenv

    load_dotenv(".env.development")

    # Initialize connection pool
    initialize_pool()

    yield

    # Clean up
    close_all_connections()


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_data():
    """Clean up test episodes after each test."""
    yield
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Delete test episodes created during tests
            cursor.execute(
                "DELETE FROM episode_memory WHERE query LIKE 'test_%' OR reflection LIKE 'test_%'"
            )
            conn.commit()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.data = [Mock()]
    mock_response.data[0].embedding = [0.1] * 1536  # 1536-dimensional test embedding
    mock_client.embeddings.create.return_value = mock_response
    return mock_client


class TestEpisodeMemoryInsertion:
    """Test Episode Memory Storage Logic."""

    def test_valid_episode_insertion(self, mock_openai_client):
        """Test 1: Valid episode insertion - verify episode added to DB with all fields."""
        with get_connection() as conn:
            # Clean up before test
            cursor = conn.cursor()
            cursor.execute("DELETE FROM episode_memory WHERE query LIKE 'test_%'")
            conn.commit()

            # Test data
            query = "test_valid_episode_query"
            reward = 0.8
            reflection = "test_reflection: Problem was solved successfully"

            # Add episode using mocked OpenAI client
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                result = asyncio.run(add_episode(query, reward, reflection, conn))

            # Verify result structure
            assert "id" in result
            assert "embedding_status" in result
            assert "query" in result
            assert "reward" in result
            assert "created_at" in result

            assert result["embedding_status"] == "success"
            assert result["query"] == query
            assert result["reward"] == reward
            assert isinstance(result["id"], int)
            assert result["id"] > 0

            # Verify episode was stored correctly in database
            cursor.execute(
                "SELECT query, reward, reflection, created_at FROM episode_memory WHERE id=%s;",
                (result["id"],),
            )
            stored_episode = cursor.fetchone()

            assert stored_episode["query"] == query
            assert stored_episode["reward"] == reward
            assert stored_episode["reflection"] == reflection
            assert stored_episode["created_at"] is not None

            conn.commit()

    def test_reward_validation_boundary_values(self, mock_openai_client):
        """Test 2: Reward validation - test boundary values (-1.0, 0.0, +1.0) and invalid (1.5, -1.5)."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM episode_memory WHERE query LIKE 'test_%'")
            conn.commit()

            # Test valid boundary values
            valid_rewards = [-1.0, 0.0, 1.0]
            for reward in valid_rewards:
                query = f"test_reward_validation_{reward}"
                reflection = f"test_reflection_for_reward_{reward}"

                with patch(
                    "mcp_server.tools.OpenAI", return_value=mock_openai_client
                ):
                    result = asyncio.run(add_episode(query, reward, reflection, conn))

                assert result["reward"] == reward
                assert result["embedding_status"] == "success"

            # Test invalid rewards - should fail at validation level
            invalid_rewards = [1.5, -1.5, 2.0, -2.0]
            for reward in invalid_rewards:
                result = asyncio.run(handle_store_episode(
                    {
                        "query": "test_invalid_reward",
                        "reward": reward,
                        "reflection": "test_reflection",
                    }
                ))

                assert result["embedding_status"] == "failed"
                assert "Reward out of range" in result["error"]

    def test_empty_query_reflection_validation(self):
        """Test 3: Empty query/reflection - verify error returned."""
        # Test empty query
        result = asyncio.run(handle_store_episode(
            {"query": "", "reward": 0.5, "reflection": "test_reflection"}
        ))

        assert result["embedding_status"] == "failed"
        assert "Invalid query parameter" in result["error"]

        # Test empty reflection
        result = asyncio.run(handle_store_episode(
            {"query": "test_query", "reward": 0.5, "reflection": ""}
        ))

        assert result["embedding_status"] == "failed"
        assert "Invalid reflection parameter" in result["error"]

        # Test whitespace-only strings
        result = asyncio.run(handle_store_episode(
            {"query": "   ", "reward": 0.5, "reflection": "test_reflection"}
        ))

        assert result["embedding_status"] == "failed"
        assert "Invalid query parameter" in result["error"]

    def test_embedding_generation_verification(self, mock_openai_client):
        """Test 4: Embedding generation - verify query is embedded (1536-dim vector)."""
        with get_connection() as conn:
            query = "test_embedding_query"
            reward = 0.7
            reflection = "test_embedding_reflection"

            # Test with mocked embedding
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                result = asyncio.run(add_episode(query, reward, reflection, conn))

            # Verify OpenAI API was called
            mock_openai_client.embeddings.create.assert_called_once_with(
                model="text-embedding-3-small", input=query, encoding_format="float"
            )

            # Verify embedding was stored in database
            cursor = conn.cursor()
            cursor.execute(
                "SELECT embedding FROM episode_memory WHERE id=%s;", (result["id"],)
            )
            stored_embedding = cursor.fetchone()["embedding"]

            # Should be a 1536-dimensional vector
            assert len(stored_embedding) == 1536
            # Check if all elements are numeric (float or numpy.float64)
            assert all(isinstance(x, (int, float)) or hasattr(x, '__float__') for x in stored_embedding)

            conn.commit()

    def test_similarity_search_preparation(self):
        """Test 5: Similarity search preparation - add 3 episodes, verify embeddings differ."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM episode_memory WHERE query LIKE 'test_similarity_%'"
            )
            conn.commit()

            # Create different mock embeddings for each query
            def create_mock_embedding(base_value):
                mock_client = Mock()
                mock_response = Mock()
                mock_response.data = [Mock()]
                mock_response.data[0].embedding = [base_value] * 1536
                mock_client.embeddings.create.return_value = mock_response
                return mock_client

            # Add 3 different episodes
            episodes = [
                ("test_similarity_1", 0.8, "reflection_1", 0.1),
                ("test_similarity_2", -0.3, "reflection_2", 0.2),
                ("test_similarity_3", 0.0, "reflection_3", 0.3),
            ]

            stored_ids = []
            for query, reward, reflection, embedding_value in episodes:
                with patch(
                    "mcp_server.tools.OpenAI",
                    return_value=create_mock_embedding(embedding_value),
                ):
                    result = asyncio.run(add_episode(query, reward, reflection, conn))
                    stored_ids.append(result["id"])

            # Verify all episodes have different embeddings
            cursor.execute(
                "SELECT id, query, embedding FROM episode_memory WHERE id = ANY(%s) ORDER BY id;",
                (stored_ids,),
            )
            stored_episodes = cursor.fetchall()

            assert len(stored_episodes) == 3

            # Embeddings should be different (convert to lists for comparison)
            embedding_1 = list(stored_episodes[0]["embedding"])
            embedding_2 = list(stored_episodes[1]["embedding"])
            embedding_3 = list(stored_episodes[2]["embedding"])

            assert embedding_1 != embedding_2
            assert embedding_2 != embedding_3
            assert embedding_1 != embedding_3

            # All should be 1536-dimensional
            assert all(len(ep["embedding"]) == 1536 for ep in stored_episodes)

            conn.commit()

    def test_api_failure_handling(self):
        """Test 6: API failure handling - mock OpenAI API failure, verify retry logic and episode NOT stored."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM episode_memory WHERE query LIKE 'test_api_failure_%'"
            )
            conn.commit()

            # Create mock client that fails on all calls
            mock_client = Mock()
            from openai import RateLimitError

            mock_client.embeddings.create.side_effect = RateLimitError(
                message="Rate limit exceeded",
                response=Mock(status_code=429),
                body={"error": {"message": "Rate limit exceeded"}},
            )

            # Test add_episode function directly
            query = "test_api_failure_query"
            reward = 0.5
            reflection = "test_api_failure_reflection"

            with patch("mcp_server.tools.OpenAI", return_value=mock_client):
                with pytest.raises(RuntimeError, match="Embedding generation failed"):
                    asyncio.run(add_episode(query, reward, reflection, conn))

            # Verify episode was NOT stored in database
            cursor.execute(
                "SELECT COUNT(*) as count FROM episode_memory WHERE query=%s;", (query,)
            )
            count = cursor.fetchone()["count"]
            assert count == 0, "Episode should not be stored when embedding fails"

            # Verify OpenAI API was called 3 times (retry logic)
            assert mock_client.embeddings.create.call_count == 3

    def test_database_constraint_validation(self):
        """Test 7: Verify reward validation happens at application level (no DB CHECK constraint).

        Note: The episode_memory table does NOT have a CHECK constraint on reward.
        Validation is enforced at the application level in handle_store_episode().
        This test verifies that direct DB inserts with out-of-range rewards succeed
        (because there's no DB constraint), confirming that validation must be done
        at the application layer.
        """
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM episode_memory WHERE query LIKE 'test_constraint_%'"
            )
            conn.commit()

            # Test direct database insert with out-of-range reward
            # This WILL succeed because there's no CHECK constraint at DB level
            query = "test_constraint_query"
            reflection = "test_constraint_reflection"
            out_of_range_reward = 2.0  # Outside valid range but no DB constraint

            # Direct insert bypasses application validation - should succeed at DB level
            cursor.execute(
                "INSERT INTO episode_memory (query, reward, reflection, embedding, created_at) VALUES (%s, %s, %s, %s, NOW()) RETURNING id",
                (query, out_of_range_reward, reflection, [0.1] * 1536),
            )
            result = cursor.fetchone()
            inserted_id = result["id"]

            # Verify the row was inserted (no DB constraint blocked it)
            cursor.execute("SELECT reward FROM episode_memory WHERE id = %s", (inserted_id,))
            stored = cursor.fetchone()
            assert stored["reward"] == out_of_range_reward

            # Clean up test data
            cursor.execute("DELETE FROM episode_memory WHERE id = %s", (inserted_id,))
            conn.commit()

    def test_mcp_tool_call_end_to_end_valid(self, mock_openai_client):
        """Integration test: Valid MCP tool call - success response format."""
        query = "test_mcp_tool_valid"
        reward = 0.8
        reflection = "test_mcp_tool_reflection"

        with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
            result = asyncio.run(handle_store_episode(
                {"query": query, "reward": reward, "reflection": reflection}
            ))

        # Verify success response format
        assert "id" in result
        assert "embedding_status" in result
        assert "query" in result
        assert "reward" in result
        assert "created_at" in result

        assert result["embedding_status"] == "success"
        assert result["query"] == query
        assert result["reward"] == reward
        assert isinstance(result["id"], int)
        assert result["id"] > 0

    def test_mcp_tool_call_end_to_end_invalid(self):
        """Integration test: Invalid MCP tool call - error response format."""
        # Test invalid reward
        result = asyncio.run(handle_store_episode(
            {
                "query": "test_mcp_tool_invalid",
                "reward": -2.0,  # Invalid reward
                "reflection": "test_reflection",
            }
        ))

        # Verify error response format
        assert "error" in result
        assert "details" in result
        assert "tool" in result
        assert "embedding_status" in result

        assert result["embedding_status"] == "failed"
        assert result["tool"] == "store_episode"
        assert "Reward out of range" in result["error"]

    def test_multiple_episodes_storage(self, mock_openai_client):
        """Integration test: Add 5 episodes → verify all stored in episode_memory table."""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM episode_memory WHERE query LIKE 'test_multiple_%'"
            )
            conn.commit()

            # Add 5 different episodes
            episodes = []
            for i in range(5):
                query = f"test_multiple_{i}"
                reward = (i - 2) * 0.4  # Range from -0.8 to 0.8
                reflection = f"test_reflection_{i}"
                episodes.append((query, reward, reflection))

            stored_ids = []
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                for query, reward, reflection in episodes:
                    result = asyncio.run(handle_store_episode(
                        {"query": query, "reward": reward, "reflection": reflection}
                    ))
                    stored_ids.append(result["id"])

            # Verify all episodes were stored
            cursor.execute(
                "SELECT id, query, reward, reflection FROM episode_memory WHERE id = ANY(%s) ORDER BY id;",
                (stored_ids,),
            )
            stored_episodes = cursor.fetchall()

            assert len(stored_episodes) == 5

            # Verify data integrity
            for i, episode in enumerate(stored_episodes):
                expected_query, expected_reward, expected_reflection = episodes[i]
                assert episode["query"] == expected_query
                assert episode["reward"] == expected_reward
                assert episode["reflection"] == expected_reflection

            conn.commit()
