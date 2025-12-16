"""
Tests for entrenchment level auto-setting in graph edges.

Tests the automatic setting of entrenchment_level based on edge_type
when creating edges via add_edge function.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from mcp_server.db.graph import add_edge


class TestEntrenchmentAutoSetting:
    """Test automatic entrenchment level setting."""

    @pytest.mark.asyncio
    async def test_add_edge_constitutive_sets_maximal_entrenchment(self):
        """Test that constitutive edges get maximal entrenchment."""
        # Mock database connection and cursor
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Mock successful INSERT ... ON CONFLICT result
            mock_cursor.fetchone.return_value = {
                "id": "test-edge-id",
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "BELIEVES",
                "weight": 1.0,
                "created_at": "2023-01-01T00:00:00Z",
                "was_inserted": True
            }

            # Call add_edge with constitutive edge_type
            properties_with_edge_type = json.dumps({
                "edge_type": "constitutive",
                "some_other_property": "value"
            })

            result = add_edge(
                source_id="source-id",
                target_id="target-id",
                relation="BELIEVES",
                weight=1.0,
                properties=properties_with_edge_type
            )

            # Verify the result
            assert result["edge_id"] == "test-edge-id"
            assert result["created"] is True

            # Check that the SQL was called with modified properties
            # The entrenchment_level should be added
            call_args = mock_cursor.execute.call_args
            sql_query = call_args[0][0]
            sql_params = call_args[0][1]

            # Verify properties parameter includes entrenchment_level
            properties_param = sql_params[4]  # 5th parameter (index 4)
            parsed_props = json.loads(properties_param)

            assert parsed_props.get("entrenchment_level") == "maximal"
            assert parsed_props.get("edge_type") == "constitutive"
            assert parsed_props.get("some_other_property") == "value"

    @pytest.mark.asyncio
    async def test_add_edge_descriptive_sets_default_entrenchment(self):
        """Test that descriptive edges get default entrenchment."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            mock_cursor.fetchone.return_value = {
                "id": "test-edge-id",
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "USES",
                "weight": 0.8,
                "created_at": "2023-01-01T00:00:00Z",
                "was_inserted": True
            }

            # Call add_edge with descriptive edge_type
            properties_with_edge_type = json.dumps({
                "edge_type": "descriptive",
                "context": "project dependency"
            })

            result = add_edge(
                source_id="source-id",
                target_id="target-id",
                relation="USES",
                weight=0.8,
                properties=properties_with_edge_type
            )

            assert result["created"] is True

            # Check properties
            call_args = mock_cursor.execute.call_args
            properties_param = call_args[0][1][4]
            parsed_props = json.loads(properties_param)

            assert parsed_props.get("entrenchment_level") == "default"

    @pytest.mark.asyncio
    async def test_add_edge_no_edge_type_sets_default_entrenchment(self):
        """Test that edges without edge_type get default entrenchment."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            mock_cursor.fetchone.return_value = {
                "id": "test-edge-id",
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "RELATED_TO",
                "weight": 0.5,
                "created_at": "2023-01-01T00:00:00Z",
                "was_inserted": True
            }

            # Call add_edge without edge_type
            properties_no_edge_type = json.dumps({
                "context": "general relationship",
                "strength": "moderate"
            })

            result = add_edge(
                source_id="source-id",
                target_id="target-id",
                relation="RELATED_TO",
                weight=0.5,
                properties=properties_no_edge_type
            )

            assert result["created"] is True

            # Check properties
            call_args = mock_cursor.execute.call_args
            properties_param = call_args[0][1][4]
            parsed_props = json.loads(properties_param)

            # Should set "default" entrenchment (edge_type is used but not written back)
            assert parsed_props.get("entrenchment_level") == "default"
            # Note: edge_type is NOT written to properties, only used for logic
            # The original properties remain unchanged except for entrenchment_level

    @pytest.mark.asyncio
    async def test_add_edge_empty_properties_sets_default_entrenchment(self):
        """Test that empty properties get default entrenchment."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            mock_cursor.fetchone.return_value = {
                "id": "test-edge-id",
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "CONNECTS_TO",
                "weight": 1.0,
                "created_at": "2023-01-01T00:00:00Z",
                "was_inserted": True
            }

            # Call add_edge with empty properties
            result = add_edge(
                source_id="source-id",
                target_id="target-id",
                relation="CONNECTS_TO",
                weight=1.0,
                properties="{}"
            )

            assert result["created"] is True

            # Check properties
            call_args = mock_cursor.execute.call_args
            properties_param = call_args[0][1][4]
            parsed_props = json.loads(properties_param)

            assert parsed_props.get("entrenchment_level") == "default"
            # Note: edge_type is NOT written to properties, only used for logic

    @pytest.mark.asyncio
    async def test_add_edge_invalid_json_properties(self):
        """Test handling of invalid JSON in properties."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor  # Fixed: was mock_conn
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            mock_cursor.fetchone.return_value = {
                "id": "test-edge-id",
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "TEST_RELATION",
                "weight": 1.0,
                "created_at": "2023-01-01T00:00:00Z",
                "was_inserted": True
            }

            # Call add_edge with invalid JSON
            result = add_edge(
                source_id="source-id",
                target_id="target-id",
                relation="TEST_RELATION",
                weight=1.0,
                properties="invalid json {"
            )

            assert result["created"] is True

            # Should handle invalid JSON gracefully
            # Check properties - it should create empty dict and apply defaults
            call_args = mock_cursor.execute.call_args
            properties_param = call_args[0][1][4]
            parsed_props = json.loads(properties_param)

            assert parsed_props.get("entrenchment_level") == "default"
            # Note: edge_type is NOT written to properties, only used for logic

    @pytest.mark.asyncio
    async def test_add_edge_update_existing_preserves_entrenchment(self):
        """Test that updating existing edge preserves its entrenchment setting."""
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            # Simulate edge update (was_inserted = False)
            mock_cursor.fetchone.return_value = {
                "id": "existing-edge-id",
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "BELIEVES",
                "weight": 1.0,
                "created_at": "2023-01-01T00:00:00Z",
                "was_inserted": False  # Existing edge updated
            }

            # Call with constitutive edge_type
            properties_with_edge_type = json.dumps({
                "edge_type": "constitutive",
                "updated_reason": "clarification"
            })

            result = add_edge(
                source_id="source-id",
                target_id="target-id",
                relation="BELIEVES",
                weight=1.0,
                properties=properties_with_edge_type
            )

            assert result["created"] is False  # Was an update

            # Check that the update still sets entrenchment_level
            call_args = mock_cursor.execute.call_args
            properties_param = call_args[0][1][4]
            parsed_props = json.loads(properties_param)

            assert parsed_props.get("entrenchment_level") == "maximal"
            assert parsed_props.get("edge_type") == "constitutive"

    @pytest.mark.asyncio
    async def test_add_edge_constitutive_always_sets_maximal(self):
        """Test that constitutive edges ALWAYS get maximal entrenchment (by design).

        Note: Per AGM Belief Revision theory, constitutive edges must ALWAYS
        have maximal entrenchment, regardless of any pre-existing value.
        This is by design, not a bug.
        """
        with patch('mcp_server.db.graph.get_connection') as mock_get_conn:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_get_conn.return_value.__enter__.return_value = mock_conn

            mock_cursor.fetchone.return_value = {
                "id": "existing-edge-id",
                "source_id": "source-id",
                "target_id": "target-id",
                "relation": "CUSTOM_RELATION",
                "weight": 1.0,
                "created_at": "2023-01-01T00:00:00Z",
                "was_inserted": True
            }

            # Properties with pre-existing entrenchment_level that will be overwritten
            properties_with_existing = json.dumps({
                "edge_type": "constitutive",
                "entrenchment_level": "custom_level",  # Will be overwritten!
                "special_property": "value"
            })

            result = add_edge(
                source_id="source-id",
                target_id="target-id",
                relation="CUSTOM_RELATION",
                weight=1.0,
                properties=properties_with_existing
            )

            assert result["created"] is True

            call_args = mock_cursor.execute.call_args
            properties_param = call_args[0][1][4]
            parsed_props = json.loads(properties_param)

            # Constitutive edges ALWAYS get maximal (AGM requirement)
            assert parsed_props.get("entrenchment_level") == "maximal"
            assert parsed_props.get("edge_type") == "constitutive"
            assert parsed_props.get("special_property") == "value"