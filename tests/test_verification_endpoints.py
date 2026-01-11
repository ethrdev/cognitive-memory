"""
Integration Tests for Verification Workflow

Tests the Write-then-Verify pattern across all Epic 6 tools:
- get_node_by_name (Story 6.1)
- get_edge (Story 6.2)
- count_by_type (Story 6.3)
- list_episodes (Story 6.4)
- get_insight_by_id (Story 6.5)

Story 6.6: Integration Tests für Verification Workflow

IMPORTANT: Tests marked with @pytest.mark.integration require:
- DATABASE_URL in .env.development
- OPENAI_API_KEY for episode/insight tests (will skip if not configured)
"""

from __future__ import annotations

import os
import uuid
from typing import Generator

import pytest
from dotenv import load_dotenv

# Load environment FIRST
load_dotenv(".env.development")

# Tool Handler Imports - all from specific modules for consistency
from mcp_server.db.connection import get_connection
from mcp_server.tools import handle_compress_to_l2_insight, handle_store_episode
from mcp_server.tools.count_by_type import handle_count_by_type
from mcp_server.tools.get_edge import handle_get_edge
from mcp_server.tools.get_insight_by_id import handle_get_insight_by_id
from mcp_server.tools.get_node_by_name import handle_get_node_by_name
from mcp_server.tools.graph_add_edge import handle_graph_add_edge
from mcp_server.tools.graph_add_node import handle_graph_add_node
from mcp_server.tools.list_episodes import handle_list_episodes


# ============================================================================
# Fixtures for Test Configuration
# ============================================================================


@pytest.fixture
def require_database() -> Generator[None, None, None]:
    """Skip test if DATABASE_URL not configured."""
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not configured - skipping integration test")
    yield


@pytest.fixture
def require_openai() -> Generator[None, None, None]:
    """Skip test if OPENAI_API_KEY not configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-openai-api-key-here":
        pytest.skip("OPENAI_API_KEY not configured - skipping API-dependent test")
    yield


# ============================================================================
# AC-6.6.1: Write-then-Verify Node Test
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_write_then_verify_node(require_database: Generator[None, None, None]) -> None:
    """Test Write-then-Verify pattern for graph nodes.

    AC-6.6.1: Test flow:
    1. graph_add_node(label, name) -> receive node_id
    2. get_node_by_name(name) -> verify identical node_id
    3. Cleanup: delete test node
    """
    test_name = f"TestNode_{uuid.uuid4().hex[:8]}"
    created_node_id = None

    try:
        # WRITE: Create node
        result = await handle_graph_add_node({
            "label": "TestLabel",
            "name": test_name
        })
        assert result["status"] == "success"
        assert result["created"] is True
        created_node_id = result["node_id"]

        # VERIFY: Get node by name
        verify = await handle_get_node_by_name({"name": test_name})
        assert verify["status"] == "success"
        assert verify["node_id"] == created_node_id
        assert verify["name"] == test_name

    finally:
        # CLEANUP
        if created_node_id:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM nodes WHERE id = %s", (created_node_id,))
                conn.commit()


# ============================================================================
# AC-6.6.2: Write-then-Verify Edge Test
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_write_then_verify_edge(require_database: Generator[None, None, None]) -> None:
    """Test Write-then-Verify pattern for graph edges.

    AC-6.6.2: Test flow:
    1. Create Source-Node: graph_add_node(label, source_name)
    2. Create Target-Node: graph_add_node(label, target_name)
    3. graph_add_edge(source, target, relation) -> receive edge_id
    4. get_edge(source, target, relation) -> verify identical edge_id
    5. Cleanup: Edges BEFORE Nodes (FK-Constraint!)
    """
    source_name = f"SourceNode_{uuid.uuid4().hex[:8]}"
    target_name = f"TargetNode_{uuid.uuid4().hex[:8]}"
    source_id = None
    target_id = None

    try:
        # Create source node
        source_result = await handle_graph_add_node({
            "label": "Test", "name": source_name
        })
        source_id = source_result["node_id"]

        # Create target node
        target_result = await handle_graph_add_node({
            "label": "Test", "name": target_name
        })
        target_id = target_result["node_id"]

        # WRITE: Create edge
        edge_result = await handle_graph_add_edge({
            "source_name": source_name,
            "target_name": target_name,
            "relation": "TEST_RELATION"
        })
        assert edge_result["status"] == "success"
        edge_id = edge_result["edge_id"]

        # VERIFY: Get edge
        verify = await handle_get_edge({
            "source_name": source_name,
            "target_name": target_name,
            "relation": "TEST_RELATION"
        })
        assert verify["status"] == "success"
        assert verify["edge_id"] == edge_id

    finally:
        # CLEANUP: Edges BEFORE nodes (FK constraint!)
        async with get_connection() as conn:
            with conn.cursor() as cur:
                if source_id and target_id:
                    cur.execute(
                        "DELETE FROM edges WHERE source_id = %s OR target_id = %s",
                        (source_id, target_id)
                    )
                if source_id:
                    cur.execute("DELETE FROM nodes WHERE id = %s", (source_id,))
                if target_id:
                    cur.execute("DELETE FROM nodes WHERE id = %s", (target_id,))
            conn.commit()


# ============================================================================
# AC-6.6.3: Count Sanity Check Test
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_count_sanity_check(require_database: Generator[None, None, None]) -> None:
    """Test count_by_type verification pattern.

    AC-6.6.3: Test flow:
    1. count_by_type() -> initial count (baseline)
    2. Insert test data (Node)
    3. count_by_type() -> verify counts increased
    4. Cleanup: delete test data
    5. count_by_type() -> verify counts back to baseline
    """
    test_name = f"CountTestNode_{uuid.uuid4().hex[:8]}"
    created_node_id = None

    try:
        # BASELINE: Get initial counts
        baseline = await handle_count_by_type({})
        assert baseline["status"] == "success"
        initial_nodes = baseline["graph_nodes"]

        # INSERT: Create test node
        create_result = await handle_graph_add_node({
            "label": "CountTest",
            "name": test_name
        })
        assert create_result["status"] == "success"
        created_node_id = create_result["node_id"]

        # VERIFY: Counts increased
        after_insert = await handle_count_by_type({})
        assert after_insert["graph_nodes"] == initial_nodes + 1

        # CLEANUP
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM nodes WHERE id = %s", (created_node_id,))
            conn.commit()
        created_node_id = None  # Mark as cleaned

        # VERIFY: Counts back to baseline
        after_cleanup = await handle_count_by_type({})
        assert after_cleanup["graph_nodes"] == initial_nodes

    finally:
        # Safety cleanup in case of early failure
        if created_node_id:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM nodes WHERE id = %s", (created_node_id,))
                conn.commit()


# ============================================================================
# AC-6.6.4: List-Episodes-then-Verify Test
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_episodes_verification(
    require_database: Generator[None, None, None],
    require_openai: Generator[None, None, None],
) -> None:
    """Test store_episode -> list_episodes verification.

    AC-6.6.4: Test flow:
    1. list_episodes() -> initial count
    2. store_episode(query, reward, reflection) -> receive id
    3. list_episodes() -> verify count increased + episode present
    4. Cleanup: delete episode

    WICHTIG: This test requires OPENAI_API_KEY (embedding generation).
    """
    episode_id = None

    try:
        # Get initial count
        initial = await handle_list_episodes({})
        initial_count = initial["total_count"]

        # WRITE: Store episode (CALLS OPENAI API!)
        result = await handle_store_episode({
            "query": f"Test query {uuid.uuid4().hex[:8]}",
            "reward": 0.75,
            "reflection": "Problem: Test problem. Lesson: Test lesson."
        })
        assert result["embedding_status"] == "success"
        episode_id = result["id"]  # NOTE: Field is "id", not "episode_id"!

        # VERIFY: List episodes - count increased
        after = await handle_list_episodes({})
        assert after["total_count"] == initial_count + 1

    finally:
        # CLEANUP
        if episode_id:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM episode_memory WHERE id = %s", (episode_id,))
                conn.commit()


# ============================================================================
# AC-6.6.5: Get-Insight-by-ID-then-Verify Test
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_insight_by_id_verification(
    require_database: Generator[None, None, None],
    require_openai: Generator[None, None, None],
) -> None:
    """Test compress_to_l2_insight -> get_insight_by_id verification.

    AC-6.6.5: Test flow:
    1. compress_to_l2_insight(content, source_ids) -> receive id
    2. get_insight_by_id(id) -> verify content and source_ids match
    3. Cleanup: delete insight

    WICHTIG: This test requires OPENAI_API_KEY (embedding generation).
    """
    insight_id = None
    test_content = f"Test insight content {uuid.uuid4().hex[:8]}"

    try:
        # WRITE: Create insight (CALLS OPENAI API!)
        result = await handle_compress_to_l2_insight({
            "content": test_content,
            "source_ids": []  # Empty list is valid
        })
        assert result["embedding_status"] == "success"
        insight_id = result["id"]  # NOTE: Field is "id", not "insight_id"!

        # VERIFY: Get insight by ID
        verify = await handle_get_insight_by_id({"id": insight_id})
        assert verify["status"] == "success"
        assert verify["content"] == test_content
        assert verify["source_ids"] == []
        assert "embedding" not in verify  # Embedding excluded from response

    finally:
        # CLEANUP
        if insight_id:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM l2_insights WHERE id = %s", (insight_id,))
                conn.commit()


# ============================================================================
# AC-6.6.6: Complete Verification Workflow Test
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_verification_workflow(
    require_database: Generator[None, None, None],
) -> None:
    """Test complete E2E verification workflow demonstrating I/O Agent pattern.

    AC-6.6.6: Demonstrates the complete I/O Agent Verification Pattern:

    Phase 1: Data Creation (Graph-only, no API calls)
    - Create Graph-Node 1
    - Create Graph-Node 2
    - Create Edge between nodes

    Phase 2: Verification
    - get_node_by_name -> verify Node 1
    - get_node_by_name -> verify Node 2
    - get_edge -> verify Edge
    - count_by_type -> verify graph counts

    Phase 3: Cleanup
    - Delete edges BEFORE nodes (FK-Constraint!)
    - Verify counts back to baseline
    """
    node1_name = f"E2E_Node1_{uuid.uuid4().hex[:8]}"
    node2_name = f"E2E_Node2_{uuid.uuid4().hex[:8]}"
    node1_id = None
    node2_id = None

    try:
        # Get baseline counts
        baseline = await handle_count_by_type({})
        baseline_nodes = baseline["graph_nodes"]
        baseline_edges = baseline["graph_edges"]

        # ====================================================================
        # PHASE 1: Data Creation
        # ====================================================================

        # Create Node 1
        node1_result = await handle_graph_add_node({
            "label": "E2ETest",
            "name": node1_name
        })
        assert node1_result["status"] == "success"
        node1_id = node1_result["node_id"]

        # Create Node 2
        node2_result = await handle_graph_add_node({
            "label": "E2ETest",
            "name": node2_name
        })
        assert node2_result["status"] == "success"
        node2_id = node2_result["node_id"]

        # Create Edge between nodes
        # NOTE: Must pass source_label and target_label to avoid default "Entity" overwrite
        edge_result = await handle_graph_add_edge({
            "source_name": node1_name,
            "target_name": node2_name,
            "relation": "E2E_CONNECTS_TO",
            "source_label": "E2ETest",
            "target_label": "E2ETest"
        })
        assert edge_result["status"] == "success"
        edge_id = edge_result["edge_id"]

        # ====================================================================
        # PHASE 2: Verification
        # ====================================================================

        # Verify Node 1
        verify_node1 = await handle_get_node_by_name({"name": node1_name})
        assert verify_node1["status"] == "success"
        assert verify_node1["node_id"] == node1_id
        assert verify_node1["label"] == "E2ETest"

        # Verify Node 2
        verify_node2 = await handle_get_node_by_name({"name": node2_name})
        assert verify_node2["status"] == "success"
        assert verify_node2["node_id"] == node2_id
        assert verify_node2["label"] == "E2ETest"

        # Verify Edge
        verify_edge = await handle_get_edge({
            "source_name": node1_name,
            "target_name": node2_name,
            "relation": "E2E_CONNECTS_TO"
        })
        assert verify_edge["status"] == "success"
        assert verify_edge["edge_id"] == edge_id

        # Verify counts increased
        after_create = await handle_count_by_type({})
        assert after_create["graph_nodes"] == baseline_nodes + 2
        assert after_create["graph_edges"] == baseline_edges + 1

        # ====================================================================
        # PHASE 3: Cleanup
        # ====================================================================

        # Delete edges BEFORE nodes (FK-Constraint!)
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM edges WHERE source_id = %s OR target_id = %s",
                    (node1_id, node2_id)
                )
                cur.execute("DELETE FROM nodes WHERE id = %s", (node1_id,))
                cur.execute("DELETE FROM nodes WHERE id = %s", (node2_id,))
            conn.commit()

        node1_id = None  # Mark as cleaned
        node2_id = None

        # Verify counts back to baseline
        after_cleanup = await handle_count_by_type({})
        assert after_cleanup["graph_nodes"] == baseline_nodes
        assert after_cleanup["graph_edges"] == baseline_edges

    finally:
        # Safety cleanup in case of early failure
        async with get_connection() as conn:
            with conn.cursor() as cur:
                if node1_id or node2_id:
                    cur.execute(
                        "DELETE FROM edges WHERE source_id = %s OR target_id = %s OR source_id = %s OR target_id = %s",
                        (node1_id, node2_id, node1_id, node2_id)
                    )
                if node1_id:
                    cur.execute("DELETE FROM nodes WHERE id = %s", (node1_id,))
                if node2_id:
                    cur.execute("DELETE FROM nodes WHERE id = %s", (node2_id,))
            conn.commit()
