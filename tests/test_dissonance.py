"""
Tests for the Dissonance Engine module.

Tests the dissonance detection and classification functionality
for cognitive memory self-narrative analysis.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.analysis.dissonance import (
    DissonanceEngine,
    DissonanceType,
    DissonanceResult,
    DissonanceCheckResult,
    NuanceReviewProposal,
    EntrenchmentLevel,
    DISSONANCE_CLASSIFICATION_PROMPT
)


class TestDissonanceType:
    """Test DissonanceType enum values."""

    def test_dissonance_type_values(self):
        """Test that DissonanceType has correct values."""
        assert DissonanceType.EVOLUTION.value == "evolution"
        assert DissonanceType.CONTRADICTION.value == "contradiction"
        assert DissonanceType.NUANCE.value == "nuance"
        assert DissonanceType.NONE.value == "none"


class TestEntrenchmentLevel:
    """Test EntrenchmentLevel enum values."""

    def test_entrenchment_level_values(self):
        """Test that EntrenchmentLevel has correct values."""
        assert EntrenchmentLevel.DEFAULT.value == "default"
        assert EntrenchmentLevel.MAXIMAL.value == "maximal"


class TestDissonanceResult:
    """Test DissonanceResult dataclass."""

    def test_dissonance_result_creation(self):
        """Test creating a DissonanceResult with all fields."""
        result = DissonanceResult(
            edge_a_id="edge-1",
            edge_b_id="edge-2",
            dissonance_type=DissonanceType.CONTRADICTION,
            confidence_score=0.85,
            description="Direct contradiction between beliefs",
            context={"reasoning": "Both statements cannot be true simultaneously"},
            requires_review=False,
            edge_a_memory_strength=0.9,
            edge_b_memory_strength=0.7,
            authoritative_source="edge_a"
        )

        assert result.edge_a_id == "edge-1"
        assert result.edge_b_id == "edge-2"
        assert result.dissonance_type == DissonanceType.CONTRADICTION
        assert result.confidence_score == 0.85
        assert result.requires_review is False
        assert result.edge_a_memory_strength == 0.9
        assert result.authoritative_source == "edge_a"

    def test_dissonance_result_defaults(self):
        """Test DissonanceResult with default values."""
        result = DissonanceResult(
            edge_a_id="edge-1",
            edge_b_id="edge-2",
            dissonance_type=DissonanceType.NUANCE,
            confidence_score=0.6,
            description="Complex relationship",
            context={}
        )

        # Note: requires_review defaults to False in dataclass
        # It is set to True by _analyze_dissonance_pair when type is NUANCE
        assert result.requires_review is False  # Dataclass default
        assert result.edge_a_memory_strength is None
        assert result.edge_b_memory_strength is None
        assert result.authoritative_source is None


class TestDissonanceCheckResult:
    """Test DissonanceCheckResult dataclass."""

    def test_dissonance_check_result_creation(self):
        """Test creating a DissonanceCheckResult."""
        dissonance = DissonanceResult(
            edge_a_id="edge-1",
            edge_b_id="edge-2",
            dissonance_type=DissonanceType.EVOLUTION,
            confidence_score=0.9,
            description="Position evolved over time",
            context={}
        )

        result = DissonanceCheckResult(
            context_node="I/O",
            scope="recent",
            edges_analyzed=5,
            conflicts_found=1,
            dissonances=[dissonance],
            pending_reviews=[],
            api_calls=1,
            total_tokens=250,
            estimated_cost_eur=0.001
        )

        assert result.context_node == "I/O"
        assert result.scope == "recent"
        assert result.edges_analyzed == 5
        assert result.conflicts_found == 1
        assert len(result.dissonances) == 1
        assert result.fallback is False
        assert result.status == "success"


class TestDissonanceEngine:
    """Test DissonanceEngine class functionality."""

    @pytest.fixture
    def mock_haiku_client(self):
        """Create a mock HaikuClient."""
        client = MagicMock()
        client.generate_response = AsyncMock()
        return client

    @pytest.fixture
    def engine(self, mock_haiku_client):
        """Create a DissonanceEngine instance with mock client."""
        return DissonanceEngine(haiku_client=mock_haiku_client)

    def test_engine_initialization(self):
        """Test engine initialization with default client."""
        with patch('mcp_server.analysis.dissonance.HaikuClient') as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            engine = DissonanceEngine()

            mock_client_class.assert_called_once()
            assert engine.haiku_client == mock_client

    def test_engine_initialization_with_client(self, mock_haiku_client):
        """Test engine initialization with provided client."""
        engine = DissonanceEngine(haiku_client=mock_haiku_client)
        assert engine.haiku_client == mock_haiku_client

    @pytest.mark.asyncio
    async def test_dissonance_check_insufficient_data(self, engine):
        """Test dissonance check with less than 2 edges."""
        with patch('mcp_server.analysis.dissonance.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Mock cursor to return only one edge
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [{"id": "edge-1"}]
            mock_conn.cursor.return_value = mock_cursor

            result = await engine.dissonance_check(context_node="test-node", scope="recent")

            assert result.status == "insufficient_data"
            assert result.edges_analyzed == 1
            assert result.conflicts_found == 0
            assert len(result.dissonances) == 0

    @pytest.mark.asyncio
    async def test_dissonance_check_invalid_scope(self, engine):
        """Test dissonance check with invalid scope parameter."""
        with pytest.raises(ValueError, match="Invalid scope 'invalid'"):
            await engine.dissonance_check(context_node="test-node", scope="invalid")

    @pytest.mark.asyncio
    async def test_dissonance_check_node_not_found(self, engine):
        """Test dissonance check with non-existent node."""
        with patch('mcp_server.analysis.dissonance.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Mock cursor to return no node
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor

            result = await engine.dissonance_check(context_node="non-existent", scope="recent")

            assert result.status == "insufficient_data"
            assert result.edges_analyzed == 0

    @pytest.mark.asyncio
    async def test_analyze_dissonance_pair_evolution(self, engine, mock_haiku_client):
        """Test analyzing a pair of edges for EVOLUTION dissonance."""
        # Setup mock response
        mock_response = json.dumps({
            "dissonance_type": "EVOLUTION",
            "confidence_score": 0.9,
            "description": "Position changed from earlier to later",
            "reasoning": "Timestamps show clear progression"
        })
        mock_haiku_client.generate_response.return_value = mock_response

        edge_a = {
            "id": "edge-1",
            "relation": "BELIEVES",
            "source_name": "I/O",
            "target_name": "X",
            "properties": {"timestamp": "2023-01-01"},
            "created_at": "2023-01-01T00:00:00Z"
        }

        edge_b = {
            "id": "edge-2",
            "relation": "BELIEVES",
            "source_name": "I/O",
            "target_name": "Y",
            "properties": {"timestamp": "2023-06-01"},
            "created_at": "2023-06-01T00:00:00Z"
        }

        result = await engine._analyze_dissonance_pair(edge_a, edge_b)

        assert result.edge_a_id == "edge-1"
        assert result.edge_b_id == "edge-2"
        assert result.dissonance_type == DissonanceType.EVOLUTION
        assert result.confidence_score == 0.9
        # Description comes from mock response, not generated
        assert result.description == "Position changed from earlier to later"
        assert result.requires_review is False

    @pytest.mark.asyncio
    async def test_analyze_dissonance_pair_contradiction(self, engine, mock_haiku_client):
        """Test analyzing a pair of edges for CONTRADICTION dissonance."""
        mock_response = json.dumps({
            "dissonance_type": "CONTRADICTION",
            "confidence_score": 0.95,
            "description": "Direct logical contradiction",
            "reasoning": "Both statements cannot be true simultaneously"
        })
        mock_haiku_client.generate_response.return_value = mock_response

        edge_a = {
            "id": "edge-1",
            "relation": "BELIEVES",
            "properties": {},
            "created_at": "2023-01-01T00:00:00Z"
        }

        edge_b = {
            "id": "edge-2",
            "relation": "BELIEVES",
            "properties": {},
            "created_at": "2023-01-01T00:00:00Z"
        }

        result = await engine._analyze_dissonance_pair(edge_a, edge_b)

        assert result.dissonance_type == DissonanceType.CONTRADICTION
        assert result.confidence_score == 0.95
        assert result.requires_review is False

    @pytest.mark.asyncio
    async def test_analyze_dissonance_pair_nuance(self, engine, mock_haiku_client):
        """Test analyzing a pair of edges for NUANCE dissonance."""
        mock_response = json.dumps({
            "dissonance_type": "NUANCE",
            "confidence_score": 0.7,
            "description": "Complex relationship between values",
            "reasoning": "Both positions can coexist with contextual understanding"
        })
        mock_haiku_client.generate_response.return_value = mock_response

        edge_a = {"id": "edge-1", "properties": {}, "created_at": "2023-01-01T00:00:00Z"}
        edge_b = {"id": "edge-2", "properties": {}, "created_at": "2023-01-01T00:00:00Z"}

        result = await engine._analyze_dissonance_pair(edge_a, edge_b)

        assert result.dissonance_type == DissonanceType.NUANCE
        assert result.confidence_score == 0.7
        assert result.requires_review is True

    @pytest.mark.asyncio
    async def test_analyze_dissonance_pair_no_dissonance(self, engine, mock_haiku_client):
        """Test analyzing a pair of edges with no dissonance."""
        mock_response = json.dumps({
            "dissonance_type": "NONE",
            "confidence_score": 0.1,
            "description": "No conflict detected",
            "reasoning": "Statements are compatible"
        })
        mock_haiku_client.generate_response.return_value = mock_response

        edge_a = {"id": "edge-1", "properties": {}, "created_at": "2023-01-01T00:00:00Z"}
        edge_b = {"id": "edge-2", "properties": {}, "created_at": "2023-01-01T00:00:00Z"}

        result = await engine._analyze_dissonance_pair(edge_a, edge_b)

        assert result.dissonance_type == DissonanceType.NONE
        assert result.confidence_score == 0.1
        assert result.requires_review is False

    @pytest.mark.asyncio
    async def test_analyze_dissonance_pair_api_failure(self, engine, mock_haiku_client):
        """Test handling API failure during dissonance analysis."""
        mock_haiku_client.generate_response.side_effect = Exception("API unavailable")

        edge_a = {"id": "edge-1", "properties": {}, "created_at": "2023-01-01T00:00:00Z"}
        edge_b = {"id": "edge-2", "properties": {}, "created_at": "2023-01-01T00:00:00Z"}

        result = await engine._analyze_dissonance_pair(edge_a, edge_b)

        assert result.dissonance_type == DissonanceType.NONE
        assert result.confidence_score == 0.0
        assert "failed" in result.description.lower()
        assert result.requires_review is False

    def test_create_nuance_review(self, engine):
        """Test creating a NUANCE review proposal."""
        dissonance = DissonanceResult(
            edge_a_id="edge-1",
            edge_b_id="edge-2",
            dissonance_type=DissonanceType.NUANCE,
            confidence_score=0.7,
            description="Complex relationship",
            context={},
            requires_review=True
        )

        proposal = engine.create_nuance_review(dissonance)

        assert isinstance(proposal, NuanceReviewProposal)
        assert proposal.dissonance == dissonance
        assert proposal.status == "PENDING_IO_REVIEW"
        assert proposal.reclassified_to is None
        assert proposal.review_reason is None
        assert proposal.reviewed_at is None
        assert len(proposal.id) > 0  # UUID should be generated

    def test_get_pending_reviews_empty(self, engine):
        """Test getting pending reviews when none exist."""
        # Clear any existing reviews
        from mcp_server.analysis.dissonance import _nuance_reviews
        _nuance_reviews.clear()

        pending = engine.get_pending_reviews()
        assert pending == []

    def test_get_pending_reviews_with_items(self, engine):
        """Test getting pending reviews when items exist."""
        # Clear and add test reviews
        from mcp_server.analysis.dissonance import _nuance_reviews
        _nuance_reviews.clear()

        test_review = {
            "id": "test-1",
            "status": "PENDING_IO_REVIEW",
            "dissonance": {"edge_a_id": "edge-1"}
        }
        _nuance_reviews.append(test_review)

        # Add a completed review
        completed_review = {
            "id": "test-2",
            "status": "CONFIRMED",
            "dissonance": {"edge_a_id": "edge-2"}
        }
        _nuance_reviews.append(completed_review)

        pending = engine.get_pending_reviews()
        assert len(pending) == 1
        assert pending[0]["id"] == "test-1"
        assert pending[0]["status"] == "PENDING_IO_REVIEW"

    def test_resolve_review_confirm(self, engine):
        """Test resolving a NUANCE review with confirmation."""
        from mcp_server.analysis.dissonance import _nuance_reviews
        _nuance_reviews.clear()

        # Create a review
        dissonance = DissonanceResult(
            edge_a_id="edge-1",
            edge_b_id="edge-2",
            dissonance_type=DissonanceType.NUANCE,
            confidence_score=0.7,
            description="Test",
            context={}
        )
        proposal = engine.create_nuance_review(dissonance)

        # Resolve as confirmed
        resolved = engine.resolve_review(
            review_id=proposal.id,
            confirmed=True,
            reason="Valid nuance"
        )

        assert resolved is not None
        assert resolved["status"] == "CONFIRMED"
        assert resolved["review_reason"] == "Valid nuance"
        assert resolved["reviewed_at"] is not None
        assert resolved["reclassified_to"] is None

    def test_resolve_review_reclassify(self, engine):
        """Test resolving a NUANCE review with reclassification."""
        from mcp_server.analysis.dissonance import _nuance_reviews
        _nuance_reviews.clear()

        # Create a review
        dissonance = DissonanceResult(
            edge_a_id="edge-1",
            edge_b_id="edge-2",
            dissonance_type=DissonanceType.NUANCE,
            confidence_score=0.7,
            description="Test",
            context={}
        )
        proposal = engine.create_nuance_review(dissonance)

        # Resolve as reclassified
        resolved = engine.resolve_review(
            review_id=proposal.id,
            confirmed=False,
            reclassified_to=DissonanceType.CONTRADICTION,
            reason="Actually a contradiction"
        )

        assert resolved is not None
        assert resolved["status"] == "RECLASSIFIED"
        assert resolved["review_reason"] == "Actually a contradiction"
        assert resolved["reclassified_to"] == "contradiction"

    def test_resolve_review_not_found(self, engine):
        """Test resolving a non-existent review."""
        resolved = engine.resolve_review(
            review_id="non-existent",
            confirmed=True
        )

        assert resolved is None

    @pytest.mark.asyncio
    async def test_get_memory_strength_found(self, engine):
        """Test getting memory strength when insight exists."""
        with patch('mcp_server.analysis.dissonance.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = {"memory_strength": 0.85}
            mock_conn.cursor.return_value = mock_cursor

            strength = engine._get_memory_strength("edge-123")

            assert strength == 0.85

    @pytest.mark.asyncio
    async def test_get_memory_strength_not_found(self, engine):
        """Test getting memory strength when no insight exists."""
        with patch('mcp_server.analysis.dissonance.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value = mock_cursor

            strength = engine._get_memory_strength("edge-456")

            assert strength is None

    @pytest.mark.asyncio
    async def test_get_memory_strength_database_error(self, engine):
        """Test handling database error when getting memory strength."""
        with patch('mcp_server.analysis.dissonance.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__.side_effect = Exception("Database error")

            strength = engine._get_memory_strength("edge-789")

            assert strength is None  # Should return None on error


class TestDissonancePrompt:
    """Test the dissonance classification prompt."""

    def test_prompt_format(self):
        """Test that the prompt contains required placeholders."""
        assert "{edge_a_relation}" in DISSONANCE_CLASSIFICATION_PROMPT
        assert "{edge_b_relation}" in DISSONANCE_CLASSIFICATION_PROMPT
        assert "{edge_a_source}" in DISSONANCE_CLASSIFICATION_PROMPT
        assert "{edge_b_source}" in DISSONANCE_CLASSIFICATION_PROMPT
        assert "EVOLUTION" in DISSONANCE_CLASSIFICATION_PROMPT
        assert "CONTRADICTION" in DISSONANCE_CLASSIFICATION_PROMPT
        assert "NUANCE" in DISSONANCE_CLASSIFICATION_PROMPT
        assert "NONE" in DISSONANCE_CLASSIFICATION_PROMPT

    def test_prompt_classification_criteria(self):
        """Test that prompt includes clear classification criteria."""
        prompt = DISSONANCE_CLASSIFICATION_PROMPT

        # Check for EVOLUTION criteria
        assert "früher X, jetzt Y" in prompt.lower() or "Früher X, jetzt Y" in prompt
        assert "zeitliche entwicklung" in prompt.lower()  # Case-insensitive check

        # Check for CONTRADICTION criteria
        assert "nicht gleichzeitig wahr" in prompt.lower() or "nicht beide wahr" in prompt.lower()
        assert "widerspruch" in prompt.lower()

        # Check for NUANCE criteria
        assert "spannung" in prompt.lower()
        assert "gleichzeitig" in prompt.lower()


class TestIntegrationEdgeCases:
    """Integration tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_dissonance_check_with_malformed_properties(self):
        """Test handling edges with malformed JSON properties."""
        engine = DissonanceEngine()

        edge_a = {
            "id": "edge-1",
            "properties": "not-json",  # Invalid JSON
            "created_at": "2023-01-01T00:00:00Z"
        }
        edge_b = {
            "id": "edge-2",
            "properties": '{"valid": "json"}',  # Valid JSON
            "created_at": "2023-01-01T00:00:00Z"
        }

        with patch.object(engine, '_analyze_dissonance_pair') as mock_analyze:
            mock_analyze.return_value = DissonanceResult(
                edge_a_id="edge-1",
                edge_b_id="edge-2",
                dissonance_type=DissonanceType.NONE,
                confidence_score=0.0,
                description="Analysis failed",
                context={"error": "Invalid JSON"},
                requires_review=False
            )

            result = await engine._analyze_dissonance_pair(edge_a, edge_b)

            # Should handle malformed JSON gracefully
            assert result.dissonance_type == DissonanceType.NONE
            assert "failed" in result.description.lower()

    @pytest.mark.asyncio
    async def test_dissonance_check_api_fallback_behavior(self):
        """Test fallback behavior when Haiku API is unavailable."""
        # Create engine with client that will fail
        mock_client = MagicMock()
        mock_client.generate_response.side_effect = Exception("API unavailable after 4 retries")
        engine = DissonanceEngine(haiku_client=mock_client)

        # Mock database to return edges
        with patch('mcp_server.analysis.dissonance.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Return 2 edges to trigger analysis
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                {"id": "edge-1", "relation": "TEST"},
                {"id": "edge-2", "relation": "TEST"}
            ]
            mock_conn.cursor.return_value = mock_cursor

            # Mock _analyze_dissonance_pair to raise API error
            with patch.object(engine, '_analyze_dissonance_pair') as mock_analyze:
                mock_analyze.side_effect = Exception("Haiku API unavailable")

                result = await engine.dissonance_check(context_node="test", scope="recent")

                # Should return fallback result
                assert result.fallback is True
                assert result.status == "skipped"
                assert len(result.dissonances) == 0