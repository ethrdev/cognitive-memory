"""
OpenAI API Client for Embeddings.

Provides text embeddings using OpenAI's text-embedding-3-small model (1536 dimensions).
Includes automatic retry logic with exponential backoff for transient failures.
"""

from __future__ import annotations

import logging
import os
from typing import List

from openai import AsyncOpenAI

from mcp_server.config import calculate_api_cost
from mcp_server.db.cost_logger import insert_cost_log
from mcp_server.utils.retry_logic import retry_with_backoff

logger = logging.getLogger(__name__)


class OpenAIEmbeddingsClient:
    """
    OpenAI Embeddings API client with retry logic.

    Provides text embeddings using text-embedding-3-small model (1536 dims).
    Includes automatic retry on transient failures (rate limits, service unavailable).
    """

    def __init__(self) -> None:
        """Initialize OpenAI client with API key from environment."""
        self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key or self.api_key == "sk-your-openai-api-key-here":
            raise RuntimeError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )

        # Initialize async client
        self.client = AsyncOpenAI(api_key=self.api_key)

        # Model configuration
        self.model = "text-embedding-3-small"  # 1536 dimensions
        self.embedding_dims = 1536

        logger.info(
            f"OpenAI Embeddings Client initialized: model={self.model}, "
            f"dims={self.embedding_dims}"
        )

    @retry_with_backoff(max_retries=4, base_delays=[1.0, 2.0, 4.0, 8.0], jitter=True)
    async def create_embedding(self, text: str) -> List[float]:
        """
        Create text embedding using OpenAI API with automatic retry.

        Applies retry logic with exponential backoff for transient failures:
        - Rate Limit (429): Retries with delays [1s, 2s, 4s, 8s] ±20% jitter
        - Service Unavailable (503): Retries with exponential backoff
        - Timeout (408/504): Retries with exponential backoff

        After 4 failed retries (~15s total), raises exception to caller.
        No fallback available (embeddings are critical dependency).

        Args:
            text: Input text to embed (max 8191 tokens for text-embedding-3-small)

        Returns:
            1536-dimensional embedding vector as list of floats

        Raises:
            RateLimitError: If rate limit persists after 4 retries
            ServiceUnavailableError: If service unavailable after 4 retries
            APIConnectionError: If connection fails after 4 retries
            APITimeoutError: If timeout occurs after 4 retries

        Example:
            >>> client = OpenAIEmbeddingsClient()
            >>> embedding = await client.create_embedding("Hello world")
            >>> len(embedding)
            1536

        Note:
            Function name "create_embedding" will be mapped to api_name "openai_embeddings"
            in retry logging (see retry_logic._extract_api_name).
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
                encoding_format="float",  # Return as list of floats
            )

            # Extract embedding vector from response
            embedding = response.data[0].embedding

            # Extract token count from API response (Story 3.10: Budget Monitoring)
            token_count = response.usage.total_tokens if hasattr(response, 'usage') else len(text) // 4

            # Calculate cost (Story 3.10: Budget Monitoring)
            estimated_cost = calculate_api_cost('openai_embeddings', token_count)

            # Log API cost to database (Story 3.10: Budget Monitoring)
            insert_cost_log(
                api_name='openai_embeddings',
                num_calls=1,
                token_count=token_count,
                estimated_cost=estimated_cost
            )

            logger.debug(
                f"Embedding created: input_length={len(text)}, "
                f"embedding_dims={len(embedding)}, "
                f"tokens={token_count}, cost=€{estimated_cost:.6f}"
            )

            return embedding

        except Exception as e:
            # Let retry decorator handle retryable errors
            # Non-retryable errors (400, 401, 403) will fail immediately
            logger.error(f"OpenAI Embeddings API error: {type(e).__name__}: {e}")
            raise


# Singleton instance for module-level access
_client_instance: OpenAIEmbeddingsClient | None = None


async def get_embeddings_client() -> OpenAIEmbeddingsClient:
    """
    Get singleton OpenAI Embeddings client instance.

    Lazily initializes client on first call.

    Returns:
        Shared OpenAIEmbeddingsClient instance
    """
    global _client_instance
    if _client_instance is None:
        _client_instance = OpenAIEmbeddingsClient()
    return _client_instance


async def create_embedding(text: str) -> List[float]:
    """
    Module-level convenience function for creating embeddings.

    Uses singleton client instance. Includes automatic retry logic.

    Args:
        text: Input text to embed

    Returns:
        1536-dimensional embedding vector

    Example:
        >>> from mcp_server.external.openai_client import create_embedding
        >>> embedding = await create_embedding("Hello world")
        >>> len(embedding)
        1536
    """
    client = await get_embeddings_client()
    return await client.create_embedding(text)
