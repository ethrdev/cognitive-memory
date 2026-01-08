"""
Unit tests for graph_add_node - Epic 8 Story 8.4

Tests verify that graph_add_node creates nodes only (no edges) and that
the response does NOT include memory_sector field (AC #2).

If edge creation is added in the future, classification would be required (FR25).
"""

import pytest

from mcp_server.tools.graph_add_node import handle_graph_add_node


class TestGraphAddNodeNodeOnly:
    """
    Test suite verifying graph_add_node creates nodes only (no edges).

    Story 8.4: Auto-Classification on Node Insert
    AC #2: Node-only operation should NOT return memory_sector field
    """

    @pytest.mark.asyncio
    async def test_graph_add_node_response_has_no_memory_sector(self):
        """
        AC #2: graph_add_node response should NOT include memory_sector field.

        Given: A call to graph_add_node with valid parameters
        When: The node is created successfully
        Then: The response does NOT include a memory_sector field
        And: Backward compatibility is maintained (NFR5)
        """
        result = await handle_graph_add_node({
            "label": "TestLabel",
            "name": "TestNode_NoEdges",
            "properties": {"test": "data"}
        })

        # Verify success response
        assert result["status"] == "success"
        assert "node_id" in result
        assert "created" in result
        assert "label" in result
        assert "name" in result

        # AC #2: memory_sector field should NOT be present (node-only operation)
        assert "memory_sector" not in result, (
            "graph_add_node creates nodes only (no edges), "
            "so memory_sector should not be in response"
        )

    @pytest.mark.asyncio
    async def test_graph_add_node_with_properties_no_memory_sector(self):
        """
        AC #2: Even with properties, no memory_sector in response.

        Given: A call to graph_add_node with properties
        When: The node is created
        Then: Response still does NOT include memory_sector field
        And: No edge is created
        """
        result = await handle_graph_add_node({
            "label": "Project",  # Use standard label
            "name": "TestNodeWithProperties",
            "properties": {
                "emotional_valence": "positive",  # Property that would trigger emotional sector in edges
                "context_type": "shared_experience"
            }
        })

        # Verify success
        assert result["status"] == "success"

        # AC #2: No memory_sector in response (node-only operation)
        # Even though properties contain emotional/context data, no edges are created
        assert "memory_sector" not in result

    @pytest.mark.asyncio
    async def test_graph_add_node_minimal_response(self):
        """
        Verify graph_add_node response structure matches documented format.

        Given: A call to graph_add_node
        When: Node is created
        Then: Response contains only documented fields
        """
        result = await handle_graph_add_node({
            "label": "Project",
            "name": "MinimalResponseTest"
        })

        # Documented response fields (from graph_add_node.py lines 93-99)
        expected_fields = {"node_id", "created", "label", "name", "status"}

        # Verify exact field set (no extra fields like memory_sector)
        assert set(result.keys()) == expected_fields, (
            f"Response should only contain {expected_fields}, "
            f"but got: {set(result.keys())}"
        )

    @pytest.mark.asyncio
    async def test_graph_add_node_does_not_call_add_edge(self):
        """
        Verify graph_add_node does not create edges (implementation detail test).

        Given: The current graph_add_node implementation
        When: Examining the code
        Then: No call to add_edge() exists
        And: No edge creation occurs

        This test documents the current implementation behavior per Story 8.4 Dev Notes.
        If edge creation is added in the future, FR25 classification would be required.
        """
        # For now, verify no edge creation by checking response
        result = await handle_graph_add_node({
            "label": "Verification",
            "name": "NoEdgeCreated"
        })

        # If edges were created, response might include edge data
        # Current behavior: Node-only, no edge data
        assert "edge_id" not in result
        assert "memory_sector" not in result
        assert result["status"] == "success"


class TestGraphAddNodeBackwardCompatibility:
    """
    Test suite verifying backward compatibility (NFR5).

    Story 8.4: Auto-Classification on Node Insert
    AC #3: All existing behavior remains unchanged (NFR5)
    """

    @pytest.mark.asyncio
    async def test_graph_add_node_existing_behavior_preserved(self):
        """
        NFR5: Verify existing graph_add_node behavior is unchanged.

        Given: The current graph_add_node implementation
        When: Creating a node with standard parameters
        Then: Response format matches existing format
        And: No breaking changes to the API
        """
        result = await handle_graph_add_node({
            "label": "Technology",
            "name": "BackwardCompatibilityTest",
            "properties": {"version": "1.0"}
        })

        # Verify existing response structure is preserved
        assert isinstance(result, dict)
        assert result["status"] == "success"
        assert "node_id" in result
        assert isinstance(result["node_id"], str)
        assert "created" in result
        assert isinstance(result["created"], bool)
        assert "label" in result
        assert result["label"] == "Technology"
        assert "name" in result
        assert result["name"] == "BackwardCompatibilityTest"

        # NFR5: No new required fields added to response
        # (memory_sector is not present, which is correct for node-only)

    @pytest.mark.asyncio
    async def test_graph_add_node_idempotent_operation_unchanged(self):
        """
        Verify idempotent operation still works (existing behavior).

        Given: An existing node in the database
        When: Calling graph_add_node with same name
        Then: Existing node is returned (created=False)
        And: No duplicate nodes are created
        """
        import uuid
        node_name = f"IdempotentTest_{uuid.uuid4().hex[:8]}"

        # First call - should create
        result1 = await handle_graph_add_node({
            "label": "Technology",  # Use standard label
            "name": node_name,
            "properties": {"version": "1"}
        })

        assert result1["status"] == "success"
        assert result1["created"] is True

        # Second call - should find existing (idempotent)
        result2 = await handle_graph_add_node({
            "label": "Technology",
            "name": node_name,
            "properties": {"version": "2"}  # Different properties
        })

        assert result2["status"] == "success"
        assert result2["created"] is False  # Found existing
        assert result2["node_id"] == result1["node_id"]  # Same node

        # No memory_sector in either response (node-only operation)
        assert "memory_sector" not in result1
        assert "memory_sector" not in result2
