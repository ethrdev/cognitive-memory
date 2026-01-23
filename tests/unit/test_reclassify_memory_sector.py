"""
Unit tests for reclassify_memory_sector MCP tool.

Story 10.1, Task 2-5: Manual reclassification of edge memory sectors.
Functional Requirements: FR5, FR6, FR7, FR8, FR10, FR26, FR27
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mcp_server.utils.constants import ReclassifyStatus
from mcp_server.utils.sector_classifier import MemorySector


class TestReclassifyMemorySectorUnit:
    """Unit tests for reclassify_memory_sector tool handler."""

    @pytest.mark.asyncio
    async def test_ac1_successful_reclassification(with_project_context):
        """Test AC1: Successful reclassification returns success status."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Mock database responses
        mock_edge = {
            "id": "uuid-123",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "KNOWS",
            "weight": 1.0,
            "properties": {},
            "memory_sector": "semantic",
            "created_at": "2026-01-08T00:00:00Z"
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                      new_callable=AsyncMock) as mock_update:
                mock_get_edges.return_value = [mock_edge]

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="Dennett-Philosophie",
                    relation="KNOWS",
                    new_sector="emotional"
                )

                assert result["status"] == ReclassifyStatus.SUCCESS
                assert result["edge_id"] == "uuid-123"
                assert result["old_sector"] == "semantic"
                assert result["new_sector"] == "emotional"
                mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_ac2_invalid_sector_validation(with_project_context):
        """Test AC2: Invalid sector returns invalid_sector status."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        result = await reclassify_memory_sector(
            source_name="I/O",
            target_name="Dennett-Philosophie",
            relation="KNOWS",
            new_sector="invalid"
        )

        assert result["status"] == ReclassifyStatus.INVALID_SECTOR
        assert "Invalid sector" in result["error"]
        assert "invalid" in result["error"]
        assert "emotional" in result["error"]  # List of valid sectors

    @pytest.mark.asyncio
    async def test_ac3_edge_not_found_error(with_project_context):
        """Test AC3: Non-existent edge returns not_found status."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            mock_get_edges.return_value = []

            result = await reclassify_memory_sector(
                source_name="X",
                target_name="Y",
                relation="Z",
                new_sector="emotional"
            )

            assert result["status"] == ReclassifyStatus.NOT_FOUND
            assert "Edge not found" in result["error"]
            assert "X --Z--> Y" in result["error"]
