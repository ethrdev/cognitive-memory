"""
Insight factory for creating test L2 insights.

Provides InsightFactory class for generating test insights with:
- Configurable content and memory strength
- Database integration
- Auto-cleanup
"""

import random
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extensions import connection
from psycopg2.extras import DictCursor


class InsightFactory:
    """
    Factory for creating test L2 insights.

    Example:
        factory = InsightFactory()
        insight = factory.create(content="Test insight", memory_strength=0.8)
        insight_id = insight["id"]
    """

    def __init__(self):
        """Initialize the factory."""
        self.created_insights: List[int] = []

    def create(
        self,
        conn: Optional[connection] = None,
        content: Optional[str] = None,
        memory_strength: float = 0.5,
        source_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Create a test L2 insight.

        Args:
            conn: Database connection (if provided, saves to DB)
            content: Insight content (auto-generated if None)
            memory_strength: Memory strength (0-1)
            source_ids: Source L0 IDs (auto-generated if None)

        Returns:
            Created insight data dict
        """
        if content is None:
            content = f"Test insight {uuid.uuid4().hex[:8]}"

        if source_ids is None:
            source_ids = [random.randint(1, 1000) for _ in range(random.randint(1, 5))]

        # Generate 1536-dimensional embedding
        embedding = [random.uniform(-1, 1) for _ in range(1536)]

        insight_data = {
            "id": random.randint(100000, 999999),
            "content": content,
            "embedding": embedding,
            "memory_strength": memory_strength,
            "source_ids": source_ids,
            "created_at": "2026-01-11T12:00:00Z",
        }

        # Save to database if connection provided
        if conn is not None:
            insight_data["id"] = self._save_to_database(
                conn, content, embedding, memory_strength
            )
            self.created_insights.append(insight_data["id"])

        return insight_data

    def create_batch(
        self,
        conn: Optional[connection] = None,
        count: int = 5,
        memory_strength: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Create multiple test insights.

        Args:
            conn: Database connection
            count: Number of insights to create
            memory_strength: Memory strength for all insights

        Returns:
            List of created insight data dicts
        """
        insights = []
        for _ in range(count):
            insight = self.create(conn=conn, memory_strength=memory_strength)
            insights.append(insight)
        return insights

    def create_with_strength(
        self,
        conn: connection,
        memory_strength: float,
    ) -> Dict[str, Any]:
        """
        Create an insight with specific memory strength.

        Args:
            conn: Database connection
            memory_strength: Memory strength (0-1)

        Returns:
            Created insight data dict
        """
        return self.create(conn=conn, memory_strength=memory_strength)

    def _save_to_database(
        self,
        conn: connection,
        content: str,
        embedding: List[float],
        memory_strength: float,
    ) -> int:
        """
        Save insight to database.

        Args:
            conn: Database connection
            content: Insight content
            embedding: 1536-dimensional embedding vector
            memory_strength: Memory strength (0-1)

        Returns:
            Created insight ID (integer)
        """
        cursor = conn.cursor(cursor_factory=DictCursor)

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

    def cleanup(self, conn: Optional[connection] = None) -> None:
        """
        Clean up created insights.

        Args:
            conn: Database connection (if insights were saved to DB)
        """
        if not self.created_insights:
            return

        if conn is not None:
            cursor = conn.cursor(cursor_factory=DictCursor)

            # Delete insights
            cursor.execute(
                "DELETE FROM l2_insights WHERE id = ANY(%s)",
                (self.created_insights,),
            )

            conn.commit()

        self.created_insights.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()
