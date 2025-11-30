"""
Cognitive Memory Library API - Direct programmatic access to memory storage.

This package provides a Python API for cognitive memory operations,
enabling direct integration with Python applications without MCP protocol overhead.

Usage:
    from cognitive_memory import MemoryStore

    with MemoryStore() as store:
        results = store.search("query", top_k=5)

The library wraps the mcp_server implementation, ensuring:
- No code duplication
- Consistent behavior between MCP and library APIs
- Shared connection pooling

Available Classes:
    MemoryStore: Main entry point for all memory operations
    WorkingMemory: Focused interface for working memory
    EpisodeMemory: Focused interface for episode storage
    GraphStore: Focused interface for graph operations
    ConnectionManager: Database connection management

Result Types:
    SearchResult: Results from hybrid search
    InsightResult: Results from L2 insight storage
    WorkingMemoryResult: Results from working memory operations
    EpisodeResult: Results from episode storage

Exceptions:
    CognitiveMemoryError: Base exception for all errors
    ConnectionError: Database connection failures
    SearchError: Search operation failures
    StorageError: Storage operation failures
    ValidationError: Input validation failures
    EmbeddingError: Embedding generation failures

Example:
    >>> from cognitive_memory import MemoryStore
    >>> with MemoryStore() as store:
    ...     results = store.search("python programming")
    ...     for r in results:
    ...         print(f"{r.content[:50]}... (score: {r.score:.2f})")
"""

from __future__ import annotations

# Version - synchronized with pyproject.toml
__version__ = "1.0.0"

# Core classes
# Connection management
from cognitive_memory.connection import ConnectionManager

# Exceptions
from cognitive_memory.exceptions import (
    CognitiveMemoryError,
    ConnectionError,
    EmbeddingError,
    SearchError,
    StorageError,
    ValidationError,
)
from cognitive_memory.store import (
    EpisodeMemory,
    GraphStore,
    MemoryStore,
    WorkingMemory,
)

# Result types
from cognitive_memory.types import (
    EpisodeResult,
    GraphEdge,
    GraphNode,
    InsightResult,
    PathResult,
    SearchResult,
    WorkingMemoryResult,
)

__all__ = [
    # Version
    "__version__",
    # Core classes
    "MemoryStore",
    "WorkingMemory",
    "EpisodeMemory",
    "GraphStore",
    "ConnectionManager",
    # Result types
    "SearchResult",
    "InsightResult",
    "WorkingMemoryResult",
    "EpisodeResult",
    "GraphNode",
    "GraphEdge",
    "PathResult",
    # Exceptions
    "CognitiveMemoryError",
    "ConnectionError",
    "SearchError",
    "StorageError",
    "ValidationError",
    "EmbeddingError",
]
