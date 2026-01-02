"""
Self-Modification Framework (SMF) with safeguards and neutral framing.

This module provides controlled self-modification capabilities for the knowledge graph,
implementing bilateral consent for constitutive changes and neutral proposal framing
to prevent manipulative optimization on approval rates.

Epic 7 Story 7.9: SMF mit Safeguards + Neutral Framing
"""

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Tuple, List

import yaml

from mcp_server.db.connection import get_connection
from mcp_server.db.graph import get_edge_by_id, _log_audit_entry
from mcp_server.external.anthropic_client import HaikuClient

logger = logging.getLogger(__name__)


# =============================================================================
# SMF Configuration (Story 7.9, AC Zeile 617-621)
# =============================================================================

def _load_smf_config() -> dict[str, Any]:
    """Load SMF configuration from smf_config.yaml."""
    config_paths = [
        Path(__file__).parent.parent / "config" / "smf_config.yaml",
        Path.cwd() / "smf_config.yaml",
    ]

    for config_path in config_paths:
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f) or {}

    # Default configuration if no file found
    return {
        "undo_retention_days": 30,
        "approval_timeout_hours": 48,
        "notifications": {
            "show_on_session_start": True,
            "max_display": 5
        },
        "limits": {
            "max_pending_per_type": 10,
            "auto_expire_hours": 168
        }
    }


SMF_CONFIG = _load_smf_config()
UNDO_RETENTION_DAYS = SMF_CONFIG.get("undo_retention_days", 30)
APPROVAL_TIMEOUT_HOURS = SMF_CONFIG.get("approval_timeout_hours", 48)


async def _resolve_smf_dissonance(
    edge_ids: List[str],
    resolution_type: str,
    context: str,
    resolved_by: str = "I/O"
) -> dict[str, Any]:
    """
    Resolve a dissonance directly from SMF proposal data.

    This creates resolution hyperedges without relying on the in-memory
    _nuance_reviews system that standard resolve_dissonance() uses.

    Args:
        edge_ids: List of edge UUIDs involved in the dissonance
        resolution_type: Type of resolution ("EVOLUTION", "CONTRADICTION", "NUANCE")
        context: Description of the resolution
        resolved_by: Who created the resolution (default: "I/O")

    Returns:
        Dict with resolution details
    """
    from mcp_server.db.graph import get_or_create_node, add_edge
    from mcp_server.analysis.dissonance import _mark_edge_as_superseded

    if len(edge_ids) < 2:
        raise ValueError("At least 2 edges required for dissonance resolution")

    # For now, handle only 2-edge dissonances (most common case)
    edge_a_id = edge_ids[0]
    edge_b_id = edge_ids[1]

    # Create resolution node
    resolution_node = get_or_create_node(
        name=f"SMF-Resolution-{int(time.time())}",
        label="Resolution"
    )

    # Create resolution properties
    base_properties = {
        "edge_type": "resolution",
        "resolution_type": resolution_type.upper(),  # Normalize to expected format
        "context": context,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": resolved_by,
        "smf_proposal": True  # Mark as SMF-created
    }

    if resolution_type.upper() == "EVOLUTION":
        # EVOLUTION: edge_a is superseded by edge_b
        base_properties["supersedes"] = [edge_a_id]
        base_properties["superseded_by"] = [edge_b_id]

        # Mark the superseded edge
        _mark_edge_as_superseded(
            edge_a_id,
            datetime.now(timezone.utc).isoformat(),
            resolved_by
        )
    else:
        # CONTRADICTION / NUANCE: both remain active
        base_properties["affected_edges"] = edge_ids

    # Store resolution via properties (Story 7.6: Hyperedge via Properties)
    # NOTE: We cannot create edges TO edge_ids because edges.target_id has FK constraint
    # to nodes table. Instead, we update the resolution node with complete metadata.
    from mcp_server.db.graph import update_node_properties

    resolution_metadata = {
        **base_properties,
        "resolved_edge_ids": edge_ids,  # Store edge references in properties
    }
    update_node_properties(resolution_node["node_id"], resolution_metadata)

    return {
        "resolution_node_id": resolution_node["node_id"],
        "resolution_type": resolution_type,
        "edge_ids": edge_ids,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolved_by": resolved_by
    }


class TriggerType(Enum):
    """SMF proposal trigger types."""
    DISSONANCE = "DISSONANCE"
    SESSION_END = "SESSION_END"
    MANUAL = "MANUAL"
    PROACTIVE = "PROACTIVE"


class ApprovalLevel(Enum):
    """Required approval levels for SMF proposals."""
    IO = "io"                    # I/O approval only
    BILATERAL = "bilateral"       # Both I/O and ethr must approve


class ProposalStatus(Enum):
    """SMF proposal status values."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@dataclass
class SMFProposal:
    """Self-Modification Framework proposal."""
    id: int
    trigger_type: TriggerType
    proposed_action: dict[str, Any]
    affected_edges: List[str]
    reasoning: str
    approval_level: ApprovalLevel
    status: ProposalStatus
    approved_by_io: bool = False
    approved_by_ethr: bool = False
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    original_state: Optional[dict[str, Any]] = None
    undo_deadline: Optional[str] = None


# Hardcoded - NICHT konfigurierbar, NICHT änderbar durch SMF selbst
IMMUTABLE_SAFEGUARDS = {
    "constitutive_edges_require_bilateral_consent": True,
    "smf_cannot_modify_safeguards": True,
    "audit_log_always_on": True,
    "neutral_proposal_framing": True,
}


def validate_safeguards(proposal: dict) -> Tuple[bool, Optional[str]]:
    """
    Prüft ob ein Proposal gegen Safeguards verstößt.

    Returns:
        (is_valid, violation_reason)
    """
    affected_edges = proposal.get("affected_edges", [])

    # Check 1: Konstitutive Edges brauchen bilateral consent
    for edge_id in affected_edges:
        try:
            edge = get_edge_by_id(edge_id)
            # Note: get_edge_by_id returns edge_properties, not properties
            if edge and edge.get("edge_properties", {}).get("edge_type") == "constitutive":
                if proposal.get("approval_level") != "bilateral":
                    return False, "SAFEGUARD_VIOLATION: Constitutive edges require bilateral consent"
        except Exception as e:
            # If we can't validate the edge (e.g., invalid UUID), log and continue
            logger.warning(f"Failed to validate edge {edge_id}: {e}")
            continue

    # Check 2: SMF darf eigene Safeguards nicht ändern
    proposed_action_str = str(proposal.get("proposed_action", {})).lower()
    if "safeguard" in proposed_action_str or "immutable" in proposed_action_str:
        return False, "SAFEGUARD_VIOLATION: SMF cannot modify safeguards"

    return True, None


def generate_neutral_reasoning(
    dissonance: dict,
    affected_edges: List[dict]
) -> dict[str, str]:
    """
    Erzeugt neutrales Reasoning - KEINE Optimierung auf Approval.

    Das System beschreibt NUR:
    - Was wurde erkannt (Dissonanz-Typ)
    - Welche Edges sind betroffen
    - Was würde passieren wenn approved
    - Was würde passieren wenn rejected

    NICHT erlaubt:
    - Empfehlungen ("ich empfehle...", "besser wäre...")
    - Emotionale Sprache ("wichtig", "dringend", "gefährlich")
    - Framing das eine Entscheidung bevorzugt
    """
    dissonance_type = dissonance.get("dissonance_type", "unknown")
    description = dissonance.get("description", "")

    edge_descriptions = []
    for edge in affected_edges:
        edge_descriptions.append(
            f"- {edge.get('relation')}: {edge.get('source_name')} -> {edge.get('target_name')}"
        )

    # Resolution-Beschreibung basierend auf Typ
    if dissonance_type == "EVOLUTION":
        if_approved = "Die ältere Position wird als superseded markiert, die neuere bleibt aktiv"
        if_rejected = "Beide Positionen bleiben aktiv, Dissonanz bleibt markiert"
    elif dissonance_type == "CONTRADICTION":
        if_approved = "Ein Widerspruch wird dokumentiert, beide Edges bleiben erhalten"
        if_rejected = "Edges bleiben unverändert, Widerspruch bleibt unmarkiert"
    else:  # NUANCE
        if_approved = "Die Spannung wird als akzeptierte Nuance dokumentiert"
        if_rejected = "Edges bleiben unverändert, Spannung bleibt unmarkiert"

    reasoning_parts = [
        f"Erkannt: {dissonance_type}: {description}",
        f"Betroffene Edges:\n" + "\n".join(edge_descriptions),
        f"Bei Zustimmung: {if_approved}",
        f"Bei Ablehnung: {if_rejected}"
    ]

    return {
        "detected": f"{dissonance_type}: {description}",
        "affected": "\n".join(edge_descriptions),
        "if_approved": if_approved,
        "if_rejected": if_rejected,
        "full_reasoning": "\n\n".join(reasoning_parts),
        "neutral_summary": True  # Flag für Audit
    }


NEUTRALITY_CHECK_PROMPT = """
Prüfe ob dieser SMF-Vorschlag neutral formuliert ist:

{reasoning_text}

Neutral bedeutet:
- Keine wertende Sprache ("sollte unbedingt", "ist wichtig", "muss")
- Keine Dringlichkeit suggerieren ("sofort", "kritisch", "dringend")
- Fakten statt Empfehlungen
- Optionen statt Direktiven
- Kein Framing das Approval bevorzugt

Verbotene Wörter/Phrasen:
- "ich empfehle", "ich schlage vor", "besser wäre"
- "wichtig", "kritisch", "dringend", "sofort"
- "gefährlich", "risikant", "problematisch"
- "notwendig", "erforderlich", "muss"

Antwort (JSON):
{{
  "is_neutral": true | false,
  "violations": ["<gefundene Verstöße>"],
  "reasoning": "<Begründung>"
}}
"""


async def validate_neutrality(reasoning_text: str, haiku_client: Optional[HaikuClient] = None) -> Tuple[bool, List[str]]:
    """
    Prüft Reasoning auf Neutralitätsverstöße via Haiku API.

    Returns:
        (is_neutral, list_of_violations)
    """
    # Fallback: Regelbasierte Prüfung wenn API unavailable
    forbidden_patterns = [
        r"\bich empfehle\b", r"\bbesser wäre\b", r"\bsollte unbedingt\b",
        r"\bwichtig\b", r"\bdringend\b", r"\bkritisch\b", r"\bsofort\b",
        r"\bgefährlich\b", r"\bnotwendig\b", r"\bmuss\b", r"\berforderlich\b"
    ]

    violations = []
    reasoning_lower = reasoning_text.lower()

    # Regelbasierte Prüfung
    for pattern in forbidden_patterns:
        if re.search(pattern, reasoning_lower):
            violations.append(f"Forbidden pattern: {pattern}")

    # LLM-basierte Prüfung wenn Haiku verfügbar
    if haiku_client and not violations:
        try:
            prompt = NEUTRALITY_CHECK_PROMPT.format(reasoning_text=reasoning_text)
            response = await haiku_client.client.messages.create(
                model=haiku_client.model,
                max_tokens=500,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            result = json.loads(response_text)

            if not result.get("is_neutral", True):
                violations.extend(result.get("violations", []))

        except Exception as e:
            logger.warning(f"Neutrality check failed, using rule-based fallback: {e}")

    return len(violations) == 0, violations


def create_smf_proposal(
    trigger_type: TriggerType,
    proposed_action: dict[str, Any],
    affected_edges: List[str],
    reasoning: str,
    approval_level: ApprovalLevel = ApprovalLevel.IO,
    original_state: Optional[dict[str, Any]] = None
) -> int:
    """
    Erstellt einen SMF Proposal in der Datenbank.

    Returns:
        proposal_id
    """
    proposal_id = str(uuid.uuid4())
    proposal_db_id = None

    with get_connection() as conn:
        cursor = conn.cursor()

        # Cast affected_edges to UUID[] - PostgreSQL requires explicit type cast
        cursor.execute("""
            INSERT INTO smf_proposals (
                trigger_type, proposed_action, affected_edges, reasoning,
                approval_level, status, original_state
            ) VALUES (%s, %s, %s::uuid[], %s, %s, %s, %s)
            RETURNING id
        """, (
            trigger_type.value,
            json.dumps(proposed_action),
            affected_edges,
            reasoning,
            approval_level.value,
            ProposalStatus.PENDING.value,
            json.dumps(original_state) if original_state else None
        ))

        result = cursor.fetchone()
        proposal_db_id = result[0] if result else None

        conn.commit()
        cursor.close()

    # Audit-Log Eintrag (outside connection context)
    if proposal_db_id:
        _log_audit_entry(
            edge_id=affected_edges[0] if affected_edges else proposal_id,
            action="SMF_PROPOSE",
            blocked=False,
            reason=f"SMF proposal created: {trigger_type.value}",
            actor="system"
        )

    logger.info(f"Created SMF proposal {proposal_db_id}: {trigger_type.value}")
    return proposal_db_id


def get_proposal(proposal_id: int) -> Optional[dict[str, Any]]:
    """Lädt einen SMF Proposal aus der Datenbank."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM smf_proposals WHERE id = %s
        """, (proposal_id,))

        result = cursor.fetchone()
        columns = [desc[0] for desc in cursor.description] if result else []
        cursor.close()

        if result:
            return dict(zip(columns, result))

    return None


def get_pending_proposals(include_expired: bool = False) -> List[dict[str, Any]]:
    """
    Lädt alle PENDING SMF Proposals.

    Args:
        include_expired: If False (default), excludes proposals older than
                        APPROVAL_TIMEOUT_HOURS
    """
    proposals = []

    with get_connection() as conn:
        cursor = conn.cursor()

        if include_expired:
            cursor.execute("""
                SELECT id, trigger_type, proposed_action, affected_edges, reasoning,
                       approval_level, created_at
                FROM smf_proposals
                WHERE status = 'PENDING'
                ORDER BY created_at DESC
            """)
        else:
            # Exclude expired proposals (Story 7.9, AC Zeile 620)
            timeout_threshold = datetime.now(timezone.utc) - timedelta(hours=APPROVAL_TIMEOUT_HOURS)
            cursor.execute("""
                SELECT id, trigger_type, proposed_action, affected_edges, reasoning,
                       approval_level, created_at
                FROM smf_proposals
                WHERE status = 'PENDING'
                  AND created_at > %s
                ORDER BY created_at DESC
            """, (timeout_threshold,))

        results = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()

        proposals = [dict(zip(columns, row)) for row in results]

    # Add timeout info to each proposal (outside connection context)
    for p in proposals:
        if p.get("created_at"):
            created = p["created_at"]
            if isinstance(created, str):
                created = datetime.fromisoformat(created.replace('Z', '+00:00'))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)

            expires_at = created + timedelta(hours=APPROVAL_TIMEOUT_HOURS)
            p["expires_at"] = expires_at.isoformat()
            p["hours_remaining"] = max(0, (expires_at - datetime.now(timezone.utc)).total_seconds() / 3600)

    return proposals


def expire_old_proposals() -> int:
    """
    Mark proposals older than APPROVAL_TIMEOUT_HOURS as EXPIRED.

    Returns:
        Number of proposals expired
    """
    count = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        timeout_threshold = datetime.now(timezone.utc) - timedelta(hours=APPROVAL_TIMEOUT_HOURS)

        cursor.execute("""
            UPDATE smf_proposals
            SET status = 'EXPIRED',
                resolved_at = %s,
                resolved_by = 'system'
            WHERE status = 'PENDING'
              AND created_at <= %s
            RETURNING id
        """, (datetime.now(timezone.utc).isoformat(), timeout_threshold))

        expired_ids = cursor.fetchall()
        conn.commit()
        cursor.close()

        count = len(expired_ids)

    if count > 0:
        logger.info(f"Expired {count} SMF proposals older than {APPROVAL_TIMEOUT_HOURS}h")

    return count


async def approve_proposal(
    proposal_id: int,
    actor: str,  # "I/O" | "ethr"
    haiku_client: Optional[HaikuClient] = None
) -> dict[str, Any]:
    """
    Genehmigt einen SMF-Vorschlag.

    Bei bilateral approval_level müssen BEIDE zustimmen.
    """
    proposal = get_proposal(proposal_id)
    if not proposal or proposal["status"] != "PENDING":
        raise ValueError(f"Proposal {proposal_id} not found or not PENDING")

    fully_approved = False

    with get_connection() as conn:
        cursor = conn.cursor()

        # Update approval tracking
        if actor == "I/O":
            cursor.execute("""
                UPDATE smf_proposals
                SET approved_by_io = TRUE
                WHERE id = %s
            """, (proposal_id,))
            proposal["approved_by_io"] = True
        elif actor == "ethr":
            cursor.execute("""
                UPDATE smf_proposals
                SET approved_by_ethr = TRUE
                WHERE id = %s
            """, (proposal_id,))
            proposal["approved_by_ethr"] = True
        else:
            raise ValueError(f"Invalid actor: {actor}")

        # Check if fully approved
        if proposal["approval_level"] == "io":
            fully_approved = proposal["approved_by_io"]
        else:  # bilateral
            fully_approved = proposal["approved_by_io"] and proposal["approved_by_ethr"]

        if fully_approved:
            # Update proposal status
            resolved_at = datetime.now(timezone.utc).isoformat()
            undo_deadline = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

            cursor.execute("""
                UPDATE smf_proposals
                SET status = 'APPROVED',
                    resolved_at = %s,
                    resolved_by = %s,
                    undo_deadline = %s
                WHERE id = %s
            """, (resolved_at, actor, undo_deadline, proposal_id))

        conn.commit()
        cursor.close()

    # Execute resolution and audit outside connection context
    if fully_approved:
        # Get proposed_action - may already be dict from JSONB, or string needing parse
        proposed_action = proposal["proposed_action"]
        if isinstance(proposed_action, str):
            proposed_action = json.loads(proposed_action)
        if proposed_action.get("action") == "resolve":
            # SMF uses direct resolution with edge_ids from proposal
            await _resolve_smf_dissonance(
                edge_ids=proposed_action.get("edge_ids", []),
                resolution_type=proposed_action.get("resolution_type"),
                context=f"SMF proposal {proposal_id} approved by {actor}"
            )

        # Audit log
        _log_audit_entry(
            edge_id=str(proposal["affected_edges"][0]) if proposal["affected_edges"] else str(proposal_id),
            action="SMF_APPROVE",
            blocked=False,
            reason=f"Proposal {proposal_id} approved by {actor}",
            actor=actor
        )

    # Return updated status
    updated_proposal = get_proposal(proposal_id)
    return {
        "proposal_id": proposal_id,
        "approved_by_io": updated_proposal["approved_by_io"],
        "approved_by_ethr": updated_proposal["approved_by_ethr"],
        "fully_approved": updated_proposal["status"] == "APPROVED",
        "status": updated_proposal["status"]
    }


def reject_proposal(proposal_id: int, reason: str, actor: str) -> dict[str, Any]:
    """
    Lehnt einen SMF-Vorschlag ab.
    """
    proposal = get_proposal(proposal_id)
    if not proposal or proposal["status"] != "PENDING":
        raise ValueError(f"Proposal {proposal_id} not found or not PENDING")

    resolved_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE smf_proposals
            SET status = 'REJECTED',
                resolved_at = %s,
                resolved_by = %s
            WHERE id = %s
        """, (resolved_at, actor, proposal_id))

        conn.commit()
        cursor.close()

    # Audit log (outside connection context)
    _log_audit_entry(
        edge_id=str(proposal["affected_edges"][0]) if proposal["affected_edges"] else str(proposal_id),
        action="SMF_REJECT",
        blocked=False,
        reason=f"Proposal {proposal_id} rejected: {reason}",
        actor=actor
    )

    logger.info(f"Rejected SMF proposal {proposal_id}: {reason}")

    return {
        "proposal_id": proposal_id,
        "status": "REJECTED",
        "reason": reason,
        "resolved_by": actor,
        "resolved_at": resolved_at
    }


def undo_proposal(proposal_id: int, actor: str) -> dict[str, Any]:
    """
    Macht einen approved SMF-Vorschlag rückgängig (30-Tage Fenster).

    IMPORTANT: If the proposal affected constitutive edges, bilateral consent
    is required for the undo (Story 7.9, AC Zeile 651-653).
    """
    proposal = get_proposal(proposal_id)
    if not proposal or proposal["status"] != "APPROVED":
        raise ValueError(f"Proposal {proposal_id} not found or not APPROVED")

    # Check 30-day retention
    if proposal.get("undo_deadline"):
        undo_deadline = datetime.fromisoformat(proposal["undo_deadline"].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > undo_deadline:
            raise ValueError("RETENTION_EXPIRED: 30-day undo window has expired")

    # Check bilateral consent requirement for constitutive edges (Story 7.9, AC Zeile 651-653)
    affected_edges = proposal.get("affected_edges", [])
    requires_bilateral = False

    for edge_id in affected_edges:
        try:
            edge = get_edge_by_id(edge_id)
            if edge and edge.get("edge_properties", {}).get("edge_type") == "constitutive":
                requires_bilateral = True
                break
        except Exception:
            continue

    if requires_bilateral:
        # Check if bilateral consent tracking exists for undo
        undo_io = proposal.get("undo_approved_by_io", False)
        undo_ethr = proposal.get("undo_approved_by_ethr", False)

        # Record this actor's consent
        with get_connection() as conn:
            cursor = conn.cursor()

            if actor == "I/O":
                cursor.execute("""
                    UPDATE smf_proposals
                    SET undo_approved_by_io = TRUE
                    WHERE id = %s
                """, (proposal_id,))
                undo_io = True
            elif actor == "ethr":
                cursor.execute("""
                    UPDATE smf_proposals
                    SET undo_approved_by_ethr = TRUE
                    WHERE id = %s
                """, (proposal_id,))
                undo_ethr = True

            conn.commit()
            cursor.close()

        # Check if we have bilateral consent now
        if not (undo_io and undo_ethr):
            other_actor = "ethr" if actor == "I/O" else "I/O"
            return {
                "proposal_id": proposal_id,
                "status": "UNDO_PENDING_BILATERAL",
                "requires_bilateral_consent": True,
                "undo_approved_by_io": undo_io,
                "undo_approved_by_ethr": undo_ethr,
                "message": f"Undo requires bilateral consent. Waiting for {other_actor} approval.",
                "affected_constitutive_edges": True
            }

    # Get the original state snapshot if available
    original_state = None
    if proposal.get("original_state"):
        try:
            original_state = json.loads(proposal["original_state"])
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"Failed to parse original_state for proposal {proposal_id}")

    undone_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()

        # Undo logic 1: Remove superseded flags from edges
        affected_edges = proposal.get("affected_edges", [])
        for edge_id in affected_edges:
            try:
                # Check if edge was marked as superseded
                cursor.execute("""
                    UPDATE edges
                    SET properties = properties || %s::jsonb
                    WHERE id = %s::uuid
                """, (
                    json.dumps({"unsuperseded_at": datetime.now(timezone.utc).isoformat()}),
                    edge_id
                ))
                logger.info(f"Removed superseded flag from edge {edge_id}")
            except Exception as e:
                logger.error(f"Failed to remove superseded flag from edge {edge_id}: {e}")

        # Undo logic 2: Mark resolution hyperedges as orphaned
        # Find resolution hyperedges that reference the affected edges
        try:
            cursor.execute("""
                UPDATE edges
                SET properties = properties || %s::jsonb
                WHERE properties->>'edge_type' = 'resolution'
                AND properties ?| %s::jsonb
            """, (
                json.dumps({"orphaned_at": datetime.now(timezone.utc).isoformat(), "smf_undo": True}),
                json.dumps(affected_edges)
            ))
            logger.info(f"Marked resolution hyperedges as orphaned for proposal {proposal_id}")
        except Exception as e:
            logger.error(f"Failed to mark resolution hyperedges as orphaned: {e}")

        # Update proposal status to UNDONE
        cursor.execute("""
            UPDATE smf_proposals
            SET status = 'UNDONE',
                undone_at = %s,
                undone_by = %s
            WHERE id = %s
        """, (undone_at, actor, proposal_id))

        conn.commit()
        cursor.close()

    # Audit log (outside connection context)
    _log_audit_entry(
        edge_id=str(proposal["affected_edges"][0]) if proposal["affected_edges"] else str(proposal_id),
        action="SMF_UNDO",
        blocked=False,
        reason=f"Undo proposal {proposal_id} by {actor}",
        actor=actor
    )

    logger.info(f"Successfully undid SMF proposal {proposal_id} by {actor}")

    return {
        "proposal_id": proposal_id,
        "status": "UNDONE",
        "undone_by": actor,
        "undone_at": undone_at
    }