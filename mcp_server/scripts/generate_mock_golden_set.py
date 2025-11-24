#!/usr/bin/env python3
"""
Generate Mock Golden Test Set Data

: Infrastructure validation with mock data before production deployment.

Generates:
- 100 mock queries with stratified distribution (40% Short, 40% Medium, 20% Long)
- Realistic German philosophical/psychological queries
- Expected_docs arrays (random L2 Insight IDs for infrastructure testing)
- Session IDs (different from Ground Truth to simulate no-overlap)

Output: mock_golden_test_set.json
"""

import json
import random
import uuid
from typing import List, Dict
from datetime import datetime


# =============================================================================
# Mock Query Templates (German Philosophical/Psychological Queries)
# =============================================================================

MOCK_QUERIES = {
    "short": [
        # ≤10 words (1-2 Sätze, einfache Fragen)
        "Was ist Bewusstsein?",
        "Wie funktioniert Denken?",
        "Was bedeutet Freiheit?",
        "Wie entsteht Kreativität?",
        "Was ist Identität?",
        "Wie lernen wir?",
        "Was ist Wahrnehmung?",
        "Wie entsteht Sprache?",
        "Was bedeutet Intelligenz?",
        "Wie funktioniert Gedächtnis?",
        "Was ist Emotion?",
        "Warum träumen wir?",
        "Was ist Zeit?",
        "Wie entsteht Bedeutung?",
        "Was ist Realität?",
        "Wie funktioniert Intuition?",
        "Was bedeutet Bewusstsein?",
        "Wie entsteht Motivation?",
        "Was ist Selbstwahrnehmung?",
        "Warum vergessen wir?",
    ],
    "medium": [
        # 11-29 words (3-5 Sätze, komplexere Fragen) - ADJUSTED for actual word count
        "Wie unterscheiden sich deklaratives und prozedurales Gedächtnis in ihrer neuronalen Basis und ihren Funktionen?",
        "Welche Rolle spielt das Unbewusste bei der Entscheidungsfindung nach modernen kognitiven Theorien der Psychologie?",
        "Wie hängen Bewusstsein und Selbstwahrnehmung zusammen und welche neuronalen Korrelate sind dafür verantwortlich in der modernen Forschung?",
        "Welche kognitiven Prozesse sind beim Spracherwerb beteiligt und wie unterscheiden sich nativistische von konstruktivistischen Theorien?",
        "Wie funktioniert semantisches im Vergleich zu episodischem Gedächtnis und welche Hirnregionen sind jeweils primär involviert?",
        "Warum haben Emotionen einen starken Einfluss auf rationale Entscheidungen und wie erklärt die Somatic Marker Hypothesis dies?",
        "Wie entwickelt sich abstraktes Denken im Kindesalter nach Piaget und welche neueren Erkenntnisse gibt es dazu?",
        "Welche neuronalen Mechanismen und Netzwerke liegen der selektiven Aufmerksamkeit zugrunde nach aktueller neurowissenschaftlicher Forschung?",
        "Wie unterscheidet sich künstliche von natürlicher Intelligenz bezüglich Flexibilität Kreativität und Kontextverständnis in der KI Forschung?",
        "Warum sind Träume oft so bizarr und unlogisch und welche Funktion könnte diese Bizarrerie haben nach modernen Schlafforschungstheorien?",
        "Wie beeinflusst Kreativität die Problemlösungsfähigkeit und welche kognitiven Prozesse sind bei kreativer Einsicht involviert nach Forschung?",
        "Welche zentrale Rolle spielt das Gedächtnis beim Lernen und wie interagieren Arbeitsgedächtnis und Langzeitgedächtnis dabei?",
        "Wie entsteht subjektive phänomenale Erfahrung aus rein neuronaler Aktivität und warum ist dies das Hard Problem?",
        "Welche evolutionären Vorteile könnte Bewusstsein bieten und warum hat es sich überhaupt entwickelt in der Evolution?",
        "Wie kann man das Hard Problem of Consciousness philosophisch und neurowissenschaftlich angehen und welche Theorien existieren?",
        "Warum ist der Turing-Test als Maß für maschinelle Intelligenz umstritten und welche Alternativen werden diskutiert?",
        "Wie unterscheiden sich verschiedene Gedächtnistheorien grundlegend in ihrer Erklärung von Vergessen und Gedächtnisverfall über Zeit?",
        "Welche zentrale Rolle spielen Emotionen in der rationalen Entscheidungsfindung nach Damasio und seiner Somatic Marker Theory?",
        "Wie funktioniert der komplexe Prozess der Bedeutungszuweisung in der Sprache nach semantischen und pragmatischen Theorien?",
        "Welche wichtigen kognitiven Verzerrungen und Heuristiken beeinflussen unser Urteilsvermögen systematisch nach Kahneman und Tversky?",
    ],
    "long": [
        # ≥30 words (6+ Sätze, sehr komplexe philosophische Fragen)
        "Wenn Bewusstsein aus neuronaler Aktivität emergiert, wie erklärt das die subjektive Qualität unserer Erfahrungen? Warum fühlt es sich auf eine bestimmte Weise an, rot zu sehen oder Schmerz zu empfinden, wenn diese Erfahrungen letztlich nur Muster elektrochemischer Prozesse im Gehirn sind?",
        "Wie können wir zwischen echtem Verständnis und bloßer Simulation unterscheiden? Wenn ein KI-System alle Verhaltenstests besteht und menschenähnliche Antworten gibt, bedeutet das, dass es tatsächlich versteht, oder führt es nur komplexe Musterverarbeitung durch ohne echte Bedeutungszuweisungen?",
        "Ist freier Wille mit Determinismus vereinbar? Wenn jede Handlung durch vorherige Zustände und Naturgesetze determiniert ist, können unsere Entscheidungen dann überhaupt frei sein, oder ist das Gefühl der Handlungsfreiheit nur eine nützliche Illusion, die unser Gehirn konstruiert?",
        "Welche Implikationen hat die Embodied Cognition Theorie für unser Verständnis von Intelligenz? Wenn Denken fundamental in körperlichen Erfahrungen verwurzelt ist, können dann nicht-verkörperte KI-Systeme jemals echtes Verständnis entwickeln, oder benötigen sie eine Form von Verkörperung für genuine kognitive Prozesse?",
        "Wie verändert sich Identität über Zeit wenn alle physischen und mentalen Komponenten einer Person graduell ersetzt werden? Ist Identität eine Illusion, eine narrative Konstruktion, oder gibt es einen kontinuierlichen Kern, der trotz aller Veränderungen bestehen bleibt und uns als dieselbe Person definiert?",
        "Kann künstliches Bewusstsein existieren und wenn ja, hätte es moralische Rechte? Welche Kriterien müssten erfüllt sein, um ein System als bewusst zu klassifizieren, und welche ethischen Verpflichtungen hätten wir gegenüber bewussten künstlichen Entitäten die wir erschaffen haben?",
        "Wie beeinflusst Sprache unser Denken fundamental? Bestimmt die Struktur unserer Sprache die Grenzen dessen, was wir denken können, oder ist Sprache nur ein Werkzeug zur Externalisierung von Gedanken die unabhängig von sprachlichen Kategorien existieren können?",
        "Welche Rolle spielt das Default Mode Network für Selbstbewusstsein und kreatives Denken? Sind diese spontanen neuronalen Aktivitäten in Ruhephasen essentiell für die Konstruktion unseres Selbstmodells und die Generierung neuartiger Ideen, oder sind sie nur Nebenprodukte ohne funktionale Bedeutung?",
        "Ist Bedeutung objektiv oder konstruiert? Existieren Bedeutungen unabhängig von Interpreten in der Welt, oder entstehen sie erst durch den Akt der Interpretation, wobei unterschiedliche Kontexte und Interpreten verschiedene aber gleichermaßen valide Bedeutungen generieren können?",
        "Wie verhält sich phänomenales Bewusstsein zu Zugriffsbewusstsein? Gibt es Erfahrungen, die wir haben ohne darauf Zugriff zu haben, und was bedeutet das für unser Verständnis von Bewusstsein, wenn nicht alle bewussten Inhalte gleichzeitig kognitiv verfügbar sind?",
    ]
}


# =============================================================================
# Mock Data Generation
# =============================================================================

def classify_query_length(query: str) -> str:
    """
    Classify query by word count (consistent with validation script)

    Classification:
    - Short: ≤10 words
    - Medium: 11-29 words
    - Long: ≥30 words
    """
    word_count = len(query.split())

    if word_count <= 10:
        return "short"
    elif word_count >= 30:
        return "long"
    else:
        return "medium"


def generate_mock_session_id() -> str:
    """Generate mock UUID session ID (different from Ground Truth)"""
    return str(uuid.uuid4())


def generate_expected_docs(num_docs: int = None) -> List[int]:
    """
    Generate mock expected_docs array

    Simulates manually labeled relevant L2 Insight IDs.
    In production: These would be actual labels from Streamlit UI.

    Args:
        num_docs: Number of relevant docs (default: random 1-5)

    Returns:
        List of L2 Insight IDs (mock: random from 1-30)
    """
    if num_docs is None:
        num_docs = random.randint(1, 5)  # Realistic range

    # Mock: Sample from pool of 30 L2 Insights
    return random.sample(range(1, 31), min(num_docs, 30))


def generate_mock_golden_test_set(
    target_total: int = 100,
    short_pct: float = 0.40,
    medium_pct: float = 0.40,
    long_pct: float = 0.20
) -> List[Dict]:
    """
    Generate mock Golden Test Set with stratified distribution

    NEW APPROACH: First classify all queries by actual word count,
    then stratified sample to achieve target distribution.

    Args:
        target_total: Total number of queries (default: 100)
        short_pct: Percentage of short queries (default: 40%)
        medium_pct: Percentage of medium queries (default: 40%)
        long_pct: Percentage of long queries (default: 20%)

    Returns:
        List of mock Golden Test Set items
    """
    target_short = int(target_total * short_pct)
    target_medium = int(target_total * medium_pct)
    target_long = int(target_total * long_pct)

    # Step 1: Collect ALL queries from all templates and classify
    all_queries_classified = {
        "short": [],
        "medium": [],
        "long": []
    }

    for template_category, queries in MOCK_QUERIES.items():
        for query in queries:
            actual_type = classify_query_length(query)
            all_queries_classified[actual_type].append(query)

    # Debug: Print classification results
    print(f"   Classified pool: Short={len(all_queries_classified['short'])}, Medium={len(all_queries_classified['medium'])}, Long={len(all_queries_classified['long'])}")
    print(f"   Targets: Short={target_short}, Medium={target_medium}, Long={target_long}")

    # Step 2: Stratified sampling from classified pools
    golden_set = []

    # Sample short queries
    if len(all_queries_classified["short"]) < target_short:
        # Not enough unique short queries, allow repetition
        short_sample = random.choices(all_queries_classified["short"], k=target_short)
    else:
        short_sample = random.sample(all_queries_classified["short"], target_short)

    for query in short_sample:
        word_count = len(query.split())
        golden_set.append({
            "id": len(golden_set) + 1,
            "query": query,
            "query_type": "short",
            "word_count": word_count,
            "expected_docs": generate_expected_docs(),
            "session_id": generate_mock_session_id(),
            "created_at": datetime.now().isoformat(),
            "labeled_by": "ethr",
            "notes": "Mock data - infrastructure testing"
        })

    # Sample medium queries
    if len(all_queries_classified["medium"]) < target_medium:
        # Not enough unique medium queries, allow repetition
        medium_sample = random.choices(all_queries_classified["medium"], k=target_medium)
    else:
        medium_sample = random.sample(all_queries_classified["medium"], target_medium)

    for query in medium_sample:
        word_count = len(query.split())
        golden_set.append({
            "id": len(golden_set) + 1,
            "query": query,
            "query_type": "medium",
            "word_count": word_count,
            "expected_docs": generate_expected_docs(),
            "session_id": generate_mock_session_id(),
            "created_at": datetime.now().isoformat(),
            "labeled_by": "ethr",
            "notes": "Mock data - infrastructure testing"
        })

    # Sample long queries
    if len(all_queries_classified["long"]) < target_long:
        # Not enough unique long queries, allow repetition
        long_sample = random.choices(all_queries_classified["long"], k=target_long)
    else:
        long_sample = random.sample(all_queries_classified["long"], target_long)

    for query in long_sample:
        word_count = len(query.split())
        golden_set.append({
            "id": len(golden_set) + 1,
            "query": query,
            "query_type": "long",
            "word_count": word_count,
            "expected_docs": generate_expected_docs(),
            "session_id": generate_mock_session_id(),
            "created_at": datetime.now().isoformat(),
            "labeled_by": "ethr",
            "notes": "Mock data - infrastructure testing"
        })

    # Shuffle to avoid perfect ordering
    random.shuffle(golden_set)

    # Re-number IDs after shuffle
    for i, item in enumerate(golden_set, 1):
        item["id"] = i

    return golden_set


def validate_stratification(golden_set: List[Dict]) -> Dict:
    """
    Validate that stratification is within acceptable ranges

    Returns:
        {
            "total": int,
            "short_count": int,
            "medium_count": int,
            "long_count": int,
            "short_pct": float,
            "medium_pct": float,
            "long_pct": float,
            "valid": bool
        }
    """
    total = len(golden_set)

    counts = {"short": 0, "medium": 0, "long": 0}
    for item in golden_set:
        counts[item["query_type"]] += 1

    percentages = {
        "short": counts["short"] / total if total > 0 else 0,
        "medium": counts["medium"] / total if total > 0 else 0,
        "long": counts["long"] / total if total > 0 else 0
    }

    # Valid if within ±5% of targets (40%, 40%, 20%)
    valid = (
        0.35 <= percentages["short"] <= 0.45 and
        0.35 <= percentages["medium"] <= 0.45 and
        0.15 <= percentages["long"] <= 0.25
    )

    return {
        "total": total,
        "short_count": counts["short"],
        "medium_count": counts["medium"],
        "long_count": counts["long"],
        "short_pct": percentages["short"],
        "medium_pct": percentages["medium"],
        "long_pct": percentages["long"],
        "valid": valid
    }


# =============================================================================
# Main Execution
# =============================================================================

def main():
    """Generate and save mock Golden Test Set"""
    print("=" * 60)
    print(": Mock Golden Test Set Generation")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Generate mock data
    print("🔄 Generating mock Golden Test Set...")
    golden_set = generate_mock_golden_test_set(target_total=100)

    # Validate stratification
    print("\n📊 Validating stratification...")
    stats = validate_stratification(golden_set)

    print(f"   Total queries: {stats['total']}")
    print(f"   Short ({stats['short_count']}): {stats['short_pct']:.1%} (target: 40%)")
    print(f"   Medium ({stats['medium_count']}): {stats['medium_pct']:.1%} (target: 40%)")
    print(f"   Long ({stats['long_count']}): {stats['long_pct']:.1%} (target: 20%)")

    if stats['valid']:
        print("   ✅ Stratification VALID (within ±5% of targets)")
    else:
        print("   ⚠️ Stratification out of range (regenerating...)")
        # Retry with adjusted targets
        golden_set = generate_mock_golden_test_set(target_total=100)
        stats = validate_stratification(golden_set)

    # Save to file
    output_file = "/home/user/i-o/mcp_server/scripts/mock_golden_test_set.json"
    print(f"\n💾 Saving to: {output_file}")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(golden_set, f, indent=2, ensure_ascii=False)

    print(f"✅ Mock Golden Test Set generated successfully!")
    print(f"   {len(golden_set)} queries saved")
    print()
    print("=" * 60)
    print("Next Steps:")
    print("1. Adapt Streamlit UI for Golden Test Set labeling")
    print("2. Implement validation script")
    print("3. Test infrastructure with mock data")
    print("4. Transition to production (Neon PostgreSQL)")
    print("=" * 60)


if __name__ == "__main__":
    main()
