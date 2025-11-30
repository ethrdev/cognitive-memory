"""
Tests for Graph-Extended Hybrid Search (Story 4.6)

Tests the hybrid search extension including:
- RRF fusion with 3 sources (semantic, keyword, graph)
- Query routing (relational vs. standard queries)
- Entity extraction from queries
- Graph search functionality
- Config-based weights
- Backwards compatibility

Story 4.6: Hybrid Search Erweiterung (Vector + Keyword + Graph RRF)
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.tools import (
    rrf_fusion,
    extract_entities_from_query,
    detect_relational_query,
    get_adjusted_weights,
    graph_search,
    handle_hybrid_search,
    DEFAULT_RELATIONAL_KEYWORDS,
)


# =============================================================================
# Test: Entity Extraction (AC-4.6.2)
# =============================================================================

class TestEntityExtraction:
    """Test suite for entity extraction from queries."""

    def test_extract_capitalized_words(self):
        """Test extracting capitalized words from query."""
        query = "What technologies does Python use?"
        entities = extract_entities_from_query(query)

        # "Python" should be extracted (capitalized, >3 chars)
        assert "Python" in entities

    def test_extract_multiple_entities(self):
        """Test extracting multiple entities from query."""
        query = "How does Django connect to PostgreSQL?"
        entities = extract_entities_from_query(query)

        # Both Django and PostgreSQL should be extracted
        assert "Django" in entities
        assert "PostgreSQL" in entities

    def test_extract_quoted_strings(self):
        """Test extracting quoted strings from query."""
        query = 'What does "cognitive-memory" project use?'
        entities = extract_entities_from_query(query)

        assert "cognitive-memory" in entities

    def test_extract_single_quoted_strings(self):
        """Test extracting single-quoted strings from query."""
        query = "What is 'Next.js' used for?"
        entities = extract_entities_from_query(query)

        assert "Next.js" in entities

    def test_deduplicate_entities(self):
        """Test that duplicate entities are removed."""
        query = "Python uses Python libraries for Python development"
        entities = extract_entities_from_query(query)

        # Should only have one "Python"
        python_count = sum(1 for e in entities if e.lower() == "python")
        assert python_count == 1

    def test_empty_query(self):
        """Test empty query returns empty list."""
        entities = extract_entities_from_query("")
        assert entities == []

    def test_no_entities_in_query(self):
        """Test query with no extractable entities."""
        query = "how does this work in general?"
        entities = extract_entities_from_query(query)

        # First word "how" is lowercase, no capitalized words except at start
        assert len(entities) == 0


# =============================================================================
# Test: Query Routing (AC-4.6.1)
# =============================================================================

class TestQueryRouting:
    """Test suite for query routing logic."""

    def test_detect_german_relational_keywords(self):
        """Test detecting German relational keywords."""
        query = "Welche Technologie nutzt dieses Projekt?"
        is_relational, matched = detect_relational_query(query)

        assert is_relational is True
        assert "nutzt" in matched

    def test_detect_english_relational_keywords(self):
        """Test detecting English relational keywords."""
        query = "What technology uses Python?"
        is_relational, matched = detect_relational_query(query)

        assert is_relational is True
        assert "uses" in matched

    def test_detect_multiple_keywords(self):
        """Test detecting multiple relational keywords."""
        query = "Was verwendet das Projekt und welche Technologie nutzt es?"
        is_relational, matched = detect_relational_query(query)

        assert is_relational is True
        assert len(matched) >= 2

    def test_non_relational_query(self):
        """Test non-relational query returns False."""
        query = "Explain how machine learning works."
        is_relational, matched = detect_relational_query(query)

        assert is_relational is False
        assert matched == []

    def test_case_insensitive_matching(self):
        """Test case-insensitive keyword matching."""
        query = "WHAT TECHNOLOGY USES THIS PROJECT?"
        is_relational, matched = detect_relational_query(query)

        assert is_relational is True

    def test_custom_keywords(self):
        """Test custom keyword lists."""
        custom_keywords = {
            "de": ["verlinkt"],
            "en": ["interacts"]
        }
        query = "How does A interact with B?"
        is_relational, matched = detect_relational_query(query, custom_keywords)

        # Default keywords should NOT match
        query2 = "What uses Python?"
        is_relational2, _ = detect_relational_query(query2, custom_keywords)

        # "interacts" is not in query, "uses" is not in custom_keywords
        assert is_relational2 is False


class TestWeightAdjustment:
    """Test suite for weight adjustment based on query type."""

    def test_relational_query_weights(self):
        """Test weights for relational queries."""
        weights = get_adjusted_weights(is_relational=True)

        assert weights["semantic"] == 0.4
        assert weights["keyword"] == 0.2
        assert weights["graph"] == 0.4
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_standard_query_weights(self):
        """Test weights for standard queries."""
        weights = get_adjusted_weights(is_relational=False)

        assert weights["semantic"] == 0.6
        assert weights["keyword"] == 0.2
        assert weights["graph"] == 0.2
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_custom_base_weights(self):
        """Test custom base weights for standard queries."""
        custom_weights = {"semantic": 0.5, "keyword": 0.3, "graph": 0.2}
        weights = get_adjusted_weights(is_relational=False, base_weights=custom_weights)

        assert weights["semantic"] == 0.5
        assert weights["keyword"] == 0.3
        assert weights["graph"] == 0.2


# =============================================================================
# Test: RRF Fusion (AC-4.6.3)
# =============================================================================

class TestRRFFusion:
    """Test suite for extended RRF fusion with graph results."""

    def test_three_source_fusion(self):
        """Test RRF fusion with all three sources."""
        semantic_results = [
            {"id": 1, "content": "Doc 1", "score": 0.9},
            {"id": 2, "content": "Doc 2", "score": 0.8},
        ]
        keyword_results = [
            {"id": 2, "content": "Doc 2", "score": 0.85},
            {"id": 3, "content": "Doc 3", "score": 0.7},
        ]
        graph_results = [
            {"id": 3, "content": "Doc 3", "score": 0.95},
            {"id": 4, "content": "Doc 4", "score": 0.6},
        ]
        weights = {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}

        fused = rrf_fusion(semantic_results, keyword_results, weights, k=60, graph_results=graph_results)

        # All documents should be in results
        ids = [r["id"] for r in fused]
        assert 1 in ids
        assert 2 in ids
        assert 3 in ids
        assert 4 in ids

        # Doc 2 and Doc 3 appear in multiple sources - should have higher scores
        doc2 = next(r for r in fused if r["id"] == 2)
        doc4 = next(r for r in fused if r["id"] == 4)
        assert doc2["score"] > doc4["score"]  # Doc 2 in 2 sources > Doc 4 in 1 source

    def test_two_source_fusion_graph_missing(self):
        """Test RRF fusion with only semantic and keyword (backwards compat)."""
        semantic_results = [
            {"id": 1, "content": "Doc 1", "score": 0.9},
        ]
        keyword_results = [
            {"id": 1, "content": "Doc 1", "score": 0.8},
        ]
        weights = {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}

        # graph_results defaults to empty list
        fused = rrf_fusion(semantic_results, keyword_results, weights, k=60)

        assert len(fused) == 1
        assert fused[0]["id"] == 1
        # Score should be from semantic + keyword only
        expected_score = 0.6 / (60 + 1) + 0.2 / (60 + 1)
        assert abs(fused[0]["score"] - expected_score) < 1e-9

    def test_weight_normalization(self):
        """Test that weights are normalized to sum to 1.0."""
        semantic_results = [{"id": 1, "content": "Doc 1"}]
        keyword_results = []
        graph_results = []

        # Weights don't sum to 1.0
        weights = {"semantic": 0.8, "keyword": 0.4, "graph": 0.4}

        fused = rrf_fusion(semantic_results, keyword_results, weights, k=60, graph_results=graph_results)

        # Should still work - weights get normalized
        assert len(fused) == 1

    def test_empty_all_sources(self):
        """Test empty results from all sources."""
        fused = rrf_fusion([], [], {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}, graph_results=[])

        assert fused == []

    def test_graph_only_results(self):
        """Test fusion with only graph results."""
        semantic_results = []
        keyword_results = []
        graph_results = [
            {"id": 1, "content": "Doc 1"},
            {"id": 2, "content": "Doc 2"},
        ]
        weights = {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}

        fused = rrf_fusion(semantic_results, keyword_results, weights, k=60, graph_results=graph_results)

        assert len(fused) == 2
        # All scores should come from graph only
        for result in fused:
            assert "score" in result


# =============================================================================
# Test: Graph Search (AC-4.6.2)
# =============================================================================

class TestGraphSearch:
    """Test suite for graph search functionality."""

    @pytest.mark.asyncio
    async def test_graph_search_with_matching_node(self):
        """Test graph search when entity matches a node."""
        with patch('mcp_server.db.graph.get_node_by_name') as mock_get_node, \
             patch('mcp_server.db.graph.query_neighbors') as mock_neighbors:

            # Node lookup function - called multiple times
            def node_lookup(name):
                if name == "Python":
                    return {
                        "id": "python-node-id",
                        "label": "Technology",
                        "name": "Python",
                        "properties": {},
                        "vector_id": None,
                    }
                elif name == "Django":
                    return {
                        "id": "django-node-id",
                        "label": "Framework",
                        "name": "Django",
                        "properties": {},
                        "vector_id": 42,
                    }
                return None

            mock_get_node.side_effect = node_lookup

            mock_neighbors.return_value = [
                {
                    "node_id": "django-node-id",
                    "label": "Framework",
                    "name": "Django",
                    "relation": "USES",
                    "weight": 0.9,
                    "distance": 1,
                    "properties": {}
                }
            ]

            # Mock database connection and cursor
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {
                "id": 42,
                "content": "Django is a Python web framework",
                "source_ids": [1, 2],
                "metadata": {},
                "io_category": None,
                "is_identity": False,
                "source_file": None,
            }

            query = "What does Python use?"
            results = await graph_search(query, top_k=5, conn=mock_conn)

            assert len(results) == 1
            assert results[0]["id"] == 42
            assert results[0]["content"] == "Django is a Python web framework"
            assert results[0]["graph_score"] == 0.9  # weight / distance = 0.9 / 1
            assert results[0]["rank"] == 1

    @pytest.mark.asyncio
    async def test_graph_search_no_matching_nodes(self):
        """Test graph search when no entities match nodes."""
        with patch('mcp_server.db.graph.get_node_by_name') as mock_get_node:
            mock_get_node.return_value = None  # No node found

            mock_conn = MagicMock()
            query = "What does Python use?"
            results = await graph_search(query, top_k=5, conn=mock_conn)

            assert results == []

    @pytest.mark.asyncio
    async def test_graph_search_no_entities_extracted(self):
        """Test graph search when no entities are extracted."""
        mock_conn = MagicMock()
        query = "how does this work?"  # No extractable entities
        results = await graph_search(query, top_k=5, conn=mock_conn)

        assert results == []


# =============================================================================
# Test: Handle Hybrid Search (AC-4.6.3, AC-4.6.5)
# =============================================================================

class TestHandleHybridSearch:
    """Test suite for extended handle_hybrid_search."""

    @pytest.mark.asyncio
    async def test_relational_query_uses_graph_weights(self):
        """Test that relational queries use boosted graph weights."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            # Setup mocks
            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            mock_semantic.return_value = [{"id": 1, "content": "Doc 1"}]
            mock_keyword.return_value = []
            mock_graph.return_value = []

            # Relational query
            arguments = {
                "query_text": "What technology uses Python?",
                "top_k": 5
            }

            result = await handle_hybrid_search(arguments)

            # Should detect as relational and use 40/20/40 weights
            assert result["query_type"] == "relational"
            assert result["applied_weights"]["semantic"] == 0.4
            assert result["applied_weights"]["keyword"] == 0.2
            assert result["applied_weights"]["graph"] == 0.4
            assert "uses" in result["matched_keywords"]

    @pytest.mark.asyncio
    async def test_standard_query_uses_default_weights(self):
        """Test that standard queries use default 60/20/20 weights."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            # Setup mocks
            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            mock_semantic.return_value = []
            mock_keyword.return_value = []
            mock_graph.return_value = []

            # Standard query (no relational keywords)
            arguments = {
                "query_text": "Explain machine learning concepts",
                "top_k": 5
            }

            result = await handle_hybrid_search(arguments)

            # Should detect as standard and use 60/20/20 weights
            assert result["query_type"] == "standard"
            assert result["applied_weights"]["semantic"] == 0.6
            assert result["applied_weights"]["keyword"] == 0.2
            assert result["applied_weights"]["graph"] == 0.2
            assert result["matched_keywords"] == []

    @pytest.mark.asyncio
    async def test_response_includes_graph_results_count(self):
        """Test that response includes graph_results_count field."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            mock_semantic.return_value = [{"id": 1, "content": "Doc 1"}]
            mock_keyword.return_value = [{"id": 2, "content": "Doc 2"}]
            mock_graph.return_value = [{"id": 3, "content": "Doc 3"}]

            arguments = {"query_text": "Test query", "top_k": 5}
            result = await handle_hybrid_search(arguments)

            # New fields from Story 4.6
            assert "graph_results_count" in result
            assert result["graph_results_count"] == 1
            assert "query_type" in result
            assert "applied_weights" in result
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_backwards_compatibility_old_weights_format(self):
        """Test backwards compatibility with old 2-source weight format."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            mock_semantic.return_value = []
            mock_keyword.return_value = []
            mock_graph.return_value = []

            # Old format weights (no "graph" key)
            arguments = {
                "query_text": "Test query",
                "top_k": 5,
                "weights": {"semantic": 0.7, "keyword": 0.3}  # Old format
            }

            result = await handle_hybrid_search(arguments)

            # Should still work and apply query routing weights
            assert result["status"] == "success"
            # Since old weights sum to 1.0, should use query routing defaults
            assert "graph" in result["applied_weights"]

    @pytest.mark.asyncio
    async def test_new_weights_format_with_graph(self):
        """Test new 3-source weight format."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            mock_semantic.return_value = []
            mock_keyword.return_value = []
            mock_graph.return_value = []

            # New format weights with graph
            arguments = {
                "query_text": "Test query",
                "top_k": 5,
                "weights": {"semantic": 0.5, "keyword": 0.3, "graph": 0.2}
            }

            result = await handle_hybrid_search(arguments)

            assert result["status"] == "success"
            assert result["applied_weights"]["semantic"] == 0.5
            assert result["applied_weights"]["keyword"] == 0.3
            assert result["applied_weights"]["graph"] == 0.2


# =============================================================================
# Test: Config Integration (AC-4.6.4)
# =============================================================================

class TestConfigIntegration:
    """Test suite for config loading."""

    def test_get_hybrid_search_weights(self):
        """Test loading hybrid search weights from config."""
        with patch('mcp_server.config.get_config') as mock_config:
            mock_config.return_value = {
                "memory": {
                    "hybrid_search_weights": {
                        "semantic": 0.6,
                        "keyword": 0.2,
                        "graph": 0.2
                    }
                }
            }

            from mcp_server.config import get_hybrid_search_weights
            weights = get_hybrid_search_weights()

            assert weights["semantic"] == 0.6
            assert weights["keyword"] == 0.2
            assert weights["graph"] == 0.2

    def test_get_hybrid_search_weights_defaults(self):
        """Test default weights when config is missing."""
        with patch('mcp_server.config.get_config') as mock_config:
            mock_config.return_value = {"memory": {}}  # No hybrid_search_weights

            from mcp_server.config import get_hybrid_search_weights
            weights = get_hybrid_search_weights()

            # Should return defaults
            assert weights["semantic"] == 0.6
            assert weights["keyword"] == 0.2
            assert weights["graph"] == 0.2

    def test_get_query_routing_config(self):
        """Test loading query routing config."""
        with patch('mcp_server.config.get_config') as mock_config:
            mock_config.return_value = {
                "memory": {
                    "query_routing": {
                        "relational_keywords": {
                            "de": ["nutzt"],
                            "en": ["uses"]
                        },
                        "relational_weights": {
                            "semantic": 0.4,
                            "keyword": 0.2,
                            "graph": 0.4
                        }
                    }
                }
            }

            from mcp_server.config import get_query_routing_config
            config = get_query_routing_config()

            assert "relational_keywords" in config
            assert "relational_weights" in config
            assert config["relational_weights"]["graph"] == 0.4

    def test_get_query_routing_config_defaults(self):
        """Test default query routing when config is missing."""
        with patch('mcp_server.config.get_config') as mock_config:
            mock_config.return_value = {"memory": {}}

            from mcp_server.config import get_query_routing_config
            config = get_query_routing_config()

            # Should return defaults
            assert "relational_keywords" in config
            assert "de" in config["relational_keywords"]
            assert "en" in config["relational_keywords"]
            assert config["relational_weights"]["graph"] == 0.4
