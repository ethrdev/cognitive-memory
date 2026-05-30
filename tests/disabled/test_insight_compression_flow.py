"""
Integration Test for Insight Compression Flow (EP-3).

Tests the complete flow:
1. Store raw dialogue → 2. Compress to L2 insight → 3. Verify history

Story TD-2.1.4: Integration Tests
EP-3: History-on-Mutation Pattern
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from mcp_server.db.connection import get_connection_with_project_context
from mcp_server.db.raw_dialogue import store_raw_dialogue
from mcp_server.db.insights import compress_to_l2_insight, get_insight_by_id, get_insight_history
from mcp_server.middleware.context import clear_context, set_project_id


@pytest.mark.asyncio
@pytest.mark.P0
async def test_insight_compression_full_flow(conn):
    """
    Integration Test: Complete insight compression flow.

    AC-5: Atomic History - History entry is written in same
    transaction as compression.
    """
    # Arrange - Set project context
    set_project_id("test-isolated")

    # Step 1: Store raw dialogue
    dialogue_result = await store_raw_dialogue(
        content="Test dialogue for compression",
        actor="ethr",
        source_type="user_input",
        metadata={"test_key": "test_value"}
    )
    assert dialogue_result["success"] is True
    dialogue_id = dialogue_result["dialogue_id"]

    # Step 2: Compress to L2 insight
    compression_result = await compress_to_l2_insight(
        source_ids=[dialogue_id],
        actor="I/O",
        reason="Integration test for insight compression"
    )
    assert compression_result["success"] is True
    insight_id = compression_result["insight_id"]

    # Step 3: Verify L2 insight was created
    created_insight = await get_insight_by_id(insight_id)
    assert created_insight is not None
    assert created_insight["io_category"] == "shared"
    assert "compression" in created_insight["content"].lower()

    # Step 4: Verify history entry exists
    history = await get_insight_history(insight_id, limit=5)
    assert len(history) > 0

    # Verify history includes source dialogue reference
    source_ref_found = any(
        entry["source_dialogue_ids"]
        and dialogue_id in entry["source_dialogue_ids"]
        for entry in history
    )
    assert source_ref_found, "History should reference source dialogue"

    # Verify history entry includes compression reason
    compression_entry = next(
        (h for h in history if h["action"] == "compress_to_l2"),
        None
    )
    assert compression_entry is not None
    assert compression_entry["reason"] == "Integration test for insight compression"

    # Clean up
    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_insight_compression_with_tags(conn):
    """
    Integration Test: Insight compression with tags.

    AC-5: Tags are preserved through compression.
    """
    set_project_id("test-isolated")

    # Store raw dialogue with metadata
    dialogue_result = await store_raw_dialogue(
        content="Dialogue about technical concepts",
        actor="ethr",
        source_type="user_input",
        metadata={"domain": "technical"}
    )
    dialogue_id = dialogue_result["dialogue_id"]

    # Compress with tags
    compression_result = await compress_to_l2_insight(
        source_ids=[dialogue_id],
        actor="I/O",
        reason="Compression with tags test",
        tags=["technical", "documentation"]
    )
    insight_id = compression_result["insight_id"]

    # Verify tags were preserved
    created_insight = await get_insight_by_id(insight_id)
    assert created_insight is not None
    assert set(created_insight.get("tags", [])) == {"technical", "documentation"}

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_insight_compression_memory_strength(conn):
    """
    Integration Test: Insight compression with custom memory strength.

    AC-5: memory_strength is preserved through compression.
    """
    set_project_id("test-isolated")

    # Store raw dialogue
    dialogue_result = await store_raw_dialogue(
        content="Important conversation",
        actor="ethr",
        source_type="user_input"
    )
    dialogue_id = dialogue_result["dialogue_id"]

    # Compress with high memory strength
    compression_result = await compress_to_l2_insight(
        source_ids=[dialogue_id],
        actor="I/O",
        reason="High importance memory",
        memory_strength=0.9
    )
    insight_id = compression_result["insight_id"]

    # Verify memory strength was preserved
    created_insight = await get_insight_by_id(insight_id)
    assert created_insight is not None
    assert created_insight["memory_strength"] == 0.9

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_insight_compression_with_io_category(conn):
    """
    Integration Test: Insight compression with io_category.

    AC-5: io_category is correctly set.
    """
    set_project_id("test-isolated")

    # Store raw dialogue
    dialogue_result = await store_raw_dialogue(
        content="Work-related discussion",
        actor="ethr",
        source_type="user_input"
    )
    dialogue_id = dialogue_result["dialogue_id"]

    # Compress with ethr category
    compression_result = await compress_to_l2_insight(
        source_ids=[dialogue_id],
        actor="I/O",
        reason="Test ethr category",
        io_category="ethr"
    )
    insight_id = compression_result["insight_id"]

    # Verify io_category was preserved
    created_insight = await get_insight_by_id(insight_id)
    assert created_insight is not None
    assert created_insight["io_category"] == "ethr"

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_insight_compression_identity_marking(conn):
    """
    Integration Test: Insight compression with is_identity flag.

    AC-5: is_identity is correctly set for self-referential insights.
    """
    set_project_id("test-isolated")

    # Store self-referential dialogue
    dialogue_result = await store_raw_dialogue(
        content="I am an AI assistant",
        actor="I/O",
        source_type="system"
    )
    dialogue_id = dialogue_result["dialogue_id"]

    # Compress as identity insight
    compression_result = await compress_to_l2_insight(
        source_ids=[dialogue_id],
        actor="I/O",
        reason="Test identity marking",
        is_identity=True
    )
    insight_id = compression_result["insight_id"]

    # Verify is_identity flag
    created_insight = await get_insight_by_id(insight_id)
    assert created_insight is not None
    assert created_insight["is_identity"] is True

    clear_context()
