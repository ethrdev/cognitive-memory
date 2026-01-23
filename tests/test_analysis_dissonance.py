"""
[P1] Analysis - Dissonance Detection Tests

Tests for dissonance detection and resolution in the cognitive memory system.

Priority: P1 (High) - Dissonance detection is important for maintaining coherent memory
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from mcp_server.analysis.dissonance import DissonanceDetector
from mcp_server.analysis.smf import SMFAnalyzer


@pytest.mark.P1
class TestDissonanceDetector:
    """P1 tests for dissonance detection functionality."""

    @pytest.fixture
    def dissonance_detector(self):
        """Create dissonance detector instance."""
        return DissonanceDetector(
            dissonance_threshold=0.7,
            evolution_threshold=0.5,
        )

    @pytest.mark.asyncio
    async def test_detect_dissonance_simple_case(self, dissonance_detector):
        """[P1] Detect dissonance should identify conflicting edges."""
        # GIVEN: Two conflicting edges
        edge1 = {
            "source": "Python",
            "target": "Best",
            "relation": "IS",
            "weight": 0.9,
            "context": "general_programming",
        }
        edge2 = {
            "source": "Python",
            "target": "Worst",
            "relation": "IS",
            "weight": 0.8,
            "context": "performance_critical",
        }

        # WHEN: Detecting dissonance
        result = await dissonance_detector.detect_dissonance(edge1, edge2)

        # THEN: Should identify contradiction
        assert result["dissonance_detected"] is True
        assert result["dissonance_type"] == "CONTRADICTION"
        assert result["dissonance_score"] > 0.5
        assert result["severity"] in ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_detect_dissonance_evolution_case(self, dissonance_detector):
        """[P1] Detect dissonance should identify evolution over time."""
        # GIVEN: Edges showing evolution
        old_edge = {
            "source": "Python",
            "target": "Slow",
            "relation": "IS",
            "weight": 0.7,
            "context": "python_2",
            "timestamp": "2020-01-01",
        }
        new_edge = {
            "source": "Python",
            "target": "Fast",
            "relation": "IS",
            "weight": 0.9,
            "context": "python_3_optimizations",
            "timestamp": "2024-01-01",
        }

        # WHEN: Detecting dissonance
        result = await dissonance_detector.detect_dissonance(old_edge, new_edge)

        # THEN: Should identify as evolution
        assert result["dissonance_detected"] is True
        assert result["dissonance_type"] == "EVOLUTION"
        assert result["temporal_context"] is not None

    @pytest.mark.asyncio
    async def test_detect_dissonance_no_conflict(self, dissonance_detector):
        """[P1] Detect dissonance should return no conflict for compatible edges."""
        # GIVEN: Two compatible edges
        edge1 = {
            "source": "Python",
            "target": "Programming",
            "relation": "IS_USED_FOR",
            "weight": 0.9,
        }
        edge2 = {
            "source": "Java",
            "target": "Programming",
            "relation": "IS_USED_FOR",
            "weight": 0.8,
        }

        # WHEN: Detecting dissonance
        result = await dissonance_detector.detect_dissonance(edge1, edge2)

        # THEN: Should not detect dissonance
        assert result["dissonance_detected"] is False
        assert result["dissonance_score"] < 0.3

    @pytest.mark.asyncio
    async def test_analyze_node_dissonance(self, dissonance_detector):
        """[P1] Analyze node dissonance should check all edges."""
        # GIVEN: Node with multiple edges
        node_name = "Python"
        edges = [
            {"source": "Python", "target": "Easy", "relation": "IS", "weight": 0.9},
            {"source": "Python", "target": "Difficult", "relation": "IS", "weight": 0.7},
            {"source": "Python", "target": "Dynamic", "relation": "IS", "weight": 0.8},
        ]

        # WHEN: Analyzing node dissonance
        result = await dissonance_detector.analyze_node_dissonance(
            node_name,
            edges
        )

        # THEN: Should analyze all edge pairs
        assert result["node"] == node_name
        assert result["total_edges"] == 3
        assert result["dissonant_pairs"] >= 0
        assert result["overall_dissonance"] >= 0.0
        assert result["overall_dissonance"] <= 1.0

    @pytest.mark.asyncio
    async def test_classify_dissonance_type(self, dissonance_detector):
        """[P1] Classify dissonance type should categorize correctly."""
        # TEST: Contradiction classification
        contradiction_edges = [
            {"source": "A", "target": "Good", "relation": "IS"},
            {"source": "A", "target": "Bad", "relation": "IS"},
        ]
        contradiction = await dissonance_detector.classify_dissonance_type(
            contradiction_edges[0],
            contradiction_edges[1]
        )
        assert contradiction["type"] == "CONTRADICTION"

        # TEST: Evolution classification
        evolution_edges = [
            {"source": "B", "target": "Old", "relation": "IS", "timestamp": "2020"},
            {"source": "B", "target": "New", "relation": "IS", "timestamp": "2024"},
        ]
        evolution = await dissonance_detector.classify_dissonance_type(
            evolution_edges[0],
            evolution_edges[1]
        )
        assert evolution["type"] == "EVOLUTION"

        # TEST: Nuance classification
        nuance_edges = [
            {"source": "C", "target": "Complex", "relation": "IS"},
            {"source": "C", "target": "Simple", "relation": "IS", "weight": 0.3},
        ]
        nuance = await dissonance_detector.classify_dissonance_type(
            nuance_edges[0],
            nuance_edges[1]
        )
        assert nuance["type"] == "NUANCE"


@pytest.mark.P1
class TestSMFAnalyzer:
    """P1 tests for SMF (Self-Modifying Framework) analysis."""

    @pytest.fixture
    def smf_analyzer(self):
        """Create SMF analyzer instance."""
        return SMFAnalyzer()

    @pytest.mark.asyncio
    async def test_analyze_proposal_impact(self, smf_analyzer):
        """[P1] Analyze proposal impact should assess changes."""
        # GIVEN: SMF proposal
        proposal = {
            "id": "prop_001",
            "type": "NUANCE",
            "action": "update_edge",
            "target": {"source": "Python", "relation": "IS", "target": "Fast"},
            "proposed_changes": {
                "weight": {"from": 0.5, "to": 0.8},
                "context": {"from": "general", "to": "optimized"}
            }
        }

        # WHEN: Analyzing impact
        impact = await smf_analyzer.analyze_proposal_impact(proposal)

        # THEN: Should assess impact correctly
        assert impact["proposal_id"] == "prop_001"
        assert impact["impact_level"] in ["low", "medium", "high"]
        assert impact["affected_nodes"] >= 0
        assert "risk_assessment" in impact

    @pytest.mark.asyncio
    async def test_validate_proposal(self, smf_analyzer):
        """[P1] Validate proposal should check proposal validity."""
        # GIVEN: Valid proposal
        valid_proposal = {
            "id": "prop_002",
            "type": "EVOLUTION",
            "target": {"source": "X", "relation": "RELATED_TO", "target": "Y"},
            "justification": "Performance improvements justify this change",
            "supporting_evidence": ["benchmark_1", "benchmark_2"],
        }

        # WHEN: Validating proposal
        validation = await smf_analyzer.validate_proposal(valid_proposal)

        # THEN: Should pass validation
        assert validation["valid"] is True
        assert validation["errors"] == []
        assert validation["warnings"] == []

    @pytest.mark.asyncio
    async def test_validate_proposal_invalid(self, smf_analyzer):
        """[P1] Validate proposal should reject invalid proposals."""
        # GIVEN: Invalid proposal
        invalid_proposal = {
            "id": "prop_003",
            "type": "INVALID_TYPE",
            # Missing required fields
        }

        # WHEN: Validating proposal
        validation = await smf_analyzer.validate_proposal(invalid_proposal)

        # THEN: Should fail validation
        assert validation["valid"] is False
        assert len(validation["errors"]) > 0

    @pytest.mark.asyncio
    async def test_check_consent_requirements(self, smf_analyzer):
        """[P1] Check consent requirements should identify when consent is needed."""
        # GIVEN: Constitutive edge modification proposal
        constitutive_proposal = {
            "id": "prop_004",
            "edge_type": "constitutive",
            "modification_type": "delete",
            "impact": "high",
        }

        # WHEN: Checking consent requirements
        consent_check = await smf_analyzer.check_consent_requirements(
            constitutive_proposal
        )

        # THEN: Should require consent
        assert consent_check["consent_required"] is True
        assert consent_check["consent_level"] == "bilateral"
        assert "io_consent" in consent_check
        assert "ethr_consent" in consent_check

    @pytest.mark.asyncio
    async def test_generate_resolution_recommendation(self, smf_analyzer):
        """[P2] Generate resolution recommendation should suggest actions."""
        # GIVEN: Dissonance case
        dissonance_case = {
            "type": "CONTRADICTION",
            "severity": "high",
            "edges": [
                {"source": "A", "target": "True", "relation": "IS"},
                {"source": "A", "target": "False", "relation": "IS"},
            ],
        }

        # WHEN: Generating recommendation
        recommendation = await smf_analyzer.generate_resolution_recommendation(
            dissonance_case
        )

        # THEN: Should provide actionable recommendation
        assert "recommended_action" in recommendation
        assert "rationale" in recommendation
        assert "alternative_actions" in recommendation
        assert recommendation["recommended_action"] in [
            "approve", "reject", "modify", "defer"
        ]


@pytest.mark.P2
class TestDissonanceIntegration:
    """P2 integration tests for dissonance detection system."""

    @pytest.mark.asyncio
    async def test_full_dissonance_detection_workflow(self):
        """[P2] Full workflow from detection to resolution."""
        # GIVEN: Dissonance detector and SMF analyzer
        detector = DissonanceDetector()
        analyzer = SMFAnalyzer()

        # WHEN: Running complete workflow
        # 1. Detect dissonance
        edges = [
            {"source": "Test", "target": "A", "relation": "IS", "weight": 0.9},
            {"source": "Test", "target": "B", "relation": "IS", "weight": 0.8},
        ]
        detection = await detector.analyze_node_dissonance("Test", edges)

        # 2. If dissonance detected, generate proposal
        if detection["overall_dissonance"] > 0.5:
            proposal = await analyzer.create_resolution_proposal(
                detection
            )
            # THEN: Proposal should be created
            assert proposal is not None
            assert "id" in proposal

    @pytest.mark.asyncio
    async def test_batch_dissonance_analysis(self, dissonance_detector):
        """[P2] Batch analysis should handle multiple nodes."""
        # GIVEN: Multiple nodes with edges
        nodes_data = {
            "Node1": [
                {"source": "Node1", "target": "A", "relation": "IS"},
                {"source": "Node1", "target": "B", "relation": "IS"},
            ],
            "Node2": [
                {"source": "Node2", "target": "C", "relation": "IS"},
            ],
        }

        # WHEN: Batch analysis runs
        results = await dissonance_detector.batch_analyze(nodes_data)

        # THEN: Should analyze all nodes
        assert len(results) == 2
        assert "Node1" in results
        assert "Node2" in results
        for node, result in results.items():
            assert "overall_dissonance" in result
            assert "dissonant_pairs" in result
