"""
Data Factories for Cognitive Memory Tests

Factory functions for generating test data with overrides support.
Provides consistent, maintainable test data across the test suite.

Usage:
    from tests.factories.content_factory import create_content, create_embedding

    # Use defaults
    content = create_content()

    # Override specific values
    high_density_content = create_content(density="high")
"""

from __future__ import annotations


def create_content(density: str = "medium") -> str:
    """
    Factory for creating test content with specified semantic density.

    Args:
        density: Semantic density level - "high", "medium", or "low"

    Returns:
        Test content string with specified semantic characteristics

    Examples:
        >>> create_content(density="high")
        'Machine learning algorithms analyze complex mathematical patterns efficiently'
        >>> create_content(density="low")
        'this is a test that has many words but not much meaning at all'
    """
    content_templates = {
        "high": "Machine learning algorithms analyze complex mathematical patterns efficiently",
        "low": "this is a test that has many words but not much meaning at all",
        "medium": "test with some meaningful words and some stop words mixed together",
        "german": "der machine learning algorithm",
        "single": "algorithm",
        "empty": "",
        "whitespace": "   ",
    }
    return content_templates.get(density, content_templates["medium"])


def create_embedding(dimension: int = 1536, value: float = 0.1) -> list[float]:
    """
    Factory for creating test embedding vectors.

    Args:
        dimension: Embedding vector dimensions (default: 1536 for OpenAI)
        value: Fill value for all dimensions (default: 0.1)

    Returns:
        List of floats representing an embedding vector

    Examples:
        >>> create_embedding()
        [0.1, 0.1, 0.1, ...]  # 1536 dimensions
        >>> create_embedding(dimension=512, value=0.5)
        [0.5, 0.5, 0.5, ...]  # 512 dimensions
    """
    return [value] * dimension


def create_l2_insight_data(
    content: str | None = None,
    source_ids: list[int] | None = None,
    memory_strength: float = 0.5,
) -> dict:
    """
    Factory for creating L2 insight test data.

    Args:
        content: Insight content (uses default if None)
        source_ids: List of source L0 memory IDs (uses default if None)
        memory_strength: I/O memory strength (0.0-1.0)

    Returns:
        Dictionary with L2 insight data

    Examples:
        >>> create_l2_insight_data()
        {'content': 'test_discussion about...', 'source_ids': [1, 2, 3], 'memory_strength': 0.5}
        >>> create_l2_insight_data(content="Custom content", source_ids=[5, 6])
        {'content': 'Custom content', 'source_ids': [5, 6], 'memory_strength': 0.5}
    """
    if content is None:
        content = "test_discussion about artificial intelligence and machine learning algorithms"
    if source_ids is None:
        source_ids = [1, 2, 3]
    return {
        "content": content,
        "source_ids": source_ids,
        "memory_strength": memory_strength,
    }


def create_graph_node(
    node_id: str | None = None,
    name: str = "TestNode",
    label: str = "Entity",
    properties: dict | None = None,
) -> dict:
    """
    Factory for creating graph node test data.

    Args:
        node_id: Unique node identifier (generated if None)
        name: Node name
        label: Node label/type
        properties: Additional node properties

    Returns:
        Dictionary representing a graph node

    Examples:
        >>> create_graph_node()
        {'id': 'node-test-id', 'name': 'TestNode', 'label': 'Entity', 'properties': {}}
        >>> create_graph_node(name="Python", label="Technology")
        {'id': 'node-python-id', 'name': 'Python', 'label': 'Technology', 'properties': {}}
    """
    if node_id is None:
        node_id = f"node-{name.lower().replace(' ', '-')}-id"
    if properties is None:
        properties = {}
    return {
        "id": node_id,
        "name": name,
        "label": label,
        "properties": properties,
        "vector_id": None,
        "created_at": "2025-11-30T10:00:00Z",
    }


def create_graph_neighbor(
    node_id: str | None = None,
    name: str = "NeighborNode",
    relation: str = "RELATED_TO",
    weight: float = 0.9,
    distance: int = 1,
    edge_direction: str = "outgoing",
) -> dict:
    """
    Factory for creating graph neighbor test data.

    Args:
        node_id: Neighbor node ID
        name: Neighbor node name
        relation: Relationship type
        weight: Edge weight (0.0-1.0)
        distance: Hop distance from start node
        edge_direction: "outgoing", "incoming", or "both"

    Returns:
        Dictionary representing a graph neighbor

    Examples:
        >>> create_graph_neighbor()
        {'node_id': 'neighbor-node-id', 'name': 'NeighborNode', 'relation': 'RELATED_TO', ...}
        >>> create_graph_neighbor(name="Python", relation="USES", distance=1)
        {'node_id': 'neighbor-python-id', 'name': 'Python', 'relation': 'USES', ...}
    """
    if node_id is None:
        node_id = f"neighbor-{name.lower().replace(' ', '-')}-id"
    return {
        "node_id": node_id,
        "label": "Entity",
        "name": name,
        "properties": {},
        "relation": relation,
        "weight": weight,
        "distance": distance,
        "edge_direction": edge_direction,
    }


def create_episode_data(
    query: str | None = None,
    reward: float = 0.0,
    reflection: str | None = None,
) -> dict:
    """
    Factory for creating episode memory test data.

    Args:
        query: User query that triggered the episode
        reward: Reward score (-1.0 to +1.0)
        reflection: Lesson learned (verbalized reflection)

    Returns:
        Dictionary with episode data

    Examples:
        >>> create_episode_data()
        {'query': 'test query', 'reward': 0.0, 'reflection': 'test reflection'}
        >>> create_episode_data(reward=0.8, reflection="Great success")
        {'query': 'test query', 'reward': 0.8, 'reflection': 'Great success'}
    """
    if query is None:
        query = "test query"
    if reflection is None:
        reflection = "test reflection"
    return {
        "query": query,
        "reward": reward,
        "reflection": reflection,
    }
