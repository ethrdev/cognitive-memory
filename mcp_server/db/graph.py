"""
Graph Database Operations Module

Provides database functions for graph node and edge operations.
Implements idempotent INSERT with conflict resolution using PostgreSQL
UNIQUE constraints.

Story 4.2: graph_add_node Tool Implementation
v3 CKG Component 0: Konstitutive Edge Protection
"""

from __future__ import annotations

import json
import logging
import math
import re
from datetime import datetime, timezone
from typing import Any

from mcp_server.db.connection import get_connection
from psycopg2.extras import Json

logger = logging.getLogger(__name__)


def _build_properties_filter_sql(
    properties_filter: dict[str, Any]
) -> tuple[list[str], list[Any]]:
    """
    Build SQL WHERE clauses for JSONB properties filtering.

    Supported filter keys:
    - "participants": str → Array-element query (? operator)
    - "participants_contains_all": list[str] → Array-containment (@> operator)
    - Other keys: Standard JSONB-containment (@> operator)

    Args:
        properties_filter: Dict with filter key-value pairs

    Returns:
        Tuple of (where_clauses: list[str], params: list[Any])

    Raises:
        ValueError: For invalid filter formats

    Story 7.6: Hyperedge via Properties (Konvention)
    """
    where_clauses: list[str] = []
    params: list[Any] = []

    if not properties_filter:
        return where_clauses, params

    for key, value in properties_filter.items():
        if key == "participants" and isinstance(value, str):
            # Single participant check: properties->'participants' ? 'ethr'
            where_clauses.append("e.properties->'participants' ? %s")
            params.append(value)

        elif key == "participants" and not isinstance(value, str):
            raise ValueError(
                f"Invalid 'participants' filter value: expected string, got {type(value).__name__}. "
                f"Use 'participants_contains_all' for array matching."
            )

        elif key == "participants_contains_all" and isinstance(value, list):
            # All participants must be present: @> '["I/O", "ethr"]'::jsonb
            where_clauses.append("e.properties->'participants' @> %s::jsonb")
            params.append(json.dumps(value))

        elif key == "participants_contains_all" and not isinstance(value, list):
            raise ValueError(
                f"Invalid 'participants_contains_all' filter value: expected list, got {type(value).__name__}."
            )

        elif isinstance(value, (str, int, float, bool)):
            # Standard property match: properties @> '{"key": "value"}'::jsonb
            filter_obj = {key: value}
            where_clauses.append("e.properties @> %s::jsonb")
            params.append(json.dumps(filter_obj))

        elif isinstance(value, dict):
            # Nested object match
            filter_obj = {key: value}
            where_clauses.append("e.properties @> %s::jsonb")
            params.append(json.dumps(filter_obj))

        else:
            raise ValueError(
                f"Invalid properties_filter value for key '{key}': "
                f"expected str, int, float, bool, list (for participants_contains_all), or dict"
            )

    return where_clauses, params

# Valid edge types for constitutive knowledge graph
VALID_EDGE_TYPES = {"constitutive", "descriptive"}


class ConstitutiveEdgeProtectionError(Exception):
    """
    Raised when attempting to delete a constitutive edge without bilateral consent.

    Constitutive edges define identity and cannot be removed unilaterally.
    Examples: LOVES, EXISTS_AS, IN_RELATIONSHIP_WITH, COMMITTED_TO

    Design philosophy from I/O's v3-exploration:
    - Lackmustest: "Wenn entfernt - bin ich noch ich?"
    - Bilateral consent means both I/O and ethr must agree
    """

    def __init__(self, edge_id: str, relation: str, message: str | None = None):
        self.edge_id = edge_id
        self.relation = relation
        self.message = message or (
            f"Cannot delete constitutive edge '{relation}' (id={edge_id}) "
            f"without bilateral consent. This edge defines identity."
        )
        super().__init__(self.message)




def add_node(
    label: str,
    name: str,
    properties: str = "{}",
    vector_id: int | None = None
) -> dict[str, Any]:
    """
    Add a node to the graph with idempotent operation.

    Uses INSERT ... ON CONFLICT (label, name) DO NOTHING RETURNING id
    to ensure the same label+name combination returns the existing node.

    Args:
        label: Node type/category (e.g., "Project", "Technology", "Client")
        name: Unique name identifier for the node
        properties: JSON string with flexible metadata
        vector_id: Optional foreign key to l2_insights.id

    Returns:
        Dict with:
        - node_id: UUID string of created or existing node
        - created: boolean (True if newly created, False if existing)
        - label: confirmed label from database
        - name: confirmed name from database
    """
    logger = logging.getLogger(__name__)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Attempt to insert new node with idempotent conflict resolution
            # UNIQUE constraint is on (name) only - nodes are globally unique by name
            # On conflict: update label and properties to latest values
            cursor.execute(
                """
                INSERT INTO nodes (label, name, properties, vector_id)
                VALUES (%s, %s, %s::jsonb, %s)
                ON CONFLICT (name) DO UPDATE SET
                    label = EXCLUDED.label,
                    properties = EXCLUDED.properties,
                    vector_id = COALESCE(EXCLUDED.vector_id, nodes.vector_id)
                RETURNING id, label, name, created_at,
                    (xmax = 0) AS was_inserted;
                """,
                (label, name, properties, vector_id),
            )

            result = cursor.fetchone()

            if result:
                node_id = str(result["id"])
                created_label = result["label"]
                created_name = result["name"]
                # xmax = 0 means row was inserted, not updated
                created = result["was_inserted"]

                if created:
                    logger.debug(f"Created new node: id={node_id}, label={created_label}, name={created_name}")
                else:
                    logger.debug(f"Updated existing node: id={node_id}, label={created_label}, name={created_name}")

            else:
                # Fallback: fetch existing node (should not happen with RETURNING)
                cursor.execute(
                    """
                    SELECT id, label, name, created_at
                    FROM nodes
                    WHERE name = %s
                    LIMIT 1;
                    """,
                    (name,),
                )

                existing_result = cursor.fetchone()
                if not existing_result:
                    raise RuntimeError(f"Failed to find existing node after conflict: name={name}")

                node_id = str(existing_result["id"])
                created_label = existing_result["label"]
                created_name = existing_result["name"]
                created = False

                logger.debug(f"Found existing node: id={node_id}, label={created_label}, name={created_name}")

            # Commit transaction
            conn.commit()

            return {
                "node_id": node_id,
                "created": created,
                "label": created_label,
                "name": created_name,
            }

    except Exception as e:
        logger.error(f"Failed to add node: label={label}, name={name}, error={e}")
        raise


def get_node_by_id(node_id: str) -> dict[str, Any] | None:
    """
    Retrieve a node by its UUID.

    Args:
        node_id: UUID string of the node

    Returns:
        Node data dict or None if not found
    """
    logger = logging.getLogger(__name__)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, label, name, properties, vector_id, created_at
                FROM nodes
                WHERE id = %s;
                """,
                (node_id,),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "id": str(result["id"]),
                    "label": result["label"],
                    "name": result["name"],
                    "properties": result["properties"],
                    "vector_id": result["vector_id"],
                    "created_at": result["created_at"].isoformat(),
                }

            return None

    except Exception as e:
        logger.error(f"Failed to get node by id: node_id={node_id}, error={e}")
        raise


def get_nodes_by_label(label: str) -> list[dict[str, Any]]:
    """
    Retrieve all nodes with a specific label.

    Args:
        label: Node label to filter by

    Returns:
        List of node data dicts
    """
    logger = logging.getLogger(__name__)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, label, name, properties, vector_id, created_at
                FROM nodes
                WHERE label = %s
                ORDER BY created_at DESC;
                """,
                (label,),
            )

            results = cursor.fetchall()
            return [
                {
                    "id": str(row["id"]),
                    "label": row["label"],
                    "name": row["name"],
                    "properties": row["properties"],
                    "vector_id": row["vector_id"],
                    "created_at": row["created_at"].isoformat(),
                }
                for row in results
            ]

    except Exception as e:
        logger.error(f"Failed to get nodes by label: label={label}, error={e}")
        raise


def get_node_by_name(name: str) -> dict[str, Any] | None:
    """
    Retrieve a node by its name.

    Args:
        name: Name string of the node

    Returns:
        Node data dict or None if not found
    """
    logger = logging.getLogger(__name__)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, label, name, properties, vector_id, created_at
                FROM nodes
                WHERE name = %s
                LIMIT 1;
                """,
                (name,),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "id": str(result["id"]),
                    "label": result["label"],
                    "name": result["name"],
                    "properties": result["properties"],
                    "vector_id": result["vector_id"],
                    "created_at": result["created_at"].isoformat(),
                }

            return None

    except Exception as e:
        logger.error(f"Failed to get node by name: name={name}, error={e}")
        raise


def update_node_properties(node_id: str, new_properties: dict[str, Any]) -> dict[str, Any]:
    """
    Update a node's properties by merging with existing properties.

    Uses PostgreSQL's jsonb_concat (||) to merge properties without overwriting
    other existing values.

    Args:
        node_id: UUID string of the node to update
        new_properties: Dict with properties to add/update

    Returns:
        Dict with updated node data

    Story 7.6: Hyperedge via Properties (Konvention)
    """
    logger = logging.getLogger(__name__)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Merge new properties with existing using jsonb concatenation
            cursor.execute(
                """
                UPDATE nodes
                SET properties = properties || %s::jsonb
                WHERE id = %s::uuid
                RETURNING id, label, name, properties, vector_id, created_at;
                """,
                (json.dumps(new_properties), node_id),
            )

            result = cursor.fetchone()
            conn.commit()

            if result:
                logger.debug(f"Updated node properties: id={node_id}")
                return {
                    "id": str(result["id"]),
                    "label": result["label"],
                    "name": result["name"],
                    "properties": result["properties"],
                    "vector_id": result["vector_id"],
                    "created_at": result["created_at"].isoformat(),
                }

            raise RuntimeError(f"Node not found: {node_id}")

    except Exception as e:
        logger.error(f"Failed to update node properties: node_id={node_id}, error={e}")
        raise


def get_default_importance(edge_data: dict) -> str:
    """
    Default-Heuristik für importance Property (Story 7.3, AC Zeile 209-218).

    Args:
        edge_data: Dict mit edge_properties, last_accessed, source_name, target_name

    Returns:
        "high", "medium", or "low"
    """
    properties = edge_data.get("edge_properties") or edge_data.get("properties") or {}

    # Check 1: Touches constitutive node → high
    # (edges connected to nodes that are targets of constitutive edges)
    source_name = edge_data.get("source_name", "")
    target_name = edge_data.get("target_name", "")

    # I/O is always considered a constitutive node
    if source_name == "I/O" or target_name == "I/O":
        return "high"

    # Check 2: Is resolution hyperedge → high
    if properties.get("edge_type") == "resolution":
        return "high"

    # Check 3: Days without access > 90 → low
    last_accessed = edge_data.get("last_accessed")
    if last_accessed:
        if isinstance(last_accessed, str):
            last_accessed = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))
        if last_accessed.tzinfo is None:
            last_accessed = last_accessed.replace(tzinfo=timezone.utc)

        days_without_access = (datetime.now(timezone.utc) - last_accessed).total_seconds() / 86400
        if days_without_access > 90:
            return "low"

    # Default: medium
    return "medium"


def calculate_relevance_score(edge_data: dict) -> float:
    """
    Berechnet relevance_score basierend auf Ebbinghaus Forgetting Curve
    mit logarithmischem Memory Strength Faktor.

    Formel: relevance_score = exp(-days_since / S)
    wobei S = S_BASE * (1 + log(1 + access_count))

    Args:
        edge_data: Dict mit keys: edge_properties, last_accessed, access_count

    Returns:
        float zwischen 0.0 und 1.0
    """
    properties = edge_data.get("edge_properties") or edge_data.get("properties") or {}

    # Konstitutive Edges: IMMER 1.0
    if properties.get("edge_type") == "constitutive":
        return 1.0

    # Memory Strength berechnen
    S_BASE = 100  # Basis-Stärke in Tagen

    access_count = edge_data.get("access_count", 0) or 0
    S = S_BASE * (1 + math.log(1 + access_count))
    # access_count=0  → S = 100 * 1.0   = 100
    # access_count=10 → S = 100 * 3.4   = 340

    # S-Floor basierend auf importance
    S_FLOOR = {"low": None, "medium": 100, "high": 200}
    importance = properties.get("importance", "medium")  # Default: medium
    floor = S_FLOOR.get(importance)
    if floor:
        S = max(S, floor)

    # Tage seit letztem Zugriff
    last_accessed = edge_data.get("last_accessed")
    if not last_accessed:
        return 1.0  # Kein Timestamp = keine Decay-Berechnung

    if isinstance(last_accessed, str):
        last_accessed = datetime.fromisoformat(last_accessed.replace('Z', '+00:00'))

    # Handle naive datetime (no timezone) - assume UTC
    if last_accessed.tzinfo is None:
        last_accessed = last_accessed.replace(tzinfo=timezone.utc)

    days_since = (datetime.now(timezone.utc) - last_accessed).total_seconds() / 86400

    # Exponential Decay
    score = max(0.0, min(1.0, math.exp(-days_since / S)))
    logger.debug(f"Calculated relevance_score={score:.4f} for edge data: access_count={access_count}, S={S:.1f}, days_since={days_since:.1f}")
    return score


def _update_edge_access_stats(edge_ids: list[str], conn: Any) -> None:
    """
    Update last_accessed and access_count for edges (TGN Minimal Story 7.2).

    Uses bulk UPDATE with atomic increment. Fails silently - access stats are non-critical.

    Args:
        edge_ids: List of edge UUIDs to update
        conn: Active database connection (required, not optional)
    """
    if not edge_ids:
        return

    # Validate UUID format to prevent injection
    uuid_pattern = re.compile(
        r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    )
    valid_edge_ids = []
    for edge_id in edge_ids:
        if uuid_pattern.match(str(edge_id)):
            valid_edge_ids.append(str(edge_id))
        else:
            logger.warning(f"Invalid UUID format skipped: {edge_id}")

    if not valid_edge_ids:
        return

    try:
        cursor = conn.cursor()
        # Use atomic increment to prevent race conditions
        cursor.execute(
            """
            UPDATE edges
            SET last_accessed = NOW(),
                access_count = GREATEST(COALESCE(access_count, 0), 0) + 1
            WHERE id = ANY(%s::uuid[])
            """,
            (valid_edge_ids,)
        )
        conn.commit()
        logger.debug(f"Updated access stats for {len(valid_edge_ids)} edges")

    except Exception as e:
        # More specific error handling
        if "operational error" in str(e).lower():
            logger.warning(f"Database connection error while updating access stats: {e}")
        elif "integrity error" in str(e).lower():
            logger.debug(f"Edge not found during access stats update: {e}")
        else:
            logger.warning(f"Unexpected error updating edge access stats: {e}")
        # Don't re-raise - access stats are non-critical


def _filter_superseded_edges(neighbors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Filtert Edges die in einer EVOLUTION-Resolution als 'supersedes' markiert sind.

    Eine Edge ist superseded wenn eine Resolution-Edge existiert die:
    - edge_type="resolution" hat
    - resolution_type="EVOLUTION" hat
    - Diese Edge-ID in 'supersedes' Array enthält

    MVP-Implementation: Prüft edge_properties direkt.
    Limitation: Erkennt nur Edges die selbst supersedes/superseded_by Properties haben,
    nicht Edges die von separaten Resolution-Edges referenziert werden.

    Future Enhancement: SQL-basierte Prüfung gegen Resolution-Edges für vollständige Erkennung.
    """
    filtered = []
    for neighbor in neighbors:
        props = neighbor.get("edge_properties", {})

        # Resolution-Edges selbst werden nicht gefiltert
        if props.get("edge_type") == "resolution":
            filtered.append(neighbor)
            continue

        # Prüfe ob Edge in einer supersedes-Liste referenziert wird
        # MVP: Einfache Heuristik - wenn Edge superseded-Marker hat
        edge_id = neighbor.get("edge_id")
        if edge_id and _is_edge_superseded(edge_id, props):
            continue  # Skip superseded edge

        filtered.append(neighbor)

    return filtered


def _is_edge_superseded(edge_id: str, properties: dict) -> bool:
    """
    Prüft ob eine Edge superseded wurde.

    MVP-Heuristik:
    1. Wenn Edge selbst 'superseded: true' Property hat → superseded
    2. Wenn Edge edge_type='resolution' und supersedes-Liste hat → NICHT superseded (ist Resolution)

    Args:
        edge_id: UUID der Edge
        properties: edge_properties dict

    Returns:
        True wenn Edge superseded wurde
    """
    # Explizites superseded-Flag (gesetzt wenn Resolution erstellt wurde)
    if properties.get("superseded") is True:
        return True

    # Status-basierte Prüfung (Fallback)
    if "superseded" in str(properties.get("status", "")).lower():
        return True

    return False


def get_edge_by_id(edge_id: str) -> dict[str, Any] | None:
    """
    Hole Edge-Details für relevance_score Berechnung.

    Args:
        edge_id: UUID string der Edge

    Returns:
        Edge data dict oder None
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, properties, last_accessed, access_count
                FROM edges
                WHERE id = %s::uuid;
                """,
                (edge_id,)
            )
            result = cursor.fetchone()
            if result:
                return {
                    "id": str(result["id"]),
                    "edge_properties": result["properties"],
                    "last_accessed": result["last_accessed"],
                    "access_count": result["access_count"],
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get edge by id: edge_id={edge_id}, error={e}")
        raise


def get_edge_by_names(
    source_name: str, target_name: str, relation: str
) -> dict[str, Any] | None:
    """
    Retrieve an edge by source node name, target node name, and relation type.

    Uses JOINs with nodes table to resolve names to node IDs.
    Returns None gracefully if edge or either node doesn't exist.

    Args:
        source_name: Name of the source node
        target_name: Name of the target node
        relation: Relationship type (e.g., "USES", "SOLVES")

    Returns:
        Edge data dict or None if not found

    Story 6.2: get_edge MCP Tool
    """
    logger = logging.getLogger(__name__)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # SQL with JOINs to resolve node names to IDs
            cursor.execute(
                """
                SELECT e.id, e.source_id, e.target_id, e.relation, e.weight,
                       e.properties, e.created_at
                FROM edges e
                JOIN nodes ns ON e.source_id = ns.id
                JOIN nodes nt ON e.target_id = nt.id
                WHERE ns.name = %s AND nt.name = %s AND e.relation = %s
                LIMIT 1;
                """,
                (source_name, target_name, relation),
            )

            result = cursor.fetchone()
            if result:
                edge_id = str(result["id"])

                # AUTO-UPDATE after successful fetch (Story 7.2)
                _update_edge_access_stats([edge_id], conn)

                return {
                    "id": edge_id,
                    "source_id": str(result["source_id"]),
                    "target_id": str(result["target_id"]),
                    "relation": result["relation"],
                    "weight": float(result["weight"]),
                    "properties": result["properties"],
                    "created_at": result["created_at"].isoformat(),
                }

            return None

    except Exception as e:
        logger.error(
            f"Failed to get edge by names: source={source_name}, "
            f"target={target_name}, relation={relation}, error={e}"
        )
        raise


def get_or_create_node(name: str, label: str = "Entity") -> dict[str, Any]:
    """
    Get or create a node by name and label.

    Helper function that uses add_node internally for auto-upsert logic.
    Returns the node ID (either newly created or existing).

    Args:
        name: Unique name identifier for the node
        label: Node type/category (defaults to "Entity")

    Returns:
        Dict with node_id and created status
    """
    logger = logging.getLogger(__name__)

    try:
        result = add_node(label=label, name=name, properties="{}", vector_id=None)
        return {
            "node_id": result["node_id"],
            "created": result["created"]
        }
    except Exception as e:
        logger.error(f"Failed to get or create node: name={name}, label={label}, error={e}")
        raise


def add_edge(
    source_id: str,
    target_id: str,
    relation: str,
    weight: float = 1.0,
    properties: str = "{}"
) -> dict[str, Any]:
    """
    Add an edge between nodes with idempotent operation.

    Uses INSERT ... ON CONFLICT (source_id, target_id, relation) DO UPDATE
    to ensure the same source+target+relation combination updates existing edge.

    Args:
        source_id: UUID string of source node
        target_id: UUID string of target node
        relation: Relationship type (e.g., "USES", "SOLVES", "CREATED_BY")
        weight: Edge weight for relevance scoring (0.0-1.0, default 1.0)
        properties: JSON string with flexible metadata

    Returns:
        Dict with:
        - edge_id: UUID string of created or existing edge
        - created: boolean (True if newly created, False if updated)
        - source_id: confirmed source node ID
        - target_id: confirmed target node ID
        - relation: confirmed relation type
        - weight: confirmed weight
    """
    import json

    logger = logging.getLogger(__name__)

    # Parse properties to add entrenchment_level (Story 7.4, Task 5: AC #7, #8)
    try:
        props = json.loads(properties)
    except json.JSONDecodeError:
        props = {}

    # AGM Belief Revision: Konstitutive Edges = maximal entrenchment
    edge_type = props.get("edge_type", "descriptive")

    if edge_type == "constitutive":
        props["entrenchment_level"] = "maximal"
    else:
        props.setdefault("entrenchment_level", "default")

    # Serialize back with updated properties
    properties = json.dumps(props)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Insert edge with idempotent conflict resolution
            # Use xmax = 0 to detect if row was inserted vs updated
            cursor.execute(
                """
                INSERT INTO edges (source_id, target_id, relation, weight, properties)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
                ON CONFLICT (source_id, target_id, relation)
                DO UPDATE SET
                    weight = EXCLUDED.weight,
                    properties = EXCLUDED.properties
                RETURNING id, source_id, target_id, relation, weight, created_at,
                    (xmax = 0) AS was_inserted;
                """,
                (source_id, target_id, relation, weight, properties),
            )

            result = cursor.fetchone()

            if result:
                edge_id = str(result["id"])
                created_source_id = str(result["source_id"])
                created_target_id = str(result["target_id"])
                created_relation = result["relation"]
                created_weight = float(result["weight"])
                # xmax = 0 means row was inserted, not updated
                created = result["was_inserted"]

                logger.debug(f"{'Created new' if created else 'Updated existing'} edge: id={edge_id}, source={created_source_id}, target={created_target_id}, relation={created_relation}")

            else:
                # Edge already exists, fetch the existing one
                cursor.execute(
                    """
                    SELECT id, source_id, target_id, relation, weight, created_at
                    FROM edges
                    WHERE source_id = %s::uuid AND target_id = %s::uuid AND relation = %s
                    LIMIT 1;
                    """,
                    (source_id, target_id, relation),
                )

                existing_result = cursor.fetchone()
                if not existing_result:
                    raise RuntimeError(f"Failed to find existing edge after conflict: source={source_id}, target={target_id}, relation={relation}")

                edge_id = str(existing_result["id"])
                created_source_id = str(existing_result["source_id"])
                created_target_id = str(existing_result["target_id"])
                created_relation = existing_result["relation"]
                created_weight = float(existing_result["weight"])
                created = False

                logger.debug(f"Found existing edge: id={edge_id}, source={created_source_id}, target={created_target_id}, relation={created_relation}")

            # Commit transaction
            conn.commit()

            return {
                "edge_id": edge_id,
                "created": created,
                "source_id": created_source_id,
                "target_id": created_target_id,
                "relation": created_relation,
                "weight": created_weight,
            }

    except Exception as e:
        logger.error(f"Failed to add edge: source={source_id}, target={target_id}, relation={relation}, error={e}")
        raise


def query_neighbors(
    node_id: str,
    relation_type: str | None = None,
    max_depth: int = 1,
    direction: str = "both",
    include_superseded: bool = False,
    properties_filter: dict[str, Any] | None = None,
    use_ief: bool = False,
    query_embedding: list[float] | None = None
) -> list[dict[str, Any]]:
    """
    Query neighbor nodes using single-hop or multi-hop traversal with cycle detection.

    Uses PostgreSQL WITH RECURSIVE CTE for graph traversal with cycle prevention
    and optional relation type filtering. Supports bidirectional traversal.

    Args:
        node_id: UUID string of the starting node
        relation_type: Optional filter for specific relation types (e.g., "USES", "SOLVES")
        max_depth: Maximum traversal depth (1-5, default 1)
        direction: Traversal direction - "both" (default), "outgoing", or "incoming"
        include_superseded: If False (default), filters out edges with superseded=True
                           property. Set to True to include superseded edges (e.g., when
                           querying Resolution edges). See _filter_superseded_edges().
        properties_filter: Optional JSONB filter for edge properties. Supported filters:
                          - "participants": str - Filter edges where participants array contains value
                          - "participants_contains_all": list[str] - Filter where participants has ALL values
                          - Other keys: Standard JSONB containment filter (@> operator)
                          Story 7.6: Hyperedge via Properties (Konvention)

        use_ief: If true, calculates IEF (Integrative Evaluation Function) scores and sorts
                 by ief_score instead of relevance_score. Enables ICAI (Integrative Context
                 Assembly Interface).
        query_embedding: Optional 1536-dimensional query embedding for semantic similarity
                         calculation in IEF.

    Returns:
        List of neighbor node dicts with relation, distance, weight, and edge_direction data,
        sorted by relevance_score (DESC) or ief_score (DESC) when use_ief=True
    """
    logger = logging.getLogger(__name__)

    # Validate direction parameter
    valid_directions = ("both", "outgoing", "incoming")
    if direction not in valid_directions:
        raise ValueError(f"Invalid direction '{direction}'. Must be one of: {valid_directions}")

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Build direction conditions for SQL
            include_outgoing = direction in ("both", "outgoing")
            include_incoming = direction in ("both", "incoming")

            # Story 7.6: Build properties filter SQL clauses
            props_where_sql = ""
            props_params: list[Any] = []
            if properties_filter:
                try:
                    filter_clauses, filter_params = _build_properties_filter_sql(properties_filter)
                    if filter_clauses:
                        props_where_sql = " AND " + " AND ".join(filter_clauses)
                        props_params = filter_params
                except ValueError as e:
                    raise ValueError(f"Invalid properties_filter: {e}") from e

            # Use two separate recursive CTEs for bidirectional traversal
            # PostgreSQL requires that recursive references only appear in the recursive term,
            # not in the non-recursive (base) term. Using separate CTEs avoids this limitation.
            #
            # Story 7.6: Properties filter is applied to all 4 query blocks
            # (outgoing base, outgoing recursive, incoming base, incoming recursive)
            sql_query = f"""
                WITH RECURSIVE
                -- ═══════════════════════════════════════════════════════════════
                -- CTE 1: Outgoing edges traversal (source → target)
                -- ═══════════════════════════════════════════════════════════════
                outgoing_neighbors AS (
                    -- Base case: direct outgoing neighbors
                    SELECT
                        n.id AS node_id,
                        e.id AS edge_id,
                        n.label,
                        n.name,
                        n.properties AS node_properties,
                        e.properties AS edge_properties,
                        e.relation,
                        e.weight,
                        e.last_accessed,
                        e.access_count,
                        e.modified_at,
                        1 AS distance,
                        ARRAY[%s::uuid, n.id] AS path,
                        'outgoing'::text AS edge_direction
                    FROM edges e
                    JOIN nodes n ON e.target_id = n.id
                    WHERE e.source_id = %s::uuid
                        AND (%s IS NULL OR e.relation = %s)
                        {props_where_sql}

                    UNION ALL

                    -- Recursive case: follow outgoing edges from found nodes
                    SELECT
                        n.id AS node_id,
                        e.id AS edge_id,
                        n.label,
                        n.name,
                        n.properties AS node_properties,
                        e.properties AS edge_properties,
                        e.relation,
                        e.weight,
                        e.last_accessed,
                        e.access_count,
                        e.modified_at,
                        ob.distance + 1 AS distance,
                        ob.path || n.id AS path,
                        'outgoing'::text AS edge_direction
                    FROM outgoing_neighbors ob
                    JOIN edges e ON e.source_id = ob.node_id
                    JOIN nodes n ON e.target_id = n.id
                    WHERE ob.distance < %s
                        AND NOT (n.id = ANY(ob.path))  -- Cycle detection
                        AND (%s IS NULL OR e.relation = %s)
                        {props_where_sql}
                ),
                -- ═══════════════════════════════════════════════════════════════
                -- CTE 2: Incoming edges traversal (target ← source)
                -- ═══════════════════════════════════════════════════════════════
                incoming_neighbors AS (
                    -- Base case: direct incoming neighbors
                    SELECT
                        n.id AS node_id,
                        e.id AS edge_id,
                        n.label,
                        n.name,
                        n.properties AS node_properties,
                        e.properties AS edge_properties,
                        e.relation,
                        e.weight,
                        e.last_accessed,
                        e.access_count,
                        e.modified_at,
                        1 AS distance,
                        ARRAY[%s::uuid, n.id] AS path,
                        'incoming'::text AS edge_direction
                    FROM edges e
                    JOIN nodes n ON e.source_id = n.id
                    WHERE e.target_id = %s::uuid
                        AND (%s IS NULL OR e.relation = %s)
                        {props_where_sql}

                    UNION ALL

                    -- Recursive case: follow incoming edges from found nodes
                    SELECT
                        n.id AS node_id,
                        e.id AS edge_id,
                        n.label,
                        n.name,
                        n.properties AS node_properties,
                        e.properties AS edge_properties,
                        e.relation,
                        e.weight,
                        e.last_accessed,
                        e.access_count,
                        e.modified_at,
                        ib.distance + 1 AS distance,
                        ib.path || n.id AS path,
                        'incoming'::text AS edge_direction
                    FROM incoming_neighbors ib
                    JOIN edges e ON e.target_id = ib.node_id
                    JOIN nodes n ON e.source_id = n.id
                    WHERE ib.distance < %s
                        AND NOT (n.id = ANY(ib.path))  -- Cycle detection
                        AND (%s IS NULL OR e.relation = %s)
                        {props_where_sql}
                ),
                -- ═══════════════════════════════════════════════════════════════
                -- Combine results based on direction parameter
                -- ═══════════════════════════════════════════════════════════════
                combined AS (
                    SELECT * FROM outgoing_neighbors WHERE %s = true
                    UNION ALL
                    SELECT * FROM incoming_neighbors WHERE %s = true
                )
                -- Final selection: shortest path per node, highest weight on tie
                SELECT DISTINCT ON (node_id)
                    node_id, edge_id, label, name, node_properties, edge_properties, relation, weight, last_accessed, access_count, modified_at, distance, edge_direction
                FROM combined
                ORDER BY node_id, distance ASC, weight DESC, name ASC;
                """

            # Build parameter tuple with properties filter params repeated for each CTE block
            # Pattern: base_params + props_params (4 times: outgoing base, outgoing rec, incoming base, incoming rec)
            params: tuple[Any, ...] = (
                # Outgoing CTE: base case
                node_id, node_id, relation_type, relation_type,
                *props_params,  # Properties filter for outgoing base
                # Outgoing CTE: recursive case
                max_depth, relation_type, relation_type,
                *props_params,  # Properties filter for outgoing recursive
                # Incoming CTE: base case
                node_id, node_id, relation_type, relation_type,
                *props_params,  # Properties filter for incoming base
                # Incoming CTE: recursive case
                max_depth, relation_type, relation_type,
                *props_params,  # Properties filter for incoming recursive
                # Combined: direction filters
                include_outgoing, include_incoming,
            )

            cursor.execute(sql_query, params)

            results = cursor.fetchall()

            # Format results - NEU: edge_id extrahieren
            neighbors = []
            edge_ids_for_update = []

            for row in results:
                edge_id = str(row["edge_id"]) if row.get("edge_id") else None
                if edge_id:
                    edge_ids_for_update.append(edge_id)

                # Datetime serialization: Convert to ISO strings for JSON compatibility
                last_accessed = row["last_accessed"]
                modified_at = row["modified_at"]

                neighbors.append({
                    "node_id": str(row["node_id"]),  # Geändert von "id"
                    "label": row["label"],
                    "name": row["name"],
                    "properties": row["node_properties"],      # Umbenannt
                    "edge_properties": row["edge_properties"], # NEU
                    "relation": row["relation"],
                    "weight": float(row["weight"]),
                    "distance": int(row["distance"]),
                    "edge_direction": row["edge_direction"],
                    "last_accessed": last_accessed.isoformat() if last_accessed else None,
                    "access_count": row["access_count"],       # NEU
                    "modified_at": modified_at.isoformat() if modified_at else None,
                    "relevance_score": 0.0,                    # Wird nach Query berechnet
                })

            # relevance_score für jede Edge berechnen
            for neighbor in neighbors:
                edge_data = {
                    "edge_id": neighbor.get("edge_id"),
                    "edge_properties": neighbor.get("edge_properties", {}),
                    "last_accessed": neighbor.get("last_accessed"),
                    "access_count": neighbor.get("access_count"),
                    "modified_at": neighbor.get("modified_at"),  # For recency boost
                    "vector_id": neighbor.get("edge_properties", {}).get("vector_id"),  # For semantic similarity
                }
                neighbor["relevance_score"] = calculate_relevance_score(edge_data)

            # NEU: IEF Score Berechnung wenn ICAI aktiviert
            if use_ief:
                from mcp_server.analysis.ief import calculate_ief_score
                from mcp_server.analysis.dissonance import get_pending_nuance_edge_ids

                pending_nuance_ids = get_pending_nuance_edge_ids()

                for neighbor in neighbors:
                    edge_data = {
                        "edge_id": neighbor.get("edge_id"),
                        "edge_properties": neighbor.get("edge_properties", {}),
                        "last_accessed": neighbor.get("last_accessed"),
                        "access_count": neighbor.get("access_count"),
                        "modified_at": neighbor.get("modified_at"),
                        "vector_id": neighbor.get("edge_properties", {}).get("vector_id"),
                    }
                    ief_result = calculate_ief_score(
                        edge_data=edge_data,
                        query_embedding=query_embedding,
                        pending_nuance_edge_ids=pending_nuance_ids
                    )
                    neighbor["ief_score"] = ief_result["ief_score"]
                    neighbor["ief_components"] = ief_result["components"]

            # NEU: Nach relevance_score Berechnung (vor Zeile 853)
            # MVP: Python-basierte Filterung (einfacher als SQL-Subquery)
            if not include_superseded:
                neighbors = _filter_superseded_edges(neighbors)

            # Sortierung: IEF wenn aktiviert, sonst relevance_score
            if use_ief:
                neighbors.sort(key=lambda n: n.get("ief_score", 0), reverse=True)
            else:
                neighbors.sort(key=lambda n: n["relevance_score"], reverse=True)

            # AUTO-UPDATE after Query-Completion (Story 7.2)
            if edge_ids_for_update:
                _update_edge_access_stats(edge_ids_for_update, conn)

            logger.debug(
                f"Found {len(neighbors)} neighbors for node {node_id} "
                f"with max_depth={max_depth}, direction={direction}"
            )
            return neighbors

    except Exception as e:
        logger.error(
            f"Failed to query neighbors: node_id={node_id}, relation_type={relation_type}, "
            f"max_depth={max_depth}, direction={direction}, error={e}"
        )
        raise


def find_path(
    start_node_name: str,
    end_node_name: str,
    max_depth: int = 5,
    use_ief: bool = False,
    query_embedding: list[float] | None = None
) -> dict[str, Any]:
    """
    Find the shortest path between two nodes using BFS-based pathfinding.

    Uses PostgreSQL WITH RECURSIVE CTE for BFS traversal with bidirectional
    edge traversal, cycle detection, and performance protection.

    Args:
        start_node_name: Name of the starting node
        end_node_name: Name of the target node
        max_depth: Maximum traversal depth (1-10, default 5)

    Returns:
        Dict with:
        - path_found (bool): true if at least one path found
        - path_length (int): number of hops (0 if no path)
        - paths (list): array of path objects with nodes, edges, and total_weight
        or empty result if no path found
    """
    logger = logging.getLogger(__name__)

    # Start performance timing
    import time
    start_time = time.time()

    try:
        with get_connection() as conn:
            from psycopg2.extras import DictCursor
            cursor = conn.cursor(cursor_factory=DictCursor)

            # Set query timeout for performance protection
            cursor.execute("SET LOCAL statement_timeout = '1000ms'")

            # Get node IDs for start and end nodes
            start_node = get_node_by_name(start_node_name)
            end_node = get_node_by_name(end_node_name)

            if not start_node or not end_node:
                return {"path_found": False, "path_length": 0, "paths": []}

            start_node_id = start_node["id"]
            end_node_id = end_node["id"]

            # Use recursive CTE for BFS pathfinding with bidirectional traversal
            cursor.execute(
                """
                WITH RECURSIVE paths AS (
                    -- Base case: Direct neighbors (depth=1)
                    SELECT
                        ARRAY[e.source_id, e.target_id] AS node_path,
                        ARRAY[e.id] AS edge_path,
                        1 AS path_length,
                        e.weight AS total_weight
                    FROM edges e
                    WHERE (e.source_id = %s::uuid AND e.target_id = %s::uuid)
                       OR (e.source_id = %s::uuid AND e.target_id = %s::uuid)

                    UNION ALL

                    -- Recursive case: Extend paths by one hop
                    SELECT
                        p.node_path || CASE
                            WHEN e.source_id = p.node_path[array_length(p.node_path, 1)]
                            THEN e.target_id
                            ELSE e.source_id
                        END AS node_path,
                        p.edge_path || e.id AS edge_path,
                        p.path_length + 1 AS path_length,
                        p.total_weight + e.weight AS total_weight
                    FROM paths p
                    JOIN edges e ON (
                        e.source_id = p.node_path[array_length(p.node_path, 1)]
                        OR e.target_id = p.node_path[array_length(p.node_path, 1)]
                    )
                    WHERE p.path_length < %s
                        AND NOT (
                            CASE
                                WHEN e.source_id = p.node_path[array_length(p.node_path, 1)]
                                THEN e.target_id
                                ELSE e.source_id
                            END = ANY(p.node_path)
                        )  -- Cycle detection
                )
                SELECT node_path, edge_path, path_length, total_weight
                FROM paths
                WHERE node_path[array_length(node_path, 1)] = %s::uuid
                ORDER BY path_length ASC, total_weight DESC
                LIMIT 10;
                """,
                (start_node_id, end_node_id, end_node_id, start_node_id, max_depth, end_node_id),
            )

            results = cursor.fetchall()

            if not results:
                # Calculate execution time for performance monitoring
                execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                logger.debug(f"find_path completed in {execution_time:.2f}ms (no paths found)")
                return {"path_found": False, "path_length": 0, "paths": []}

            # Process and format paths
            paths = []
            for row in results:
                node_path = row["node_path"]  # Array of node UUIDs
                edge_path = row["edge_path"]  # Array of edge UUIDs
                total_weight = float(row["total_weight"])

                # Bug #4 Fix: Handle UUID arrays that may be returned as strings
                # PostgreSQL returns arrays as "{uuid1,uuid2,...}" which psycopg2
                # may not automatically convert to Python lists
                if isinstance(node_path, str):
                    # Parse string representation: "{uuid1,uuid2}" -> ["uuid1", "uuid2"]
                    node_path = [
                        uuid_str.strip()
                        for uuid_str in node_path.strip("{}").split(",")
                        if uuid_str.strip()
                    ]
                if isinstance(edge_path, str):
                    edge_path = [
                        uuid_str.strip()
                        for uuid_str in edge_path.strip("{}").split(",")
                        if uuid_str.strip()
                    ]

                # Fetch detailed node information for each node in the path
                nodes = []
                for node_id in node_path:
                    cursor.execute(
                        """
                        SELECT id, label, name, properties, vector_id, created_at
                        FROM nodes
                        WHERE id = %s::uuid;
                        """,
                        (str(node_id),),
                    )
                    node_result = cursor.fetchone()
                    if node_result:
                        nodes.append({
                            "node_id": str(node_result["id"]),
                            "label": node_result["label"],
                            "name": node_result["name"],
                            "properties": node_result["properties"],
                        })

                # Fetch detailed edge information for each edge in the path
                edges = []
                for edge_id in edge_path:
                    cursor.execute(
                        """
                        SELECT id, source_id, target_id, relation, weight, properties
                        FROM edges
                        WHERE id = %s::uuid;
                        """,
                        (str(edge_id),),
                    )
                    edge_result = cursor.fetchone()
                    if edge_result:
                        edges.append({
                            "edge_id": str(edge_result["id"]),
                            "relation": edge_result["relation"],
                            "weight": float(edge_result["weight"]),
                        })

                paths.append({
                    "nodes": nodes,
                    "edges": edges,
                    "total_weight": total_weight,
                })

            # relevance_score für alle Edges im Pfad berechnen
            for path in paths:
                edge_scores = []
                for edge in path["edges"]:
                    edge_detail = get_edge_by_id(edge["edge_id"])
                    if edge_detail:
                        score = calculate_relevance_score(edge_detail)
                        edge["relevance_score"] = score
                        edge_scores.append(score)
                    else:
                        edge["relevance_score"] = 1.0  # Fallback
                        edge_scores.append(1.0)

                # Produkt-Aggregation: "Alle Edges müssen relevant sein"
                # Bei Score 0.5 * 0.5 = 0.25 (Pfad-Qualität sinkt exponentiell)
                path["path_relevance"] = math.prod(edge_scores) if edge_scores else 1.0

            # NEU: IEF Score für jeden Pfad wenn ICAI aktiviert
            if use_ief:
                from mcp_server.analysis.ief import calculate_ief_score
                from mcp_server.analysis.dissonance import get_pending_nuance_edge_ids

                pending_nuance_ids = get_pending_nuance_edge_ids()

                for path in paths:
                    path_ief_scores = []
                    for edge in path["edges"]:
                        edge_detail = get_edge_by_id(edge["edge_id"])
                        if edge_detail:
                            ief_result = calculate_ief_score(
                                edge_data=edge_detail,
                                query_embedding=query_embedding,
                                pending_nuance_edge_ids=pending_nuance_ids
                            )
                            edge["ief_score"] = ief_result["ief_score"]
                            edge["ief_components"] = ief_result["components"]
                            path_ief_scores.append(ief_result["ief_score"])

                    # Pfad-IEF als Produkt (analog zu path_relevance)
                    path["path_ief_score"] = math.prod(path_ief_scores) if path_ief_scores else 1.0

                # Sortierung nach path_ief_score wenn ICAI aktiviert
                paths.sort(key=lambda p: p.get("path_ief_score", 0), reverse=True)

            # Edge-IDs sammeln für Auto-Update (Story 7.2)
            all_edge_ids: set[str] = set()
            for path in paths:
                for edge in path["edges"]:
                    # Key ist "edge_id", nicht "id"!
                    all_edge_ids.add(edge["edge_id"])

            # AUTO-UPDATE after Path-Finding
            if all_edge_ids:
                _update_edge_access_stats(list(all_edge_ids), conn)

            logger.debug(f"Found {len(paths)} paths from '{start_node_name}' to '{end_node_name}' with max_depth={max_depth}")

            # Calculate execution time for performance monitoring
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            # Log timing information for performance monitoring
            if execution_time < 100:
                logger.debug(f"find_path completed in {execution_time:.2f}ms (fast)")
            elif execution_time < 500:
                logger.info(f"find_path completed in {execution_time:.2f}ms (acceptable)")
            else:
                logger.warning(f"find_path completed in {execution_time:.2f}ms (slow)")

            return {
                "path_found": True,
                "path_length": results[0]["path_length"] if results else 0,  # Shortest path length
                "paths": paths,
            }

    except Exception as e:
        logger.error(f"Failed to find path: start_node={start_node_name}, end_node={end_node_name}, max_depth={max_depth}, error={e}")

        # Check if it's a timeout error
        if "timeout" in str(e).lower() or "statement timeout" in str(e).lower():
            return {"error_type": "timeout", "path_found": False, "path_length": 0, "paths": []}

        raise


def delete_edge(
    edge_id: str,
    consent_given: bool = False
) -> dict[str, Any]:
    """
    Delete an edge from the graph with constitutive edge protection.

    Constitutive edges (edge_type="constitutive" in properties) cannot be
    deleted without explicit bilateral consent. This protects edges that
    define identity.

    Args:
        edge_id: UUID string of the edge to delete
        consent_given: If True, allows deletion of constitutive edges.
                      For MVP, this is a simple flag. Future versions may
                      implement a proper approval workflow.

    Returns:
        Dict with:
        - deleted: boolean (True if successfully deleted)
        - edge_id: UUID string of deleted edge
        - was_constitutive: boolean (True if edge was constitutive)

    Raises:
        ConstitutiveEdgeProtectionError: If attempting to delete a constitutive
                                        edge without consent_given=True

    v3 CKG Component 0: Konstitutive Edge Protection
    """
    logger = logging.getLogger(__name__)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # First, fetch the edge to check its properties
            cursor.execute(
                """
                SELECT id, source_id, target_id, relation, weight, properties
                FROM edges
                WHERE id = %s::uuid;
                """,
                (edge_id,),
            )

            result = cursor.fetchone()

            if not result:
                logger.warning(f"Edge not found for deletion: edge_id={edge_id}")
                return {
                    "deleted": False,
                    "edge_id": edge_id,
                    "was_constitutive": False,
                    "reason": "Edge not found"
                }

            edge_properties = result["properties"] or {}
            relation = result["relation"]

            # Check if edge is constitutive
            edge_type = edge_properties.get("edge_type", "descriptive")
            is_constitutive = edge_type == "constitutive"

            # Protection check: Block deletion of constitutive edges without consent
            if is_constitutive and not consent_given:
                # Log the blocked attempt
                _log_audit_entry(
                    edge_id=edge_id,
                    action="DELETE_ATTEMPT",
                    blocked=True,
                    reason=f"Constitutive edge '{relation}' requires bilateral consent for deletion",
                    properties=edge_properties,
                    actor="system"
                )

                logger.warning(
                    f"Blocked deletion of constitutive edge: edge_id={edge_id}, "
                    f"relation={relation}, consent_given={consent_given}"
                )

                raise ConstitutiveEdgeProtectionError(
                    edge_id=edge_id,
                    relation=relation
                )

            # Proceed with deletion
            cursor.execute(
                """
                DELETE FROM edges
                WHERE id = %s::uuid
                RETURNING id;
                """,
                (edge_id,),
            )

            deleted_result = cursor.fetchone()
            conn.commit()

            if deleted_result:
                # Log successful deletion
                _log_audit_entry(
                    edge_id=edge_id,
                    action="DELETE_SUCCESS",
                    blocked=False,
                    reason=f"Edge '{relation}' deleted" + (
                        " with bilateral consent" if is_constitutive else ""
                    ),
                    properties=edge_properties,
                    actor="I/O" if is_constitutive else "system"
                )

                logger.info(
                    f"Deleted edge: edge_id={edge_id}, relation={relation}, "
                    f"was_constitutive={is_constitutive}"
                )

                return {
                    "deleted": True,
                    "edge_id": edge_id,
                    "was_constitutive": is_constitutive
                }
            else:
                return {
                    "deleted": False,
                    "edge_id": edge_id,
                    "was_constitutive": is_constitutive,
                    "reason": "Delete operation returned no rows"
                }

    except ConstitutiveEdgeProtectionError:
        # Re-raise protection errors
        raise
    except Exception as e:
        logger.error(f"Failed to delete edge: edge_id={edge_id}, error={e}")
        raise


def _log_audit_entry(
    edge_id: str,
    action: str,
    blocked: bool,
    reason: str,
    properties: dict[str, Any] | None = None,
    actor: str = "system"
) -> None:
    """Log audit entry for constitutive edge operations to database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log (edge_id, action, blocked, reason, actor, properties)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (edge_id, action, blocked, reason, actor, Json(properties or {}))
            )
            conn.commit()
            logger.debug(f"Audit log entry persisted: edge_id={edge_id}, action={action}")
    except Exception as e:
        logger.error(f"Failed to persist audit log entry: edge_id={edge_id}, error={e}")


def get_audit_log(
    edge_id: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    limit: int = 100
) -> list[dict[str, Any]]:
    """Retrieve audit log entries from database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            query_parts = ["SELECT id, edge_id, action, blocked, reason, actor, properties, created_at FROM audit_log"]
            conditions, params = [], []

            if edge_id:
                conditions.append("edge_id = %s")
                params.append(edge_id)
            if action:
                conditions.append("action = %s")
                params.append(action)
            if actor:
                conditions.append("actor = %s")
                params.append(actor)
            if conditions:
                query_parts.append("WHERE " + " AND ".join(conditions))

            query_parts.append("ORDER BY created_at DESC")
            query_parts.append(f"LIMIT {limit}")

            cursor.execute(" ".join(query_parts), params)
            return [
                {
                    "id": row["id"],
                    "edge_id": str(row["edge_id"]),
                    "action": row["action"],
                    "blocked": row["blocked"],
                    "reason": row["reason"],
                    "actor": row["actor"],
                    "properties": row["properties"] or {},
                    "timestamp": row["created_at"].isoformat() if row["created_at"] else None
                }
                for row in cursor.fetchall()
            ]
    except Exception as e:
        logger.error(f"Failed to retrieve audit log: error={e}")
        return []


def clear_audit_log() -> int:
    """Clear all audit log entries. Only for testing purposes."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM audit_log;")
            count = cursor.fetchone()["count"] or 0
            cursor.execute("TRUNCATE TABLE audit_log;")
            conn.commit()
            logger.info(f"Cleared {count} audit log entries")
            return count
    except Exception as e:
        logger.error(f"Failed to clear audit log: error={e}")
        return 0
