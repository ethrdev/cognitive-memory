"""Embedding Generator using OpenAI API."""

import os
import time
from collections.abc import Callable

from openai import OpenAI

# Initialize client lazily
_client: OpenAI | None = None


def get_client() -> OpenAI:
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        _client = OpenAI(api_key=api_key)
    return _client


def generate_embedding(
    text: str,
    model: str = "text-embedding-3-small",
    dimensions: int = 1536,
    max_retries: int = 3,
) -> list[float]:
    """Generate embedding for a single text.

    Args:
        text: Text to embed
        model: OpenAI embedding model
        dimensions: Embedding dimensions (1536 for text-embedding-3-small)
        max_retries: Number of retries on failure

    Returns:
        List of floats representing the embedding vector
    """
    client = get_client()

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model=model, input=text, dimensions=dimensions
            )
            return response.data[0].embedding
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2**attempt  # Exponential backoff
                print(f"Embedding failed, retrying in {wait_time}s: {e}")
                time.sleep(wait_time)
            else:
                raise


def generate_embeddings_batch(
    texts: list[str],
    model: str = "text-embedding-3-small",
    dimensions: int = 1536,
    batch_size: int = 100,
    checkpoint_callback: Callable[[int, int], None] | None = None,
) -> list[list[float]]:
    """Generate embeddings for multiple texts in batches.

    Args:
        texts: List of texts to embed
        model: OpenAI embedding model
        dimensions: Embedding dimensions
        batch_size: Number of texts per API call (max 2048)
        checkpoint_callback: Optional callback(batch_num, total_batches) for progress

    Returns:
        List of embedding vectors
    """
    client = get_client()
    all_embeddings = []

    total_batches = (len(texts) + batch_size - 1) // batch_size

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_num = i // batch_size + 1

        try:
            response = client.embeddings.create(
                model=model, input=batch, dimensions=dimensions
            )

            # Sort by index to ensure correct order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            batch_embeddings = [item.embedding for item in sorted_data]
            all_embeddings.extend(batch_embeddings)

            if checkpoint_callback:
                checkpoint_callback(batch_num, total_batches)

        except Exception as e:
            print(f"Batch {batch_num}/{total_batches} failed: {e}")
            # Try individual texts in failed batch
            for text in batch:
                try:
                    emb = generate_embedding(text, model, dimensions)
                    all_embeddings.append(emb)
                except Exception as e2:
                    print(f"Individual embedding failed: {e2}")
                    # Use zero vector as fallback (will need manual fix)
                    all_embeddings.append([0.0] * dimensions)

        # Small delay between batches to avoid rate limits
        if batch_num < total_batches:
            time.sleep(0.1)

    return all_embeddings


def estimate_cost(num_tokens: int, model: str = "text-embedding-3-small") -> float:
    """Estimate embedding cost in USD.

    Pricing (as of 2024):
    - text-embedding-3-small: $0.00002 per 1K tokens
    - text-embedding-3-large: $0.00013 per 1K tokens
    """
    prices = {
        "text-embedding-3-small": 0.00002,
        "text-embedding-3-large": 0.00013,
    }
    price_per_1k = prices.get(model, 0.00002)
    return (num_tokens / 1000) * price_per_1k
