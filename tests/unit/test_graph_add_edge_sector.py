"""
Unit Tests for Auto-Classification in graph_add_edge

Tests that memory sector classification is automatically applied
when creating edges via the graph_add_edge MCP tool.

Author: Epic 8 Implementation
Story: 8.3 - Auto-Classification on Edge Insert
"""

import pytest

from mcp_server.db.connection import get_connection
from mcp_server.tools.graph_add_edge import handle_graph_add_edge


class TestEmotionalEdgeClassification:
    """Test AC #2: Edges with emotional_valence are classified as emotional."""

    @pytest.mark.asyncio
    async def test_emotional_valence_positive(with_project_context):
        """Edge with positive emotional_valence should be classified as emotional."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "EXPERIENCED",
            "properties": {"emotional_valence": "positive"}
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "emotional"

    @pytest.mark.asyncio
    async def test_emotional_valence_negative(with_project_context):
        """Edge with negative emotional_valence should be classified as emotional."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "EXPERIENCED",
            "properties": {"emotional_valence": "negative"}
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "emotional"

    @pytest.mark.asyncio
    async def test_emotional_valence_neutral(with_project_context):
        """Edge with neutral emotional_valence should be classified as emotional."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "EXPERIENCED",
            "properties": {"emotional_valence": "neutral"}
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "emotional"


class TestEpisodicEdgeClassification:
    """Test AC #3: Edges with shared_experience are classified as episodic."""

    @pytest.mark.asyncio
    async def test_shared_experience_context(with_project_context):
        """Edge with context_type=shared_experience should be classified as episodic."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "PARTICIPATED_IN",
            "properties": {"context_type": "shared_experience"}
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "episodic"


class TestProceduralEdgeClassification:
    """Test AC #4: Edges with LEARNED/CAN_DO relations are classified as procedural."""

    @pytest.mark.asyncio
    async def test_learned_relation(with_project_context):
        """Edge with LEARNED relation should be classified as procedural."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "LEARNED"
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "procedural"

    @pytest.mark.asyncio
    async def test_can_do_relation(with_project_context):
        """Edge with CAN_DO relation should be classified as procedural."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "CAN_DO"
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "procedural"


class TestReflectiveEdgeClassification:
    """Test AC #5: Edges with REFLECTS/REFLECTS_ON/REALIZED relations are classified as reflective."""

    @pytest.mark.asyncio
    async def test_reflects_relation(with_project_context):
        """Edge with REFLECTS relation should be classified as reflective."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "REFLECTS"
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "reflective"

    @pytest.mark.asyncio
    async def test_reflects_on_relation(with_project_context):
        """Edge with REFLECTS_ON relation should be classified as reflective."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "REFLECTS_ON"
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "reflective"

    @pytest.mark.asyncio
    async def test_realized_relation(with_project_context):
        """Edge with REALIZED relation should be classified as reflective."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "REALIZED"
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "reflective"


class TestSemanticDefaultClassification:
    """Test AC #6: Edges matching no specific rule default to semantic."""

    @pytest.mark.asyncio
    async def test_semantic_default_no_properties(with_project_context):
        """Edge without special properties should default to semantic."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "KNOWS"
        })

        assert result["status"] == "success"
        assert result["memory_sector"] == "semantic"

    @pytest.mark.asyncio
    async def test_semantic_default_standard_relations(with_project_context):
        """Standard relations without special properties should be semantic."""
        for relation in ["USES", "SOLVES", "CREATED_BY", "RELATED_TO", "DEPENDS_ON"]:
            result = await handle_graph_add_edge({
                "source_name": f"Source_{relation}",
                "target_name": f"Target_{relation}",
                "relation": relation
            })

            assert result["status"] == "success"
            assert result["memory_sector"] == "semantic"


class TestMemorySectorInResponse:
    """Test AC #1: Response includes memory_sector field."""

    @pytest.mark.asyncio
    async def test_memory_sector_field_present(with_project_context):
        """Response should always include memory_sector field."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "USES"
        })

        assert "memory_sector" in result
        assert isinstance(result["memory_sector"], str)
        assert len(result["memory_sector"]) > 0

    @pytest.mark.asyncio
    async def test_memory_sector_lowercase(with_project_context):
        """memory_sector in response should always be lowercase."""
        result = await handle_graph_add_edge({
            "source_name": "TestSource",
            "target_name": "TestTarget",
            "relation": "EXPERIENCED",
            "properties": {"emotional_valence": "positive"}
        })

        assert result["memory_sector"] == result["memory_sector"].lower()


class TestEdgeUpdatePreservesClassification:
    """Test AC #8: Edge update with ON CONFLICT reclassifies based on new properties."""

    @pytest.mark.asyncio
    async def test_edge_update_reclassifies_sector(with_project_context):
        """Updating an edge with changed properties should reclassify memory_sector."""
        # Create initial edge as semantic
        result1 = await handle_graph_add_edge({
            "source_name": "UpdateTestSource_initial",
            "target_name": "UpdateTestTarget_initial",
            "relation": "EXPERIENCED"
        })

        assert result1["status"] == "success"
        assert result1["memory_sector"] == "semantic"

        # Verify database state after initial insert
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_sector FROM edges WHERE source_id = %s::uuid",
                (result1["source_id"],)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["memory_sector"] == "semantic", "Database should store 'semantic' sector"

        # Update same edge with emotional_valence
        result2 = await handle_graph_add_edge({
            "source_name": "UpdateTestSource_initial",
            "target_name": "UpdateTestTarget_initial",
            "relation": "EXPERIENCED",
            "properties": {"emotional_valence": "positive"}
        })

        assert result2["status"] == "success"
        # Note: created might be False if nodes already exist, but edge should be updated
        assert result2["memory_sector"] == "emotional"  # Reclassified!

        # Verify database state was actually updated (AC #8)
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_sector FROM edges WHERE source_id = %s::uuid",
                (result1["source_id"],)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["memory_sector"] == "emotional", "ON CONFLICT should update memory_sector in database"

    @pytest.mark.asyncio
    async def test_edge_update_from_emotional_to_semantic(with_project_context):
        """Updating edge and removing emotional property should reclassify to semantic."""
        # Create edge with emotional_valence
        result1 = await handle_graph_add_edge({
            "source_name": "ReverseTestSource",
            "target_name": "ReverseTestTarget",
            "relation": "EXPERIENCED",
            "properties": {"emotional_valence": "negative"}
        })

        assert result1["status"] == "success"
        assert result1["memory_sector"] == "emotional"

        # Verify database state after initial insert
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_sector FROM edges WHERE source_id = %s::uuid",
                (result1["source_id"],)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["memory_sector"] == "emotional", "Database should store 'emotional' sector"

        # Update same edge without emotional_valence
        result2 = await handle_graph_add_edge({
            "source_name": "ReverseTestSource",
            "target_name": "ReverseTestTarget",
            "relation": "EXPERIENCED"
        })

        assert result2["status"] == "success"
        assert result2["created"] is False
        assert result2["memory_sector"] == "semantic"  # Reclassified back to default

        # Verify database state was actually updated (AC #8)
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT memory_sector FROM edges WHERE source_id = %s::uuid",
                (result1["source_id"],)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["memory_sector"] == "semantic", "ON CONFLICT should reclassify to semantic in database"
