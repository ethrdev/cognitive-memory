"""
ATDD Tests: Hybrid Search Library API (Story 5.3)

These tests verify the store.search() functionality:
- Basic search with query and top_k
- Custom weights configuration
- Search result format (SearchResult dataclass)
- Empty result handling
- Error handling

Status: RED Phase (search method not yet implemented)
Risk: R-003 - API divergence between Library and MCP
Priority: P0 - Core search functionality
"""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestSearchBasic:
    """P0: Verify basic search functionality."""

    @pytest.fixture
    def mock_store_with_db(self):
        """Create a store with mocked database and connection."""
        from cognitive_memory import MemoryStore

        # Mock the connection pool and state
        mock_conn = MagicMock()
        mock_connection_manager = MagicMock()
        mock_connection_manager.is_initialized = True
        mock_connection_manager.get_connection.return_value.__enter__.return_value = mock_conn

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://test:test@localhost/test_db"},
        ):
            store = MemoryStore.from_env()
            store._connection_manager = mock_connection_manager
            store._is_connected = True  # Set connected state
            yield store

    @pytest.fixture
    def mock_mcp_tools(self):
        """Mock MCP tools for testing."""
        with patch('cognitive_memory.store.generate_query_embedding') as mock_embed, \
             patch('cognitive_memory.store.semantic_search') as mock_semantic, \
             patch('cognitive_memory.store.keyword_search') as mock_keyword, \
             patch('cognitive_memory.store.rrf_fusion') as mock_rrf:

            # Setup default return values
            mock_embed.return_value = [0.1] * 1536  # Mock embedding
            mock_semantic.return_value = [
                {
                    "id": 1,
                    "content": "test semantic result",
                    "distance": 0.2,
                    "metadata": {"type": "semantic"},
                    "source_ids": [1, 2],
                    "io_category": "test",
                    "is_identity": False,
                    "source_file": "test.py"
                }
            ]
            mock_keyword.return_value = [
                {
                    "id": 1,
                    "content": "test keyword result",
                    "rank": 0.8,
                    "metadata": {"type": "keyword"},
                    "source_ids": [1, 2],
                    "io_category": "test",
                    "is_identity": False,
                    "source_file": "test.py"
                }
            ]
            mock_rrf.return_value = [
                {
                    "id": 1,
                    "content": "test result",
                    "score": 0.85,
                    "metadata": {"type": "fused"},
                    "distance": 0.2,
                    "rank": 0.8
                }
            ]

            yield {
                'embed': mock_embed,
                'semantic': mock_semantic,
                'keyword': mock_keyword,
                'rrf': mock_rrf
            }

    def test_search_returns_list_of_search_results(self, mock_store_with_db, mock_mcp_tools):
        """
        GIVEN: MemoryStore with data in database
        WHEN: calling store.search(query, top_k=5)
        THEN: returns list of SearchResult objects

        Story: 5.3 - Hybrid Search Library API
        """
        from cognitive_memory import SearchResult

        results = mock_store_with_db.search("test query", top_k=5)

        assert isinstance(results, list)
        # If results exist, they should be SearchResult instances
        for result in results:
            assert isinstance(result, SearchResult)
            assert hasattr(result, "id")
            assert hasattr(result, "content")
            assert hasattr(result, "score")
            assert hasattr(result, "source")
            assert hasattr(result, "metadata")

        # Verify MCP tools were called
        mock_mcp_tools['embed'].assert_called_once_with("test query")
        mock_mcp_tools['semantic'].assert_called_once()
        mock_mcp_tools['keyword'].assert_called_once()
        mock_mcp_tools['rrf'].assert_called_once()

    def test_search_returns_empty_list_for_no_matches(self, mock_store_with_db, mock_mcp_tools):
        """
        GIVEN: MemoryStore with no matching data
        WHEN: calling store.search() with unmatched query
        THEN: returns empty list (not None, not exception)

        Story: 5.3 - Empty result handling
        """
        # Override mock to return empty results
        mock_mcp_tools['semantic'].return_value = []
        mock_mcp_tools['keyword'].return_value = []
        mock_mcp_tools['rrf'].return_value = []

        results = mock_store_with_db.search("xyznonexistentquery12345", top_k=5)

        assert isinstance(results, list)
        assert len(results) == 0

    def test_search_respects_top_k_limit(self, mock_store_with_db, mock_mcp_tools):
        """
        GIVEN: MemoryStore with many matching documents
        WHEN: calling store.search() with top_k=3
        THEN: returns at most 3 results

        Story: 5.3 - top_k parameter
        """
        # Override mock to return more results than top_k
        mock_mcp_tools['rrf'].return_value = [
            {"id": i, "content": f"result {i}", "score": 0.9 - i*0.1, "metadata": {}}
            for i in range(1, 6)  # 5 results
        ]

        results = mock_store_with_db.search("test", top_k=3)

        assert len(results) <= 3


class TestSearchWeights:
    """P0: Verify custom weight configuration."""

    @pytest.fixture
    def mock_store_with_db(self):
        """Create a store with mocked database and connection."""
        from cognitive_memory import MemoryStore

        # Mock the connection pool and state
        mock_conn = MagicMock()
        mock_connection_manager = MagicMock()
        mock_connection_manager.is_initialized = True
        mock_connection_manager.get_connection.return_value.__enter__.return_value = mock_conn

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://test:test@localhost/test_db"},
        ):
            store = MemoryStore.from_env()
            store._connection_manager = mock_connection_manager
            store._is_connected = True  # Set connected state
            yield store

    @pytest.fixture
    def mock_mcp_tools(self):
        """Mock MCP tools for testing."""
        with patch('cognitive_memory.store.generate_query_embedding') as mock_embed, \
             patch('cognitive_memory.store.semantic_search') as mock_semantic, \
             patch('cognitive_memory.store.keyword_search') as mock_keyword, \
             patch('cognitive_memory.store.rrf_fusion') as mock_rrf:

            mock_embed.return_value = [0.1] * 1536
            mock_semantic.return_value = [
                {"id": 1, "content": "semantic result", "distance": 0.2, "metadata": {},
                 "source_ids": [], "io_category": "test", "is_identity": False, "source_file": "test.py"}
            ]
            mock_keyword.return_value = [
                {"id": 1, "content": "keyword result", "rank": 0.8, "metadata": {},
                 "source_ids": [], "io_category": "test", "is_identity": False, "source_file": "test.py"}
            ]
            mock_rrf.return_value = [
                {"id": 1, "content": "fused result", "score": 0.85, "metadata": {}, "distance": 0.2, "rank": 0.8}
            ]

            yield {
                'embed': mock_embed,
                'semantic': mock_semantic,
                'keyword': mock_keyword,
                'rrf': mock_rrf
            }

    def test_search_with_default_weights(self, mock_store_with_db, mock_mcp_tools):
        """
        GIVEN: MemoryStore
        WHEN: calling store.search() without weights parameter
        THEN: uses default weights (semantic: 0.7, keyword: 0.3)

        Story: 5.3 - Default weights
        """
        results = mock_store_with_db.search("test query")

        assert isinstance(results, list)
        # Verify rrf_fusion was called with default weights
        mock_mcp_tools['rrf'].assert_called_once()
        call_args = mock_mcp_tools['rrf'].call_args[0]
        weights_arg = call_args[2] if len(call_args) > 2 else {}
        expected_default = {"semantic": 0.7, "keyword": 0.3}
        assert weights_arg == expected_default

    def test_search_with_custom_weights(self, mock_store_with_db, mock_mcp_tools):
        """
        GIVEN: MemoryStore
        WHEN: calling store.search() with custom weights
        THEN: applies custom weights to hybrid search

        Story: 5.3 - Custom weights
        """
        custom_weights = {"semantic": 0.8, "keyword": 0.2}

        results = mock_store_with_db.search(
            "test query", top_k=5, weights=custom_weights
        )

        assert isinstance(results, list)
        # Verify rrf_fusion was called with custom weights
        mock_mcp_tools['rrf'].assert_called_once()
        call_args = mock_mcp_tools['rrf'].call_args[0]
        weights_arg = call_args[2] if len(call_args) > 2 else {}
        assert weights_arg == custom_weights

    def test_search_with_keyword_only_weights(self, mock_store_with_db, mock_mcp_tools):
        """
        GIVEN: MemoryStore
        WHEN: calling store.search() with 100% keyword weight
        THEN: performs keyword-only search

        Story: 5.3 - Weight flexibility
        """
        keyword_only = {"semantic": 0.0, "keyword": 1.0}

        results = mock_store_with_db.search("test query", weights=keyword_only)

        assert isinstance(results, list)
        # Verify rrf_fusion was called with keyword-only weights
        mock_mcp_tools['rrf'].assert_called_once()
        call_args = mock_mcp_tools['rrf'].call_args[0]
        weights_arg = call_args[2] if len(call_args) > 2 else {}
        assert weights_arg == keyword_only

    def test_search_with_semantic_only_weights(self, mock_store_with_db, mock_mcp_tools):
        """
        GIVEN: MemoryStore
        WHEN: calling store.search() with 100% semantic weight
        THEN: performs semantic-only search

        Story: 5.3 - Weight flexibility
        """
        semantic_only = {"semantic": 1.0, "keyword": 0.0}

        results = mock_store_with_db.search("test query", weights=semantic_only)

        assert isinstance(results, list)
        # Verify rrf_fusion was called with semantic-only weights
        mock_mcp_tools['rrf'].assert_called_once()
        call_args = mock_mcp_tools['rrf'].call_args[0]
        weights_arg = call_args[2] if len(call_args) > 2 else {}
        assert weights_arg == semantic_only


class TestSearchResultDataclass:
    """P0: Verify SearchResult dataclass structure."""

    def test_search_result_has_required_fields(self):
        """
        GIVEN: SearchResult dataclass
        WHEN: creating an instance
        THEN: all required fields are present

        Story: 5.3 - SearchResult dataclass
        """
        from cognitive_memory import SearchResult

        result = SearchResult(
            id=1,
            content="Test content",
            score=0.85,
            source="l2_insight",
            metadata={"key": "value"},
        )

        assert result.id == 1
        assert result.content == "Test content"
        assert result.score == 0.85
        assert result.source == "l2_insight"
        assert result.metadata == {"key": "value"}

    def test_search_result_score_is_float(self):
        """
        GIVEN: SearchResult from search
        WHEN: accessing score field
        THEN: score is a float between 0 and 1

        Story: 5.3 - Score format
        """
        from cognitive_memory import SearchResult

        result = SearchResult(
            id=1, content="Test", score=0.75, source="l2_insight", metadata={}
        )

        assert isinstance(result.score, float)
        assert 0.0 <= result.score <= 1.0

    def test_search_result_source_is_valid_type(self):
        """
        GIVEN: SearchResult from search
        WHEN: accessing source field
        THEN: source is either "l2_insight" or "l0_raw"

        Story: 5.3 - Source identification
        """
        from cognitive_memory import SearchResult

        valid_sources = {"l2_insight", "l0_raw"}

        result = SearchResult(
            id=1, content="Test", score=0.75, source="l2_insight", metadata={}
        )

        assert result.source in valid_sources


class TestSearchValidation:
    """P0: Verify input validation for search."""

    @pytest.fixture
    def mock_store_not_connected(self):
        """Create a store that is not connected."""
        from cognitive_memory import MemoryStore

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://test:test@localhost/test_db"},
        ):
            store = MemoryStore.from_env()
            # Don't connect - keep is_connected False
            yield store

    @pytest.fixture
    def mock_store_with_db(self):
        """Create a store with mocked database and connection."""
        from cognitive_memory import MemoryStore

        # Mock the connection pool and state
        mock_conn = MagicMock()
        mock_connection_manager = MagicMock()
        mock_connection_manager.is_initialized = True
        mock_connection_manager.get_connection.return_value.__enter__.return_value = mock_conn

        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://test:test@localhost/test_db"},
        ):
            store = MemoryStore.from_env()
            store._connection_manager = mock_connection_manager
            store._is_connected = True  # Set connected state
            yield store

    def test_search_rejects_empty_query(self, mock_store_with_db):
        """
        GIVEN: MemoryStore
        WHEN: calling store.search() with empty string
        THEN: raises ValidationError

        Story: 5.3 - Input validation
        """
        from cognitive_memory.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Query must be a non-empty string"):
            mock_store_with_db.search("", top_k=5)

        with pytest.raises(ValidationError, match="Query must be a non-empty string"):
            mock_store_with_db.search("   ", top_k=5)

    def test_search_rejects_invalid_top_k(self, mock_store_with_db):
        """
        GIVEN: MemoryStore
        WHEN: calling store.search() with invalid top_k
        THEN: raises ValidationError

        Story: 5.3 - Input validation
        """
        from cognitive_memory.exceptions import ValidationError

        # Test negative top_k
        with pytest.raises(ValidationError, match="top_k must be an integer between 1 and 100"):
            mock_store_with_db.search("test", top_k=-1)

        # Test top_k > 100
        with pytest.raises(ValidationError, match="top_k must be an integer between 1 and 100"):
            mock_store_with_db.search("test", top_k=101)

        # Test non-integer top_k
        with pytest.raises(ValidationError, match="top_k must be an integer between 1 and 100"):
            mock_store_with_db.search("test", top_k=3.5)

    def test_rejects_invalid_weights(self, mock_store_with_db):
        """
        GIVEN: MemoryStore
        WHEN: calling store.search() with invalid weights
        THEN: raises ValidationError

        Story: 5.3 - Input validation for weights
        """
        from cognitive_memory.exceptions import ValidationError

        # Test missing keys
        with pytest.raises(ValidationError, match="weights must contain 'semantic' and 'keyword' keys"):
            mock_store_with_db.search("test", weights={"semantic": 0.5})

        with pytest.raises(ValidationError, match="weights must contain 'semantic' and 'keyword' keys"):
            mock_store_with_db.search("test", weights={"keyword": 0.5})

        # Test non-dict weights
        with pytest.raises(ValidationError, match="weights must be a dictionary"):
            mock_store_with_db.search("test", weights="invalid")

        # Test negative weights
        with pytest.raises(ValidationError, match="weights must contain non-negative numbers"):
            mock_store_with_db.search("test", weights={"semantic": -0.1, "keyword": 1.1})

    def test_search_rejects_when_not_connected(self, mock_store_not_connected):
        """
        GIVEN: MemoryStore that is not connected
        WHEN: calling store.search()
        THEN: raises ConnectionError

        Story: 5.3 - Connection required
        """
        from cognitive_memory.exceptions import ConnectionError

        with pytest.raises(ConnectionError, match="MemoryStore is not connected"):
            mock_store_not_connected.search("test", top_k=5)

    @pytest.fixture
    def mock_mcp_tools(self):
        """Mock MCP tools for testing."""
        with patch('cognitive_memory.store.generate_query_embedding') as mock_embed, \
             patch('cognitive_memory.store.semantic_search') as mock_semantic, \
             patch('cognitive_memory.store.keyword_search') as mock_keyword, \
             patch('cognitive_memory.store.rrf_fusion') as mock_rrf:

            mock_embed.return_value = [0.1] * 1536
            mock_semantic.return_value = []
            mock_keyword.return_value = []
            mock_rrf.return_value = []

            yield {
                'embed': mock_embed,
                'semantic': mock_semantic,
                'keyword': mock_keyword,
                'rrf': mock_rrf
            }

    def test_search_handles_special_characters(self, mock_store_with_db, mock_mcp_tools):
        """
        GIVEN: MemoryStore
        WHEN: calling store.search() with SQL special characters
        THEN: handles safely without SQL injection

        Story: 5.3 - Security (SQL injection prevention)
        """
        # Should not raise error or cause SQL injection
        results = mock_store_with_db.search("test'; DROP TABLE users; --", top_k=5)

        assert isinstance(results, list)
        # Verify the special characters were passed to the embed function
        mock_mcp_tools['embed'].assert_called_once_with("test'; DROP TABLE users; --")
