"""
ATDD Tests: L2 Insight Storage Library API (Story 5.4)

These tests verify store.store_insight() functionality:
- Basic insight storage with embedding
- Fidelity score calculation
- Validation of inputs
- InsightResult dataclass

Status: RED Phase (store_insight not yet implemented)
Risk: R-003 - API divergence between Library and MCP
Priority: P0 - Core storage functionality
"""

import os
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest


class TestStoreInsightBasic:
    """P0: Verify basic insight storage functionality."""

    @pytest.fixture
    def mock_store(self):
        """Create a store with mocked database and OpenAI."""
        from cognitive_memory import MemoryStore

        # Mock embedding response
        mock_embedding = [0.1] * 1536  # 1536-dimensional mock embedding

        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost/test_db",
            "OPENAI_API_KEY": "test-key-12345"
        }):
            with patch('cognitive_memory.store.get_embedding_with_retry') as mock_get_embedding:
                with patch('cognitive_memory.store.get_connection') as mock_get_connection:
                    with patch('cognitive_memory.store.register_vector'):
                        # Mock embedding generation
                        mock_get_embedding.return_value = mock_embedding

                        # Mock database connection and cursor
                        mock_conn = MagicMock()
                        mock_cursor = MagicMock()
                        mock_conn.cursor.return_value = mock_cursor
                        mock_get_connection.return_value.__enter__.return_value = mock_conn

                        # Mock successful INSERT with ID and timestamp
                        mock_cursor.fetchone.return_value = {
                            "id": 123,
                            "created_at": datetime.now()
                        }

                        store = MemoryStore.from_env()
                        store.connect()
                        yield store

    def test_store_insight_returns_insight_result(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: calling store.store_insight() with valid parameters
        THEN: returns InsightResult dataclass

        Story: 5.4 - L2 Insight Storage
        """
        from cognitive_memory import InsightResult

        result = mock_store.store_insight(
            content="User prefers direct communication style.",
            source_ids=[1, 2, 3],
        )

        assert isinstance(result, InsightResult)
        assert hasattr(result, "id")
        assert hasattr(result, "embedding_status")
        assert hasattr(result, "fidelity_score")
        assert hasattr(result, "created_at")

    def test_store_insight_generates_embedding(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: storing an insight
        THEN: embedding is automatically generated via OpenAI

        Story: 5.4 - Automatic embedding generation
        """
        result = mock_store.store_insight(
            content="Test insight content for embedding verification.",
            source_ids=[1],
        )

        # Embedding should be generated successfully
        assert result.embedding_status == "success"

    def test_store_insight_calculates_fidelity_score(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: storing an insight
        THEN: fidelity score is calculated (0.0 to 1.0)

        Story: 5.4 - Fidelity score calculation
        """
        result = mock_store.store_insight(
            content="Test insight for fidelity check.", source_ids=[1, 2]
        )

        assert isinstance(result.fidelity_score, float)
        assert 0.0 <= result.fidelity_score <= 1.0

    def test_store_insight_returns_valid_id(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: storing an insight
        THEN: returns a positive integer ID

        Story: 5.4 - ID assignment
        """
        result = mock_store.store_insight(
            content="Test insight for ID verification.", source_ids=[]
        )

        assert isinstance(result.id, int)
        assert result.id > 0


class TestStoreInsightWithMetadata:
    """P0: Verify metadata handling in insight storage."""

    @pytest.fixture
    def mock_store(self):
        """Create a store with mocked database and OpenAI."""
        from cognitive_memory import MemoryStore

        # Mock embedding response
        mock_embedding = [0.1] * 1536  # 1536-dimensional mock embedding

        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost/test_db",
            "OPENAI_API_KEY": "test-key-12345"
        }):
            with patch('cognitive_memory.store.get_embedding_with_retry') as mock_get_embedding:
                with patch('cognitive_memory.store.get_connection') as mock_get_connection:
                    with patch('cognitive_memory.store.register_vector'):
                        # Mock embedding generation
                        mock_get_embedding.return_value = mock_embedding

                        # Mock database connection and cursor
                        mock_conn = MagicMock()
                        mock_cursor = MagicMock()
                        mock_conn.cursor.return_value = mock_cursor
                        mock_get_connection.return_value.__enter__.return_value = mock_conn

                        # Mock successful INSERT with ID and timestamp
                        mock_cursor.fetchone.return_value = {
                            "id": 456,
                            "created_at": datetime.now()
                        }

                        store = MemoryStore.from_env()
                        store.connect()
                        yield store

    def test_store_insight_with_metadata(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: storing insight with metadata
        THEN: metadata is stored alongside content

        Story: 5.4 - Metadata support
        """
        metadata = {"source": "test", "category": "preference", "confidence": 0.9}

        result = mock_store.store_insight(
            content="Test insight with metadata.",
            source_ids=[1],
            metadata=metadata,
        )

        assert result.id > 0
        assert result.embedding_status == "success"

    def test_store_insight_without_metadata(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: storing insight without metadata parameter
        THEN: works correctly (metadata is optional)

        Story: 5.4 - Optional metadata
        """
        result = mock_store.store_insight(
            content="Test insight without metadata.", source_ids=[1]
        )

        assert result.id > 0


class TestStoreInsightValidation:
    """P0: Verify input validation for store_insight."""

    @pytest.fixture
    def mock_store(self):
        """Create a store with mocked database and OpenAI."""
        from cognitive_memory import MemoryStore

        # Mock embedding response
        mock_embedding = [0.1] * 1536  # 1536-dimensional mock embedding

        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost/test_db",
            "OPENAI_API_KEY": "test-key-12345"
        }):
            with patch('cognitive_memory.store.get_embedding_with_retry') as mock_get_embedding:
                with patch('cognitive_memory.store.get_connection') as mock_get_connection:
                    with patch('cognitive_memory.store.register_vector'):
                        # Mock embedding generation
                        mock_get_embedding.return_value = mock_embedding

                        # Mock database connection and cursor
                        mock_conn = MagicMock()
                        mock_cursor = MagicMock()
                        mock_conn.cursor.return_value = mock_cursor
                        mock_get_connection.return_value.__enter__.return_value = mock_conn

                        # Mock successful INSERT with ID and timestamp
                        mock_cursor.fetchone.return_value = {
                            "id": 789,
                            "created_at": datetime.now()
                        }

                        store = MemoryStore.from_env()
                        store.connect()
                        yield store

    def test_store_insight_rejects_empty_content(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: calling store_insight with empty content
        THEN: raises ValidationError

        Story: 5.4 - Content validation
        """
        from cognitive_memory.exceptions import ValidationError

        with pytest.raises(ValidationError):
            mock_store.store_insight(content="", source_ids=[1])

    def test_store_insight_rejects_whitespace_only_content(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: calling store_insight with whitespace-only content
        THEN: raises ValidationError

        Story: 5.4 - Content validation
        """
        from cognitive_memory.exceptions import ValidationError

        with pytest.raises(ValidationError):
            mock_store.store_insight(content="   \n\t  ", source_ids=[1])

    def test_store_insight_accepts_empty_source_ids(self, mock_store):
        """
        GIVEN: MemoryStore instance
        WHEN: calling store_insight with empty source_ids list
        THEN: succeeds (source_ids can be empty)

        Story: 5.4 - Flexible source_ids
        """
        result = mock_store.store_insight(
            content="Insight with no source references.", source_ids=[]
        )

        assert result.id > 0


class TestInsightResultDataclass:
    """P0: Verify InsightResult dataclass structure."""

    def test_insight_result_has_required_fields(self):
        """
        GIVEN: InsightResult dataclass
        WHEN: creating an instance
        THEN: all required fields are present

        Story: 5.4 - InsightResult dataclass
        """
        from cognitive_memory import InsightResult

        now = datetime.now()
        result = InsightResult(
            id=1, embedding_status="success", fidelity_score=0.92, created_at=now
        )

        assert result.id == 1
        assert result.embedding_status == "success"
        assert result.fidelity_score == 0.92
        assert result.created_at == now

    def test_insight_result_embedding_status_values(self):
        """
        GIVEN: InsightResult
        WHEN: checking embedding_status
        THEN: value is "success" or "failed"

        Story: 5.4 - Status values
        """
        from cognitive_memory import InsightResult

        valid_statuses = {"success", "failed"}

        result = InsightResult(
            id=1,
            embedding_status="success",
            fidelity_score=0.9,
            created_at=datetime.now(),
        )

        assert result.embedding_status in valid_statuses

    def test_insight_result_created_at_is_datetime(self):
        """
        GIVEN: InsightResult from store_insight
        WHEN: accessing created_at
        THEN: value is a datetime object

        Story: 5.4 - Timestamp
        """
        from cognitive_memory import InsightResult

        result = InsightResult(
            id=1,
            embedding_status="success",
            fidelity_score=0.85,
            created_at=datetime.now(),
        )

        assert isinstance(result.created_at, datetime)
