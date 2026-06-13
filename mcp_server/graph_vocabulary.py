"""
Graph Vocabulary Enforcement — project-specific Label/Relation whitelists.

This module holds the *closed* graph vocabularies (node labels + edge relations)
per project_id and provides the enforcement primitives used by the graph tools.

Behaviour contract (Graph-Enforcement-Schicht, 2026-06-12):
  - A project WITH a configured vocabulary -> violations are REJECTED (hard block).
  - A project WITHOUT a configured vocabulary (io, ab, njord, ...) -> unchanged
    warning-only behaviour, the node/edge is still created.

This keeps the blast radius limited to projects that explicitly opted in via a
vocabulary entry below; every other project behaves exactly as before.

SOURCE OF TRUTH
---------------
The authoritative definition of the `tethr` vocabulary lives in:
    tethr/data/core/schema/graph-taxonomy.md  (v1.0)
The constants below MIRROR that file. When the taxonomy file changes
(Stefan-Entscheidung + Versions-Sprung), update this module in the same step.
Do not edit the vocabulary here without updating graph-taxonomy.md first.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# tethr vocabulary — mirror of graph-taxonomy.md v1.0
# ---------------------------------------------------------------------------

# Knoten-Labels (geschlossen, 9) — "is a"-Logik: genau ein Label pro Knoten.
TETHR_LABELS: frozenset[str] = frozenset({
    "Person",
    "Agent",
    "Commitment",
    "Pattern",
    "Framework",
    "Area",
    "Protocol",
    "Diagnosis",
    "Project",
})

# Kanten-Verben (geschlossen, 15) — RELATES_TO ist der Druckablass-Sammelbezug.
TETHR_RELATIONS: frozenset[str] = frozenset({
    "COMMITTED_TO",
    "KNOWS",
    "PRACTICES",
    "PURSUES",
    "EXHIBITS",
    "COUNTERACTS",
    "LEADS_TO",
    "PART_OF",
    "REQUIRES",
    "IMPLEMENTS",
    "SUPPORTS",
    "DEVELOPS",
    "SIMILAR_TO",
    "EVIDENCED_BY",
    "RELATES_TO",
})


# ---------------------------------------------------------------------------
# Registry: project_id -> {"labels": frozenset, "relations": frozenset}
# ---------------------------------------------------------------------------
# Only projects listed here are hard-enforced. Everything else stays
# warning-only (global STANDARD_LABELS / STANDARD_RELATIONS in the tool files).
PROJECT_VOCABULARIES: dict[str, dict[str, frozenset[str]]] = {
    "tethr": {
        "labels": TETHR_LABELS,
        "relations": TETHR_RELATIONS,
    },
}


def is_vocabulary_enforced(project_id: str | None) -> bool:
    """Return True if the given project has a hard-enforced vocabulary."""
    return project_id in PROJECT_VOCABULARIES


def get_allowed_labels(project_id: str | None) -> frozenset[str] | None:
    """Return the allowed labels for a project, or None if not enforced."""
    vocab = PROJECT_VOCABULARIES.get(project_id or "")
    return vocab["labels"] if vocab else None


def get_allowed_relations(project_id: str | None) -> frozenset[str] | None:
    """Return the allowed relations for a project, or None if not enforced."""
    vocab = PROJECT_VOCABULARIES.get(project_id or "")
    return vocab["relations"] if vocab else None


def validate_label(project_id: str | None, label: str) -> str | None:
    """
    Validate a node label against the project vocabulary.

    Returns:
        None if the label is allowed (or the project is not enforced).
        An error message string (naming the allowed list) if rejected.
    """
    allowed = get_allowed_labels(project_id)
    if allowed is None:
        return None  # project not enforced -> warning-only handled by caller
    if label in allowed:
        return None
    return (
        f"Invalid label '{label}' for project '{project_id}'. "
        f"Allowed labels (graph-taxonomy.md v1.0): {sorted(allowed)}"
    )


def validate_relation(project_id: str | None, relation: str) -> str | None:
    """
    Validate an edge relation against the project vocabulary.

    Returns:
        None if the relation is allowed (or the project is not enforced).
        An error message string (naming the allowed list) if rejected.
    """
    allowed = get_allowed_relations(project_id)
    if allowed is None:
        return None  # project not enforced -> warning-only handled by caller
    if relation in allowed:
        return None
    return (
        f"Invalid relation '{relation}' for project '{project_id}'. "
        f"Allowed relations (graph-taxonomy.md v1.0): {sorted(allowed)}"
    )
