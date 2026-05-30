"""
Integration Test for Graph Operations Flow.

Tests the complete graph workflow:
1. Add nodes → 2. Add edges → 3. Query path → 4. Delete edge

Story TD-2.1.4: Integration Tests
v3 CKG Component 0: Graph Operations
"""

from __future__ import annotations

import pytest

from mcp_server.db.graph import (
    add_node,
    add_edge,
    delete_edge,
    find_path,
    fuzzy_search_node_by_name,
    get_node_by_name,
)
from mcp_server.db.connection import get_connection_with_project_context
from mcp_server.middleware.context import clear_context, set_project_id


@pytest.mark.asyncio
@pytest.mark.P0
async def test_graph_create_and_query_path(conn):
    """
    Integration Test: Create nodes and query path between them.

    Tests:
    - Node creation with project scoping
    - Path finding algorithm (Neo4j/Cypher style)
    """
    set_project_id("test-isolated")

    # Create source and target nodes
    source_result = await add_node(label="Person", name="Alice")
    assert source_result["created"] is True
    source_id = source_result["node_id"]

    target_result = await add_node(label="Person", name="Bob")
    assert target_result["created"] is True
    target_id = target_result["node_id"]

    # Create edge
    edge_result = await add_edge(
        source_id=source_id,
        target_id=target_id,
        relation="KNOWS"
    )
    assert edge_result["created"] is True

    # Query path
    path_result = await find_path(
        source_name="Alice",
        target_name="Bob",
        relation_types=["KNOWS"]
    )

    # Verify path was found
    assert path_result is not None
    assert len(path_result["path"]) > 0
    assert path_result["path"][0]["source_name"] == "Alice"
    assert path_result["path"][-1]["target_name"] == "Bob"

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_graph_fuzzy_search_and_update(conn):
    """
    Integration Test: Fuzzy search and update node properties.

    Tests:
    - Fuzzy search with pg_trgm
    - Property merge with vector_id
    """
    set_project_id("test-isolated")

    # Create node with properties
    initial_result = await add_node(
        label="Technology",
        name="Python",
        properties={"version": "3.9"}
    )
    assert initial_result["created"] is True
    node_id = initial_result["node_id"]

    # Fuzzy search for similar node
    search_result = await fuzzy_search_node_by_name(
        name="Pytho",  # Typo for testing fuzzy search
        limit=5
    )

    # Should find the node with typo tolerance
    assert len(search_result) > 0

    # Update node with new properties and vector_id
    update_result = await fuzzy_search_node_by_name(
        name="Python",
        new_properties={"version": "3.11", "status": "active"},
        vector_id=123
    )

    # Verify update was successful
    assert update_result["id"] == node_id
    assert update_result["name"] == "Python"
    assert update_result["properties"]["version"] == "3.11"
    assert update_result["properties"]["status"] == "active"

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_graph_delete_edge_with_verification(conn):
    """
    Integration Test: Delete edge with verification.

    Tests:
    - Edge deletion
    - Verification that edge is removed
    """
    set_project_id("test-isolated")

    # Create nodes and edge
    source_result = await add_node(label="Person", name="Charlie")
    target_result = await add_node(label="Person", name="Dana")
    source_id = source_result["node_id"]
    target_id = target_result["node_id"]

    edge_result = await add_edge(
        source_id=source_id,
        target_id=target_id,
        relation="KNOWS"
    )
    edge_id = edge_result["edge_id"]
    assert edge_result["created"] is True

    # Delete edge
    delete_result = await delete_edge(
        edge_id=edge_id,
        consent_given=True  # Allow deletion of non-constitutive edge
    )

    # Verify deletion
    assert delete_result["deleted"] is True
    assert delete_result["edge_id"] == edge_id

    # Verify edge is actually gone
    from mcp_server.db.graph import get_edge_by_id
    deleted_edge = await get_edge_by_id(edge_id)
    assert deleted_edge is None, "Edge should be deleted"

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_graph_multi_hop_relationship(conn):
    """
    Integration Test: Multi-hop relationship query.

    Tests:
    - Path finding through intermediate nodes
    - Project-scoped query results
    """
    set_project_id("test-isolated")

    # Create three nodes in a chain: A → B → C
    node_a = await add_node(label="City", name="Zurich")
    node_b = await add_node(label="City", name="Munich")
    node_c = await add_node(label="City", name="Frankfurt")

    await add_edge(
        source_id=node_a["node_id"],
        target_id=node_b["node_id"],
        relation="CONNECTED_TO"
    )

    await add_edge(
        source_id=node_b["node_id"],
        target_id=node_c["node_id"],
        relation="CONNECTED_TO"
    )

    # Query path from A to C (should go through B)
    path_result = await find_path(
        source_name="Zurich",
        target_name="Frankfurt",
        relation_types=["CONNECTED_TO"]
    )

    # Verify multi-hop path
    assert path_result is not None
    assert len(path_result["path"]) == 3
    assert path_result["path"][0]["source_name"] == "Zurich"
    assert path_result["path"][1]["target_name"] == "Munich"
    assert path_result["path"][2]["target_name"] == "Frankfurt"

    # Verify all nodes in path have same project_id
    for node_info in path_result["path"]:
        assert node_info["project_id"] == "test-isolated"

    clear_context()
