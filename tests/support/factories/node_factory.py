"""
Node factory for creating test graph nodes.

Provides NodeFactory class for generating test nodes with:
- Configurable labels and properties
- Database integration
- Auto-cleanup
"""

import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extensions import connection
from psycopg2.extras import DictCursor


class NodeFactory:
    """
    Factory for creating test graph nodes.

    Example:
        factory = NodeFactory()
        node = factory.create(label="Agent", name="TestAgent")
        node_id = node["id"]
    """

    def __init__(self):
        """Initialize the factory."""
        self.created_nodes: List[str] = []

    def create(
        self,
        conn: Optional[connection] = None,
        label: str = "TestLabel",
        name: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        vector_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a test node.

        Args:
            conn: Database connection (if provided, saves to DB)
            label: Node label
            name: Node name (auto-generated if None)
            properties: Node properties
            vector_id: Vector ID (auto-generated if None)

        Returns:
            Created node data dict
        """
        if name is None:
            name = f"TestNode_{uuid.uuid4().hex[:8]}"

        if properties is None:
            properties = {"test": True, "factory": "NodeFactory"}

        if vector_id is None:
            vector_id = 999999

        node_data = {
            "id": str(uuid.uuid4()),
            "label": label,
            "name": name,
            "properties": properties,
            "vector_id": vector_id,
            "created_at": "2026-01-11T12:00:00Z",
        }

        # Save to database if connection provided
        if conn is not None:
            node_data["id"] = self._save_to_database(conn, label, name, properties, vector_id)
            self.created_nodes.append(node_data["id"])

        return node_data

    def create_batch(
        self,
        conn: Optional[connection] = None,
        count: int = 5,
        label: str = "TestLabel",
    ) -> List[Dict[str, Any]]:
        """
        Create multiple test nodes.

        Args:
            conn: Database connection
            count: Number of nodes to create
            label: Node label for all nodes

        Returns:
            List of created node data dicts
        """
        nodes = []
        for _ in range(count):
            node = self.create(conn=conn, label=label)
            nodes.append(node)
        return nodes

    def create_with_label(self, conn: connection, label: str) -> Dict[str, Any]:
        """
        Create a node with specific label.

        Args:
            conn: Database connection
            label: Node label

        Returns:
            Created node data dict
        """
        return self.create(conn=conn, label=label)

    def _save_to_database(
        self,
        conn: connection,
        label: str,
        name: str,
        properties: Dict[str, Any],
        vector_id: int,
    ) -> str:
        """
        Save node to database.

        Args:
            conn: Database connection
            label: Node label
            name: Node name
            properties: Node properties
            vector_id: Vector ID

        Returns:
            Created node ID (UUID string)
        """
        cursor = conn.cursor(cursor_factory=DictCursor)

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

    def cleanup(self, conn: Optional[connection] = None) -> None:
        """
        Clean up created nodes.

        Args:
            conn: Database connection (if nodes were saved to DB)
        """
        if not self.created_nodes:
            return

        if conn is not None:
            cursor = conn.cursor(cursor_factory=DictCursor)

            # Delete edges first
            cursor.execute(
                """
                DELETE FROM graph_edges
                WHERE source_id = ANY(%s)
                OR target_id = ANY(%s)
                """,
                (self.created_nodes, self.created_nodes),
            )

            # Delete nodes
            cursor.execute(
                "DELETE FROM graph_nodes WHERE id = ANY(%s)",
                (self.created_nodes,),
            )

            conn.commit()

        self.created_nodes.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()
