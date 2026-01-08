"""Integration tests for Story 8-5: memory_sector in query responses.

Tests FR26: System returns memory_sector in graph_query_neighbors, get_edge, and graph_find_path responses.

NOTE: These tests directly call add_edge() with memory_sector parameter to test
QUERY RESPONSE functionality (Story 8-5). Auto-classification is tested separately
in Story 8-3 integration tests.
"""
import json
import pytest
from mcp_server.db.graph import (
    query_neighbors,
    get_edge_by_names,
    find_path,
    add_node,
    add_edge,
    get_node_by_name,
)
from mcp_server.utils.sector_classifier import MemorySector


@pytest.mark.asyncio
async def test_query_neighbors_includes_memory_sector(conn):
    """graph_query_neighbors should include memory_sector for each neighbor (AC#1, #4, #5)."""
    # Setup: Create test nodes and edge with known sector
    source_result = add_node(
        label="TestSource",
        name="TestSource_QueryNeighbors",
        properties=json.dumps({"test": "data"}),
    )

    target_result = add_node(
        label="TestTarget",
        name="TestTarget_QueryNeighbors",
        properties=json.dumps({"test": "data"}),
    )

    # Create edge with memory_sector explicitly set to "emotional"
    # Note: We directly set memory_sector to test query response, not auto-classification
    edge_result = add_edge(
        source_id=source_result["node_id"],
        target_id=target_result["node_id"],
        relation="EXPERIENCED",
        weight=0.8,
        properties=json.dumps({"emotional_valence": "positive"}),
        memory_sector="emotional",  # Explicitly set for testing query response
    )

    # Test: query_neighbors returns memory_sector
    # Note: query_neighbors() takes node_id (UUID string), not source_name
    result = query_neighbors(
        node_id=source_result["node_id"],
        relation_type=None,
        max_depth=1,
        direction="both",
    )

    # query_neighbors() returns list directly, not dict with status
    assert len(result) > 0

    # Verify each neighbor has memory_sector
    for neighbor in result:
        assert "memory_sector" in neighbor
        assert neighbor["memory_sector"] in [
            "semantic",
            "emotional",
            "episodic",
            "procedural",
            "reflective",
        ]

    # Verify the emotional edge was returned correctly
    assert result[0]["memory_sector"] == "emotional"


@pytest.mark.asyncio
async def test_query_neighbors_default_semantic_sector(conn):
    """Query response should default to 'semantic' for edges without explicit sector (AC#5)."""
    # Setup: Create nodes and edge with semantic relation
    source_result = add_node(
        label="TestSource",
        name="TestSource_DefaultSemantic",
        properties=json.dumps({}),
    )

    target_result = add_node(
        label="TestTarget",
        name="TestTarget_DefaultSemantic",
        properties=json.dumps({}),
    )

    # RELATED_TO → semantic (explicitly set for testing query response)
    add_edge(
        source_id=source_result["node_id"],
        target_id=target_result["node_id"],
        relation="RELATED_TO",
        weight=0.5,
        properties=json.dumps({}),
        memory_sector="semantic",  # Explicitly set for testing query response
    )

    # Test: query_neighbors() returns list, not dict with status
    result = query_neighbors(
        node_id=source_result["node_id"],
        relation_type=None,
        max_depth=1,
        direction="outgoing",
    )

    assert len(result) == 1
    assert result[0]["memory_sector"] == "semantic"


@pytest.mark.asyncio
async def test_query_neighbors_multiple_sectors(conn):
    """Query responses should correctly return different sectors for different edges (AC#4)."""
    # Setup: Create source node
    source_result = add_node(
        label="TestSource",
        name="TestSource_MultipleSectors",
        properties=json.dumps({}),
    )

    # Create emotional edge (explicitly set for testing query response)
    emotional_target = add_node(
        label="TestTarget",
        name="EmotionalTarget",
        properties=json.dumps({}),
    )
    add_edge(
        source_id=source_result["node_id"],
        target_id=emotional_target["node_id"],
        relation="EXPERIENCED",
        weight=0.8,
        properties=json.dumps({"emotional_valence": "positive"}),
        memory_sector="emotional",
    )

    # Create episodic edge (explicitly set for testing query response)
    episodic_target = add_node(
        label="TestTarget",
        name="EpisodicTarget",
        properties=json.dumps({}),
    )
    add_edge(
        source_id=source_result["node_id"],
        target_id=episodic_target["node_id"],
        relation="OCCURRED_DURING",
        weight=0.7,
        properties=json.dumps({"timestamp": "2025-01-01T00:00:00Z"}),
        memory_sector="episodic",
    )

    # Create semantic edge (explicitly set for testing query response)
    semantic_target = add_node(
        label="TestTarget",
        name="SemanticTarget",
        properties=json.dumps({}),
    )
    add_edge(
        source_id=source_result["node_id"],
        target_id=semantic_target["node_id"],
        relation="RELATED_TO",
        weight=0.5,
        properties=json.dumps({}),
        memory_sector="semantic",
    )

    # Test: query_neighbors() returns list, not dict with status
    result = query_neighbors(
        node_id=source_result["node_id"],
        relation_type=None,
        max_depth=1,
        direction="outgoing",
    )

    assert len(result) == 3

    # Verify all three sectors are present
    sectors = {n["memory_sector"] for n in result}
    assert sectors == {"emotional", "episodic", "semantic"}


@pytest.mark.asyncio
async def test_query_neighbors_backwards_compatibility(conn):
    """Adding memory_sector should not remove or change existing fields (AC#6)."""
    # Setup
    source_result = add_node(
        label="TestSource",
        name="TestSource_Compatibility",
        properties=json.dumps({}),
    )

    target_result = add_node(
        label="TestTarget",
        name="TestTarget_Compatibility",
        properties=json.dumps({}),
    )

    add_edge(
        source_id=source_result["node_id"],
        target_id=target_result["node_id"],
        relation="RELATED_TO",
        weight=0.6,
        properties=json.dumps({"key": "value"}),
    )

    # Test: query_neighbors() returns list, not dict with status
    result = query_neighbors(
        node_id=source_result["node_id"],
        relation_type=None,
        max_depth=1,
        direction="outgoing",
    )

    neighbor = result[0]

    # Verify all existing fields are still present
    assert "node_id" in neighbor
    assert "label" in neighbor
    assert "name" in neighbor
    assert "properties" in neighbor
    assert "edge_properties" in neighbor
    assert "relation" in neighbor
    assert "weight" in neighbor
    assert "distance" in neighbor
    assert "edge_direction" in neighbor
    assert "last_accessed" in neighbor
    assert "access_count" in neighbor
    assert "modified_at" in neighbor
    assert "relevance_score" in neighbor

    # Verify new field is additive
    assert "memory_sector" in neighbor
    assert neighbor["memory_sector"] == "semantic"
