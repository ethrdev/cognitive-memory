#!/usr/bin/env python3
"""
Test Graph Setup Script for Story 4.7

Creates test data for BMAD-BMM integration testing including:
- 10+ Nodes with various labels (Project, Technology, Requirement, Error, Solution)
- 15+ Edges with various relations (USES, SOLVED_BY, DEPENDS_ON, RELATED_TO)
- vector_id references to L2 Insights (if available)

Usage:
    python scripts/setup_test_graph.py --setup     # Create test data
    python scripts/setup_test_graph.py --cleanup   # Remove test data
    python scripts/setup_test_graph.py --verify    # Verify test data exists

Story 4.7: Integration Testing mit BMAD-BMM Use Cases
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from mcp_server.db.connection import get_connection
from mcp_server.db.graph import add_node, add_edge, get_node_by_name

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =============================================================================
# Test Data Definitions
# =============================================================================

# Test nodes for all use cases (AC 4.7.1, 4.7.2, 4.7.3, 4.7.4)
TEST_NODES: list[dict[str, Any]] = [
    # Use Case 1: Architecture Check (AC-4.7.1)
    {"label": "Requirement", "name": "High Volume Requirement", "properties": {"priority": "high", "type": "nfr"}},
    {"label": "Technology", "name": "PostgreSQL", "properties": {"type": "database", "version": "16"}},

    # Use Case 2: Risk Analysis (AC-4.7.2)
    {"label": "Project", "name": "Projekt A", "properties": {"status": "active", "team_size": 5}},
    {"label": "Technology", "name": "Stripe API", "properties": {"type": "payment", "version": "v2023"}},

    # Use Case 3: Knowledge Harvesting (AC-4.7.3)
    # "Neues Projekt" and "FastAPI" will be created dynamically during tests

    # Additional nodes for Performance Tests (AC-4.7.4)
    {"label": "Project", "name": "Projekt B", "properties": {"status": "completed", "team_size": 3}},
    {"label": "Technology", "name": "FastAPI", "properties": {"type": "framework", "version": "0.100"}},
    {"label": "Technology", "name": "Redis", "properties": {"type": "cache", "version": "7.0"}},
    {"label": "Technology", "name": "pgvector", "properties": {"type": "extension", "version": "0.5"}},
    {"label": "Error", "name": "Connection Timeout", "properties": {"severity": "high", "frequency": "occasional"}},
    {"label": "Solution", "name": "Retry with Backoff", "properties": {"effectiveness": "high"}},
    {"label": "Client", "name": "Acme Corp", "properties": {"industry": "fintech", "since": "2023"}},
    {"label": "Technology", "name": "OpenAI API", "properties": {"type": "ai", "version": "v1"}},
    {"label": "Requirement", "name": "Low Latency", "properties": {"priority": "high", "target_ms": 50}},
    {"label": "Solution", "name": "Connection Pooling", "properties": {"effectiveness": "high"}},
]

# Test edges for all use cases
TEST_EDGES: list[dict[str, Any]] = [
    # Use Case 1: Architecture Check (AC-4.7.1)
    {"source": "High Volume Requirement", "target": "PostgreSQL", "relation": "SOLVED_BY", "weight": 0.9},

    # Use Case 2: Risk Analysis (AC-4.7.2)
    {"source": "Projekt A", "target": "Stripe API", "relation": "USES", "weight": 0.95},

    # Additional edges for Performance + Path Testing (AC-4.7.4)
    {"source": "Projekt A", "target": "FastAPI", "relation": "USES", "weight": 0.8},
    {"source": "Projekt A", "target": "PostgreSQL", "relation": "USES", "weight": 0.9},
    {"source": "Projekt B", "target": "PostgreSQL", "relation": "USES", "weight": 0.85},
    {"source": "Projekt B", "target": "Redis", "relation": "USES", "weight": 0.7},
    {"source": "Connection Timeout", "target": "Retry with Backoff", "relation": "SOLVED_BY", "weight": 0.85},
    {"source": "Acme Corp", "target": "Projekt A", "relation": "COMMISSIONED", "weight": 1.0},
    {"source": "Acme Corp", "target": "Projekt B", "relation": "COMMISSIONED", "weight": 1.0},
    {"source": "PostgreSQL", "target": "pgvector", "relation": "DEPENDS_ON", "weight": 0.7},
    {"source": "FastAPI", "target": "PostgreSQL", "relation": "DEPENDS_ON", "weight": 0.6},
    {"source": "Low Latency", "target": "Redis", "relation": "SOLVED_BY", "weight": 0.8},
    {"source": "Low Latency", "target": "Connection Pooling", "relation": "SOLVED_BY", "weight": 0.9},
    {"source": "Projekt A", "target": "OpenAI API", "relation": "USES", "weight": 0.75},
    {"source": "Connection Timeout", "target": "Connection Pooling", "relation": "SOLVED_BY", "weight": 0.8},
]

# Test node names for cleanup (includes dynamically created nodes)
TEST_NODE_NAMES = [node["name"] for node in TEST_NODES] + ["Neues Projekt"]


def setup_test_graph() -> dict[str, int]:
    """
    Create test graph data for integration testing.

    Returns:
        Dict with counts: {"nodes_created": int, "edges_created": int}
    """
    logger.info("Setting up test graph data...")

    nodes_created = 0
    edges_created = 0

    # Create nodes
    for node_data in TEST_NODES:
        try:
            import json
            result = add_node(
                label=node_data["label"],
                name=node_data["name"],
                properties=json.dumps(node_data.get("properties", {})),
                vector_id=node_data.get("vector_id")
            )

            if result["created"]:
                nodes_created += 1
                logger.info(f"Created node: {node_data['name']} (label={node_data['label']})")
            else:
                logger.info(f"Node already exists: {node_data['name']}")

        except Exception as e:
            logger.error(f"Failed to create node {node_data['name']}: {e}")

    # Create edges
    for edge_data in TEST_EDGES:
        try:
            # Get node IDs
            source_node = get_node_by_name(edge_data["source"])
            target_node = get_node_by_name(edge_data["target"])

            if not source_node:
                logger.warning(f"Source node not found: {edge_data['source']}")
                continue
            if not target_node:
                logger.warning(f"Target node not found: {edge_data['target']}")
                continue

            result = add_edge(
                source_id=source_node["id"],
                target_id=target_node["id"],
                relation=edge_data["relation"],
                weight=edge_data.get("weight", 1.0),
                properties="{}"
            )

            if result["created"]:
                edges_created += 1
                logger.info(f"Created edge: {edge_data['source']} --[{edge_data['relation']}]--> {edge_data['target']}")
            else:
                logger.info(f"Edge already exists: {edge_data['source']} -> {edge_data['target']}")

        except Exception as e:
            logger.error(f"Failed to create edge {edge_data['source']} -> {edge_data['target']}: {e}")

    logger.info(f"Test graph setup complete: {nodes_created} nodes created, {edges_created} edges created")

    return {"nodes_created": nodes_created, "edges_created": edges_created}


def cleanup_test_graph() -> dict[str, int]:
    """
    Remove test graph data (idempotent - can be run multiple times).

    Returns:
        Dict with counts: {"nodes_deleted": int, "edges_deleted": int}
    """
    logger.info("Cleaning up test graph data...")

    nodes_deleted = 0
    edges_deleted = 0

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get node IDs for test nodes
            node_ids = []
            for name in TEST_NODE_NAMES:
                cursor.execute(
                    "SELECT id FROM nodes WHERE name = %s;",
                    (name,)
                )
                result = cursor.fetchone()
                if result:
                    node_ids.append(str(result["id"]))

            if node_ids:
                # Delete edges connected to test nodes (CASCADE handles this, but explicit is safer)
                placeholders = ",".join(["%s::uuid" for _ in node_ids])
                cursor.execute(
                    f"DELETE FROM edges WHERE source_id IN ({placeholders}) OR target_id IN ({placeholders});",
                    node_ids + node_ids
                )
                edges_deleted = cursor.rowcount
                logger.info(f"Deleted {edges_deleted} edges")

                # Delete test nodes
                cursor.execute(
                    f"DELETE FROM nodes WHERE id IN ({placeholders});",
                    node_ids
                )
                nodes_deleted = cursor.rowcount
                logger.info(f"Deleted {nodes_deleted} nodes")

            conn.commit()

    except Exception as e:
        logger.error(f"Failed to cleanup test graph: {e}")
        raise

    logger.info(f"Test graph cleanup complete: {nodes_deleted} nodes deleted, {edges_deleted} edges deleted")

    return {"nodes_deleted": nodes_deleted, "edges_deleted": edges_deleted}


def verify_test_graph() -> dict[str, Any]:
    """
    Verify that test graph data exists.

    Returns:
        Dict with verification results
    """
    logger.info("Verifying test graph data...")

    results = {
        "nodes_found": 0,
        "edges_found": 0,
        "missing_nodes": [],
        "verification_passed": False,
    }

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Count test nodes
            for node_data in TEST_NODES:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM nodes WHERE name = %s;",
                    (node_data["name"],)
                )
                result = cursor.fetchone()
                if result and result["count"] > 0:
                    results["nodes_found"] += 1
                else:
                    results["missing_nodes"].append(node_data["name"])

            # Count test edges (approximate - by relation types)
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM edges e
                JOIN nodes n1 ON e.source_id = n1.id
                JOIN nodes n2 ON e.target_id = n2.id
                WHERE n1.name IN %s AND n2.name IN %s;
                """,
                (tuple(TEST_NODE_NAMES), tuple(TEST_NODE_NAMES))
            )
            result = cursor.fetchone()
            results["edges_found"] = result["count"] if result else 0

    except Exception as e:
        logger.error(f"Failed to verify test graph: {e}")
        results["error"] = str(e)
        return results

    # Check if verification passed
    expected_nodes = len(TEST_NODES)
    expected_edges = len(TEST_EDGES)

    results["expected_nodes"] = expected_nodes
    results["expected_edges"] = expected_edges
    results["verification_passed"] = (
        results["nodes_found"] >= expected_nodes * 0.9 and  # 90% tolerance
        results["edges_found"] >= expected_edges * 0.9
    )

    if results["verification_passed"]:
        logger.info(f"Verification PASSED: {results['nodes_found']}/{expected_nodes} nodes, {results['edges_found']}/{expected_edges} edges")
    else:
        logger.warning(f"Verification FAILED: {results['nodes_found']}/{expected_nodes} nodes, {results['edges_found']}/{expected_edges} edges")
        if results["missing_nodes"]:
            logger.warning(f"Missing nodes: {results['missing_nodes']}")

    return results


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Test Graph Setup Script for Story 4.7 Integration Testing"
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Create test graph data"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove test graph data"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify test graph data exists"
    )

    args = parser.parse_args()

    if not any([args.setup, args.cleanup, args.verify]):
        parser.print_help()
        sys.exit(1)

    if args.cleanup:
        cleanup_test_graph()

    if args.setup:
        setup_test_graph()

    if args.verify:
        results = verify_test_graph()
        if not results["verification_passed"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
