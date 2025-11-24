"""
Dual Judge Implementation for IRR Validation.

Uses GPT-4o and Haiku for independent evaluation to calculate Cohen's Kappa.
Provides methodologically valid ground truth with true independence between judges.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI, RateLimitError
from sklearn.metrics import cohen_kappa_score

from mcp_server.config import calculate_api_cost, load_environment
from mcp_server.db.connection import get_connection
from mcp_server.db.cost_logger import insert_cost_log
from mcp_server.utils.retry_logic import retry_with_backoff

logger = logging.getLogger(__name__)


class DualJudgeEvaluator:
    """
    Independent dual judge evaluator using GPT-4o and Haiku.

    Implements true independence between judges for valid IRR calculation.
    """

    def __init__(self) -> None:
        """Initialize dual judge with async clients and staged dual judge config."""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        if (
            not self.openai_api_key
            or self.openai_api_key == "sk-your-openai-api-key-here"
        ):
            raise RuntimeError("OpenAI API key not configured")

        if (
            not self.anthropic_api_key
            or self.anthropic_api_key == "sk-ant-your-anthropic-api-key-here"
        ):
            raise RuntimeError("Anthropic API key not configured")

        # Initialize async clients
        self.gpt4o_client = AsyncOpenAI(api_key=self.openai_api_key)
        self.haiku_client = AsyncAnthropic(api_key=self.anthropic_api_key)

        # Load Staged Dual Judge configuration (Story 3.9)
        try:
            config = load_environment()
            staged_config = config.get('staged_dual_judge', {})
            self.dual_judge_enabled = staged_config.get('dual_judge_enabled', True)
            self.primary_judge = staged_config.get('primary_judge', 'gpt-4o')
            self.spot_check_rate = staged_config.get('spot_check_rate', 0.05)
            logger.info(
                f"Staged Dual Judge config loaded: "
                f"dual_judge_enabled={self.dual_judge_enabled}, "
                f"spot_check_rate={self.spot_check_rate}"
            )
        except Exception as e:
            # Default to Dual Judge Mode if config fails to load
            logger.warning(f"Failed to load Staged Dual Judge config: {e}. Defaulting to Dual Judge Mode.")
            self.dual_judge_enabled = True
            self.primary_judge = 'gpt-4o'
            self.spot_check_rate = 0.05

    def _create_prompt(self, query: str, doc_content: str) -> tuple[str, str]:
        """
        Create prompts for both judges.

        Args:
            query: User query
            doc_content: Document content to evaluate

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = (
            "You are evaluating the relevance of a document for a given user query.\n\n"
            "Rate the document's relevance on a scale from 0.0 to 1.0:\n"
            "- 0.0 = Completely irrelevant (no semantic overlap)\n"
            "- 0.3 = Marginally relevant (tangential connection)\n"
            "- 0.5 = Moderately relevant (some useful information)\n"
            "- 0.7 = Highly relevant (directly addresses query)\n"
            "- 1.0 = Perfectly relevant (comprehensive answer)\n\n"
            "Return ONLY a float number between 0.0 and 1.0, nothing else."
        )

        user_prompt = (
            f"Query: {query}\n\n"
            f"Document: {doc_content}\n\n"
            f"Relevance score (0.0-1.0):"
        )

        return system_prompt, user_prompt

    @retry_with_backoff(max_retries=4, base_delays=[1.0, 2.0, 4.0, 8.0], jitter=True)
    async def _call_gpt4o_judge(self, query: str, doc_content: str) -> float:
        """
        Call GPT-4o API for relevance rating with automatic retry.

        Applies retry logic with exponential backoff for transient failures:
        - Rate Limit (429): Retries with delays [1s, 2s, 4s, 8s] ±20% jitter
        - Service Unavailable (503): Retries with exponential backoff
        - Timeout: Retries with exponential backoff

        After 4 failed retries, raises exception (Ground Truth Collection can be retried manually).

        Args:
            query: User query
            doc_content: Document content to evaluate

        Returns:
            Relevance score between 0.0 and 1.0

        Raises:
            RuntimeError: If all retries fail after 4 attempts

        Note:
            Function name "_call_gpt4o_judge" is mapped to api_name "gpt4o_judge"
            in retry logging (see retry_logic._extract_api_name).
        """
        system_prompt, user_prompt = self._create_prompt(query, doc_content)

        response = await self.gpt4o_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,  # Deterministic scoring
        )

        score_text = response.choices[0].message.content.strip()
        score = float(score_text)

        # Validate score range
        if not (0.0 <= score <= 1.0):
            logger.warning(f"GPT-4o returned invalid score: {score}, using 0.5")
            score = 0.5

        # Log API cost (Story 3.10: Budget Monitoring)
        # Extract actual token counts from API response
        if hasattr(response, 'usage') and response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = response.usage.total_tokens

            # Calculate cost using configured rates
            estimated_cost = calculate_api_cost('gpt4o', input_tokens, output_tokens)

            # Log to database
            insert_cost_log(
                api_name='gpt4o_judge',
                num_calls=1,
                token_count=total_tokens,
                estimated_cost=estimated_cost
            )

        return score

    @retry_with_backoff(max_retries=4, base_delays=[1.0, 2.0, 4.0, 8.0], jitter=True)
    async def _call_haiku_judge(self, query: str, doc_content: str) -> float:
        """
        Call Haiku API for relevance rating with automatic retry.

        Applies retry logic with exponential backoff for transient failures:
        - Rate Limit (429): Retries with delays [1s, 2s, 4s, 8s] ±20% jitter
        - Service Unavailable (503): Retries with exponential backoff
        - Timeout: Retries with exponential backoff

        Independent retry logic from GPT-4o judge (failures don't cascade).
        After 4 failed retries, raises exception (Ground Truth Collection can be retried manually).

        Args:
            query: User query
            doc_content: Document content to evaluate

        Returns:
            Relevance score between 0.0 and 1.0

        Raises:
            RuntimeError: If all retries fail after 4 attempts

        Note:
            Function name "_call_haiku_judge" is mapped to api_name "haiku_judge"
            in retry logging (see retry_logic._extract_api_name).
        """
        _, user_prompt = self._create_prompt(query, doc_content)

        response = await self.haiku_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=100,
            temperature=0.0,  # Deterministic scoring
            messages=[{"role": "user", "content": user_prompt}],
        )

        score_text = response.content[0].text.strip()
        score = float(score_text)

        # Validate score range
        if not (0.0 <= score <= 1.0):
            logger.warning(f"Haiku returned invalid score: {score}, using 0.5")
            score = 0.5

        # Log API cost (Story 3.10: Budget Monitoring)
        # Extract actual token counts from API response
        if hasattr(response, 'usage') and response.usage:
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens

            # Calculate cost using configured rates
            estimated_cost = calculate_api_cost('haiku', input_tokens, output_tokens)

            # Log to database
            insert_cost_log(
                api_name='haiku_judge',
                num_calls=1,
                token_count=total_tokens,
                estimated_cost=estimated_cost
            )

        return score

    def _binarize_scores(self, scores: list[float]) -> list[int]:
        """
        Convert scores to binary (relevant/not relevant).

        Args:
            scores: List of relevance scores

        Returns:
            List of binary scores (1 if >0.5, 0 otherwise)
        """
        return [1 if score > 0.5 else 0 for score in scores]

    def _calculate_cohen_kappa(
        self, judge1_scores: list[float], judge2_scores: list[float]
    ) -> float:
        """
        Calculate Cohen's Kappa for inter-rater reliability.

        Args:
            judge1_scores: Scores from judge 1 (GPT-4o)
            judge2_scores: Scores from judge 2 (Haiku)

        Returns:
            Cohen's Kappa score between -1.0 and 1.0

        Raises:
            ValueError: If arrays are empty or have different lengths
        """
        if not judge1_scores or not judge2_scores:
            raise ValueError(
                "Both score arrays must be non-empty for Kappa calculation"
            )

        if len(judge1_scores) != len(judge2_scores):
            raise ValueError("Score arrays must have the same length")

        # Convert to binary
        judge1_binary = self._binarize_scores(judge1_scores)
        judge2_binary = self._binarize_scores(judge2_scores)

        # Calculate Cohen's Kappa using sklearn
        try:
            kappa = cohen_kappa_score(judge1_binary, judge2_binary)
            # Handle NaN results
            if kappa != kappa:  # NaN check
                if judge1_binary == judge2_binary:
                    # Perfect agreement edge case
                    kappa = 1.0
                else:
                    # Use manual calculation for other edge cases
                    kappa = self._manual_cohen_kappa(judge1_binary, judge2_binary)
        except ValueError:
            # Handle edge case where sklearn fails
            if judge1_binary == judge2_binary:
                # Perfect agreement
                kappa = 1.0
            else:
                # Calculate manually for other edge cases
                kappa = self._manual_cohen_kappa(judge1_binary, judge2_binary)

        return kappa

    def _manual_cohen_kappa(
        self, judge1_binary: list[int], judge2_binary: list[int]
    ) -> float:
        """
        Manually calculate Cohen's Kappa for edge cases where sklearn fails.

        Args:
            judge1_binary: Binary scores from judge 1
            judge2_binary: Binary scores from judge 2

        Returns:
            Cohen's Kappa score
        """
        n = len(judge1_binary)
        if n == 0:
            return 0.0

        # Calculate observed agreement (P_o)
        agreement = sum(
            1 for j1, j2 in zip(judge1_binary, judge2_binary, strict=False) if j1 == j2
        )
        P_o = agreement / n

        # Calculate expected agreement (P_e)
        # Count number of 1s and 0s for each judge
        judge1_ones = sum(judge1_binary)
        judge1_zeros = n - judge1_ones
        judge2_ones = sum(judge2_binary)
        judge2_zeros = n - judge2_ones

        # Probability both say 1 by chance
        p_both_1 = (judge1_ones / n) * (judge2_ones / n)
        # Probability both say 0 by chance
        p_both_0 = (judge1_zeros / n) * (judge2_zeros / n)

        P_e = p_both_1 + p_both_0

        # Calculate Kappa
        if P_e == 1.0:
            # Perfect chance agreement, undefined Kappa, return 0
            return 0.0

        kappa = (P_o - P_e) / (1 - P_e)
        return kappa


    async def evaluate_documents(
        self, query_id: int, query: str, docs: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Evaluate documents with Staged Dual Judge logic (Story 3.9).

        Evaluation Strategy:
        - If dual_judge_enabled=True: Call both judges (full dual judge)
        - If dual_judge_enabled=False: Spot check logic
          - Random sampling: if random() < spot_check_rate, call both judges
          - Otherwise: Call only primary judge (GPT-4o)

        Args:
            query_id: Ground truth query ID
            query: User query
            docs: List of documents with 'id' and 'content' keys

        Returns:
            Dictionary with judge scores, kappa, and metadata
            - spot_check (bool): True if spot check performed
        """
        if not docs:
            return {
                "error": "No documents provided for evaluation",
                "judge1_scores": [],
                "judge2_scores": [],
                "kappa": 0.0,
                "spot_check": False,
                "status": "failed",
            }

        start_time = time.time()

        # Staged Dual Judge Logic (Story 3.9)
        is_spot_check = False
        if self.dual_judge_enabled:
            # Phase 1: Full Dual Judge Mode
            call_both_judges = True
            logger.info(f"Evaluating {len(docs)} documents with FULL Dual Judge...")
        else:
            # Phase 2: Single Judge + Spot Checks
            # Random sampling for spot check
            if random.random() < self.spot_check_rate:
                call_both_judges = True
                is_spot_check = True
                logger.info(
                    f"SPOT CHECK: Evaluating {len(docs)} documents with both judges "
                    f"(rate={self.spot_check_rate:.1%})"
                )
            else:
                call_both_judges = False
                logger.info(
                    f"Evaluating {len(docs)} documents with primary judge only "
                    f"({self.primary_judge})"
                )

        try:
            if call_both_judges:
                # Call both judges (existing dual judge logic)
                tasks = []
                for doc in docs:
                    # Both judges evaluate the same document
                    gpt4o_task = asyncio.create_task(
                        self._call_gpt4o_judge(query, doc["content"])
                    )
                    haiku_task = asyncio.create_task(
                        self._call_haiku_judge(query, doc["content"])
                    )

                    # Gather both results for this document
                    doc_tasks = asyncio.gather(
                        gpt4o_task, haiku_task, return_exceptions=True
                    )
                    tasks.append(doc_tasks)

                # Wait for all document evaluations
                results = await asyncio.gather(*tasks, return_exceptions=True)
            else:
                # Call only primary judge (Single Judge Mode)
                tasks = []
                for doc in docs:
                    gpt4o_task = asyncio.create_task(
                        self._call_gpt4o_judge(query, doc["content"])
                    )
                    tasks.append(gpt4o_task)

                # Wait for all document evaluations
                results = await asyncio.gather(*tasks, return_exceptions=True)

            # Separate judge scores and handle partial failures
            judge1_scores = []
            judge2_scores = []
            successful_evals = 0

            if call_both_judges:
                # Dual judge results: (gpt4o_score, haiku_score) tuples
                for i, doc_result in enumerate(results):
                    if isinstance(doc_result, Exception):
                        logger.error(f"Document {i+1} evaluation failed: {doc_result}")
                        # Use neutral score for failed evaluations
                        judge1_scores.append(0.5)
                        judge2_scores.append(0.5)
                        continue

                    gpt4o_score, haiku_score = doc_result

                    # Handle individual judge failures
                    if isinstance(gpt4o_score, Exception):
                        logger.warning(f"GPT-4o failed for document {i+1}: {gpt4o_score}")
                        gpt4o_score = 0.5
                    else:
                        successful_evals += 1

                    if isinstance(haiku_score, Exception):
                        logger.warning(f"Haiku failed for document {i+1}: {haiku_score}")
                        haiku_score = 0.5
                    else:
                        successful_evals += 1

                    judge1_scores.append(gpt4o_score)
                    judge2_scores.append(haiku_score)
            else:
                # Single judge results: just gpt4o_score
                for i, doc_result in enumerate(results):
                    if isinstance(doc_result, Exception):
                        logger.error(f"Document {i+1} evaluation failed: {doc_result}")
                        # Use neutral score for failed evaluation
                        judge1_scores.append(0.5)
                        judge2_scores.append(None)  # No second judge
                        continue

                    gpt4o_score = doc_result

                    if isinstance(gpt4o_score, Exception):
                        logger.warning(f"GPT-4o failed for document {i+1}: {gpt4o_score}")
                        gpt4o_score = 0.5
                    else:
                        successful_evals += 1

                    judge1_scores.append(gpt4o_score)
                    judge2_scores.append(None)  # No second judge in single judge mode

            # Calculate Cohen's Kappa if we have both judges
            if call_both_judges and successful_evals > 0:
                try:
                    kappa = self._calculate_cohen_kappa(judge1_scores, judge2_scores)
                except ValueError as e:
                    logger.warning(f"Kappa calculation failed: {e}")
                    kappa = 0.0
            else:
                # Single judge mode: No Kappa (only one judge)
                kappa = None

            # Calculate performance metrics
            latency = time.time() - start_time

            # Note: API costs are now logged per-call in _call_gpt4o_judge() and
            # _call_haiku_judge() using actual token counts (Story 3.10)

            # Update ground_truth table
            await self._update_ground_truth(
                query_id, judge1_scores, judge2_scores, kappa, is_spot_check
            )

            logger.info(
                f"Dual judge evaluation completed: {len(docs)} docs, "
                f"kappa={kappa:.3f if kappa is not None else 'N/A'}, latency={latency:.2f}s"
            )

            return {
                "judge1_scores": judge1_scores,
                "judge2_scores": judge2_scores,
                "judge1_model": "gpt-4o",
                "judge2_model": "claude-3-5-haiku-20241022" if call_both_judges else None,
                "kappa": kappa,
                "latency_seconds": latency,
                "successful_evaluations": successful_evals,
                "total_evaluations": len(docs) * (2 if call_both_judges else 1),
                "spot_check": is_spot_check,
                "dual_judge_enabled": self.dual_judge_enabled,
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Dual judge evaluation failed: {e}")
            return {
                "error": "Evaluation failed",
                "details": str(e),
                "judge1_scores": [],
                "judge2_scores": [],
                "kappa": 0.0,
                "spot_check": is_spot_check,
                "status": "failed",
            }

    async def _update_ground_truth(
        self,
        query_id: int,
        judge1_scores: list[float],
        judge2_scores: list[float],
        kappa: float | None,
        is_spot_check: bool,
    ) -> None:
        """
        Update ground_truth table with judge scores and spot check metadata.

        Story 3.9: Adds spot_check flag to metadata JSONB field for tracking
        spot checks vs full evaluations.

        Args:
            query_id: Ground truth query ID
            judge1_scores: Scores from GPT-4o
            judge2_scores: Scores from Haiku (or None for single judge mode)
            kappa: Cohen's Kappa score (None for single judge mode)
            is_spot_check: True if this was a spot check, False otherwise
        """
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Build metadata JSONB with spot_check flag
                metadata = {"spot_check": is_spot_check}

                # Update with judge scores and metadata
                cursor.execute(
                    """
                    UPDATE ground_truth
                    SET judge1_score = %s,
                        judge2_score = %s,
                        judge1_model = 'gpt-4o',
                        judge2_model = CASE
                            WHEN %s IS NOT NULL THEN 'claude-3-5-haiku-20241022'
                            ELSE NULL
                        END,
                        kappa = %s,
                        metadata = metadata || %s::jsonb
                    WHERE id = %s;
                    """,
                    (judge1_scores, judge2_scores, judge2_scores, kappa, metadata, query_id),
                )

                conn.commit()
                mode = "spot check" if is_spot_check else ("single judge" if judge2_scores is None or all(s is None for s in judge2_scores) else "dual judge")
                logger.info(
                    f"Updated ground_truth record {query_id} with {mode} scores"
                )

        except Exception as e:
            logger.error(f"Failed to update ground_truth: {e}")
            raise
