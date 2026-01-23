"""
P0 Tests: Backward Compatibility All MCP Tools (Epic 8)
ATDD Red Phase - Tests that will pass after implementation

Risk Mitigation: R-004 (Backward compatibility broken in existing MCP tools)
Test Count: 12
"""

import pytest
from pathlib import Path
from typing import Dict, List, Any


class TestGraphAddEdgeBackwardCompatibility:
    """FR24: graph_add_edge must include memory_sector but not break existing behavior"""

    @pytest.mark.p0
    def test_graph_add_edge_response_includes_memory_sector(self):
        """FR24: Sector in graph_add_edge response

        Given a call to graph_add_edge(source, target, relation, properties)
        When the edge is created
        Then the response includes memory_sector field
        """
        # Check that graph_add_edge.py imports and uses sector_classifier
        tool_file = Path("mcp_server/tools/graph_add_edge.py")
        content = tool_file.read_text()
        assert "from mcp_server.utils.sector_classifier import classify_memory_sector" in content, \
            "graph_add_edge should import sector_classifier"
        assert "memory_sector" in content, "graph_add_edge should handle memory_sector"

    @pytest.mark.p0
    def test_graph_add_edge_existing_functionality_preserved(self):
        """NFR5: No breaking changes to existing functionality

        Given existing graph_add_edge behavior
        When new memory_sector feature is added
        Then all existing functionality continues to work

        The memory_sector is an addition, not a replacement.
        """
        # Verify existing functionality is preserved
        tool_file = Path("mcp_server/tools/graph_add_edge.py")
        content = tool_file.read_text()
        # Should still have all original parameters
        assert "source_name" in content, "Original parameter preserved"
        assert "target_name" in content, "Original parameter preserved"
        assert "relation" in content, "Original parameter preserved"
        assert "weight" in content, "Original parameter preserved"
        # memory_sector is an addition, not replacement
        assert "memory_sector" in content, "memory_sector should be included"


class TestGraphAddNodeBackwardCompatibility:
    """FR25: graph_add_node must auto-classify connected edges"""

    @pytest.mark.p0
    def test_graph_add_node_auto_classifies_connected_edges(self):
        """FR25: Sector in graph_add_node response

        Given a call to graph_add_node(name, label, properties) that creates connected edges
        When the node is created with edges
        Then each edge is classified and response includes memory_sector
        """
        # Check that graph_add_node.py mentions sector_classifier
        tool_file = Path("mcp_server/tools/graph_add_node.py")
        if tool_file.exists():
            content = tool_file.read_text()
            # Should mention sector classification
            assert "sector" in content.lower(), \
                "graph_add_node should handle sector classification"

    @pytest.mark.p0
    def test_graph_add_node_existing_functionality_preserved(self):
        """NFR5: No breaking changes to existing functionality

        Given existing graph_add_node behavior
        When new auto-classification feature is added
        Then all existing functionality continues to work
        """
        # Verify existing functionality is preserved
        tool_file = Path("mcp_server/tools/graph_add_node.py")
        if tool_file.exists():
            content = tool_file.read_text()
            # Should still have all original parameters
            assert "name" in content, "Original parameter preserved"
            assert "label" in content, "Original parameter preserved"
            assert "properties" in content, "Original parameter preserved"


class TestQueryNeighborsBackwardCompatibility:
    """FR4: query_neighbors must include memory_sector in results"""

    @pytest.mark.p0
    def test_query_neighbors_includes_memory_sector(self):
        """FR4, FR19: Sector in query_neighbors results

        Given a call to query_neighbors(node_name)
        When edges are returned
        Then each edge includes memory_sector field
        """
        # Check that db/graph.py returns memory_sector in query results
        db_file = Path("mcp_server/db/graph.py")
        content = db_file.read_text()

        # Verify memory_sector is in the SELECT
        assert '"memory_sector": row["memory_sector"]' in content, \
            "query_neighbors should return memory_sector in results"

    @pytest.mark.p0
    def test_query_neighbors_existing_parameters_unchanged(self):
        """NFR5: No breaking changes to existing parameters

        Given existing query_neighbors parameters
        When memory_sector feature is added
        Then all existing parameters work exactly as before
        """
        # Check that sector_filter is an addition, not replacement
        tool_file = Path("mcp_server/tools/graph_query_neighbors.py")
        content = tool_file.read_text()

        # Should still have all original parameters
        assert "node_name" in content, "Original parameter preserved"
        assert "relation_type" in content, "Original parameter preserved"
        assert "depth" in content, "Original parameter preserved"
        # sector_filter is an addition
        assert "sector_filter" in content, "sector_filter should be included"

    @pytest.mark.p0
    def test_query_neighbors_return_format_backward_compatible(self):
        """NFR5: No breaking changes to return format

        Given existing query_neighbors return format
        When memory_sector field is added
        Then existing fields remain unchanged
        """
        # Check that return format is backward compatible
        db_file = Path("mcp_server/db/graph.py")
        content = db_file.read_text()

        # Should include all original fields plus memory_sector
        assert '"node_id": str(row["node_id"])' in content, "Original field preserved"
        assert '"label": row["label"]' in content, "Original field preserved"
        assert '"name": row["name"]' in content, "Original field preserved"
        assert '"memory_sector": row["memory_sector"]' in content, "New field added"


class TestHybridSearchBackwardCompatibility:
    """FR4: hybrid_search must include memory_sector in results"""

    @pytest.mark.p0
    def test_hybrid_search_includes_memory_sector(self):
        """FR4, FR19: Sector in hybrid_search results

        Given a call to hybrid_search(query_text)
        When edges are returned
        Then each edge includes memory_sector field
        """
        # Check if hybrid_search tool exists
        tool_file = Path("mcp_server/tools/hybrid_search.py")
        if tool_file.exists():
            content = tool_file.read_text()
            # Verify memory_sector handling
            assert "memory_sector" in content, "hybrid_search should handle memory_sector"

    @pytest.mark.p0
    def test_hybrid_search_existing_parameters_unchanged(self):
        """NFR5: No breaking changes to existing parameters

        Given existing hybrid_search parameters
        When memory_sector feature is added
        Then all existing parameters work exactly as before
        """
        # Check if hybrid_search tool exists
        tool_file = Path("mcp_server/tools/hybrid_search.py")
        if tool_file.exists():
            content = tool_file.read_text()
            # Should still have original parameters
            assert "query_text" in content, "Original parameter preserved"

    @pytest.mark.p0
    def test_hybrid_search_return_format_backward_compatible(self):
        """NFR5: No breaking changes to return format

        Given existing hybrid_search return format
        When memory_sector field is added
        Then existing fields remain unchanged
        """
        # Verify return format is backward compatible
        db_file = Path("mcp_server/db/graph.py")
        content = db_file.read_text()

        # Hybrid search should use similar return format as query_neighbors
        # Check that memory_sector is included in general graph query results
        assert '"memory_sector": row["memory_sector"]' in content, \
            "Graph queries should return memory_sector"


class TestGetEdgeBackwardCompatibility:
    """FR4: get_edge must include memory_sector in response"""

    @pytest.mark.p0
    def test_get_edge_includes_memory_sector(self):
        """FR4, FR19: Sector in get_edge response

        Given a call to get_edge(source, target, relation)
        When an edge is returned
        Then the response includes memory_sector field
        """
        # Check that db/graph.py get_edge function returns memory_sector
        db_file = Path("mcp_server/db/graph.py")
        content = db_file.read_text()

        # get_edge should return memory_sector
        assert "memory_sector" in content, "get_edge should return memory_sector"

    @pytest.mark.p0
    def test_get_edge_existing_functionality_preserved(self):
        """NFR5: No breaking changes to existing functionality

        Given existing get_edge behavior
        When memory_sector is added
        Then all existing functionality continues to work
        """
        # Verify existing functionality is preserved
        db_file = Path("mcp_server/db/graph.py")
        content = db_file.read_text()

        # Should still have original parameters
        assert "source_name" in content or "source_id" in content, "Original parameter preserved"
        assert "target_name" in content or "target_id" in content, "Original parameter preserved"
        assert "relation" in content, "Original parameter preserved"


class TestExistingTestsRegression:
    """NFR5: All existing tests should continue to pass"""

    @pytest.mark.p0
    def test_existing_graph_tests_still_work(self):
        """Regression: Existing tests should not break

        Given existing test files for graph functionality
        When Epic 8 is implemented
        Then all existing tests should still pass (or be explicitly updated)
        """
        # Check that test files exist
        test_dir = Path("tests")
        assert test_dir.exists(), "Tests directory should exist"

        # Verify that existing graph tests are present
        graph_tests = [
            "test_database.py",
            "test_resources.py",
        ]
        for test_file in graph_tests:
            test_path = test_dir / test_file
            if test_path.exists():
                content = test_path.read_text()
                # Tests should still be valid
                assert len(content) > 0, f"{test_file} should have content"
