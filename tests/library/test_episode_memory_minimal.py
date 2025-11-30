"""
Minimal unit tests for EpisodeMemory Library API.

Tests focus on the core functionality without complex mocking dependencies.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from cognitive_memory.store import EpisodeMemory
from cognitive_memory.types import EpisodeResult
from cognitive_memory.exceptions import ValidationError, StorageError, SearchError, EmbeddingError


class TestEpisodeMemoryStoreMinimal:
    """Test EpisodeMemory.store() method with minimal dependencies."""

    @patch("mcp_server.tools.add_episode", new_callable=AsyncMock)
    def test_store_success(self, mock_add_episode):
        """Test successful episode storage with valid inputs."""
        # Setup mocks
        mock_add_episode.return_value = {
            "id": 1,
            "embedding_status": "success",
            "query": "test query",
            "reward": 0.8,
            "created_at": "2025-11-30T12:00:00",
        }

        # Test store operation with mocked connection manager
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()
        mock_connection = MagicMock()
        episode_memory._connection_manager.get_connection.return_value.__enter__.return_value = mock_connection

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

    def test_store_validation_empty_query(self):
        """Test ValidationError for empty query."""
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()

        with pytest.raises(ValidationError) as exc_info:
            episode_memory.store(query="", reward=0.5, reflection="Lesson learned")

        assert "query must be a non-empty string" in str(exc_info.value)

    def test_store_validation_reward_too_high(self):
        """Test ValidationError for reward > 1.0."""
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()

        with pytest.raises(ValidationError) as exc_info:
            episode_memory.store(query="test", reward=1.5, reflection="test")

        assert "reward" in str(exc_info.value).lower()
        assert "outside valid range" in str(exc_info.value)

    def test_store_validation_reward_too_low(self):
        """Test ValidationError for reward < -1.0."""
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()

        with pytest.raises(ValidationError) as exc_info:
            episode_memory.store(query="test", reward=-1.5, reflection="test")

        assert "reward" in str(exc_info.value).lower()
        assert "outside valid range" in str(exc_info.value)


class TestEpisodeMemoryListMinimal:
    """Test EpisodeMemory.list() method with minimal dependencies."""

    def test_list_success(self):
        """Test successful listing of recent episodes."""
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()

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
        episode_memory._connection_manager.get_connection.return_value.__enter__.return_value = mock_connection

        results = episode_memory.list(limit=5)

        # Assertions
        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, EpisodeResult) for r in results)
        # Should be sorted by created_at DESC (newest first)
        assert results[0].query == "Latest query"
        assert results[1].query == "Earlier query"

    def test_list_validation_invalid_limit(self):
        """Test ValidationError for invalid limit."""
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()

        # Limit < 1
        with pytest.raises(ValidationError):
            episode_memory.list(limit=0)

    def test_list_empty_database(self):
        """Test list with empty database."""
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()

        mock_connection = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # No results
        mock_connection.cursor.return_value = mock_cursor
        episode_memory._connection_manager.get_connection.return_value.__enter__.return_value = mock_connection

        results = episode_memory.list(limit=10)

        assert results == []  # Should return empty list


class TestEpisodeMemorySearchMinimal:
    """Test EpisodeMemory.search() method with minimal dependencies."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_search_validation(self):
        """Test input validation for search method."""
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()

        # Empty query
        with pytest.raises(ValidationError):
            episode_memory.search(query="", min_similarity=0.7, limit=3)

        # Invalid similarity
        with pytest.raises(ValidationError):
            episode_memory.search(query="test", min_similarity=-0.1, limit=3)

        # Invalid limit
        with pytest.raises(ValidationError):
            episode_memory.search(query="test", min_similarity=0.7, limit=0)

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    def test_search_no_api_key(self):
        """Test EmbeddingError when OpenAI API key is not configured."""
        episode_memory = EpisodeMemory()
        episode_memory._connection_manager = MagicMock()

        with pytest.raises(EmbeddingError) as exc_info:
            episode_memory.search(query="test query", min_similarity=0.7, limit=3)

        assert "OpenAI API key not configured" in str(exc_info.value)