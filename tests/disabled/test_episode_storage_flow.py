"""
Integration Test for Episode Storage Flow.

Tests the complete workflow:
1. Store raw dialogue → 2. Create episode → 3. Verify episode content

Story TD-2.1.4: Integration Tests
EP-3: History-on-Mutation Pattern
"""

from __future__ import annotations

import pytest

from datetime import datetime, timezone

from mcp_server.db.connection import get_connection_with_project_context
from mcp_server.db.raw_dialogue import store_raw_dialogue
from mcp_server.db.episodes import store_episode, get_episodes, list_episodes
from mcp_server.middleware.context import clear_context, set_project_id


@pytest.mark.asyncio
@pytest.mark.P0
async def test_episode_storage_full_flow(conn):
    """
    Integration Test: Complete episode storage flow.

    Tests:
    - Episode creation from dialogue
    - Episode retrieval and verification
    """
    # Arrange - Set project context
    set_project_id("test-isolated")

    # Step 1: Store raw dialogue
    dialogue_result = await store_raw_dialogue(
        content="Test dialogue for episode storage",
        actor="ethr",
        source_type="user_input"
    )
    assert dialogue_result["success"] is True
    dialogue_id = dialogue_result["dialogue_id"]

    # Step 2: Create episode from dialogue
    episode_result = await store_episode(
        dialogue_ids=[dialogue_id],
        title="Test Episode",
        summary="Integration test episode",
    )
    assert episode_result["success"] is True
    episode_id = episode_result["episode_id"]

    # Step 3: Verify episode was created
    episodes = await get_episodes(limit=1)
    assert len(episodes) == 1
    episode = episodes[0]

    assert episode["episode_id"] == episode_id
    assert episode["title"] == "Test Episode"
    assert "Integration test episode" in episode["summary"]

    # Verify episode references the dialogue
    assert dialogue_id in episode["dialogue_ids"]

    # Verify timestamps
    assert episode["created_at"] is not None
    assert isinstance(episode["created_at"], datetime)

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_episode_storage_with_metadata(conn):
    """
    Integration Test: Episode creation with metadata.

    Tests:
    - Metadata preservation through episode storage
    """
    set_project_id("test-isolated")

    # Store dialogues with metadata
    dialogue_1 = await store_raw_dialogue(
        content="First dialogue",
        actor="ethr",
        source_type="user_input",
        metadata={"session_id": "session-123"}
    )

    dialogue_2 = await store_raw_dialogue(
        content="Second dialogue",
        actor="ethr",
        source_type="user_input",
        metadata={"session_id": "session-123"}
    )

    # Create episode with metadata
    episode_result = await store_episode(
        dialogue_ids=[dialogue_1["dialogue_id"], dialogue_2["dialogue_id"]],
        title="Episode with Metadata",
        summary="Testing metadata preservation",
        metadata={"test_key": "test_value", "category": "test"}
    )

    assert episode_result["success"] is True
    episode_id = episode_result["episode_id"]

    # Verify metadata was preserved
    episodes = await get_episodes(limit=1)
    episode = episodes[0]

    assert episode["metadata"] == {"test_key": "test_value", "category": "test"}

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_episode_list_with_pagination(conn):
    """
    Integration Test: Episode listing with pagination.

    Tests:
    - Multiple episodes with pagination
    - Project-scoped episode listing
    """
    set_project_id("test-isolated")

    # Create multiple episodes
    for i in range(5):
        await store_raw_dialogue(
            content=f"Dialogue {i}",
            actor="ethr",
            source_type="user_input"
        )

    await store_episode(
        dialogue_ids=[i],  # Simplified - would store actual IDs
        title=f"Episode {i}",
        summary=f"Test episode {i}"
    )

    # Test pagination - page 1 (limit 2)
    page_1 = await list_episodes(limit=2, offset=0)
    assert len(page_1) == 2
    assert page_1[0]["title"] == "Episode 0"

    # Test pagination - page 2 (limit 2, offset 2)
    page_2 = await list_episodes(limit=2, offset=2)
    assert len(page_2) == 2
    assert page_2[0]["title"] == "Episode 2"

    # Test all episodes (no limit)
    all_episodes = await list_episodes()
    assert len(all_episodes) == 5

    clear_context()


@pytest.mark.asyncio
@pytest.mark.P0
async def test_episode_cross_project_isolation(conn):
    """
    Integration Test: Episodes are project-scoped.

    Tests:
    - Episodes in different projects don't mix
    - Project filtering works correctly
    """
    # Create episode in project A
    set_project_id("project-a")
    dialogue_a = await store_raw_dialogue(
        content="Project A dialogue",
        actor="ethr",
        source_type="user_input"
    )

    episode_a = await store_episode(
        dialogue_ids=[dialogue_a["dialogue_id"]],
        title="Project A Episode"
    )

    # Create episode in project B
    set_project_id("project-b")
    dialogue_b = await store_raw_dialogue(
        content="Project B dialogue",
        actor="ethr",
        source_type="user_input"
    )

    episode_b = await store_episode(
        dialogue_ids=[dialogue_b["dialogue_id"]],
        title="Project B Episode"
    )

    # Query episodes from project A
    set_project_id("project-a")
    episodes_a = await list_episodes()

    # Query episodes from project B
    set_project_id("project-b")
    episodes_b = await list_episodes()

    # Verify isolation
    assert len(episodes_a) == 1
    assert episodes_a[0]["title"] == "Project A Episode"

    assert len(episodes_b) == 1
    assert episodes_b[0]["title"] == "Project B Episode"

    # Verify no cross-project leakage
    # (Project A episodes should not include Project B episode)
    for episode in episodes_a:
        if episode["episode_id"] == episodes_b[0]["episode_id"]:
            assert False, "Project isolation violated"

    clear_context()
    set_project_id(None)  # Reset
