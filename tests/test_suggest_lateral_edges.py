"""
Test Suggest Lateral Edges Tool

Tests for the suggest_lateral_edges MCP tool which recommends potential
connections between nodes based on semantic similarity.
"""

import pytest
from unittest.mock import Mock, patch
from mcp_server.tools.suggest_lateral_edges import suggest_lateral_edges


class TestSuggestLateralEdges:
    """Test cases for suggest_lateral_edges tool"""

    @pytest.mark.p2
    def test_suggest_edges_for_node(self, mock_db_connection):
        """
        [P2] Should suggest lateral edges for given node
        """
        # GIVEN: Node with potential connections
        node_name = "cognitive-memory"
        top_k = 5

        # Mock finding similar nodes
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("semantic-memory", "similar concept", 0.85),
            ("neural-networks", "related technology", 0.72),
            ("knowledge-graph", "adjacent concept", 0.68),
            ("machine-learning", "broader field", 0.55),
            ("embeddings", "enabling technology", 0.51),
        ]

        # WHEN: Requesting suggestions
        result = suggest_lateral_edges(mock_db_connection, node_name, top_k)

        # THEN: Should return suggestions
        assert "suggestions" in result
        assert len(result["suggestions"]) <= top_k
        assert all("node_name" in s for s in result["suggestions"])
        assert all("similarity_score" in s for s in result["suggestions"])

    @pytest.mark.p2
    def test_suggestions_ordered_by_similarity(self, mock_db_connection):
        """
        [P2] Should return suggestions ordered by similarity score
        """
        # GIVEN: Node with various similarity scores
        node_name = "test-node"
        top_k = 3

        # Mock unsorted results
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("low-similarity", "desc", 0.30),
            ("high-similarity", "desc", 0.90),
            ("medium-similarity", "desc", 0.60),
        ]

        # WHEN: Getting suggestions
        result = suggest_lateral_edges(mock_db_connection, node_name, top_k)

        # THEN: Should be ordered by similarity (descending)
        similarities = [s["similarity_score"] for s in result["suggestions"]]
        assert similarities == sorted(similarities, reverse=True)

    @pytest.mark.p2
    def test_minimum_similarity_threshold(self, mock_db_connection):
        """
        [P2] Should filter suggestions below minimum threshold
        """
        # GIVEN: Node with mixed similarity scores
        node_name = "threshold-node"
        top_k = 10

        # Mock various similarity scores
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("very-similar", "desc", 0.95),
            ("somewhat-similar", "desc", 0.45),
            ("barely-similar", "desc", 0.20),
            ("not-similar", "desc", 0.05),
        ]

        # WHEN: Getting suggestions
        result = suggest_lateral_edges(mock_db_connection, node_name, top_k)

        # THEN: Should filter low-similarity results
        assert all(s["similarity_score"] >= 0.30 for s in result["suggestions"])

    @pytest.mark.p2
    def test_no_suggestions_for_isolated_node(self, mock_db_connection):
        """
        [P2] Should return empty suggestions for isolated node
        """
        # GIVEN: Node with no similar nodes
        node_name = "isolated-node"
        top_k = 5

        # Mock no similar nodes
        mock_db_connection.execute.return_value.fetchall.return_value = []

        # WHEN: Requesting suggestions
        result = suggest_lateral_edges(mock_db_connection, node_name, top_k)

        # THEN: Should return empty list
        assert "suggestions" in result
        assert len(result["suggestions"]) == 0
        assert result["count"] == 0

    @pytest.mark.p2
    def test_limit_top_k_suggestions(self, mock_db_connection):
        """
        [P2] Should limit results to top_k suggestions
        """
        # GIVEN: Node with many potential connections
        node_name = "popular-node"
        top_k = 3

        # Mock many similar nodes
        mock_db_connection.execute.return_value.fetchall.return_value = [
            (f"node-{i}", "desc", 1.0 - (i * 0.05))
            for i in range(10)
        ]

        # WHEN: Requesting limited suggestions
        result = suggest_lateral_edges(mock_db_connection, node_name, top_k)

        # THEN: Should return exactly top_k results
        assert len(result["suggestions"]) == top_k
        assert result["count"] == top_k

    @pytest.mark.p2
    def test_exclude_existing_connections(self, mock_db_connection):
        """
        [P2] Should exclude nodes already connected to source
        """
        # GIVEN: Node with some existing connections
        node_name = "existing-connections"
        top_k = 10

        # Mock nodes including some already connected
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("connected-node-1", "already connected", 0.90),
            ("unconnected-node", "not connected", 0.80),
            ("connected-node-2", "already connected", 0.70),
        ]

        # WHEN: Getting suggestions
        result = suggest_lateral_edges(mock_db_connection, node_name, top_k)

        # THEN: Should not suggest already connected nodes
        # (Implementation should filter out existing edges)
        node_names = [s["node_name"] for s in result["suggestions"]]
        assert "connected-node-1" not in node_names
        assert "connected-node-2" not in node_names
        assert "unconnected-node" in node_names

    @pytest.mark.p2
    def test_similarity_score_range(self, mock_db_connection):
        """
        [P2] Should return similarity scores in valid range [0, 1]
        """
        # GIVEN: Various similarity scores
        node_name = "score-test"
        top_k = 5

        # Mock different score ranges
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("high-score", "desc", 0.99),
            ("medium-score", "desc", 0.50),
            ("low-score", "desc", 0.01),
        ]

        # WHEN: Getting suggestions
        result = suggest_lateral_edges(mock_db_connection, node_name, top_k)

        # THEN: All scores should be in valid range
        for suggestion in result["suggestions"]:
            score = suggestion["similarity_score"]
            assert 0.0 <= score <= 1.0

    @pytest.mark.p3
    def test_include_description_metadata(self, mock_db_connection):
        """
        [P3] Should include description metadata for suggestions
        """
        # GIVEN: Nodes with descriptions
        node_name = "metadata-node"
        top_k = 3

        # Mock nodes with descriptions
        mock_db_connection.execute.return_value.fetchall.return_value = [
            ("node-a", "A related concept", 0.85),
            ("node-b", "Another related concept", 0.72),
        ]

        # WHEN: Getting suggestions
        result = suggest_lateral_edges(mock_db_connection, node_name, top_k)

        # THEN: Should include description
        assert all("description" in s for s in result["suggestions"])


@pytest.fixture
def mock_db_connection():
    """Create mock database connection"""
    mock_conn = Mock()
    return mock_conn
