"""
Unit tests for EpisodeMemory Library API.

Tests cover store(), search(), and list() methods with comprehensive validation
and error handling following AC-5.6.1 through AC-5.6.6.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from cognitive_memory import MemoryStore
from cognitive_memory.store import EpisodeMemory
from cognitive_memory.types import EpisodeResult
from cognitive_memory.exceptions import ValidationError, StorageError, SearchError, EmbeddingError


class TestEpisodeMemoryStore:
    """Test EpisodeMemory.store() method."""

    @patch("mcp_server.tools.add_episode", new_callable=AsyncMock)
    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_success(self, mock_conn_manager, mock_add_episode):
        """Test successful episode storage with valid inputs."""
        # Setup mocks
        mock_add_episode.return_value = {
            "id": 1,
            "embedding_status": "success",
            "query": "test query",
            "reward": 0.8,
            "created_at": "2025-11-30T12:00:00",
        }

        mock_connection = MagicMock()
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        # Test store operation
        with EpisodeMemory() as episode_memory:
            result = episode_memory.store(
                query="test query",
                reward=0.8,
                reflection="Lesson learned"
            )

        # Assertions
        assert isinstance(result, EpisodeResult)
        assert result.id == 1
        assert result.query == "test query"
        assert result.reward == 0.8
        assert result.reflection == "Lesson learned"
        assert isinstance(result.created_at, datetime)

        # Verify MCP function was called correctly
        mock_add_episode.assert_called_once_with("test query", 0.8, "Lesson learned", mock_connection)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_validation_empty_query(self, mock_conn_manager):
        """Test ValidationError for empty query."""
        with EpisodeMemory() as episode_memory:
            with pytest.raises(ValidationError) as exc_info:
                episode_memory.store(query="", reward=0.5, reflection="Lesson learned")

        assert "query must be a non-empty string" in str(exc_info.value)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_validation_empty_reflection(self, mock_conn_manager):
        """Test ValidationError for empty reflection."""
        with EpisodeMemory() as episode_memory:
            with pytest.raises(ValidationError) as exc_info:
                episode_memory.store(query="Valid query", reward=0.5, reflection="")

        assert "reflection must be a non-empty string" in str(exc_info.value)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_validation_none_values(self, mock_conn_manager):
        """Test ValidationError for None values."""
        with EpisodeMemory() as episode_memory:
            # None query
            with pytest.raises(ValidationError):
                episode_memory.store(query=None, reward=0.5, reflection="Test")

            # None reflection
            with pytest.raises(ValidationError):
                episode_memory.store(query="Valid query", reward=0.5, reflection=None)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_validation_reward_too_high(self, mock_conn_manager):
        """Test ValidationError for reward > 1.0."""
        with EpisodeMemory() as episode_memory:
            with pytest.raises(ValidationError) as exc_info:
                episode_memory.store(query="test", reward=1.5, reflection="test")

        assert "reward" in str(exc_info.value).lower()
        assert "outside valid range" in str(exc_info.value)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_validation_reward_too_low(self, mock_conn_manager):
        """Test ValidationError for reward < -1.0."""
        with EpisodeMemory() as episode_memory:
            with pytest.raises(ValidationError) as exc_info:
                episode_memory.store(query="test", reward=-1.5, reflection="test")

        assert "reward" in str(exc_info.value).lower()
        assert "outside valid range" in str(exc_info.value)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_validation_invalid_reward_type(self, mock_conn_manager):
        """Test ValidationError for non-numeric reward."""
        with EpisodeMemory() as episode_memory:
            with pytest.raises(ValidationError) as exc_info:
                episode_memory.store(query="test", reward="invalid", reflection="test")

        assert "reward must be a number" in str(exc_info.value)

    @patch("mcp_server.tools.add_episode", new_callable=AsyncMock)
    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_embedding_error(self, mock_conn_manager, mock_add_episode):
        """Test EmbeddingError when embedding generation fails."""
        mock_add_episode.side_effect = RuntimeError("Embedding generation failed")

        mock_connection = MagicMock()
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        with EpisodeMemory() as episode_memory:
            with pytest.raises(EmbeddingError) as exc_info:
                episode_memory.store(query="test query", reward=0.8, reflection="Lesson learned")

        assert "embedding" in str(exc_info.value).lower()

    @patch("mcp_server.tools.add_episode", new_callable=AsyncMock)
    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_storage_error(self, mock_conn_manager, mock_add_episode):
        """Test StorageError when MCP function returns error."""
        mock_add_episode.return_value = {"error": "Database constraint violation"}

        mock_connection = MagicMock()
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        with EpisodeMemory() as episode_memory:
            with pytest.raises(StorageError) as exc_info:
                episode_memory.store(query="test query", reward=0.8, reflection="Lesson learned")

        assert "Episode storage failed" in str(exc_info.value)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_store_connection_error(self, mock_conn_manager):
        """Test StorageError when database connection fails."""
        mock_conn_manager.return_value.get_connection.side_effect = Exception("Connection failed")

        with EpisodeMemory() as episode_memory:
            with pytest.raises(StorageError) as exc_info:
                episode_memory.store(query="test query", reward=0.8, reflection="Lesson learned")

        assert "Database connection failed" in str(exc_info.value)


class TestEpisodeMemorySearch:
    """Test EpisodeMemory.search() method."""

    @patch("mcp_server.tools.get_embedding_with_retry", new_callable=AsyncMock)
    @patch("cognitive_memory.store.ConnectionManager")
    @patch("pgvector.psycopg2.register_vector")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_search_success(self, mock_register_vector, mock_conn_manager, mock_embedding):
        """Test successful similarity search."""
        # Setup mocks
        mock_embedding.return_value = [0.1] * 1536  # Mock embedding vector

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "query": "Caching Strategy",
                "reward": 0.9,
                "reflection": "Use TTL-based invalidation",
                "created_at": datetime(2025, 11, 30, 12, 0, 0),
            },
            {
                "id": 2,
                "query": "Cache Invalidation",
                "reward": 0.7,
                "reflection": "Implement proper cache clearing",
                "created_at": datetime(2025, 11, 30, 11, 0, 0),
            },
        ]
        mock_connection.cursor.return_value = mock_cursor
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        # Test search
        with EpisodeMemory() as episode_memory:
            results = episode_memory.search("Caching", min_similarity=0.5, limit=5)

        # Assertions
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, EpisodeResult) for r in results)
        assert results[0].query == "Caching Strategy"
        assert results[1].query == "Cache Invalidation"

        # Verify pgvector registration was called
        mock_register_vector.assert_called_once_with(mock_connection)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_search_validation_empty_query(self, mock_conn_manager):
        """Test ValidationError for empty search query."""
        with EpisodeMemory() as episode_memory:
            with pytest.raises(ValidationError) as exc_info:
                episode_memory.search(query="", min_similarity=0.7, limit=3)

        assert "query must be a non-empty string" in str(exc_info.value)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_search_validation_invalid_similarity(self, mock_conn_manager):
        """Test ValidationError for invalid min_similarity."""
        with EpisodeMemory() as episode_memory:
            # Negative similarity
            with pytest.raises(ValidationError):
                episode_memory.search(query="test", min_similarity=-0.1, limit=3)

            # Similarity > 1.0
            with pytest.raises(ValidationError):
                episode_memory.search(query="test", min_similarity=1.1, limit=3)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_search_validation_invalid_limit(self, mock_conn_manager):
        """Test ValidationError for invalid limit."""
        with EpisodeMemory() as episode_memory:
            # Non-integer limit
            with pytest.raises(ValidationError):
                episode_memory.search(query="test", min_similarity=0.7, limit="invalid")

            # Limit < 1
            with pytest.raises(ValidationError):
                episode_memory.search(query="test", min_similarity=0.7, limit=0)

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    @patch("cognitive_memory.store.ConnectionManager")
    def test_search_no_api_key(self, mock_conn_manager):
        """Test EmbeddingError when OpenAI API key is not configured."""
        with EpisodeMemory() as episode_memory:
            with pytest.raises(EmbeddingError) as exc_info:
                episode_memory.search(query="test query", min_similarity=0.7, limit=3)

        assert "OpenAI API key not configured" in str(exc_info.value)

    @patch("mcp_server.tools.get_embedding_with_retry", new_callable=AsyncMock)
    @patch("cognitive_memory.store.ConnectionManager")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_search_embedding_error(self, mock_conn_manager, mock_embedding):
        """Test EmbeddingError when embedding generation fails."""
        mock_embedding.side_effect = RuntimeError("Embedding generation failed")

        mock_connection = MagicMock()
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        with EpisodeMemory() as episode_memory:
            with pytest.raises(EmbeddingError) as exc_info:
                episode_memory.search(query="test query", min_similarity=0.7, limit=3)

        assert "Embedding generation failed" in str(exc_info.value)

    @patch("mcp_server.tools.get_embedding_with_retry", new_callable=AsyncMock)
    @patch("cognitive_memory.store.ConnectionManager")
    @patch("pgvector.psycopg2.register_vector")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_search_empty_results(self, mock_register_vector, mock_conn_manager, mock_embedding):
        """Test search with no similar episodes found."""
        mock_embedding.return_value = [0.1] * 1536

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # No results
        mock_connection.cursor.return_value = mock_cursor
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        with EpisodeMemory() as episode_memory:
            results = episode_memory.search("nonexistent topic", min_similarity=0.9, limit=5)

        assert results == []  # Should return empty list

        # Verify pgvector registration was called
        mock_register_vector.assert_called_once_with(mock_connection)


class TestEpisodeMemoryList:
    """Test EpisodeMemory.list() method."""

    @patch("cognitive_memory.store.ConnectionManager")
    def test_list_success(self, mock_conn_manager):
        """Test successful listing of recent episodes."""
        # Setup mocks
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 2,
                "query": "Latest query",
                "reward": 0.8,
                "reflection": "Latest reflection",
                "created_at": datetime(2025, 11, 30, 12, 0, 0),
            },
            {
                "id": 1,
                "query": "Earlier query",
                "reward": 0.6,
                "reflection": "Earlier reflection",
                "created_at": datetime(2025, 11, 30, 11, 0, 0),
            },
        ]
        mock_connection.cursor.return_value = mock_cursor
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        # Test list
        with EpisodeMemory() as episode_memory:
            results = episode_memory.list(limit=5)

        # Assertions
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, EpisodeResult) for r in results)
        # Should be sorted by created_at DESC (newest first)
        assert results[0].query == "Latest query"
        assert results[1].query == "Earlier query"

    @patch("cognitive_memory.store.ConnectionManager")
    def test_list_validation_invalid_limit(self, mock_conn_manager):
        """Test ValidationError for invalid limit."""
        with EpisodeMemory() as episode_memory:
            # Non-integer limit
            with pytest.raises(ValidationError):
                episode_memory.list(limit="invalid")

            # Limit < 1
            with pytest.raises(ValidationError):
                episode_memory.list(limit=0)

    @patch("cognitive_memory.store.ConnectionManager")
    def test_list_empty_database(self, mock_conn_manager):
        """Test list with empty database."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # No results
        mock_connection.cursor.return_value = mock_cursor
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        with EpisodeMemory() as episode_memory:
            results = episode_memory.list(limit=10)

        assert results == []  # Should return empty list

    @patch("cognitive_memory.store.ConnectionManager")
    def test_list_limit_respected(self, mock_conn_manager):
        """Test that limit parameter is respected."""
        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        # Return 5 results but ask for limit 3
        mock_cursor.fetchall.return_value = [
            {"id": i, "query": f"Query {i}", "reward": 0.5, "reflection": f"Reflection {i}",
             "created_at": datetime(2025, 11, 30, i, 0, 0)} for i in range(5, 0, -1)
        ]
        mock_connection.cursor.return_value = mock_cursor
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        with EpisodeMemory() as episode_memory:
            results = episode_memory.list(limit=3)

        # Database should be queried with limit 3
        mock_cursor.execute.assert_called_once()
        args, kwargs = mock_cursor.execute.call_args
        assert "LIMIT %s" in args[0]
        assert args[1] == (3,)


class TestEpisodeMemoryIntegration:
    """Integration tests for EpisodeMemory workflow."""

    @patch("mcp_server.tools.add_episode", new_callable=AsyncMock)
    @patch("mcp_server.tools.get_embedding_with_retry", new_callable=AsyncMock)
    @patch("cognitive_memory.store.ConnectionManager")
    @patch("pgvector.psycopg2.register_vector")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_store_search_list_workflow(self, mock_register_vector, mock_conn_manager, mock_embedding, mock_add_episode):
        """Test integration workflow: store → search → list."""
        # Setup store mock
        mock_add_episode.return_value = {
            "id": 1,
            "embedding_status": "success",
            "query": "Caching Strategy",
            "reward": 0.9,
            "created_at": "2025-11-30T12:00:00",
        }

        # Setup search mock
        mock_embedding.return_value = [0.1] * 1536

        # Setup list mock
        mock_connection = MagicMock()
        mock_cursor = MagicMock()

        # Mock search results
        mock_cursor.fetchall.side_effect = [
            [  # First call: search results
                {
                    "id": 1,
                    "query": "Caching Strategy",
                    "reward": 0.9,
                    "reflection": "Use TTL-based invalidation",
                    "created_at": datetime(2025, 11, 30, 12, 0, 0),
                }
            ],
            [  # Second call: list results
                {
                    "id": 1,
                    "query": "Caching Strategy",
                    "reward": 0.9,
                    "reflection": "Use TTL-based invalidation",
                    "created_at": datetime(2025, 11, 30, 12, 0, 0),
                }
            ]
        ]

        mock_connection.cursor.return_value = mock_cursor
        mock_conn_manager.return_value.get_connection.return_value.__enter__.return_value = mock_connection

        # Test workflow
        with EpisodeMemory() as episode_memory:
            # Store an episode
            stored = episode_memory.store(
                query="Caching Strategy",
                reward=0.9,
                reflection="Use TTL-based invalidation"
            )
            assert isinstance(stored, EpisodeResult)

            # Search for similar episodes
            search_results = episode_memory.search("Caching", min_similarity=0.5, limit=5)
            assert isinstance(search_results, list)
            assert len(search_results) >= 1

            # List recent episodes
            list_results = episode_memory.list(limit=10)
            assert isinstance(list_results, list)
            assert len(list_results) >= 1

        # Verify all database operations were called
        assert mock_cursor.execute.call_count == 2  # search + list
        # Verify pgvector registration was called once
        mock_register_vector.assert_called_once()