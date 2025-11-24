"""
Comprehensive Tests for : IRR Validation & Contingency Plan

This test suite covers all components of the IRR validation system:
- Global Kappa calculation (macro and micro averaging)
- Success path validation (kappa >= 0.70)
- Contingency path activation (kappa < 0.70)
- Wilcoxon Signed-Rank Test for systematic bias
- High disagreement query identification
- Judge recalibration logic
"""

import tempfile
from unittest.mock import Mock, patch

import numpy as np
import pytest

from mcp_server.validation.contingency import (
    ContingencyManager,
    HighDisagreementAnalyzer,
    JudgeRecalibration,
    ThresholdAdjustmentRecommender,
)
from mcp_server.validation.irr_validator import (
    IRRValidator,
    run_irr_validation,
)


class TestIRRCalculations:
    """Test Cohen's Kappa calculations for IRR validation"""

    def test_macro_average_kappa_calculation(self):
        """Test macro-average kappa calculation (Task 1, Subtask 4)"""
        # Setup: Mock 5 queries mit bekannten Kappas
        queries = [
            {"kappa": 0.80},
            {"kappa": 0.75},
            {"kappa": 0.65},
            {"kappa": 0.70},
            {"kappa": 0.85},
        ]

        # Execute
        validator = IRRValidator()
        macro_kappa = validator.calculate_macro_average_kappa(queries)

        # Verify
        expected = sum([0.80, 0.75, 0.65, 0.70, 0.85]) / 5  # 0.75
        assert macro_kappa == pytest.approx(expected, abs=0.01)

    @patch("mcp_server.validation.irr_validator.DualJudgeEvaluator")
    def test_micro_average_kappa_calculation(self, mock_evaluator):
        """Test micro-average kappa calculation (Task 1, Subtask 5)"""
        # Setup: Mock the Cohen's Kappa calculation
        mock_evaluator.return_value._calculate_cohen_kappa.return_value = 0.85

        # Setup: Pool all documents from all queries
        judge1_all = [0.8, 0.6, 0.3, 0.9, 0.4, 0.7, 0.5, 0.2]  # 8 docs
        judge2_all = [0.7, 0.6, 0.2, 0.8, 0.4, 0.6, 0.5, 0.3]  # 8 docs

        queries = [{"judge1_score": judge1_all, "judge2_score": judge2_all}]

        # Execute
        validator = IRRValidator()
        micro_kappa = validator.calculate_micro_average_kappa(queries)

        # Verify (should be high since scores are very similar)
        assert micro_kappa == 0.85  # Mocked value

    def test_kappa_calculation_with_empty_data(self):
        """Test kappa calculation with empty data"""
        validator = IRRValidator()

        # Test macro calculation with empty queries
        assert validator.calculate_macro_average_kappa([]) == 0.0

        # Test micro calculation with queries that have no scores
        empty_queries = [{"judge1_score": [], "judge2_score": []}]
        assert validator.calculate_micro_average_kappa(empty_queries) == 0.0

    def test_kappa_calculation_with_none_values(self):
        """Test kappa calculation handles None values gracefully"""
        validator = IRRValidator()

        # Test with None kappa values
        queries_with_none = [{"kappa": 0.80}, {"kappa": None}, {"kappa": 0.70}]

        macro_kappa = validator.calculate_macro_average_kappa(queries_with_none)
        expected = (0.80 + 0.70) / 2  # Should ignore None values
        assert macro_kappa == pytest.approx(expected, abs=0.01)


class TestSuccessPathValidation:
    """Test success path when kappa >= 0.70 (AC: 2)"""

    @patch("mcp_server.validation.irr_validator.get_connection")
    def test_validation_success_path(self, mock_get_connection):
        """Test success path with kappa >= 0.70 (Task 2)"""
        # Setup mock database response
        mock_queries = [MockQuery(kappa=0.75) for _ in range(100)]
        _setup_mock_database(mock_get_connection, mock_queries)

        # Execute
        results = run_irr_validation()

        # Verify
        assert results["status"] == "passed"
        assert results["kappa_macro"] == pytest.approx(0.75, abs=0.01)
        assert not results["contingency_triggered"]
        assert len(results["high_disagreement_queries"]) == 0
        assert "IRR Validation Passed" in results["notes"]

    @patch("mcp_server.validation.irr_validator.get_connection")
    def test_validation_saves_success_results(self, mock_get_connection):
        """Test that success results are saved to database"""
        mock_queries = [MockQuery(kappa=0.80) for _ in range(50)]
        mock_conn = _setup_mock_database(mock_get_connection, mock_queries)

        # Execute
        run_irr_validation()

        # Verify database insertion was called
        mock_conn.cursor().execute.assert_called()
        mock_conn.commit.assert_called()


class TestContingencyPathValidation:
    """Test contingency path when kappa < 0.70 (AC: 3)"""

    @patch("mcp_server.validation.irr_validator.get_connection")
    def test_validation_contingency_path(self, mock_get_connection):
        """Test contingency path with kappa < 0.70 (Task 3)"""
        # Setup: Mock 100 queries mit Kappa 0.65
        mock_queries = [MockQuery(kappa=0.65) for _ in range(100)]
        _setup_mock_database(mock_get_connection, mock_queries)

        # Execute
        results = run_irr_validation()

        # Verify
        assert results["status"] == "contingency_triggered"
        assert results["kappa_macro"] == pytest.approx(0.65, abs=0.01)
        assert results["contingency_triggered"]
        assert len(results["high_disagreement_queries"]) > 0
        assert len(results["contingency_actions"]) > 0

    @patch("mcp_server.validation.irr_validator.get_connection")
    def test_high_disagreement_identification(self, mock_get_connection):
        """Test high disagreement query identification (Task 3.1)"""
        # Setup: Create queries with varying disagreement levels
        mock_queries = [
            MockQuery(kappa=0.65, disagreement=0.5),  # High disagreement
            MockQuery(kappa=0.80, disagreement=0.1),  # Low disagreement
            MockQuery(kappa=0.60, disagreement=0.6),  # Very high disagreement
            MockQuery(kappa=0.90, disagreement=0.05),  # Very low disagreement
        ]
        _setup_mock_database(mock_get_connection, mock_queries)

        # Execute
        validator = IRRValidator()
        high_disagreement = validator.identify_high_disagreement_queries(mock_queries)

        # Verify
        assert (
            len(high_disagreement) == 2
        )  # Should identify queries with disagreement > 0.4 or kappa < 0.70
        assert (
            high_disagreement[0]["avg_disagreement"] == 0.6
        )  # Highest disagreement first
        assert high_disagreement[1]["avg_disagreement"] == 0.5


class TestWilcoxonSignedRankTest:
    """Test Wilcoxon Signed-Rank Test for systematic bias (AC: 3.2)"""

    def test_wilcoxon_systematic_bias_detection(self):
        """Test Wilcoxon test detects systematic bias (Task 5)"""
        # Setup: GPT-4o systematisch +0.1 höher als Haiku
        judge1_scores = [
            0.7,
            0.8,
            0.6,
            0.9,
            0.5,
            0.75,
            0.65,
            0.85,
            0.72,
            0.78,
            0.68,
            0.82,
        ]
        judge2_scores = [
            0.6,
            0.7,
            0.5,
            0.8,
            0.4,
            0.65,
            0.55,
            0.75,
            0.62,
            0.68,
            0.58,
            0.72,
        ]  # Consistent -0.1 difference

        queries = [{"judge1_score": judge1_scores, "judge2_score": judge2_scores}]

        # Execute
        recommender = ThresholdAdjustmentRecommender()
        result = recommender.analyze_systematic_bias(queries)

        # Verify
        assert result is not None
        assert result["significant_bias"]
        assert result["p_value"] < 0.05
        assert pytest.approx(result["median_difference"], 0.01) == 0.1
        assert result["threshold_adjustment"] is not None
        assert result["threshold_adjustment"]["judge"] == "GPT-4o"

    def test_wilcoxon_no_systematic_bias(self):
        """Test Wilcoxon test when no systematic bias exists"""
        # Setup: Random variation without systematic bias
        np.random.seed(42)
        judge1_scores = np.random.uniform(0.3, 0.9, 20).tolist()
        judge2_scores = np.random.uniform(0.3, 0.9, 20).tolist()

        queries = [{"judge1_score": judge1_scores, "judge2_score": judge2_scores}]

        # Execute
        recommender = ThresholdAdjustmentRecommender()
        result = recommender.analyze_systematic_bias(queries)

        # Verify
        assert result is not None
        assert not result["significant_bias"]
        assert result["p_value"] >= 0.05
        assert result["threshold_adjustment"] is None

    def test_wilcoxon_insufficient_data(self):
        """Test Wilcoxon test with insufficient data"""
        # Setup: Less than 10 scores
        judge1_scores = [0.7, 0.8, 0.6]
        judge2_scores = [0.6, 0.7, 0.5]

        queries = [{"judge1_score": judge1_scores, "judge2_score": judge2_scores}]

        # Execute
        recommender = ThresholdAdjustmentRecommender()
        result = recommender.analyze_systematic_bias(queries)

        # Verify
        assert result is None


class TestJudgeRecalibration:
    """Test judge recalibration functionality (AC: 3.3)"""

    def test_low_kappa_query_identification(self):
        """Test identification of low-kappa queries (Task 6.1)"""
        # Setup: Mix of high and low kappa queries
        queries = [
            MockQuery(kappa=0.35, id=1),  # Low kappa
            MockQuery(kappa=0.80, id=2),  # High kappa
            MockQuery(kappa=0.25, id=3),  # Very low kappa
            MockQuery(kappa=0.90, id=4),  # Very high kappa
        ]

        with patch(
            "mcp_server.validation.contingency.get_connection"
        ) as mock_get_connection:
            _setup_mock_database_for_contingency(mock_get_connection, queries)

            # Execute
            recalibrator = JudgeRecalibration()
            low_kappa_queries = recalibrator.identify_low_kappa_queries()

            # Verify
            assert len(low_kappa_queries) == 2  # Only queries with kappa < 0.40
            assert (
                low_kappa_queries[0]["kappa"] == 0.25
            )  # Sorted by kappa (lowest first)
            assert low_kappa_queries[1]["kappa"] == 0.35

    def test_low_kappa_pattern_analysis(self):
        """Test analysis of patterns in low-kappa queries (Task 6.2)"""
        # Setup: Create low-kappa queries with different patterns
        queries = [
            MockQuery(
                kappa=0.30, query_text="short query", query_length=12
            ),  # Short query
            MockQuery(
                kappa=0.25,
                query_text="very long detailed query with many words",
                query_length=50,
            ),  # Long query
            MockQuery(
                kappa=0.35, query_text="medium length query", query_length=25
            ),  # Medium query
        ]

        # Execute
        recalibrator = JudgeRecalibration()
        analysis = recalibrator.analyze_low_kappa_patterns(queries)

        # Verify
        assert analysis["total_queries"] == 3
        assert analysis["avg_kappa"] == pytest.approx(0.30, abs=0.01)
        assert analysis["min_kappa"] == 0.25
        assert analysis["max_kappa"] == 0.35
        assert "potential_causes" in analysis
        assert "recommendation" in analysis

    def test_recalibrated_prompts_generation(self):
        """Test generation of recalibrated prompts (Task 6.3)"""
        # Execute
        recalibrator = JudgeRecalibration()
        prompts = recalibrator.get_recalibrated_prompts()

        # Verify
        assert "gpt4o_prompt" in prompts
        assert "haiku_prompt" in prompts
        assert "Criteria for Rating" in prompts["gpt4o_prompt"]
        assert "Semantic Overlap" in prompts["gpt4o_prompt"]
        assert (
            prompts["gpt4o_prompt"] == prompts["haiku_prompt"]
        )  # Should be identical after recalibration


class TestContingencyManager:
    """Test overall contingency management"""

    @patch("mcp_server.validation.contingency.get_connection")
    def test_contingency_analysis_workflow(self, mock_get_connection):
        """Test complete contingency analysis workflow"""
        # Setup: Mock queries with various issues
        mock_queries = [
            MockQuery(kappa=0.65, disagreement=0.5),  # High disagreement
            MockQuery(kappa=0.30, query_text="short", query_length=8),  # Low kappa
        ]
        _setup_mock_database_for_contingency(mock_get_connection, mock_queries)

        # Execute
        manager = ContingencyManager()
        results = manager.run_contingency_analysis(mock_queries)

        # Verify
        assert "high_disagreement_queries" in results
        assert "bias_analysis" in results
        assert "low_kappa_queries" in results
        assert "recalibrated_prompts" in results
        assert len(results["actions"]) > 0

    @patch("mcp_server.validation.contingency.get_connection")
    def test_human_override_saving(self, mock_get_connection):
        """Test saving human override decisions"""
        # Setup
        mock_conn = Mock()
        mock_cursor = Mock()
        # Add context manager support for cursor
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value = mock_cursor
        mock_get_connection.return_value.__enter__.return_value = mock_conn

        # Execute
        manager = ContingencyManager()
        success = manager.save_human_override(
            query_id=123, final_expected_docs=[1, 3, 5], reason="Low Kappa Tiebreaker"
        )

        # Verify
        assert success
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()


class TestCSVExport:
    """Test CSV export functionality"""

    def test_high_disagreement_csv_export(self):
        """Test exporting high-disagreement queries to CSV"""
        # Setup
        queries = [
            {
                "id": 1,
                "query": "test query 1",
                "kappa": 0.65,
                "avg_disagreement": 0.5,
                "avg_judge1": 0.75,
                "avg_judge2": 0.25,
                "top_disagreements": [{"doc_index": 1}, {"doc_index": 2}],
            },
            {
                "id": 2,
                "query": "test query 2",
                "kappa": 0.60,
                "avg_disagreement": 0.6,
                "avg_judge1": 0.80,
                "avg_judge2": 0.20,
                "top_disagreements": [{"doc_index": 3}],
            },
        ]

        # Execute
        analyzer = HighDisagreementAnalyzer()
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as tmp_file:
            analyzer.export_to_csv(queries, tmp_file.name)

            # Verify
            with open(tmp_file.name) as f:
                content = f.read()
                assert "id,query,kappa,avg_disagreement" in content
                assert "test query 1" in content
                assert "test query 2" in content
                assert "2" in content  # Should have both queries


class MockQuery:
    """Mock query class for testing"""

    def __init__(
        self,
        kappa=0.75,
        disagreement=0.2,
        id=1,
        query_text="test query",
        query_length=20,
    ):
        self.id = id
        self.query = query_text
        self.kappa = kappa
        self.expected_docs = [1, 2, 3]
        self.avg_disagreement = disagreement

        # Generate mock scores with specified disagreement
        base_scores = np.random.uniform(0.3, 0.9, 10).tolist()
        self.judge1_score = base_scores

        # Create judge2 scores with specified disagreement
        if disagreement > 0:
            self.judge2_score = [
                max(0.1, min(1.0, score - disagreement)) for score in base_scores
            ]
        else:
            self.judge2_score = base_scores.copy()

        self.avg_judge1 = np.mean(self.judge1_score)
        self.avg_judge2 = np.mean(self.judge2_score)

        # Create top disagreements
        self.top_disagreements = []
        for i, (score1, score2) in enumerate(
            zip(self.judge1_score, self.judge2_score, strict=False)
        ):
            if abs(score1 - score2) > 0.3:
                self.top_disagreements.append(
                    {
                        "doc_index": i,
                        "judge1_score": score1,
                        "judge2_score": score2,
                        "disagreement": abs(score1 - score2),
                    }
                )

    def __getitem__(self, key):
        """Make MockQuery subscriptable like a dictionary"""
        return {
            "id": self.id,
            "query": self.query,
            "kappa": self.kappa,
            "expected_docs": self.expected_docs,
            "judge1_score": self.judge1_score,
            "judge2_score": self.judge2_score,
            "avg_disagreement": self.avg_disagreement,
            "avg_judge1": self.avg_judge1,
            "avg_judge2": self.avg_judge2,
            "top_disagreements": self.top_disagreements,
            "query_length": len(self.query),
        }[key]

    def to_dict(self):
        """Convert to dictionary format"""
        return {
            "id": self.id,
            "query": self.query,
            "kappa": self.kappa,
            "expected_docs": self.expected_docs,
            "judge1_score": self.judge1_score,
            "judge2_score": self.judge2_score,
            "avg_disagreement": self.avg_disagreement,
            "avg_judge1": self.avg_judge1,
            "avg_judge2": self.avg_judge2,
            "top_disagreements": self.top_disagreements,
        }


def _setup_mock_database(mock_get_connection, mock_queries):
    """Helper method to setup mock database for IRR validation tests"""
    mock_conn = Mock()
    mock_cursor = Mock()
    # Add context manager support for cursor
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)
    mock_conn.cursor.return_value = mock_cursor
    mock_get_connection.return_value.__enter__.return_value = mock_conn

    # Mock database response
    mock_rows = []
    for query in mock_queries:
        query_dict = (
            query.to_dict()
            if hasattr(query, "to_dict")
            else {
                "id": query.id,
                "query": query.query,
                "judge1_score": query.judge1_score,
                "judge2_score": query.judge2_score,
                "kappa": query.kappa,
                "expected_docs": query.expected_docs,
            }
        )
        mock_rows.append(
            (
                query_dict["id"],
                query_dict["query"],
                query_dict["judge1_score"],
                query_dict["judge2_score"],
                query_dict["kappa"],
                query_dict["expected_docs"],
            )
        )

    mock_cursor.fetchall.return_value = mock_rows
    return mock_conn


def _setup_mock_database_for_contingency(mock_get_connection, mock_queries):
    """Helper method to setup mock database for contingency tests"""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.__enter__ = Mock(return_value=mock_cursor)
    mock_cursor.__exit__ = Mock(return_value=None)
    mock_conn.cursor.return_value = mock_cursor
    mock_get_connection.return_value.__enter__.return_value = mock_conn

    # Mock different queries for different use cases
    # Production expects 9 columns: id, query, judge1_score, judge2_score, kappa,
    # expected_docs, avg_disagreement, avg_judge1, avg_judge2
    mock_cursor.fetchall.return_value = [
        (
            q.id,
            q.query,
            q.judge1_score,
            q.judge2_score,
            q.kappa,
            q.expected_docs,
            getattr(q, "avg_disagreement", 0.2),  # avg_disagreement
            getattr(q, "avg_judge1", 0.6),  # avg_judge1
            getattr(q, "avg_judge2", 0.5),  # avg_judge2
        )
        for q in mock_queries
    ]

    return mock_conn


class TestEndToEndValidation:
    """End-to-end integration tests"""

    @patch("mcp_server.validation.irr_validator.get_connection")
    def test_end_to_end_validation_success_scenario(self, mock_get_connection):
        """Test end-to-end validation with success scenario (AC: all)"""
        # Setup: Seed 50 queries with high kappa
        mock_queries = [MockQuery(kappa=0.78) for _ in range(50)]
        _setup_mock_database(mock_get_connection, mock_queries)

        # Execute
        results = run_irr_validation(kappa_threshold=0.70)

        # Verify success path
        assert results["status"] == "passed"
        assert results["kappa_macro"] > 0.70
        assert not results["contingency_triggered"]

    @patch("mcp_server.validation.irr_validator.get_connection")
    def test_end_to_end_validation_contingency_scenario(self, mock_get_connection):
        """Test end-to-end validation with contingency scenario"""
        # Setup: Seed 50 queries with mixed kappa (average below threshold)
        mock_queries = []
        for i in range(50):
            if i < 30:
                kappa = 0.75  # Good agreement
            else:
                kappa = 0.55  # Poor agreement
            mock_queries.append(MockQuery(kappa=kappa))

        _setup_mock_database(mock_get_connection, mock_queries)

        # Execute
        results = run_irr_validation(kappa_threshold=0.70)

        # Verify contingency path
        assert results["status"] == "contingency_triggered"
        assert results["kappa_macro"] < 0.70
        assert len(results["high_disagreement_queries"]) > 0


# Add helper methods to test classes after they are defined
TestSuccessPathValidation._setup_mock_database = _setup_mock_database
TestContingencyPathValidation._setup_mock_database = _setup_mock_database
TestJudgeRecalibration._setup_mock_database_for_contingency = (
    _setup_mock_database_for_contingency
)
TestContingencyManager._setup_mock_database_for_contingency = (
    _setup_mock_database_for_contingency
)
TestEndToEndValidation._setup_mock_database = _setup_mock_database


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
