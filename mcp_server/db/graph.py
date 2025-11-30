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
            cursor.execute(
                """
                INSERT INTO nodes (label, name, properties, vector_id)
                VALUES (%s, %s, %s::jsonb, %s)
                ON CONFLICT (label, name) DO NOTHING
                RETURNING id, label, name, created_at;
                """,
                (label, name, properties, vector_id),
            )

            result = cursor.fetchone()

            if result:
                # New node was created
                node_id = str(result["id"])
                created_label = result["label"]
                created_name = result["name"]
                created = True

                logger.debug(f"Created new node: id={node_id}, label={created_label}, name={created_name}")

            else:
                # Node already exists, fetch the existing one
                cursor.execute(
                    """
                    SELECT id, label, name, created_at
                    FROM nodes
                    WHERE label = %s AND name = %s
                    LIMIT 1;
                    """,
                    (label, name),
                )

                existing_result = cursor.fetchone()
                if not existing_result:
                    raise RuntimeError(f"Failed to find existing node after conflict: label={label}, name={name}")

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
            cursor.execute(
                """
                INSERT INTO edges (source_id, target_id, relation, weight, properties)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb)
                ON CONFLICT (source_id, target_id, relation)
                DO UPDATE SET
                    weight = EXCLUDED.weight,
                    properties = EXCLUDED.properties
                RETURNING id, source_id, target_id, relation, weight, created_at;
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
                created = True

                logger.debug(f"Created new edge: id={edge_id}, source={created_source_id}, target={created_target_id}, relation={created_relation}")

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
                SELECT DISTINCT ON (id)
                    id, label, name, properties, relation, weight, distance
                FROM neighbors
                ORDER BY id, distance ASC, weight DESC;
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
