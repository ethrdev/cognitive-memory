#!/usr/bin/env python3
"""
Populate L2 Insights Test Data for Story 2.7
============================================

Inserts 30 realistic L2 insights with embeddings into Neon database.
These insights span multiple topics to enable comprehensive RAG testing:
- High confidence queries (exact matches)
- Low confidence queries (semantic matches with Reflexion)
- Medium confidence queries (hybrid search)
- Episode memory retrieval tests

Usage:
    # With OpenAI embeddings (requires API credits)
    poetry run python populate_test_data.py

    # With mock embeddings (for testing without API credits)
    poetry run python populate_test_data.py --mock
"""

import os
import sys
import json
import psycopg2
from datetime import datetime, timedelta
import random
import numpy as np

# Check if --mock flag is provided
USE_MOCK_EMBEDDINGS = '--mock' in sys.argv

# Read environment variables
env_content = open('.env.development').read()
for line in env_content.split('\n'):
    if line.startswith('DATABASE_URL='):
        DATABASE_URL = line.replace('DATABASE_URL=', '').strip()
    elif line.startswith('OPENAI_API_KEY='):
        OPENAI_API_KEY = line.replace('OPENAI_API_KEY=', '').strip()

# Initialize OpenAI client only if not using mocks
if not USE_MOCK_EMBEDDINGS:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
    except ImportError:
        print("⚠️  OpenAI package not installed. Using mock embeddings.")
        USE_MOCK_EMBEDDINGS = True

# Test L2 Insights - diverse topics for RAG testing
TEST_INSIGHTS = [
    # Philosophy & Ethics (5 insights)
    {
        "content": "Kant's categorical imperative states that one should act only according to maxims that could become universal laws. This deontological approach emphasizes duty over consequences.",
        "source_ids": [1, 2, 3],
        "metadata": {"topic": "philosophy", "subtopic": "ethics", "thinker": "Kant"}
    },
    {
        "content": "Virtue ethics, championed by Aristotle, focuses on character development rather than rules or consequences. Eudaimonia (human flourishing) is achieved through practicing virtues like courage, temperance, and wisdom.",
        "source_ids": [4, 5],
        "metadata": {"topic": "philosophy", "subtopic": "virtue_ethics", "thinker": "Aristotle"}
    },
    {
        "content": "Utilitarianism, developed by Bentham and Mill, judges actions by their consequences. The morally right action maximizes overall happiness or utility for the greatest number of people.",
        "source_ids": [6, 7, 8],
        "metadata": {"topic": "philosophy", "subtopic": "consequentialism", "thinker": "Mill"}
    },
    {
        "content": "Existentialism emphasizes individual freedom, choice, and responsibility. Sartre argued that existence precedes essence - we create our own meaning through authentic choices.",
        "source_ids": [9, 10],
        "metadata": {"topic": "philosophy", "subtopic": "existentialism", "thinker": "Sartre"}
    },
    {
        "content": "The trolley problem illustrates moral dilemmas between active harm and passive allowance. It tests intuitions about consequentialism versus deontological constraints on action.",
        "source_ids": [11, 12, 13],
        "metadata": {"topic": "philosophy", "subtopic": "thought_experiments", "type": "dilemma"}
    },

    # Machine Learning & AI (7 insights)
    {
        "content": "Transformers use self-attention mechanisms to process sequences in parallel, enabling breakthrough performance in NLP. The attention mechanism allows models to weigh the importance of different input tokens.",
        "source_ids": [14, 15, 16],
        "metadata": {"topic": "machine_learning", "subtopic": "transformers", "year": 2017}
    },
    {
        "content": "Retrieval-Augmented Generation (RAG) combines parametric knowledge from language models with non-parametric retrieval from external knowledge bases. This enables factual grounding and reduces hallucinations.",
        "source_ids": [17, 18],
        "metadata": {"topic": "machine_learning", "subtopic": "RAG", "application": "question_answering"}
    },
    {
        "content": "Chain-of-Thought prompting improves reasoning by encouraging models to generate intermediate reasoning steps. This technique significantly boosts performance on complex multi-step problems.",
        "source_ids": [19, 20, 21],
        "metadata": {"topic": "machine_learning", "subtopic": "prompting", "technique": "CoT"}
    },
    {
        "content": "Reinforcement Learning from Human Feedback (RLHF) aligns language models with human preferences. The process involves supervised fine-tuning, reward modeling, and policy optimization via PPO.",
        "source_ids": [22, 23, 24],
        "metadata": {"topic": "machine_learning", "subtopic": "alignment", "technique": "RLHF"}
    },
    {
        "content": "Vector databases enable semantic search by storing high-dimensional embeddings and supporting approximate nearest neighbor search. pgvector extends PostgreSQL with vector similarity capabilities.",
        "source_ids": [25, 26],
        "metadata": {"topic": "machine_learning", "subtopic": "vector_databases", "tool": "pgvector"}
    },
    {
        "content": "Few-shot learning enables models to generalize from minimal examples by leveraging pre-trained knowledge. In-context learning in large language models demonstrates impressive few-shot capabilities.",
        "source_ids": [27, 28, 29],
        "metadata": {"topic": "machine_learning", "subtopic": "few_shot_learning", "paradigm": "in_context"}
    },
    {
        "content": "Constitutional AI uses AI feedback instead of human feedback to align models with specified principles. This approach can scale alignment beyond what human oversight alone can achieve.",
        "source_ids": [30, 31],
        "metadata": {"topic": "machine_learning", "subtopic": "alignment", "technique": "CAI"}
    },

    # Cognitive Science & Memory (6 insights)
    {
        "content": "Working memory has limited capacity, typically holding 4-7 chunks of information. The phonological loop and visuospatial sketchpad are subsystems for temporary storage.",
        "source_ids": [32, 33, 34],
        "metadata": {"topic": "cognitive_science", "subtopic": "memory", "type": "working_memory"}
    },
    {
        "content": "Episodic memory stores personally experienced events with temporal and spatial context. The hippocampus plays a crucial role in encoding and retrieving episodic memories.",
        "source_ids": [35, 36],
        "metadata": {"topic": "cognitive_science", "subtopic": "memory", "type": "episodic"}
    },
    {
        "content": "Semantic memory contains factual knowledge about the world, independent of personal experience. It includes concepts, meanings, and general knowledge organized in associative networks.",
        "source_ids": [37, 38, 39],
        "metadata": {"topic": "cognitive_science", "subtopic": "memory", "type": "semantic"}
    },
    {
        "content": "Memory consolidation transforms short-term memories into long-term storage through synaptic strengthening. Sleep plays a critical role in consolidating declarative memories.",
        "source_ids": [40, 41],
        "metadata": {"topic": "cognitive_science", "subtopic": "memory", "process": "consolidation"}
    },
    {
        "content": "Retrieval practice enhances long-term retention more effectively than repeated study. The testing effect demonstrates that active recall strengthens memory traces.",
        "source_ids": [42, 43, 44],
        "metadata": {"topic": "cognitive_science", "subtopic": "learning", "technique": "retrieval_practice"}
    },
    {
        "content": "Metacognition involves thinking about one's own cognitive processes. Accurate metacognitive monitoring enables effective self-regulated learning and error detection.",
        "source_ids": [45, 46],
        "metadata": {"topic": "cognitive_science", "subtopic": "metacognition", "application": "learning"}
    },

    # Physics & Cosmology (5 insights)
    {
        "content": "General relativity describes gravity as spacetime curvature caused by mass and energy. Einstein's field equations predict phenomena like gravitational lensing and black holes.",
        "source_ids": [47, 48, 49],
        "metadata": {"topic": "physics", "subtopic": "relativity", "scientist": "Einstein"}
    },
    {
        "content": "Quantum entanglement creates correlations between particles that cannot be explained by classical physics. Measuring one entangled particle instantaneously affects its partner, regardless of distance.",
        "source_ids": [50, 51],
        "metadata": {"topic": "physics", "subtopic": "quantum_mechanics", "phenomenon": "entanglement"}
    },
    {
        "content": "The cosmic microwave background radiation is the afterglow of the Big Bang, providing evidence for the hot dense early universe. WMAP and Planck satellites mapped its tiny temperature fluctuations.",
        "source_ids": [52, 53, 54],
        "metadata": {"topic": "physics", "subtopic": "cosmology", "evidence": "CMB"}
    },
    {
        "content": "Dark matter comprises about 85% of the universe's matter but doesn't interact with light. Its existence is inferred from gravitational effects on galaxy rotation curves and gravitational lensing.",
        "source_ids": [55, 56],
        "metadata": {"topic": "physics", "subtopic": "cosmology", "mystery": "dark_matter"}
    },
    {
        "content": "The uncertainty principle states that certain pairs of physical properties cannot be simultaneously measured with arbitrary precision. Position and momentum are complementary variables with fundamental measurement limits.",
        "source_ids": [57, 58, 59],
        "metadata": {"topic": "physics", "subtopic": "quantum_mechanics", "principle": "uncertainty"}
    },

    # Biology & Evolution (4 insights)
    {
        "content": "Natural selection operates on heritable variation in fitness. Organisms with advantageous traits are more likely to survive and reproduce, leading to adaptation over generations.",
        "source_ids": [60, 61, 62],
        "metadata": {"topic": "biology", "subtopic": "evolution", "mechanism": "natural_selection"}
    },
    {
        "content": "CRISPR-Cas9 enables precise genome editing by using guide RNA to direct Cas9 nuclease to specific DNA sequences. This technology revolutionized genetic engineering and gene therapy.",
        "source_ids": [63, 64],
        "metadata": {"topic": "biology", "subtopic": "genetics", "tool": "CRISPR"}
    },
    {
        "content": "The microbiome consists of trillions of microorganisms living in and on the human body. Gut microbiota influence digestion, immunity, and even mental health through the gut-brain axis.",
        "source_ids": [65, 66, 67],
        "metadata": {"topic": "biology", "subtopic": "microbiome", "system": "gut"}
    },
    {
        "content": "Epigenetic modifications like DNA methylation and histone acetylation regulate gene expression without changing the DNA sequence. Environmental factors can influence epigenetic marks across generations.",
        "source_ids": [68, 69],
        "metadata": {"topic": "biology", "subtopic": "epigenetics", "mechanism": "methylation"}
    },

    # Economics & Game Theory (3 insights)
    {
        "content": "The prisoner's dilemma illustrates how rational self-interest can lead to suboptimal outcomes. Nash equilibrium occurs when both players defect, even though mutual cooperation yields better results.",
        "source_ids": [70, 71, 72],
        "metadata": {"topic": "economics", "subtopic": "game_theory", "concept": "prisoners_dilemma"}
    },
    {
        "content": "Market failures occur when free markets fail to allocate resources efficiently. Common causes include externalities, public goods, information asymmetries, and monopoly power.",
        "source_ids": [73, 74],
        "metadata": {"topic": "economics", "subtopic": "market_failure", "type": "externalities"}
    },
    {
        "content": "Behavioral economics incorporates psychological insights into economic models. Concepts like loss aversion, anchoring, and hyperbolic discounting explain deviations from rational choice theory.",
        "source_ids": [75, 76, 77],
        "metadata": {"topic": "economics", "subtopic": "behavioral_economics", "bias": "loss_aversion"}
    }
]

def get_embedding(text: str) -> list[float]:
    """Generate embedding for text - either OpenAI or mock."""
    if USE_MOCK_EMBEDDINGS:
        # Generate deterministic mock embedding based on text hash
        np.random.seed(hash(text) % (2**32))
        return np.random.randn(1536).tolist()
    else:
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"⚠️  OpenAI API error: {e}")
            print("   Falling back to mock embedding for this insight...")
            np.random.seed(hash(text) % (2**32))
            return np.random.randn(1536).tolist()

def insert_l2_insight(cursor, content: str, source_ids: list[int], metadata: dict) -> int:
    """Insert a single L2 insight with embedding and return its ID."""
    # Generate embedding
    embedding = get_embedding(content)

    # Insert into database (use json.dumps instead of psycopg2.extras.Json)
    cursor.execute("""
        INSERT INTO l2_insights (content, embedding, source_ids, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (
        content,
        embedding,
        source_ids,
        json.dumps(metadata),  # Fixed: use json.dumps instead of psycopg2.extras.Json
        datetime.now() - timedelta(days=random.randint(1, 30))  # Random timestamps
    ))

    return cursor.fetchone()[0]

def main():
    print("🚀 Starting L2 Insights Test Data Population")
    if USE_MOCK_EMBEDDINGS:
        print(f"📊 Inserting {len(TEST_INSIGHTS)} insights with MOCK embeddings (deterministic random vectors)...\n")
        print("⚠️  NOTE: Mock embeddings enable testing but won't provide meaningful semantic search.")
        print("   For full RAG testing, rerun with OpenAI API credits (remove --mock flag).\n")
    else:
        print(f"📊 Inserting {len(TEST_INSIGHTS)} insights with OpenAI embeddings...\n")

    # Connect to Neon
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    inserted_ids = []
    topic_counts = {}

    for i, insight in enumerate(TEST_INSIGHTS, 1):
        try:
            # Insert insight
            insight_id = insert_l2_insight(
                cursor,
                insight['content'],
                insight['source_ids'],
                insight['metadata']
            )
            inserted_ids.append(insight_id)

            # Track topic counts
            topic = insight['metadata'].get('topic', 'unknown')
            topic_counts[topic] = topic_counts.get(topic, 0) + 1

            # Progress indicator
            print(f"✅ [{i:2d}/{len(TEST_INSIGHTS)}] Inserted ID {insight_id:3d} - {topic:20s} - {insight['content'][:60]}...")

        except Exception as e:
            print(f"❌ [{i:2d}/{len(TEST_INSIGHTS)}] Failed: {e}")
            conn.rollback()
            continue

    # Commit all inserts
    conn.commit()

    # Verify insertion count
    cursor.execute("SELECT COUNT(*) FROM l2_insights;")
    total_count = cursor.fetchone()[0]

    print(f"\n{'='*80}")
    print(f"🎉 Data Population Complete!")
    print(f"{'='*80}")
    print(f"📊 Total L2 Insights in Database: {total_count}")
    print(f"✅ Successfully Inserted: {len(inserted_ids)}")
    print(f"\n📈 Insights by Topic:")
    for topic, count in sorted(topic_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   - {topic:25s}: {count:2d} insights")

    print(f"\n🔍 Sample IDs: {inserted_ids[:5]} ... {inserted_ids[-5:]}")

    # Close connection
    cursor.close()
    conn.close()

    print(f"\n✅ Database connection closed")
    print(f"🚀 Ready for Story 2.7 RAG Pipeline Testing!")

if __name__ == "__main__":
    main()
