#!/usr/bin/env python3
"""
Golden Test Set Labeling UI

Story 3.1: Streamlit app for manually labeling Golden Test Set queries.

Features:
- Load queries from mock_golden_test_set.json (mock mode)
- Display query and retrieve top-5 documents (simulated)
- Binary relevance labeling (Relevant? Yes/No)
- Progress tracking
- Save labeled results to golden_test_set_labeled.json

Mock Mode:
- Uses mock_golden_test_set.json as source
- Simulates hybrid_search results (random L2 Insight IDs)
- Saves to golden_test_set_labeled.json (no PostgreSQL)

Production Mode (Future):
- Load unlabeled queries from PostgreSQL
- Call actual hybrid_search MCP Tool
- Save labels to PostgreSQL golden_test_set table
"""

import streamlit as st
import json
import random
import sys
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path for database imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from db.connection import get_connection, initialize_pool

# =============================================================================
# Configuration
# =============================================================================

MOCK_MODE = False  # Set to True for mock mode testing

MOCK_QUERIES_FILE = "/home/user/i-o/mcp_server/scripts/mock_golden_test_set.json"
LABELED_OUTPUT_FILE = "/home/user/i-o/mcp_server/scripts/golden_test_set_labeled.json"

# Mock L2 Insights (simulated retrieval results)
MOCK_L2_INSIGHTS = [
    {"id": 1, "content": "Bewusstsein als emergentes Phänomen neuronaler Aktivität"},
    {"id": 2, "content": "Gedächtnis und Lernen: Synaptic Plasticity und Konsolidierung"},
    {"id": 3, "content": "Sprache als Werkzeug des Denkens - Sapir-Whorf Hypothese"},
    {"id": 4, "content": "Emotionen und Entscheidungsfindung: Damasio's Somatic Marker Hypothesis"},
    {"id": 5, "content": "Kreativität als rekombinatorischer Prozess"},
    {"id": 6, "content": "Identität und Selbstwahrnehmung: Narrative Kontinuität"},
    {"id": 7, "content": "Wahrnehmung als aktiver Konstruktionsprozess"},
    {"id": 8, "content": "Aufmerksamkeit und selektive Informationsverarbeitung"},
    {"id": 9, "content": "Intelligenz: Fluid vs. Crystallized Intelligence"},
    {"id": 10, "content": "Zeitwahrnehmung und subjektive Dauer"},
    {"id": 11, "content": "Bedeutung emergiert aus Kontext und Verwendung"},
    {"id": 12, "content": "Realität als konstruierte Repräsentation"},
    {"id": 13, "content": "Intuition und implizites Wissen"},
    {"id": 14, "content": "Motivation: Intrinsisch vs. Extrinsisch"},
    {"id": 15, "content": "Selbstbewusstsein als metakognitive Fähigkeit"},
    {"id": 16, "content": "Vergessen als aktiver Prozess: Interference und Decay"},
    {"id": 17, "content": "Deklaratives vs. Prozedurales Gedächtnis"},
    {"id": 18, "content": "Unbewusstes und automatische Prozesse"},
    {"id": 19, "content": "Semantisches vs. Episodisches Gedächtnis"},
    {"id": 20, "content": "Neuronale Korrelate des Bewusstseins (NCC)"},
    {"id": 21, "content": "Abstraktion und Konzeptbildung im Kindesalter"},
    {"id": 22, "content": "Spracherwerb: Chomsky's Universal Grammar"},
    {"id": 23, "content": "Träume und REM-Schlaf: Memory Consolidation"},
    {"id": 24, "content": "Hard Problem of Consciousness: Qualia und subjektive Erfahrung"},
    {"id": 25, "content": "Künstliche vs. Natürliche Intelligenz: Symbol Grounding Problem"},
    {"id": 26, "content": "Problemlösung und kreative Einsicht"},
    {"id": 27, "content": "Embodied Cognition: Verkörperung des Denkens"},
    {"id": 28, "content": "Freier Wille vs. Determinismus: Libet's Experimente"},
    {"id": 29, "content": "Default Mode Network und Selbstreferenzielles Denken"},
    {"id": 30, "content": "Phänomenales vs. Zugriffsbewusstsein: Block's Dichotomy"},
]


# =============================================================================
# Data Loading and Storage
# =============================================================================

@st.cache_data
def load_queries_from_db() -> List[Dict]:
    """Load unlabeled queries from PostgreSQL golden_test_set table"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Load all queries from golden_test_set (labeled and unlabeled)
                cur.execute("""
                    SELECT id, query, query_type, expected_docs, session_id, word_count
                    FROM golden_test_set
                    ORDER BY id
                """)

                queries = []
                for row in cur.fetchall():
                    queries.append({
                        "id": row[0],
                        "query": row[1],
                        "query_type": row[2],
                        "expected_docs": row[3] if row[3] else [],
                        "session_id": str(row[4]) if row[4] else None,
                        "word_count": row[5] if row[5] else len(row[1].split())
                    })

                return queries
    except Exception as e:
        st.error(f"Database error: {e}")
        return []


def load_queries() -> List[Dict]:
    """Load queries from mock file or PostgreSQL based on MOCK_MODE"""
    if MOCK_MODE:
        with open(MOCK_QUERIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # Production: Load from PostgreSQL
        return load_queries_from_db()


def load_labeled_data() -> Dict:
    """Load existing labeled data (for resume functionality)"""
    output_path = Path(LABELED_OUTPUT_FILE)
    if output_path.exists():
        with open(output_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"labeled_queries": []}


def save_labeled_query_to_db(query_id: int, expected_docs: List[int]) -> bool:
    """
    Save labeled query to PostgreSQL golden_test_set table.

    Args:
        query_id: ID of query in golden_test_set table
        expected_docs: List of relevant L2 Insight IDs

    Returns:
        True if successful, False otherwise
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE golden_test_set
                    SET expected_docs = %s
                    WHERE id = %s
                """, (expected_docs, query_id))
                conn.commit()
                return True
    except Exception as e:
        st.error(f"Database save error: {e}")
        return False


def save_labeled_query(query_data: Dict):
    """Save a single labeled query (mock or PostgreSQL)"""
    if MOCK_MODE:
        labeled_data = load_labeled_data()
        labeled_data["labeled_queries"].append(query_data)

        with open(LABELED_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(labeled_data, f, indent=2, ensure_ascii=False)
    else:
        # Production: Save to PostgreSQL
        query_id = query_data.get("id")
        expected_docs = query_data.get("expected_docs", [])
        return save_labeled_query_to_db(query_id, expected_docs)


def simulate_hybrid_search(query: str, top_k: int = 5) -> List[Dict]:
    """
    Simulate hybrid_search MCP Tool call (mock mode)

    In production: Replace with actual MCP Tool call

    Returns:
        List of {id: int, content: str, score: float}
    """
    # Mock: Return random L2 Insights with random scores
    sampled_insights = random.sample(MOCK_L2_INSIGHTS, min(top_k, len(MOCK_L2_INSIGHTS)))

    results = []
    for insight in sampled_insights:
        results.append({
            "id": insight["id"],
            "content": insight["content"],
            "score": round(random.uniform(0.5, 0.95), 3)  # Mock relevance score
        })

    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


# =============================================================================
# Streamlit UI
# =============================================================================

def main():
    st.set_page_config(
        page_title="Golden Test Set Labeling",
        page_icon="🏆",
        layout="wide"
    )

    st.title("🏆 Golden Test Set Labeling")
    st.markdown("**Story 3.1:** Label 50-100 queries for production monitoring")

    # Initialize database connection pool (production mode only)
    if not MOCK_MODE:
        try:
            initialize_pool()
        except Exception as e:
            st.error(f"Failed to initialize database connection: {e}")
            st.stop()

    # Load data
    queries = load_queries()

    if MOCK_MODE:
        labeled_data = load_labeled_data()
        labeled_count = len(labeled_data["labeled_queries"])
    else:
        # Production: Count labeled queries (non-empty expected_docs)
        labeled_count = sum(1 for q in queries if q.get("expected_docs") and len(q["expected_docs"]) > 0)

    # Progress tracking
    target_total = 100
    progress = labeled_count / target_total

    st.progress(progress)
    st.write(f"**Progress:** {labeled_count}/{target_total} queries labeled ({progress:.0%})")

    # Show stratification balance
    if labeled_count > 0:
        if MOCK_MODE:
            query_types = [q["query_type"] for q in labeled_data["labeled_queries"]]
        else:
            # Production: Count labeled queries by type
            query_types = [q["query_type"] for q in queries if q.get("expected_docs") and len(q["expected_docs"]) > 0]

        type_counts = {
            "short": query_types.count("short"),
            "medium": query_types.count("medium"),
            "long": query_types.count("long")
        }
        st.write(f"**Stratification:** Short: {type_counts['short']}, Medium: {type_counts['medium']}, Long: {type_counts['long']}")

    st.markdown("---")

    # Check if all labeled
    if labeled_count >= target_total:
        st.success("🎉 All queries labeled! You can review or re-label.")
        if st.button("Reset Progress"):
            Path(LABELED_OUTPUT_FILE).unlink(missing_ok=True)
            st.rerun()
        return

    # Initialize session state
    if 'current_idx' not in st.session_state:
        st.session_state.current_idx = labeled_count

    # Get current query
    if st.session_state.current_idx >= len(queries):
        st.success("✅ All available queries processed!")
        return

    current_query = queries[st.session_state.current_idx]

    # Display query info
    st.subheader(f"Query {st.session_state.current_idx + 1}/{len(queries)}")

    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"**Type:** {current_query['query_type'].capitalize()}")
    with col2:
        st.write(f"**Word Count:** {current_query['word_count']}")

    st.markdown(f"### 📝 Query")
    st.info(current_query['query'])

    # Simulate hybrid_search
    st.markdown("### 🔍 Retrieved Documents (Top-5)")
    st.caption("Select all documents that are relevant to answer this query")

    retrieved_docs = simulate_hybrid_search(current_query['query'], top_k=5)

    relevant_docs = []
    for i, doc in enumerate(retrieved_docs):
        col1, col2, col3 = st.columns([1, 5, 1])

        with col1:
            st.write(f"**Doc {i+1}**")
        with col2:
            st.write(f"{doc['content']}")
            st.caption(f"Score: {doc['score']:.3f} | ID: {doc['id']}")
        with col3:
            is_relevant = st.checkbox("Relevant?", key=f"doc_{i}")
            if is_relevant:
                relevant_docs.append(doc['id'])

    st.markdown("---")

    # Action buttons
    col1, col2, col3 = st.columns([2, 2, 2])

    with col1:
        if st.button("✅ Submit & Next", type="primary", use_container_width=True):
            # Save labeled query
            labeled_query = {
                **current_query,
                "expected_docs": relevant_docs,
                "labeled_at": st.session_state.get('_last_run_time', 'unknown')
            }
            save_labeled_query(labeled_query)

            st.session_state.current_idx += 1
            st.success(f"✅ Labeled! {len(relevant_docs)} relevant docs marked.")
            st.rerun()

    with col2:
        if st.button("⏭️ Skip Query", use_container_width=True):
            st.session_state.current_idx += 1
            st.warning("⏭️ Query skipped.")
            st.rerun()

    with col3:
        if st.button("🔄 Restart", use_container_width=True):
            st.session_state.current_idx = 0
            st.info("🔄 Restarted from beginning.")
            st.rerun()

    # Keyboard shortcuts hint
    st.markdown("---")
    st.caption("💡 **Tip:** Use keyboard navigation - Y (Yes), N (No), Enter (Submit)")

    # Debug info (collapsible)
    with st.expander("🔧 Debug Info"):
        st.json({
            "current_idx": st.session_state.current_idx,
            "labeled_count": labeled_count,
            "mock_mode": MOCK_MODE,
            "output_file": LABELED_OUTPUT_FILE
        })


if __name__ == "__main__":
    main()
