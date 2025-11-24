"""
RRF Fusion Utility

Reciprocal Rank Fusion (RRF) algorithm for combining multiple search result lists.
This utility can be reused across different Streamlit apps that implement hybrid search.

Formula: score = semantic_weight * 1/(60 + semantic_rank) +
                 keyword_weight * 1/(60 + keyword_rank)

Based on the algorithm implemented in mcp_server/tools/__init__.py
"""

from typing import Any


def rrf_fusion(
    semantic_results: list[tuple[int, str, list[int], float]],
    keyword_results: list[tuple[int, str, list[int], float]],
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) for Hybrid Search.

    Combines semantic and keyword search results using the RRF algorithm.
    Higher ranked documents (lower rank numbers) receive higher scores.

    Args:
        semantic_results: Semantic search results as tuples (id, content, source_ids, distance)
        keyword_results: Keyword search results as tuples (id, content, source_ids, ts_rank)
        semantic_weight: Weight for semantic scores (default: 0.7)
        keyword_weight: Weight for keyword scores (default: 0.3)

    Returns:
        List of dictionaries with merged results, sorted by final score (descending).
        Each dict contains: 'id', 'content', 'source_ids', 'score'
    """
    doc_scores: dict[int, dict[str, Any]] = {}

    # Process semantic search results
    for rank, (doc_id, content, source_ids, _distance) in enumerate(semantic_results):
        doc_scores[doc_id] = {
            "id": doc_id,
            "content": content,
            "source_ids": source_ids,
            "score": semantic_weight * (1 / (60 + rank)),
        }

    # Process keyword search results (additive scoring)
    for rank, (doc_id, content, source_ids, _ts_rank) in enumerate(keyword_results):
        if doc_id in doc_scores:
            # Add to existing score
            doc_scores[doc_id]["score"] += keyword_weight * (1 / (60 + rank))
        else:
            # Create new entry for keyword-only results
            doc_scores[doc_id] = {
                "id": doc_id,
                "content": content,
                "source_ids": source_ids,
                "score": keyword_weight * (1 / (60 + rank)),
            }

    # Sort by final score in descending order
    sorted_docs = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
    return sorted_docs


def calculate_rrf_score(rank: int, weight: float = 1.0, k: int = 60) -> float:
    """
    Calculate individual RRF score for a given rank.

    Formula: score = weight * 1/(k + rank)

    Args:
        rank: The rank of the document (0-based)
        weight: Weight factor for this result list (default: 1.0)
        k: RRF constant, typically 60 (default: 60)

    Returns:
        RRF score for the given rank
    """
    return weight * (1 / (k + rank))


def validate_rrf_inputs(
    semantic_results: list[Any],
    keyword_results: list[Any],
    semantic_weight: float,
    keyword_weight: float,
) -> bool:
    """
    Validate RRF fusion inputs.

    Args:
        semantic_results: Semantic search results list
        keyword_results: Keyword search results list
        semantic_weight: Weight for semantic scores
        keyword_weight: Weight for keyword scores

    Returns:
        True if inputs are valid, False otherwise
    """
    # Check weights are positive and sum to reasonable value
    if semantic_weight < 0 or keyword_weight < 0:
        return False

    if semantic_weight + keyword_weight <= 0:
        return False

    # Check that at least one result list has content
    if not semantic_results and not keyword_results:
        return False

    return True
