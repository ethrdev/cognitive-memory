"""
[P1] Validation - IRR Validator Tests

Tests for Inter-Rater Reliability (IRR) validation and contingency planning.

Priority: P1 (High) - IRR validation ensures consistent evaluation quality
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import asyncio

from mcp_server.validation.irr_validator import IRRValidator
from mcp_server.validation.contingency import ContingencyPlanner


@pytest.mark.P1
class TestIRRValidator:
    """P1 tests for IRR validation functionality."""

    @pytest.fixture
    def irr_validator(self):
        """Create IRR validator instance."""
        return IRRValidator(
            min_irr_threshold=0.7,
            acceptable_irr_threshold=0.8,
        )

    @pytest.mark.asyncio
    async def test_calculate_cohens_kappa(self, irr_validator):
        """[P1] Calculate Cohen's Kappa should return correct IRR score."""
        # GIVEN: Two raters' evaluations
        rater1_scores = [1, 2, 1, 3, 2, 1, 2, 1, 3, 2]
        rater2_scores = [1, 2, 2, 3, 2, 1, 2, 1, 3, 2]

        # WHEN: Calculating Cohen's Kappa
        kappa = await irr_validator.calculate_cohens_kappa(
            rater1_scores,
            rater2_scores,
            categories=[1, 2, 3]
        )

        # THEN: Should return valid kappa score
        assert kappa["kappa"] >= -1.0
        assert kappa["kappa"] <= 1.0
        assert kappa["agreement"] >= 0.0
        assert kappa["agreement"] <= 1.0
        assert "interpretation" in kappa

    @pytest.mark.asyncio
    async def test_validate_evaluation_consistency(self, irr_validator):
        """[P1] Validate evaluation consistency should check IRR."""
        # GIVEN: Evaluations from multiple judges
        evaluations = {
            "judge_1": [0.8, 0.7, 0.9, 0.6, 0.8],
            "judge_2": [0.82, 0.68, 0.91, 0.59, 0.83],
            "judge_3": [0.79, 0.72, 0.88, 0.61, 0.81],
        }

        # WHEN: Validating consistency
        result = await irr_validator.validate_evaluation_consistency(evaluations)

        # THEN: Should assess consistency
        assert "overall_irr" in result
        assert "pairwise_irr" in result
        assert "consistency_status" in result
        assert result["consistency_status"] in ["pass", "warning", "fail"]
        assert "recommendations" in result

    @pytest.mark.asyncio
    async def test_detect_outlier_judges(self, irr_validator):
        """[P1] Detect outlier judges should identify inconsistent raters."""
        # GIVEN: Mixed quality evaluations
        evaluations = {
            "judge_1": [0.8, 0.7, 0.9, 0.8, 0.7],  # Consistent
            "judge_2": [0.8, 0.7, 0.9, 0.8, 0.7],  # Consistent
            "judge_3": [0.2, 0.9, 0.1, 0.8, 0.3],  # Inconsistent
        }

        # WHEN: Detecting outliers
        outliers = await irr_validator.detect_outlier_judges(evaluations)

        # THEN: Should identify judge_3 as outlier
        assert "judge_3" in outliers["outliers"]
        assert "judge_1" not in outliers["outliers"]
        assert "judge_2" not in outliers["outliers"]
        assert outliers["outlier_score"]["judge_3"] > 0.5

    @pytest.mark.asyncio
    async def test_calculate_fleiss_kappa(self, irr_validator):
        """[P1] Calculate Fleiss' Kappa for multiple raters."""
        # GIVEN: Multiple raters
        ratings = [
            {"rater_1": 1, "rater_2": 1, "rater_3": 2, "rater_4": 1},
            {"rater_1": 2, "rater_2": 2, "rater_3": 2, "rater_4": 2},
            {"rater_1": 3, "rater_2": 2, "rater_3": 3, "rater_4": 2},
        ]
        categories = [1, 2, 3]

        # WHEN: Calculating Fleiss' Kappa
        fleiss_kappa = await irr_validator.calculate_fleiss_kappa(
            ratings,
            categories
        )

        # THEN: Should return valid score
        assert fleiss_kappa["kappa"] >= -1.0
        assert fleiss_kappa["kappa"] <= 1.0
        assert "p_value" in fleiss_kappa
        assert "significance" in fleiss_kappa

    @pytest.mark.asyncio
    async def test_generate_irr_report(self, irr_validator):
        """[P1] Generate IRR report should create comprehensive summary."""
        # GIVEN: Evaluation data
        evaluations = {
            "judge_1": [0.8, 0.7, 0.9],
            "judge_2": [0.82, 0.68, 0.91],
            "judge_3": [0.79, 0.72, 0.88],
        }

        # WHEN: Generating report
        report = await irr_validator.generate_irr_report(evaluations)

        # THEN: Should contain comprehensive information
        assert "summary" in report
        assert "detailed_metrics" in report
        assert "judge_analysis" in report
        assert "recommendations" in report
        assert "passes_threshold" in report["summary"]

    @pytest.mark.asyncio
    async def test_check_irr_thresholds(self, irr_validator):
        """[P1] Check IRR thresholds should validate against standards."""
        # GIVEN: IRR results
        irr_results = {
            "cohens_kappa": 0.75,
            "fleiss_kappa": 0.78,
            "overall_agreement": 0.82,
        }

        # WHEN: Checking thresholds
        threshold_check = await irr_validator.check_irr_thresholds(irr_results)

        # THEN: Should evaluate against thresholds
        assert "meets_minimum" in threshold_check
        assert "meets_acceptable" in threshold_check
        assert "threshold_details" in threshold_check
        assert threshold_check["meets_minimum"] in [True, False]
        assert threshold_check["meets_acceptable"] in [True, False]


@pytest.mark.P1
class TestContingencyPlanner:
    """P1 tests for contingency planning."""

    @pytest.fixture
    def contingency_planner(self):
        """Create contingency planner instance."""
        return ContingencyPlanner()

    @pytest.mark.asyncio
    async def test_create_contingency_plan(self, contingency_planner):
        """[P1] Create contingency plan should handle IRR failures."""
        # GIVEN: IRR failure scenario
        irr_failure = {
            "status": "fail",
            "kappa": 0.45,  # Below 0.7 threshold
            "outliers": ["judge_3"],
            "failure_reasons": ["low_inter_rater_reliability"],
        }

        # WHEN: Creating contingency plan
        plan = await contingency_planner.create_contingency_plan(irr_failure)

        # THEN: Should provide action plan
        assert "actions" in plan
        assert len(plan["actions"]) > 0
        assert "immediate_actions" in plan
        assert "followup_actions" in plan
        assert plan["contingency_level"] in ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_handle_judge_conflict(self, contingency_planner):
        """[P1] Handle judge conflict should resolve disagreements."""
        # GIVEN: Judge conflict scenario
        conflict = {
            "type": "systematic_disagreement",
            "conflicting_judges": ["judge_2", "judge_4"],
            "conflict_severity": "high",
            "affected_evaluations": 15,
        }

        # WHEN: Handling conflict
        resolution = await contingency_planner.handle_judge_conflict(conflict)

        # THEN: Should provide resolution strategy
        assert "resolution_strategy" in resolution
        assert "recalibration_needed" in resolution
        assert "remediation_actions" in resolution

    @pytest.mark.asyncio
    async def test_validate_ground_truth(self, contingency_planner):
        """[P1] Validate ground truth should ensure quality standards."""
        # GIVEN: Ground truth data
        ground_truth = {
            "query_id": "gt_001",
            "expected_score": 0.85,
            "confidence": 0.9,
            "judge_agreement": 0.88,
        }

        # WHEN: Validating ground truth
        validation = await contingency_planner.validate_ground_truth(ground_truth)

        # THEN: Should validate quality
        assert "valid" in validation
        assert "quality_score" in validation
        assert "issues" in validation
        assert "recommendations" in validation


@pytest.mark.P2
class TestIRRIntegration:
    """P2 integration tests for IRR validation system."""

    @pytest.mark.asyncio
    async def test_end_to_end_irr_validation(self):
        """[P2] End-to-end IRR validation workflow."""
        # GIVEN: IRR validator and contingency planner
        validator = IRRValidator()
        planner = ContingencyPlanner()

        # WHEN: Running complete workflow
        # 1. Validate evaluations
        evaluations = {
            "judge_1": [0.8, 0.7, 0.9],
            "judge_2": [0.82, 0.68, 0.91],
            "judge_3": [0.79, 0.72, 0.88],
        }
        validation = await validator.validate_evaluation_consistency(evaluations)

        # 2. If fail, create contingency plan
        if validation["consistency_status"] == "fail":
            contingency = await planner.create_contingency_plan(validation)
            # THEN: Should have contingency plan
            assert contingency is not None
            assert "actions" in contingency

    @pytest.mark.asyncio
    async def test_irr_monitoring_workflow(self, irr_validator, contingency_planner):
        """[P2] IRR monitoring should continuously validate quality."""
        # GIVEN: Ongoing evaluation monitoring
        batch_evaluations = [
            {"batch_1": {"judge_1": [0.8], "judge_2": [0.82]}},
            {"batch_2": {"judge_1": [0.7], "judge_2": [0.68]}},
            {"batch_3": {"judge_1": [0.9], "judge_2": [0.91]}},
        ]

        # WHEN: Monitoring batches
        monitoring_results = []
        for batch in batch_evaluations:
            for batch_name, evaluations in batch.items():
                validation = await irr_validator.validate_evaluation_consistency(
                    evaluations
                )
                monitoring_results.append({
                    "batch": batch_name,
                    "validation": validation,
                })

        # THEN: Should track IRR over time
        assert len(monitoring_results) == 3
        for result in monitoring_results:
            assert "validation" in result
            assert "consistency_status" in result["validation"]
