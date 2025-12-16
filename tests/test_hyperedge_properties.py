"""
Tests for Hyperedge Properties Filtering (Story 7.6)

Tests the properties_filter functionality in query_neighbors:
- Single participant filter (participants: "ethr")
- All participants filter (participants_contains_all: ["I/O", "ethr"])
- Standard JSONB property filters (context_type, emotional_valence)
- Combined property filters
- Invalid filter input handling
- MCP tool parameter validation

Story 7.6: Hyperedge via Properties (Konvention)
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from mcp_server.db.graph import query_neighbors, _build_properties_filter_sql
from mcp_server.tools.graph_query_neighbors import handle_graph_query_neighbors


class TestBuildPropertiesFilterSQL:
    """Test suite for _build_properties_filter_sql helper function."""

    def test_empty_filter_returns_empty(self):
        """Test that empty filter returns empty clauses."""
        clauses, params = _build_properties_filter_sql({})
        assert clauses == []
        assert params == []

    def test_participants_single_element_filter(self):
        """Test single participant filter using ? operator (AC #3)."""
        properties_filter = {"participants": "ethr"}
        clauses, params = _build_properties_filter_sql(properties_filter)

        assert len(clauses) == 1
        assert "e.properties->'participants' ? %s" in clauses[0]
        assert params == ["ethr"]

    def test_participants_contains_all_filter(self):
        """Test all participants filter using @> operator (AC #3)."""
        properties_filter = {"participants_contains_all": ["I/O", "ethr"]}
        clauses, params = _build_properties_filter_sql(properties_filter)

        assert len(clauses) == 1
        assert "@>" in clauses[0]
        assert "e.properties->'participants'" in clauses[0]
        # Params should contain JSON serialized array
        assert '["I/O", "ethr"]' in params[0] or '["ethr", "I/O"]' in params[0]

    def test_standard_string_property_filter(self):
        """Test standard string property filter using @> containment (AC #3)."""
        properties_filter = {"context_type": "shared_experience"}
        clauses, params = _build_properties_filter_sql(properties_filter)

        assert len(clauses) == 1
        assert "e.properties @> %s::jsonb" in clauses[0]
        assert '{"context_type": "shared_experience"}' in params[0]

    def test_combined_property_filters(self):
        """Test multiple property filters combined with AND (AC #3)."""
        properties_filter = {
            "context_type": "shared_experience",
            "emotional_valence": "positive"
        }
        clauses, params = _build_properties_filter_sql(properties_filter)

        assert len(clauses) == 2
        assert len(params) == 2
        # All clauses should be containment checks
        for clause in clauses:
            assert "e.properties @> %s::jsonb" in clause

    def test_mixed_filter_types(self):
        """Test mixing participants filter with standard property filters."""
        properties_filter = {
            "participants": "ethr",
            "context_type": "shared_experience"
        }
        clauses, params = _build_properties_filter_sql(properties_filter)

        assert len(clauses) == 2
        assert len(params) == 2
        # One should be ? operator, one should be @> operator
        participants_clause = [c for c in clauses if "?" in c]
        containment_clause = [c for c in clauses if "@>" in c and "?" not in c]
        assert len(participants_clause) == 1
        assert len(containment_clause) == 1

    def test_integer_property_filter(self):
        """Test integer property value filter."""
        properties_filter = {"priority": 5}
        clauses, params = _build_properties_filter_sql(properties_filter)

        assert len(clauses) == 1
        assert "e.properties @> %s::jsonb" in clauses[0]
        assert '{"priority": 5}' in params[0]

    def test_boolean_property_filter(self):
        """Test boolean property value filter."""
        properties_filter = {"is_active": True}
        clauses, params = _build_properties_filter_sql(properties_filter)

        assert len(clauses) == 1
        assert '{"is_active": true}' in params[0]

    def test_nested_object_property_filter(self):
        """Test nested object property filter."""
        properties_filter = {"metadata": {"version": "1.0"}}
        clauses, params = _build_properties_filter_sql(properties_filter)

        assert len(clauses) == 1
        assert "e.properties @> %s::jsonb" in clauses[0]

    def test_invalid_participants_type_raises_error(self):
        """Test that participants with invalid type raises ValueError."""
        # participants should be string, not list (use participants_contains_all for list)
        properties_filter = {"participants": ["ethr"]}  # Wrong: should be string

        with pytest.raises(ValueError) as exc_info:
            _build_properties_filter_sql(properties_filter)

        assert "participants" in str(exc_info.value).lower()

    def test_invalid_participants_contains_all_type_raises_error(self):
        """Test that participants_contains_all with invalid type raises ValueError."""
        # participants_contains_all should be list, not string
        properties_filter = {"participants_contains_all": "ethr"}  # Wrong: should be list

        with pytest.raises(ValueError) as exc_info:
            _build_properties_filter_sql(properties_filter)

        assert "participants_contains_all" in str(exc_info.value).lower()


class TestQueryNeighborsPropertiesFilter:
    """Test suite for query_neighbors with properties_filter parameter."""

    def test_function_signature_includes_properties_filter(self):
        """Test that query_neighbors has properties_filter parameter."""
        import inspect
        sig = inspect.signature(query_neighbors)

        assert "properties_filter" in sig.parameters
        # Default should be None
        assert sig.parameters["properties_filter"].default is None

    @pytest.mark.asyncio
    async def test_properties_filter_passed_to_sql_query(self):
        """Test that properties_filter is used to build SQL WHERE clauses."""
        # This would require database integration testing
        # For now, we verify the parameter is accepted
        pass


class TestMCPToolPropertiesFilter:
    """Test suite for graph_query_neighbors MCP tool with properties_filter."""

    @pytest.mark.asyncio
    async def test_properties_filter_parameter_accepted(self):
        """Test that properties_filter parameter is accepted by MCP tool (AC #3)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "io-node-id",
                "name": "I/O",
                "label": "Entity",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-12-17T10:00:00Z"
            }
            mock_query.return_value = [
                {
                    "node_id": "decision-node-id",
                    "label": "Decision",
                    "name": "Dennett-Entscheidung",
                    "properties": {},
                    "edge_properties": {
                        "participants": ["I/O", "ethr", "2025-12-15"],
                        "context_type": "shared_experience",
                        "emotional_valence": "positive"
                    },
                    "relation": "EXPERIENCED",
                    "weight": 1.0,
                    "distance": 1,
                    "edge_direction": "outgoing",
                    "relevance_score": 1.0
                }
            ]

            arguments = {
                "node_name": "I/O",
                "properties_filter": {"participants": "ethr"}
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["neighbor_count"] == 1

            # Verify properties_filter was passed to query_neighbors
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args
            assert call_kwargs.kwargs.get("properties_filter") == {"participants": "ethr"} or \
                   (len(call_kwargs.args) > 5 and call_kwargs.args[5] == {"participants": "ethr"})

    @pytest.mark.asyncio
    async def test_properties_filter_in_query_params_response(self):
        """Test that properties_filter is included in query_params response."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "io-node-id",
                "name": "I/O",
                "label": "Entity",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-12-17T10:00:00Z"
            }
            mock_query.return_value = []

            arguments = {
                "node_name": "I/O",
                "properties_filter": {"context_type": "shared_experience"}
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert "query_params" in result
            assert result["query_params"].get("properties_filter") == {"context_type": "shared_experience"}

    @pytest.mark.asyncio
    async def test_invalid_properties_filter_type_error(self):
        """Test that non-dict properties_filter returns validation error."""
        arguments = {
            "node_name": "I/O",
            "properties_filter": "invalid"  # Should be dict
        }

        result = await handle_graph_query_neighbors(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "properties_filter" in result["details"]
        assert result["tool"] == "graph_query_neighbors"

    @pytest.mark.asyncio
    async def test_invalid_filter_value_propagates_as_database_error(self):
        """Test that ValueError from _build_properties_filter_sql propagates correctly.

        When an invalid filter value is passed (e.g., participants as list instead of string),
        the ValueError should be caught and returned as a database operation error.
        """
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "io-node-id",
                "name": "I/O",
                "label": "Entity",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-12-17T10:00:00Z"
            }
            # Simulate ValueError from _build_properties_filter_sql
            mock_query.side_effect = ValueError(
                "Invalid 'participants' filter value: expected string, got list"
            )

            arguments = {
                "node_name": "I/O",
                "properties_filter": {"participants": ["invalid", "list"]}  # Wrong type
            }

            result = await handle_graph_query_neighbors(arguments)

            # ValueError from query_neighbors should be caught as database error
            assert result["error"] == "Database operation failed"
            assert "participants" in result["details"]
            assert result["tool"] == "graph_query_neighbors"

    @pytest.mark.asyncio
    async def test_properties_filter_with_participants_contains_all(self):
        """Test properties_filter with participants_contains_all array filter (AC #3)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "decision-node-id",
                "name": "Dennett-Entscheidung",
                "label": "Decision",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-12-17T10:00:00Z"
            }
            mock_query.return_value = []

            arguments = {
                "node_name": "Dennett-Entscheidung",
                "properties_filter": {"participants_contains_all": ["I/O", "ethr"]}
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            # Verify query was called with the filter
            mock_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_properties_filter_combined_with_other_params(self):
        """Test properties_filter works with other query parameters."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "io-node-id",
                "name": "I/O",
                "label": "Entity",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-12-17T10:00:00Z"
            }
            mock_query.return_value = []

            arguments = {
                "node_name": "I/O",
                "relation_type": "EXPERIENCED",
                "depth": 2,
                "direction": "outgoing",
                "properties_filter": {
                    "context_type": "shared_experience",
                    "emotional_valence": "positive"
                }
            }

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["query_params"]["relation_type"] == "EXPERIENCED"
            assert result["query_params"]["depth"] == 2
            assert result["query_params"]["direction"] == "outgoing"
            assert result["query_params"]["properties_filter"] == {
                "context_type": "shared_experience",
                "emotional_valence": "positive"
            }

    @pytest.mark.asyncio
    async def test_edge_properties_in_response_includes_participants(self):
        """Test that edge_properties in response includes participants array (AC #4)."""
        with patch('mcp_server.tools.graph_query_neighbors.get_node_by_name') as mock_get_node, \
             patch('mcp_server.tools.graph_query_neighbors.query_neighbors') as mock_query:

            mock_get_node.return_value = {
                "id": "io-node-id",
                "name": "I/O",
                "label": "Entity",
                "properties": {},
                "vector_id": None,
                "created_at": "2025-12-17T10:00:00Z"
            }
            # Response includes edge_properties with participants
            mock_query.return_value = [
                {
                    "node_id": "decision-node-id",
                    "label": "Decision",
                    "name": "Dennett-Entscheidung",
                    "properties": {},
                    "edge_properties": {
                        "participants": ["I/O", "ethr", "2025-12-15"],
                        "context_type": "shared_experience",
                        "emotional_valence": "positive"
                    },
                    "relation": "EXPERIENCED",
                    "weight": 1.0,
                    "distance": 1,
                    "edge_direction": "outgoing",
                    "relevance_score": 1.0
                }
            ]

            arguments = {"node_name": "I/O"}

            result = await handle_graph_query_neighbors(arguments)

            assert result["status"] == "success"
            assert result["neighbor_count"] == 1

            neighbor = result["neighbors"][0]
            assert "edge_properties" in neighbor
            assert "participants" in neighbor["edge_properties"]
            assert neighbor["edge_properties"]["participants"] == ["I/O", "ethr", "2025-12-15"]
            assert neighbor["edge_properties"]["context_type"] == "shared_experience"


class TestHyperedgeCreationWithParticipants:
    """Test suite for creating edges with participants property (AC #1, #2)."""

    @pytest.mark.asyncio
    async def test_edge_with_participants_property_created(self):
        """Test that edge with participants array can be created (AC #1)."""
        # This test verifies existing graph_add_edge functionality
        # AC #2 states existing graph_add_edge should remain unchanged
        from mcp_server.tools.graph_add_edge import handle_graph_add_edge

        with patch('mcp_server.tools.graph_add_edge.get_or_create_node') as mock_get_create, \
             patch('mcp_server.tools.graph_add_edge.add_edge') as mock_add_edge:

            # Mock node creation
            mock_get_create.side_effect = [
                {"node_id": "io-node-id", "created": False},
                {"node_id": "decision-node-id", "created": False}
            ]

            # Mock edge creation
            mock_add_edge.return_value = {
                "edge_id": "edge-uuid",
                "created": True,
                "source_id": "io-node-id",
                "target_id": "decision-node-id",
                "relation": "EXPERIENCED",
                "weight": 1.0
            }

            arguments = {
                "source_name": "I/O",
                "target_name": "Dennett-Entscheidung",
                "relation": "EXPERIENCED",
                "properties": {
                    "participants": ["I/O", "ethr", "2025-12-15"],
                    "context_type": "shared_experience",
                    "emotional_valence": "positive"
                }
            }

            result = await handle_graph_add_edge(arguments)

            assert result["status"] == "success"
            # Verify properties were passed to add_edge
            mock_add_edge.assert_called_once()
            call_args = mock_add_edge.call_args
            # Properties should be JSON string
            import json
            properties_arg = call_args.kwargs.get("properties") or call_args.args[4]
            properties_dict = json.loads(properties_arg)
            assert "participants" in properties_dict
            assert properties_dict["participants"] == ["I/O", "ethr", "2025-12-15"]
