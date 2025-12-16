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
from datetime import datetime, timezone
from typing import Any

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)

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


# In-memory audit log for MVP (can be moved to database later)
# TODO: Persist audit log to database - critical for long-term traceability
#       of constitutive edge operations. Current in-memory storage does not
#       survive restarts. See v3-exploration for why this matters.
_audit_log: list[dict[str, Any]] = []


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
                return {
                    "id": str(result["id"]),
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
    logger = logging.getLogger(__name__)

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
    direction: str = "both"
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

    Returns:
        List of neighbor node dicts with relation, distance, weight, and edge_direction data,
        sorted by distance (ASC) then weight (DESC)
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

            # Use two separate recursive CTEs for bidirectional traversal
            # PostgreSQL requires that recursive references only appear in the recursive term,
            # not in the non-recursive (base) term. Using separate CTEs avoids this limitation.
            cursor.execute(
                """
                WITH RECURSIVE
                -- ═══════════════════════════════════════════════════════════════
                -- CTE 1: Outgoing edges traversal (source → target)
                -- ═══════════════════════════════════════════════════════════════
                outgoing_neighbors AS (
                    -- Base case: direct outgoing neighbors
                    SELECT
                        n.id,
                        n.label,
                        n.name,
                        n.properties,
                        e.relation,
                        e.weight,
                        1 AS distance,
                        ARRAY[%s::uuid, n.id] AS path,
                        'outgoing'::text AS edge_direction
                    FROM edges e
                    JOIN nodes n ON e.target_id = n.id
                    WHERE e.source_id = %s::uuid
                        AND (%s IS NULL OR e.relation = %s)

                    UNION ALL

                    -- Recursive case: follow outgoing edges from found nodes
                    SELECT
                        n.id,
                        n.label,
                        n.name,
                        n.properties,
                        e.relation,
                        e.weight,
                        ob.distance + 1 AS distance,
                        ob.path || n.id AS path,
                        'outgoing'::text AS edge_direction
                    FROM outgoing_neighbors ob
                    JOIN edges e ON e.source_id = ob.id
                    JOIN nodes n ON e.target_id = n.id
                    WHERE ob.distance < %s
                        AND NOT (n.id = ANY(ob.path))  -- Cycle detection
                        AND (%s IS NULL OR e.relation = %s)
                ),
                -- ═══════════════════════════════════════════════════════════════
                -- CTE 2: Incoming edges traversal (target ← source)
                -- ═══════════════════════════════════════════════════════════════
                incoming_neighbors AS (
                    -- Base case: direct incoming neighbors
                    SELECT
                        n.id,
                        n.label,
                        n.name,
                        n.properties,
                        e.relation,
                        e.weight,
                        1 AS distance,
                        ARRAY[%s::uuid, n.id] AS path,
                        'incoming'::text AS edge_direction
                    FROM edges e
                    JOIN nodes n ON e.source_id = n.id
                    WHERE e.target_id = %s::uuid
                        AND (%s IS NULL OR e.relation = %s)

                    UNION ALL

                    -- Recursive case: follow incoming edges from found nodes
                    SELECT
                        n.id,
                        n.label,
                        n.name,
                        n.properties,
                        e.relation,
                        e.weight,
                        ib.distance + 1 AS distance,
                        ib.path || n.id AS path,
                        'incoming'::text AS edge_direction
                    FROM incoming_neighbors ib
                    JOIN edges e ON e.target_id = ib.id
                    JOIN nodes n ON e.source_id = n.id
                    WHERE ib.distance < %s
                        AND NOT (n.id = ANY(ib.path))  -- Cycle detection
                        AND (%s IS NULL OR e.relation = %s)
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
                SELECT DISTINCT ON (id)
                    id, label, name, properties, relation, weight, distance, edge_direction
                FROM combined
                ORDER BY id, distance ASC, weight DESC, name ASC;
                """,
                (
                    # Outgoing CTE: base case
                    node_id, node_id, relation_type, relation_type,
                    # Outgoing CTE: recursive case
                    max_depth, relation_type, relation_type,
                    # Incoming CTE: base case
                    node_id, node_id, relation_type, relation_type,
                    # Incoming CTE: recursive case
                    max_depth, relation_type, relation_type,
                    # Combined: direction filters
                    include_outgoing, include_incoming,
                ),
            )

            results = cursor.fetchall()

            # Format results with proper UUID string conversion
            neighbors = []
            for row in results:
                neighbors.append({
                    "node_id": str(row["id"]),
                    "label": row["label"],
                    "name": row["name"],
                    "properties": row["properties"],
                    "relation": row["relation"],
                    "weight": float(row["weight"]),
                    "distance": int(row["distance"]),
                    "edge_direction": row["edge_direction"],
                })

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


def find_path(start_node_name: str, end_node_name: str, max_depth: int = 5) -> dict[str, Any]:
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
                    properties=edge_properties
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
                    properties=edge_properties
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
    properties: dict[str, Any] | None = None
) -> None:
    """
    Internal function to log audit entries for constitutive edge operations.

    For MVP, uses in-memory storage. Future versions may persist to database.
    """
    entry = {
        "edge_id": edge_id,
        "action": action,
        "blocked": blocked,
        "reason": reason,
        "properties": properties or {},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    _audit_log.append(entry)
    logger.debug(f"Audit log entry: {entry}")


def get_audit_log(
    edge_id: str | None = None,
    action: str | None = None,
    limit: int = 100
) -> list[dict[str, Any]]:
    """
    Retrieve audit log entries for constitutive edge operations.

    Args:
        edge_id: Optional filter by edge ID
        action: Optional filter by action type (DELETE_ATTEMPT, DELETE_SUCCESS)
        limit: Maximum number of entries to return (default 100)

    Returns:
        List of audit log entries, most recent first

    v3 CKG Component 0: Audit logging for constitutive edge operations
    """
    filtered = _audit_log

    if edge_id:
        filtered = [e for e in filtered if e["edge_id"] == edge_id]

    if action:
        filtered = [e for e in filtered if e["action"] == action]

    # Return most recent first, limited
    return list(reversed(filtered))[:limit]


def clear_audit_log() -> int:
    """
    Clear all audit log entries. Useful for testing.

    Returns:
        Number of entries cleared
    """
    global _audit_log
    count = len(_audit_log)
    _audit_log = []
    return count
