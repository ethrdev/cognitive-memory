"""
Consent policy: which projects require io co-signature (EP-1 bilateral consent)
for ethr-actor insight edits/deletes.

By default every project requires io co-sign for ethr-initiated mutations
(EP-1 Consent-Aware Pattern). Projects listed in DECOUPLED_PROJECTS are exempt:
their ethr actor edits its own (project-isolated) insights directly, symmetric
to how I/O manages its own memories. io / ab / njord stay on the default and
are unaffected.

Decision: Stefan, 2026-06-15 — tethr's insights are project-isolated
(io_category = NULL for all of them), so requiring io co-approval over
tethr-only data is over-coupling. Modeled on graph_vocabulary.is_vocabulary_enforced.
"""

from __future__ import annotations

# Projects exempt from io co-sign for ethr-actor insight mutations.
# Everything NOT in this set keeps the default bilateral (EP-1) behavior.
DECOUPLED_PROJECTS: frozenset[str] = frozenset({"tethr"})


def requires_io_cosign(project_id: str | None) -> bool:
    """Return True if ethr-actor insight edits in this project need io co-sign.

    Default True (EP-1 bilateral). False only for DECOUPLED_PROJECTS, where
    ethr edits execute directly (like I/O over its own memories).
    A None / unknown project_id defaults to True (safe: keep co-sign).
    """
    return project_id not in DECOUPLED_PROJECTS
