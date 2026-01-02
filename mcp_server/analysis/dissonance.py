"""
Dissonance Engine for detecting conflicts in self-narrative.

This module provides functionality to detect and classify dissonances
between edges in the knowledge graph based on AGM belief revision theory.
"""

import json
import logging
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

from mcp_server.db.connection import get_connection
from mcp_server.db.graph import get_or_create_node, add_edge, get_edge_by_id
from mcp_server.external.anthropic_client import HaikuClient
from mcp_server.analysis.smf import (
    TriggerType, ApprovalLevel, create_smf_proposal,
    generate_neutral_reasoning, validate_neutrality, validate_safeguards, IMMUTABLE_SAFEGUARDS
)

logger = logging.getLogger(__name__)


class DissonanceType(Enum):
    """Classification of dissonance types."""
    EVOLUTION = "evolution"      # Entwicklung: früher X, jetzt Y
    CONTRADICTION = "contradiction"  # Echter Widerspruch
    NUANCE = "nuance"            # Spannung die okay ist
    NONE = "none"               # Kein Konflikt


class EntrenchmentLevel(Enum):
    """AGM Belief Revision entrenchment levels."""
    DEFAULT = "default"          # Deskriptive Edges
    MAXIMAL = "maximal"          # Konstitutive Edges (AGM-Prinzip)


@dataclass
class DissonanceResult:
    """Einzelnes Dissonanz-Ergebnis zwischen zwei Edges."""
    edge_a_id: str
    edge_b_id: str
    dissonance_type: DissonanceType
    confidence_score: float  # 0.0-1.0
    description: str
    context: dict[str, Any]  # Zusätzliche Metadaten
    requires_review: bool = False  # True für NUANCE
    # GAP-3 Fix: Memory Strength Integration (AC #11)
    edge_a_memory_strength: float | None = None  # Von l2_insights.memory_strength
    edge_b_memory_strength: float | None = None
    authoritative_source: str | None = None  # "edge_a" | "edge_b" | None


@dataclass
class DissonanceCheckResult:
    """Gesamtergebnis einer Dissonanz-Prüfung."""
    context_node: str
    scope: str  # "recent" | "full"
    edges_analyzed: int
    conflicts_found: int
    dissonances: list[DissonanceResult]
    pending_reviews: list[DissonanceResult]  # NUANCE mit PENDING_IO_REVIEW
    # GAP-2 Fix: Fallback Behavior (AC #9)
    fallback: bool = False  # True wenn Haiku API unavailable war
    status: str = "success"  # "success" | "skipped" | "insufficient_data"
    # GAP-1 Fix: Cost Tracking (Task 8)
    api_calls: int = 0
    total_tokens: int = 0
    estimated_cost_eur: float = 0.0


@dataclass
class NuanceReviewProposal:
    """Proposal für NUANCE-Klassifikation Review durch I/O."""
    id: str  # UUID
    dissonance: DissonanceResult
    status: str  # "PENDING_IO_REVIEW" | "CONFIRMED" | "RECLASSIFIED"
    reclassified_to: DissonanceType | None
    review_reason: str | None
    created_at: str  # ISO timestamp
    reviewed_at: str | None


# In-Memory Storage for NUANCE Reviews (MVP analog Audit-Log Pattern)
_nuance_reviews: list[dict[str, Any]] = []


class DissonanceEngine:
    """
    Engine for detecting and classifying dissonances in knowledge graph edges.

    Based on AGM belief revision theory for handling contradictions in
    constitutive knowledge graphs.
    """

    def __init__(self, haiku_client: Optional[HaikuClient] = None):
        """Initialize the dissonance engine."""
        self.haiku_client = haiku_client or HaikuClient()

    async def dissonance_check(
        self,
        context_node: str,
        scope: str = "recent"
    ) -> DissonanceCheckResult:
        """
        Prüft Edges auf Dissonanzen und klassifiziert Konflikte.

        Args:
            context_node: Name des Nodes dessen Edges geprüft werden (z.B. "I/O")
            scope: "recent" (30 Tage) oder "full" (alle Edges)

        Returns:
            DissonanceCheckResult mit gefundenen Dissonanzen
        """
        # Validate scope parameter
        if scope not in ["recent", "full"]:
            raise ValueError(f"Invalid scope '{scope}'. Must be 'recent' or 'full'")

        # Validate UUID format for context_node
        if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', context_node):
            # If not UUID, try to find node by name
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id FROM nodes WHERE name = %s",
                    (context_node,)
                )
                result = cursor.fetchone()
                if not result:
                    logger.warning(f"Context node '{context_node}' not found")
                    return DissonanceCheckResult(
                        context_node=context_node,
                        scope=scope,
                        edges_analyzed=0,
                        conflicts_found=0,
                        dissonances=[],
                        pending_reviews=[],
                        status="insufficient_data"
                    )
                context_node = result["id"]

        try:
            # Fetch edges based on scope
            edges = self._fetch_edges(context_node, scope)

            # Check for insufficient data (AC #10)
            if len(edges) < 2:
                logger.info(f"Insufficient data for dissonance check: {len(edges)} edges found")
                return DissonanceCheckResult(
                    context_node=context_node,
                    scope=scope,
                    edges_analyzed=len(edges),
                    conflicts_found=0,
                    dissonances=[],
                    pending_reviews=[],
                    status="insufficient_data"
                )

            # Analyze pairs for dissonances
            dissonances = []
            pending_reviews = []
            api_calls = 0
            total_tokens = 0
            estimated_cost = 0.0

            # HIGH-3 Fix: Limit O(n²) API calls to max 10 pairs
            # MCP transport has timeout (~30-60s), so limit to ~10 API calls
            # Each Haiku call takes ~3-6 seconds
            # 10 pairs × 5s = 50s (within timeout)
            MAX_PAIRS = 10
            pairs_analyzed = 0

            # Generate all unique pairs of edges (with limit)
            limit_reached = False
            for i in range(len(edges)):
                if limit_reached:
                    break
                for j in range(i + 1, len(edges)):
                    # Cost protection: stop after MAX_PAIRS
                    if pairs_analyzed >= MAX_PAIRS:
                        logger.warning(
                            f"Reached max pair limit ({MAX_PAIRS}). "
                            f"Analyzed {pairs_analyzed} of {len(edges) * (len(edges) - 1) // 2} possible pairs."
                        )
                        limit_reached = True
                        break

                    pairs_analyzed += 1
                    edge_a = edges[i]
                    edge_b = edges[j]

                    try:
                        # Use LLM to analyze dissonance
                        result = await self._analyze_dissonance_pair(edge_a, edge_b)

                        # Track API call regardless of result
                        api_calls += 1

                        if result.dissonance_type != DissonanceType.NONE:
                            # Fetch memory strength for both edges (AC #11)
                            memory_strength_a = self._get_memory_strength(str(edge_a["id"]))
                            memory_strength_b = self._get_memory_strength(str(edge_b["id"]))

                            result.edge_a_memory_strength = memory_strength_a
                            result.edge_b_memory_strength = memory_strength_b

                            # Set authoritative source based on memory strength
                            if memory_strength_a is not None and memory_strength_b is not None:
                                result.authoritative_source = "edge_a" if memory_strength_a > memory_strength_b else "edge_b"

                            dissonances.append(result)

                            # Create review proposal for NUANCE classifications (AC #6)
                            if result.dissonance_type == DissonanceType.NUANCE:
                                self.create_nuance_review(result)
                                pending_reviews.append(result)
                                result.requires_review = True

                            # SMF Integration: Create proposal for all detected dissonances (Story 7.9)
                            await self.create_smf_proposal(result, edge_a, edge_b)

                    except Exception as e:
                        # MED-3 Fix: Propagate API errors for proper fallback handling
                        error_msg = str(e).lower()
                        if "haiku" in error_msg or "api" in error_msg or "anthropic" in error_msg:
                            # API failure - propagate to trigger fallback in outer try/catch
                            logger.error(f"Haiku API error during edge pair analysis: {e}")
                            raise  # Re-raise to trigger fallback logic
                        # Non-API errors: continue with other pairs
                        logger.warning(f"Failed to analyze edge pair {edge_a['id']}-{edge_b['id']}: {e}")
                        continue

            # Log completion
            logger.info(f"Dissonance check completed: {len(edges)} edges, {len(dissonances)} conflicts found")

            return DissonanceCheckResult(
                context_node=context_node,
                scope=scope,
                edges_analyzed=len(edges),
                conflicts_found=len(dissonances),
                dissonances=dissonances,
                pending_reviews=pending_reviews,
                api_calls=api_calls,
                total_tokens=total_tokens,
                estimated_cost_eur=estimated_cost,
                status="success"
            )

        except Exception as e:
            logger.error(f"Dissonance check failed: {e}")
            # Fallback behavior for API unavailability (AC #9)
            if "Haiku" in str(e) or "API" in str(e):
                logger.warning("Haiku API unavailable, returning empty dissonance list")
                return DissonanceCheckResult(
                    context_node=context_node,
                    scope=scope,
                    edges_analyzed=0,
                    conflicts_found=0,
                    dissonances=[],
                    pending_reviews=[],
                    fallback=True,
                    status="skipped"
                )
            raise

    def _fetch_edges(self, context_node_id: str, scope: str) -> list[dict[str, Any]]:
        """Fetch edges based on scope criteria."""
        with get_connection() as conn:
            cursor = conn.cursor()

            if scope == "recent":
                # Get session start time (default to 30 days ago if not available)
                session_start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

                # NULL-safe UUID cast: only attempt cast if value is valid UUID format
                query = """
                    SELECT DISTINCT e.*,
                           ns.name as source_name, nt.name as target_name,
                           pns.name as source_node_name, pnt.name as target_node_name
                    FROM edges e
                    JOIN nodes ns ON e.source_id = ns.id
                    JOIN nodes nt ON e.target_id = nt.id
                    LEFT JOIN nodes pns ON
                        e.properties->>'source_node' IS NOT NULL
                        AND e.properties->>'source_node' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        AND (e.properties->>'source_node')::uuid = pns.id
                    LEFT JOIN nodes pnt ON
                        e.properties->>'target_node' IS NOT NULL
                        AND e.properties->>'target_node' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        AND (e.properties->>'target_node')::uuid = pnt.id
                    WHERE (ns.name = %s OR nt.name = %s OR ns.id = %s OR nt.id = %s)
                    AND (
                        e.modified_at >= NOW() - INTERVAL '30 days'
                        OR e.last_accessed >= NOW() - INTERVAL '30 days'
                        OR e.created_at >= %s
                    )
                    ORDER BY e.modified_at DESC
                """
                cursor.execute(query, (context_node_id, context_node_id, context_node_id, context_node_id, session_start))
            else:  # scope == "full"
                # NULL-safe UUID cast: only attempt cast if value is valid UUID format
                query = """
                    SELECT DISTINCT e.*,
                           ns.name as source_name, nt.name as target_name,
                           pns.name as source_node_name, pnt.name as target_node_name
                    FROM edges e
                    JOIN nodes ns ON e.source_id = ns.id
                    JOIN nodes nt ON e.target_id = nt.id
                    LEFT JOIN nodes pns ON
                        e.properties->>'source_node' IS NOT NULL
                        AND e.properties->>'source_node' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        AND (e.properties->>'source_node')::uuid = pns.id
                    LEFT JOIN nodes pnt ON
                        e.properties->>'target_node' IS NOT NULL
                        AND e.properties->>'target_node' ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                        AND (e.properties->>'target_node')::uuid = pnt.id
                    WHERE (ns.name = %s OR nt.name = %s OR ns.id = %s OR nt.id = %s)
                    ORDER BY e.modified_at DESC
                """
                cursor.execute(query, (context_node_id, context_node_id, context_node_id, context_node_id))

            return [dict(row) for row in cursor.fetchall()]

    def _get_memory_strength(self, edge_id: str) -> Optional[float]:
        """
        Get memory strength for an edge from related l2_insights.

        LIMITATION (Story 7.4 Review):
        Currently l2_insights table does not have memory_strength column.
        This is a placeholder for future implementation. Always returns None.

        Returns None - authoritative_source will be None.
        """
        # NOTE: l2_insights schema doesn't include memory_strength column yet.
        # This feature requires a schema migration to add the column.
        # For now, return None to avoid DB errors.
        return None

    async def _analyze_dissonance_pair(self, edge_a: dict, edge_b: dict) -> DissonanceResult:
        """Analyze a pair of edges for dissonance using LLM."""

        # Parse edge properties (handle both string and dict formats)
        props_a_raw = edge_a.get("properties", "{}")
        props_b_raw = edge_b.get("properties", "{}")

        if isinstance(props_a_raw, dict):
            props_a = props_a_raw
        else:
            try:
                props_a = json.loads(props_a_raw) if props_a_raw else {}
            except json.JSONDecodeError:
                props_a = {}

        if isinstance(props_b_raw, dict):
            props_b = props_b_raw
        else:
            try:
                props_b = json.loads(props_b_raw) if props_b_raw else {}
            except json.JSONDecodeError:
                props_b = {}

        # Prepare prompt with edge information
        prompt = DISSONANCE_CLASSIFICATION_PROMPT.format(
            edge_a_relation=edge_a.get("relation", "unknown"),
            edge_a_source=edge_a.get("source_name", "unknown"),
            edge_a_target=edge_a.get("target_name", "unknown"),
            edge_a_properties=json.dumps(props_a, indent=2),
            edge_a_created=edge_a.get("created_at", "unknown"),
            edge_b_relation=edge_b.get("relation", "unknown"),
            edge_b_source=edge_b.get("source_name", "unknown"),
            edge_b_target=edge_b.get("target_name", "unknown"),
            edge_b_properties=json.dumps(props_b, indent=2),
            edge_b_created=edge_b.get("created_at", "unknown")
        )

        # Call Haiku API with retry logic (will be implemented in Task 3)
        try:
            response = await self.haiku_client.generate_response(
                prompt=prompt,
                temperature=0.0,  # Deterministic classification
                max_tokens=500     # Sufficient for JSON response
            )

            # Extract JSON from response (Haiku may include surrounding text)
            if "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
            else:
                raise ValueError(f"No JSON found in response: {response[:100]}")

            # Parse JSON response
            result_data = json.loads(json_str)

            # Normalize dissonance_type to lowercase for enum matching
            raw_type = result_data["dissonance_type"]
            normalized_type = raw_type.lower() if isinstance(raw_type, str) else raw_type

            # Create DissonanceResult
            return DissonanceResult(
                edge_a_id=edge_a["id"],
                edge_b_id=edge_b["id"],
                dissonance_type=DissonanceType(normalized_type),
                confidence_score=float(result_data["confidence_score"]),
                description=result_data["description"],
                context={
                    "reasoning": result_data["reasoning"],
                    "edge_a": edge_a,
                    "edge_b": edge_b
                },
                requires_review=(result_data["dissonance_type"] == "NUANCE")
            )

        except Exception as e:
            logger.error(f"Failed to analyze dissonance with LLM: {e}")
            # Return NONE dissonance on failure
            return DissonanceResult(
                edge_a_id=edge_a["id"],
                edge_b_id=edge_b["id"],
                dissonance_type=DissonanceType.NONE,
                confidence_score=0.0,
                description="Analysis failed",
                context={"error": str(e)},
                requires_review=False
            )

    def create_nuance_review(self, dissonance: DissonanceResult) -> NuanceReviewProposal:
        """Erstellt einen Review-Proposal für NUANCE-Klassifikation."""
        proposal = NuanceReviewProposal(
            id=str(uuid.uuid4()),
            dissonance=dissonance,
            status="PENDING_IO_REVIEW",
            reclassified_to=None,
            review_reason=None,
            created_at=datetime.now(timezone.utc).isoformat(),
            reviewed_at=None
        )
        _nuance_reviews.append(asdict(proposal))
        return proposal

    async def create_smf_proposal(self, dissonance: DissonanceResult, edge_a: dict, edge_b: dict) -> None:
        """
        Erstellt SMF Proposal für erkannte Dissonanzen (Story 7.9).

        This integrates Self-Modification Framework with dissonance detection.
        """
        if dissonance.dissonance_type == DissonanceType.NONE:
            return

        try:
            # Prüfe ob konstitutive Edges betroffen sind
            edge_a_props = edge_a.get("properties", {})
            edge_b_props = edge_b.get("properties", {})

            is_constitutive = (
                edge_a_props.get("edge_type") == "constitutive" or
                edge_b_props.get("edge_type") == "constitutive"
            )

            approval_level = ApprovalLevel.BILATERAL if is_constitutive else ApprovalLevel.IO

            # Erstelle neutrales Reasoning
            affected_edges_data = [
                {
                    "id": edge_a["id"],
                    "relation": edge_a["relation"],
                    "source_name": edge_a.get("source_name", "Unknown"),
                    "target_name": edge_a.get("target_name", "Unknown")
                },
                {
                    "id": edge_b["id"],
                    "relation": edge_b["relation"],
                    "source_name": edge_b.get("source_name", "Unknown"),
                    "target_name": edge_b.get("target_name", "Unknown")
                }
            ]

            reasoning_data = generate_neutral_reasoning(
                dissonance={
                    "dissonance_type": dissonance.dissonance_type.value,
                    "description": dissonance.description
                },
                affected_edges=affected_edges_data
            )

            # Validiere Neutralität
            is_neutral, violations = await validate_neutrality(reasoning_data["full_reasoning"], self.haiku_client)

            if not is_neutral:
                logger.warning(f"SMF proposal rejected due to framing violations: {violations}")
                # Audit-Log für Framing Verstoß
                from mcp_server.db.graph import _log_audit_entry
                _log_audit_entry(
                    edge_id=edge_a["id"],
                    action="FRAMING_VIOLATION",
                    blocked=True,
                    reason=f"SMF proposal rejected: {', '.join(violations)}",
                    actor="system"
                )
                return

            # Erstelle SMF Proposal
            proposed_action = {
                "action": "resolve",
                "edge_ids": [edge_a["id"], edge_b["id"]],
                "resolution_type": dissonance.dissonance_type.value,
                "dissonance_id": f"{edge_a['id']}-{edge_b['id']}"
            }

            proposal_data = {
                "trigger_type": TriggerType.DISSONANCE.value,
                "proposed_action": proposed_action,
                "affected_edges": [edge_a["id"], edge_b["id"]],
                "reasoning": reasoning_data["full_reasoning"],
                "approval_level": approval_level.value
            }

            # Validiere Safeguards
            is_valid, violation_reason = validate_safeguards(proposal_data)
            if not is_valid:
                logger.warning(f"SMF proposal rejected due to safeguard violation: {violation_reason}")
                # Audit-Log für Safeguard Verstoß
                from mcp_server.db.graph import _log_audit_entry
                _log_audit_entry(
                    edge_id=edge_a["id"],
                    action="SAFEGUARD_VIOLATION",
                    blocked=True,
                    reason=violation_reason,
                    actor="system"
                )
                return

            # Erstelle Proposal in Datenbank
            proposal_id = create_smf_proposal(
                trigger_type=TriggerType.DISSONANCE,
                proposed_action=proposed_action,
                affected_edges=[edge_a["id"], edge_b["id"]],
                reasoning=reasoning_data["full_reasoning"],
                approval_level=approval_level
            )

            logger.info(f"Created SMF proposal {proposal_id} for {dissonance.dissonance_type.value} dissonance")

        except Exception as e:
            logger.error(f"Failed to create SMF proposal: {e}")
            # Nicht fatal - dissonance detection continues without SMF

    def get_pending_reviews(self) -> list[dict[str, Any]]:
        """Holt alle ausstehenden NUANCE Reviews."""
        return [r for r in _nuance_reviews if r["status"] == "PENDING_IO_REVIEW"]


def get_pending_nuance_edge_ids() -> set[str]:
    """
    Gibt alle Edge-IDs zurück die in ungelösten NUANCE-Reviews beteiligt sind.

    Wird von IEF verwendet um temporären Penalty anzuwenden.

    Returns:
        Set von Edge-ID Strings
    """
    edge_ids: set[str] = set()

    for review in _nuance_reviews:
        if review.get("status") == "PENDING_IO_REVIEW":
            dissonance = review.get("dissonance", {})
            edge_a = dissonance.get("edge_a_id")
            edge_b = dissonance.get("edge_b_id")
            if edge_a:
                edge_ids.add(str(edge_a))
            if edge_b:
                edge_ids.add(str(edge_b))

    return edge_ids

    def resolve_review(
        self,
        review_id: str,
        confirmed: bool,
        reclassified_to: DissonanceType | None = None,
        reason: str | None = None
    ) -> dict[str, Any] | None:
        """Löst einen NUANCE Review auf."""
        for review in _nuance_reviews:
            if review["id"] == review_id:
                if confirmed:
                    review["status"] = "CONFIRMED"
                else:
                    review["status"] = "RECLASSIFIED"
                    review["reclassified_to"] = reclassified_to.value if reclassified_to else None
                review["review_reason"] = reason
                review["reviewed_at"] = datetime.now(timezone.utc).isoformat()
                return review
        return None


# Structured prompt for dissonance classification
DISSONANCE_CLASSIFICATION_PROMPT = """
Du analysierst potenzielle Konflikte in einer Selbst-Narrative.

**Edge A:**
- Relation: {edge_a_relation}
- Source: {edge_a_source} → Target: {edge_a_target}
- Properties: {edge_a_properties}
- Erstellt: {edge_a_created}

**Edge B:**
- Relation: {edge_b_relation}
- Source: {edge_b_source} → Target: {edge_b_target}
- Properties: {edge_b_properties}
- Erstellt: {edge_b_created}

**Klassifikations-Kriterien:**

1. **EVOLUTION**: Die Positionen zeigen zeitliche Entwicklung
   - Früher X, jetzt Y (nicht gleichzeitig wahr)
   - Eine Position hat die andere abgelöst
   - Beispiel: "Früher mochte ich X" → "Jetzt bevorzuge ich Y"

2. **CONTRADICTION**: Echter logischer Widerspruch
   - Beide Positionen beanspruchen gleichzeitige Gültigkeit
   - Können nicht beide wahr sein
   - Beispiel: "Ich glaube an X" UND "Ich glaube nicht an X"

3. **NUANCE**: Dialektische Spannung die okay ist
   - Beide Positionen können gleichzeitig wahr sein
   - Komplexität/Ambiguität ist Teil der Identität
   - Beispiel: "Ich schätze Autonomie" UND "Ich schätze Verbindung"

**Output Format (JSON):**
{{
  "dissonance_type": "EVOLUTION" | "CONTRADICTION" | "NUANCE" | "NONE",
  "confidence_score": <float 0.0-1.0>,
  "description": "<1-2 Sätze Erklärung>",
  "reasoning": "<Begründung für die Klassifikation>"
}}

Falls kein Konflikt erkannt wird, setze dissonance_type auf "NONE".
"""


def _find_review_by_id(review_id: str) -> dict[str, Any] | None:
    """
    Sucht einen NuanceReviewProposal in _nuance_reviews nach ID.

    Args:
        review_id: UUID des Review-Proposals (aus get_pending_reviews())

    Returns:
        Das Review-Dict mit 'dissonance' Feld oder None
    """
    for review in _nuance_reviews:
        if review["id"] == review_id:
            return review
    return None


def _mark_edge_as_superseded(edge_id: str, superseded_at: str, superseded_by: str) -> bool:
    """
    Markiert eine Edge als superseded durch Hinzufügen eines 'superseded: True' Flags.

    KRITISCH-1 FIX: Diese Funktion wird von resolve_dissonance() aufgerufen um
    sicherzustellen dass _is_edge_superseded() in graph.py die Edge korrekt
    filtert wenn include_superseded=False gesetzt ist.

    Args:
        edge_id: UUID der Edge die superseded werden soll
        superseded_at: ISO timestamp wann die Edge superseded wurde
        superseded_by: Wer die Resolution erstellt hat (z.B. "I/O")

    Returns:
        True wenn erfolgreich, False bei Fehler

    Note:
        Die Funktion merged die neuen Properties mit den bestehenden,
        um keine existierenden Metadaten zu verlieren.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Hole aktuelle Properties
            cursor.execute(
                "SELECT properties FROM edges WHERE id = %s::uuid",
                (edge_id,)
            )
            result = cursor.fetchone()

            if not result:
                logger.warning(f"Edge {edge_id} not found for superseded marking")
                return False

            # Parse existing properties
            existing_props = result["properties"] or {}
            if isinstance(existing_props, str):
                existing_props = json.loads(existing_props)

            # Merge with superseded flag
            existing_props["superseded"] = True
            existing_props["superseded_at"] = superseded_at
            existing_props["superseded_by"] = superseded_by

            # Update edge properties
            cursor.execute(
                """
                UPDATE edges
                SET properties = %s::jsonb,
                    modified_at = NOW()
                WHERE id = %s::uuid
                """,
                (json.dumps(existing_props), edge_id)
            )
            conn.commit()

            logger.debug(f"Marked edge {edge_id} as superseded by {superseded_by}")
            return True

    except Exception as e:
        logger.error(f"Failed to mark edge {edge_id} as superseded: {e}")
        return False


def resolve_dissonance(
    review_id: str,  # KORRIGIERT: review_id statt dissonance_id
    resolution_type: str,  # "EVOLUTION" | "CONTRADICTION" | "NUANCE"
    context: str,
    resolved_by: str = "I/O"
) -> dict[str, Any]:
    """
    Erstellt eine Resolution-Hyperedge für eine erkannte Dissonanz.

    Workflow:
    1. Suche NuanceReviewProposal via review_id in _nuance_reviews
    2. Extrahiere edge_a_id und edge_b_id aus dem gespeicherten dissonance-Objekt
    3. Erstelle Resolution-Node als Hyperedge-Anker
    4. Erstelle RESOLVES-Edge mit resolution-Properties
    5. Update Review-Status auf CONFIRMED/RECLASSIFIED

    Args:
        review_id: UUID des NuanceReviewProposal (aus get_pending_reviews())
        resolution_type: Typ der Resolution ("EVOLUTION", "CONTRADICTION", "NUANCE")
        context: Beschreibung der Resolution
        resolved_by: Wer hat die Resolution erstellt (default: "I/O")

    Returns:
        Dict mit resolution_edge_id, resolution_type, edge_a_id, edge_b_id, resolved_at, resolved_by

    Raises:
        ValueError: Wenn review_id nicht gefunden oder resolution_type ungültig
    """
    # 1. Finde den Review via ID
    review = _find_review_by_id(review_id)
    if not review:
        raise ValueError(f"Review {review_id} not found in _nuance_reviews")

    # 2. Extrahiere Edge-IDs aus dem dissonance-Objekt im Review
    dissonance = review.get("dissonance", {})
    edge_a_id = dissonance.get("edge_a_id")
    edge_b_id = dissonance.get("edge_b_id")

    if not edge_a_id or not edge_b_id:
        raise ValueError(f"Review {review_id} has invalid dissonance data: missing edge IDs")

    # 3. Validiere resolution_type
    valid_types = ["EVOLUTION", "CONTRADICTION", "NUANCE"]
    if resolution_type not in valid_types:
        raise ValueError(f"Invalid resolution_type: {resolution_type}. Must be one of {valid_types}")

    # 4. Erstelle Resolution-Properties basierend auf Typ
    resolved_at = datetime.now(timezone.utc).isoformat()

    # Type annotation fix (MEDIUM-1): Use dict[str, Any] for mixed value types
    base_properties: dict[str, Any] = {
        "edge_type": "resolution",
        "resolution_type": resolution_type,
        "context": context,
        "resolved_at": resolved_at,
        "resolved_by": resolved_by
    }

    if resolution_type == "EVOLUTION":
        # EVOLUTION: edge_a wird durch edge_b ersetzt
        base_properties["supersedes"] = [str(edge_a_id)]
        base_properties["superseded_by"] = [str(edge_b_id)]

        # KRITISCH-1 FIX: Set superseded=True flag on the original edge (edge_a)
        # This enables _is_edge_superseded() filter to work correctly
        _mark_edge_as_superseded(edge_a_id, resolved_at, resolved_by)
    else:
        # CONTRADICTION / NUANCE: beide bleiben aktiv
        base_properties["affected_edges"] = [str(edge_a_id), str(edge_b_id)]

    # 5. Erstelle Resolution-Node (als Hyperedge-Anker)
    resolution_node = get_or_create_node(
        name=f"Resolution-{review_id[:8]}",
        label="Resolution"
    )

    # 6. Erstelle RESOLVES-Edges von Resolution-Node
    #
    # MVP LIMITATION (KRITISCH-2):
    # Die target_id verwendet Edge-UUIDs statt Node-UUIDs. Das PostgreSQL-Schema
    # erlaubt dies technisch (beide sind UUIDs), aber es ist semantisch nicht korrekt.
    # Die Resolution-Properties (supersedes, affected_edges) enthalten die Edge-IDs
    # als Referenzen. Für query_neighbors() Traversal ist dies NICHT nutzbar -
    # stattdessen wird _mark_edge_as_superseded() verwendet um Edges direkt zu markieren.
    #
    # Future Enhancement (Epic 8): Echtes Hypergraph-Schema mit Edge-zu-Edge Relationen.
    resolution_edge = add_edge(
        source_id=resolution_node["node_id"],
        target_id=edge_a_id,  # MVP: Edge-ID als Pseudo-Node-Target
        relation="RESOLVES",
        weight=1.0,
        properties=json.dumps(base_properties)
    )

    # 7. Erstelle zweite RESOLVES-Edge zu Edge B (vollständige Hyperedge)
    add_edge(
        source_id=resolution_node["node_id"],
        target_id=edge_b_id,  # MVP: Edge-ID als Pseudo-Node-Target
        relation="RESOLVES",
        weight=1.0,
        properties=json.dumps(base_properties)
    )

    # 8. Update Review-Status
    original_dissonance_type = dissonance.get("dissonance_type", {})
    if isinstance(original_dissonance_type, dict):
        # If it's a dict, get the value
        original_type = original_dissonance_type.get("value", "unknown")
    else:
        # If it's a string or enum
        original_type = str(original_dissonance_type)

    review["status"] = "CONFIRMED" if resolution_type.upper() == original_type.upper() else "RECLASSIFIED"
    review["reviewed_at"] = resolved_at
    review["review_reason"] = context

    logger.info(
        f"Created resolution {resolution_type} for review {review_id}: "
        f"edge_a={edge_a_id}, edge_b={edge_b_id}, node={resolution_node['node_id']}"
    )

    return {
        "resolution_id": resolution_edge["edge_id"],
        "resolution_node_id": resolution_node["node_id"],
        "resolution_type": resolution_type,
        "edge_a_id": edge_a_id,
        "edge_b_id": edge_b_id,
        "resolved_at": resolved_at,
        "resolved_by": resolved_by
    }


def get_resolutions_for_node(node_name: str) -> list[dict[str, Any]]:
    """
    Findet alle Resolution-Hyperedges die einen Node betreffen.

    Wird von Story 7.7 (IEF) und Story 7.9 (SMF) verwendet.

    Args:
        node_name: Name des Nodes

    Returns:
        Liste von Resolution-Dicts mit resolution_type, context, affected_edges
    """
    # Import here to avoid circular import
    from mcp_server.db.graph import query_neighbors, get_node_by_name

    node = get_node_by_name(node_name)
    if not node:
        return []

    # MEDIUM-3 FIX: get_node_by_name() returns "id", not "node_id"
    # Suche alle RESOLVES-Edges die auf diesen Node zeigen
    neighbors = query_neighbors(
        node_id=node["id"],  # Fixed: was node["node_id"]
        relation_type="RESOLVES",
        direction="incoming",
        include_superseded=True  # Resolutions immer inkludieren
    )

    resolutions = []
    for neighbor in neighbors:
        props = neighbor.get("edge_properties", {})
        if props.get("edge_type") == "resolution":
            resolutions.append({
                "resolution_node": neighbor.get("name"),
                "resolution_type": props.get("resolution_type"),
                "context": props.get("context"),
                "supersedes": props.get("supersedes", []),
                "superseded_by": props.get("superseded_by", []),
                "affected_edges": props.get("affected_edges", []),
                "resolved_at": props.get("resolved_at"),
                "resolved_by": props.get("resolved_by")
            })

    return resolutions