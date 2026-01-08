"""
suggest_lateral_edges Tool Implementation

MCP tool for suggesting potential lateral edges between graph nodes.
Uses semantic search to find nodes that might be related to a given node,
excluding nodes that are already directly connected.

Story: Phase 3b - Lateral Edge Suggestions (Graph-Nutzung-Request 2026-01-02)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from openai import APIConnectionError, OpenAI, RateLimitError

from mcp_server.db.graph import get_node_by_name, query_neighbors


async def _get_embedding(text: str) -> list[float] | None:
    """
    Generate embedding for text using OpenAI API with retry logic.

    Returns None if embedding generation fails.
    """
    logger = logging.getLogger(__name__)
    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return None

    client = OpenAI(api_key=api_key)
    delays = [1, 2, 4]
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except RateLimitError:
            if attempt < max_retries - 1:
                await asyncio.sleep(delays[attempt])
            else:
                logger.error(f"Rate limit after {max_retries} attempts")
                return None
        except APIConnectionError:
            if attempt < max_retries - 1:
                await asyncio.sleep(delays[attempt])
            else:
                logger.error(f"API connection error after {max_retries} attempts")
                return None
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    return None


async def handle_suggest_lateral_edges(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Suggest potential lateral edges for a given node.

    Performs semantic search to find nodes that might be related,
    then filters out already-connected nodes and suggests relation types.

    Args:
        arguments: Tool arguments containing:
            - node_name: Name of the node to find lateral edges for
            - top_k: Maximum number of suggestions (default: 5)

    Returns:
        Dict with suggested lateral edges and their potential relations.
    """
    logger = logging.getLogger(__name__)

    try:
        # Extract parameters
        node_name = arguments.get("node_name")
        top_k = arguments.get("top_k", 5)

        # Parameter validation
        if not node_name or not isinstance(node_name, str):
            return {
                "error": "Parameter validation failed",
                "details": "Missing or invalid 'node_name' parameter (must be non-empty string)",
                "tool": "suggest_lateral_edges",
            }

        # 1. Verify the node exists
        source_node = get_node_by_name(node_name)
        if not source_node:
            return {
                "error": "Node not found",
                "details": f"No node with name '{node_name}' exists in the graph",
                "tool": "suggest_lateral_edges",
            }

        source_node_id = source_node["id"]

        # 2. Get already-connected nodes (to exclude them)
        connected_neighbors = query_neighbors(
            node_id=source_node_id,
            relation_type=None,  # All relations
            max_depth=1,
            direction="both",
        )
        connected_node_ids = {n.get("node_id") for n in connected_neighbors}
        connected_node_ids.add(source_node_id)  # Also exclude self

        # 3. Perform semantic search for related nodes
        # We use hybrid_search via direct DB query for graph nodes only
        from mcp_server.db.connection import get_connection

        # Get embedding for the node name
        query_embedding = await _get_embedding(node_name)

        if query_embedding is None:
            return {
                "error": "Embedding generation failed",
                "details": f"Could not generate embedding for '{node_name}'",
                "tool": "suggest_lateral_edges",
            }

        # Search for semantically similar L2 insights and check if they have graph connections
        with get_connection() as conn:
            cursor = conn.cursor()

            # First, search L2 insights for semantic matches
            cursor.execute(
                """
                SELECT
                    l2.id,
                    l2.content,
                    1 - (l2.embedding <=> %s::vector) as similarity
                FROM l2_insights l2
                WHERE l2.embedding IS NOT NULL
                ORDER BY l2.embedding <=> %s::vector
                LIMIT %s;
                """,
                (query_embedding, query_embedding, top_k * 3)  # Get more, we'll filter
            )
            l2_results = cursor.fetchall()

            # Also search graph nodes directly by name similarity (keyword-based)
            cursor.execute(
                """
                SELECT
                    n.id::text as node_id,
                    n.name,
                    n.label,
                    n.properties,
                    ts_rank(to_tsvector('german', n.name), plainto_tsquery('german', %s)) as rank
                FROM nodes n
                WHERE to_tsvector('german', n.name) @@ plainto_tsquery('german', %s)
                   OR n.name ILIKE %s
                ORDER BY rank DESC
                LIMIT %s;
                """,
                (node_name, node_name, f"%{node_name}%", top_k * 2)
            )
            keyword_node_results = cursor.fetchall()

        # 4. Collect candidate nodes (from graph nodes + L2-linked nodes)
        candidates = []
        seen_names = set()

        # Add keyword-matched nodes
        for row in keyword_node_results:
            if row["node_id"] not in connected_node_ids and row["name"] not in seen_names:
                seen_names.add(row["name"])
                candidates.append({
                    "node_id": row["node_id"],
                    "name": row["name"],
                    "label": row["label"],
                    "match_type": "keyword",
                    "score": float(row["rank"]) if row["rank"] else 0.5,
                })

        # For L2 insights, check if they're linked to graph nodes
        # (This is a simplified approach - in production, we'd have vector_id links)
        for row in l2_results:
            # Extract potential node names from L2 content
            content = row["content"]
            similarity = float(row["similarity"])

            # Search for nodes mentioned in the L2 content
            with get_connection() as conn:
                cursor = conn.cursor()
                # Find nodes whose names appear in this insight's content
                cursor.execute(
                    """
                    SELECT
                        n.id::text as node_id,
                        n.name,
                        n.label,
                        n.properties
                    FROM nodes n
                    WHERE %s ILIKE '%%' || n.name || '%%'
                      AND n.id::text NOT IN (SELECT unnest(%s::text[]))
                    LIMIT 3;
                    """,
                    (content, list(connected_node_ids))
                )
                mentioned_nodes = cursor.fetchall()

                for node in mentioned_nodes:
                    if node["name"] not in seen_names:
                        seen_names.add(node["name"])
                        candidates.append({
                            "node_id": node["node_id"],
                            "name": node["name"],
                            "label": node["label"],
                            "match_type": "semantic_l2",
                            "score": similarity,
                        })

        # 5. Sort by score and take top_k
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = candidates[:top_k]

        # 6. Suggest relation types based on labels
        suggestions = []
        for candidate in top_candidates:
            suggested_relations = _suggest_relations(
                source_label=source_node.get("label", "Entity"),
                target_label=candidate.get("label", "Entity"),
                target_name=candidate["name"]
            )

            suggestions.append({
                "target_node": candidate["name"],
                "target_label": candidate.get("label", "Entity"),
                "match_type": candidate["match_type"],
                "confidence": round(candidate["score"], 3),
                "suggested_relations": suggested_relations,
            })

        logger.info(f"Found {len(suggestions)} lateral edge suggestions for '{node_name}'")

        return {
            "source_node": node_name,
            "suggestions": suggestions,
            "count": len(suggestions),
            "already_connected": len(connected_node_ids) - 1,  # Exclude self
            "tool": "suggest_lateral_edges",
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Error in suggest_lateral_edges: {e}")
        return {
            "error": "Tool execution failed",
            "details": str(e),
            "tool": "suggest_lateral_edges",
            "status": "error",
        }


def _suggest_relations(source_label: str, target_label: str, target_name: str) -> list[str]:
    """
    Suggest appropriate relation types based on node labels and names.

    Returns a prioritized list of suggested relation types.
    """
    suggestions = []

    # Label-based suggestions
    label_relations = {
        ("Entity", "Pattern"): ["MANIFESTATION_OF", "RELATED_TO"],
        ("Pattern", "Entity"): ["LEADS_TO", "MANIFESTATION_OF"],
        ("Entity", "Entity"): ["RELATED_TO", "LEADS_TO", "CONTRASTS_WITH"],
        ("Practice", "Entity"): ["RELATED_TO", "ENABLES"],
        ("Entity", "Practice"): ["USES", "RELATED_TO"],
        ("Concept", "Concept"): ["RELATED_TO", "CONTRASTS_WITH"],
    }

    key = (source_label, target_label)
    if key in label_relations:
        suggestions.extend(label_relations[key])

    # Name-based heuristics
    target_lower = target_name.lower()
    if "anti-pattern" in target_lower or "vermeid" in target_lower:
        suggestions.insert(0, "CONTRASTS_WITH")
    if "bias" in target_lower or "fehler" in target_lower:
        suggestions.insert(0, "MANIFESTATION_OF")
    if any(word in target_lower for word in ["lernen", "verstehen", "erkennen"]):
        suggestions.insert(0, "LEADS_TO")

    # Always include RELATED_TO as fallback
    if "RELATED_TO" not in suggestions:
        suggestions.append("RELATED_TO")

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for rel in suggestions:
        if rel not in seen:
            seen.add(rel)
            unique.append(rel)

    return unique[:3]  # Return top 3 suggestions
