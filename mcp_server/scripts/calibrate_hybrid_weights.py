#!/usr/bin/env python3
"""
Hybrid Search Weight Calibration via Grid Search

Story 2.8: Optimize Hybrid Search weights (semantic vs. keyword) using Grid Search
to achieve Precision@5 >0.75 on Ground Truth Set.

Implementation:
- Grid: semantic={0.5, 0.6, 0.7, 0.8, 0.9}, keyword={0.5, 0.4, 0.3, 0.2, 0.1}
- Constraint: semantic + keyword = 1.0
- Metric: Precision@5 = (relevant_docs_in_top5) / 5
- Baseline: MEDRAG-Default (0.7, 0.3)

Note: This version uses MOCK DATA for infrastructure testing.
      Real calibration requires PostgreSQL connection and actual Ground Truth Set.
"""

import json
import random
from typing import List, Dict, Tuple
from datetime import datetime


# =============================================================================
# Configuration
# =============================================================================

MOCK_MODE = True  # Set to False when PostgreSQL connection available
MOCK_DATA_FILE = "/home/user/i-o/mcp_server/scripts/mock_ground_truth.json"

# Grid Search Parameters
SEMANTIC_WEIGHTS = [0.5, 0.6, 0.7, 0.8, 0.9]
KEYWORD_WEIGHTS = [0.5, 0.4, 0.3, 0.2, 0.1]

# MEDRAG Baseline
BASELINE_SEMANTIC = 0.7
BASELINE_KEYWORD = 0.3


# =============================================================================
# Mock Hybrid Search (for testing without DB connection)
# =============================================================================

def mock_hybrid_search(query: str, top_k: int, weights: Dict[str, float]) -> List[int]:
    """
    Simulate hybrid_search results for testing

    In production: Replace with actual hybrid_search tool call

    Args:
        query: Query text
        top_k: Number of results (default 5)
        weights: {"semantic": float, "keyword": float}

    Returns:
        List of L2 Insight IDs (top-k results)
    """
    # Simulate semantic vs keyword preference based on weights
    # Higher semantic weight → tend towards certain IDs
    # This creates *some* variation between weight combinations

    semantic_weight = weights.get("semantic", 0.7)

    # Generate mock results (1-30 are our mock L2 IDs)
    all_ids = list(range(1, 31))

    # Simulate semantic preference: higher weights favor lower IDs
    # (this is arbitrary but creates measurable differences)
    if semantic_weight > 0.7:
        # Semantic-heavy: prefer IDs 1-15
        candidate_pool = list(range(1, 16)) * 2 + list(range(16, 31))
    elif semantic_weight < 0.7:
        # Keyword-heavy: prefer IDs 16-30
        candidate_pool = list(range(1, 16)) + list(range(16, 31)) * 2
    else:
        # Balanced
        candidate_pool = all_ids

    # Sample top_k results
    random.seed(hash(query + str(semantic_weight)))  # Deterministic per query+weight
    results = random.sample(candidate_pool, min(top_k, len(set(candidate_pool))))

    return results[:top_k]


# =============================================================================
# Precision@5 Calculation
# =============================================================================

def calculate_precision_at_5(retrieved_ids: List[int], expected_docs: List[int]) -> float:
    """
    Calculate Precision@5 metric

    Formula: (number of relevant docs in top-5) / 5

    Args:
        retrieved_ids: Top-5 L2 Insight IDs from hybrid_search
        expected_docs: Ground truth relevant doc IDs

    Returns:
        Float 0.0-1.0 (0.0 = no matches, 1.0 = all 5 relevant)
    """
    top_5 = retrieved_ids[:5]
    relevant_count = len(set(top_5) & set(expected_docs))
    return relevant_count / 5.0


# =============================================================================
# Grid Search Engine
# =============================================================================

def load_ground_truth() -> List[Dict]:
    """Load Ground Truth Set (mock or real)"""
    if MOCK_MODE:
        print("📂 Loading MOCK Ground Truth Data...")
        with open(MOCK_DATA_FILE, 'r') as f:
            ground_truth = json.load(f)
        print(f"   ✅ Loaded {len(ground_truth)} mock queries\n")
        return ground_truth
    else:
        # TODO: Replace with actual PostgreSQL query
        # cursor.execute("SELECT query, expected_docs FROM ground_truth WHERE expected_docs IS NOT NULL")
        # return cursor.fetchall()
        raise NotImplementedError("PostgreSQL connection not available in this environment")


def run_grid_search(ground_truth: List[Dict]) -> List[Dict]:
    """
    Execute Grid Search over all weight combinations

    Returns:
        List of results: {"semantic": float, "keyword": float, "precision_at_5": float}
    """
    results = []

    print("🔍 Starting Grid Search...")
    print(f"   Combinations to test: {len(SEMANTIC_WEIGHTS)}")
    print(f"   Queries per combination: {len(ground_truth)}")
    print(f"   Total hybrid_search calls: {len(SEMANTIC_WEIGHTS) * len(ground_truth)}\n")

    # Iterate over all weight combinations
    for idx, (sem, kw) in enumerate(zip(SEMANTIC_WEIGHTS, KEYWORD_WEIGHTS)):
        print(f"⚙️  Testing combination {idx+1}/{len(SEMANTIC_WEIGHTS)}: semantic={sem}, keyword={kw}")

        weights = {"semantic": sem, "keyword": kw}
        precision_scores = []

        # Test on all ground truth queries
        for query_data in ground_truth:
            query = query_data["query"]
            expected_docs = query_data["expected_docs"]

            # Run hybrid search (mock or real)
            if MOCK_MODE:
                retrieved_ids = mock_hybrid_search(query, top_k=5, weights=weights)
            else:
                # TODO: Replace with actual hybrid_search tool call
                # from mcp_server.tools import hybrid_search
                # results = hybrid_search(query_text=query, top_k=5, weights=weights)
                # retrieved_ids = [r['id'] for r in results]
                raise NotImplementedError("Real hybrid_search requires PostgreSQL connection")

            # Calculate Precision@5
            precision = calculate_precision_at_5(retrieved_ids, expected_docs)
            precision_scores.append(precision)

        # Calculate Macro-Average Precision@5
        macro_avg_precision = sum(precision_scores) / len(precision_scores)

        results.append({
            "semantic": sem,
            "keyword": kw,
            "precision_at_5": macro_avg_precision
        })

        print(f"   ✅ Precision@5: {macro_avg_precision:.4f}\n")

    return results


def analyze_results(results: List[Dict]) -> Dict:
    """Analyze Grid Search results and identify best weights"""

    # Sort by Precision@5 (descending)
    sorted_results = sorted(results, key=lambda x: x["precision_at_5"], reverse=True)

    best = sorted_results[0]
    baseline = next((r for r in results if r["semantic"] == BASELINE_SEMANTIC), results[0])

    # Calculate uplift
    uplift = (best["precision_at_5"] - baseline["precision_at_5"]) / baseline["precision_at_5"]
    uplift_percentage = uplift * 100

    analysis = {
        "best_weights": best,
        "baseline_weights": baseline,
        "uplift": uplift,
        "uplift_percentage": uplift_percentage,
        "all_results": sorted_results
    }

    return analysis


# =============================================================================
# Main Execution
# =============================================================================

def main():
    print("=" * 70)
    print("  Hybrid Search Weight Calibration via Grid Search")
    print("  Story 2.8: Optimize semantic vs. keyword weights")
    print("=" * 70)
    print()

    if MOCK_MODE:
        print("⚠️  MOCK MODE: Using synthetic data for infrastructure testing")
        print("   Real calibration requires PostgreSQL connection and Ground Truth Set\n")

    # Step 1: Load Ground Truth Set
    ground_truth = load_ground_truth()

    if len(ground_truth) < 50:
        print(f"❌ ERROR: Ground Truth Set has only {len(ground_truth)} queries")
        print(f"   Minimum 50 queries required for statistical robustness (AC-2.8.1)")
        return

    # Step 2: Run Grid Search
    results = run_grid_search(ground_truth)

    # Step 3: Analyze Results
    analysis = analyze_results(results)

    # Step 4: Display Results
    print("=" * 70)
    print("  GRID SEARCH RESULTS")
    print("=" * 70)
    print()
    print("📊 All Combinations (sorted by Precision@5):")
    print()
    print("  Semantic  Keyword  Precision@5")
    print("  " + "-" * 40)
    for r in analysis["all_results"]:
        marker = "⭐" if r == analysis["best_weights"] else "  "
        baseline_marker = "[BASELINE]" if r == analysis["baseline_weights"] else ""
        print(f"  {marker} {r['semantic']:.1f}      {r['keyword']:.1f}     {r['precision_at_5']:.4f}  {baseline_marker}")
    print()

    best = analysis["best_weights"]
    baseline = analysis["baseline_weights"]

    print("=" * 70)
    print("  CALIBRATION SUMMARY")
    print("=" * 70)
    print()
    print(f"🏆 Best Weights:")
    print(f"   Semantic: {best['semantic']}")
    print(f"   Keyword:  {best['keyword']}")
    print(f"   Precision@5: {best['precision_at_5']:.4f}")
    print()
    print(f"📍 Baseline (MEDRAG-Default):")
    print(f"   Semantic: {baseline['semantic']}")
    print(f"   Keyword:  {baseline['keyword']}")
    print(f"   Precision@5: {baseline['precision_at_5']:.4f}")
    print()
    print(f"📈 Uplift:")
    print(f"   Absolute: +{(best['precision_at_5'] - baseline['precision_at_5']):.4f}")
    print(f"   Relative: {analysis['uplift_percentage']:+.1f}%")
    print()

    # Success criteria check
    print("=" * 70)
    print("  ACCEPTANCE CRITERIA VALIDATION")
    print("=" * 70)
    print()

    ac_2_8_3 = best["precision_at_5"] >= 0.70
    ac_2_8_4 = analysis["uplift_percentage"] >= 5.0
    story_2_9_ready = best["precision_at_5"] >= 0.75

    print(f"✅ AC-2.8.3: Best Precision@5 ≥0.70: {'PASS' if ac_2_8_3 else 'FAIL'} ({best['precision_at_5']:.4f})")
    print(f"✅ AC-2.8.4: Uplift ≥+5%: {'PASS' if ac_2_8_4 else 'FAIL'} ({analysis['uplift_percentage']:+.1f}%)")
    print(f"{'✅' if story_2_9_ready else '⚠️ '} Story 2.9 Ready (Precision@5 ≥0.75): {'YES' if story_2_9_ready else 'NO'} ({best['precision_at_5']:.4f})")
    print()

    # Save results to JSON
    output_file = "/home/user/i-o/mcp_server/scripts/calibration_results.json"
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "mock_mode": MOCK_MODE,
        "ground_truth_size": len(ground_truth),
        "best_weights": best,
        "baseline_weights": baseline,
        "uplift_percentage": analysis["uplift_percentage"],
        "all_results": analysis["all_results"],
        "acceptance_criteria": {
            "ac_2_8_3_precision_gte_070": ac_2_8_3,
            "ac_2_8_4_uplift_gte_5pct": ac_2_8_4,
            "story_2_9_ready_precision_gte_075": story_2_9_ready
        }
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"💾 Results saved to: {output_file}")
    print()

    if MOCK_MODE:
        print("⚠️  REMINDER: These results are based on MOCK DATA")
        print("   Re-run with real Ground Truth Set for production calibration")

    return analysis


if __name__ == "__main__":
    main()
