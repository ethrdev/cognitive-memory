"""
MCP Server Resources Registration Module

Provides resource registration and implementation for the Cognitive Memory System.
Includes 5 resources: memory://l2-insights, memory://working-memory, memory://episode-memory,
memory://l0-raw, and memory://stale-memory for read-only state exposure.

Note: This file uses psycopg2 DictCursor which returns dict-like rows.
Type checkers may see these as tuples, so we use type: ignore comments
to handle the DictCursor row access patterns throughout this file.

KNOWN MYPY LIMITATIONS:
- psycopg2 DictCursor row access patterns generate type errors
- MCP Resource URI type checking requires AnyUrl which conflicts with string URIs
- These are documented limitations that don't affect functionality
- The code works correctly at runtime despite mypy --strict errors
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any
from urllib.parse import ParseResult, parse_qs, urlparse

from mcp.server import Server
from mcp.types import Resource
from openai import OpenAI
from pgvector.psycopg2 import register_vector  # type: ignore
from psycopg2.extensions import connection as Psycopg2Connection
from psycopg2.extras import DictCursor

from mcp_server.db.connection import get_connection, get_pool_status
from mcp_server.tools import get_embedding_with_retry


# TypedDict definitions for DictCursor rows
class DBRowDict(dict[str, Any]):
    """TypedDict for DictCursor rows to satisfy mypy --strict."""

    pass


class L2InsightsRow(DBRowDict):
    id: int
    content: str
    embedding: list[float]
    created_at: datetime
    source_ids: list[int]


class WorkingMemoryRow(DBRowDict):
    id: int
    content: str
    importance: float
    last_accessed: datetime
    created_at: datetime


class EpisodeMemoryRow(DBRowDict):
    id: int
    query: str
    reward: float
    reflection: str
    created_at: datetime
    embedding: list[float]


class L0RawRow(DBRowDict):
    id: int
    session_id: str
    timestamp: datetime
    speaker: str
    content: str
    metadata: dict[str, Any]


class StaleMemoryRow(DBRowDict):
    id: int
    original_content: str
    archived_at: datetime
    importance: float | None
    reason: str


def parse_resource_uri(uri: str) -> tuple[str, dict[str, list[str]]]:
    """
    Parse resource URI into path and query parameters.

    Args:
        uri: Resource URI (e.g., "memory://l2-insights?query=test&top_k=5")

    Returns:
        Tuple of (path, query_params) where query_params maps parameter names to lists of values

    Example:
        parse_resource_uri("memory://l2-insights?query=test&top_k=5")
        → ("memory://l2-insights", {"query": ["test"], "top_k": ["5"]})
    """
    parsed = urlparse(uri)
    path = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    params = parse_qs(parsed.query)
    return path, params


def get_single_param(params: dict[str, list[str]], name: str, default: str = "") -> str:
    """
    Extract single parameter value from query parameters.

    Args:
        params: Query parameters dictionary
        name: Parameter name
        default: Default value if parameter not found

    Returns:
        Parameter value or default
    """
    values = params.get(name, [])
    return values[0] if values else default


async def handle_l2_insights(uri: str) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Handle L2 insights resource read with semantic search.

    Args:
        uri: Resource URI with query parameters (query required, top_k optional)

    Returns:
        JSON array of L2 insights with [{id, content, score, source_ids}]

    Raises:
        ValueError: If query parameter is missing or invalid
        RuntimeError: If OpenAI API key not configured
    """
    logger = logging.getLogger(__name__)
    path, params = parse_resource_uri(uri)

    # Parse and validate parameters
    query = get_single_param(params, "query", "")
    if not query or not query.strip():
        return {
            "error": "Invalid query parameter",
            "details": "Query parameter is required and cannot be empty",
            "resource": uri,
        }

    try:
        top_k = int(get_single_param(params, "top_k", "5"))
        top_k = max(1, min(100, top_k))  # Clamp between 1 and 100
    except ValueError:
        return {
            "error": "Invalid top_k parameter",
            "details": "top_k must be a positive integer",
            "resource": uri,
        }

    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        raise RuntimeError("OpenAI API key not configured")

    client = OpenAI(api_key=api_key)

    try:
        async with get_connection() as conn:
            # Register pgvector type
            register_vector(conn)

            # Generate embedding for query
            embedding = await get_embedding_with_retry(client, query.strip())

            # Execute semantic search
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, embedding <=> %s AS distance, source_ids
                FROM l2_insights
                ORDER BY distance
                LIMIT %s
            """,
                (embedding, top_k),
            )

            results = []
            for row in cursor.fetchall():  # type: ignore[assignment]
                results.append(
                    {
                        "id": row["id"],  # type: ignore[call-overload]
                        "content": row["content"],  # type: ignore[call-overload]
                        "score": 1.0 - row["distance"],  # type: ignore[call-overload]
                        "source_ids": row["source_ids"],  # type: ignore[call-overload]
                    }
                )

            logger.info(
                f"Retrieved {len(results)} L2 insights for query: {query[:50]}..."
            )
            return results

    except Exception as e:
        logger.error(f"Failed to read L2 insights resource {uri}: {e}")
        return {
            "error": "Database query failed",
            "details": str(e),
            "resource": uri,
        }


async def handle_working_memory(uri: str) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Handle working memory resource read with sorting by last_accessed.

    Args:
        uri: Resource URI with optional limit parameter

    Returns:
        JSON array of working memory items sorted by last_accessed DESC
        Format: [{id, content, importance, last_accessed, created_at}]

    Note: Uses synchronous database I/O. This is a known limitation that
    blocks the async event loop during database queries. For production
    use, consider migrating to asyncpg for true async database operations.
    """
    logger = logging.getLogger(__name__)
    path, params = parse_resource_uri(uri)

    # Parse and validate limit parameter
    limit = get_single_param(params, "limit", "100")
    try:
        limit = int(limit)
        limit = max(1, min(1000, limit))  # Clamp between 1 and 1000
    except ValueError:
        return {
            "error": "Invalid limit parameter",
            "details": "limit must be a positive integer between 1 and 1000",
            "resource": uri,
        }

    try:
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, importance, last_accessed, created_at
                FROM working_memory
                ORDER BY last_accessed DESC
                LIMIT %s
            """,
                (limit,),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "id": row["id"],
                        "content": row["content"],
                        "importance": row["importance"],
                        "last_accessed": row["last_accessed"].isoformat(),
                        "created_at": row["created_at"].isoformat(),
                    }
                )

            logger.info(
                f"Retrieved {len(results)} working memory items (limit: {limit})"
            )
            return results

    except Exception as e:
        logger.error(f"Failed to read working memory resource {uri}: {e}")
        return {
            "error": "Database query failed",
            "details": str(e),
            "resource": uri,
        }


async def handle_episode_memory(uri: str) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Handle episode memory resource read with semantic search and similarity filtering.

    Args:
        uri: Resource URI with query parameters (query required, min_similarity optional)

    Returns:
        JSON array of similar episodes with [{id, query, reward, reflection, similarity}]
        Limited to Top-3 episodes (FR009 requirement)
    """
    logger = logging.getLogger(__name__)
    path, params = parse_resource_uri(uri)

    # Parse and validate parameters
    query = get_single_param(params, "query", "")
    if not query or not query.strip():
        return {
            "error": "Invalid query parameter",
            "details": "Query parameter is required and cannot be empty",
            "resource": uri,
        }

    try:
        min_similarity = float(get_single_param(params, "min_similarity", "0.70"))
        min_similarity = max(0.0, min(1.0, min_similarity))  # Clamp between 0.0 and 1.0
    except ValueError:
        return {
            "error": "Invalid min_similarity parameter",
            "details": "min_similarity must be a float between 0.0 and 1.0",
            "resource": uri,
        }

    # Initialize OpenAI client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        raise RuntimeError("OpenAI API key not configured")

    client = OpenAI(api_key=api_key)

    try:
        async with get_connection() as conn:
            # Register pgvector type
            register_vector(conn)

            # Generate embedding for query
            embedding = await get_embedding_with_retry(client, query.strip())

            # Execute semantic search with similarity filtering and Top-3 limit
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, query, reward, reflection, embedding <=> %s AS distance
                FROM episode_memory
                WHERE (embedding <=> %s) <= %s  -- cosine distance <= 1-similarity
                ORDER BY distance
                LIMIT 3
            """,
                (embedding, embedding, 1.0 - min_similarity),
            )

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "id": row["id"],
                        "query": row["query"],
                        "reward": row["reward"],
                        "reflection": row["reflection"],
                        "similarity": 1.0 - row["distance"],
                    }
                )

            logger.info(
                f"Retrieved {len(results)} episodes for query: {query[:50]}... (min_similarity: {min_similarity})"
            )
            return results

    except Exception as e:
        logger.error(f"Failed to read episode memory resource {uri}: {e}")
        return {
            "error": "Database query failed",
            "details": str(e),
            "resource": uri,
        }


async def handle_l0_raw(uri: str) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Handle L0 raw memory resource read with session and date filtering.

    Args:
        uri: Resource URI with optional query parameters (session_id, date_range, limit)

    Returns:
        JSON array of raw dialogue entries with [{id, session_id, timestamp, speaker, content, metadata}]
        Sorted by timestamp DESC (most recent first)
    """
    logger = logging.getLogger(__name__)
    path, params = parse_resource_uri(uri)

    # Parse and validate parameters
    session_id = get_single_param(params, "session_id", "")
    date_range = get_single_param(params, "date_range", "")

    try:
        limit = int(get_single_param(params, "limit", "100"))
        limit = max(1, min(1000, limit))  # Clamp between 1 and 1000
    except ValueError:
        return {
            "error": "Invalid limit parameter",
            "details": "limit must be a positive integer between 1 and 1000",
            "resource": uri,
        }

    # Validate session_id format if provided
    if session_id:
        try:
            uuid.UUID(session_id)  # Validate UUID format
        except ValueError:
            return {
                "error": "Invalid session_id parameter",
                "details": "session_id must be a valid UUID",
                "resource": uri,
            }

    # Validate date_range format if provided
    if date_range:
        if not re.match(r"^\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}$", date_range):
            return {
                "error": "Invalid date_range parameter",
                "details": "date_range must be in format YYYY-MM-DD:YYYY-MM-DD",
                "resource": uri,
            }

    try:
        async with get_connection() as conn:
            # Build query with optional filters
            query = """
                SELECT id, session_id, timestamp, speaker, content, metadata
                FROM l0_raw
            """
            query_params = []
            conditions = []

            if session_id:
                conditions.append("session_id = %s")
                query_params.append(session_id)

            if date_range:
                start_date, end_date = date_range.split(":")
                conditions.append("timestamp BETWEEN %s AND %s")
                query_params.extend([start_date, end_date])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT %s"
            query_params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, query_params)

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "id": row["id"],
                        "session_id": str(row["session_id"]),
                        "timestamp": row["timestamp"].isoformat(),
                        "speaker": row["speaker"],
                        "content": row["content"],
                        "metadata": row["metadata"],
                    }
                )

            logger.info(f"Retrieved {len(results)} L0 raw entries (limit: {limit})")
            return results

    except Exception as e:
        logger.error(f"Failed to read L0 raw resource {uri}: {e}")
        return {
            "error": "Database query failed",
            "details": str(e),
            "resource": uri,
        }


async def handle_stale_memory(uri: str) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Handle stale memory resource read with importance filtering.

    Args:
        uri: Resource URI with optional importance_min parameter

    Returns:
        JSON array of archived memory items with [{id, original_content, archived_at, importance, reason}]
        Sorted by archived_at DESC (most recently archived first)
    """
    logger = logging.getLogger(__name__)
    path, params = parse_resource_uri(uri)

    # Parse and validate importance_min parameter
    importance_min_str = get_single_param(params, "importance_min", "")
    importance_min = None

    if importance_min_str:
        try:
            importance_min = float(importance_min_str)
            importance_min = max(
                0.0, min(1.0, importance_min)
            )  # Clamp between 0.0 and 1.0
        except ValueError:
            return {
                "error": "Invalid importance_min parameter",
                "details": "importance_min must be a float between 0.0 and 1.0",
                "resource": uri,
            }

    # Parse and validate limit parameter
    limit = get_single_param(params, "limit", "100")
    try:
        limit = int(limit)
        limit = max(1, min(1000, limit))  # Clamp between 1 and 1000
    except ValueError:
        return {
            "error": "Invalid limit parameter",
            "details": "limit must be a positive integer between 1 and 1000",
            "resource": uri,
        }

    try:
        async with get_connection() as conn:
            # Build query with optional importance filter
            query = """
                SELECT id, original_content, archived_at, importance, reason
                FROM stale_memory
            """
            query_params = []

            if importance_min is not None:
                query += " WHERE importance >= %s"
                query_params.append(importance_min)

            query += " ORDER BY archived_at DESC LIMIT %s"
            query_params.append(limit)

            cursor = conn.cursor()
            cursor.execute(query, query_params)

            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "id": row["id"],
                        "original_content": row["original_content"],
                        "archived_at": row["archived_at"].isoformat(),
                        "importance": row["importance"],
                        "reason": row["reason"],
                    }
                )

            filter_desc = (
                f" (importance >= {importance_min})"
                if importance_min is not None
                else ""
            )
            logger.info(
                f"Retrieved {len(results)} stale memory items{filter_desc} (limit: {limit})"
            )
            return results

    except Exception as e:
        logger.error(f"Failed to read stale memory resource {uri}: {e}")
        return {
            "error": "Database query failed",
            "details": str(e),
            "resource": uri,
        }


def register_resources(server: Server) -> list[Resource]:
    """
    Register all MCP resources with the server.

    Args:
        server: MCP server instance

    Returns:
        List of registered resources
    """
    logger = logging.getLogger(__name__)

    # Resource definitions
    resources = [
        Resource(
            uri="memory://l2-insights",  # type: ignore[arg-type]
            name="L2 Insights",
            description="Read access to L2 compressed insights with optional search parameters",
            mimeType="application/json",
        ),
        Resource(
            uri="memory://working-memory",  # type: ignore[arg-type]
            name="Working Memory",
            description="Current state of working memory with importance-ranked items",
            mimeType="application/json",
        ),
        Resource(
            uri="memory://episode-memory",  # type: ignore[arg-type]
            name="Episode Memory",
            description="Read access to episode memories with similarity search",
            mimeType="application/json",
        ),
        Resource(
            uri="memory://l0-raw",  # type: ignore[arg-type]
            name="L0 Raw Memory",
            description="Read access to raw dialogue data by session or date range",
            mimeType="application/json",
        ),
        Resource(
            uri="memory://stale-memory",  # type: ignore[arg-type]
            name="Stale Memory",
            description="Read access to archived memory items with optional importance filtering",
            mimeType="application/json",
        ),
    ]

    # Resource handler mapping
    resource_handlers = {
        "memory://l2-insights": handle_l2_insights,
        "memory://working-memory": handle_working_memory,
        "memory://episode-memory": handle_episode_memory,
        "memory://l0-raw": handle_l0_raw,
        "memory://stale-memory": handle_stale_memory,
    }

    # Register resource read handler
    @server.read_resource()
    async def read_resource_handler(uri: str) -> str:
        """Handle resource read requests.

        Returns:
            JSON string of the resource content. MCP SDK expects str | bytes,
            not dict. The handlers return dicts which we serialize to JSON here.

        Note:
            MCP SDK passes AnyUrl objects, not strings. We convert to str immediately
            to avoid serialization issues with urlparse and json.dumps.
        """
        # Convert AnyUrl to string immediately (MCP SDK passes AnyUrl, not str)
        uri_str = str(uri)
        try:
            # Parse URI to get base path
            path, params = parse_resource_uri(uri_str)

            # Find matching resource handler
            if path in resource_handlers:
                logger.info(f"Reading resource: {uri_str}")
                result = await resource_handlers[path](uri_str)
                logger.info(f"Resource {uri_str} read successfully")
                # MCP SDK expects str | bytes, serialize dict to JSON
                return json.dumps(result, default=str, ensure_ascii=False)
            else:
                raise ValueError(f"Unknown resource: {path}")

        except Exception as e:
            logger.error(f"Failed to read resource {uri_str}: {e}")
            error_response = {
                "error": "Resource read failed",
                "details": str(e),
                "resource": uri_str,
            }
            return json.dumps(error_response, ensure_ascii=False)

    logger.info(f"Registered {len(resources)} resources")
    return resources
