"""
IRR Validation Module for 

This module implements Inter-Rater Reliability (IRR) validation using Cohen's Kappa
for dual judge scores (GPT-4o + Haiku) across all ground truth queries.

Key Features:
- Global Kappa calculation (macro and micro averaging)
- Success path validation (kappa >= 0.70)
- Contingency plan activation (kappa < 0.70)
- Statistical analysis (Wilcoxon Signed-Rank Test)
- High disagreement query identification
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np

# Import scipy for statistical tests
from scipy.stats import wilcoxon

from mcp_server.db.connection import get_connection_sync

# Import existing Cohen's Kappa calculation
from mcp_server.tools.dual_judge import DualJudgeEvaluator

logger = logging.getLogger(__name__)


@dataclass
class ValidationResults:
    """Data class for validation results"""

    kappa_macro: float
    kappa_micro: float
    status: str  # 'passed' | 'contingency_triggered'
    total_queries: int
    high_disagreement_queries: list[dict]
    wilcoxon_result: dict | None = None
    contingency_actions: list[str] = None
    notes: str = ""

    def __post_init__(self):
        if self.contingency_actions is None:
            self.contingency_actions = []


class IRRValidator:
    """
    Inter-Rater Reliability Validator for Ground Truth Queries

    Implements Cohen's Kappa validation across all ground truth queries
    with contingency plan for low agreement scenarios.
    """

    def __init__(self, kappa_threshold: float = 0.70):
        """
        Initialize IRR Validator

        Args:
            kappa_threshold: Minimum acceptable kappa value (default: 0.70)
        """
        self.kappa_threshold = kappa_threshold
        self.disagreement_threshold = 0.4

    def load_all_queries(self) -> list[dict]:
        """
        Load all ground truth queries with dual judge scores

        Returns:
            List of queries with judge1_score and judge2_score arrays
        """
        with get_connection_sync() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        query,
                        judge1_score,
                        judge2_score,
                        kappa,
                        expected_docs
                    FROM ground_truth
                    WHERE judge1_score IS NOT NULL
                      AND judge2_score IS NOT NULL
                      AND kappa IS NOT NULL
                    ORDER BY id
                """
                )

                queries = []
                for row in cursor.fetchall():
                    queries.append(
                        {
                            "id": row[0],
                            "query": row[1],
                            "judge1_score": row[2],
                            "judge2_score": row[3],
                            "kappa": row[4],
                            "expected_docs": row[5],
                        }
                    )

                logger.info(f"Loaded {len(queries)} queries with dual judge scores")
                return queries

    def calculate_macro_average_kappa(self, queries: list[dict]) -> float:
        """
        Calculate macro-average kappa (average of per-query kappas)

        Args:
            queries: List of queries with kappa values

        Returns:
            Macro-average kappa value
        """
        if not queries:
            return 0.0

        kappas = [query["kappa"] for query in queries if query["kappa"] is not None]

        if not kappas:
            logger.warning("No valid kappa values found for macro calculation")
            return 0.0

        macro_kappa = np.mean(kappas)
        logger.info(
            f"Macro-average kappa: {macro_kappa:.3f} (from {len(kappas)} queries)"
        )

        return macro_kappa

    def calculate_micro_average_kappa(self, queries: list[dict]) -> float:
        """
        Calculate micro-average kappa (all documents pooled together)

        Args:
            queries: List of queries with judge scores

        Returns:
            Micro-average kappa value
        """
        if not queries:
            return 0.0

        # Pool all scores from all queries
        judge1_all_scores = []
        judge2_all_scores = []

        for query in queries:
            if query["judge1_score"] and query["judge2_score"]:
                judge1_all_scores.extend(query["judge1_score"])
                judge2_all_scores.extend(query["judge2_score"])

        if not judge1_all_scores or not judge2_all_scores:
            logger.warning("No valid scores found for micro calculation")
            return 0.0

        # Calculate Cohen's Kappa on pooled scores
        evaluator = DualJudgeEvaluator()
        micro_kappa = evaluator._calculate_cohen_kappa(
            judge1_all_scores, judge2_all_scores
        )
        logger.info(
            f"Micro-average kappa: {micro_kappa:.3f} (from {len(judge1_all_scores)} documents)"
        )

        return micro_kappa

    def identify_high_disagreement_queries(self, queries: list[dict]) -> list[dict]:
        """
        Identify queries with high judge disagreement

        Args:
            queries: List of queries with judge scores

        Returns:
            List of high disagreement queries sorted by disagreement magnitude
        """
        high_disagreement = []

        for query in queries:
            if not query["judge1_score"] or not query["judge2_score"]:
                continue

            # Calculate average disagreement for this query
            avg_judge1 = np.mean(query["judge1_score"])
            avg_judge2 = np.mean(query["judge2_score"])
            disagreement = abs(avg_judge1 - avg_judge2)

            # Include queries with high disagreement or low kappa
            if disagreement > self.disagreement_threshold or query["kappa"] < 0.70:
                high_disagreement.append(
                    {
                        "id": query["id"],
                        "query": query["query"],
                        "kappa": query["kappa"],
                        "avg_disagreement": disagreement,
                        "judge1_scores": query["judge1_score"],
                        "judge2_scores": query["judge2_score"],
                        "expected_docs": query["expected_docs"],
                    }
                )

        # Sort by disagreement magnitude (highest first)
        high_disagreement.sort(key=lambda x: x["avg_disagreement"], reverse=True)

        logger.info(f"Identified {len(high_disagreement)} high-disagreement queries")
        return high_disagreement

    def run_wilcoxon_test(self, queries: list[dict]) -> dict | None:
        """
        Run Wilcoxon Signed-Rank Test to detect systematic bias between judges

        Args:
            queries: List of queries with judge scores

        Returns:
            Wilcoxon test results or None if test cannot be performed
        """
        # Pool all scores from all queries
        judge1_scores = []
        judge2_scores = []

        for query in queries:
            if query["judge1_score"] and query["judge2_score"]:
                judge1_scores.extend(query["judge1_score"])
                judge2_scores.extend(query["judge2_score"])

        if len(judge1_scores) < 10 or len(judge2_scores) < 10:
            logger.warning(
                "Insufficient data for Wilcoxon test (need at least 10 scores)"
            )
            return None

        try:
            # Run Wilcoxon Signed-Rank Test
            statistic, p_value = wilcoxon(judge1_scores, judge2_scores)

            # Calculate median difference
            median_diff = np.median(judge1_scores) - np.median(judge2_scores)

            result = {
                "statistic": statistic,
                "p_value": p_value,
                "median_difference": median_diff,
                "judge1_median": np.median(judge1_scores),
                "judge2_median": np.median(judge2_scores),
                "significant_bias": p_value < 0.05,
                "threshold_adjustment": None,
            }

            # Recommend threshold adjustment if systematic bias detected
            if result["significant_bias"]:
                if median_diff > 0:
                    # GPT-4o is systematically higher
                    adjustment = 0.5 + median_diff
                    result["threshold_adjustment"] = {
                        "judge": "GPT-4o",
                        "recommended_threshold": adjustment,
                        "reasoning": f"GPT-4o is systematically higher by {median_diff:.3f}",
                    }
                else:
                    # Haiku is systematically higher
                    adjustment = 0.5 + abs(median_diff)
                    result["threshold_adjustment"] = {
                        "judge": "Haiku",
                        "recommended_threshold": adjustment,
                        "reasoning": f"Haiku is systematically higher by {abs(median_diff):.3f}",
                    }

            logger.info(
                f"Wilcoxon test: p-value={p_value:.4f}, median_diff={median_diff:.3f}"
            )
            return result

        except Exception as e:
            logger.error(f"Error running Wilcoxon test: {e}")
            return None

    def save_validation_results(self, results: ValidationResults):
        """
        Save validation results to database

        Args:
            results: Validation results to save
        """
        with get_connection_sync() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO validation_results (
                        timestamp, kappa_macro, kappa_micro, status,
                        contingency_actions, notes, total_queries
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        datetime.now(),
                        results.kappa_macro,
                        results.kappa_micro,
                        results.status,
                        json.dumps(results.contingency_actions),
                        results.notes,
                        results.total_queries,
                    ),
                )

            conn.commit()
            logger.info("Validation results saved to database")

    def run_validation(self) -> ValidationResults:
        """
        Run complete IRR validation

        Returns:
            ValidationResults object with comprehensive validation outcome
        """
        logger.info("Starting IRR validation")

        # Load all queries
        queries = self.load_all_queries()

        if not queries:
            raise ValueError("No queries found with dual judge scores")

        # Calculate macro and micro kappa
        kappa_macro = self.calculate_macro_average_kappa(queries)
        kappa_micro = self.calculate_micro_average_kappa(queries)

        # Determine status and create base results
        if kappa_macro >= self.kappa_threshold and kappa_micro >= self.kappa_threshold:
            status = "passed"
            notes = f"IRR Validation Passed (Macro: {kappa_macro:.3f}, Micro: {kappa_micro:.3f})"
            logger.info(f"IRR validation PASSED with kappa >= {self.kappa_threshold}")
        else:
            status = "contingency_triggered"
            notes = f"IRR Validation Failed (Macro: {kappa_macro:.3f}, Micro: {kappa_micro:.3f})"
            logger.warning(f"IRR validation FAILED with kappa < {self.kappa_threshold}")

        # Create base results
        results = ValidationResults(
            kappa_macro=kappa_macro,
            kappa_micro=kappa_micro,
            status=status,
            total_queries=len(queries),
            high_disagreement_queries=[],
            notes=notes,
        )

        # If contingency triggered, run additional analyses
        if status == "contingency_triggered":
            logger.info("Running contingency analyses...")

            # Identify high disagreement queries
            results.high_disagreement_queries = self.identify_high_disagreement_queries(
                queries
            )
            results.contingency_actions.append(
                f"Identified {len(results.high_disagreement_queries)} high-disagreement queries"
            )

            # Run Wilcoxon test for systematic bias
            wilcoxon_result = self.run_wilcoxon_test(queries)
            if wilcoxon_result:
                results.wilcoxon_result = wilcoxon_result
                results.contingency_actions.append(
                    "Wilcoxon Signed-Rank Test completed"
                )

                if wilcoxon_result["significant_bias"]:
                    results.contingency_actions.append(
                        "Systematic bias detected - threshold adjustment recommended"
                    )
                else:
                    results.contingency_actions.append("No systematic bias detected")
            else:
                results.contingency_actions.append(
                    "Wilcoxon test could not be performed"
                )

        # Save results to database
        self.save_validation_results(results)

        return results


def run_irr_validation(kappa_threshold: float = 0.70) -> dict:
    """
    Convenience function to run IRR validation

    Args:
        kappa_threshold: Minimum acceptable kappa value

    Returns:
        Dictionary with validation results
    """
    validator = IRRValidator(kappa_threshold=kappa_threshold)
    results = validator.run_validation()

    # Convert to dictionary for easy serialization
    return {
        "kappa_macro": results.kappa_macro,
        "kappa_micro": results.kappa_micro,
        "status": results.status,
        "total_queries": results.total_queries,
        "high_disagreement_queries": results.high_disagreement_queries,
        "wilcoxon_result": results.wilcoxon_result,
        "contingency_actions": results.contingency_actions,
        "notes": results.notes,
    }


if __name__ == "__main__":
    # Test validation
    logging.basicConfig(level=logging.INFO)

    try:
        results = run_irr_validation()
        print("Validation Results:")
        print(f"Status: {results['status']}")
        print(f"Macro Kappa: {results['kappa_macro']:.3f}")
        print(f"Micro Kappa: {results['kappa_micro']:.3f}")
        print(f"Notes: {results['notes']}")

        if results["status"] == "contingency_triggered":
            print(
                f"High Disagreement Queries: {len(results['high_disagreement_queries'])}"
            )
            if results["wilcoxon_result"]:
                print(f"Wilcoxon p-value: {results['wilcoxon_result']['p_value']:.4f}")

    except Exception as e:
        logger.error(f"Validation failed: {e}")
        print(f"Error: {e}")
