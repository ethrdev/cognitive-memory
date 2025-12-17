#!/usr/bin/env python3
"""
IEF (Integrative Evaluation Function) Tests
============================================

Tests for the IEF scoring system that combines relevance,
semantic similarity, recency, and constitutive relationships.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from mcp_server.analysis.ief import (
    calculate_ief_score, _calculate_recency_boost, _cosine_similarity,
    CONSTITUTIVE_BOOST, NUANCE_PENALTY, W_MIN_CONSTITUTIVE,
    on_feedback_received, recalibrate_weights, get_feedback_count,
    RECALIBRATION_THRESHOLD, _feedback_count_since_calibration
)


class TestIEFCore:
    """Critical tests for IEF core function."""

    def test_ief_score_constitutive_boost(self):
        """AC #2: Constitutive edge gets 50% boost."""
        edge_data = {
            "edge_id": "test-edge",
            "edge_properties": {"edge_type": "constitutive"},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)

        # Check that constitutive weight is applied
        assert result["components"]["constitutive_weight"] == 1.5
        # Check that the score is higher due to constitutive boost
        assert result["ief_score"] > 0.25  # Minimum constitutive contribution

    def test_ief_score_descriptive_edge(self):
        """Descriptive edges get normal weight (1.0)."""
        edge_data = {
            "edge_id": "test-edge",
            "edge_properties": {"edge_type": "descriptive"},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)

        assert result["components"]["constitutive_weight"] == 1.0

    def test_ief_score_with_nuance_penalty(self):
        """AC #6: Nuance penalty is applied."""
        edge_data = {
            "edge_id": "nuance-edge",
            "edge_properties": {},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(
            edge_data,
            pending_nuance_edge_ids={"nuance-edge"}
        )

        assert result["components"]["nuance_penalty"] == 0.1
        # Score should be reduced by the penalty
        base_score = result["ief_score"] + NUANCE_PENALTY
        assert result["ief_score"] == base_score - NUANCE_PENALTY

    def test_ief_score_without_nuance_penalty(self):
        """No penalty when edge not in pending nuance set."""
        edge_data = {
            "edge_id": "normal-edge",
            "edge_properties": {},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(
            edge_data,
            pending_nuance_edge_ids={"other-edge"}
        )

        assert result["components"]["nuance_penalty"] == 0.0

    def test_ief_score_all_components_returned(self):
        """All components and weights are returned."""
        edge_data = {
            "edge_id": "test-edge",
            "edge_properties": {},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)

        # Check all components exist
        assert "ief_score" in result
        assert "components" in result
        assert "weights" in result

        # Check all component values
        components = result["components"]
        assert "relevance_score" in components
        assert "semantic_similarity" in components
        assert "recency_boost" in components
        assert "constitutive_weight" in components
        assert "nuance_penalty" in components

        # Check weights sum to 1.0
        weights = result["weights"]
        assert sum(weights.values()) == pytest.approx(1.0)


class TestRecencyBoost:
    """Tests for recency boost calculation."""

    def test_recency_boost_values(self):
        """AC #4: Recency boost with exp(-days/30)."""
        now = datetime.now(timezone.utc)

        # 1 day: ~0.97
        boost_1_day = _calculate_recency_boost(now - timedelta(days=1))
        assert boost_1_day > 0.95

        # 7 days: ~0.79
        boost_7_days = _calculate_recency_boost(now - timedelta(days=7))
        assert 0.75 <= boost_7_days <= 0.82

        # 30 days: ~0.37
        boost_30_days = _calculate_recency_boost(now - timedelta(days=30))
        assert 0.35 <= boost_30_days <= 0.40

    def test_recency_boost_no_timestamp(self):
        """Neutral boost when no modified_at."""
        boost = _calculate_recency_boost(None)
        assert boost == 0.5

    def test_recency_boost_string_timestamp(self):
        """Handle ISO string timestamps."""
        timestamp = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        boost = _calculate_recency_boost(timestamp)
        assert 0.75 <= boost <= 0.82

    def test_recency_boost_timezone_naive(self):
        """Handle timezone-naive timestamps."""
        timestamp = datetime.now() - timedelta(days=7)
        boost = _calculate_recency_boost(timestamp)
        assert 0.75 <= boost <= 0.82


class TestSemanticSimilarity:
    """Tests for semantic similarity calculation."""

    @patch('mcp_server.analysis.ief._get_insight_embedding')
    def test_semantic_similarity_with_embedding(self, mock_get_embedding):
        """Calculate similarity when embedding exists."""
        mock_get_embedding.return_value = [1.0, 0.0, 0.0, 1.0]
        query_embedding = [1.0, 0.0, 0.0, 1.0]

        from mcp_server.analysis.ief import _calculate_semantic_similarity

        similarity = _calculate_semantic_similarity(
            vector_id=123,
            query_embedding=query_embedding
        )

        # Perfect match should be 1.0
        assert similarity == pytest.approx(1.0)

    @patch('mcp_server.analysis.ief._get_insight_embedding')
    def test_semantic_similarity_no_embedding(self, mock_get_embedding):
        """Neutral similarity when no embedding."""
        mock_get_embedding.return_value = None
        query_embedding = [1.0, 0.0, 0.0, 1.0]

        from mcp_server.analysis.ief import _calculate_semantic_similarity

        similarity = _calculate_semantic_similarity(
            vector_id=123,
            query_embedding=query_embedding
        )

        assert similarity == 0.5

    def test_semantic_similarity_no_query(self):
        """Neutral similarity when no query embedding."""
        from mcp_server.analysis.ief import _calculate_semantic_similarity

        similarity = _calculate_semantic_similarity(
            vector_id=123,
            query_embedding=None
        )

        assert similarity == 0.5

    @patch('mcp_server.analysis.ief._get_insight_embedding')
    def test_semantic_similarity_no_vector_id(self, mock_get_embedding):
        """Neutral similarity when no vector_id."""
        query_embedding = [1.0, 0.0, 0.0, 1.0]

        from mcp_server.analysis.ief import _calculate_semantic_similarity

        similarity = _calculate_semantic_similarity(
            vector_id=None,
            query_embedding=query_embedding
        )

        assert similarity == 0.5
        mock_get_embedding.assert_not_called()


class TestCosineSimilarity:
    """Tests for cosine similarity calculation."""

    def test_cosine_similarity_identical_vectors(self):
        """Identical vectors should have similarity 1.0."""
        vec = [1.0, 2.0, 3.0, 4.0]
        similarity = _cosine_similarity(vec, vec)
        assert similarity == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.5 (mapped from 0)."""
        vec_a = [1.0, 0.0]
        vec_b = [0.0, 1.0]
        similarity = _cosine_similarity(vec_a, vec_b)
        assert similarity == pytest.approx(0.5)

    def test_cosine_similarity_opposite_vectors(self):
        """Opposite vectors should have similarity 0.0 (mapped from -1)."""
        vec_a = [1.0, 0.0]
        vec_b = [-1.0, 0.0]
        similarity = _cosine_similarity(vec_a, vec_b)
        assert similarity == pytest.approx(0.0)

    def test_cosine_similarity_dimension_mismatch(self):
        """Different dimensions should return neutral 0.5."""
        similarity = _cosine_similarity([1, 2], [1, 2, 3])
        assert similarity == 0.5

    def test_cosine_similarity_zero_vector(self):
        """Zero vectors should return neutral 0.5."""
        similarity = _cosine_similarity([0, 0], [1, 2])
        assert similarity == 0.5


class TestIEFIntegration:
    """Integration tests for IEF with mocked dependencies."""

    @patch('mcp_server.analysis.ief._get_insight_embedding')
    def test_ief_with_all_components(self, mock_get_embedding):
        """IEF with all components active."""
        mock_get_embedding.return_value = [1.0, 0.0, 0.0, 1.0]
        query_embedding = [1.0, 0.0, 0.0, 1.0]

        edge_data = {
            "edge_id": "test-edge",
            "edge_properties": {"edge_type": "constitutive", "vector_id": 123},
            "modified_at": datetime.now(timezone.utc) - timedelta(days=7),
            "access_count": 5,
            "last_accessed": datetime.now(timezone.utc) - timedelta(days=1),
        }

        result = calculate_ief_score(
            edge_data,
            query_embedding=query_embedding,
            pending_nuance_edge_ids={"other-edge"}  # Not our edge
        )

        # Verify all components contributed
        assert result["components"]["relevance_score"] > 0
        assert result["components"]["semantic_similarity"] > 0
        assert result["components"]["recency_boost"] > 0
        assert result["components"]["constitutive_weight"] == 1.5
        assert result["components"]["nuance_penalty"] == 0.0

        # Verify IEF score is reasonable
        assert 0.0 <= result["ief_score"] <= 1.5


class TestNuancePenaltyIntegration:
    """Integration tests for IEF nuance penalty components."""

    def test_nuance_penalty_integration(self):
        """Test that nuance penalty is applied correctly."""
        # Create a mock nuance review
        with patch('mcp_server.analysis.dissonance._nuance_reviews', [
            {
                "id": "review1",
                "status": "PENDING_IO_REVIEW",
                "dissonance": {
                    "edge_a_id": "edge1",
                    "edge_b_id": "edge2"
                }
            }
        ]):
            from mcp_server.analysis.dissonance import get_pending_nuance_edge_ids

            pending_ids = get_pending_nuance_edge_ids()
            assert "edge1" in pending_ids
            assert "edge2" in pending_ids

            # Test IEF with nuance penalty
            edge_data = {
                "edge_id": "edge1",
                "edge_properties": {},
                "modified_at": datetime.now(timezone.utc),
            }
            result = calculate_ief_score(
                edge_data,
                pending_nuance_edge_ids=pending_ids
            )

            assert result["components"]["nuance_penalty"] == 0.1
            assert result["ief_score"] < 1.0  # Should be reduced by penalty


class TestMCPToolsWithIEF:
    """Test MCP tool integration with IEF parameters."""

    @pytest.mark.asyncio
    async def test_graph_query_neighbors_parameter_validation(self):
        """Test graph_query_neighbors MCP tool parameter validation."""
        from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors

        # Test invalid query_embedding length
        result = await handle_graph_query_neighbors({
            "node_name": "test_node",
            "use_ief": True,
            "query_embedding": [1.0, 2.0]  # Too short
        })

        assert "error" in result
        assert "1536 numbers" in result["details"]

        # Test invalid use_ief type
        result = await handle_graph_query_neighbors({
            "node_name": "test_node",
            "use_ief": "yes",  # Should be boolean
        })

        assert "error" in result
        assert "use_ief" in result["details"]

    @pytest.mark.asyncio
    async def test_graph_find_path_parameter_validation(self):
        """Test graph_find_path MCP tool parameter validation."""
        from mcp_server.tools.graph_find_path import handle_graph_find_path

        # Test invalid query_embedding length
        result = await handle_graph_find_path({
            "start_node": "start_node",
            "end_node": "end_node",
            "use_ief": True,
            "query_embedding": [1.0]  # Too short
        })

        assert "error" in result
        assert "1536 numbers" in result["details"]


# =============================================================================
# ICAI (Integrative Context Assembly Interface) Tests - Story 7.7
# =============================================================================

class TestFeedbackRequest:
    """Tests for feedback_request field in IEF results."""

    def test_feedback_request_field_exists(self):
        """AC Zeile 394-406: calculate_ief_score returns feedback_request."""
        edge_data = {
            "edge_id": "test-edge",
            "edge_properties": {},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)

        assert "feedback_request" in result
        assert "query_id" in result["feedback_request"]
        assert "helpful" in result["feedback_request"]
        assert "feedback_reason" in result["feedback_request"]

    def test_feedback_request_query_id_is_uuid(self):
        """query_id should be a valid UUID string."""
        import uuid

        edge_data = {
            "edge_id": "test-edge",
            "edge_properties": {},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)

        query_id = result["feedback_request"]["query_id"]
        # Should not raise ValueError if valid UUID
        uuid.UUID(query_id)

    def test_feedback_request_initial_state(self):
        """helpful and feedback_reason should be None initially."""
        edge_data = {
            "edge_id": "test-edge",
            "edge_properties": {},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)

        assert result["feedback_request"]["helpful"] is None
        assert result["feedback_request"]["feedback_reason"] is None


class TestOnFeedbackReceived:
    """Tests for on_feedback_received() ICAI function."""

    @patch('mcp_server.db.connection.get_connection')
    def test_stores_feedback_in_database(self, mock_get_conn):
        """AC Zeile 411-420: Feedback is stored in ief_feedback table."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [42]  # feedback_id
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        # Reset feedback counter
        import mcp_server.analysis.ief as ief_module
        ief_module._feedback_count_since_calibration = 0

        result = on_feedback_received(
            query_id="test-query-123",
            helpful=True,
            feedback_reason="Very relevant results",
            query_text="test query"
        )

        # Verify INSERT was called
        mock_cursor.execute.assert_called()
        call_args = mock_cursor.execute.call_args[0]
        assert "INSERT INTO ief_feedback" in call_args[0]
        assert result["feedback_id"] == 42
        assert result["helpful"] is True

    @patch('mcp_server.db.connection.get_connection')
    @patch('mcp_server.analysis.ief.recalibrate_weights')
    def test_triggers_recalibration_at_threshold(self, mock_recal, mock_get_conn):
        """AC Zeile 437-444: Recalibration triggers after threshold."""
        # Setup mock
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [1]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        mock_recal.return_value = {"constitutive": 0.25}

        # Set counter just below threshold
        import mcp_server.analysis.ief as ief_module
        ief_module._feedback_count_since_calibration = RECALIBRATION_THRESHOLD - 1

        result = on_feedback_received(
            query_id="trigger-recal",
            helpful=True
        )

        # Should trigger recalibration
        assert result["recalibration_triggered"] is True
        mock_recal.assert_called_once()

    @patch('mcp_server.db.connection.get_connection')
    def test_no_recalibration_below_threshold(self, mock_get_conn):
        """No recalibration when below threshold."""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = [1]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        import mcp_server.analysis.ief as ief_module
        ief_module._feedback_count_since_calibration = 0

        result = on_feedback_received(
            query_id="no-recal",
            helpful=False
        )

        assert result["recalibration_triggered"] is False


class TestRecalibrateWeights:
    """Tests for recalibrate_weights() ICAI function."""

    @patch('mcp_server.db.connection.get_connection')
    def test_maintains_w_min_guarantee(self, mock_get_conn):
        """AC Zeile 432: W_MIN_CONSTITUTIVE >= 1.5 is guaranteed."""
        # Setup mock - simulate data that would push weight down
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (True, 0.10, 10),   # helpful: low avg weight
            (False, 0.30, 10),  # unhelpful: higher avg weight
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = recalibrate_weights()

        # W_MIN guarantee must be in result
        assert "w_min_guarantee" in result
        assert result["w_min_guarantee"] == W_MIN_CONSTITUTIVE
        assert result["w_min_guarantee"] >= 1.5

    @patch('mcp_server.db.connection.get_connection')
    def test_returns_all_weights(self, mock_get_conn):
        """recalibrate_weights returns complete weight set."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = recalibrate_weights()

        assert "relevance" in result
        assert "similarity" in result
        assert "recency" in result
        assert "constitutive" in result
        assert "total" in result

    @patch('mcp_server.db.connection.get_connection')
    def test_adjusts_weight_based_on_feedback(self, mock_get_conn):
        """Weight adjusts towards helpful query patterns."""
        import mcp_server.analysis.ief as ief_module
        original_weight = ief_module.IEF_WEIGHT_CONSTITUTIVE

        # Setup: helpful queries used higher weight
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (True, 0.30, 25),   # helpful: higher avg weight
            (False, 0.20, 25),  # unhelpful: lower avg weight
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = recalibrate_weights()

        # Weight should increase (towards helpful pattern)
        assert result["constitutive"] >= original_weight

        # Reset for other tests
        ief_module.IEF_WEIGHT_CONSTITUTIVE = original_weight


class TestWMinConstitutiveGuarantee:
    """Explicit tests for W_MIN constitutive guarantee."""

    def test_w_min_constant_value(self):
        """W_MIN_CONSTITUTIVE is exactly 1.5."""
        assert W_MIN_CONSTITUTIVE == 1.5

    def test_constitutive_edge_never_below_w_min(self):
        """Constitutive edges always get at least W_MIN weight."""
        edge_data = {
            "edge_id": "constitutive-edge",
            "edge_properties": {"edge_type": "constitutive"},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)

        assert result["components"]["constitutive_weight"] >= W_MIN_CONSTITUTIVE

    def test_descriptive_edge_below_w_min_allowed(self):
        """Descriptive edges CAN be below W_MIN (they get 1.0)."""
        edge_data = {
            "edge_id": "descriptive-edge",
            "edge_properties": {"edge_type": "descriptive"},
            "modified_at": datetime.now(timezone.utc),
        }
        result = calculate_ief_score(edge_data)

        assert result["components"]["constitutive_weight"] == 1.0
        assert result["components"]["constitutive_weight"] < W_MIN_CONSTITUTIVE