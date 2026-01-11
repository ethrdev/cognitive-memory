"""
Test data generators for cognitive-memory tests.

Provides utilities for generating:
- Test nodes
- Test edges
- Test insights
- Test episodes
- Test users
"""

import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


def generate_test_node(
    label: Optional[str] = None,
    name: Optional[str] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a test node.

    Args:
        label: Node label (random if None)
        name: Node name (auto-generated if None)
        properties: Node properties (generated if None)

    Returns:
        Generated node data
    """
    if label is None:
        label = random.choice(["Agent", "Technology", "Concept", "Project"])

    if name is None:
        name = f"TestNode_{uuid.uuid4().hex[:8]}"

    if properties is None:
        properties = {
            "test": True,
            "created_by": "generator",
            "created_at": datetime.now().isoformat(),
            "tags": ["test", "generated"],
        }

    return {
        "id": str(uuid.uuid4()),
        "label": label,
        "name": name,
        "properties": properties,
        "vector_id": random.randint(100000, 999999),
        "created_at": datetime.now().isoformat(),
    }


def generate_test_edge(
    source_name: Optional[str] = None,
    target_name: Optional[str] = None,
    relation: Optional[str] = None,
    weight: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Generate a test edge.

    Args:
        source_name: Source node name (auto-generated if None)
        target_name: Target node name (auto-generated if None)
        relation: Edge relation (random if None)
        weight: Edge weight (0-1, random if None)

    Returns:
        Generated edge data
    """
    if source_name is None:
        source_name = f"Source_{uuid.uuid4().hex[:8]}"

    if target_name is None:
        target_name = f"Target_{uuid.uuid4().hex[:8]}"

    if relation is None:
        relation = random.choice(
            ["USES", "CREATED_BY", "RELATED_TO", "DEPENDS_ON", "SOLVES"]
        )

    if weight is None:
        weight = round(random.uniform(0.1, 1.0), 2)

    return {
        "id": str(uuid.uuid4()),
        "source_id": str(uuid.uuid4()),
        "target_id": str(uuid.uuid4()),
        "relation": relation,
        "weight": weight,
        "properties": {
            "test": True,
            "created_by": "generator",
            "context": f"Test context for {relation}",
        },
        "memory_sector": random.choice(
            ["semantic", "episodic", "emotional", "procedural", "reflective"]
        ),
        "created_at": datetime.now().isoformat(),
    }


def generate_test_insight(
    content: Optional[str] = None,
    memory_strength: Optional[float] = None,
    source_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Generate a test L2 insight.

    Args:
        content: Insight content (generated if None)
        memory_strength: Memory strength 0-1 (random if None)
        source_ids: Source L0 IDs (generated if None)

    Returns:
        Generated insight data
    """
    if content is None:
        content = f"Test insight content {uuid.uuid4().hex[:8]}"

    if memory_strength is None:
        memory_strength = round(random.uniform(0.1, 1.0), 2)

    if source_ids is None:
        source_ids = [random.randint(1, 1000) for _ in range(random.randint(1, 5))]

    return {
        "id": random.randint(100000, 999999),
        "content": content,
        "embedding": [random.uniform(-1, 1) for _ in range(1536)],
        "memory_strength": memory_strength,
        "source_ids": source_ids,
        "created_at": datetime.now().isoformat(),
    }


def generate_test_episode(
    query: Optional[str] = None,
    reward: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Generate a test episode.

    Args:
        query: Episode query (generated if None)
        reward: Episode reward -1 to 1 (random if None)

    Returns:
        Generated episode data
    """
    if query is None:
        query = f"What is the meaning of {random.choice(['life', 'test', 'data'])}?"

    if reward is None:
        reward = round(random.uniform(-1, 1), 2)

    return {
        "id": random.randint(100000, 999999),
        "query": query,
        "reward": reward,
        "reflection": f"Learned: {query} - Reward: {reward}",
        "created_at": datetime.now().isoformat(),
    }


def generate_test_user(
    email: Optional[str] = None,
    name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a test user.

    Args:
        email: User email (generated if None)
        name: User name (generated if None)

    Returns:
        Generated user data
    """
    if email is None:
        email = f"test.{uuid.uuid4().hex[:8]}@example.com"

    if name is None:
        name = f"Test User {uuid.uuid4().hex[:8]}"

    return {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": name,
        "created_at": datetime.now().isoformat(),
    }


def generate_test_memory_sector(
    sector: Optional[str] = None,
) -> str:
    """
    Generate a test memory sector.

    Args:
        sector: Specific sector (random if None)

    Returns:
        Memory sector name
    """
    if sector is None:
        sector = random.choice(
            ["semantic", "episodic", "emotional", "procedural", "reflective"]
        )

    return sector


def generate_test_vector_embedding(
    dimensions: int = 1536,
) -> List[float]:
    """
    Generate a test vector embedding.

    Args:
        dimensions: Vector dimensions (default 1536)

    Returns:
        Generated embedding vector
    """
    return [random.uniform(-1, 1) for _ in range(dimensions)]


def generate_test_timestamp(
    days_ago: Optional[int] = None,
) -> str:
    """
    Generate a test timestamp.

    Args:
        days_ago: Days ago from now (random 0-30 if None)

    Returns:
        ISO format timestamp
    """
    if days_ago is None:
        days_ago = random.randint(0, 30)

    timestamp = datetime.now() - timedelta(days=days_ago)
    return timestamp.isoformat()


def generate_random_string(
    length: int = 10,
    prefix: Optional[str] = None,
) -> str:
    """
    Generate a random string.

    Args:
        length: String length
        prefix: String prefix (optional)

    Returns:
        Random string
    """
    chars = string.ascii_letters + string.digits

    random_str = "".join(random.choice(chars) for _ in range(length))

    if prefix:
        return f"{prefix}_{random_str}"

    return random_str


def generate_test_properties(
    num_props: int = 3,
) -> Dict[str, Any]:
    """
    Generate test properties dict.

    Args:
        num_props: Number of properties to generate

    Returns:
        Generated properties dict
    """
    properties = {}

    for _ in range(num_props):
        key = generate_random_string(8)
        value = random.choice(
            [
                random.randint(1, 100),
                random.uniform(0, 1),
                generate_random_string(10),
                random.choice([True, False]),
                generate_test_timestamp(),
            ]
        )
        properties[key] = value

    return properties


def generate_test_dataset(
    num_nodes: int = 10,
    num_edges: int = 20,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Generate a complete test dataset.

    Args:
        num_nodes: Number of nodes to generate
        num_edges: Number of edges to generate

    Returns:
        Generated dataset with 'nodes' and 'edges'
    """
    nodes = [generate_test_node() for _ in range(num_nodes)]
    edges = [generate_test_edge() for _ in range(num_edges)]

    return {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "num_nodes": num_nodes,
            "num_edges": num_edges,
        },
    }
