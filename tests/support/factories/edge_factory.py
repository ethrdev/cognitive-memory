"""
Edge factory for creating test graph edges.

Provides EdgeFactory class for generating test edges with:
- Configurable source, target, and relation
- Database integration
- Auto-cleanup
"""

import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extensions import connection
from psycopg2.extras import DictCursor


class EdgeFactory:
    """
    Factory for creating test graph edges.

    Example:
        factory = EdgeFactory()
        edge = factory.create(source_name="NodeA", target_name="NodeB", relation="USES")
        edge_id = edge["id"]
    """

    def __init__(self):
        """Initialize the factory."""
        self.created_edges: List[str] = []

    def create(
        self,
        conn: Optional[connection] = None,
        source_name: Optional[str] = None,
        target_name: Optional[str] = None,
        relation: str = "TEST_RELATION",
        weight: float = 1.0,
        properties: Optional[Dict[str, Any]] = None,
        memory_sector: str = "semantic",
    ) -> Dict[str, Any]:
        """
        Create a test edge.

        Args:
            conn: Database connection (if provided, saves to DB)
            source_name: Source node name (auto-generated if None)
            target_name: Target node name (auto-generated if None)
            relation: Edge relation type
            weight: Edge weight (0-1)
            properties: Edge properties
            memory_sector: Memory sector classification

        Returns:
            Created edge data dict
        """
        if source_name is None:
            source_name = f"Source_{uuid.uuid4().hex[:8]}"

        if target_name is None:
            target_name = f"Target_{uuid.uuid4().hex[:8]}"

        if properties is None:
            properties = {"test": True, "factory": "EdgeFactory"}

        edge_data = {
            "id": str(uuid.uuid4()),
            "source_id": str(uuid.uuid4()),
            "target_id": str(uuid.uuid4()),
            "relation": relation,
            "weight": weight,
            "properties": properties,
            "memory_sector": memory_sector,
            "created_at": "2026-01-11T12:00:00Z",
        }

        # Save to database if connection provided
        if conn is not None:
            edge_data["id"] = self._save_to_database(
                conn, source_name, target_name, relation, weight, properties, memory_sector
            )
            self.created_edges.append(edge_data["id"])

        return edge_data

    def create_batch(
        self,
        conn: Optional[connection] = None,
        count: int = 5,
        relation: str = "TEST_RELATION",
    ) -> List[Dict[str, Any]]:
        """
        Create multiple test edges.

        Args:
            conn: Database connection
            count: Number of edges to create
            relation: Relation type for all edges

        Returns:
            List of created edge data dicts
        """
        edges = []
        for _ in range(count):
            edge = self.create(conn=conn, relation=relation)
            edges.append(edge)
        return edges

    def create_with_relation(
        self,
        conn: connection,
        source_name: str,
        target_name: str,
        relation: str,
    ) -> Dict[str, Any]:
        """
        Create an edge with specific relation.

        Args:
            conn: Database connection
            source_name: Source node name
            target_name: Target node name
            relation: Edge relation type

        Returns:
            Created edge data dict
        """
        return self.create(conn=conn, source_name=source_name, target_name=target_name, relation=relation)

    def _save_to_database(
        self,
        conn: connection,
        source_name: str,
        target_name: str,
        relation: str,
        weight: float,
        properties: Dict[str, Any],
        memory_sector: str,
    ) -> str:
        """
        Save edge to database.

        Args:
            conn: Database connection
            source_name: Source node name
            target_name: Target node name
            relation: Edge relation type
            weight: Edge weight
            properties: Edge properties
            memory_sector: Memory sector

        Returns:
            Created edge ID (UUID string)
        """
        cursor = conn.cursor(cursor_factory=DictCursor)

        # Get or create source node
        cursor.execute("SELECT id FROM graph_nodes WHERE name = %s", (source_name,))
        source_result = cursor.fetchone()

        if source_result:
            source_id = source_result["id"]
        else:
            # Create source node
            cursor.execute(
                """
                INSERT INTO graph_nodes (label, name, properties, vector_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                ("TestLabel", source_name, {"created_by": "EdgeFactory"}, 999999),
            )
            source_id = cursor.fetchone()["id"]

        # Get or create target node
        cursor.execute("SELECT id FROM graph_nodes WHERE name = %s", (target_name,))
        target_result = cursor.fetchone()

        if target_result:
            target_id = target_result["id"]
        else:
            # Create target node
            cursor.execute(
                """
                INSERT INTO graph_nodes (label, name, properties, vector_id)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                ("TestLabel", target_name, {"created_by": "EdgeFactory"}, 999999),
            )
            target_id = cursor.fetchone()["id"]

        # Create edge
        cursor.execute(
            """
            INSERT INTO graph_edges (source_id, target_id, relation, weight, properties, memory_sector)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (source_id, target_id, relation, weight, properties, memory_sector),
        )

        edge_id = cursor.fetchone()["id"]
        conn.commit()

        return edge_id

    def cleanup(self, conn: Optional[connection] = None) -> None:
        """
        Clean up created edges.

        Args:
            conn: Database connection (if edges were saved to DB)
        """
        if not self.created_edges:
            return

        if conn is not None:
            cursor = conn.cursor(cursor_factory=DictCursor)

            # Delete edges
            cursor.execute(
                "DELETE FROM graph_edges WHERE id = ANY(%s)",
                (self.created_edges,),
            )

            conn.commit()

        self.created_edges.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()
