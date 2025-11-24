#!/usr/bin/env python3
"""
Generate Mock Ground Truth Data for Grid Search Testing

Note: This is MOCK DATA for infrastructure testing only.
Real Ground Truth Set requires  (Ground Truth Collection UI).

Generated: 100 mock queries with synthetic expected_docs
"""

import random
import json

def generate_mock_ground_truth(num_queries=100):
    """Generate mock ground truth queries with expected L2 IDs"""

    # Mock query templates (stratified: 40% short, 40% medium, 20% long)
    short_queries = [
        "Was ist Bewusstsein?",
        "Wie funktioniert Denken?",
        "Was bedeutet Intelligenz?",
        "Warum träumen wir?",
        "Was ist Kreativität?",
        "Wie lernen wir?",
        "Was ist Gedächtnis?",
        "Warum vergessen wir?",
        "Was ist Emotion?",
        "Wie entsteht Sprache?",
    ]

    medium_queries = [
        "Wie hängen Bewusstsein und Selbstwahrnehmung zusammen?",
        "Welche Rolle spielt das Gedächtnis beim Lernen?",
        "Wie unterscheidet sich künstliche von natürlicher Intelligenz?",
        "Warum sind Träume oft so bizarr und unlogisch?",
        "Wie beeinflusst Kreativität die Problemlösungsfähigkeit?",
        "Welche kognitiven Prozesse sind beim Spracherwerb beteiligt?",
        "Wie funktioniert semantisches vs. episodisches Gedächtnis?",
        "Warum haben Emotionen Einfluss auf Entscheidungen?",
        "Wie entwickelt sich abstraktes Denken im Kindesalter?",
        "Welche neuronalen Mechanismen liegen der Aufmerksamkeit zugrunde?",
    ]

    long_queries = [
        "Wie kann man das Hard Problem of Consciousness philosophisch und neurowissenschaftlich angehen?",
        "Welche evolutionären Vorteile bietet Bewusstsein und warum hat es sich entwickelt?",
        "Wie unterscheiden sich verschiedene Gedächtnistheorien in ihrer Erklärung von Vergessen?",
        "Warum ist der Turing-Test als Maß für maschinelle Intelligenz umstritten?",
        "Welche Rolle spielen Emotionen in der rationalen Entscheidungsfindung nach Damasio?",
    ]

    ground_truth = []

    # Generate queries (stratified distribution)
    query_id = 1

    # 40% short queries
    for _ in range(40):
        query = random.choice(short_queries)
        expected_docs = random.sample(range(1, 31), k=random.randint(1, 3))  # 1-3 docs
        ground_truth.append({
            "id": query_id,
            "query": query,
            "expected_docs": expected_docs,
            "query_type": "short"
        })
        query_id += 1

    # 40% medium queries
    for _ in range(40):
        query = random.choice(medium_queries)
        expected_docs = random.sample(range(1, 31), k=random.randint(2, 4))  # 2-4 docs
        ground_truth.append({
            "id": query_id,
            "query": query,
            "expected_docs": expected_docs,
            "query_type": "medium"
        })
        query_id += 1

    # 20% long queries
    for _ in range(20):
        query = random.choice(long_queries)
        expected_docs = random.sample(range(1, 31), k=random.randint(3, 5))  # 3-5 docs
        ground_truth.append({
            "id": query_id,
            "query": query,
            "expected_docs": expected_docs,
            "query_type": "long"
        })
        query_id += 1

    return ground_truth


if __name__ == "__main__":
    # Generate mock data
    ground_truth = generate_mock_ground_truth(100)

    # Save to JSON file
    output_file = "/home/user/i-o/mcp_server/scripts/mock_ground_truth.json"
    with open(output_file, 'w') as f:
        json.dump(ground_truth, f, indent=2, ensure_ascii=False)

    print(f"✅ Generated {len(ground_truth)} mock ground truth queries")
    print(f"   Saved to: {output_file}")
    print(f"\n📊 Distribution:")
    print(f"   Short queries (1-3 docs): {sum(1 for q in ground_truth if q['query_type'] == 'short')}")
    print(f"   Medium queries (2-4 docs): {sum(1 for q in ground_truth if q['query_type'] == 'medium')}")
    print(f"   Long queries (3-5 docs): {sum(1 for q in ground_truth if q['query_type'] == 'long')}")
    print(f"\n⚠️  NOTE: This is MOCK DATA for infrastructure testing only!")
    print(f"   Real calibration requires actual Ground Truth Set from ")
