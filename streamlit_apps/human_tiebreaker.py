"""
Human Tiebreaker UI for Story 1.12

Streamlit application for manual review of high-disagreement queries
when IRR validation shows Cohen's Kappa < 0.70.

Features:
- Display queries with highest judge disagreement
- Show GPT-4o vs Haiku scores side-by-side
- Allow manual relevance decisions
- Progress tracking through disputed queries
- Save human overrides to database
"""

import logging
import os
import sys
from datetime import datetime

import streamlit as st

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.validation.contingency import (
    ContingencyManager,
    HighDisagreementAnalyzer,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Human Tiebreaker - Ground Truth Validation",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown(
    """
<style>
.metric-container {
    background-color: #f0f2f6;
    padding: 1rem;
    border-radius: 0.5rem;
    border: 1px solid #e0e0e0;
}
.query-container {
    background-color: #fafafa;
    padding: 1rem;
    border-radius: 0.5rem;
    border: 1px solid #ddd;
    margin-bottom: 1rem;
}
.score-high { color: #d32f2f; font-weight: bold; }
.score-medium { color: #f57c00; font-weight: bold; }
.score-low { color: #388e3c; font-weight: bold; }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if "current_query_index" not in st.session_state:
        st.session_state.current_query_index = 0
    if "disagreement_queries" not in st.session_state:
        st.session_state.disagreement_queries = []
    if "user_decisions" not in st.session_state:
        st.session_state.user_decisions = {}
    if "validation_completed" not in st.session_state:
        st.session_state.validation_completed = False
    if "contingency_manager" not in st.session_state:
        st.session_state.contingency_manager = ContingencyManager()


def load_disagreement_queries() -> list[dict]:
    """Load high-disagreement queries from database"""
    try:
        analyzer = HighDisagreementAnalyzer()
        queries = analyzer.identify_high_disagreement_queries(limit=50)
        logger.info(f"Loaded {len(queries)} high-disagreement queries")
        return queries
    except Exception as e:
        st.error(f"Fehler beim Laden der Queries: {e}")
        logger.error(f"Error loading disagreement queries: {e}")
        return []


def save_user_decision(query_id: int, relevant_docs: list[int], reason: str):
    """Save user decision to database"""
    try:
        manager = st.session_state.contingency_manager
        manager.save_human_override(query_id, relevant_docs, reason)
        logger.info(
            f"Saved decision for query {query_id}: {len(relevant_docs)} relevant docs, reason: {reason}"
        )
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern der Entscheidung: {e}")
        logger.error(f"Error saving decision: {e}")
        return False


def get_score_color(score: float) -> str:
    """Get color class based on score value"""
    if score > 0.7:
        return "score-high"
    elif score > 0.4:
        return "score-medium"
    else:
        return "score-low"


def format_score_comparison(score1: float, score2: float) -> str:
    """Format score comparison with disagreement highlighting"""
    diff = abs(score1 - score2)
    color_class = (
        "score-high" if diff > 0.5 else "score-medium" if diff > 0.3 else "score-low"
    )
    return f'<span class="{color_class}">Δ{diff:.2f}</span>'


def display_query_overview(query: dict):
    """Display query overview and statistics"""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Query ID", query["id"], help="Eindeutige Kennung des Queries")

    with col2:
        st.metric(
            "Cohen's Kappa",
            f"{query['kappa']:.3f}",
            help="Übereinstimmung zwischen den beiden Judges",
        )

    with col3:
        st.metric(
            "Durchschnittliche Disagreement",
            f"{query['avg_disagreement']:.3f}",
            help="Mittlere absolute Differenz der Judge-Scores",
        )

    with col4:
        st.metric(
            "Progress",
            f"{st.session_state.current_query_index + 1}/{len(st.session_state.disagreement_queries)}",
            help="Fortschritt durch die Disagreement Queries",
        )

    # Display the query text
    st.markdown("### Query Text")
    st.markdown(f"**{query['query']}**")
    st.markdown("---")


def display_judge_scores(query: dict):
    """Display judge scores side by side"""
    st.markdown("### Judge Scores Comparison")

    if not query["judge1_score"] or not query["judge2_score"]:
        st.warning("Keine gültigen Judge-Scores verfügbar")
        return

    # Create columns for side-by-side comparison
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### GPT-4o Judge")
        st.markdown(f"*Durchschnitt: {query['avg_judge1']:.3f}*")

        # Display top disagreement documents
        if query["top_disagreements"]:
            st.markdown("**Top Disagreements:**")
            for disagreement in query["top_disagreements"][:5]:
                doc_idx = disagreement["doc_index"]
                score1 = disagreement["judge1_score"]
                score2 = disagreement["judge2_score"]
                diff = disagreement["disagreement"]

                st.markdown(
                    f"""
                **Doc {doc_idx}:**
                - GPT-4o: {score1:.2f}
                - Haiku: {score2:.2f}
                - Disagreement: {diff:.2f}
                """,
                    unsafe_allow_html=True,
                )

        # Display all scores in a table
        st.markdown("**Alle Scores:**")
        score_data = []
        for i, (score1, _) in enumerate(
            zip(query["judge1_score"], query["judge2_score"], strict=False)
        ):
            score_data.append({"Doc": i, "Score": score1, "Relevant": score1 > 0.5})
        st.dataframe(score_data, use_container_width=True)

    with col2:
        st.markdown("#### Haiku Judge")
        st.markdown(f"*Durchschnitt: {query['avg_judge2']:.3f}*")

        # Display top disagreement documents (mirror of left side)
        if query["top_disagreements"]:
            st.markdown("**Top Disagreements:**")
            for disagreement in query["top_disagreements"][:5]:
                doc_idx = disagreement["doc_index"]
                score1 = disagreement["judge1_score"]
                score2 = disagreement["judge2_score"]
                diff = disagreement["disagreement"]

                st.markdown(
                    f"""
                **Doc {doc_idx}:**
                - GPT-4o: {score1:.2f}
                - Haiku: {score2:.2f}
                - Disagreement: {diff:.2f}
                """,
                    unsafe_allow_html=True,
                )

        # Display all scores in a table
        st.markdown("**Alle Scores:**")
        score_data = []
        for i, (_, score2) in enumerate(
            zip(query["judge1_score"], query["judge2_score"], strict=False)
        ):
            score_data.append({"Doc": i, "Score": score2, "Relevant": score2 > 0.5})
        st.dataframe(score_data, use_container_width=True)


def display_user_interface(query: dict):
    """Display user decision interface"""
    st.markdown("### Your Decision")

    if not query["judge1_score"] or not query["judge2_score"]:
        st.error("Keine gültigen Daten für diese Query verfügbar")
        return

    # Explanation of the task
    with st.expander("📖 Anleitung", expanded=False):
        st.markdown(
            """
        **Ihre Aufgabe:**
        1. Überprüfen Sie die Query und die Dokumente
        2. Entscheiden Sie, welche Dokumente relevant für die Query sind
        3. Verwenden Sie die Checkboxen, um Relevanz zu markieren
        4. Fügen Sie eine Begründung für Ihre Entscheidung hinzu
        5. Speichern Sie Ihre Entscheidung

        **Relevanzkriterien:**
        - Beantwortet das Dokument die Query direkt?
        - Enthält es nützliche Informationen?
        - Ist der semantische Overlap ausreichend?
        """
        )

    # Create checkboxes for each document
    st.markdown("#### Relevanz-Entscheidung")

    current_decision = st.session_state.user_decisions.get(query["id"], {})
    selected_docs = current_decision.get("selected_docs", [])

    cols = st.columns(3)  # 3 columns for better layout
    relevant_docs = []

    for i, (score1, score2) in enumerate(
        zip(query["judge1_score"], query["judge2_score"], strict=False)
    ):
        col_idx = i % 3
        with cols[col_idx]:
            is_selected = i in selected_docs
            is_relevant = st.checkbox(
                f"**Doc {i}** Relevant? *(GPT-4o: {score1:.2f}, Haiku: {score2:.2f})*",
                value=is_selected,
                key=f"doc_{query['id']}_{i}",
                help=f"GPT-4o: {score1:.2f}, Haiku: {score2:.2f}",
            )
            if is_relevant:
                relevant_docs.append(i)

    # Reason for decision
    st.markdown("#### Begründung")
    reason = st.text_area(
        "Warum haben Sie diese Entscheidung getroffen?",
        value=current_decision.get("reason", ""),
        key=f"reason_{query['id']}",
        help="Beschreiben Sie kurz Ihre Entscheidungsgrundlage",
    )

    # Save button
    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button(
            "⬅️ Vorherige Query", disabled=st.session_state.current_query_index == 0
        ):
            st.session_state.current_query_index -= 1
            st.rerun()

    with col3:
        if st.button("💾 Entscheidung speichern", type="primary"):
            if relevant_docs:
                success = save_user_decision(query["id"], relevant_docs, reason)
                if success:
                    st.session_state.user_decisions[query["id"]] = {
                        "selected_docs": relevant_docs,
                        "reason": reason,
                        "timestamp": datetime.now(),
                    }
                    st.success("Entscheidung gespeichert!")

                    # Move to next query after successful save
                    if (
                        st.session_state.current_query_index
                        < len(st.session_state.disagreement_queries) - 1
                    ):
                        st.session_state.current_query_index += 1
                        st.rerun()
                    else:
                        st.session_state.validation_completed = True
                        st.rerun()
            else:
                st.warning("Bitte wählen Sie mindestens ein relevantes Dokument aus")

    with col2:
        st.markdown(
            f"<div style='text-align: center; padding: 0.5rem;'>"
            f"Dokumente ausgewählt: {len(relevant_docs)}</div>",
            unsafe_allow_html=True,
        )


def display_completion_summary():
    """Display completion summary when all queries are processed"""
    st.markdown("## ✅ Validierung abgeschlossen!")

    total_decisions = len(st.session_state.user_decisions)
    total_queries = len(st.session_state.disagreement_queries)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Verarbeitete Queries", total_decisions)

    with col2:
        st.metric("Übrige Queries", total_queries - total_decisions)

    with col3:
        completion_rate = (
            (total_decisions / total_queries * 100) if total_queries > 0 else 0
        )
        st.metric("Abschlussrate", f"{completion_rate:.1f}%")

    st.markdown("### Zusammenfassung Ihrer Entscheidungen")

    decision_summary = []
    for query_id, decision in st.session_state.user_decisions.items():
        decision_summary.append(
            {
                "Query ID": query_id,
                "Relevante Dokumente": len(decision["selected_docs"]),
                "Begründung": (
                    decision["reason"][:100] + "..."
                    if len(decision["reason"]) > 100
                    else decision["reason"]
                ),
                "Zeitpunkt": decision["timestamp"].strftime("%H:%M:%S"),
            }
        )

    if decision_summary:
        st.dataframe(decision_summary, use_container_width=True)

    st.markdown("### Nächste Schritte")

    st.info(
        """
    Ihre manuellen Entscheidungen wurden in der Datenbank gespeichert.
    Das System wird nun die IRR-Validierung mit Ihren Überbrückungen neu berechnen.

    **Empfohlene nächste Schritte:**
    1. Führen Sie die IRR-Validierung erneut aus
    2. Überprüfen Sie das neue Kappa-Ergebnis
    3. Bei Bedarf: Führen Sie weitere Kontingenzmaßnahmen durch
    """
    )

    if st.button("🔄 Zurück zum Anfang"):
        st.session_state.current_query_index = 0
        st.session_state.validation_completed = False
        st.rerun()


def main():
    """Main application entry point"""
    st.title("⚖️ Human Tiebreaker - Ground Truth Validation")
    st.markdown("Manuelle Überprüfung von Queries mit hoher Judge-Disagreement")

    # Initialize session state
    initialize_session_state()

    # Sidebar
    st.sidebar.markdown("## 📊 Status")
    st.sidebar.markdown(
        f"**Aktuelle Query:** {st.session_state.current_query_index + 1}/{len(st.session_state.disagreement_queries)}"
    )

    if st.sidebar.button("🔄 Neu laden"):
        st.session_state.disagreement_queries = load_disagreement_queries()
        st.session_state.current_query_index = 0
        st.session_state.user_decisions = {}
        st.session_state.validation_completed = False
        st.rerun()

    # Load data if needed
    if not st.session_state.disagreement_queries:
        with st.spinner("Lade Disagreement Queries..."):
            st.session_state.disagreement_queries = load_disagreement_queries()
            if not st.session_state.disagreement_queries:
                st.error(
                    "Keine Disagreement Queries gefunden. Stellen Sie sicher, dass:"
                )
                st.markdown("- Die Datenbankverbindung funktioniert")
                st.markdown("- Dual Judge Scores vorhanden sind")
                st.markdown("- IRR-Validierung vorher durchgeführt wurde")
                st.stop()

    # Main content
    if st.session_state.validation_completed:
        display_completion_summary()
    else:
        # Get current query
        if st.session_state.current_query_index < len(
            st.session_state.disagreement_queries
        ):
            current_query = st.session_state.disagreement_queries[
                st.session_state.current_query_index
            ]

            # Display query information
            display_query_overview(current_query)

            # Display judge scores
            display_judge_scores(current_query)

            # Display user interface
            display_user_interface(current_query)
        else:
            st.session_state.validation_completed = True
            st.rerun()

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📈 Statistiken")
    if st.session_state.disagreement_queries:
        avg_kappa = sum(
            q["kappa"] for q in st.session_state.disagreement_queries
        ) / len(st.session_state.disagreement_queries)
        avg_disagreement = sum(
            q["avg_disagreement"] for q in st.session_state.disagreement_queries
        ) / len(st.session_state.disagreement_queries)
        st.sidebar.metric("Durchschnitt Kappa", f"{avg_kappa:.3f}")
        st.sidebar.metric("Durchschnitt Disagreement", f"{avg_disagreement:.3f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"Anwendungsfehler: {e}")
        logger.error(f"Application error: {e}", exc_info=True)
