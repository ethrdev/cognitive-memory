"""
IEF (Integrative Evaluation Function) Implementation
====================================================

Core module for calculating the Integrative Evaluation Function score
that combines multiple relevance signals for context-aware graph traversal.

This function implements the ICAI (Integrative Context Assembly Interface)
scoring logic that weights relevance, semantic similarity, recency, and
constitutive relationships.
"""

import math
from datetime import datetime, timezone
from typing import Any

# IEF Weights (sum = 1.0)
IEF_WEIGHT_RELEVANCE = 0.30
IEF_WEIGHT_SIMILARITY = 0.25
IEF_WEIGHT_RECENCY = 0.20
IEF_WEIGHT_CONSTITUTIVE = 0.25

# Constants
RECENCY_DECAY_DAYS = 30  # Half-life for recency_boost
CONSTITUTIVE_BOOST = 1.5  # 50% boost for constitutive edges
NUANCE_PENALTY = 0.1  # Temporary penalty for unresolved NUANCE conflicts


def calculate_ief_score(
    edge_data: dict[str, Any],
    query_embedding: list[float] | None = None,
    pending_nuance_edge_ids: set[str] | None = None
) -> dict[str, Any]:
    """
    Calculate the Integrative Evaluation Score for an edge.

    Combines four components:
    - relevance_score: Memory Strength × Ebbinghaus Decay
    - semantic_similarity: Cosine similarity to query (via L2-Insight)
    - recency_boost: Exponential boost for recent updates
    - constitutive_weight: Higher weight for constitutive edges

    Args:
        edge_data: Dict with edge_properties, last_accessed, access_count,
                   modified_at, vector_id (optional)
        query_embedding: Optional 1536-dim query embedding for semantic similarity
        pending_nuance_edge_ids: Optional set of edge IDs with unresolved NUANCE reviews

    Returns:
        Dict with ief_score and all components for transparency:
        {
            "ief_score": float,
            "components": {
                "relevance_score": float,
                "semantic_similarity": float,
                "recency_boost": float,
                "constitutive_weight": float,
                "nuance_penalty": float
            },
            "weights": {
                "relevance": 0.30,
                "similarity": 0.25,
                "recency": 0.20,
                "constitutive": 0.25
            }
        }
    """
    edge_id = edge_data.get("edge_id") or edge_data.get("id")
    properties = edge_data.get("edge_properties") or edge_data.get("properties") or {}

    # Component 1: Relevance Score (from Story 7.3)
    # Import here to avoid circular imports
    from mcp_server.db.graph import calculate_relevance_score
    relevance_score = calculate_relevance_score(edge_data)

    # Component 2: Semantic Similarity
    vector_id = properties.get("vector_id") or edge_data.get("vector_id")
    semantic_similarity = _calculate_semantic_similarity(
        vector_id=vector_id,
        query_embedding=query_embedding
    )

    # Component 3: Recency Boost
    modified_at = edge_data.get("modified_at")
    recency_boost = _calculate_recency_boost(modified_at)

    # Component 4: Constitutive Weight
    is_constitutive = properties.get("edge_type") == "constitutive"
    constitutive_weight = CONSTITUTIVE_BOOST if is_constitutive else 1.0

    # Nuance Penalty (temporary for unresolved conflicts)
    nuance_penalty = 0.0
    if pending_nuance_edge_ids and edge_id and str(edge_id) in pending_nuance_edge_ids:
        nuance_penalty = NUANCE_PENALTY

    # Calculate IEF Score
    ief_score = (
        (relevance_score * IEF_WEIGHT_RELEVANCE) +
        (semantic_similarity * IEF_WEIGHT_SIMILARITY) +
        (recency_boost * IEF_WEIGHT_RECENCY) +
        (constitutive_weight * IEF_WEIGHT_CONSTITUTIVE)
    ) - nuance_penalty

    # Clamp to [0.0, 1.5] (theoretical maximum with constitutive boost)
    ief_score = max(0.0, min(1.5, ief_score))

    return {
        "ief_score": ief_score,
        "components": {
            "relevance_score": relevance_score,
            "semantic_similarity": semantic_similarity,
            "recency_boost": recency_boost,
            "constitutive_weight": constitutive_weight,
            "nuance_penalty": nuance_penalty
        },
        "weights": {
            "relevance": IEF_WEIGHT_RELEVANCE,
            "similarity": IEF_WEIGHT_SIMILARITY,
            "recency": IEF_WEIGHT_RECENCY,
            "constitutive": IEF_WEIGHT_CONSTITUTIVE
        }
    }


def _calculate_recency_boost(modified_at: datetime | str | None) -> float:
    """
    Calculate recency boost based on modified_at timestamp.

    Formula: recency = exp(-days_since_modified / RECENCY_DECAY_DAYS)

    Args:
        modified_at: Timestamp of last modification

    Returns:
        Float between 0.0 and 1.0
    """
    if not modified_at:
        return 0.5  # Neutral if no timestamp

    if isinstance(modified_at, str):
        modified_at = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))

    # Timezone-aware handling (from Story 7.3 review fix)
    if modified_at.tzinfo is None:
        modified_at = modified_at.replace(tzinfo=timezone.utc)

    days_since = (datetime.now(timezone.utc) - modified_at).total_seconds() / 86400

    # Exponential decay
    return max(0.0, min(1.0, math.exp(-days_since / RECENCY_DECAY_DAYS)))


def _calculate_semantic_similarity(
    vector_id: int | None,
    query_embedding: list[float] | None
) -> float:
    """
    Calculate cosine similarity between query embedding and L2-Insight embedding.

    Args:
        vector_id: Foreign key to l2_insights.id
        query_embedding: 1536-dim query embedding

    Returns:
        Float between 0.0 and 1.0, or 0.5 if not calculable
    """
    if not vector_id or not query_embedding:
        return 0.5  # Neutral if no data

    insight_embedding = _get_insight_embedding(vector_id)
    if not insight_embedding:
        return 0.5

    return _cosine_similarity(query_embedding, insight_embedding)


def _get_insight_embedding(vector_id: int) -> list[float] | None:
    """
    Get embedding from l2_insights table.

    Args:
        vector_id: Foreign key to l2_insights.id

    Returns:
        1536-dim embedding or None
    """
    from mcp_server.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT embedding
            FROM l2_insights
            WHERE id = %s;
            """,
            (vector_id,)
        )
        result = cursor.fetchone()
        if result and result["embedding"]:
            # pgvector stores as list
            return list(result["embedding"])
    return None


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors (numpy-free).

    Args:
        vec_a: First vector
        vec_b: Second vector (must have same length)

    Returns:
        Float between -1.0 and 1.0 (normalized to 0.0-1.0)
    """
    if len(vec_a) != len(vec_b):
        return 0.5  # Fallback on dimension mismatch

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.5  # Fallback on zero vector

    # Cosine similarity range: [-1, 1] → normalize to [0, 1]
    cos_sim = dot_product / (norm_a * norm_b)
    return (cos_sim + 1) / 2  # Map [-1,1] to [0,1]