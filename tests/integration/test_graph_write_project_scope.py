"""
Integration tests for Graph Write Operations with Project Scoping.

Story 11.5.1: Graph Write Operations (graph_add_node, graph_add_edge)

Tests that nodes and edges are automatically scoped to projects,
nodes with same name in different projects coexist, and RLS blocks
cross-project writes.
"""

from __future__ import annotations

import pytest

from mcp_server.db.graph import add_node, add_edge, get_or_create_node
from mcp_server.middleware.context import clear_context, set_project_id


class TestAddNodeProjectScoping:
    """Test add_node() includes project_id in INSERT and ON CONFLICT."""

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_add_node_includes_project_id(self, conn):
        """Test that add_node() creates nodes with project_id from context."""
        # Set project context (simulating TenantMiddleware)
        set_project_id("test_isolated")

        # Create a node
        result = await add_node(label="Entity", name="TestNode1")

        # Verify project_id is in response
        assert "project_id" in result
        assert result["project_id"] == "test_isolated"
        assert result["created"] is True
        assert result["name"] == "TestNode1"

        # Verify node was created with correct project_id in database
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT project_id, label, name
            FROM nodes
            WHERE name = %s
            """,
            (result["name"],)
        )
        node = cursor.fetchone()

        assert node is not None
        assert node["project_id"] == "test_isolated"
        assert node["label"] == "Entity"
        assert node["name"] == "TestNode1"

        # Clean up
        clear_context()

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_add_node_uses_composite_key_on_conflict(self, conn):
        """Test that add_node() uses (project_id, name) composite key for upsert."""
        # Create node in project aa
        set_project_id("test_isolated")
        result1 = await add_node(label="Entity", name="SharedName")
        assert result1["created"] is True
        assert result1["project_id"] == "test_isolated"

        # Create node with same name in different project test_shared
        # This should succeed with a different project_id
        set_project_id("test_shared")
        result2 = await add_node(label="Entity", name="SharedName")
        assert result2["created"] is True  # NEW node, not update
        assert result2["project_id"] == "test_shared"
        assert result2["node_id"] != result1["node_id"]  # Different IDs

        # Verify two separate nodes exist
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, project_id, name
            FROM nodes
            WHERE name = %s
            ORDER BY project_id
            """,
            ("SharedName",)
        )
        nodes = cursor.fetchall()

        assert len(nodes) == 2
        assert nodes[0]["project_id"] == "test_isolated"
        assert nodes[1]["project_id"] == "test_shared"
        assert nodes[0]["id"] != nodes[1]["id"]

        # Clean up
        clear_context()

    @pytest.mark.asyncio
    @pytest.mark.P1
    async def test_add_node_upsert_within_same_project(self, conn):
        """Test that add_node() updates existing node within same project."""
        set_project_id("test_isolated")

        # Create initial node
        result1 = await add_node(label="Entity", name="UpdateTest")
        assert result1["created"] is True

        # Upsert with same project_id
        result2 = await add_node(label="Updated", name="UpdateTest")
        assert result2["created"] is False  # Updated, not new
        assert result2["project_id"] == "test_isolated"
        assert result2["node_id"] == result1["node_id"]  # Same ID

        # Verify only one node exists
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM nodes WHERE name = %s AND project_id = %s",
            ("UpdateTest", "test_isolated")
        )
        count = cursor.fetchone()["count"]
        assert count == 1

        # Clean up
        clear_context()


class TestAddEdgeProjectScoping:
    """Test add_edge() includes project_id in INSERT and ON CONFLICT."""

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_add_edge_includes_project_id(self, conn):
        """Test that add_edge() creates edges with project_id from context."""
        set_project_id("test_isolated")

        # Create two nodes
        node1 = await add_node(label="Entity", name="Node1")
        node2 = await add_node(label="Entity", name="Node2")

        # Create edge
        result = await add_edge(
            source_id=node1["node_id"],
            target_id=node2["node_id"],
            relation="RELATES_TO"
        )

        # Verify project_id is in response
        assert "project_id" in result
        assert result["project_id"] == "test_isolated"
        assert result["created"] is True

        # Verify edge was created with correct project_id in database
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT project_id, source_id, target_id, relation
            FROM edges
            WHERE id = %s
            """,
            (result["edge_id"],)
        )
        edge = cursor.fetchone()

        assert edge is not None
        assert edge["project_id"] == "test_isolated"
        assert str(edge["source_id"]) == node1["node_id"]
        assert str(edge["target_id"]) == node2["node_id"]
        assert edge["relation"] == "RELATES_TO"

        # Clean up
        clear_context()

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_add_edge_uses_composite_key_on_conflict(self, conn):
        """Test that add_edge() uses (project_id, source_id, target_id, relation) composite key."""
        set_project_id("test_isolated")

        # Create nodes
        node1 = await add_node(label="Entity", name="EdgeTest1")
        node2 = await add_node(label="Entity", name="EdgeTest2")

        # Create edge
        result1 = await add_edge(
            source_id=node1["node_id"],
            target_id=node2["node_id"],
            relation="RELATES_TO"
        )
        assert result1["created"] is True
        assert result1["project_id"] == "test_isolated"

        # Upsert with same project_id
        result2 = await add_edge(
            source_id=node1["node_id"],
            target_id=node2["node_id"],
            relation="RELATES_TO",
            weight=0.5
        )
        assert result2["created"] is False  # Updated, not new
        assert result2["project_id"] == "test_isolated"
        assert result2["edge_id"] == result1["edge_id"]  # Same ID
        assert result2["weight"] == 0.5

        # Clean up
        clear_context()


class TestGetOrCreateNodeProjectScoping:
    """Test get_or_create_node() returns project_id."""

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_get_or_create_node_returns_project_id(self, conn):
        """Test that get_or_create_node() returns project_id."""
        set_project_id("test_isolated")

        # Create new node
        result = await get_or_create_node(name="AutoCreateNode")

        # Verify project_id is in response
        assert "project_id" in result
        assert result["project_id"] == "test_isolated"
        assert result["created"] is True

        # Get existing node
        result2 = await get_or_create_node(name="AutoCreateNode")
        assert result2["project_id"] == "test_isolated"
        assert result2["created"] is False
        assert result2["node_id"] == result["node_id"]

        # Clean up
        clear_context()


class TestRLSCrossProjectWritePrevention:
    """Test RLS WITH CHECK prevents cross-project writes."""

    @pytest.mark.asyncio
    @pytest.mark.P1
    async def test_rls_blocks_cross_project_edge_write(self, conn):
        """Test that RLS WITH CHECK blocks edge writes to nodes outside project scope."""
        # Create node in test_isolated
        set_project_id("test_isolated")
        isolated_node = await add_node(label="Entity", name="IsolatedNode")

        # Try to create edge from test_shared to test_isolated node
        # This should fail because the edge would have project_id=test_shared
        # but reference a node owned by test_isolated
        set_project_id("test_shared")

        # Create a node in test_shared for source
        shared_node = await add_node(label="Entity", name="SharedNode")

        # Try to create edge to isolated node
        # RLS WITH CHECK should block this because:
        # - Edge would have project_id=test_shared
        # - Target node has project_id=test_isolated
        # - RLS policy requires edge.project_id = node.project_id for all referenced nodes
        with pytest.raises(Exception) as exc_info:
            await add_edge(
                source_id=shared_node["node_id"],
                target_id=isolated_node["node_id"],
                relation="ATTEMPTS_CROSS_PROJECT"
            )

        # Error should mention RLS or permission
        error_msg = str(exc_info.value).lower()
        assert "rls" in error_msg or "permission" in error_msg or "new row violates" in error_msg

        # Clean up
        clear_context()


class TestProjectScopingIntegration:
    """Integration tests for complete project-scoped graph operations."""

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_nodes_with_same_name_in_different_projects_coexist(self, conn):
        """Test AC: Nodes with same name in different projects coexist."""
        # Create node in project aa
        set_project_id("test_isolated")
        node_aa = await add_node(label="Customer", name="Customer")

        # Create node with same name in different project
        set_project_id("test_shared")
        node_ab = await add_node(label="Customer", name="Customer")

        # Verify they are different nodes
        assert node_aa["node_id"] != node_ab["node_id"]
        assert node_aa["project_id"] == "test_isolated"
        assert node_ab["project_id"] == "test_shared"

        # Verify both exist in database
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM nodes WHERE name = %s",
            ("Customer",)
        )
        count = cursor.fetchone()["count"]
        assert count == 2

        # Clean up
        clear_context()

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_edges_scoped_to_project_id(self, conn):
        """Test AC: Edges are scoped to project_id."""
        # Create nodes and edges in two projects
        set_project_id("test_isolated")
        node_aa_1 = await add_node(label="Entity", name="AA_Node1")
        node_aa_2 = await add_node(label="Entity", name="AA_Node2")
        edge_aa = await add_edge(
            source_id=node_aa_1["node_id"],
            target_id=node_aa_2["node_id"],
            relation="RELATES_TO"
        )

        set_project_id("test_shared")
        node_ab_1 = await add_node(label="Entity", name="AB_Node1")
        node_ab_2 = await add_node(label="Entity", name="AB_Node2")
        edge_ab = await add_edge(
            source_id=node_ab_1["node_id"],
            target_id=node_ab_2["node_id"],
            relation="RELATES_TO"
        )

        # Verify edges have correct project_ids
        assert edge_aa["project_id"] == "test_isolated"
        assert edge_ab["project_id"] == "test_shared"

        # Verify edges are separate
        assert edge_aa["edge_id"] != edge_ab["edge_id"]

        # Clean up
        clear_context()

    @pytest.mark.asyncio
    @pytest.mark.P0
    async def test_upsert_behavior_with_project_scope(self, conn):
        """Test AC: Upsert behavior with project scope."""
        # Create node in test_isolated
        set_project_id("test_isolated")
        result1 = await add_node(label="Entity", name="UpsertTest")
        assert result1["created"] is True

        # Same project: upsert (update existing)
        result2 = await add_node(label="Updated", name="UpsertTest")
        assert result2["created"] is False
        assert result2["node_id"] == result1["node_id"]

        # Different project: create new
        set_project_id("test_shared")
        result3 = await add_node(label="Entity", name="UpsertTest")
        assert result3["created"] is True  # NEW node, not update
        assert result3["node_id"] != result1["node_id"]

        # Clean up
        clear_context()
