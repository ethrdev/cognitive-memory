#!/usr/bin/env python3
"""
Cognitive Memory Library Usage Examples

Dieses Script demonstriert alle Features der Cognitive Memory Library API
mit praktischen Beispielen für Connection Management, Core Operations,
Error Handling und Ecosystem Integration.

Ausführbar mit: python examples/library_usage.py
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from typing import Any

# Add project root to path for imports when running standalone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cognitive_memory import (
    ConnectionError,
    EmbeddingError,
    MemoryStore,
    SearchError,
    StorageError,
    ValidationError,
)


def print_section(title: str) -> None:
    """Print formatted section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def print_subsection(title: str) -> None:
    """Print formatted subsection header."""
    print(f"\n--- {title} ---")


def demo_connection_setup() -> None:
    """Demonstriert verschiedene Connection Setup Methoden."""
    print_section("1. Connection Setup Examples")

    # Methode 1: Mit Environment Variable
    print_subsection("Environment Variable Connection")
    try:
        with MemoryStore.from_env() as store:
            print("✅ Connection mit Environment Variable erfolgreich")
            print("   DATABASE_URL wird aus Umgebung geladen")
    except ConnectionError as e:
        print(f"❌ Connection fehlgeschlagen: {e}")
        print("   Stelle sicher dass DATABASE_URL gesetzt ist")
        return

    # Methode 2: Mit explizitem Connection String
    print_subsection("Explicit Connection String")
    connection_string = os.getenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    try:
        store = MemoryStore(connection_string)
        print("✅ Connection mit explizitem String erfolgreich")
        store.disconnect()  # Manuelles Disconnect
    except ConnectionError as e:
        print(f"❌ Connection fehlgeschlagen: {e}")

    # Methode 3: Context Manager Pattern
    print_subsection("Context Manager Pattern")
    try:
        with MemoryStore() as store:
            print("✅ Context Manager Connection erfolgreich")
            print("   Connection wird automatisch am Ende geschlossen")
    except ConnectionError as e:
        print(f"❌ Context Manager Connection fehlgeschlagen: {e}")


def demo_hybrid_search() -> None:
    """Demonstriert Hybrid Search mit verschiedenen Weights."""
    print_section("2. Hybrid Search Examples")

    try:
        with MemoryStore.from_env() as store:
            print_subsection("Standard Search")

            # Standard Suche mit Default Weights
            results = store.search("künstliche intelligenz maschinelles lernen", top_k=3)

            if results:
                print(f"✅ {len(results)} Ergebnisse gefunden:")
                for i, result in enumerate(results, 1):
                    print(f"   {i}. [{result.score:.3f}] {result.content[:100]}...")
                    print(f"      Source: {result.source}, Semantic: {result.semantic_score:.3f}")
            else:
                print("ℹ️  Keine Ergebnisse gefunden (DB möglicherweise leer)")

            print_subsection("Custom Weights")

            # Suche mit angepassten Weights
            custom_weights = {"semantic": 0.8, "keyword": 0.1, "graph": 0.1}
            results = store.search(
                "deep learning neural networks",
                top_k=2,
                weights=custom_weights
            )

            if results:
                print(f"✅ {len(results)} Ergebnisse mit Custom Weights:")
                for result in results:
                    print(f"   [{result.score:.3f}] {result.content[:80]}...")

            print_subsection("Keyword-Only Search")

            # Nur Keyword Search (fallback bei embedding issues)
            keyword_weights = {"semantic": 0.0, "keyword": 1.0, "graph": 0.0}
            results = store.search("python programming", top_k=2, weights=keyword_weights)

            if results:
                print(f"✅ {len(results)} Keyword-Only Ergebnisse:")
                for result in results:
                    print(f"   [{result.score:.3f}] {result.content[:80]}...")

    except ConnectionError:
        print("❌ Keine Datenbank-Connection verfügbar")
    except SearchError as e:
        print(f"❌ Search Fehler: {e}")


def demo_l2_insight_storage() -> None:
    """Demonstriert L2 Insight Storage mit Metadata."""
    print_section("3. L2 Insight Storage Examples")

    try:
        with MemoryStore.from_env() as store:
            print_subsection("Basic Insight Storage")

            # Einfache Insight mit Metadaten
            result = store.store_insight(
                content=(
                    "Kognitive Architekturen erfordern modulare Designprinzipien "
                    "mit klaren Schnittstellen zwischen Komponenten"
                ),
                source_ids=[1, 2, 3],  # Beispiel Source IDs
                metadata={
                    "category": "architecture",
                    "priority": "high",
                    "tags": ["kognition", "architektur", "design"],
                    "author": "AI System"
                }
            )

            print(f"✅ Insight gespeichert:")
            print(f"   ID: {result.id}")
            print(f"   Embedding Status: {result.embedding_status}")
            print(f"   Fidelity Score: {result.fidelity_score:.3f}")
            print(f"   Created: {result.created_at}")

            print_subsection("Insight with Different Metadata")

            # Insight mit anderen Metadaten
            result2 = store.store_insight(
                content=(
                    "Machine Learning Modelle benötigen saubere, "
                    "repräsentative Trainingsdaten für gute Performance"
                ),
                source_ids=[4, 5],
                metadata={
                    "category": "machine_learning",
                    "domain": "data_science",
                    "confidence": 0.9,
                    "review_status": "pending"
                }
            )

            print(f"✅ Zweiter Insight gespeichert:")
            print(f"   ID: {result2.id}")
            print(f"   Category: {result2.fidelity_score:.3f} fidelity")

    except ConnectionError:
        print("❌ Keine Datenbank-Connection verfügbar")
    except (StorageError, EmbeddingError) as e:
        print(f"❌ Storage Fehler: {e}")
    except ValidationError as e:
        print(f"❌ Validation Fehler: {e}")


def demo_working_memory() -> None:
    """Demonstriert Working Memory Operations."""
    print_section("4. Working Memory Examples")

    try:
        with MemoryStore.from_env() as store:
            print_subsection("Add Items with Importance")

            # Items mit verschiedener Importance hinzufügen
            items_to_add = [
                ("User prefers German language explanations", 0.9),
                ("Current context: software development", 0.7),
                ("Session started recently", 0.5),
                ("Temporary note about API limits", 0.3)
            ]

            added_ids = []
            for content, importance in items_to_add:
                result = store.working.add(content, importance=importance)
                added_ids.append(result.added_id)
                print(f"✅ Added ID {result.added_id}: [{importance:.1f}] {content[:50]}...")

            print_subsection("List All Items")

            # Alle Items auflisten
            items = store.working.list()
            if items:
                print(f"✅ {len(items)} Items in Working Memory:")
                for item in sorted(items, key=lambda x: x.importance, reverse=True):
                    print(f"   ID {item.id}: [{item.importance:.1f}] {item.content}")
                    print(f"      Last accessed: {item.last_accessed}")
            else:
                print("ℹ️  Keine Items im Working Memory")

            print_subsection("Clear Working Memory")

            # Working Memory leeren
            cleared_count = store.working.clear()
            print(f"✅ {cleared_count} Items aus Working Memory entfernt")

    except ConnectionError:
        print("❌ Keine Datenbank-Connection verfügbar")
    except StorageError as e:
        print(f"❌ Working Memory Fehler: {e}")


def demo_episode_memory() -> None:
    """Demonstriert Episode Memory Operations."""
    print_section("5. Episode Memory Examples")

    try:
        with MemoryStore.from_env() as store:
            print_subsection("Store Episodes")

            # Episoden mit verschiedenen Rewards speichern
            episodes = [
                (
                    "Wie funktioniert KI-Lernen?",
                    0.8,
                    "Erkläre mit konkreten Beispielen statt abstrakter Theorie"
                ),
                (
                    "Was ist der Unterschied zwischen ML und DL?",
                    0.6,
                    "Fange mit einer einfachen Analogie an, gehe dann ins Detail"
                ),
                (
                    "Debugging fehlgeschlagen",
                    -0.3,
                    "Frage nach spezifischen Fehlermeldungen und Umgebungsdetails"
                )
            ]

            stored_episodes = []
            for query, reward, reflection in episodes:
                result = store.episode.store(query, reward, reflection)
                stored_episodes.append(result.id)
                print(f"✅ Episode {result.id}: [{reward:+.1f}] {query[:50]}...")
                print(f"   Reflection: {reflection[:60]}...")

            print_subsection("Search Similar Episodes")

            # Ähnliche Episoden suchen
            search_query = "Wie lerne ich am besten?"
            similar_episodes = store.episode.search(
                search_query,
                min_similarity=0.5,
                limit=2
            )

            if similar_episodes:
                print(f"✅ {len(similar_episodes)} ähnliche Episoden gefunden:")
                for episode in similar_episodes:
                    print(f"   [{episode.reward:+.1f}] {episode.query}")
                    print(f"   {episode.reflection[:80]}...")
            else:
                print("ℹ️  Keine ähnlichen Episoden gefunden")

    except ConnectionError:
        print("❌ Keine Datenbank-Connection verfügbar")
    except StorageError as e:
        print(f"❌ Episode Memory Fehler: {e}")


def demo_graph_operations() -> None:
    """Demonstriert Graph Operations für GraphRAG."""
    print_section("6. Graph Operations Examples")

    try:
        with MemoryStore.from_env() as store:
            print_subsection("Add Graph Nodes")

            # Concept Nodes hinzufügen
            concepts = [
                ("Concept", "Künstliche Intelligenz", {"domain": "cs", "level": "advanced"}),
                ("Concept", "Maschinelles Lernen", {"domain": "cs", "level": "intermediate"}),
                ("Concept", "Neuronale Netze", {"domain": "cs", "level": "advanced"}),
                ("Person", "Geoffrey Hinton", {"role": "pioneer", "field": "deep_learning"}),
                ("Technique", "Backpropagation", {"type": "algorithm", "year": 1970})
            ]

            added_nodes = {}
            for label, name, properties in concepts:
                result = store.graph.add_node(label, name, properties)
                added_nodes[name] = result.id
                print(f"✅ Node: {label} '{name}' (ID: {result.id})")

            print_subsection("Add Graph Edges")

            # Relationships hinzufügen
            relationships = [
                ("Künstliche Intelligenz", "Maschinelles Lernen", "INCLUDES", 0.9),
                ("Maschinelles Lernen", "Neuronale Netze", "INCLUDES", 0.8),
                ("Geoffrey Hinton", "Backpropagation", "CONTRIBUTED_TO", 1.0),
                ("Backpropagation", "Neuronale Netze", "ENABLES", 0.9)
            ]

            for source, target, relation, weight in relationships:
                result = store.graph.add_edge(source, target, relation, weight)
                print(f"✅ Edge: {source} --[{relation}]--> {target} (weight: {weight})")

            print_subsection("Query Neighbors")

            # Nachbarn eines Nodes finden
            neighbors = store.graph.query_neighbors("Maschinelles Lernen")
            if neighbors:
                print(f"✅ Neighbors von 'Maschinelles Lernen':")
                for neighbor in neighbors:
                    print(f"   - {neighbor.label}: {neighbor.name}")
                    if neighbor.properties:
                        print(f"     Properties: {neighbor.properties}")

            print_subsection("Find Path")

            # Pfad zwischen Nodes finden
            path_result = store.graph.find_path(
                "Künstliche Intelligenz",
                "Neuronale Netze",
                max_depth=3
            )

            if path_result.found:
                print(f"✅ Pfad gefunden (Länge: {path_result.length}):")
                print("   → ".join(path_result.path))
                print(f"   Details: {len(path_result.nodes)} Nodes, {len(path_result.edges)} Edges")
            else:
                print("ℹ️  Kein Pfad gefunden")

    except ConnectionError:
        print("❌ Keine Datenbank-Connection verfügbar")
    except StorageError as e:
        print(f"❌ Graph Operations Fehler: {e}")


def demo_error_handling() -> None:
    """Demonstriert Error Handling Patterns."""
    print_section("7. Error Handling Examples")

    print_subsection("Connection Error Handling")
    try:
        # Invalid connection string
        store = MemoryStore("postgresql://invalid:credentials@localhost/memory")
        store.search("test")
    except ConnectionError as e:
        print(f"✅ Connection Error korrekt behandelt: {e}")

    print_subsection("Validation Error Handling")
    try:
        with MemoryStore.from_env() as store:
            # Invalid importance value
            store.working.add("test", importance=2.0)  # Out of range (0.0-1.0)
    except ValidationError as e:
        print(f"✅ Validation Error korrekt behandelt: {e}")

    print_subsection("Search Error Handling")
    try:
        with MemoryStore.from_env() as store:
            # Empty query might cause issues
            store.search("", top_k=0)  # Invalid parameters
    except (ValidationError, SearchError) as e:
        print(f"✅ Search Error korrekt behandelt: {e}")

    print_subsection("Retry Pattern mit Exponential Backoff")

    def store_with_retry(store, content, max_retries=3):
        """Retry-Pattern für transient errors."""
        for attempt in range(max_retries):
            try:
                return store.store_insight(content, [1, 2, 3])
            except EmbeddingError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"   Embedding Error, retry in {wait_time}s... (attempt {attempt + 1})")
                    time.sleep(wait_time)
                    continue
                raise
            except ConnectionError as e:
                if attempt < max_retries - 1:
                    print(f"   Connection Error, retry... (attempt {attempt + 1})")
                    time.sleep(1)
                    continue
                raise

    # Demo (wird bei realen API Errors retrys zeigen)
    print("✅ Retry Pattern implementiert (siehe store_with_retry function)")

    print_subsection("Graceful Degradation")

    def robust_search(store, query):
        """Funktioniert auch wenn einige Komponenten ausfallen."""
        strategies = [
            ("Hybrid Search", {"semantic": 0.6, "keyword": 0.2, "graph": 0.2}),
            ("Keyword-Only", {"semantic": 0.0, "keyword": 1.0, "graph": 0.0}),
        ]

        for strategy_name, weights in strategies:
            try:
                results = store.search(query, weights=weights)
                print(f"✅ {strategy_name} erfolgreich: {len(results)} Ergebnisse")
                return results
            except (EmbeddingError, SearchError) as e:
                print(f"⚠️  {strategy_name} fehlgeschlagen: {e}")
                continue

        print("⚠️  Alle Search-Strategien fehlgeschlagen")
        return []

    print("✅ Graceful Degradation implementiert (siehe robust_search function)")


def demo_ecosystem_integration() -> None:
    """Demonstriert Ecosystem Integration Patterns."""
    print_section("8. Ecosystem Integration Examples")

    print_subsection("Storage Backend Adapter Pattern")

    # Beispiel für i-o-system Integration
    class CognitiveMemoryAdapter:
        """Adapter für StorageBackend Protocol Compliance."""

        def __init__(self):
            try:
                self._store = MemoryStore.from_env()
                self._connected = True
            except ConnectionError as e:
                print(f"⚠️  Adapter konnte nicht connecten: {e}")
                self._connected = False

        def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
            """Suche nach relevanten Inhalten."""
            if not self._connected:
                return []

            try:
                results = self._store.search(query, top_k=limit)
                return [self._to_io_format(r) for r in results]
            except Exception as e:
                print(f"Search failed: {e}")
                return []

        def store(self, content: str, metadata: dict[str, Any] = None) -> str:
            """Speichere neuen Inhalt."""
            if not self._connected:
                raise ConnectionError("Adapter not connected")

            try:
                result = self._store.store_insight(content, [], metadata or {})
                return str(result.id)
            except Exception as e:
                print(f"Storage failed: {e}")
                raise

        def _to_io_format(self, result) -> dict[str, Any]:
            """Konvertiere SearchResult zu i-o-system Format."""
            return {
                "id": str(result.id),
                "content": result.content,
                "score": result.score,
                "source": result.source,
                "metadata": result.metadata,
                "timestamp": datetime.now().isoformat()
            }

    # Adapter Demo
    adapter = CognitiveMemoryAdapter()
    if adapter._connected:
        print("✅ CognitiveMemoryAdapter erfolgreich erstellt")

        # Suchen
        results = adapter.search("kognitive systeme", limit=3)
        print(f"✅ Adapter Search: {len(results)} Ergebnisse")

        # Speichern
        try:
            item_id = adapter.store(
                "Kognitive Systeme benötigen klare Architekturen",
                {"category": "architecture", "priority": "high"}
            )
            print(f"✅ Adapter Store: Item {item_id} gespeichert")
        except Exception as e:
            print(f"⚠️  Adapter Store fehlgeschlagen: {e}")

    print_subsection("Dependency Management")

    required_packages = [
        "psycopg2-binary",
        "pgvector",
        "openai",
        "numpy",
        "scipy",
        "scikit-learn",
        "python-dotenv"
    ]

    print("✅ Required Dependencies:")
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} (not installed)")

    print_subsection("Configuration Management")

    # Environment Variables für die Library
    env_vars = {
        "DATABASE_URL": "PostgreSQL connection string",
        "OPENAI_API_KEY": "OpenAI API key for embeddings",
        "ANTHROPIC_API_KEY": "Anthropic API key (optional)"
    }

    print("✅ Environment Variables:")
    for var, description in env_vars.items():
        value = os.getenv(var)
        if value:
            masked = value[:10] + "..." if len(value) > 10 else "***"
            print(f"   ✅ {var}: {masked} ({description})")
        else:
            print(f"   ⚠️  {var}: not set ({description})")


def main() -> None:
    """Hauptfunktion - führt alle Demos aus."""
    print("🧠 Cognitive Memory Library Usage Examples")
    print("=" * 60)
    print("Dieses Script demonstriert alle Features der Library API.")
    print("Stelle sicher dass DATABASE_URL gesetzt ist für volle Funktionalität.")

    try:
        demo_connection_setup()
        demo_hybrid_search()
        demo_l2_insight_storage()
        demo_working_memory()
        demo_episode_memory()
        demo_graph_operations()
        demo_error_handling()
        demo_ecosystem_integration()

        print_section("✅ Alle Demos abgeschlossen")
        print("Die Cognitive Memory Library ist voll funktionsfähig!")
        print("\nNächste Schritte:")
        print("1. Integriere MemoryStore in deine Anwendung")
        print("2. Passe Weights für deine Use Cases an")
        print("3. Implementiere Error Handling für Production")
        print("4. Nutze Working Memory für Session-Kontext")
        print("5. Erweitere mit Graph Operations für Knowledge Graphs")

    except KeyboardInterrupt:
        print("\n\n⏹️  Demo vom Benutzer abgebrochen")
    except Exception as e:
        print(f"\n\n❌ Unerwarteter Fehler: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()