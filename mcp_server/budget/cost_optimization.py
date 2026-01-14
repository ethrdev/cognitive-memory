"""
Cost Optimization Insights Module

Analyzes API cost patterns and provides recommendations for cost reduction
while maintaining system performance and quality.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from mcp_server.budget.budget_monitor import get_monthly_cost_by_api
from mcp_server.config import get_config

logger = logging.getLogger(__name__)


def get_cost_breakdown_insights() -> Dict[str, Any]:
    """
    Analyze monthly cost breakdown and identify expensive APIs.

    Returns:
        Dict with:
        - breakdown: List[Dict] (API-wise cost breakdown)
        - most_expensive: str (API with highest cost)
        - cost_distribution: Dict[str, float] (percentage distribution)
        - total_cost: float (total monthly cost)

    Example:
        >>> insights = get_cost_breakdown_insights()
        >>> print(f"Most expensive: {insights['most_expensive']}")
        >>> for api, pct in insights['cost_distribution'].items():
        ...     print(f"{api}: {pct:.1f}%")
    """
    breakdown = get_monthly_cost_by_api()

    if not breakdown:
        return {
            "breakdown": [],
            "most_expensive": None,
            "cost_distribution": {},
            "total_cost": 0.0,
        }

    # Calculate total cost
    total_cost = sum(api["total_cost"] for api in breakdown)

    # Calculate percentage distribution
    cost_distribution = {}
    for api in breakdown:
        if total_cost > 0:
            pct = (api["total_cost"] / total_cost) * 100.0
            cost_distribution[api["api_name"]] = pct

    # Identify most expensive
    most_expensive = breakdown[0]["api_name"] if breakdown else None

    return {
        "breakdown": breakdown,
        "most_expensive": most_expensive,
        "cost_distribution": cost_distribution,
        "total_cost": total_cost,
    }


def get_optimization_recommendations() -> List[Dict[str, Any]]:
    """
    Generate cost optimization recommendations based on current usage patterns.

    Analyzes:
    - Query Expansion (): num_variants configuration
    - Dual Judge (): staged_dual_judge configuration
    - Embedding batch sizes and caching opportunities

    Returns:
        List of recommendation dicts with:
        - category: str (e.g., 'query_expansion', 'dual_judge')
        - current_config: Dict (current configuration)
        - recommendation: str (what to change)
        - estimated_savings_pct: float (estimated cost reduction %)
        - estimated_savings_eur: float (estimated monthly savings in EUR)
        - impact: str ('low', 'medium', 'high')
        - trade_off: str (what you lose by implementing this)

    Example:
        >>> recommendations = get_optimization_recommendations()
        >>> for rec in recommendations:
        ...     print(f"{rec['category']}: {rec['recommendation']}")
        ...     print(f"  Savings: €{rec['estimated_savings_eur']:.2f}/mo ({rec['estimated_savings_pct']:.0f}%)")
        ...     print(f"  Trade-off: {rec['trade_off']}")
    """
    recommendations = []

    # Get current configuration
    try:
        config = get_config()
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")
        return recommendations

    # Get cost breakdown
    insights = get_cost_breakdown_insights()
    total_cost = insights["total_cost"]
    breakdown = insights["breakdown"]

    # Calculate embeddings cost
    embeddings_cost = next(
        (api["total_cost"] for api in breakdown if api["api_name"] == "openai_embeddings"),
        0.0
    )

    # Recommendation 1: Query Expansion Variants
    query_expansion = config.get("memory", {}).get("query_expansion", {})
    num_variants = query_expansion.get("num_variants", 3)

    if num_variants > 2 and embeddings_cost > 0:
        # Reducing from 3 variants to 2 saves ~25% of embedding costs
        # (4 queries → 3 queries = 25% reduction)
        estimated_savings_eur = embeddings_cost * 0.25
        estimated_savings_pct = (estimated_savings_eur / total_cost * 100.0) if total_cost > 0 else 0.0

        recommendations.append({
            "category": "query_expansion",
            "current_config": {
                "num_variants": num_variants,
                "total_queries": num_variants + 1,  # variants + original
            },
            "recommendation": f"Reduce query_expansion.num_variants from {num_variants} to 2",
            "estimated_savings_pct": estimated_savings_pct,
            "estimated_savings_eur": estimated_savings_eur,
            "impact": "medium" if estimated_savings_pct > 5 else "low",
            "trade_off": "~5% recall reduction (from : 3 variants = +15% recall, 2 variants = +10% recall)",
        })

    # Recommendation 2: Staged Dual Judge Transition
    staged_dual_judge = config.get("staged_dual_judge", {})
    dual_judge_enabled = staged_dual_judge.get("dual_judge_enabled", True)

    # Calculate dual judge costs
    gpt4o_cost = next(
        (api["total_cost"] for api in breakdown if api["api_name"] == "gpt4o_judge"),
        0.0
    )
    haiku_judge_cost = next(
        (api["total_cost"] for api in breakdown if api["api_name"] == "haiku_judge"),
        0.0
    )
    dual_judge_cost = gpt4o_cost + haiku_judge_cost

    if dual_judge_enabled and haiku_judge_cost > 0:
        # Transition to Single Judge Mode ( Enhancement E8)
        # Saves ~95% of Haiku judge costs (only 5% spot checks remain)
        estimated_savings_eur = haiku_judge_cost * 0.95
        estimated_savings_pct = (estimated_savings_eur / total_cost * 100.0) if total_cost > 0 else 0.0

        recommendations.append({
            "category": "dual_judge",
            "current_config": {
                "dual_judge_enabled": True,
                "mode": "Full Dual Judge",
            },
            "recommendation": "Transition to Single Judge Mode (set staged_dual_judge.dual_judge_enabled=false)",
            "estimated_savings_pct": estimated_savings_pct,
            "estimated_savings_eur": estimated_savings_eur,
            "impact": "high" if estimated_savings_pct > 10 else "medium",
            "trade_off": (
                "Requires Kappa ≥ 0.85 for safe transition. "
                "Maintains 5% spot checks for quality monitoring. "
                "Expected from : -40% budget reduction (€7.50 → €2.50/mo)"
            ),
        })

    # Recommendation 3: Reduce Evaluation/Reflexion Frequency
    haiku_eval_cost = next(
        (api["total_cost"] for api in breakdown if api["api_name"] == "haiku_eval"),
        0.0
    )
    haiku_refl_cost = next(
        (api["total_cost"] for api in breakdown if api["api_name"] == "haiku_reflexion"),
        0.0
    )
    total_eval_cost = haiku_eval_cost + haiku_refl_cost

    if total_eval_cost > total_cost * 0.20:  # If eval/refl >20% of total cost
        # Reduce reflexion trigger threshold or evaluation frequency
        estimated_savings_eur = total_eval_cost * 0.30  # 30% reduction
        estimated_savings_pct = (estimated_savings_eur / total_cost * 100.0) if total_cost > 0 else 0.0

        recommendations.append({
            "category": "evaluation",
            "current_config": {
                "reward_threshold": config.get("memory", {}).get("evaluation", {}).get("reward_threshold", 0.3),
                "eval_cost_pct": (total_eval_cost / total_cost * 100.0) if total_cost > 0 else 0.0,
            },
            "recommendation": "Increase evaluation.reward_threshold from 0.3 to 0.2 (fewer reflexions)",
            "estimated_savings_pct": estimated_savings_pct,
            "estimated_savings_eur": estimated_savings_eur,
            "impact": "medium",
            "trade_off": (
                "Fewer reflexions = less verbalized learning from failed evaluations. "
                "May slow system improvement over time. "
                "Threshold 0.2 triggers reflexion for scores <0.2 (vs <0.3 currently)"
            ),
        })

    # Recommendation 4: Semantic Weight Optimization
    semantic_weight = config.get("memory", {}).get("semantic_weight", 0.7)

    if semantic_weight > 0.5 and embeddings_cost > 0:
        # Reducing semantic weight reduces reliance on embeddings (can reduce embedding calls)
        # This is a marginal optimization
        estimated_savings_eur = embeddings_cost * 0.10  # 10% reduction
        estimated_savings_pct = (estimated_savings_eur / total_cost * 100.0) if total_cost > 0 else 0.0

        recommendations.append({
            "category": "hybrid_search",
            "current_config": {
                "semantic_weight": semantic_weight,
                "keyword_weight": config.get("memory", {}).get("keyword_weight", 0.3),
            },
            "recommendation": f"Adjust semantic_weight from {semantic_weight} to 0.5 (balanced hybrid search)",
            "estimated_savings_pct": estimated_savings_pct,
            "estimated_savings_eur": estimated_savings_eur,
            "impact": "low",
            "trade_off": (
                "Lower semantic weight may reduce recall for semantically similar queries. "
                "Requires re-calibration via grid search (). "
                "Marginal cost savings, mainly impacts search quality"
            ),
        })

    # Sort by estimated savings (descending)
    recommendations.sort(key=lambda x: x["estimated_savings_eur"], reverse=True)

    return recommendations


def calculate_potential_savings() -> Dict[str, Any]:
    """
    Calculate total potential savings from all optimization recommendations.

    Returns:
        Dict with:
        - current_monthly_cost: float (current monthly cost)
        - total_potential_savings: float (sum of all recommendations)
        - optimized_monthly_cost: float (cost after optimizations)
        - savings_pct: float (percentage savings)
        - recommendations_count: int (number of recommendations)
        - top_recommendation: Dict (highest-impact recommendation)

    Example:
        >>> savings = calculate_potential_savings()
        >>> print(f"Current: €{savings['current_monthly_cost']:.2f}")
        >>> print(f"Potential savings: €{savings['total_potential_savings']:.2f} ({savings['savings_pct']:.1f}%)")
        >>> print(f"Optimized cost: €{savings['optimized_monthly_cost']:.2f}")
    """
    insights = get_cost_breakdown_insights()
    current_cost = insights["total_cost"]

    recommendations = get_optimization_recommendations()

    if not recommendations:
        return {
            "current_monthly_cost": current_cost,
            "total_potential_savings": 0.0,
            "optimized_monthly_cost": current_cost,
            "savings_pct": 0.0,
            "recommendations_count": 0,
            "top_recommendation": None,
        }

    # Sum potential savings (note: assumes non-overlapping savings)
    total_potential_savings = sum(rec["estimated_savings_eur"] for rec in recommendations)

    # Calculate optimized cost
    optimized_cost = max(0.0, current_cost - total_potential_savings)

    # Calculate percentage savings
    savings_pct = (total_potential_savings / current_cost * 100.0) if current_cost > 0 else 0.0

    # Get top recommendation
    top_recommendation = recommendations[0] if recommendations else None

    return {
        "current_monthly_cost": current_cost,
        "total_potential_savings": total_potential_savings,
        "optimized_monthly_cost": optimized_cost,
        "savings_pct": savings_pct,
        "recommendations_count": len(recommendations),
        "top_recommendation": top_recommendation,
    }


def validate_staged_dual_judge_transition() -> Dict[str, Any]:
    """
    Validate if Staged Dual Judge transition is safe ( Enhancement E8).

    Checks:
    - Cohen's Kappa ≥ 0.85 ("Almost Perfect Agreement")
    - Sufficient ground truth data for reliable Kappa calculation
    - Current dual_judge_enabled status

    Returns:
        Dict with:
        - transition_ready: bool (True if safe to transition)
        - current_kappa: float (current Cohen's Kappa score)
        - kappa_threshold: float (required threshold, default 0.85)
        - ground_truth_count: int (number of ground truth evaluations)
        - current_mode: str ('dual_judge' or 'single_judge')
        - recommendation: str (action to take)

    Example:
        >>> validation = validate_staged_dual_judge_transition()
        >>> if validation['transition_ready']:
        ...     print("✓ Safe to transition to Single Judge Mode")
        ...     print(f"  Kappa: {validation['current_kappa']:.3f} ≥ {validation['kappa_threshold']:.3f}")
        ... else:
        ...     print("✗ Not ready for transition")
        ...     print(f"  {validation['recommendation']}")
    """
    from mcp_server.db.connection import get_connection_sync

    # Get configuration
    try:
        config = get_config()
        staged_dual_judge = config.get("staged_dual_judge", {})
        dual_judge_enabled = staged_dual_judge.get("dual_judge_enabled", True)
        kappa_threshold = staged_dual_judge.get("kappa_threshold", 0.85)
    except Exception as e:
        logger.warning(f"Failed to load config: {e}")
        dual_judge_enabled = True
        kappa_threshold = 0.85

    # Query ground truth data for Kappa scores
    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            # Get average Kappa from recent ground truth evaluations
            cursor.execute("""
                SELECT
                    COUNT(*) as evaluation_count,
                    AVG(kappa) as avg_kappa,
                    MIN(kappa) as min_kappa,
                    MAX(kappa) as max_kappa
                FROM ground_truth
                WHERE kappa IS NOT NULL
                  AND created_at >= NOW() - INTERVAL '30 days'
            """)

            row = cursor.fetchone()

            if row and row[0] > 0:
                ground_truth_count = int(row[0])
                avg_kappa = float(row[1]) if row[1] is not None else 0.0
                min_kappa = float(row[2]) if row[2] is not None else 0.0
                max_kappa = float(row[3]) if row[3] is not None else 0.0
            else:
                ground_truth_count = 0
                avg_kappa = 0.0
                min_kappa = 0.0
                max_kappa = 0.0

    except Exception as e:
        logger.error(f"Failed to query ground truth data: {e}")
        ground_truth_count = 0
        avg_kappa = 0.0
        min_kappa = 0.0
        max_kappa = 0.0

    # Determine if transition is ready
    transition_ready = (
        dual_judge_enabled
        and avg_kappa >= kappa_threshold
        and ground_truth_count >= 10  # Minimum 10 evaluations for reliability
    )

    # Generate recommendation
    if not dual_judge_enabled:
        recommendation = "Already in Single Judge Mode (staged_dual_judge.dual_judge_enabled=false)"
    elif avg_kappa >= kappa_threshold and ground_truth_count >= 10:
        recommendation = (
            f"✓ READY FOR TRANSITION: Kappa {avg_kappa:.3f} ≥ {kappa_threshold:.3f} "
            f"with {ground_truth_count} evaluations. "
            f"Set staged_dual_judge.dual_judge_enabled=false to transition to Single Judge Mode."
        )
    elif ground_truth_count < 10:
        recommendation = (
            f"Need more ground truth data ({ground_truth_count}/10 evaluations). "
            f"Collect at least 10 dual judge evaluations before transition."
        )
    else:
        recommendation = (
            f"Kappa too low ({avg_kappa:.3f} < {kappa_threshold:.3f}). "
            f"Continue with Dual Judge Mode until agreement improves."
        )

    return {
        "transition_ready": transition_ready,
        "current_kappa": avg_kappa,
        "kappa_threshold": kappa_threshold,
        "kappa_range": {"min": min_kappa, "max": max_kappa},
        "ground_truth_count": ground_truth_count,
        "current_mode": "single_judge" if not dual_judge_enabled else "dual_judge",
        "recommendation": recommendation,
    }
