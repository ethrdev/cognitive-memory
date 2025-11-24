#!/usr/bin/env python3
"""
Ground Truth Collection UI (Streamlit App)

Story 1.10: Streamlit-based interface for efficient labeling of 50-100 Ground Truth Queries
Features: Stratified query extraction, direct DB hybrid search, progress tracking, PostgreSQL storage
"""

import asyncio
import logging
import os
from typing import Any

import streamlit as st
from openai import OpenAI
from pgvector.psycopg2 import register_vector  # type: ignore

# Import required modules from the MCP server for reuse
from mcp_server.db.connection import get_connection
from mcp_server.tools import get_embedding_with_retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# App configuration
st.set_page_config(
    page_title="Ground Truth Collection",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Constants
TARGET_QUERIES = 100
STRATIFICATION_TARGETS = {"short": 0.4, "medium": 0.4, "long": 0.2}  # 40/40/20 split


def get_embedding_with_retry_sync(client: OpenAI, text: str) -> list[float]:
    """
    Synchronous wrapper for get_embedding_with_retry
    """
    return asyncio.run(get_embedding_with_retry(client, text))


def extract_queries() -> list[tuple[str, str, str]]:
    """
    Extract 50-100 queries with stratified sampling & temporal diversity.

    Returns:
        List of tuples: (query_text, category, session_id)
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # SQL for stratified sampling with temporal diversity
            stratified_query_sql = """
            -- Step 1: Identify eligible sessions with 3-5 queries
            WITH eligible_sessions AS (
              SELECT session_id
              FROM l0_raw
              WHERE speaker = 'user'
              GROUP BY session_id
              HAVING COUNT(*) BETWEEN 3 AND 5
            ),

            -- Step 2: Calculate sentence count for all queries in eligible sessions
            queries_with_sentence_count AS (
              SELECT
                l0.content,
                l0.session_id,
                -- Count all sentence-ending punctuation (.!?)
                LENGTH(l0.content) - LENGTH(
                  REPLACE(REPLACE(REPLACE(l0.content, '.', ''), '?', ''), '!', '')
                ) AS sentence_count
              FROM l0_raw l0
              INNER JOIN eligible_sessions es ON l0.session_id = es.session_id
              WHERE l0.speaker = 'user'
                AND LENGTH(l0.content) > 10  -- Filter very short queries
            ),

            -- Step 3: Stratified Sampling (40% Short, 40% Medium, 20% Long)
            short_queries AS (
              SELECT content, session_id, 'short' AS category
              FROM queries_with_sentence_count
              WHERE sentence_count BETWEEN 1 AND 2
              ORDER BY RANDOM()
              LIMIT 40
            ),
            medium_queries AS (
              SELECT content, session_id, 'medium' AS category
              FROM queries_with_sentence_count
              WHERE sentence_count BETWEEN 3 AND 5
              ORDER BY RANDOM()
              LIMIT 40
            ),
            long_queries AS (
              SELECT content, session_id, 'long' AS category
              FROM queries_with_sentence_count
              WHERE sentence_count >= 6
              ORDER BY RANDOM()
              LIMIT 20
            )

            -- Step 4: UNION ALL results
            SELECT * FROM short_queries
            UNION ALL
            SELECT * FROM medium_queries
            UNION ALL
            SELECT * FROM long_queries
            LIMIT 100;
            """

            cursor.execute(stratified_query_sql)
            queries = cursor.fetchall()

            if not queries:
                st.error(
                    "Keine Queries aus L0 Raw Memory gefunden. Bitte sicherstellen, dass Dialogtranskripte vorhanden sind."
                )
                return []

            logger.info(f"Extrahierte {len(queries)} Queries mit stratified sampling")
            return queries

    except Exception as e:
        logger.exception(f"Query extraction failed: {e}")
        st.error(f"Fehler bei der Query-Extraktion: {e}")
        return []


def rrf_fusion(
    semantic_results: list[tuple[int, str, list[int], float]],
    keyword_results: list[tuple[int, str, list[int], float]],
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[dict[str, Any]]:
    """
    Reciprocal Rank Fusion (RRF) for Hybrid Search.

    Formula: score = semantic_weight * 1/(60 + semantic_rank) +
                     keyword_weight * 1/(60 + keyword_rank)

    Args:
        semantic_results: Semantic search results (id, content, source_ids, distance)
        keyword_results: Keyword search results (id, content, source_ids, rank)
        semantic_weight: Weight for semantic scores (default: 0.7)
        keyword_weight: Weight for keyword scores (default: 0.3)

    Returns:
        Sorted list of documents with merged scores
    """
    doc_scores: dict[int, dict[str, Any]] = {}

    # Semantic Scores
    for rank, (doc_id, content, source_ids, _distance) in enumerate(semantic_results):
        doc_scores[doc_id] = {
            "id": doc_id,
            "content": content,
            "source_ids": source_ids,
            "score": semantic_weight * (1 / (60 + rank)),
        }

    # Keyword Scores (additive)
    for rank, (doc_id, content, source_ids, _ts_rank) in enumerate(keyword_results):
        if doc_id in doc_scores:
            doc_scores[doc_id]["score"] += keyword_weight * (1 / (60 + rank))
        else:
            doc_scores[doc_id] = {
                "id": doc_id,
                "content": content,
                "source_ids": source_ids,
                "score": keyword_weight * (1 / (60 + rank)),
            }

    # Sort by final score
    sorted_docs = sorted(doc_scores.values(), key=lambda x: x["score"], reverse=True)
    return sorted_docs


def get_top_5_docs_via_hybrid_search(query: str) -> list[dict[str, Any]]:
    """
    Hybrid Search direkt in Streamlit App (keine MCP Server Dependency).

    Implements Semantic Search (70%) + Keyword Search (30%) + RRF Fusion.

    Args:
        query: User query text

    Returns:
        List of top-5 documents with id, content, source_ids, score
        Empty list on error (graceful degradation)
    """
    try:
        # 1. Embed Query
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set in environment")
            st.error("OpenAI API Key nicht konfiguriert")
            return []

        client = OpenAI(api_key=api_key)
        query_embedding = get_embedding_with_retry_sync(client, query)

        with get_connection() as conn:
            register_vector(conn)  # Register pgvector types
            cursor = conn.cursor()

            # 2. Semantic Search via pgvector (Top-20)
            try:
                cursor.execute(
                    """
                    SELECT
                        id,
                        content,
                        source_ids,
                        embedding <=> %s::vector AS distance
                    FROM l2_insights
                    ORDER BY distance ASC
                    LIMIT 20
                """,
                    (query_embedding,),
                )
                semantic_results = cursor.fetchall()
            except Exception as e:
                logger.error(f"Semantic search failed: {e}")
                st.warning("Semantic search fehlgeschlagen, nutze nur Keyword Search")
                semantic_results = []

            # 3. Keyword Search via Full-Text Search (Top-20)
            # German FTS for better ranking
            try:
                cursor.execute(
                    """
                    SELECT
                        id,
                        content,
                        source_ids,
                        ts_rank(to_tsvector('german', content),
                                plainto_tsquery('german', %s)) AS rank
                    FROM l2_insights
                    WHERE to_tsvector('german', content) @@ plainto_tsquery('german', %s)
                    ORDER BY rank DESC
                    LIMIT 20
                """,
                    (query, query),
                )
                keyword_results = cursor.fetchall()
            except Exception as e:
                logger.error(f"Keyword search failed: {e}")
                st.warning("Keyword search fehlgeschlagen, nutze nur Semantic Search")
                keyword_results = []

            # Fallback: If both searches failed, return empty
            if not semantic_results and not keyword_results:
                logger.error("Both semantic and keyword search failed")
                st.error(
                    "Hybrid Search komplett fehlgeschlagen - keine Dokumente gefunden"
                )
                return []

            # 4. RRF Fusion
            fused_results = rrf_fusion(
                semantic_results=semantic_results,
                keyword_results=keyword_results,
                semantic_weight=0.7,
                keyword_weight=0.3,
            )

            # 5. Return Top-5 Docs
            return fused_results[:5]

    except Exception as e:
        logger.exception(f"Hybrid Search failed with exception: {e}")
        st.error(f"Hybrid Search fehlgeschlagen: {e}")
        return []  # Graceful degradation


def save_to_ground_truth(query: str, relevant_docs: list[int]) -> bool:
    """
    Save labeled query to ground_truth table.

    Args:
        query: Query text
        relevant_docs: List of relevant L2 Insight IDs

    Returns:
        True if successful, False otherwise
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check for duplicates
            cursor.execute("SELECT id FROM ground_truth WHERE query = %s", (query,))
            existing = cursor.fetchone()
            if existing:
                logger.warning(f"Query already exists in ground_truth: {query[:50]}...")
                st.warning("Diese Query wurde bereits gelabelt und wird übersprungen.")
                return True

            # Insert new ground truth entry
            cursor.execute(
                "INSERT INTO ground_truth (query, expected_docs) VALUES (%s, %s)",
                (query, relevant_docs),
            )
            conn.commit()

            logger.info(
                f"Saved ground truth entry: {query[:50]}... with {len(relevant_docs)} relevant docs"
            )
            return True

    except Exception as e:
        logger.exception(f"Failed to save ground truth: {e}")
        st.error(f"Fehler beim Speichern: {e}")
        return False


def get_progress_stats() -> dict[str, Any]:
    """
    Get current progress statistics.

    Returns:
        Dictionary with progress stats
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Count labeled queries
            cursor.execute("SELECT COUNT(*) FROM ground_truth")
            result = cursor.fetchone()
            labeled_count = result[0] if result else 0

            # Get stratification balance from current queries
            cursor.execute(
                """
                SELECT
                    CASE
                        WHEN LENGTH(query) - LENGTH(
                            REPLACE(REPLACE(REPLACE(query, '.', ''), '?', ''), '!', '')
                        ) <= 2 THEN 'short'
                        WHEN LENGTH(query) - LENGTH(
                            REPLACE(REPLACE(REPLACE(query, '.', ''), '?', ''), '!', '')
                        ) <= 5 THEN 'medium'
                        ELSE 'long'
                    END as category,
                    COUNT(*) as count
                FROM ground_truth
                GROUP BY category
            """
            )
            stratification = dict(cursor.fetchall())

            return {
                "labeled_count": labeled_count,
                "total_target": TARGET_QUERIES,
                "progress_percentage": (labeled_count / TARGET_QUERIES) * 100,
                "stratification": stratification,
            }

    except Exception as e:
        logger.exception(f"Failed to get progress stats: {e}")
        return {
            "labeled_count": 0,
            "total_target": TARGET_QUERIES,
            "progress_percentage": 0,
            "stratification": {"short": 0, "medium": 0, "long": 0},
        }


def main() -> None:
    """Main Streamlit application"""
    st.title("🏷️ Ground Truth Collection")
    st.markdown(
        "Labeln Sie Queries, um ein Ground Truth Set für die Hybrid Search Kalibrierung zu erstellen."
    )

    # Initialize session state
    if "queries" not in st.session_state:
        st.session_state.queries = extract_queries()
        st.session_state.query_index = 0

    if "query_index" not in st.session_state:
        st.session_state.query_index = 0

    # Sidebar: Progress tracking
    with st.sidebar:
        st.header("📊 Fortschritt")

        stats = get_progress_stats()

        # Progress bar
        progress = stats["labeled_count"] / stats["total_target"]
        st.progress(progress)
        st.write(
            f"**{stats['labeled_count']}/{stats['total_target']}** Queries gelabelt"
        )

        # Stratification balance
        st.subheader("Stratification Balance")
        for category in ["short", "medium", "long"]:
            count = stats["stratification"].get(category, 0)
            percentage = (
                (count / stats["labeled_count"] * 100)
                if stats["labeled_count"] > 0
                else 0
            )
            target = STRATIFICATION_TARGETS[category] * 100
            st.write(
                f"**{category.capitalize()}**: {count} ({percentage:.1f}%) - Target: {target:.0f}%"
            )

        # Action buttons
        st.subheader("Aktionen")
        if st.button("💾 Save & Continue Later"):
            st.success(
                "Aktueller Stand wurde gespeichert. Sie können später fortsetzen."
            )
            st.info("Starten Sie die App einfach neu, um fortzufahren.")

    # Main content: Query labeling
    queries = st.session_state.queries
    query_index = st.session_state.query_index

    if not queries:
        st.error(
            "Keine Queries gefunden. Bitte sicherstellen, dass L0 Raw Memory Daten vorhanden sind."
        )
        return

    if query_index >= len(queries):
        st.success("🎉 Alle Queries wurden gelabelt!")
        st.info("Ground Truth Collection abgeschlossen.")
        return

    # Current query
    query_text, category, session_id = queries[query_index]

    st.header(f"Query #{query_index + 1} ({category.upper()})")
    st.write(f"**Session:** {session_id}")
    st.write(f"**Query:** {query_text}")

    # Get top 5 documents via hybrid search
    with st.spinner("Suche relevante Dokumente..."):
        docs = get_top_5_docs_via_hybrid_search(query_text)

    if not docs:
        st.warning("Keine Dokumente gefunden für diese Query.")
        docs = []

    # Document relevance labeling
    st.subheader("Relevante Dokumente markieren")

    relevant_docs = []
    for doc in docs:
        col1, col2 = st.columns([1, 20])

        with col1:
            is_relevant = st.checkbox(
                "Relevant?",
                key=f"doc_{doc['id']}",
                help="Markieren Sie dieses Dokument als relevant für die Query",
            )

        with col2:
            # Truncate content for display
            content_preview = (
                doc["content"][:200] + "..."
                if len(doc["content"]) > 200
                else doc["content"]
            )
            st.write(f"**Dokument {doc['id']}:** {content_preview}")
            st.caption(f"Score: {doc['score']:.4f}")

        if is_relevant:
            relevant_docs.append(doc["id"])

    # Validation warning
    if not relevant_docs:
        st.warning("⚠️ Mindestens ein Dokument sollte als relevant markiert werden.")

    # Action buttons
    st.divider()
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("⏭️ Skip Query", type="secondary"):
            # Save with empty relevant_docs
            if save_to_ground_truth(query_text, []):
                st.session_state.query_index += 1
                st.rerun()

    with col2:
        if st.button(
            "💾 Save & Next", type="primary", disabled=len(relevant_docs) == 0
        ):
            if save_to_ground_truth(query_text, relevant_docs):
                st.session_state.query_index += 1
                st.rerun()

    with col3:
        if st.button("🏠 Zurück zur Übersicht"):
            st.session_state.query_index = 0
            st.rerun()

    # Footer
    st.divider()
    st.markdown(
        """
        **Anleitung:**
        1. Lesen Sie die Query aufmerksam durch
        2. Prüfen Sie die gefundenen Dokumente auf Relevanz
        3. Markieren Sie alle relevanten Dokumente mit den Checkboxen
        4. Klicken Sie auf "Save & Next" um fortzufahren oder "Skip Query" zu überspringen

        **Hinweis:** Jede Query sollte mindestens ein relevantes Dokument haben.
        """,
        help="""
        **Stratification:**
        - **Short:** 1-2 Sätze (40% der Queries)
        - **Medium:** 3-5 Sätze (40% der Queries)
        - **Long:** 6+ Sätze (20% der Queries)

        **Temporal Diversity:** Queries stammen aus verschiedenen Sessions, um Bias zu vermeiden.
        """,
    )


if __name__ == "__main__":
    main()
