"""
Type definitions and result classes for cognitive_memory library.

These dataclasses represent the return types from various memory operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SearchResult:
    """
    Result from a hybrid search operation.

    Attributes:
        id: Unique identifier of the result
        content: The retrieved content text
        score: Combined RRF score (0.0-1.0)
        source: Source type ('l2_insight', 'working_memory', 'episode', 'graph')
        metadata: Additional metadata from the source
        semantic_score: Score from semantic search component
        keyword_score: Score from keyword search component
    """

    id: int
    content: str
    score: float
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    semantic_score: float | None = None
    keyword_score: float | None = None


@dataclass
class InsightResult:
    """
    Result from L2 insight storage operation.

    Attributes:
        id: Unique identifier of the stored insight
        embedding_status: Status of embedding generation ("success", "failed", "retried")
        fidelity_score: Semantic fidelity score (0.0-1.0)
        created_at: Timestamp of creation
    """

    id: int
    embedding_status: str
    fidelity_score: float
    created_at: datetime


@dataclass
class WorkingMemoryResult:
    """
    Result from working memory operations.

    Attributes:
        added_id: ID of the newly added item (if add operation)
        evicted_id: ID of the evicted item (if capacity exceeded)
        archived_id: ID of the archived item (if applicable)
        current_count: Current number of items in working memory
    """

    added_id: int | None = None
    evicted_id: int | None = None
    archived_id: int | None = None
    current_count: int = 0


@dataclass
class WorkingMemoryItem:
    """
    Represents an item in working memory.

    Attributes:
        id: Unique identifier for the working memory item
        content: The content text stored in working memory
        importance: Importance score (0.0-1.0), items >0.8 are considered critical
        last_accessed: Timestamp of last access (for LRU eviction)
        created_at: Timestamp of creation
    """

    id: int
    content: str
    importance: float
    last_accessed: datetime
    created_at: datetime


@dataclass
class EpisodeResult:
    """
    Result from episode memory storage operation.

    Attributes:
        id: Unique identifier of the stored episode
        query: The user query that triggered the episode
        reward: Reward score from evaluation (-1.0 to +1.0)
        reflection: Verbalized lesson learned
        created_at: Timestamp of creation
    """

    id: int
    query: str
    reward: float
    reflection: str
    created_at: datetime | None = None


@dataclass
class GraphNode:
    """
    Represents a node in the knowledge graph.

    Attributes:
        id: Unique node identifier
        name: Node name (unique within label)
        label: Node type/category
        properties: Flexible metadata
        vector_id: Optional link to L2 insight embedding
    """

    id: int
    name: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    vector_id: int | None = None


@dataclass
class GraphEdge:
    """
    Represents an edge in the knowledge graph.

    Attributes:
        id: Unique edge identifier
        source_id: Source node ID
        target_id: Target node ID
        relation: Relationship type
        weight: Edge weight (0.0-1.0)
        properties: Flexible metadata
    """

    id: int
    source_id: int
    target_id: int
    relation: str
    weight: float = 1.0
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class PathResult:
    """
    Result from graph path finding operation.

    Attributes:
        path: List of node names in the path
        length: Number of hops in the path
        found: Whether a path was found
        nodes: Detailed node information
        edges: Detailed edge information
    """

    path: list[str]
    length: int
    found: bool
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
