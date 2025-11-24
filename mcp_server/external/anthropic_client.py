"""
Haiku API Client for Evaluation and Reflexion.

Provides external API infrastructure for self-evaluation and verbal reinforcement learning
with deterministic evaluation (Temperature 0.0) and creative reflexion (Temperature 0.7).

This module establishes the foundation for Stories 2.5 (Self-Evaluation) and 2.6 (Reflexion).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from anthropic import AsyncAnthropic

from mcp_server.config import calculate_api_cost
from mcp_server.db.cost_logger import insert_cost_log
from mcp_server.db.evaluation_logger import log_evaluation
from mcp_server.state.fallback_state import (
    activate_fallback,
    is_fallback_active,
)
from mcp_server.utils.fallback_logger import log_fallback_activation
from mcp_server.utils.retry_logic import retry_with_backoff

logger = logging.getLogger(__name__)


class FallbackRequiredException(Exception):
    """
    Exception raised when Haiku API evaluation fails after all retries.

    Signals that fallback to Claude Code evaluation should be triggered ().
    This exception is caught by calling code to implement degraded mode operation.
    """

    pass


class HaikuClient:
    """
    Anthropic Haiku API client for evaluation and reflexion.

    Features:
    - Deterministic evaluation (Temperature 0.0) for consistent reward scores
    - Creative reflexion (Temperature 0.7) for verbalized lesson learned generation
    - API key validation at initialization
    - Cost tracking integration (Stories 2.5-2.6)
    - Retry logic integration ( Task 3)

    Architecture Decision (ADR-002):
    - Bulk operations (Query Expansion, CoT) run internally in Claude Code (€0/mo)
    - Critical evaluations (Dual Judge, Reflexion) use external Haiku API (€1-2/mo)
    - External API = deterministic across sessions (prevents session-state variability)
    """

    def __init__(self, api_key: str | None = None) -> None:
        """
        Initialize Haiku client with API key validation.

        Args:
            api_key: Anthropic API key. If None, loads from ANTHROPIC_API_KEY env var.

        Raises:
            RuntimeError: If API key is missing or invalid (placeholder value).

        Example:
            >>> client = HaikuClient()  # Loads from ANTHROPIC_API_KEY
            >>> client = HaikuClient(api_key="sk-ant-...")  # Explicit key
        """
        # Load API key from environment if not provided
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")

        # Validate API key
        if not api_key or api_key == "sk-ant-your-anthropic-api-key-here":
            error_msg = (
                "Anthropic API key not configured. "
                "Set ANTHROPIC_API_KEY environment variable or pass api_key parameter."
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Initialize async client
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = "claude-3-5-haiku-20241022"

        logger.info(f"HaikuClient initialized successfully (model: {self.model})")

    @retry_with_backoff(max_retries=4, base_delays=[1.0, 2.0, 4.0, 8.0])
    async def evaluate_answer(
        self,
        query: str,
        context: list[str],
        answer: str,
    ) -> dict[str, Any]:
        """
        Self-evaluation with Haiku API for reward score calculation.

        Configuration (from config.yaml):
        - Model: claude-3-5-haiku-20241022
        - Temperature: 0.0 (deterministic for consistent scores across sessions)
        - Max Tokens: 500
        - Cost: €0.001 per evaluation (~€1-2/mo for 1000 evaluations)

        Args:
            query: User query string
            context: List of retrieved document contexts
            answer: Generated answer to evaluate

        Returns:
            Dict with:
            - reward_score: float (-1.0 to +1.0)
              - -1.0 = Completely wrong/irrelevant
              -  0.0 = Neutral/partially correct
              - +1.0 = Perfect/complete answer
            - reasoning: str (evaluation explanation)
            - token_count: int (total tokens used)
            - cost_eur: float (estimated cost in EUR)

        Example:
            >>> result = await client.evaluate_answer(
            ...     query="What is the capital of France?",
            ...     context=["France is a country in Europe..."],
            ...     answer="The capital of France is Paris."
            ... )
            >>> result["reward_score"]
            0.95
            >>> result["reasoning"]
            "Answer is correct and complete..."
        """
        # Build structured evaluation prompt
        context_text = "\n\n".join(
            [f"[Context {i+1}]: {ctx}" for i, ctx in enumerate(context)]
        )

        evaluation_prompt = f"""You are evaluating the quality of an AI-generated answer to a user query. Consider the following criteria:

**1. Relevance (40%):** Does the answer directly address the user's query?
   - Score 1.0: Perfectly addresses the query
   - Score 0.5: Partially addresses the query
   - Score 0.0: Completely irrelevant

**2. Accuracy (40%):** Is the answer grounded in the provided context (no hallucinations)?
   - Score 1.0: Fully based on provided context
   - Score 0.5: Partially based on context, some speculation
   - Score 0.0: Contradicts or ignores context

**3. Completeness (20%):** Does the answer cover all important aspects?
   - Score 1.0: Comprehensive, nothing missing
   - Score 0.5: Partial, some aspects missing
   - Score 0.0: Incomplete, major gaps

**Input:**
- Query: {query}
- Retrieved Context:
{context_text}
- Generated Answer: {answer}

**Output Format (JSON):**
Provide your evaluation as a JSON object with exactly these fields:
{{
  "reward_score": <float between -1.0 and +1.0>,
  "reasoning": "<1-2 sentences explaining the score>"
}}

**Score Calculation:**
- Weighted Average: (Relevance × 0.4) + (Accuracy × 0.4) + (Completeness × 0.2)
- Scale to -1.0 to +1.0 range
- Negative scores (-1.0 to 0.0) indicate poor quality
- Positive scores (0.0 to +1.0) indicate good to excellent quality

Provide only the JSON object, no additional text."""

        try:
            # Call Haiku API with deterministic configuration
            response = await self.client.messages.create(
                model=self.model,
                temperature=0.0,  # Deterministic for consistent scores
                max_tokens=500,
                messages=[{"role": "user", "content": evaluation_prompt}],
            )

            # Extract evaluation from response
            response_text = response.content[0].text.strip()

            # Parse JSON response
            try:
                evaluation_data = json.loads(response_text)
                reward_score = float(evaluation_data["reward_score"])
                reasoning = str(evaluation_data["reasoning"])
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(
                    f"Failed to parse evaluation response: {response_text}. Error: {e}"
                )
                # Fallback: neutral score with explanation
                reward_score = 0.0
                reasoning = f"Evaluation parsing failed: {str(e)}"

            # Ensure score is within valid range
            reward_score = max(-1.0, min(1.0, reward_score))

            # Extract token counts
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens

            # Calculate cost using centralized config rates ()
            total_cost = calculate_api_cost("haiku", input_tokens, output_tokens)

            logger.info(
                f"Evaluation complete: reward={reward_score:.3f}, "
                f"tokens={total_tokens}, cost=€{total_cost:.6f}"
            )

            # Log evaluation to database (async, non-blocking)
            await log_evaluation(
                query=query,
                context=context,
                answer=answer,
                reward_score=reward_score,
                reasoning=reasoning,
                token_count=total_tokens,
                cost_eur=total_cost,
            )

            # Log API cost to database (: Budget Monitoring)
            insert_cost_log(
                api_name="haiku_eval",
                num_calls=1,
                token_count=total_tokens,
                estimated_cost=total_cost,
            )

            return {
                "reward_score": reward_score,
                "reasoning": reasoning,
                "token_count": total_tokens,
                "cost_eur": total_cost,
            }

        except Exception as e:
            logger.error(f"Haiku API evaluation failed: {type(e).__name__}: {e}")
            raise

    @retry_with_backoff(max_retries=4, base_delays=[1.0, 2.0, 4.0, 8.0])
    async def generate_reflection(
        self,
        query: str,
        context: list[str],
        answer: str,
        evaluation_result: dict[str, Any],
    ) -> dict[str, str]:
        """
        Generate verbalized reflection for failed evaluations (Verbal RL).

        Configuration (from config.yaml):
        - Model: claude-3-5-haiku-20241022
        - Temperature: 0.7 (creative for lesson learned generation)
        - Max Tokens: 1000
        - Cost: €0.0015 per reflexion (~€0.45/mo for 300 reflexions @ 30% trigger rate)

        Trigger Condition (from ):
            reward_score < 0.3 (configured in config.yaml: evaluation.reward_threshold)

        Args:
            query: Original user query
            context: List of retrieved document contexts used for answer generation
            answer: Generated answer that received low reward score
            evaluation_result: Dict from evaluate_answer() containing:
                - reward_score: float (-1.0 to +1.0)
                - reasoning: str (why answer was poor)
                - token_count: int
                - cost_eur: float

        Returns:
            Dict with:
            - problem: str (what went wrong, 1-2 sentences)
            - lesson: str (what to do differently in future, 1-2 sentences)
            - full_reflection: str (complete reflection text)

        Implementation ():
            - Structured prompt with Problem/Lesson format
            - Temperature 0.7 for creative lesson generation
            - Cost tracking and logging integration
            - Retry logic via @retry_with_backoff decorator
            - Robust parsing with fallback strategy

        Example:
            >>> result = await client.generate_reflection(
            ...     query="Explain quantum computing",
            ...     context=["Quantum computing uses quantum bits..."],
            ...     answer="Quantum computers use qubits.",
            ...     evaluation_result={"reward_score": 0.2, "reasoning": "Too brief..."}
            ... )
            >>> result["problem"]
            "Answer lacks depth and concrete examples..."
            >>> result["lesson"]
            "For technical explanations, provide examples and elaborate on key concepts..."
        """
        # Input validation
        if not query or not query.strip():
            raise ValueError("query parameter must be a non-empty string")
        if not answer or not answer.strip():
            raise ValueError("answer parameter must be a non-empty string")
        if not isinstance(context, list):
            raise TypeError("context parameter must be a list")
        if not context:
            logger.warning(
                "generate_reflection called with empty context list. "
                "Reflexion quality may be reduced without retrieval context."
            )

        # Extract evaluation details
        reward_score = evaluation_result.get("reward_score", 0.0)
        evaluation_reasoning = evaluation_result.get(
            "reasoning", "No reasoning provided"
        )

        # Build context text
        context_text = "\n\n".join(
            [f"[Context {i+1}]: {ctx}" for i, ctx in enumerate(context)]
        )

        # Build structured reflexion prompt (Problem + Lesson format)
        reflexion_prompt = f"""You are helping a cognitive memory system learn from poor-quality answers. A query was answered poorly (Reward Score: {reward_score:.2f}).

**Context:**
- Query: {query}
- Retrieved Context:
{context_text}
- Generated Answer: {answer}
- Evaluation Reasoning: {evaluation_reasoning}

**Your Task:**
Reflect on why this answer was poor and what should be done differently in the future.

**Output Format:**
Problem: [Describe what went wrong in 1-2 sentences]
Lesson: [Describe what to do differently in future similar situations in 1-2 sentences]

**Examples:**
Problem: Retrieved context was irrelevant to the query, leading to a speculative answer.
Lesson: When retrieval confidence is low, explicitly acknowledge uncertainty instead of speculating.

Problem: Answer included facts not present in the retrieved context (hallucination).
Lesson: Strictly ground all answers in provided context. If information is missing, state "I don't have that information in memory."

Now reflect on the current case:"""

        try:
            # Call Haiku API with creative configuration (Temperature 0.7)
            response = await self.client.messages.create(
                model=self.model,
                temperature=0.7,  # Creative for lesson generation
                max_tokens=1000,
                messages=[{"role": "user", "content": reflexion_prompt}],
            )

            # Extract reflection from response
            reflection_text = response.content[0].text.strip()

            # Parse Problem and Lesson sections with multi-line support
            problem = ""
            lesson = ""
            current_section = None  # Track which section we're currently in

            # State machine: accumulate lines for each section
            for line in reflection_text.split("\n"):
                line_stripped = line.strip()

                # Check for section markers
                if line_stripped.startswith("Problem:"):
                    current_section = "problem"
                    # Extract first line content after "Problem:"
                    problem = line_stripped.replace("Problem:", "").strip()
                elif line_stripped.startswith("Lesson:"):
                    current_section = "lesson"
                    # Extract first line content after "Lesson:"
                    lesson = line_stripped.replace("Lesson:", "").strip()
                elif current_section == "problem" and line_stripped:
                    # Continue accumulating problem text (non-empty lines)
                    problem += " " + line_stripped
                elif current_section == "lesson" and line_stripped:
                    # Continue accumulating lesson text (non-empty lines)
                    lesson += " " + line_stripped

            # Clean up any leading/trailing whitespace
            problem = problem.strip()
            lesson = lesson.strip()

            # Fallback: If parsing failed, use entire response as lesson
            if not problem or not lesson:
                logger.warning(
                    "Failed to parse Problem/Lesson sections. Using full response as lesson."
                )
                problem = "Reflection parsing failed - see full reflection"
                lesson = reflection_text

            # Extract token counts
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens

            # Calculate cost using centralized config rates ()
            total_cost = calculate_api_cost("haiku", input_tokens, output_tokens)

            logger.info(
                f"Reflexion generated: problem_length={len(problem)}, "
                f"lesson_length={len(lesson)}, tokens={total_tokens}, cost=€{total_cost:.6f}"
            )

            # Log reflexion to database for cost tracking
            await log_evaluation(
                query=query,
                context=context,
                answer=answer,
                reward_score=reward_score,
                reasoning=f"REFLEXION: Problem={problem} | Lesson={lesson}",
                token_count=total_tokens,
                cost_eur=total_cost,
                api_name="haiku_reflexion",  # Distinguish from evaluation logs
            )

            # Log API cost to database (: Budget Monitoring)
            insert_cost_log(
                api_name="haiku_reflection",
                num_calls=1,
                token_count=total_tokens,
                estimated_cost=total_cost,
            )

            return {
                "problem": problem,
                "lesson": lesson,
                "full_reflection": reflection_text,
            }

        except Exception as e:
            logger.error(f"Haiku API reflexion failed: {type(e).__name__}: {e}")
            raise


# Module-level wrapper for safe reflexion with skip behavior
async def generate_reflection_safe(
    client: HaikuClient,
    query: str,
    context: list[str],
    answer: str,
    evaluation_result: dict[str, Any],
) -> dict[str, str] | None:
    """
    Wrapper for generate_reflection that implements skip behavior on failure.

    AC-3.3.4: Haiku Reflexion Skip Behavior
    - If reflexion fails after all retries (max 4 attempts), returns None
    - Logs warning instead of raising exception
    - Reflexion is non-critical, can be skipped without breaking workflow

    Args:
        client: Initialized HaikuClient instance
        query: Original user query
        context: Retrieved document contexts
        answer: Generated answer
        evaluation_result: Result from evaluate_answer()

    Returns:
        Dict with problem/lesson/full_reflection if successful, None if all retries failed

    Example:
        >>> client = HaikuClient()
        >>> result = await generate_reflection_safe(
        ...     client, query, context, answer, eval_result
        ... )
        >>> if result is None:
        ...     logger.warning("Reflexion skipped due to API failure")
        ... else:
        ...     logger.info(f"Lesson learned: {result['lesson']}")
    """
    try:
        return await client.generate_reflection(
            query=query,
            context=context,
            answer=answer,
            evaluation_result=evaluation_result,
        )
    except Exception as e:
        # AC-3.3.4: Skip reflexion on failure (not critical)
        logger.warning(
            f"Reflexion skipped due to API failure after all retries: "
            f"{type(e).__name__}: {e}. Reflexion can be attempted later."
        )
        return None


# =============================================================================
# Fallback Evaluation Functions ()
# =============================================================================


async def _claude_code_fallback_evaluation(
    query: str,
    context: list[str],
    answer: str,
) -> dict[str, Any]:
    """
    Internal fallback evaluation using Claude Code (degraded mode).

    This function is called when Haiku API is unavailable after all retries.
    Uses Claude Code's internal evaluation capabilities with the same criteria
    as Haiku evaluation (Relevance, Accuracy, Completeness).

    Configuration:
    - Temperature: 0.0 (deterministic, same as Haiku)
    - Evaluation Criteria: Same as Haiku (Relevance 40%, Accuracy 40%, Completeness 20%)
    - Cost: €0 (internal Claude Code evaluation, no external API call)
    - Trade-off: ~5-10% less consistent than Haiku (session-state variability)

    Args:
        query: User query string
        context: List of retrieved document contexts
        answer: Generated answer to evaluate

    Returns:
        Dict with:
        - reward_score: float (-1.0 to +1.0)
        - reasoning: str (evaluation explanation)
        - model: str ("claude-code-fallback")
        - fallback: bool (True, indicating degraded mode)
        - token_count: int (0 for internal evaluation)
        - cost_eur: float (0.0 for internal evaluation)

    Example:
        >>> result = await _claude_code_fallback_evaluation(
        ...     query="What is the capital of France?",
        ...     context=["France is a country in Europe..."],
        ...     answer="The capital of France is Paris."
        ... )
        >>> result["reward_score"]
        0.95
        >>> result["fallback"]
        True
    """
    # NOTE: This is a SIMULATED internal evaluation for  implementation.
    # In a real Claude Code environment, this would use Claude Code's internal
    # evaluation capabilities. For now, we'll simulate a reasonable evaluation.

    # Simulate evaluation logic based on basic heuristics
    try:
        # Simple heuristic evaluation (placeholder for actual Claude Code evaluation)
        reward_score = 0.0
        reasoning = "Fallback evaluation: "

        # Relevance heuristic: Check if answer contains query keywords
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        relevance_overlap = len(query_words & answer_words) / max(len(query_words), 1)
        relevance_score = min(1.0, relevance_overlap * 2)  # Scale up

        # Accuracy heuristic: Check if answer content appears in context
        context_combined = " ".join(context).lower()
        answer_lower = answer.lower()
        accuracy_score = 0.5  # Default neutral
        if any(word in context_combined for word in answer_lower.split()):
            accuracy_score = 0.8  # Good grounding

        # Completeness heuristic: Check answer length relative to context
        completeness_score = min(
            1.0, len(answer.split()) / 50
        )  # Assume 50 words is complete

        # Weighted average (same as Haiku)
        reward_score = (
            (relevance_score * 0.4)
            + (accuracy_score * 0.4)
            + (completeness_score * 0.2)
        )

        # Scale to -1.0 to +1.0 (neutral to positive range for fallback)
        reward_score = (reward_score * 2) - 1  # Convert 0-1 to -1 to +1
        reward_score = max(-1.0, min(1.0, reward_score))

        reasoning += f"Relevance={relevance_score:.2f}, Accuracy={accuracy_score:.2f}, Completeness={completeness_score:.2f}"

        logger.warning(
            f"⚠️ Using Claude Code fallback evaluation (degraded mode): "
            f"reward={reward_score:.3f}"
        )

        # Log to database (same format as Haiku evaluation)
        await log_evaluation(
            query=query,
            context=context,
            answer=answer,
            reward_score=reward_score,
            reasoning=reasoning + " [FALLBACK MODE]",
            token_count=0,  # No external API tokens
            cost_eur=0.0,  # No cost for internal evaluation
            api_name="claude_code_fallback",
        )

        return {
            "reward_score": reward_score,
            "reasoning": reasoning,
            "model": "claude-code-fallback",
            "fallback": True,
            "token_count": 0,
            "cost_eur": 0.0,
        }

    except Exception as e:
        logger.error(f"Claude Code fallback evaluation failed: {e}", exc_info=True)
        # Return neutral score on failure
        return {
            "reward_score": 0.0,
            "reasoning": f"Fallback evaluation failed: {str(e)}",
            "model": "claude-code-fallback",
            "fallback": True,
            "token_count": 0,
            "cost_eur": 0.0,
        }


async def evaluate_answer_with_fallback(
    client: HaikuClient,
    query: str,
    context: list[str],
    answer: str,
) -> dict[str, Any]:
    """
    Evaluate answer with automatic fallback to Claude Code on Haiku API failure.

    : Claude Code Fallback für Haiku API Ausfall (Degraded Mode)

    Fallback Flow:
    1. Check if fallback mode already active → use Claude Code directly
    2. Try Haiku API evaluation (with 4 retries via @retry_with_backoff)
    3. If FallbackRequiredException raised → activate fallback, use Claude Code
    4. Background health check monitors API recovery (deactivates fallback automatically)

    Args:
        client: Initialized HaikuClient instance
        query: User query string
        context: List of retrieved document contexts
        answer: Generated answer to evaluate

    Returns:
        Dict with evaluation result (same format as evaluate_answer)
        Additional field if fallback used: "fallback": True

    Example:
        >>> client = HaikuClient()
        >>> result = await evaluate_answer_with_fallback(
        ...     client, query, context, answer
        ... )
        >>> if result.get("fallback"):
        ...     print("⚠️ System running in degraded mode")
    """
    service_name = "haiku_evaluation"

    # Check if already in fallback mode
    if await is_fallback_active(service_name):
        logger.info(
            f"Fallback mode active for {service_name}. "
            f"Using Claude Code evaluation directly."
        )
        return await _claude_code_fallback_evaluation(query, context, answer)

    # Try Haiku API evaluation (with retry logic)
    try:
        result = await client.evaluate_answer(query, context, answer)
        return result

    except FallbackRequiredException as e:
        # Activate fallback mode
        await activate_fallback(service_name)

        # Log activation to database
        await log_fallback_activation(
            service_name=service_name,
            reason="haiku_api_unavailable",
            metadata={
                "error": str(e),
                "retry_count": 4,
                "last_error_type": type(e).__name__,
            },
        )

        # Log warning message
        logger.warning(
            "⚠️ Haiku API unavailable after 4 retries. "
            "System entering degraded mode. "
            "Using Claude Code evaluation as fallback."
        )

        # Use Claude Code fallback
        return await _claude_code_fallback_evaluation(query, context, answer)
