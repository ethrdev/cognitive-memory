"""
Mock utilities for cognitive-memory tests.

Provides utilities for:
- Mocking database connections
- Mocking OpenAI clients
- Mocking Anthropic clients
- Creating realistic mock data
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

from psycopg2.extensions import connection


def mock_postgres_connection(
    fetchone_result: Optional[Dict[str, Any]] = None,
    fetchall_result: Optional[List[Dict[str, Any]]] = None,
    execute_side_effect: Optional[Exception] = None,
) -> MagicMock:
    """
    Create a mock PostgreSQL connection.

    Args:
        fetchone_result: Result for fetchone() calls
        fetchall_result: Result for fetchall() calls
        execute_side_effect: Exception to raise on execute()

    Returns:
        Mocked connection with configured behavior
    """
    mock_conn = MagicMock(spec=connection)
    mock_cursor = MagicMock()

    # Configure cursor behavior
    if fetchone_result is not None:
        mock_cursor.fetchone.return_value = fetchone_result

    if fetchall_result is not None:
        mock_cursor.fetchall.return_value = fetchall_result

    if execute_side_effect is not None:
        mock_cursor.execute.side_effect = execute_side_effect

    mock_conn.cursor.return_value = mock_cursor

    return mock_conn


def mock_openai_embedding(
    embedding: Optional[List[float]] = None,
) -> MagicMock:
    """
    Create a mock OpenAI embedding response.

    Args:
        embedding: 1536-dimensional embedding vector (auto-generated if None)

    Returns:
        Mocked OpenAI embeddings.create response
    """
    if embedding is None:
        embedding = [0.01 * i for i in range(1536)]

    mock_embedding = MagicMock()
    mock_embedding.embedding = embedding

    mock_response = MagicMock()
    mock_response.data = [mock_embedding]

    mock_client = MagicMock()
    mock_client.embeddings.create.return_value = mock_response

    return mock_client


def mock_anthropic_response(
    text: str = '{"score": 0.8, "reasoning": "Test evaluation"}',
) -> MagicMock:
    """
    Create a mock Anthropic messages response.

    Args:
        text: Response text content

    Returns:
        Mocked Anthropic messages.create response
    """
    mock_content = MagicMock()
    mock_content.text = text

    mock_response = MagicMock()
    mock_response.content = [mock_content]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    return mock_client


def mock_graph_node(
    node_id: Optional[str] = None,
    label: str = "TestLabel",
    name: str = "TestNode",
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create mock graph node data.

    Args:
        node_id: Node ID (UUID, auto-generated if None)
        label: Node label
        name: Node name
        properties: Node properties

    Returns:
        Mocked node data dict
    """
    import uuid

    if node_id is None:
        node_id = str(uuid.uuid4())

    if properties is None:
        properties = {"test": True, "created_by": "mock"}

    return {
        "id": node_id,
        "label": label,
        "name": name,
        "properties": properties,
        "vector_id": 999999,
        "created_at": "2026-01-11T12:00:00Z",
    }


def mock_graph_edge(
    edge_id: Optional[str] = None,
    source_id: Optional[str] = None,
    target_id: Optional[str] = None,
    relation: str = "TEST_RELATION",
    weight: float = 1.0,
) -> Dict[str, Any]:
    """
    Create mock graph edge data.

    Args:
        edge_id: Edge ID (UUID, auto-generated if None)
        source_id: Source node ID
        target_id: Target node ID
        relation: Edge relation
        weight: Edge weight (0-1)

    Returns:
        Mocked edge data dict
    """
    import uuid

    if edge_id is None:
        edge_id = str(uuid.uuid4())

    if source_id is None:
        source_id = str(uuid.uuid4())

    if target_id is None:
        target_id = str(uuid.uuid4())

    return {
        "id": edge_id,
        "source_id": source_id,
        "target_id": target_id,
        "relation": relation,
        "weight": weight,
        "properties": {"test": True, "created_by": "mock"},
        "memory_sector": "semantic",
        "created_at": "2026-01-11T12:00:00Z",
    }


def mock_l2_insight(
    insight_id: Optional[int] = None,
    content: Optional[str] = None,
    memory_strength: float = 0.5,
) -> Dict[str, Any]:
    """
    Create mock L2 insight data.

    Args:
        insight_id: Insight ID (auto-generated if None)
        content: Insight content
        memory_strength: Memory strength (0-1)

    Returns:
        Mocked insight data dict
    """
    import uuid

    if insight_id is None:
        insight_id = 999999

    if content is None:
        content = f"Test insight {uuid.uuid4().hex[:8]}"

    return {
        "id": insight_id,
        "content": content,
        "embedding": [0.01 * i for i in range(1536)],
        "memory_strength": memory_strength,
        "created_at": "2026-01-11T12:00:00Z",
    }


def mock_episode(
    episode_id: Optional[int] = None,
    query: Optional[str] = None,
    reward: float = 0.0,
) -> Dict[str, Any]:
    """
    Create mock episode data.

    Args:
        episode_id: Episode ID (auto-generated if None)
        query: Episode query
        reward: Episode reward (-1 to 1)

    Returns:
        Mocked episode data dict
    """
    import uuid

    if episode_id is None:
        episode_id = 999999

    if query is None:
        query = f"Test query {uuid.uuid4().hex[:8]}"

    return {
        "id": episode_id,
        "query": query,
        "reward": reward,
        "reflection": f"Test reflection for {query}",
        "created_at": "2026-01-11T12:00:00Z",
    }


def mock_pagination_response(
    items: List[Dict[str, Any]],
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Create mock paginated response.

    Args:
        items: List of items
        limit: Page limit
        offset: Page offset

    Returns:
        Mocked paginated response dict
    """
    return {
        "items": items,
        "total_count": len(items) + offset,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < len(items) + offset,
    }


def mock_error_response(
    error: str,
    status: str = "error",
) -> Dict[str, Any]:
    """
    Create mock error response.

    Args:
        error: Error message
        status: Error status

    Returns:
        Mocked error response dict
    """
    return {
        "error": error,
        "status": status,
    }


def mock_success_response(
    data: Any,
    status: str = "success",
) -> Dict[str, Any]:
    """
    Create mock success response.

    Args:
        data: Response data
        status: Success status

    Returns:
        Mocked success response dict
    """
    return {
        "data": data,
        "status": status,
    }
