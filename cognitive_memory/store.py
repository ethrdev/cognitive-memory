"""
MemoryStore - Main entry point for cognitive memory operations.

Provides programmatic access to cognitive memory storage and retrieval.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Any

import psycopg2
from pgvector.psycopg2 import register_vector
from openai import OpenAI, APIConnectionError, RateLimitError

from cognitive_memory.connection import ConnectionManager
from cognitive_memory.exceptions import ConnectionError, ValidationError, SearchError, StorageError, EmbeddingError

# Import graph database functions for Story 5.7 implementation
from mcp_server.db.graph import (
    add_node as db_add_node,
    add_edge as db_add_edge,
    query_neighbors as db_query_neighbors,
    find_path as db_find_path,
    get_node_by_name,
    get_or_create_node,
)
from cognitive_memory.types import SearchResult
from mcp_server.tools import (
    semantic_search,
    keyword_search,
    rrf_fusion,
    generate_query_embedding,
    calculate_fidelity,
    get_embedding_with_retry,
)
from mcp_server.db.connection import get_connection

if TYPE_CHECKING:
    from cognitive_memory.types import (
        EpisodeResult,
        InsightResult,
        WorkingMemoryItem,
        WorkingMemoryResult,
    )

_logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Main entry point for cognitive memory storage operations.

    Provides programmatic access to:
    - Hybrid Search (semantic + keyword)
    - L2 Insight Storage
    - Working Memory Management
    - Episode Memory Storage
    - Graph Operations

    Example:
        with MemoryStore() as store:
            results = store.search("query", top_k=5)

        # Or manual lifecycle management:
        store = MemoryStore()
        store.connect()
        try:
            results = store.search("query")
        finally:
            store.close()

    Attributes:
        is_connected: Whether the store is connected to the database
    """

    def __init__(
        self,
        connection_string: str | None = None,
        auto_initialize: bool = True,
    ) -> None:
        """
        Initialize MemoryStore.

        Args:
            connection_string: PostgreSQL connection string.
                             If None, reads from DATABASE_URL env var.
            auto_initialize: If True, automatically initialize connection pool
                           when using context manager.
        """
        self._connection_manager = ConnectionManager(connection_string)
        self._auto_initialize = auto_initialize
        self._is_connected = False
        # Lazy-initialized sub-objects
        self._working: WorkingMemory | None = None
        self._episode: EpisodeMemory | None = None
        self._graph: GraphStore | None = None

    @classmethod
    def from_env(cls) -> MemoryStore:
        """
        Create MemoryStore from DATABASE_URL environment variable.

        This factory method reads the PostgreSQL connection string from
        the DATABASE_URL environment variable.

        Returns:
            MemoryStore instance configured with DATABASE_URL

        Raises:
            ConnectionError: If DATABASE_URL is not set or empty

        Example:
            # Ensure DATABASE_URL is set in environment
            store = MemoryStore.from_env()
            with store:
                results = store.search("query")
        """
        connection_string = os.environ.get("DATABASE_URL")
        if not connection_string:
            raise ConnectionError(
                "DATABASE_URL environment variable is not set. "
                "Set it to your PostgreSQL connection string."
            )
        return cls(connection_string=connection_string)

    @property
    def is_connected(self) -> bool:
        """Check if store is connected to database."""
        return self._is_connected and self._connection_manager.is_initialized

    def connect(
        self,
        min_connections: int = 1,
        max_connections: int = 10,
        connection_timeout: int = 5,
    ) -> None:
        """
        Connect to the database.

        Args:
            min_connections: Minimum pool connections
            max_connections: Maximum pool connections
            connection_timeout: Connection timeout in seconds

        Raises:
            ConnectionError: If connection fails
        """
        self._connection_manager.initialize(
            min_connections=min_connections,
            max_connections=max_connections,
            connection_timeout=connection_timeout,
        )
        self._is_connected = True
        _logger.info("MemoryStore connected")

    def close(self) -> None:
        """Close the database connection."""
        self._connection_manager.close()
        self._is_connected = False
        _logger.info("MemoryStore disconnected")

    def __enter__(self) -> MemoryStore:
        """Enter context manager."""
        if self._auto_initialize:
            self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager."""
        self.close()

    # =========================================================================
    # Sub-Object Accessor Properties (Story 5.2)
    # =========================================================================

    @property
    def working(self) -> WorkingMemory:
        """
        Get WorkingMemory sub-object (lazy-initialized).

        The WorkingMemory instance shares the connection pool with
        this MemoryStore instance.

        Returns:
            WorkingMemory instance for working memory operations

        Example:
            with MemoryStore() as store:
                store.working.add("Important context", importance=0.8)
        """
        if self._working is None:
            self._working = WorkingMemory.__new__(WorkingMemory)
            self._working._connection_manager = self._connection_manager
            self._working._is_connected = self._is_connected
        return self._working

    @property
    def episode(self) -> EpisodeMemory:
        """
        Get EpisodeMemory sub-object (lazy-initialized).

        The EpisodeMemory instance shares the connection pool with
        this MemoryStore instance.

        Returns:
            EpisodeMemory instance for episode memory operations

        Example:
            with MemoryStore() as store:
                store.episode.store("query", reward=0.9, reflection="Lesson")
        """
        if self._episode is None:
            self._episode = EpisodeMemory.__new__(EpisodeMemory)
            self._episode._connection_manager = self._connection_manager
            self._episode._is_connected = self._is_connected
        return self._episode

    @property
    def graph(self) -> GraphStore:
        """
        Get GraphStore sub-object (lazy-initialized).

        The GraphStore instance shares the connection pool with
        this MemoryStore instance.

        Returns:
            GraphStore instance for knowledge graph operations

        Example:
            with MemoryStore() as store:
                store.graph.add_node("Python", "Technology")
        """
        if self._graph is None:
            self._graph = GraphStore.__new__(GraphStore)
            self._graph._connection_manager = self._connection_manager
            self._graph._is_connected = self._is_connected
        return self._graph

    # =========================================================================
    # Search Operations (Story 5.3)
    # =========================================================================

    def search(
        self,
        query: str,
        top_k: int = 5,
        weights: dict[str, float] | None = None,
    ) -> list[SearchResult]:
        """
        Perform hybrid search across memory stores.

        Combines semantic search (embeddings) with keyword search using RRF fusion.

        Args:
            query: Search query text
            top_k: Maximum number of results to return
            weights: Optional weights for fusion (semantic, keyword)
                   Defaults to {"semantic": 0.7, "keyword": 0.3}

        Returns:
            List of SearchResult objects sorted by relevance

        Raises:
            ValidationError: If input validation fails
            ConnectionError: If not connected
            SearchError: If search operation fails
        """
        # Input validation
        if not query or not query.strip():
            raise ValidationError("Query must be a non-empty string")
        if not isinstance(top_k, int) or top_k <= 0 or top_k > 100:
            raise ValidationError("top_k must be an integer between 1 and 100")

        # Check connection
        if not self.is_connected:
            raise ConnectionError("MemoryStore is not connected")

        # Set default weights
        weights = weights or {"semantic": 0.7, "keyword": 0.3}

        # Validate weights structure
        if not isinstance(weights, dict):
            raise ValidationError("weights must be a dictionary")
        if "semantic" not in weights or "keyword" not in weights:
            raise ValidationError("weights must contain 'semantic' and 'keyword' keys")
        if not all(isinstance(w, (int, float)) and w >= 0 for w in weights.values()):
            raise ValidationError("weights must contain non-negative numbers")

        try:
            # Generate embedding for the query
            query_embedding = generate_query_embedding(query.strip())

            # Execute search using async-to-sync conversion
            with self._connection_manager.get_connection() as conn:
                # Run async functions using asyncio.run
                semantic_results = asyncio.run(
                    semantic_search(query_embedding, top_k, conn)
                )
                keyword_results = asyncio.run(
                    keyword_search(query.strip(), top_k, conn)
                )

                # Fuse results using RRF
                fused_results = rrf_fusion(semantic_results, keyword_results, weights)

                # Convert to SearchResult objects
                search_results = []
                for result in fused_results[:top_k]:
                    search_result = SearchResult(
                        id=result["id"],
                        content=result["content"],
                        score=float(result["score"]),
                        source="l2_insight",
                        metadata=result.get("metadata", {}),
                        semantic_score=result.get("distance", None),
                        keyword_score=result.get("rank", None),
                    )
                    search_results.append(search_result)

                return search_results

        except Exception as e:
            raise SearchError(f"Search operation failed: {e}") from e

    # =========================================================================
    # L2 Insight Storage (Story 5.4)
    # =========================================================================

    def store_insight(
        self,
        content: str,
        source_ids: list[int],
        metadata: dict[str, Any] | None = None,
    ) -> InsightResult:
        """
        Store a compressed insight to L2 memory.

        Generates embedding and stores the insight with semantic indexing.

        Args:
            content: Compressed insight content
            source_ids: IDs of L0 raw memories that were compressed
            metadata: Optional metadata dictionary

        Returns:
            InsightResult with storage details

        Raises:
            ValidationError: If content validation fails
            StorageError: If storage operation fails
            EmbeddingError: If embedding generation fails
            ConnectionError: If not connected to database
        """
        logger = logging.getLogger(__name__)

        # Input validation
        if not content or not content.strip():
            raise ValidationError("Content cannot be empty or whitespace-only")

        if not isinstance(source_ids, list):
            raise ValidationError("source_ids must be a list of integers")

        # Validate all source_ids are integers
        try:
            source_ids = [int(id) for id in source_ids]
        except (ValueError, TypeError) as e:
            raise ValidationError(f"All source_ids must be integers: {e}")

        # Check connection
        if not self.is_connected:
            raise ConnectionError("MemoryStore is not connected")

        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-your-openai-api-key-here":
            raise EmbeddingError("OpenAI API key not configured")

        client = OpenAI(api_key=api_key)

        try:
            # Calculate semantic fidelity
            fidelity_score = calculate_fidelity(content)

            # Prepare metadata for storage
            storage_metadata: dict[str, Any] = {
                "fidelity_score": fidelity_score,
            }

            if metadata:
                storage_metadata.update(metadata)

            logger.info(f"Computing embedding for content (fidelity: {fidelity_score:.2f})")

            # Get embedding with retry logic (sync wrapper)
            embedding_status = "success"
            try:
                embedding = asyncio.run(get_embedding_with_retry(client, content))
            except RuntimeError as e:
                if "rate limiting" in str(e).lower():
                    embedding_status = "retried"
                    # Retry once more for rate limiting
                    try:
                        embedding = asyncio.run(get_embedding_with_retry(client, content))
                    except RuntimeError:
                        raise EmbeddingError(f"Failed to generate embedding after retries: {e}")
                else:
                    raise EmbeddingError(f"Failed to generate embedding: {e}")

            # Store in database
            with get_connection() as conn:
                # Register vector type for pgvector
                register_vector(conn)

                cursor = conn.cursor()

                # Insert insight with embedding and metadata
                cursor.execute(
                    """
                    INSERT INTO l2_insights (content, embedding, source_ids, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, created_at;
                    """,
                    (content, embedding, source_ids, json.dumps(storage_metadata)),
                )

                result = cursor.fetchone()
                conn.commit()

                insight_id = int(result["id"])
                created_at = result["created_at"]
                logger.info(f"Successfully stored L2 insight {insight_id} with {len(embedding)}-dimensional embedding")

                # Import InsightResult to avoid circular imports
                from cognitive_memory.types import InsightResult

                return InsightResult(
                    id=insight_id,
                    embedding_status=embedding_status,
                    fidelity_score=fidelity_score,
                    created_at=created_at
                )

        except psycopg2.Error as e:
            logger.error(f"Database error storing L2 insight: {e}")
            raise StorageError(f"Database operation failed: {e}")

    # =========================================================================
    # Working Memory (Story 5.5)
    # =========================================================================

    def update_working_memory(
        self,
        content: str,
        importance: float = 0.5,
    ) -> WorkingMemoryResult:
        """
        Add item to working memory with automatic eviction.

        Implements a bounded working memory with LRU-style eviction
        when capacity is exceeded.

        Args:
            content: Content to store in working memory
            importance: Importance score (0.0-1.0)

        Returns:
            WorkingMemoryResult with add/evict details

        Raises:
            StorageError: If storage operation fails
            ValidationError: If importance is out of range

        Note:
            Full implementation in Story 5.5
        """
        raise NotImplementedError(
            "Working memory functionality implemented in Story 5.5"
        )

    # =========================================================================
    # Episode Memory (Story 5.6)
    # =========================================================================

    def store_episode(
        self,
        query: str,
        reward: float,
        reflection: str,
    ) -> EpisodeResult:
        """
        Store an episode for verbal reinforcement learning.

        Episodes capture query-reward-reflection triplets for learning
        from experience.

        Args:
            query: User query that triggered the episode
            reward: Reward score (-1.0 to +1.0)
            reflection: Verbalized lesson learned

        Returns:
            EpisodeResult with storage details

        Raises:
            StorageError: If storage operation fails
            ValidationError: If reward is out of range

        Note:
            Full implementation in Story 5.6
        """
        raise NotImplementedError(
            "Episode memory functionality implemented in Story 5.6"
        )

    # =========================================================================
    # Raw Memory Storage
    # =========================================================================

    def store_raw_dialogue(
        self,
        session_id: str,
        speaker: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Store raw dialogue to L0 memory.

        Args:
            session_id: Unique session identifier
            speaker: Speaker identifier (user, assistant, etc.)
            content: Dialogue content
            metadata: Optional additional metadata

        Returns:
            ID of the stored dialogue entry

        Raises:
            StorageError: If storage operation fails

        Note:
            Full implementation in Story 5.4
        """
        raise NotImplementedError(
            "Raw dialogue storage functionality implemented in Story 5.4"
        )


class WorkingMemory:
    """
    Dedicated interface for working memory operations.

    Provides a focused API for working memory management without
    the overhead of full MemoryStore initialization.

    Example:
        with WorkingMemory() as wm:
            result = wm.add("Important context", importance=0.8)

    Note:
        Full implementation in Story 5.5
    """

    def __init__(self, connection_string: str | None = None) -> None:
        """Initialize WorkingMemory interface."""
        self._connection_manager = ConnectionManager(connection_string)
        self._is_connected = False

    def __enter__(self) -> WorkingMemory:
        """Enter context manager."""
        self._connection_manager.initialize()
        self._is_connected = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager."""
        self._connection_manager.close()
        self._is_connected = False

    def add(self, content: str, importance: float = 0.5) -> WorkingMemoryResult:
        """
        Add item to working memory with LRU eviction and stale memory archiving.

        Args:
            content: Content text to store in working memory
            importance: Importance score (0.0-1.0), items >0.8 are critical

        Returns:
            WorkingMemoryResult with operation details

        Raises:
            ValidationError: If content is empty or importance is out of range
            ConnectionError: If not connected to database
        """
        # Input validation
        if not content or not content.strip():
            raise ValidationError("Content must be a non-empty string")

        if not isinstance(importance, (int, float)):
            raise ValidationError("Importance must be a number")

        importance = float(importance)

        if importance < 0.0 or importance > 1.0:
            raise ValidationError(f"Importance must be between 0.0 and 1.0, got {importance}")

        # Check connection
        if not self._is_connected:
            raise ConnectionError("WorkingMemory is not connected")

        # Use the shared connection manager
        with self._connection_manager.get_connection() as conn:
            try:
                cursor = conn.cursor()

                # 1. Add the new item
                cursor.execute(
                    """
                    INSERT INTO working_memory (content, importance, last_accessed, created_at)
                    VALUES (%s, %s, NOW(), NOW())
                    RETURNING id;
                    """,
                    (content.strip(), importance),
                )
                result = cursor.fetchone()
                if not result:
                    raise RuntimeError("INSERT into working_memory did not return ID")
                added_id = int(result["id"])

                # 2. Check capacity and evict if needed
                cursor.execute("SELECT COUNT(*) as count FROM working_memory;")
                count_result = cursor.fetchone()
                count = int(count_result["count"])

                evicted_id = None
                archived_id = None

                if count > 10:
                    # Find oldest non-critical item (importance <= 0.8)
                    cursor.execute(
                        """
                        SELECT id, importance
                        FROM working_memory
                        WHERE importance <= 0.8
                        ORDER BY last_accessed ASC
                        LIMIT 1;
                        """
                    )
                    lru_result = cursor.fetchone()

                    if lru_result:
                        evicted_id = int(lru_result["id"])
                        item_importance = float(lru_result["importance"])

                        # Archive critical items (importance > 0.8) to stale memory
                        if item_importance > 0.8:
                            cursor.execute(
                                """
                                INSERT INTO stale_memory (content, importance, archive_reason, created_at)
                                SELECT content, importance, %s, created_at
                                FROM working_memory
                                WHERE id = %s
                                RETURNING id;
                                """,
                                ("LRU_EVICTION", evicted_id),
                            )
                            archive_result = cursor.fetchone()
                            if archive_result:
                                archived_id = int(archive_result["id"])

                        # Delete the evicted item
                        cursor.execute(
                            "DELETE FROM working_memory WHERE id = %s;",
                            (evicted_id,)
                        )
                    else:
                        # All items are critical, force evict the oldest one
                        cursor.execute(
                            """
                            SELECT id, importance
                            FROM working_memory
                            ORDER BY last_accessed ASC
                            LIMIT 1;
                            """
                        )
                        oldest_result = cursor.fetchone()
                        if oldest_result:
                            evicted_id = int(oldest_result["id"])
                            item_importance = float(oldest_result["importance"])

                            # Always archive critical items
                            if item_importance > 0.8:
                                cursor.execute(
                                    """
                                    INSERT INTO stale_memory (content, importance, archive_reason, created_at)
                                    SELECT content, importance, %s, created_at
                                    FROM working_memory
                                    WHERE id = %s
                                    RETURNING id;
                                    """,
                                    ("LRU_EVICTION_CRITICAL", evicted_id),
                                )
                                archive_result = cursor.fetchone()
                                if archive_result:
                                    archived_id = int(archive_result["id"])

                            # Delete the oldest item
                            cursor.execute(
                                "DELETE FROM working_memory WHERE id = %s;",
                                (evicted_id,)
                            )

                # Get final count
                cursor.execute("SELECT COUNT(*) as count FROM working_memory;")
                final_count_result = cursor.fetchone()
                current_count = int(final_count_result["count"])

                conn.commit()

                _logger.info(
                    f"Added item to working memory: added_id={added_id}, "
                    f"evicted_id={evicted_id}, archived_id={archived_id}, "
                    f"current_count={current_count}"
                )

                from cognitive_memory.types import WorkingMemoryResult
                return WorkingMemoryResult(
                    added_id=added_id,
                    evicted_id=evicted_id,
                    archived_id=archived_id,
                    current_count=current_count,
                )

            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Failed to add item to working memory: {e}") from e

    def list(self) -> list[WorkingMemoryItem]:
        """
        List all working memory items sorted by last_accessed (newest first).

        Returns:
            List of WorkingMemoryItem objects sorted by last_accessed DESC

        Raises:
            ConnectionError: If not connected to database
        """
        # Check connection
        if not self._is_connected:
            raise ConnectionError("WorkingMemory is not connected")

        # Use the shared connection manager
        with self._connection_manager.get_connection() as conn:
            try:
                cursor = conn.cursor()

                # Get all items sorted by last_accessed DESC (newest first)
                cursor.execute(
                    """
                    SELECT id, content, importance, last_accessed, created_at
                    FROM working_memory
                    ORDER BY last_accessed DESC;
                    """
                )

                results = cursor.fetchall()
                items = []

                for row in results:
                    from cognitive_memory.types import WorkingMemoryItem
                    item = WorkingMemoryItem(
                        id=int(row["id"]),
                        content=str(row["content"]),
                        importance=float(row["importance"]),
                        last_accessed=row["last_accessed"],
                        created_at=row["created_at"],
                    )
                    items.append(item)

                return items

            except Exception as e:
                raise RuntimeError(f"Failed to list working memory items: {e}") from e

    def clear(self) -> int:
        """Clear all working memory items."""
        raise NotImplementedError("Implemented in Story 5.5")


class EpisodeMemory:
    """
    Dedicated interface for episode memory operations.

    Provides a focused API for episode storage and retrieval
    for verbal reinforcement learning.

    Example:
        with EpisodeMemory() as em:
            result = em.store("query", reward=0.8, reflection="Lesson learned")

    Note:
        Full implementation in Story 5.6
    """

    def __init__(self, connection_string: str | None = None) -> None:
        """Initialize EpisodeMemory interface."""
        self._connection_manager = ConnectionManager(connection_string)
        self._is_connected = False

    def __enter__(self) -> EpisodeMemory:
        """Enter context manager."""
        self._connection_manager.initialize()
        self._is_connected = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager."""
        self._connection_manager.close()
        self._is_connected = False

    def store(self, query: str, reward: float, reflection: str) -> EpisodeResult:
        """
        Store an episode for verbal reinforcement learning.

        Args:
            query: User query that triggered the episode
            reward: Reward score (-1.0 to +1.0)
            reflection: Verbalized lesson learned

        Returns:
            EpisodeResult with storage details

        Raises:
            ValidationError: If inputs are invalid
            StorageError: If storage operation fails
            EmbeddingError: If embedding generation fails
        """
        from cognitive_memory.types import EpisodeResult
        from mcp_server.tools import add_episode

        logger = logging.getLogger(__name__)

        # Input validation (synchronous, before any API calls)
        if not query or not isinstance(query, str):
            raise ValidationError("query must be a non-empty string")
        if not reflection or not isinstance(reflection, str):
            raise ValidationError("reflection must be a non-empty string")
        if not isinstance(reward, (int, float)):
            raise ValidationError("reward must be a number")
        if reward < -1.0 or reward > 1.0:
            raise ValidationError(f"reward {reward} is outside valid range [-1.0, 1.0]")

        logger.info(f"Storing episode with query: {query[:100]}...")

        # Get connection from pool
        try:
            with self._connection_manager.get_connection() as conn:
                # Call MCP server function (async → sync wrapper)
                try:
                    result = asyncio.run(add_episode(query, reward, reflection, conn))

                    if "error" in result:
                        raise StorageError(f"Episode storage failed: {result['error']}")

                    # Convert to EpisodeResult dataclass
                    from datetime import datetime
                    return EpisodeResult(
                        id=result["id"],
                        query=query,
                        reward=reward,
                        reflection=reflection,
                        created_at=datetime.fromisoformat(result["created_at"]),
                    )

                except RuntimeError as e:
                    if "embedding" in str(e).lower():
                        raise EmbeddingError(f"Embedding generation failed: {e}") from e
                    raise StorageError(f"Episode storage failed: {e}") from e

        except Exception as e:
            if isinstance(e, (ValidationError, StorageError, EmbeddingError)):
                raise
            raise StorageError(f"Database connection failed: {e}") from e

    def search(
        self,
        query: str,
        min_similarity: float = 0.7,
        limit: int = 3,
    ) -> list[EpisodeResult]:
        """
        Find similar episodes based on query embedding.

        Args:
            query: Search query text
            min_similarity: Minimum cosine similarity threshold (0.0-1.0)
            limit: Maximum number of results

        Returns:
            List of EpisodeResult sorted by similarity (descending)

        Raises:
            ValidationError: If inputs are invalid
            SearchError: If search operation fails
            EmbeddingError: If embedding generation fails
        """
        from cognitive_memory.types import EpisodeResult
        from mcp_server.tools import get_embedding_with_retry

        logger = logging.getLogger(__name__)

        # Input validation
        if not query or not isinstance(query, str):
            raise ValidationError("query must be a non-empty string")
        if not isinstance(min_similarity, (int, float)):
            raise ValidationError("min_similarity must be a number")
        if min_similarity < 0.0 or min_similarity > 1.0:
            raise ValidationError(f"min_similarity {min_similarity} is outside valid range [0.0, 1.0]")
        if not isinstance(limit, int):
            raise ValidationError("limit must be an integer")
        if limit < 1:
            raise ValidationError(f"limit {limit} must be >= 1")

        logger.info(f"Searching episodes with query: {query[:100]}..., min_similarity={min_similarity}, limit={limit}")

        try:
            # Initialize OpenAI client for embedding generation
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key or api_key == "sk-your-openai-api-key-here":
                raise EmbeddingError("OpenAI API key not configured")

            client = OpenAI(api_key=api_key)

            # Generate embedding for query
            try:
                embedding = asyncio.run(get_embedding_with_retry(client, query))
            except RuntimeError as e:
                raise EmbeddingError(f"Embedding generation failed: {e}") from e

            # Query database with pgvector cosine similarity
            with self._connection_manager.get_connection() as conn:
                # Register vector type for pgvector
                register_vector(conn)

                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, query, reward, reflection, created_at,
                           1 - (embedding <=> %s::vector) as similarity
                    FROM episode_memory
                    WHERE 1 - (embedding <=> %s::vector) >= %s
                    ORDER BY similarity DESC
                    LIMIT %s;
                    """,
                    (embedding, embedding, min_similarity, limit),
                )

                results = cursor.fetchall()

                logger.info(f"Found {len(results)} similar episodes")

                return [
                    EpisodeResult(
                        id=row["id"],
                        query=row["query"],
                        reward=row["reward"],
                        reflection=row["reflection"],
                        created_at=row["created_at"],
                    )
                    for row in results
                ]

        except Exception as e:
            if isinstance(e, (ValidationError, SearchError, EmbeddingError)):
                raise
            raise SearchError(f"Episode search failed: {e}") from e

    def list(self, limit: int = 10) -> list[EpisodeResult]:
        """
        Get the most recent episodes.

        Args:
            limit: Maximum number of episodes to return

        Returns:
            List of EpisodeResult sorted by created_at DESC (newest first)

        Raises:
            ValidationError: If inputs are invalid
            SearchError: If list operation fails
        """
        from cognitive_memory.types import EpisodeResult

        logger = logging.getLogger(__name__)

        # Input validation
        if not isinstance(limit, int):
            raise ValidationError("limit must be an integer")
        if limit < 1:
            raise ValidationError(f"limit {limit} must be >= 1")

        logger.info(f"Listing {limit} most recent episodes")

        try:
            with self._connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, query, reward, reflection, created_at
                    FROM episode_memory
                    ORDER BY created_at DESC
                    LIMIT %s;
                    """,
                    (limit,),
                )

                results = cursor.fetchall()

                logger.info(f"Retrieved {len(results)} recent episodes")

                return [
                    EpisodeResult(
                        id=row["id"],
                        query=row["query"],
                        reward=row["reward"],
                        reflection=row["reflection"],
                        created_at=row["created_at"],
                    )
                    for row in results
                ]

        except Exception as e:
            if isinstance(e, (ValidationError, SearchError)):
                raise
            raise SearchError(f"Episode list failed: {e}") from e


class GraphStore:
    """
    Dedicated interface for knowledge graph operations.

    Provides a focused API for graph node/edge management
    and path finding.

    Example:
        with GraphStore() as gs:
            node_id = gs.add_node("Python", "Technology")
            neighbors = gs.get_neighbors("Python")

    Note:
        Full implementation in Story 5.7
    """

    def __init__(self, connection_string: str | None = None) -> None:
        """Initialize GraphStore interface."""
        self._connection_manager = ConnectionManager(connection_string)
        self._is_connected = False

    def __enter__(self) -> GraphStore:
        """Enter context manager."""
        self._connection_manager.initialize()
        self._is_connected = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit context manager."""
        self._connection_manager.close()
        self._is_connected = False

    def _ensure_connected(self) -> None:
        """
        Ensure store is connected before operations.

        Raises:
            ConnectionError: If not connected to database
        """
        if not self._is_connected:
            raise ConnectionError(
                "GraphStore is not connected. Use context manager or call connect()."
            )

    def add_node(
        self,
        name: str,
        label: str,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """
        Add a node to the graph with idempotent operation.

        Args:
            name: Unique name identifier for the node
            label: Node type/category (e.g., "Project", "Technology")
            properties: Optional flexible metadata dictionary

        Returns:
            Node ID (str) for reference (UUID string)

        Raises:
            ValidationError: If name or label is empty
            ConnectionError: If not connected to database
            StorageError: If database operation fails
        """
        self._ensure_connected()

        # Input validation
        if not name or not name.strip():
            raise ValidationError("name cannot be empty")
        if not label or not label.strip():
            raise ValidationError("label cannot be empty")

        try:
            # Convert properties to JSON string for database storage
            properties_json = json.dumps(properties) if properties else "{}"

            # Delegate to mcp_server function
            result = db_add_node(
                label=label,
                name=name,
                properties=properties_json
            )

            return str(result["node_id"])

        except Exception as e:
            raise StorageError(f"Failed to add node: {e}") from e

    def add_edge(
        self,
        source_name: str,
        target_name: str,
        relation: str,
        weight: float = 1.0,
    ) -> str:
        """
        Add an edge to the graph with auto-upsert nodes.

        Args:
            source_name: Name of source node (created if not exists)
            target_name: Name of target node (created if not exists)
            relation: Relationship type (e.g., "USES", "SOLVES", "RELATED_TO")
            weight: Edge weight between 0.0 and 1.0

        Returns:
            Edge ID (str) for reference (UUID string)

        Raises:
            ValidationError: If names are empty, relation is empty, or weight out of range
            ConnectionError: If not connected to database
            StorageError: If database operation fails
        """
        self._ensure_connected()

        # Input validation
        if not source_name or not source_name.strip():
            raise ValidationError("source_name cannot be empty")
        if not target_name or not target_name.strip():
            raise ValidationError("target_name cannot be empty")
        if not relation or not relation.strip():
            raise ValidationError("relation cannot be empty")
        if not 0.0 <= weight <= 1.0:
            raise ValidationError("weight must be between 0.0 and 1.0")

        try:
            # Delegate to mcp_server function (handles auto-upsert of nodes)
            result = db_add_edge(
                source_name=source_name,
                target_name=target_name,
                relation=relation,
                weight=weight
            )

            return str(result["edge_id"])

        except Exception as e:
            raise StorageError(f"Failed to add edge: {e}") from e

    def query_neighbors(
        self,
        node_name: str,
        depth: int = 1,
        relation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get neighbor nodes with single-hop and multi-hop traversal.

        Args:
            node_name: Starting node name for traversal
            depth: Maximum traversal depth (1-5 for performance)
            relation_type: Optional filter for specific relation types

        Returns:
            List of neighbor node dictionaries with graph information

        Raises:
            ValidationError: If node_name is empty or depth out of range
            ConnectionError: If not connected to database
            StorageError: If database operation fails
        """
        self._ensure_connected()

        # Input validation
        if not node_name or not node_name.strip():
            raise ValidationError("node_name cannot be empty")
        if not 1 <= depth <= 5:
            raise ValidationError("depth must be between 1 and 5")

        try:
            # Get start node
            start_node = get_node_by_name(node_name)
            if not start_node:
                return []  # No node found = no neighbors

            # Delegate to mcp_server function
            neighbors = db_query_neighbors(
                node_id=start_node["id"],
                relation_type=relation_type,
                max_depth=depth
            )

            return neighbors

        except Exception as e:
            raise StorageError(f"Failed to query neighbors: {e}") from e

    def get_neighbors(
        self,
        node_name: str,
        depth: int = 1,
        relation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Legacy method for backward compatibility.

        Deprecated: Use query_neighbors() instead.
        """
        return self.query_neighbors(node_name, depth, relation_type)

    def find_path(
        self,
        start_node: str,
        end_node: str,
        max_depth: int = 5,
    ) -> dict[str, Any]:
        """
        Find shortest path between nodes using BFS-based pathfinding.

        Args:
            start_node: Name of starting node
            end_node: Name of target node
            max_depth: Maximum traversal depth (1-10 for performance)

        Returns:
            Dictionary with path_found, path_length, and paths data

        Raises:
            ValidationError: If node names are empty or max_depth out of range
            ConnectionError: If not connected to database
            StorageError: If database operation fails
        """
        self._ensure_connected()

        # Input validation
        if not start_node or not start_node.strip():
            raise ValidationError("start_node cannot be empty")
        if not end_node or not end_node.strip():
            raise ValidationError("end_node cannot be empty")
        if not 1 <= max_depth <= 10:
            raise ValidationError("max_depth must be between 1 and 10")

        try:
            # Delegate to mcp_server function
            result = db_find_path(
                start_node=start_node,
                end_node=end_node,
                max_depth=max_depth
            )

            return result

        except Exception as e:
            raise StorageError(f"Failed to find path: {e}") from e
