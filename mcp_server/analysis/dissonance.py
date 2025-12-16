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
from mcp_server.external.anthropic_client import HaikuClient

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

            # HIGH-3 Fix: Limit O(n²) API calls to max 100 pairs
            # At 100 edges we'd have 4950 pairs - that's ~€5 per check!
            # Limit to first 100 pairs for cost control
            MAX_PAIRS = 100
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

                query = """
                    SELECT DISTINCT e.*,
                           ns.name as source_name, nt.name as target_name,
                           pns.name as source_node_name, pnt.name as target_node_name
                    FROM edges e
                    JOIN nodes ns ON e.source_id = ns.id
                    JOIN nodes nt ON e.target_id = nt.id
                    LEFT JOIN nodes pns ON CAST(e.properties->>'source_node' AS VARCHAR) = pns.id
                    LEFT JOIN nodes pnt ON CAST(e.properties->>'target_node' AS VARCHAR) = pnt.id
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
                query = """
                    SELECT DISTINCT e.*,
                           ns.name as source_name, nt.name as target_name,
                           pns.name as source_node_name, pnt.name as target_node_name
                    FROM edges e
                    JOIN nodes ns ON e.source_id = ns.id
                    JOIN nodes nt ON e.target_id = nt.id
                    LEFT JOIN nodes pns ON CAST(e.properties->>'source_node' AS VARCHAR) = pns.id
                    LEFT JOIN nodes pnt ON CAST(e.properties->>'target_node' AS VARCHAR) = pnt.id
                    WHERE (ns.name = %s OR nt.name = %s OR ns.id = %s OR nt.id = %s)
                    ORDER BY e.modified_at DESC
                """
                cursor.execute(query, (context_node_id, context_node_id, context_node_id, context_node_id))

            return [dict(row) for row in cursor.fetchall()]

    def _get_memory_strength(self, edge_id: str) -> Optional[float]:
        """
        Get memory strength for an edge from related l2_insights.

        LIMITATION (Story 7.4 Review):
        Currently uses ILIKE search in content which is unreliable since
        there's no direct FK between edges and l2_insights. This is a
        best-effort approach for MVP. Future versions should establish
        proper edge-to-insight mapping via nodes.vector_id or dedicated
        junction table.

        Returns None in most cases - authoritative_source will be None.
        """
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Approach 1: Try via source/target node vector_id linkage
                # This is more reliable than ILIKE search
                query = """
                    SELECT COALESCE(
                        (SELECT memory_strength FROM l2_insights WHERE id = ns.vector_id),
                        (SELECT memory_strength FROM l2_insights WHERE id = nt.vector_id)
                    ) as memory_strength
                    FROM edges e
                    JOIN nodes ns ON e.source_id = ns.id
                    JOIN nodes nt ON e.target_id = nt.id
                    WHERE e.id = %s::uuid
                    LIMIT 1
                """
                cursor.execute(query, (edge_id,))
                result = cursor.fetchone()

                if result and result["memory_strength"] is not None:
                    return float(result["memory_strength"])

                # Fallback: ILIKE search (unreliable but kept for compatibility)
                query_fallback = """
                    SELECT memory_strength
                    FROM l2_insights
                    WHERE content ILIKE %s
                    LIMIT 1
                """
                edge_id_pattern = f"%{edge_id}%"
                cursor.execute(query_fallback, (edge_id_pattern,))
                result = cursor.fetchone()

                return float(result["memory_strength"]) if result and result["memory_strength"] else None

        except Exception as e:
            logger.debug(f"Could not fetch memory strength for edge {edge_id}: {e}")
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

            # Parse JSON response
            result_data = json.loads(response)

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

    def get_pending_reviews(self) -> list[dict[str, Any]]:
        """Holt alle ausstehenden NUANCE Reviews."""
        return [r for r in _nuance_reviews if r["status"] == "PENDING_IO_REVIEW"]

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