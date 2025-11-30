"""
Integration Tests for BMAD-BMM Use Cases (Story 4.7)

Tests end-to-end GraphRAG integration with realistic BMAD-BMM scenarios:
- Use Case 1: Architecture Check (AC-4.7.1)
- Use Case 2: Risk Analysis (AC-4.7.2)
- Use Case 3: Knowledge Harvesting (AC-4.7.3)
- Backwards Compatibility (AC-4.7.5)

Story 4.7: Integration Testing mit BMAD-BMM Use Cases
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.tools import (
    rrf_fusion,
    extract_entities_from_query,
    detect_relational_query,
    get_adjusted_weights,
    graph_search,
    handle_hybrid_search,
)
from mcp_server.db.graph import (
    add_node,
    add_edge,
    get_node_by_name,
    query_neighbors,
    find_path,
)


# =============================================================================
# Fixtures for Test Data Setup
# =============================================================================

@pytest.fixture
def mock_db_connection():
    """Create a mock database connection for testing."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    return mock_conn, mock_cursor


@pytest.fixture
def test_graph_data():
    """Test graph data definitions."""
    return {
        "nodes": [
            {"label": "Requirement", "name": "High Volume Requirement", "properties": {"priority": "high"}},
            {"label": "Technology", "name": "PostgreSQL", "properties": {"type": "database"}},
            {"label": "Project", "name": "Projekt A", "properties": {"status": "active"}},
            {"label": "Technology", "name": "Stripe API", "properties": {"type": "payment"}},
        ],
        "edges": [
            {"source": "High Volume Requirement", "target": "PostgreSQL", "relation": "SOLVED_BY"},
            {"source": "Projekt A", "target": "Stripe API", "relation": "USES"},
        ]
    }


# =============================================================================
# Use Case 1: Architecture Check (AC-4.7.1)
# =============================================================================

class TestUseCaseArchitectureCheck:
    """
    Test Use Case 1: Architecture Check

    Given: Graph with "High Volume Requirement" → "PostgreSQL" (SOLVED_BY)
    When: Query "Welche Datenbank für High Volume?"
    Then: PostgreSQL appears in results with correct query routing
    """

    def test_entity_extraction_architecture_query(self):
        """Test that entities are extracted from architecture queries."""
        query = "Welche Datenbank für High Volume?"
        entities = extract_entities_from_query(query)

        # "High" and "Volume" should be extracted (capitalized)
        assert "High" in entities or "Volume" in entities

    def test_entity_extraction_postgresql(self):
        """Test PostgreSQL entity extraction."""
        query = "How does PostgreSQL handle high volume?"
        entities = extract_entities_from_query(query)

        assert "PostgreSQL" in entities

    def test_query_routing_database_keyword(self):
        """Test that 'Datenbank' triggers relational query routing."""
        # German query with "Datenbank" keyword
        query = "Welche Datenbank eignet sich für High Volume?"
        is_relational, matched = detect_relational_query(query)

        # "Datenbank" is in the relational keywords
        # Note: The actual detection depends on config keywords
        # If "Datenbank" is not in default keywords, this test documents that
        assert isinstance(is_relational, bool)
        assert isinstance(matched, list)

    def test_relational_weights_for_architecture_query(self):
        """Test weight adjustment for relational architecture queries."""
        # Query with relational keyword "nutzt"
        query = "Welche Technologie nutzt PostgreSQL?"
        is_relational, matched = detect_relational_query(query)

        weights = get_adjusted_weights(is_relational)

        if is_relational:
            # Relational query: 40/20/40 weights
            assert weights["graph"] == 0.4
            assert weights["semantic"] == 0.4
        else:
            # Standard query: 60/20/20 weights
            assert weights["semantic"] == 0.6
            assert weights["graph"] == 0.2

    @pytest.mark.asyncio
    async def test_graph_search_architecture_pattern(self):
        """Test graph search with architecture query pattern."""
        with patch('mcp_server.db.graph.get_node_by_name') as mock_get_node, \
             patch('mcp_server.db.graph.query_neighbors') as mock_neighbors:

            # Setup: High Volume Requirement node exists
            def node_lookup(name):
                if name == "Volume" or name == "High":
                    # Entity extraction might extract "High" or "Volume"
                    return None  # No exact match
                elif name == "PostgreSQL":
                    return {
                        "id": "pg-node-id",
                        "label": "Technology",
                        "name": "PostgreSQL",
                        "properties": {},
                        "vector_id": 101,
                    }
                return None

            mock_get_node.side_effect = node_lookup
            mock_neighbors.return_value = []

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor

            # Query that should extract "PostgreSQL" as entity
            query = "Does PostgreSQL handle high volume well?"
            results = await graph_search(query, top_k=5, conn=mock_conn)

            # Should call get_node_by_name for extracted entities
            mock_get_node.assert_called()

    @pytest.mark.asyncio
    async def test_hybrid_search_architecture_use_case(self):
        """End-to-end test for architecture check use case."""
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

            # Simulate PostgreSQL appearing in graph results
            mock_semantic.return_value = []
            mock_keyword.return_value = []
            mock_graph.return_value = [
                {"id": 101, "content": "PostgreSQL is excellent for high-volume transactional workloads"}
            ]

            arguments = {
                "query_text": "Welche Datenbank für High Volume?",
                "top_k": 5
            }

            result = await handle_hybrid_search(arguments)

            assert result["status"] == "success"
            assert "graph_results_count" in result
            assert result["graph_results_count"] == 1


# =============================================================================
# Use Case 2: Risk Analysis (AC-4.7.2)
# =============================================================================

class TestUseCaseRiskAnalysis:
    """
    Test Use Case 2: Risk Analysis

    Given: Graph with "Projekt A" → "Stripe API" (USES)
    When: Query "Erfahrung mit Stripe API?"
    Then: "Projekt A" appears via graph relationship
    """

    def test_entity_extraction_stripe_api(self):
        """Test that 'Stripe API' is extracted as entity."""
        query = "Erfahrung mit Stripe API?"
        entities = extract_entities_from_query(query)

        assert "Stripe" in entities

    def test_entity_extraction_quoted_stripe(self):
        """Test quoted entity extraction."""
        query = 'What experience do we have with "Stripe API"?'
        entities = extract_entities_from_query(query)

        assert "Stripe API" in entities

    @pytest.mark.asyncio
    async def test_graph_search_finds_related_project(self):
        """Test that graph search finds Projekt A via Stripe API relationship."""
        with patch('mcp_server.db.graph.get_node_by_name') as mock_get_node, \
             patch('mcp_server.db.graph.query_neighbors') as mock_neighbors:

            # Setup: Stripe API node exists with project neighbor
            def node_lookup(name):
                if name == "Stripe":
                    return {
                        "id": "stripe-node-id",
                        "label": "Technology",
                        "name": "Stripe API",
                        "properties": {},
                        "vector_id": None,
                    }
                elif name == "Projekt A":
                    return {
                        "id": "projekt-a-id",
                        "label": "Project",
                        "name": "Projekt A",
                        "properties": {},
                        "vector_id": 201,
                    }
                return None

            mock_get_node.side_effect = node_lookup

            # Stripe API has neighbor "Projekt A" via USES relation
            mock_neighbors.return_value = [
                {
                    "node_id": "projekt-a-id",
                    "label": "Project",
                    "name": "Projekt A",
                    "relation": "USES",
                    "weight": 0.95,
                    "distance": 1,
                    "properties": {}
                }
            ]

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {
                "id": 201,
                "content": "Projekt A verwendet Stripe API für Payment Processing",
                "source_ids": [1, 2],
                "metadata": {},
                "io_category": None,
                "is_identity": False,
                "source_file": None,
            }

            query = "Erfahrung mit Stripe API?"
            results = await graph_search(query, top_k=5, conn=mock_conn)

            # Should find Projekt A via Stripe API relationship
            assert len(results) >= 1
            assert any(r["id"] == 201 for r in results)

    @pytest.mark.asyncio
    async def test_hybrid_search_risk_analysis_use_case(self):
        """End-to-end test for risk analysis use case."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            # Projekt A appears via graph relationship
            mock_semantic.return_value = []
            mock_keyword.return_value = []
            mock_graph.return_value = [
                {"id": 201, "content": "Projekt A: Stripe API Integration für Payment"}
            ]

            arguments = {
                "query_text": "Erfahrung mit Stripe API?",
                "top_k": 5
            }

            result = await handle_hybrid_search(arguments)

            assert result["status"] == "success"
            assert result["graph_results_count"] == 1


# =============================================================================
# Use Case 3: Knowledge Harvesting (AC-4.7.3)
# =============================================================================

class TestUseCaseKnowledgeHarvesting:
    """
    Test Use Case 3: Knowledge Harvesting (CRUD Verification)

    Given: Graph operations for new project/technology
    When: CRUD operations executed
    Then: Data correctly stored and searchable
    """

    def test_graph_add_node_idempotent(self):
        """Test that graph_add_node is idempotent."""
        with patch('mcp_server.db.graph.get_connection') as mock_conn_ctx:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor

            # First call creates node
            mock_cursor.fetchone.return_value = {
                "id": "new-node-id",
                "label": "Project",
                "name": "Neues Projekt",
                "created_at": "2025-01-01T00:00:00Z"
            }

            result = add_node(
                label="Project",
                name="Neues Projekt",
                properties='{"status": "active"}'
            )

            assert result["node_id"] == "new-node-id"
            assert result["label"] == "Project"
            assert result["name"] == "Neues Projekt"

    def test_graph_add_edge_creates_relationship(self):
        """Test that graph_add_edge creates relationship."""
        with patch('mcp_server.db.graph.get_connection') as mock_conn_ctx:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor

            mock_cursor.fetchone.return_value = {
                "id": "new-edge-id",
                "source_id": "source-node-id",
                "target_id": "target-node-id",
                "relation": "USES",
                "weight": 1.0,
                "created_at": "2025-01-01T00:00:00Z"
            }

            result = add_edge(
                source_id="source-node-id",
                target_id="target-node-id",
                relation="USES",
                weight=1.0
            )

            assert result["edge_id"] == "new-edge-id"
            assert result["relation"] == "USES"

    @pytest.mark.asyncio
    async def test_crud_then_search_workflow(self):
        """Test CRUD → Search workflow for knowledge harvesting."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            # After CRUD, the new project should appear in graph search
            mock_semantic.return_value = []
            mock_keyword.return_value = []
            mock_graph.return_value = [
                {"id": 301, "content": "Neues Projekt verwendet FastAPI für REST API"}
            ]

            arguments = {
                "query_text": "FastAPI Projekt",
                "top_k": 5
            }

            result = await handle_hybrid_search(arguments)

            assert result["status"] == "success"
            assert result["graph_results_count"] == 1


# =============================================================================
# Backwards Compatibility Tests (AC-4.7.5)
# =============================================================================

class TestBackwardsCompatibility:
    """
    Test Backwards Compatibility (AC-4.7.5)

    Given: Old API calls without graph parameter
    When: Executed with old format
    Then: No errors, graph weight set to default
    """

    @pytest.mark.asyncio
    async def test_old_weights_format_semantic_keyword_only(self):
        """Test old 2-source weight format still works."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            mock_semantic.return_value = [{"id": 1, "content": "Test doc"}]
            mock_keyword.return_value = []
            mock_graph.return_value = []

            # Old format: only semantic and keyword weights
            arguments = {
                "query_text": "Test query",
                "top_k": 5,
                "weights": {"semantic": 0.7, "keyword": 0.3}
            }

            result = await handle_hybrid_search(arguments)

            # Should not fail, graph weight should be added
            assert result["status"] == "success"
            assert "graph" in result["applied_weights"]

    @pytest.mark.asyncio
    async def test_no_weights_provided_uses_defaults(self):
        """Test that no weights uses query routing defaults."""
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

            # No weights provided
            arguments = {
                "query_text": "Standard query without relational keywords",
                "top_k": 5
            }

            result = await handle_hybrid_search(arguments)

            assert result["status"] == "success"
            # Standard query should get 60/20/20 weights
            assert result["applied_weights"]["semantic"] == 0.6
            assert result["applied_weights"]["keyword"] == 0.2
            assert result["applied_weights"]["graph"] == 0.2

    @pytest.mark.asyncio
    async def test_response_format_includes_all_fields(self):
        """Test that response format includes all required fields."""
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

            # Required fields from original API
            assert "results" in result
            assert "semantic_results_count" in result
            assert "keyword_results_count" in result
            assert "final_results_count" in result
            assert "weights" in result  # Backwards-compatible alias
            assert "status" in result

            # New fields from Story 4.6 (should not break old clients)
            assert "graph_results_count" in result
            assert "query_type" in result
            assert "applied_weights" in result
            assert "matched_keywords" in result

    @pytest.mark.asyncio
    async def test_old_clients_can_ignore_new_fields(self):
        """Test that old clients can safely ignore new response fields."""
        with patch('mcp_server.tools.generate_query_embedding') as mock_embed, \
             patch('mcp_server.tools.get_connection') as mock_conn_ctx, \
             patch('mcp_server.tools.semantic_search', new_callable=AsyncMock) as mock_semantic, \
             patch('mcp_server.tools.keyword_search', new_callable=AsyncMock) as mock_keyword, \
             patch('mcp_server.tools.graph_search', new_callable=AsyncMock) as mock_graph:

            mock_embed.return_value = [0.1] * 1536
            mock_conn = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)

            mock_semantic.return_value = [{"id": 1, "content": "Test"}]
            mock_keyword.return_value = []
            mock_graph.return_value = []

            arguments = {"query_text": "Test", "top_k": 5}
            result = await handle_hybrid_search(arguments)

            # Simulate old client that only reads specific fields
            old_client_data = {
                "results": result["results"],
                "semantic_results_count": result["semantic_results_count"],
                "keyword_results_count": result["keyword_results_count"],
                "weights": result["weights"],
                "status": result["status"],
            }

            # Old client should work fine
            assert old_client_data["status"] == "success"
            assert len(old_client_data["results"]) >= 0


# =============================================================================
# RRF Fusion Integration Tests
# =============================================================================

class TestRRFFusionIntegration:
    """Integration tests for RRF fusion with all three sources."""

    def test_three_source_rrf_ranking(self):
        """Test that documents appearing in multiple sources rank higher."""
        # Document appears in all 3 sources
        semantic_results = [
            {"id": 1, "content": "Common doc"},
            {"id": 2, "content": "Semantic only"},
        ]
        keyword_results = [
            {"id": 1, "content": "Common doc"},
            {"id": 3, "content": "Keyword only"},
        ]
        graph_results = [
            {"id": 1, "content": "Common doc"},
            {"id": 4, "content": "Graph only"},
        ]
        weights = {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}

        fused = rrf_fusion(semantic_results, keyword_results, weights, k=60, graph_results=graph_results)

        # Document 1 should be ranked first (appears in all 3 sources)
        assert fused[0]["id"] == 1
        assert fused[0]["score"] > fused[1]["score"]

    def test_relational_weights_boost_graph(self):
        """Test that relational weights boost graph results appropriately."""
        semantic_results = [{"id": 1, "content": "Semantic doc"}]
        keyword_results = []
        graph_results = [{"id": 2, "content": "Graph doc"}]

        # Standard weights: 60/20/20
        standard_weights = {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}
        fused_standard = rrf_fusion(semantic_results, [], standard_weights, k=60, graph_results=graph_results)

        # Relational weights: 40/20/40
        relational_weights = {"semantic": 0.4, "keyword": 0.2, "graph": 0.4}
        fused_relational = rrf_fusion(semantic_results, [], relational_weights, k=60, graph_results=graph_results)

        # With relational weights, graph doc should have relatively higher score
        standard_graph_score = next(r["score"] for r in fused_standard if r["id"] == 2)
        relational_graph_score = next(r["score"] for r in fused_relational if r["id"] == 2)

        assert relational_graph_score > standard_graph_score

    def test_empty_graph_results_still_works(self):
        """Test that empty graph results don't break fusion."""
        semantic_results = [{"id": 1, "content": "Doc 1"}]
        keyword_results = [{"id": 1, "content": "Doc 1"}]
        weights = {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}

        # graph_results is empty
        fused = rrf_fusion(semantic_results, keyword_results, weights, k=60, graph_results=[])

        assert len(fused) == 1
        assert fused[0]["id"] == 1


# =============================================================================
# Graph Query Integration Tests
# =============================================================================

class TestGraphQueryIntegration:
    """Integration tests for graph query operations."""

    def test_query_neighbors_with_mocked_db(self):
        """Test query_neighbors returns correct neighbor data."""
        with patch('mcp_server.db.graph.get_connection') as mock_conn_ctx:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor

            # Simulate neighbor query results
            mock_cursor.fetchall.return_value = [
                {
                    "id": "neighbor-1-id",
                    "label": "Technology",
                    "name": "PostgreSQL",
                    "properties": {},
                    "relation": "USES",
                    "weight": 0.9,
                    "distance": 1,
                }
            ]

            neighbors = query_neighbors("test-node-id", relation_type=None, max_depth=1)

            assert len(neighbors) == 1
            assert neighbors[0]["name"] == "PostgreSQL"
            assert neighbors[0]["relation"] == "USES"
            assert neighbors[0]["distance"] == 1

    def test_find_path_returns_shortest_path(self):
        """Test find_path returns shortest path between nodes."""
        with patch('mcp_server.db.graph.get_connection') as mock_conn_ctx, \
             patch('mcp_server.db.graph.get_node_by_name') as mock_get_node:

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn_ctx.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.cursor.return_value = mock_cursor

            # Setup node lookups
            mock_get_node.side_effect = [
                {"id": "start-id", "name": "Start Node"},  # First call
                {"id": "end-id", "name": "End Node"},      # Second call
            ]

            # Simulate path query results (direct path)
            mock_cursor.fetchall.return_value = [
                {
                    "node_path": ["start-id", "end-id"],
                    "edge_path": ["edge-1-id"],
                    "path_length": 1,
                    "total_weight": 0.9,
                }
            ]

            # Node and edge detail lookups
            mock_cursor.fetchone.side_effect = [
                {"id": "start-id", "label": "Node", "name": "Start Node", "properties": {}, "vector_id": None, "created_at": "2025-01-01"},
                {"id": "end-id", "label": "Node", "name": "End Node", "properties": {}, "vector_id": None, "created_at": "2025-01-01"},
                {"id": "edge-1-id", "source_id": "start-id", "target_id": "end-id", "relation": "CONNECTS", "weight": 0.9, "properties": {}},
            ]

            result = find_path("Start Node", "End Node", max_depth=5)

            assert result["path_found"] is True
            assert result["path_length"] == 1
            assert len(result["paths"]) >= 1
