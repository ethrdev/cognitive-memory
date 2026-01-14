"""
Reclassify Memory Sector MCP Tool

Story 10.1: Manual reclassification of edge memory sectors.
Story 10.2: Constitutive edge protection with bilateral consent.
Functional Requirements: FR5, FR6, FR7, FR8, FR9, FR10, FR23, FR26, FR27
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from mcp_server.db.connection import get_connection
from mcp_server.utils.sector_classifier import MemorySector
from mcp_server.utils.constants import ReclassifyStatus

logger = logging.getLogger(__name__)

# Valid sector values (from MemorySector Literal type)
VALID_SECTORS = {"emotional", "episodic", "semantic", "procedural", "reflective"}


def _is_constitutive_edge(edge: dict[str, Any]) -> bool:
    """
    Check if edge is constitutive (identity-defining).

    Supports two patterns for compatibility:
    1. properties.is_constitutive = true (Epic 8 pattern)
    2. properties.edge_type == "constitutive" (SMF pattern)

    Args:
        edge: Edge dict with properties field

    Returns:
        True if edge is constitutive, False otherwise

    Story 10.2, Subtask 1.1: Constitutive edge detection
    """
    properties = edge.get("properties", {})

    # Epic 8 pattern
    if properties.get("is_constitutive") is True:
        return True

    # SMF pattern (for backward compatibility)
    if properties.get("edge_type") == "constitutive":
        return True

    return False


async def reclassify_memory_sector(
    source_name: str,
    target_name: str,
    relation: str,
    new_sector: str,
    edge_id: str | None = None,
    actor: str = "I/O"
) -> dict[str, Any]:
    """
    Reclassify an edge to a different memory sector.

    Args:
        source_name: Name of the source node
        target_name: Name of the target node
        relation: Relationship type (e.g., "KNOWS", "DISCUSSED")
        new_sector: Target memory sector (must be valid MemorySector)
        edge_id: Optional UUID for disambiguation when multiple edges exist
        actor: Who is performing the reclassification (default: "I/O")

    Returns:
        Dict with status and reclassification details

    Story 10.1, AC #1, #2, #3, #4, #5
    """
    # AC2: Validate new_sector
    if new_sector not in VALID_SECTORS:
        return {
            "status": ReclassifyStatus.INVALID_SECTOR,
            "error": f"Invalid sector: '{new_sector}'. Must be one of: {', '.join(sorted(VALID_SECTORS))}"
        }

    # AC3, AC4: Find edge(s) matching criteria
    try:
        edges = await _get_edges_by_names(source_name, target_name, relation)
    except Exception as e:
        # Distinguish database errors from "not found" errors
        logger.error("Database error during edge lookup", extra={
            "source_name": source_name,
            "target_name": target_name,
            "relation": relation,
            "error": str(e)
        }, exc_info=True)
        return {
            "status": "database_error",
            "error": f"Database error while searching for edge: {str(e)}"
        }

    if not edges:
        return {
            "status": ReclassifyStatus.NOT_FOUND,
            "error": f"Edge not found: {source_name} --{relation}--> {target_name}"
        }

    # AC5: If edge_id provided, use it for disambiguation (even with single edge)
    if edge_id:
        matching_edges = [e for e in edges if e["id"] == edge_id]
        if not matching_edges:
            return {
                "status": ReclassifyStatus.NOT_FOUND,
                "error": f"Edge with id '{edge_id}' not found among edges matching {source_name} --{relation}--> {target_name}"
            }
        edges = matching_edges

    # AC4: Handle ambiguous edges when no edge_id provided
    if len(edges) > 1:
        # Return ambiguous error with all edge_ids
        return {
            "status": ReclassifyStatus.AMBIGUOUS,
            "error": f"Multiple edges found between {source_name} and {target_name} with relation '{relation}'",
            "edge_ids": [e["id"] for e in edges]
        }

    # At this point, we have exactly one edge
    edge = edges[0]
    old_sector = edge.get("memory_sector", "semantic")  # Default per Epic 8

    # Story 10.2, Subtask 1.2: Check constitutive edge protection
    proposal_id = None
    if _is_constitutive_edge(edge):
        # Story 10.2, Subtask 2.1-2.5: Check for approved SMF proposal
        approval_result = await _check_smf_approval(edge["id"], new_sector)

        # Story 10.2, Subtask 2.7: Check for error response from SMF query (AC #8)
        if "error" in approval_result:
            # SMF database error - return error response without modifying edge
            return approval_result

        # Story 10.2, Subtask 2.5: If approval found, proceed with reclassification
        if not approval_result.get("approved"):
            # Story 10.2, Subtask 1.5: Add structured logging for constitutive check (AC: #7)
            logger.info("Constitutive edge requires consent", extra={
                "edge_id": edge["id"],
                "is_constitutive": True,
                "actor": actor
            })

            # Story 10.2, Subtask 1.3, 1.4: Return CONSENT_REQUIRED with hint
            return {
                "status": ReclassifyStatus.CONSENT_REQUIRED,
                "error": "Bilateral consent required for constitutive edge",
                "edge_id": edge["id"],
                "hint": "Use smf_pending_proposals and smf_approve to grant consent"
            }

        # Extract proposal_id for logging (AC #9)
        proposal_id = approval_result.get("proposal_id")

    # AC6: Perform reclassification
    await _update_edge_sector(edge["id"], new_sector, old_sector, actor)

    # Story 10.2, Subtask 1.6: Add success logging after reclassification (AC: #9)
    # Check if this was a constitutive edge reclassification
    if _is_constitutive_edge(edge):
        log_entry = {
            "edge_id": edge["id"],
            "old_sector": old_sector,
            "new_sector": new_sector,
            "actor": actor
        }
        # Code Review Fix: Include smf_proposal_id if available (AC #9)
        if proposal_id:
            log_entry["smf_proposal_id"] = proposal_id

        logger.info("Constitutive edge reclassified", extra=log_entry)

    # AC7: Structured logging for all reclassifications
    logger.info("Edge reclassified", extra={
        "edge_id": edge["id"],
        "from_sector": old_sector,
        "to_sector": new_sector,
        "actor": actor
    })

    # AC1: Return success response
    return {
        "status": ReclassifyStatus.SUCCESS,
        "edge_id": edge["id"],
        "old_sector": old_sector,
        "new_sector": new_sector
    }


async def _check_smf_approval(
    edge_id: str,
    new_sector: str
) -> dict[str, Any]:
    """
    Check if there's an approved SMF proposal for reclassifying this edge.

    Args:
        edge_id: UUID of the edge to check
        new_sector: Target sector for reclassification

    Returns:
        Dict with:
        - {"approved": True, "proposal_id": str} if approved proposal exists
        - {"approved": False} if no approved proposal
        - Error dict if database query fails (AC #8)

    Story 10.2, Subtask 2.1-2.7: SMF proposal lookup with error handling
    Code Review Fix: Returns proposal_id for AC #9 logging and validates new_sector
    """
    try:
        # Query smf_proposals table for APPROVED proposal
        # that affects our edge_id and is for reclassification
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, proposed_action, approval_level,
                       approved_by_io, approved_by_ethr
                FROM smf_proposals
                WHERE status = 'APPROVED'
                  AND %s = ANY(affected_edges)
                  AND (proposed_action->>'action' = 'reclassify'
                       OR proposed_action->>'action' = 'reclassify_sector')
                ORDER BY resolved_at DESC
                LIMIT 1
            """, (edge_id,))

            result = cursor.fetchone()

            if result:
                proposal_id = str(result[0])
                proposed_action = result[1]
                approval_level = result[2]
                approved_by_io = result[3]
                approved_by_ethr = result[4]

                # Code Review Fix: Validate that new_sector matches proposal
                if isinstance(proposed_action, dict):
                    proposed_sector = proposed_action.get("new_sector")
                    if proposed_sector and proposed_sector != new_sector:
                        logger.warning("SMF proposal sector mismatch", extra={
                            "edge_id": edge_id,
                            "proposal_id": proposal_id,
                            "proposed_sector": proposed_sector,
                            "requested_sector": new_sector
                        })
                        return {"approved": False}

                # For bilateral, both must approve
                if approval_level == "bilateral":
                    if approved_by_io and approved_by_ethr:
                        return {"approved": True, "proposal_id": proposal_id}
                    return {"approved": False}
                # For io-only, just io approval needed
                if approved_by_io:
                    return {"approved": True, "proposal_id": proposal_id}
                return {"approved": False}

            return {"approved": False}

    except Exception as e:
        # AC #8: Log database error and return error response
        logger.error("SMF approval check failed", extra={
            "edge_id": edge_id,
            "error": str(e),
            "error_type": type(e).__name__
        })
        return {
            "status": "error",
            "error": "Failed to check SMF approval status",
            "edge_id": edge_id,
            "details": str(e)
        }


async def _get_edges_by_names(
    source_name: str,
    target_name: str,
    relation: str
) -> list[dict[str, Any]]:
    """
    Get ALL edges matching source/target/relation (for disambiguation).

    Args:
        source_name: Name of the source node
        target_name: Name of the target node
        relation: Relationship type

    Returns:
        List of edge dicts (may be empty)

    Raises:
        Exception: Database connection or query errors (propagated to caller)

    Story 10.1, Dev Notes: Multiple Edges Query Pattern
    """
    async with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.id, e.source_id, e.target_id, e.relation, e.weight,
                   e.properties, e.memory_sector, e.created_at
            FROM edges e
            JOIN nodes ns ON e.source_id = ns.id
            JOIN nodes nt ON e.target_id = nt.id
            WHERE ns.name = %s AND nt.name = %s AND e.relation = %s
        """, (source_name, target_name, relation))

        results = cursor.fetchall()

        # Format results as list of dicts
        edges = []
        for row in results:
            edges.append({
                "id": str(row[0]),
                "source_id": str(row[1]),
                "target_id": str(row[2]),
                "relation": row[3],
                "weight": row[4],
                "properties": row[5] if row[5] else {},
                "memory_sector": row[6],
                "created_at": row[7].isoformat() if row[7] else None
            })

        return edges


async def _update_edge_sector(
    edge_id: str,
    new_sector: str,
    old_sector: str,
    actor: str
) -> None:
    """
    Update edge memory_sector and add last_reclassification to properties.

    Args:
        edge_id: UUID of the edge to update
        new_sector: New memory sector value
        old_sector: Previous memory sector value
        actor: Who is performing the reclassification

    Story 10.1, AC #6, #7: Audit logging with last_reclassification property
    """
    try:
        # AC6: Build last_reclassification property
        # AC7: ISO 8601 format with Z suffix (e.g., "2026-01-08T14:30:00Z")
        timestamp_utc = datetime.now(timezone.utc)
        timestamp_iso = timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        last_reclassification = {
            "from_sector": old_sector,
            "to_sector": new_sector,
            "timestamp": timestamp_iso,
            "actor": actor
        }

        async with get_connection() as conn:
            cursor = conn.cursor()

            # Update memory_sector and merge properties with last_reclassification
            cursor.execute("""
                UPDATE edges
                SET memory_sector = %s,
                    properties = coalesce(properties, '{}'::jsonb) || %s::jsonb,
                    modified_at = NOW()
                WHERE id = %s
            """, (new_sector, json.dumps({"last_reclassification": last_reclassification}), edge_id))

            conn.commit()

    except Exception as e:
        logger.error("Failed to update edge sector", extra={
            "edge_id": edge_id,
            "new_sector": new_sector,
            "error": str(e)
        }, exc_info=True)
        raise


async def handle_reclassify_memory_sector(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    MCP Tool Handler for reclassify_memory_sector.

    Extracts parameters from arguments dict and calls the main function.

    Args:
        arguments: Tool arguments containing:
            - source_name: Name of the source node
            - target_name: Name of the target node
            - relation: Relationship type
            - new_sector: Target memory sector
            - edge_id: Optional UUID for disambiguation
            - actor: Who is performing the reclassification (default: "I/O")

    Returns:
        Dict with status and reclassification details
    """
    return await reclassify_memory_sector(
        source_name=arguments.get("source_name", ""),
        target_name=arguments.get("target_name", ""),
        relation=arguments.get("relation", ""),
        new_sector=arguments.get("new_sector", ""),
        edge_id=arguments.get("edge_id"),
        actor=arguments.get("actor", "I/O")
    )
