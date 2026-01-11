"""
Database helper utilities for cognitive-memory tests.

Provides utilities for:
- Creating test data
- Cleaning up test data
- Getting table counts
- Transaction helpers
"""

import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extensions import connection
from psycopg2.extras import DictCursor


def create_test_node(
    conn: connection,
    label: str = "TestLabel",
    name: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a test node in the database.

    Args:
        conn: Database connection
        label: Node label
        name: Node name (auto-generated if None)
        properties: Node properties (default: {})

    Returns:
        Node ID (UUID string)
    """
    if name is None:
        name = f"TestNode_{uuid.uuid4().hex[:8]}"

    if properties is None:
        properties = {"test": True, "created_by": "test_framework"}

    cursor = conn.cursor(cursor_factory=DictCursor)

    # Get a vector_id (use a placeholder)
    vector_id = 999999

    cursor.execute(
        """
        INSERT INTO graph_nodes (label, name, properties, vector_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (label, name, properties, vector_id),
    )

    node_id = cursor.fetchone()["id"]
    conn.commit()

    return node_id


def create_test_edge(
    conn: connection,
    source_name: str,
    target_name: str,
    relation: str = "TEST_RELATION",
    weight: float = 1.0,
    properties: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Create a test edge in the database.

    Args:
        conn: Database connection
        source_name: Source node name (will be created if not exists)
        target_name: Target node name (will be created if not exists)
        relation: Edge relation type
        weight: Edge weight (0-1)
        properties: Edge properties (default: {})

    Returns:
        Edge ID (UUID string)
    """
    if properties is None:
        properties = {"test": True, "created_by": "test_framework"}

    cursor = conn.cursor(cursor_factory=DictCursor)

    # Ensure source node exists
    cursor.execute("SELECT id FROM graph_nodes WHERE name = %s", (source_name,))
    source_result = cursor.fetchone()

    if source_result:
        source_id = source_result["id"]
    else:
        source_id = create_test_node(conn, "TestLabel", source_name)

    # Ensure target node exists
    cursor.execute("SELECT id FROM graph_nodes WHERE name = %s", (target_name,))
    target_result = cursor.fetchone()

    if target_result:
        target_id = target_result["id"]
    else:
        target_id = create_test_node(conn, "TestLabel", target_name)

    # Create edge
    cursor.execute(
        """
        INSERT INTO graph_edges (source_id, target_id, relation, weight, properties)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (source_id, target_id, relation, weight, properties),
    )

    edge_id = cursor.fetchone()["id"]
    conn.commit()

    return edge_id


def create_test_insight(
    conn: connection,
    content: Optional[str] = None,
    memory_strength: float = 0.5,
) -> int:
    """
    Create a test L2 insight in the database.

    Args:
        conn: Database connection
        content: Insight content (auto-generated if None)
        memory_strength: Memory strength value (0-1)

    Returns:
        Insight ID (integer)
    """
    if content is None:
        content = f"Test insight created at {uuid.uuid4().hex[:8]}"

    cursor = conn.cursor(cursor_factory=DictCursor)

    # Create embedding (1536 dimensions)
    embedding = [0.01 * i for i in range(1536)]

    cursor.execute(
        """
        INSERT INTO l2_insights (content, embedding, memory_strength)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (content, embedding, memory_strength),
    )

    insight_id = cursor.fetchone()["id"]
    conn.commit()

    return insight_id


def create_test_episode(
    conn: connection,
    query: Optional[str] = None,
    reward: float = 0.0,
) -> int:
    """
    Create a test episode in the database.

    Args:
        conn: Database connection
        query: Episode query (auto-generated if None)
        reward: Episode reward (-1 to 1)

    Returns:
        Episode ID (integer)
    """
    if query is None:
        query = f"Test query {uuid.uuid4().hex[:8]}"

    if reward is None:
        reward = 0.0

    cursor = conn.cursor(cursor_factory=DictCursor)

    reflection = f"Test reflection for {query}"

    cursor.execute(
        """
        INSERT INTO episodes (query, reward, reflection)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (query, reward, reflection),
    )

    episode_id = cursor.fetchone()["id"]
    conn.commit()

    return episode_id


def get_table_counts(conn: connection) -> Dict[str, int]:
    """
    Get counts for all major tables.

    Args:
        conn: Database connection

    Returns:
        Dict of table_name -> row_count
    """
    tables = [
        "graph_nodes",
        "graph_edges",
        "l2_insights",
        "episodes",
        "working_memory",
        "raw_dialogues",
    ]

    counts = {}
    cursor = conn.cursor(cursor_factory=DictCursor)

    for table in tables:
        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
        result = cursor.fetchone()
        counts[table] = result["count"]

    return counts


def cleanup_test_data(conn: connection, test_prefix: str = "Test") -> None:
    """
    Clean up test data from database.

    Args:
        conn: Database connection
        test_prefix: Prefix used to identify test data
    """
    cursor = conn.cursor(cursor_factory=DictCursor)

    # Clean up in reverse dependency order
    tables = [
        "episodes",
        "l2_insights",
        "graph_edges",
        "graph_nodes",
        "working_memory",
        "raw_dialogues",
    ]

    for table in tables:
        # For graph_nodes, we need to delete edges first
        if table == "graph_nodes":
            cursor.execute(
                """
                DELETE FROM graph_edges
                WHERE source_id IN (
                    SELECT id FROM graph_nodes WHERE name LIKE %s
                )
                OR target_id IN (
                    SELECT id FROM graph_nodes WHERE name LIKE %s
                )
                """,
                (f"{test_prefix}%", f"{test_prefix}%"),
            )

        # Delete from table
        cursor.execute(f"DELETE FROM {table} WHERE name LIKE %s", (f"{test_prefix}%",))

    conn.commit()


def transaction_rollback(conn: connection) -> None:
    """
    Rollback a transaction.

    Args:
        conn: Database connection
    """
    try:
        conn.rollback()
    except Exception:
        pass  # Connection might already be closed
