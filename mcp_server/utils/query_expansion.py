"""
Query Expansion Utilities Module

Provides deduplication and fusion helpers for query expansion results.
Part of () - RAG Pipeline & Hybrid Calibration.

Functions:
- deduplicate_by_l2_id: Remove duplicate search results by L2 Insight ID
- merge_rrf_scores: Merge multiple result sets using Reciprocal Rank Fusion
"""

from typing import Dict, List


def deduplicate_by_l2_id(search_results: List[Dict]) -> List[Dict]:
    """
    Deduplicate search results by L2 Insight ID.

    Keeps highest-scoring result per L2 ID when multiple queries return
    the same document. This is critical for query expansion, where 4 queries
    (original + 3 variants) may return overlapping results.

    Args:
        search_results: List of search result dictionaries.
                        Each result must have 'id' (L2 Insight ID) and 'score' fields.

    Returns:
        List of unique search results (by L2 ID), sorted by score descending.
        Only the highest-scoring instance of each document is kept.

    Example:
        >>> results = [
        ...     {'id': 'L2-001', 'score': 0.85, 'content': 'Doc A'},
        ...     {'id': 'L2-002', 'score': 0.75, 'content': 'Doc B'},
        ...     {'id': 'L2-001', 'score': 0.80, 'content': 'Doc A'},  # Duplicate
        ... ]
        >>> deduplicate_by_l2_id(results)
        [{'id': 'L2-001', 'score': 0.85, 'content': 'Doc A'},
         {'id': 'L2-002', 'score': 0.75, 'content': 'Doc B'}]
    """
    seen_ids = set()
    unique_results = []

    # Sort by score descending to ensure we keep the highest-scoring instance
    for result in sorted(search_results, key=lambda r: r["score"], reverse=True):
        if result["id"] not in seen_ids:
            unique_results.append(result)
            seen_ids.add(result["id"])

    return unique_results


def merge_rrf_scores(results_list: List[List[Dict]], k: int = 60) -> List[Dict]:
    """
    Merge multiple search result lists using Reciprocal Rank Fusion (RRF).

    RRF is a robust rank aggregation method that combines results from multiple
    queries into a single ranked list. It's particularly effective for query
    expansion, where semantic variants may rank documents differently.

    Formula: RRF_score(doc) = Σ 1/(k + rank_i)
    where k is a constant (default 60, standard in literature) and rank_i is
    the rank of the document in the i-th result list.

    Args:
        results_list: List of result lists from different queries.
                      Each result list contains dictionaries with 'id', 'score',
                      and other fields (content, source_ids, etc.).
        k: RRF constant (default 60). Higher values reduce the impact of rank
           differences. Standard value from literature is 60.

    Returns:
        Merged and re-ranked result list, sorted by RRF score descending.
        The returned dictionaries have updated 'score' fields containing RRF scores.

    Example:
        >>> query1_results = [
        ...     {'id': 'L2-001', 'score': 0.9, 'content': 'Doc A'},  # Rank 1
        ...     {'id': 'L2-002', 'score': 0.8, 'content': 'Doc B'},  # Rank 2
        ... ]
        >>> query2_results = [
        ...     {'id': 'L2-002', 'score': 0.85, 'content': 'Doc B'},  # Rank 1
        ...     {'id': 'L2-003', 'score': 0.75, 'content': 'Doc C'},  # Rank 2
        ... ]
        >>> merge_rrf_scores([query1_results, query2_results], k=60)
        # Doc B appears in both (rank 2 + rank 1): 1/61 + 1/61 = ~0.0328
        # Doc A appears in query1 (rank 1): 1/61 = ~0.0164
        # Doc C appears in query2 (rank 2): 1/62 = ~0.0161
        # Result: [Doc B (0.0328), Doc A (0.0164), Doc C (0.0161)]

    References:
        - Cormack, G. V., Clarke, C. L., & Büttcher, S. (2009).
          Reciprocal rank fusion outperforms condorcet and individual rank
          learning methods. SIGIR '09.
    """
    rrf_scores: Dict[str, Dict] = {}

    for results in results_list:
        for rank, result in enumerate(results, start=1):
            l2_id = result["id"]
            rrf_score = 1 / (k + rank)

            if l2_id in rrf_scores:
                # Document appears in multiple query results - accumulate scores
                rrf_scores[l2_id]["score"] += rrf_score
            else:
                # First occurrence of this document
                rrf_scores[l2_id] = {**result, "score": rrf_score}

    # Sort by RRF score descending
    merged = sorted(rrf_scores.values(), key=lambda r: r["score"], reverse=True)

    return merged


# Version Info
__version__ = "1.0.0"
__author__ = "Cognitive Memory Team"
__description__ = "Query expansion utilities for deduplication and RRF fusion"
