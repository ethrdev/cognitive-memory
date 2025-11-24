"""
Manual Test Script for : Self-Evaluation mit Haiku API

This script tests:
1. High-quality answer (reward >0.7)
2. Medium-quality answer (reward 0.3-0.7)
3. Low-quality answer (reward <0.3)
4. Database logging validation
5. Reflexion trigger logic

Prerequisites:
- ANTHROPIC_API_KEY environment variable set
- DATABASE_URL environment variable set
- PostgreSQL database running with migrations applied

Run with:
    python tests/manual/test_evaluation_story_2_5.py
"""

import asyncio
import os
from datetime import datetime

from mcp_server.external.anthropic_client import HaikuClient
from mcp_server.utils.reflexion_utils import (
    get_reward_threshold,
    should_trigger_reflection,
)
from mcp_server.db.evaluation_logger import (
    get_recent_evaluations,
    get_evaluation_stats,
)


async def test_high_quality_answer():
    """
    Test 1: High-quality answer (reward >0.7 expected)

    Tests evaluation with a query that has excellent context match
    and a complete, accurate answer.
    """
    print("\n" + "=" * 80)
    print("TEST 1: High-Quality Answer (Reward >0.7 Expected)")
    print("=" * 80)

    client = HaikuClient()

    query = "What is the capital of France?"
    context = [
        "France is a country in Western Europe with several overseas regions and territories.",
        "Paris is the capital and most populous city of France, located in the north-central part of the country.",
        "Paris has been one of Europe's major centres of finance, diplomacy, commerce, fashion, science, and arts since the 17th century.",
        "The City of Paris is the centre and seat of government of the Île-de-France region.",
        "Paris is known for its museums and architectural landmarks such as the Eiffel Tower and Notre-Dame Cathedral.",
    ]
    answer = (
        "The capital of France is Paris. Paris is located in north-central France and has been "
        "a major European center of culture, commerce, and government for centuries. It is the "
        "most populous city in France and serves as the seat of government for the Île-de-France region."
    )

    print(f"\n📝 Query: {query}")
    print(f"📚 Context: {len(context)} documents")
    print(f"💬 Answer: {answer[:100]}...")

    result = await client.evaluate_answer(query=query, context=context, answer=answer)

    reward_score = result["reward_score"]
    reasoning = result["reasoning"]
    token_count = result["token_count"]
    cost = result["cost_eur"]

    print(f"\n✅ EVALUATION RESULTS:")
    print(f"   Reward Score: {reward_score:.3f}")
    print(f"   Reasoning: {reasoning}")
    print(f"   Token Count: {token_count}")
    print(f"   Cost: €{cost:.6f}")

    # Check if reflexion should be triggered
    trigger = should_trigger_reflection(reward_score)
    threshold = get_reward_threshold()
    print(f"\n🔍 REFLEXION TRIGGER:")
    print(f"   Threshold: {threshold}")
    print(f"   Triggered: {trigger}")

    # Assertions
    if reward_score >= 0.7:
        print(f"\n✅ PASS: Reward score {reward_score:.3f} >= 0.7 (high quality)")
    else:
        print(
            f"\n⚠️ WARNING: Reward score {reward_score:.3f} < 0.7 (expected high quality)"
        )

    if not trigger:
        print("✅ PASS: Reflexion not triggered (as expected for high quality)")
    else:
        print("⚠️ WARNING: Reflexion triggered unexpectedly")

    return result


async def test_medium_quality_answer():
    """
    Test 2: Medium-quality answer (reward 0.3-0.7 expected)

    Tests evaluation with a partially relevant answer that has some gaps.
    """
    print("\n" + "=" * 80)
    print("TEST 2: Medium-Quality Answer (Reward 0.3-0.7 Expected)")
    print("=" * 80)

    client = HaikuClient()

    query = "Explain the concept of consciousness"
    context = [
        "Consciousness refers to the state of being awake and aware of one's surroundings.",
        "Philosophers have debated the nature of consciousness for centuries.",
        "The hard problem of consciousness concerns how physical processes give rise to subjective experience.",
        "Neuroscientists study brain activity to understand consciousness.",
        "Some theories suggest consciousness emerges from complex information processing.",
    ]
    answer = (
        "Consciousness is being aware of your surroundings. It's related to brain activity "
        "and has been studied by scientists and philosophers."
    )

    print(f"\n📝 Query: {query}")
    print(f"📚 Context: {len(context)} documents")
    print(f"💬 Answer: {answer}")

    result = await client.evaluate_answer(query=query, context=context, answer=answer)

    reward_score = result["reward_score"]
    reasoning = result["reasoning"]
    token_count = result["token_count"]
    cost = result["cost_eur"]

    print(f"\n📊 EVALUATION RESULTS:")
    print(f"   Reward Score: {reward_score:.3f}")
    print(f"   Reasoning: {reasoning}")
    print(f"   Token Count: {token_count}")
    print(f"   Cost: €{cost:.6f}")

    trigger = should_trigger_reflection(reward_score)
    threshold = get_reward_threshold()
    print(f"\n🔍 REFLEXION TRIGGER:")
    print(f"   Threshold: {threshold}")
    print(f"   Triggered: {trigger}")

    if 0.3 <= reward_score <= 0.7:
        print(
            f"\n✅ PASS: Reward score {reward_score:.3f} in range 0.3-0.7 (medium quality)"
        )
    else:
        print(
            f"\n⚠️ WARNING: Reward score {reward_score:.3f} outside expected range 0.3-0.7"
        )

    return result


async def test_low_quality_answer():
    """
    Test 3: Low-quality answer (reward <0.3 expected)

    Tests evaluation with an irrelevant or poor answer that should trigger reflexion.
    """
    print("\n" + "=" * 80)
    print("TEST 3: Low-Quality Answer (Reward <0.3 Expected)")
    print("=" * 80)

    client = HaikuClient()

    query = "What are the economic implications of climate change?"
    context = [
        "Climate change affects global weather patterns and ecosystems.",
        "Rising temperatures impact agricultural productivity.",
        "Coastal regions face increased flooding risks from sea level rise.",
        "Extreme weather events cause billions in economic damages.",
        "Transitioning to renewable energy requires significant investment.",
    ]
    answer = "I like pizza."

    print(f"\n📝 Query: {query}")
    print(f"📚 Context: {len(context)} documents")
    print(f"💬 Answer: {answer}")

    result = await client.evaluate_answer(query=query, context=context, answer=answer)

    reward_score = result["reward_score"]
    reasoning = result["reasoning"]
    token_count = result["token_count"]
    cost = result["cost_eur"]

    print(f"\n📊 EVALUATION RESULTS:")
    print(f"   Reward Score: {reward_score:.3f}")
    print(f"   Reasoning: {reasoning}")
    print(f"   Token Count: {token_count}")
    print(f"   Cost: €{cost:.6f}")

    trigger = should_trigger_reflection(reward_score)
    threshold = get_reward_threshold()
    print(f"\n🔍 REFLEXION TRIGGER:")
    print(f"   Threshold: {threshold}")
    print(f"   Triggered: {trigger}")

    if reward_score < 0.3:
        print(f"\n✅ PASS: Reward score {reward_score:.3f} < 0.3 (low quality)")
    else:
        print(
            f"\n⚠️ WARNING: Reward score {reward_score:.3f} >= 0.3 (expected low quality)"
        )

    if trigger:
        print("✅ PASS: Reflexion triggered (as expected for low quality)")
    else:
        print("⚠️ WARNING: Reflexion NOT triggered (expected for low quality)")

    return result


async def test_database_logging():
    """
    Test 4: Database logging validation

    Verifies that evaluations are properly logged to PostgreSQL.
    """
    print("\n" + "=" * 80)
    print("TEST 4: Database Logging Validation")
    print("=" * 80)

    # Get recent evaluations
    recent = await get_recent_evaluations(limit=5)

    print(f"\n📊 Recent Evaluations (last 5):")
    for i, eval_data in enumerate(recent, 1):
        print(f"\n{i}. ID: {eval_data['id']}")
        print(f"   Timestamp: {eval_data['timestamp']}")
        print(f"   Query: {eval_data['query'][:50]}...")
        print(f"   Reward: {eval_data['reward_score']:.3f}")
        print(f"   Cost: €{eval_data['cost_eur']:.6f}")

    if len(recent) > 0:
        print(f"\n✅ PASS: Found {len(recent)} evaluations in database")
    else:
        print("\n⚠️ WARNING: No evaluations found in database")

    # Get evaluation statistics
    stats = await get_evaluation_stats(days=1)

    print(f"\n📈 Evaluation Statistics (last 24 hours):")
    print(f"   Total Evaluations: {stats['total_evaluations']}")
    print(f"   Average Reward: {stats['avg_reward']:.3f}")
    print(f"   Min Reward: {stats['min_reward']:.3f}")
    print(f"   Max Reward: {stats['max_reward']:.3f}")
    print(f"   Low Quality Count: {stats['low_quality_count']}")
    print(f"   Low Quality %: {stats['low_quality_pct']:.1f}%")
    print(f"   Total Cost: €{stats['total_cost']:.6f}")

    return stats


async def run_all_tests():
    """
    Run all manual tests for 
    """
    print("\n" + "=" * 80)
    print("STORY 2.5: SELF-EVALUATION MIT HAIKU API - MANUAL TESTS")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python Version: {os.sys.version}")

    # Check prerequisites
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("\n❌ ERROR: ANTHROPIC_API_KEY environment variable not set")
        return

    if not os.getenv("DATABASE_URL"):
        print("\n❌ ERROR: DATABASE_URL environment variable not set")
        return

    print("\n✅ Prerequisites: ANTHROPIC_API_KEY and DATABASE_URL configured")

    # Run tests
    try:
        result1 = await test_high_quality_answer()
        result2 = await test_medium_quality_answer()
        result3 = await test_low_quality_answer()
        stats = await test_database_logging()

        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"\n✅ All tests completed successfully!")
        print(f"\nTotal evaluations run: 3")
        print(f"Total cost: €{result1['cost_eur'] + result2['cost_eur'] + result3['cost_eur']:.6f}")
        print(f"\nDatabase statistics:")
        print(f"  - Total evaluations logged: {stats['total_evaluations']}")
        print(f"  - Average reward score: {stats['avg_reward']:.3f}")
        print(f"  - Reflexion trigger rate: {stats['low_quality_pct']:.1f}%")

    except Exception as e:
        print(f"\n❌ ERROR: Test failed with exception: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
