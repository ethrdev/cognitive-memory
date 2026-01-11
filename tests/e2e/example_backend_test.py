"""
Example test demonstrating the test framework usage.

This file shows best practices for:
- Using factories for test data creation
- Using helpers for assertions
- Testing database operations
- Testing MCP tool handlers
"""

import pytest

from tests.support.factories import NodeFactory, EdgeFactory, InsightFactory, EpisodeFactory
from tests.support.helpers import (
    assert_database_state,
    assert_json_response,
    create_test_node,
)
from tests.support.helpers.mocks import mock_graph_node


class TestFrameworkExample:
    """Example test class demonstrating framework usage."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_and_retrieve_node(self, conn):
        """Example: Create a node and retrieve it using factories."""
        # GIVEN: We use NodeFactory to create test data
        with NodeFactory() as factory:
            # Create a test node
            node = factory.create(conn, label="Agent", name="TestAgent")

            # THEN: We can verify it exists in database
            nodes = assert_database_state(
                conn,
                "graph_nodes",
                expected_conditions={"name": "TestAgent"}
            )

            assert len(nodes) == 1
            assert nodes[0]["label"] == "Agent"

            # Auto-cleanup happens when exiting context

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_related_nodes_and_edge(self, conn):
        """Example: Create nodes with a relationship using EdgeFactory."""
        # GIVEN: We create source and target nodes with an edge
        with NodeFactory() as node_factory, EdgeFactory() as edge_factory:
            # Create source node
            source = node_factory.create(conn, label="Agent", name="I/O")

            # Create target node
            target = node_factory.create(conn, label="Technology", name="Python")

            # Create edge between them
            edge = edge_factory.create(
                conn,
                source_name="I/O",
                target_name="Python",
                relation="USES",
                weight=0.9
            )

            # THEN: Verify the edge exists
            edges = assert_database_state(conn, "graph_edges")
            assert len(edges) >= 1

            # Verify edge properties
            created_edge = edges[0]
            assert created_edge["relation"] == "USES"
            assert created_edge["weight"] == 0.9

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_insight_and_episode(self, conn):
        """Example: Create L2 insight and episode data."""
        # GIVEN: We use InsightFactory and EpisodeFactory
        with InsightFactory() as insight_factory, EpisodeFactory() as episode_factory:
            # Create an insight
            insight = insight_factory.create(
                conn,
                content="Test insight about AI",
                memory_strength=0.8
            )

            # Create an episode
            episode = episode_factory.create(
                conn,
                query="What is machine learning?",
                reward=0.7
            )

            # THEN: Verify both exist
            insights = assert_database_state(conn, "l2_insights")
            episodes = assert_database_state(conn, "episodes")

            assert len(insights) >= 1
            assert len(episodes) >= 1

            # Verify properties
            created_insight = insights[0]
            assert created_insight["memory_strength"] == 0.8

            created_episode = episodes[0]
            assert created_episode["reward"] == 0.7

    @pytest.mark.asyncio
    async def test_mock_data_generation(self):
        """Example: Generate mock data without database."""
        # GIVEN: We use mock generators for unit tests
        from tests.support.helpers.generators import (
            generate_test_node,
            generate_test_edge,
            generate_test_insight,
        )

        # WHEN: We generate test data
        node = generate_test_node(label="MockAgent", name="MockNode")
        edge = generate_test_edge(relation="USES")
        insight = generate_test_insight(content="Mock insight")

        # THEN: Data has expected structure
        assert "id" in node
        assert node["label"] == "MockAgent"
        assert node["name"] == "MockNode"

        assert "id" in edge
        assert edge["relation"] == "USES"

        assert "id" in insight
        assert insight["content"] == "Mock insight"
        assert len(insight["embedding"]) == 1536

    @pytest.mark.asyncio
    async def test_mock_responses(self):
        """Example: Using mock utilities for external services."""
        # GIVEN: We use mock utilities
        from tests.support.helpers.mocks import (
            mock_openai_embedding,
            mock_anthropic_response,
        )

        # WHEN: We create mock clients
        openai_mock = mock_openai_embedding()
        anthropic_mock = mock_anthropic_response()

        # THEN: We can use them in tests
        embedding_response = openai_mock.embeddings.create(
            input="Test input",
            model="text-embedding-3-small"
        )

        assert embedding_response.data[0].embedding is not None

        anthropic_response = await anthropic_mock.messages.create(
            messages=[{"role": "user", "content": "Test"}]
        )

        assert anthropic_response.content[0].text is not None

    @pytest.mark.asyncio
    async def test_assertion_helpers(self):
        """Example: Using custom assertion helpers."""
        # GIVEN: We have test data
        from tests.support.helpers.assertions import (
            assert_node_data,
            assert_edge_data,
        )

        # WHEN: We validate data structure
        node = {
            "id": "test-id",
            "label": "Agent",
            "name": "TestNode",
            "properties": {"test": True},
            "created_at": "2026-01-11T12:00:00Z"
        }

        edge = {
            "id": "test-edge-id",
            "source_id": "source-id",
            "target_id": "target-id",
            "relation": "USES",
            "weight": 0.8,
            "created_at": "2026-01-11T12:00:00Z"
        }

        # THEN: Assertions pass
        assert_node_data(node, "TestNode")
        assert_edge_data(edge, "source", "target")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_data_creation(self, conn):
        """Example: Creating multiple test records efficiently."""
        # GIVEN: We use batch creation
        with NodeFactory() as factory:
            # Create multiple nodes at once
            nodes = factory.create_batch(conn, count=5, label="BatchNode")

            # Create multiple edges at once
            from tests.support.factories import EdgeFactory

            with EdgeFactory() as edge_factory:
                edges = edge_factory.create_batch(conn, count=3, relation="BATCH_RELATION")

            # THEN: All records created
            all_nodes = assert_database_state(conn, "graph_nodes")
            all_edges = assert_database_state(conn, "graph_edges")

            assert len(all_nodes) >= 5
            assert len(all_edges) >= 3

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_data_cleanup_isolation(self, conn):
        """Example: Ensuring test isolation through cleanup."""
        # GIVEN: Each test gets fresh data
        initial_counts = {
            "nodes": len(assert_database_state(conn, "graph_nodes")),
            "edges": len(assert_database_state(conn, "graph_edges")),
        }

        # WHEN: We create test data
        with NodeFactory() as factory:
            factory.create(conn, label="TempNode", name="TempName")

            # Verify data exists
            nodes = assert_database_state(conn, "graph_nodes")
            assert len(nodes) > initial_counts["nodes"]

        # THEN: Data is cleaned up automatically
        final_nodes = assert_database_state(conn, "graph_nodes")
        assert len(final_nodes) == initial_counts["nodes"]

    @pytest.mark.asyncio
    async def test_error_handling_graceful(self):
        """Example: Testing graceful error handling."""
        # GIVEN: We test error scenarios
        from tests.support.helpers.mocks import mock_error_response, mock_success_response

        # WHEN: We handle errors
        error = mock_error_response("Test error", status="not_found")
        success = mock_success_response({"data": "value"}, status="success")

        # THEN: Error responses are structured correctly
        assert error["status"] == "not_found"
        assert error["error"] == "Test error"
        assert "data" not in error

        assert success["status"] == "success"
        assert success["data"]["data"] == "value"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_workflow(self, conn):
        """Example: Complete workflow from creation to verification."""
        # GIVEN: We test a complete data flow
        with NodeFactory() as node_factory, EdgeFactory() as edge_factory, \
             InsightFactory() as insight_factory, EpisodeFactory() as episode_factory:

            # Create nodes
            agent = node_factory.create(conn, label="Agent", name="TestAgent")
            tech = node_factory.create(conn, label="Technology", name="TestTech")

            # Create edge
            edge = edge_factory.create(
                conn,
                source_name="TestAgent",
                target_name="TestTech",
                relation="USES"
            )

            # Create insight
            insight = insight_factory.create(
                conn,
                content="TestAgent uses TestTech",
                memory_strength=0.9
            )

            # Create episode
            episode = episode_factory.create(
                conn,
                query="How does TestAgent use TestTech?",
                reward=0.8
            )

            # THEN: Verify complete workflow
            nodes = assert_database_state(conn, "graph_nodes")
            edges = assert_database_state(conn, "graph_edges")
            insights = assert_database_state(conn, "l2_insights")
            episodes = assert_database_state(conn, "episodes")

            assert len(nodes) >= 2
            assert len(edges) >= 1
            assert len(insights) >= 1
            assert len(episodes) >= 1

            # Verify relationships
            assert edges[0]["relation"] == "USES"
            assert insights[0]["memory_strength"] == 0.9
            assert episodes[0]["reward"] == 0.8

        # Auto-cleanup: All created data removed
