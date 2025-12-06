"""
Graph Database Operations Module

Provides database functions for graph node and edge operations.
Implements idempotent INSERT with conflict resolution using PostgreSQL
UNIQUE constraints.

Story 4.2: graph_add_node Tool Implementation
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


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


def query_neighbors(node_id: str, relation_type: str | None = None, max_depth: int = 1) -> list[dict[str, Any]]:
    """
    Query neighbor nodes using single-hop or multi-hop traversal with cycle detection.

    Uses PostgreSQL WITH RECURSIVE CTE for graph traversal with cycle prevention
    and optional relation type filtering.

    Args:
        node_id: UUID string of the starting node
        relation_type: Optional filter for specific relation types (e.g., "USES", "SOLVES")
        max_depth: Maximum traversal depth (1-5, default 1)

    Returns:
        List of neighbor node dicts with relation, distance, and weight data,
        sorted by distance (ASC) then weight (DESC)
    """
    logger = logging.getLogger(__name__)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Use recursive CTE for multi-hop graph traversal with cycle detection
            cursor.execute(
                """
                WITH RECURSIVE neighbors AS (
                    -- Base case: direct neighbors (depth=1)
                    SELECT
                        n.id,
                        n.label,
                        n.name,
                        n.properties,
                        e.relation,
                        e.weight,
                        1 AS distance,
                        ARRAY[e.source_id, n.id] AS path
                    FROM edges e
                    JOIN nodes n ON e.target_id = n.id
                    WHERE e.source_id = %s::uuid
                        AND (%s IS NULL OR e.relation = %s)

                    UNION ALL

                    -- Recursive case: next hop
                    SELECT
                        n.id,
                        n.label,
                        n.name,
                        n.properties,
                        e.relation,
                        e.weight,
                        nb.distance + 1 AS distance,
                        nb.path || n.id AS path
                    FROM neighbors nb
                    JOIN edges e ON e.source_id = nb.id
                    JOIN nodes n ON e.target_id = n.id
                    WHERE nb.distance < %s
                        AND NOT (n.id = ANY(nb.path))  -- Cycle detection
                        AND (%s IS NULL OR e.relation = %s)
                )
                SELECT id, label, name, properties, relation, weight, distance
                FROM neighbors
                ORDER BY distance ASC, weight DESC, name ASC;
                """,
                (node_id, relation_type, relation_type, max_depth, relation_type, relation_type),
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
                })

            logger.debug(f"Found {len(neighbors)} neighbors for node {node_id} with max_depth={max_depth}")
            return neighbors

    except Exception as e:
        logger.error(f"Failed to query neighbors: node_id={node_id}, relation_type={relation_type}, max_depth={max_depth}, error={e}")
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
