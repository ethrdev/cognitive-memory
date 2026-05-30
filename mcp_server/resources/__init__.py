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

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers
from openai import OpenAI
from pgvector.psycopg2 import register_vector  # type: ignore
from psycopg2.extensions import connection as Psycopg2Connection
from psycopg2.extras import DictCursor

from mcp_server.db.connection import (
    get_connection,
    get_connection_with_project_context,
    get_pool_status,
)
from mcp_server.exceptions import ProjectNotFoundError
from mcp_server.middleware.context import get_project_id, set_project_id
from mcp_server.middleware.tenant import validate_project_id
from mcp_server.tools import get_embedding_with_retry

_resource_logger = logging.getLogger(__name__)

# NOTE on architectural debt: FastMCP 3.x does not provide an `on_read_resource`
# middleware hook (only `on_call_tool`), so resource handlers must resolve their
# own project_id from headers / contextvar / env-var via
# `_resolve_project_id_for_resource()` below. If a future FastMCP version adds
# a resource middleware hook, the resolver can be removed and TenantMiddleware
# can cover both tools and resources uniformly. Until then, the resolver is the
# documented Tenant entry point for resource reads.
#
# RLS NOTE: cognitive-memory's DB user (`neondb_owner`) has BYPASSRLS, so the
# RLS policies on the domain tables are not enforced for the app's queries
# even when `get_connection_with_project_context()` sets the session vars.
# Each resource handler therefore filters explicitly with `WHERE project_id`
# in addition to opening the tenant-aware connection (defense in depth). When
# the DB user moves to a non-BYPASSRLS role, the explicit WHEREs become
# redundant but remain harmless.


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


async def _resolve_project_id_for_resource() -> str:
    """
    Resolve and activate the project_id for a resource read.

    Resources do not flow through ``TenantMiddleware`` (FastMCP 3.x has no
    ``on_read_resource`` hook), so they must resolve their own project context
    before opening a tenant-aware DB connection.

    Resolution order (mirrors ``TenantMiddleware._extract_project_id``, minus
    ``_meta`` because resources have no MiddlewareContext):

        1. HTTP ``X-Project-ID`` header (production / HTTP transport)
        2. ``project_context`` contextvar (already set, e.g. by tests/scripts)
        3. ``PROJECT_ID`` environment variable (Claude Code stdio integration)
        4. Otherwise: ``ProjectContextRequiredError`` via ``RuntimeError``

    The resolved id is validated against ``project_registry`` and pushed into
    the ``project_context`` contextvar so that
    ``get_connection_with_project_context()`` picks it up and RLS filters apply.

    Returns:
        The validated, active project_id.

    Raises:
        RuntimeError: If no project context can be resolved.
        ProjectNotFoundError: If the resolved id is not in project_registry.
    """
    # 1. HTTP header (production)
    project_id: str | None = None
    try:
        headers = get_http_headers()
        if header_pid := headers.get("x-project-id"):
            project_id = header_pid
            _resource_logger.debug(f"Resource resolver: project_id from HTTP header: {project_id}")
    except RuntimeError:
        # No HTTP request context — fall through
        pass

    # 2. Existing contextvar (tests, scripts that pre-set context)
    if project_id is None:
        if existing := get_project_id():
            project_id = existing
            _resource_logger.debug(f"Resource resolver: project_id from contextvar: {project_id}")

    # 3. Environment variable (Claude Code stdio)
    if project_id is None:
        if env_pid := os.environ.get("PROJECT_ID"):
            project_id = env_pid
            _resource_logger.debug(f"Resource resolver: project_id from PROJECT_ID env: {project_id}")

    # 4. No context — strict error
    if project_id is None:
        raise RuntimeError(
            "Missing project context for resource read. Provide X-Project-ID header "
            "(HTTP), set project_context via set_project_id() (tests/scripts), or "
            "PROJECT_ID environment variable (Claude Code stdio)."
        )

    # Validate against registry (raises ProjectNotFoundError on miss)
    metadata = await validate_project_id(project_id)

    # Activate context so get_connection_with_project_context() can pick it up
    set_project_id(metadata.project_id)

    return metadata.project_id


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
        project_id = await _resolve_project_id_for_resource()
        async with get_connection_with_project_context() as conn:
            # Register pgvector type
            register_vector(conn)

            # Generate embedding for query
            embedding = await get_embedding_with_retry(client, query.strip())

            # Execute semantic search. Explicit project_id WHERE for defense
            # in depth — the app DB user has BYPASSRLS so RLS alone isn't
            # sufficient; the resolver + WHERE clause is the working fix.
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, embedding <=> %s::vector AS distance, source_ids
                FROM l2_insights
                WHERE project_id = %s
                ORDER BY distance
                LIMIT %s
            """,
                (embedding, project_id, top_k),
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

    except (RuntimeError, ProjectNotFoundError) as e:
        logger.warning(f"Resource project context error for {uri}: {e}")
        return {
            "error": "Missing or invalid project context",
            "details": str(e),
            "resource": uri,
        }
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
        project_id = await _resolve_project_id_for_resource()
        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, content, importance, last_accessed, created_at
                FROM working_memory
                WHERE project_id = %s
                ORDER BY last_accessed DESC
                LIMIT %s
            """,
                (project_id, limit),
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

    except (RuntimeError, ProjectNotFoundError) as e:
        logger.warning(f"Resource project context error for {uri}: {e}")
        return {
            "error": "Missing or invalid project context",
            "details": str(e),
            "resource": uri,
        }
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
        project_id = await _resolve_project_id_for_resource()
        async with get_connection_with_project_context() as conn:
            # Register pgvector type
            register_vector(conn)

            # Generate embedding for query
            embedding = await get_embedding_with_retry(client, query.strip())

            # Execute semantic search with similarity filter, project_id filter,
            # and Top-3 limit. Explicit project_id WHERE for defense in depth.
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, query, reward, reflection, embedding <=> %s::vector AS distance
                FROM episode_memory
                WHERE project_id = %s
                  AND (embedding <=> %s::vector) <= %s  -- cosine distance <= 1-similarity
                ORDER BY distance
                LIMIT 3
            """,
                (embedding, project_id, embedding, 1.0 - min_similarity),
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

    except (RuntimeError, ProjectNotFoundError) as e:
        logger.warning(f"Resource project context error for {uri}: {e}")
        return {
            "error": "Missing or invalid project context",
            "details": str(e),
            "resource": uri,
        }
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
        project_id = await _resolve_project_id_for_resource()
        async with get_connection_with_project_context() as conn:
            # Build query — always filter by project_id (defense in depth)
            query = """
                SELECT id, session_id, timestamp, speaker, content, metadata
                FROM l0_raw
                WHERE project_id = %s
            """
            query_params: list[Any] = [project_id]

            if session_id:
                query += " AND session_id = %s"
                query_params.append(session_id)

            if date_range:
                start_date, end_date = date_range.split(":")
                query += " AND timestamp BETWEEN %s AND %s"
                query_params.extend([start_date, end_date])

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

    except (RuntimeError, ProjectNotFoundError) as e:
        logger.warning(f"Resource project context error for {uri}: {e}")
        return {
            "error": "Missing or invalid project context",
            "details": str(e),
            "resource": uri,
        }
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
        project_id = await _resolve_project_id_for_resource()
        async with get_connection_with_project_context() as conn:
            # Always filter by project_id; optional importance filter chains on
            query = """
                SELECT id, original_content, archived_at, importance, reason
                FROM stale_memory
                WHERE project_id = %s
            """
            query_params: list[Any] = [project_id]

            if importance_min is not None:
                query += " AND importance >= %s"
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

    except (RuntimeError, ProjectNotFoundError) as e:
        logger.warning(f"Resource project context error for {uri}: {e}")
        return {
            "error": "Missing or invalid project context",
            "details": str(e),
            "resource": uri,
        }
    except Exception as e:
        logger.error(f"Failed to read stale memory resource {uri}: {e}")
        return {
            "error": "Database query failed",
            "details": str(e),
            "resource": uri,
        }


def register_resources(server: FastMCP) -> list[str]:
    """
    Register all MCP resources with the FastMCP server.

    Uses FastMCP 3.x decorator pattern with RFC 6570 query parameters.

    Args:
        server: FastMCP server instance

    Returns:
        List of registered resource URIs
    """
    logger = logging.getLogger(__name__)
    registered_uris: list[str] = []

    # L2 Insights Resource - semantic search with query parameter
    @server.resource(
        "memory://l2-insights{?query,top_k}",
        name="L2 Insights",
        description="Read access to L2 compressed insights with semantic search",
        mime_type="application/json",
    )
    async def read_l2_insights(query: str = "", top_k: int = 5) -> str:
        """Handle L2 insights resource read with semantic search."""
        if not query or not query.strip():
            return json.dumps({
                "error": "Invalid query parameter",
                "details": "Query parameter is required and cannot be empty",
                "resource": "memory://l2-insights",
            })

        top_k = max(1, min(100, top_k))

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-your-openai-api-key-here":
            return json.dumps({
                "error": "Configuration error",
                "details": "OpenAI API key not configured",
                "resource": "memory://l2-insights",
            })

        client = OpenAI(api_key=api_key)

        try:
            project_id = await _resolve_project_id_for_resource()
            async with get_connection_with_project_context() as conn:
                register_vector(conn)
                embedding = await get_embedding_with_retry(client, query.strip())

                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, content, embedding <=> %s::vector AS distance, source_ids
                    FROM l2_insights
                    WHERE project_id = %s
                    ORDER BY distance
                    LIMIT %s
                    """,
                    (embedding, project_id, top_k),
                )

                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row["id"],
                        "content": row["content"],
                        "score": 1.0 - row["distance"],
                        "source_ids": row["source_ids"],
                    })

                logger.info(f"Retrieved {len(results)} L2 insights for query: {query[:50]}...")
                return json.dumps(results, default=str, ensure_ascii=False)

        except (RuntimeError, ProjectNotFoundError) as e:
            logger.warning(f"L2 insights resource project context error: {e}")
            return json.dumps({
                "error": "Missing or invalid project context",
                "details": str(e),
                "resource": "memory://l2-insights",
            })
        except Exception as e:
            logger.error(f"Failed to read L2 insights: {e}")
            return json.dumps({
                "error": "Database query failed",
                "details": str(e),
                "resource": "memory://l2-insights",
            })

    registered_uris.append("memory://l2-insights{?query,top_k}")

    # Working Memory Resource
    @server.resource(
        "memory://working-memory{?limit}",
        name="Working Memory",
        description="Current state of working memory with importance-ranked items",
        mime_type="application/json",
    )
    async def read_working_memory(limit: int = 100) -> str:
        """Handle working memory resource read."""
        limit = max(1, min(1000, limit))

        try:
            project_id = await _resolve_project_id_for_resource()
            async with get_connection_with_project_context() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, content, importance, last_accessed, created_at
                    FROM working_memory
                    WHERE project_id = %s
                    ORDER BY last_accessed DESC
                    LIMIT %s
                    """,
                    (project_id, limit),
                )

                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row["id"],
                        "content": row["content"],
                        "importance": row["importance"],
                        "last_accessed": row["last_accessed"].isoformat(),
                        "created_at": row["created_at"].isoformat(),
                    })

                logger.info(f"Retrieved {len(results)} working memory items (limit: {limit})")
                return json.dumps(results, default=str, ensure_ascii=False)

        except (RuntimeError, ProjectNotFoundError) as e:
            logger.warning(f"Working memory resource project context error: {e}")
            return json.dumps({
                "error": "Missing or invalid project context",
                "details": str(e),
                "resource": "memory://working-memory",
            })
        except Exception as e:
            logger.error(f"Failed to read working memory: {e}")
            return json.dumps({
                "error": "Database query failed",
                "details": str(e),
                "resource": "memory://working-memory",
            })

    registered_uris.append("memory://working-memory{?limit}")

    # Episode Memory Resource - semantic search
    @server.resource(
        "memory://episode-memory{?query,min_similarity}",
        name="Episode Memory",
        description="Read access to episode memories with similarity search",
        mime_type="application/json",
    )
    async def read_episode_memory(query: str = "", min_similarity: float = 0.70) -> str:
        """Handle episode memory resource read with semantic search."""
        if not query or not query.strip():
            return json.dumps({
                "error": "Invalid query parameter",
                "details": "Query parameter is required and cannot be empty",
                "resource": "memory://episode-memory",
            })

        min_similarity = max(0.0, min(1.0, min_similarity))

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "sk-your-openai-api-key-here":
            return json.dumps({
                "error": "Configuration error",
                "details": "OpenAI API key not configured",
                "resource": "memory://episode-memory",
            })

        client = OpenAI(api_key=api_key)

        try:
            project_id = await _resolve_project_id_for_resource()
            async with get_connection_with_project_context() as conn:
                register_vector(conn)
                embedding = await get_embedding_with_retry(client, query.strip())

                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, query, reward, reflection, embedding <=> %s::vector AS distance
                    FROM episode_memory
                    WHERE project_id = %s
                      AND (embedding <=> %s::vector) <= %s
                    ORDER BY distance
                    LIMIT 3
                    """,
                    (embedding, project_id, embedding, 1.0 - min_similarity),
                )

                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row["id"],
                        "query": row["query"],
                        "reward": row["reward"],
                        "reflection": row["reflection"],
                        "similarity": 1.0 - row["distance"],
                    })

                logger.info(f"Retrieved {len(results)} episodes for query: {query[:50]}...")
                return json.dumps(results, default=str, ensure_ascii=False)

        except (RuntimeError, ProjectNotFoundError) as e:
            logger.warning(f"Episode memory resource project context error: {e}")
            return json.dumps({
                "error": "Missing or invalid project context",
                "details": str(e),
                "resource": "memory://episode-memory",
            })
        except Exception as e:
            logger.error(f"Failed to read episode memory: {e}")
            return json.dumps({
                "error": "Database query failed",
                "details": str(e),
                "resource": "memory://episode-memory",
            })

    registered_uris.append("memory://episode-memory{?query,min_similarity}")

    # L0 Raw Memory Resource
    @server.resource(
        "memory://l0-raw{?session_id,date_range,limit}",
        name="L0 Raw Memory",
        description="Read access to raw dialogue data by session or date range",
        mime_type="application/json",
    )
    async def read_l0_raw(
        session_id: str = "", date_range: str = "", limit: int = 100
    ) -> str:
        """Handle L0 raw memory resource read."""
        limit = max(1, min(1000, limit))

        # Validate session_id format if provided
        if session_id:
            try:
                uuid.UUID(session_id)
            except ValueError:
                return json.dumps({
                    "error": "Invalid session_id parameter",
                    "details": "session_id must be a valid UUID",
                    "resource": "memory://l0-raw",
                })

        # Validate date_range format if provided
        if date_range and not re.match(r"^\d{4}-\d{2}-\d{2}:\d{4}-\d{2}-\d{2}$", date_range):
            return json.dumps({
                "error": "Invalid date_range parameter",
                "details": "date_range must be in format YYYY-MM-DD:YYYY-MM-DD",
                "resource": "memory://l0-raw",
            })

        try:
            project_id = await _resolve_project_id_for_resource()
            async with get_connection_with_project_context() as conn:
                query_sql = """
                    SELECT id, session_id, timestamp, speaker, content, metadata
                    FROM l0_raw
                    WHERE project_id = %s
                """
                query_params: list[Any] = [project_id]

                if session_id:
                    query_sql += " AND session_id = %s"
                    query_params.append(session_id)

                if date_range:
                    start_date, end_date = date_range.split(":")
                    query_sql += " AND timestamp BETWEEN %s AND %s"
                    query_params.extend([start_date, end_date])

                query_sql += " ORDER BY timestamp DESC LIMIT %s"
                query_params.append(limit)

                cursor = conn.cursor()
                cursor.execute(query_sql, query_params)

                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row["id"],
                        "session_id": str(row["session_id"]),
                        "timestamp": row["timestamp"].isoformat(),
                        "speaker": row["speaker"],
                        "content": row["content"],
                        "metadata": row["metadata"],
                    })

                logger.info(f"Retrieved {len(results)} L0 raw entries (limit: {limit})")
                return json.dumps(results, default=str, ensure_ascii=False)

        except (RuntimeError, ProjectNotFoundError) as e:
            logger.warning(f"L0 raw resource project context error: {e}")
            return json.dumps({
                "error": "Missing or invalid project context",
                "details": str(e),
                "resource": "memory://l0-raw",
            })
        except Exception as e:
            logger.error(f"Failed to read L0 raw: {e}")
            return json.dumps({
                "error": "Database query failed",
                "details": str(e),
                "resource": "memory://l0-raw",
            })

    registered_uris.append("memory://l0-raw{?session_id,date_range,limit}")

    # Stale Memory Resource
    @server.resource(
        "memory://stale-memory{?importance_min,limit}",
        name="Stale Memory",
        description="Read access to archived memory items with optional importance filtering",
        mime_type="application/json",
    )
    async def read_stale_memory(importance_min: float = -1.0, limit: int = 100) -> str:
        """Handle stale memory resource read."""
        limit = max(1, min(1000, limit))

        # -1.0 means no filter (default)
        if importance_min >= 0.0:
            importance_min = max(0.0, min(1.0, importance_min))

        try:
            project_id = await _resolve_project_id_for_resource()
            async with get_connection_with_project_context() as conn:
                query_sql = """
                    SELECT id, original_content, archived_at, importance, reason
                    FROM stale_memory
                    WHERE project_id = %s
                """
                query_params: list[Any] = [project_id]

                if importance_min >= 0.0:
                    query_sql += " AND importance >= %s"
                    query_params.append(importance_min)

                query_sql += " ORDER BY archived_at DESC LIMIT %s"
                query_params.append(limit)

                cursor = conn.cursor()
                cursor.execute(query_sql, query_params)

                results = []
                for row in cursor.fetchall():
                    results.append({
                        "id": row["id"],
                        "original_content": row["original_content"],
                        "archived_at": row["archived_at"].isoformat(),
                        "importance": row["importance"],
                        "reason": row["reason"],
                    })

                filter_desc = f" (importance >= {importance_min})" if importance_min >= 0.0 else ""
                logger.info(f"Retrieved {len(results)} stale memory items{filter_desc} (limit: {limit})")
                return json.dumps(results, default=str, ensure_ascii=False)

        except (RuntimeError, ProjectNotFoundError) as e:
            logger.warning(f"Stale memory resource project context error: {e}")
            return json.dumps({
                "error": "Missing or invalid project context",
                "details": str(e),
                "resource": "memory://stale-memory",
            })
        except Exception as e:
            logger.error(f"Failed to read stale memory: {e}")
            return json.dumps({
                "error": "Database query failed",
                "details": str(e),
                "resource": "memory://stale-memory",
            })

    registered_uris.append("memory://stale-memory{?importance_min,limit}")

    logger.info(f"Registered {len(registered_uris)} resources using FastMCP decorator pattern")
    return registered_uris
