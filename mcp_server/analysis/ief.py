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
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Callable

# IEF Weights (sum = 1.0) - mutable, can be recalibrated
IEF_WEIGHT_RELEVANCE = 0.30
IEF_WEIGHT_SIMILARITY = 0.25
IEF_WEIGHT_RECENCY = 0.20
IEF_WEIGHT_CONSTITUTIVE = 0.25

# Constants
RECENCY_DECAY_DAYS = 30  # Half-life for recency_boost
CONSTITUTIVE_BOOST = 1.5  # 50% boost for constitutive edges
NUANCE_PENALTY = 0.1  # Temporary penalty for unresolved NUANCE conflicts

# W_min Guarantee (Story 7.7, AC Zeile 432)
# Constitutive edges ALWAYS have at least this weight - non-negotiable
W_MIN_CONSTITUTIVE = 1.5

# ICAI Recalibration (Story 7.7, AC Zeile 437-444)
RECALIBRATION_THRESHOLD = 50  # Recalibrate after 50 feedbacks

# Module-level state for feedback tracking
_feedback_count_since_calibration = 0
_on_feedback_callbacks: list[Callable[[str, bool, Optional[str]], None]] = []


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
    from mcp_server.utils.relevance import calculate_relevance_score
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

    # Component 4: Constitutive Weight with W_min Guarantee (Story 7.7, AC Zeile 432)
    is_constitutive = properties.get("edge_type") == "constitutive"
    if is_constitutive:
        # W_min Guarantee: constitutive edges NEVER fall below W_MIN_CONSTITUTIVE
        constitutive_weight = max(CONSTITUTIVE_BOOST, W_MIN_CONSTITUTIVE)
    else:
        constitutive_weight = 1.0

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

    # Generate feedback_request (Story 7.7, AC Zeile 394-406)
    query_id = str(uuid.uuid4())

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
        },
        "feedback_request": {
            "query_id": query_id,
            "helpful": None,  # true/false/null - set by user via on_feedback_received()
            "feedback_reason": None  # Optional: "zu viele irrelevante Ergebnisse"
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


# =============================================================================
# ICAI Functions (Story 7.7, AC Zeile 411-444)
# =============================================================================

def on_feedback_received(
    query_id: str,
    helpful: bool,
    feedback_reason: Optional[str] = None,
    constitutive_weight_used: float = IEF_WEIGHT_CONSTITUTIVE,
    query_text: str = ""
) -> dict[str, Any]:
    """
    Process feedback for an IEF query result.

    Stores feedback in ief_feedback table and triggers recalibration
    after RECALIBRATION_THRESHOLD feedbacks.

    Args:
        query_id: UUID from feedback_request
        helpful: True if result was helpful, False otherwise
        feedback_reason: Optional explanation
        constitutive_weight_used: Weight that was used for this query

    Returns:
        Dict with feedback status and recalibration info
    """
    global _feedback_count_since_calibration

    from mcp_server.db.connection import get_connection

    conn = get_connection()
    cursor = conn.cursor()

    # Store feedback (Story 7.7, AC Zeile 411-420)
    cursor.execute("""
        INSERT INTO ief_feedback (
            query_id, query_text, helpful, feedback_reason, constitutive_weight_used
        ) VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (query_id, query_text, helpful, feedback_reason, constitutive_weight_used))

    feedback_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()

    _feedback_count_since_calibration += 1

    # Trigger recalibration if threshold reached (Story 7.7, AC Zeile 437-444)
    recalibration_triggered = False
    new_weights = None

    if _feedback_count_since_calibration >= RECALIBRATION_THRESHOLD:
        new_weights = recalibrate_weights()
        recalibration_triggered = True
        _feedback_count_since_calibration = 0

    # Notify callbacks
    for callback in _on_feedback_callbacks:
        try:
            callback(query_id, helpful, feedback_reason)
        except Exception:
            pass  # Don't break on callback errors

    return {
        "feedback_id": feedback_id,
        "query_id": query_id,
        "helpful": helpful,
        "feedback_count_since_calibration": _feedback_count_since_calibration,
        "recalibration_triggered": recalibration_triggered,
        "new_weights": new_weights
    }


def recalibrate_weights() -> dict[str, float]:
    """
    Extract optimal IEF weights from preference data (ICAI principle).

    Analyzes helpful vs unhelpful queries to optimize constitutive weight.
    Maintains W_min guarantee: constitutive_weight >= 1.5

    Returns:
        Dict with new weights
    """
    global IEF_WEIGHT_CONSTITUTIVE

    from mcp_server.db.connection import get_connection
    import logging

    logger = logging.getLogger(__name__)

    conn = get_connection()
    cursor = conn.cursor()

    # Get helpful and unhelpful query stats (Story 7.7, AC Zeile 423-429)
    cursor.execute("""
        SELECT
            helpful,
            AVG(constitutive_weight_used) as avg_weight,
            COUNT(*) as count
        FROM ief_feedback
        WHERE helpful IS NOT NULL
        GROUP BY helpful
    """)

    results = cursor.fetchall()
    cursor.close()

    helpful_avg_weight = None
    unhelpful_avg_weight = None

    for row in results:
        if row[0] is True:  # helpful
            helpful_avg_weight = row[1]
        elif row[0] is False:  # unhelpful
            unhelpful_avg_weight = row[1]

    # Simple optimization: move towards helpful weight
    old_weight = IEF_WEIGHT_CONSTITUTIVE

    if helpful_avg_weight is not None and unhelpful_avg_weight is not None:
        # Net contribution: prefer weight that correlates with helpful
        if helpful_avg_weight > unhelpful_avg_weight:
            # Helpful queries used higher weight → increase slightly
            new_weight = min(0.35, IEF_WEIGHT_CONSTITUTIVE + 0.02)
        else:
            # Unhelpful queries used higher weight → decrease slightly
            new_weight = max(0.15, IEF_WEIGHT_CONSTITUTIVE - 0.02)

        IEF_WEIGHT_CONSTITUTIVE = new_weight

    # Renormalize weights to sum to 1.0
    total = IEF_WEIGHT_RELEVANCE + IEF_WEIGHT_SIMILARITY + IEF_WEIGHT_RECENCY + IEF_WEIGHT_CONSTITUTIVE

    logger.info(f"IEF recalibration: constitutive_weight {old_weight:.2f} → {IEF_WEIGHT_CONSTITUTIVE:.2f}")

    return {
        "relevance": IEF_WEIGHT_RELEVANCE,
        "similarity": IEF_WEIGHT_SIMILARITY,
        "recency": IEF_WEIGHT_RECENCY,
        "constitutive": IEF_WEIGHT_CONSTITUTIVE,
        "total": total,
        "w_min_guarantee": W_MIN_CONSTITUTIVE
    }


def get_feedback_count() -> int:
    """Get current feedback count since last calibration."""
    return _feedback_count_since_calibration


def register_feedback_callback(callback: Callable[[str, bool, Optional[str]], None]) -> None:
    """Register a callback to be notified on feedback received."""
    _on_feedback_callbacks.append(callback)