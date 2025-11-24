"""
Contingency Plan Module for Story 1.12

This module implements the contingency plan for low IRR scenarios:
- Human Tiebreaker UI integration
- Wilcoxon Signed-Rank Test for systematic bias
- Judge Recalibration with updated prompts
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
from scipy.stats import wilcoxon

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


@dataclass
class ContingencyAction:
    """Data class for contingency actions"""

    action_type: (
        str  # 'human_tiebreaker', 'threshold_adjustment', 'judge_recalibration'
    )
    description: str
    affected_queries: list[int]
    timestamp: datetime
    result: dict | None = None


class HighDisagreementAnalyzer:
    """
    Analyzes and identifies high-disagreement queries for human review
    """

    def __init__(self, disagreement_threshold: float = 0.4):
        """
        Initialize analyzer

        Args:
            disagreement_threshold: Minimum absolute difference between judge averages to flag as high disagreement
        """
        self.disagreement_threshold = disagreement_threshold

    def identify_high_disagreement_queries(
        self, limit: int | None = None
    ) -> list[dict]:
        """
        Identify queries with highest judge disagreement

        Args:
            limit: Maximum number of queries to return (None for all)

        Returns:
            List of high-disagreement queries sorted by disagreement magnitude
        """
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # SQL query to calculate disagreement for each query
                cursor.execute(
                    """
                    SELECT
                        id,
                        query,
                        judge1_score,
                        judge2_score,
                        kappa,
                        expected_docs,
                        ABS(
                            (SELECT AVG(score) FROM unnest(judge1_score) AS score) -
                            (SELECT AVG(score) FROM unnest(judge2_score) AS score)
                        ) as avg_disagreement,
                        (SELECT AVG(score) FROM unnest(judge1_score) AS score) as avg_judge1,
                        (SELECT AVG(score) FROM unnest(judge2_score) AS score) as avg_judge2
                    FROM ground_truth
                    WHERE judge1_score IS NOT NULL
                      AND judge2_score IS NOT NULL
                      AND kappa IS NOT NULL
                      AND (
                          ABS(
                              (SELECT AVG(score) FROM unnest(judge1_score) AS score) -
                              (SELECT AVG(score) FROM unnest(judge2_score) AS score)
                          ) > %s
                          OR kappa < %s
                      )
                    ORDER BY avg_disagreement DESC
                """,
                    (self.disagreement_threshold, 0.70),
                )

                queries = []
                for row in cursor.fetchall():
                    # Calculate top documents with highest disagreement
                    judge1_scores = row[2]
                    judge2_scores = row[3]

                    top_disagreements = []
                    if judge1_scores and judge2_scores:
                        for i, (score1, score2) in enumerate(
                            zip(judge1_scores, judge2_scores, strict=False)
                        ):
                            disagreement = abs(score1 - score2)
                            if (
                                disagreement > 0.3
                            ):  # High disagreement at document level
                                top_disagreements.append(
                                    {
                                        "doc_index": i,
                                        "judge1_score": score1,
                                        "judge2_score": score2,
                                        "disagreement": disagreement,
                                    }
                                )

                    # Sort by disagreement and take top 5
                    top_disagreements.sort(
                        key=lambda x: x["disagreement"], reverse=True
                    )
                    top_disagreements = top_disagreements[:5]

                    queries.append(
                        {
                            "id": row[0],
                            "query": row[1],
                            "judge1_score": row[2],
                            "judge2_score": row[3],
                            "kappa": row[4],
                            "expected_docs": row[5],
                            "avg_disagreement": row[6],
                            "avg_judge1": row[7],
                            "avg_judge2": row[8],
                            "top_disagreements": top_disagreements,
                        }
                    )

                # Apply limit if specified
                if limit and len(queries) > limit:
                    queries = queries[:limit]

                logger.info(f"Identified {len(queries)} high-disagreement queries")
                return queries

    def export_to_csv(self, queries: list[dict], filepath: str):
        """
        Export high-disagreement queries to CSV for manual review

        Args:
            queries: List of high-disagreement queries
            filepath: Path to save CSV file
        """
        import csv

        with open(filepath, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = [
                "id",
                "query",
                "kappa",
                "avg_disagreement",
                "avg_judge1",
                "avg_judge2",
                "top_disagreement_docs",
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            for query in queries:
                writer.writerow(
                    {
                        "id": query["id"],
                        "query": query["query"],
                        "kappa": query["kappa"],
                        "avg_disagreement": query["avg_disagreement"],
                        "avg_judge1": query["avg_judge1"],
                        "avg_judge2": query["avg_judge2"],
                        "top_disagreement_docs": len(query["top_disagreements"]),
                    }
                )

        logger.info(f"Exported {len(queries)} high-disagreement queries to {filepath}")


class ThresholdAdjustmentRecommender:
    """
    Recommends threshold adjustments based on systematic bias detection
    """

    def __init__(self):
        """Initialize threshold adjustment recommender"""
        pass

    def analyze_systematic_bias(self, queries: list[dict]) -> dict | None:
        """
        Run Wilcoxon Signed-Rank Test to detect systematic bias

        Args:
            queries: List of queries with judge scores

        Returns:
            Analysis results or None if analysis cannot be performed
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

            # Calculate other statistics
            judge1_median = np.median(judge1_scores)
            judge2_median = np.median(judge2_scores)
            judge1_mean = np.mean(judge1_scores)
            judge2_mean = np.mean(judge2_scores)

            result = {
                "test_name": "Wilcoxon Signed-Rank Test",
                "statistic": statistic,
                "p_value": p_value,
                "median_difference": median_diff,
                "mean_difference": judge1_mean - judge2_mean,
                "judge1_stats": {
                    "median": judge1_median,
                    "mean": judge1_mean,
                    "std": np.std(judge1_scores),
                    "count": len(judge1_scores),
                },
                "judge2_stats": {
                    "median": judge2_median,
                    "mean": judge2_mean,
                    "std": np.std(judge2_scores),
                    "count": len(judge2_scores),
                },
                "significant_bias": p_value < 0.05,
                "threshold_adjustment": None,
                "recommendation": None,
            }

            # Generate recommendation
            if result["significant_bias"]:
                if median_diff > 0:
                    # GPT-4o is systematically higher
                    adjustment = 0.5 + median_diff
                    result["threshold_adjustment"] = {
                        "judge": "GPT-4o",
                        "current_threshold": 0.5,
                        "recommended_threshold": min(adjustment, 0.9),  # Cap at 0.9
                        "reasoning": f"GPT-4o is systematically higher by {median_diff:.3f}",
                        "adjustment_magnitude": median_diff,
                    }
                    result["recommendation"] = (
                        f"Increase GPT-4o threshold to {result['threshold_adjustment']['recommended_threshold']:.3f} to compensate for systematic bias"
                    )
                else:
                    # Haiku is systematically higher
                    adjustment = 0.5 + abs(median_diff)
                    result["threshold_adjustment"] = {
                        "judge": "Haiku",
                        "current_threshold": 0.5,
                        "recommended_threshold": min(adjustment, 0.9),  # Cap at 0.9
                        "reasoning": f"Haiku is systematically higher by {abs(median_diff):.3f}",
                        "adjustment_magnitude": abs(median_diff),
                    }
                    result["recommendation"] = (
                        f"Increase Haiku threshold to {result['threshold_adjustment']['recommended_threshold']:.3f} to compensate for systematic bias"
                    )
            else:
                result["recommendation"] = (
                    "No systematic bias detected. Disagreement appears to be random variation."
                )

            logger.info(
                f"Wilcoxon test completed: p-value={p_value:.4f}, recommendation: {result['recommendation']}"
            )
            return result

        except Exception as e:
            logger.error(f"Error running Wilcoxon test: {e}")
            return None


class JudgeRecalibration:
    """
    Handles judge recalibration with updated prompts for low-kappa queries
    """

    def __init__(self):
        """Initialize judge recalibration module"""
        self.low_kappa_threshold = 0.40

    def identify_low_kappa_queries(self) -> list[dict]:
        """
        Identify queries with low Cohen's Kappa that need recalibration

        Returns:
            List of low-kappa queries
        """
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        query,
                        judge1_score,
                        judge2_score,
                        kappa,
                        expected_docs,
                        LENGTH(query) as query_length
                    FROM ground_truth
                    WHERE judge1_score IS NOT NULL
                      AND judge2_score IS NOT NULL
                      AND kappa IS NOT NULL
                      AND kappa < %s
                    ORDER BY kappa ASC
                """,
                    (self.low_kappa_threshold,),
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
                            "query_length": row[6],
                        }
                    )

                logger.info(
                    f"Identified {len(queries)} low-kappa queries (< {self.low_kappa_threshold})"
                )
                return queries

    def analyze_low_kappa_patterns(self, queries: list[dict]) -> dict:
        """
        Analyze patterns in low-kappa queries to identify root causes

        Args:
            queries: List of low-kappa queries

        Returns:
            Analysis of patterns and potential causes
        """
        if not queries:
            return {"analysis": "No low-kappa queries found"}

        # Analyze query characteristics
        query_lengths = [q["query_length"] for q in queries]
        kappas = [q["kappa"] for q in queries]

        analysis = {
            "total_queries": len(queries),
            "avg_kappa": np.mean(kappas),
            "min_kappa": np.min(kappas),
            "max_kappa": np.max(kappas),
            "avg_query_length": np.mean(query_lengths),
            "query_length_stats": {
                "short_queries": len([q for q in queries if q["query_length"] < 50]),
                "medium_queries": len(
                    [q for q in queries if 50 <= q["query_length"] < 150]
                ),
                "long_queries": len([q for q in queries if q["query_length"] >= 150]),
            },
        }

        # Categorize potential causes
        potential_causes = []

        if analysis["query_length_stats"]["short_queries"] > len(queries) * 0.3:
            potential_causes.append("High proportion of short/ambiguous queries")

        if analysis["avg_kappa"] < 0.2:
            potential_causes.append(
                "Very low agreement suggests fundamental interpretation differences"
            )

        if analysis["query_length_stats"]["long_queries"] > len(queries) * 0.3:
            potential_causes.append(
                "Long queries may be causing interpretation difficulties"
            )

        analysis["potential_causes"] = potential_causes
        analysis["recommendation"] = self._generate_rec_prompt_recommendation(
            potential_causes
        )

        return analysis

    def _generate_rec_prompt_recommendation(self, causes: list[str]) -> str:
        """Generate recommendation for prompt improvements"""
        if "short/ambiguous queries" in str(causes):
            return (
                "Consider adding explicit criteria for handling vague or short queries"
            )
        elif "fundamental interpretation differences" in str(causes):
            return "Rewrite prompts with more explicit relevance criteria and examples"
        elif "interpretation difficulties" in str(causes):
            return "Break down long queries into specific evaluation criteria"
        else:
            return "Review and add more specific relevance guidelines to prompts"

    def get_recalibrated_prompts(self) -> dict[str, str]:
        """
        Get recalibrated prompts with more explicit criteria

        Returns:
            Dictionary with recalibrated prompts for both judges
        """
        recalibrated_prompts = {
            "gpt4o_prompt": """You are evaluating the relevance of a document for a given user query.

Rate the document's relevance on a scale from 0.0 to 1.0:

**Criteria for Rating:**
1. **Semantic Overlap:** Does the document contain keywords or concepts from the query?
2. **Direct Answer:** Does the document directly answer the query?
3. **Depth:** Does the document provide sufficient detail/context?

**Rating Scale:**
- 0.0 = No semantic overlap (completely off-topic)
- 0.3 = Tangential connection (mentions related concepts, but doesn't answer query)
- 0.5 = Partial answer (addresses some aspects of query)
- 0.7 = Good answer (directly addresses query with some detail)
- 1.0 = Perfect answer (comprehensive, detailed, directly answers query)

**Important:** Use the SAME interpretation of "relevance" for all documents.

Return ONLY a float number between 0.0 and 1.0, nothing else.""",
            "haiku_prompt": """You are evaluating the relevance of a document for a given user query.

Rate the document's relevance on a scale from 0.0 to 1.0:

**Criteria for Rating:**
1. **Semantic Overlap:** Does the document contain keywords or concepts from the query?
2. **Direct Answer:** Does the document directly answer the query?
3. **Depth:** Does the document provide sufficient detail/context?

**Rating Scale:**
- 0.0 = No semantic overlap (completely off-topic)
- 0.3 = Tangential connection (mentions related concepts, but doesn't answer query)
- 0.5 = Partial answer (addresses some aspects of query)
- 0.7 = Good answer (directly addresses query with some detail)
- 1.0 = Perfect answer (comprehensive, detailed, directly answers query)

**Important:** Use the SAME interpretation of "relevance" for all documents.

Return ONLY a float number between 0.0 and 1.0, nothing else.""",
        }

        return recalibrated_prompts


class ContingencyManager:
    """
    Main contingency manager that coordinates all contingency actions
    """

    def __init__(self):
        """Initialize contingency manager"""
        self.disagreement_analyzer = HighDisagreementAnalyzer()
        self.threshold_recommender = ThresholdAdjustmentRecommender()
        self.judge_recalibrator = JudgeRecalibration()

    def run_contingency_analysis(self, queries: list[dict]) -> dict:
        """
        Run complete contingency analysis

        Args:
            queries: List of queries with dual judge scores

        Returns:
            Comprehensive contingency analysis results
        """
        logger.info("Starting contingency analysis")

        results = {
            "timestamp": datetime.now(),
            "total_queries": len(queries),
            "actions": [],
        }

        # 1. Identify high-disagreement queries
        high_disagreement = (
            self.disagreement_analyzer.identify_high_disagreement_queries(limit=20)
        )
        results["high_disagreement_queries"] = high_disagreement
        results["actions"].append(
            f"Identified {len(high_disagreement)} high-disagreement queries"
        )

        # 2. Run systematic bias analysis
        bias_analysis = self.threshold_recommender.analyze_systematic_bias(queries)
        if bias_analysis:
            results["bias_analysis"] = bias_analysis
            results["actions"].append("Wilcoxon Signed-Rank Test completed")

            if bias_analysis["significant_bias"]:
                results["actions"].append(
                    "Systematic bias detected - threshold adjustment recommended"
                )
            else:
                results["actions"].append("No systematic bias detected")

        # 3. Identify low-kappa queries for recalibration
        low_kappa_queries = self.judge_recalibrator.identify_low_kappa_queries()
        if low_kappa_queries:
            results["low_kappa_queries"] = low_kappa_queries
            results["low_kappa_analysis"] = (
                self.judge_recalibrator.analyze_low_kappa_patterns(low_kappa_queries)
            )
            results["recalibrated_prompts"] = (
                self.judge_recalibrator.get_recalibrated_prompts()
            )
            results["actions"].append(
                f"Identified {len(low_kappa_queries)} low-kappa queries for recalibration"
            )

        logger.info(
            f"Contingency analysis completed: {len(results['actions'])} actions recommended"
        )
        return results

    def save_human_override(
        self, query_id: int, final_expected_docs: list[int], reason: str
    ):
        """
        Save human override decision to database

        Args:
            query_id: ID of the query being overridden
            final_expected_docs: Final list of relevant document IDs
            reason: Reason for the override
        """
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE ground_truth
                    SET expected_docs = %s,
                        human_override = TRUE,
                        override_reason = %s,
                        last_validated_at = NOW()
                    WHERE id = %s
                """,
                    (final_expected_docs, reason, query_id),
                )

            conn.commit()
            logger.info(f"Saved human override for query {query_id}: {reason}")


if __name__ == "__main__":
    # Test contingency analysis
    logging.basicConfig(level=logging.INFO)

    try:
        # Load queries and run analysis
        from mcp_server.validation.irr_validator import IRRValidator

        validator = IRRValidator()
        queries = validator.load_all_queries()

        if queries:
            manager = ContingencyManager()
            results = manager.run_contingency_analysis(queries)

            print("Contingency Analysis Results:")
            print(f"Total Queries: {results['total_queries']}")
            print(f"Actions: {', '.join(results['actions'])}")

            if "bias_analysis" in results:
                bias = results["bias_analysis"]
                print(f"Bias Analysis: p-value={bias['p_value']:.4f}")
                if bias["threshold_adjustment"]:
                    print(f"Recommendation: {bias['recommendation']}")

            if "low_kappa_analysis" in results:
                analysis = results["low_kappa_analysis"]
                print(f"Low-Kappa Analysis: {analysis['avg_kappa']:.3f} avg kappa")
                print(f"Recommendation: {analysis['recommendation']}")

    except Exception as e:
        logger.error(f"Contingency analysis failed: {e}")
        print(f"Error: {e}")
