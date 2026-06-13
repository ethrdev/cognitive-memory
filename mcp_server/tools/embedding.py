"""
Shared embedding helper for graph tools.

Provides a single OpenAI embedding path (text-embedding-3-small) with the same
retry semantics already used by suggest_lateral_edges, so that graph_add_node can
auto-embed nodes on creation without duplicating the retry logic.

The embedding is stored in the `l2_insights` table (vector_id FK on nodes points
there). To keep node embeddings self-contained — without forcing every node to
carry a full L2 insight — graph nodes get a lightweight L2 row whose content is
the node's `name` + `summary` property. The node's `vector_id` then references it,
which is exactly what the hybrid/graph search path expects.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from openai import APIConnectionError, OpenAI, RateLimitError

from mcp_server.db.connection import get_connection_with_project_context

logger = logging.getLogger(__name__)

# Same model used across the codebase (suggest_lateral_edges, compress_to_l2_insight)
EMBEDDING_MODEL = "text-embedding-3-small"


async def get_embedding(text: str) -> list[float] | None:
    """
    Generate an embedding for `text` via OpenAI with retry/backoff.

    Mirrors the retry logic in suggest_lateral_edges._get_embedding so that node
    creation uses the identical path. Returns None on failure (caller decides how
    to degrade — node creation falls back to vector_id=None and logs a warning).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        logger.error("OPENAI_API_KEY not set — cannot auto-embed node")
        return None

    client = OpenAI(api_key=api_key)
    delays = [1, 2, 4]
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=text,
                encoding_format="float",
            )
            return response.data[0].embedding
        except RateLimitError:
            if attempt < max_retries - 1:
                await asyncio.sleep(delays[attempt])
            else:
                logger.error(f"Rate limit after {max_retries} attempts (node embedding)")
                return None
        except APIConnectionError:
            if attempt < max_retries - 1:
                await asyncio.sleep(delays[attempt])
            else:
                logger.error(f"API connection error after {max_retries} attempts (node embedding)")
                return None
        except Exception as e:
            logger.error(f"Embedding error (node embedding): {e}")
            return None

    return None


def build_node_embedding_text(name: str, properties: dict[str, Any] | None) -> str:
    """Compose the text to embed for a node: `name` + `summary` property."""
    summary = ""
    if properties:
        raw = properties.get("summary")
        if isinstance(raw, str):
            summary = raw.strip()
    if summary:
        return f"{name}\n{summary}"
    return name


async def generate_node_embedding(
    name: str,
    properties: dict[str, Any] | None,
) -> int | None:
    """
    Create an L2 insight row holding the node's embedding and return its id.

    The returned id is meant to be stored as the node's `vector_id`, which is how
    the graph search path resolves node -> embedding. Returns None if embedding
    generation fails (caller should proceed without a vector_id rather than fail
    node creation).

    Story Graph-Enforcement A4: Auto-Embedding bei Knoten-Anlage.
    """
    text = build_node_embedding_text(name, properties)
    embedding = await get_embedding(text)
    if embedding is None:
        return None

    from mcp_server.middleware.context import get_current_project

    project_id = get_current_project()

    try:
        from pgvector.psycopg2 import register_vector

        async with get_connection_with_project_context() as conn:
            register_vector(conn)
            cursor = conn.cursor()
            metadata = {"source": "graph_node_embedding", "node_name": name}
            cursor.execute(
                """
                INSERT INTO l2_insights (project_id, content, embedding, source_ids, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (project_id, text, embedding, [], json.dumps(metadata)),
            )
            row = cursor.fetchone()
            conn.commit()
            if row:
                return int(row["id"])
            return None
    except Exception as e:
        logger.error(f"Failed to persist node embedding for '{name}': {e}")
        return None
