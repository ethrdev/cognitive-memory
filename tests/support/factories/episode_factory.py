"""
Episode factory for creating test episodes.

Provides EpisodeFactory class for generating test episodes with:
- Configurable query and reward
- Database integration
- Auto-cleanup
"""

import random
import uuid
from typing import Any, Dict, List, Optional

from psycopg2.extensions import connection
from psycopg2.extras import DictCursor


class EpisodeFactory:
    """
    Factory for creating test episodes.

    Example:
        factory = EpisodeFactory()
        episode = factory.create(query="What is AI?", reward=0.8)
        episode_id = episode["id"]
    """

    def __init__(self):
        """Initialize the factory."""
        self.created_episodes: List[int] = []

    def create(
        self,
        conn: Optional[connection] = None,
        query: Optional[str] = None,
        reward: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Create a test episode.

        Args:
            conn: Database connection (if provided, saves to DB)
            query: Episode query (auto-generated if None)
            reward: Episode reward -1 to 1 (random if None)

        Returns:
            Created episode data dict
        """
        if query is None:
            query = f"What is {random.choice(['AI', 'machine learning', 'testing', 'data'])}?"

        if reward is None:
            reward = round(random.uniform(-1, 1), 2)

        episode_data = {
            "id": random.randint(100000, 999999),
            "query": query,
            "reward": reward,
            "reflection": f"Learned: {query} - Reward: {reward}",
            "created_at": "2026-01-11T12:00:00Z",
        }

        # Save to database if connection provided
        if conn is not None:
            episode_data["id"] = self._save_to_database(conn, query, reward)
            self.created_episodes.append(episode_data["id"])

        return episode_data

    def create_batch(
        self,
        conn: Optional[connection] = None,
        count: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Create multiple test episodes.

        Args:
            conn: Database connection
            count: Number of episodes to create

        Returns:
            List of created episode data dicts
        """
        episodes = []
        for _ in range(count):
            episode = self.create(conn=conn)
            episodes.append(episode)
        return episodes

    def create_with_reward(
        self,
        conn: connection,
        reward: float,
    ) -> Dict[str, Any]:
        """
        Create an episode with specific reward.

        Args:
            conn: Database connection
            reward: Episode reward (-1 to 1)

        Returns:
            Created episode data dict
        """
        return self.create(conn=conn, reward=reward)

    def _save_to_database(
        self,
        conn: connection,
        query: str,
        reward: float,
    ) -> int:
        """
        Save episode to database.

        Args:
            conn: Database connection
            query: Episode query
            reward: Episode reward

        Returns:
            Created episode ID (integer)
        """
        cursor = conn.cursor(cursor_factory=DictCursor)

        reflection = f"Learned: {query} - Reward: {reward}"

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

    def cleanup(self, conn: Optional[connection] = None) -> None:
        """
        Clean up created episodes.

        Args:
            conn: Database connection (if episodes were saved to DB)
        """
        if not self.created_episodes:
            return

        if conn is not None:
            cursor = conn.cursor(cursor_factory=DictCursor)

            # Delete episodes
            cursor.execute(
                "DELETE FROM episodes WHERE id = ANY(%s)",
                (self.created_episodes,),
            )

            conn.commit()

        self.created_episodes.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()
