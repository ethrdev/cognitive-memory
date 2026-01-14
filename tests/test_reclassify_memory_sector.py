"""
Test Reclassify Memory Sector Tool

Tests for the reclassify_memory_sector MCP tool which allows manual correction
of automatic memory sector classifications with constitutive edge protection.

Updated to test the actual async API with proper mocking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mcp_server.tools.reclassify_memory_sector import (
    reclassify_memory_sector,
    handle_reclassify_memory_sector,
    VALID_SECTORS
)
from mcp_server.utils.constants import ReclassifyStatus


class TestReclassifyMemorySector:
    """Test cases for reclassify_memory_sector function"""

    @pytest.mark.asyncio
    async def test_invalid_sector_rejected(self):
        """
        [P0] Should reject invalid sector values before any DB operation
        """
        # WHEN: Calling with invalid sector
        result = await reclassify_memory_sector(
            source_name="NodeA",
            target_name="NodeB",
            relation="KNOWS",
            new_sector="invalid_sector"
        )

        # THEN: Should return invalid sector error
        assert result["status"] == ReclassifyStatus.INVALID_SECTOR
        assert "invalid" in result["error"].lower()
        # Should list valid sectors
        for sector in VALID_SECTORS:
            assert sector in result["error"]

    @pytest.mark.asyncio
    async def test_edge_not_found(self):
        """
        [P1] Should return not_found when edge doesn't exist
        """
        # Mock _get_edges_by_names to return empty list
        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            # WHEN: Reclassifying non-existent edge
            result = await reclassify_memory_sector(
                source_name="NonExistent",
                target_name="Target",
                relation="KNOWS",
                new_sector="emotional"
            )

        # THEN: Should return not found
        assert result["status"] == ReclassifyStatus.NOT_FOUND
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_ambiguous_edges_without_edge_id(self):
        """
        [P1] Should return ambiguous when multiple edges match
        """
        # Mock multiple edges found
        mock_edges = [
            {"id": "uuid-1", "properties": {}, "memory_sector": "semantic"},
            {"id": "uuid-2", "properties": {}, "memory_sector": "semantic"},
        ]

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_edges

            # WHEN: Reclassifying without edge_id
            result = await reclassify_memory_sector(
                source_name="A",
                target_name="B",
                relation="DISCUSSED",
                new_sector="emotional"
            )

        # THEN: Should return ambiguous with edge IDs
        assert result["status"] == ReclassifyStatus.AMBIGUOUS
        assert "edge_ids" in result
        assert len(result["edge_ids"]) == 2

    @pytest.mark.asyncio
    async def test_constitutive_edge_requires_consent(self):
        """
        [P0] Should require bilateral consent for constitutive edges
        """
        # Mock constitutive edge
        mock_edge = {
            "id": "uuid-const",
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic"
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [mock_edge]

            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                       new_callable=AsyncMock) as mock_smf:
                mock_smf.return_value = {"approved": False}

                # WHEN: Reclassifying constitutive edge
                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="CREATED_BY",
                    new_sector="emotional"
                )

        # THEN: Should require consent
        assert result["status"] == ReclassifyStatus.CONSENT_REQUIRED
        assert "bilateral consent" in result["error"].lower()
        assert "hint" in result

    @pytest.mark.asyncio
    async def test_successful_reclassification(self):
        """
        [P0] Should successfully reclassify non-constitutive edge
        """
        # Mock non-constitutive edge
        mock_edge = {
            "id": "uuid-123",
            "properties": {"is_constitutive": False},
            "memory_sector": "semantic"
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [mock_edge]

            with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                       new_callable=AsyncMock) as mock_update:
                mock_update.return_value = None

                # WHEN: Reclassifying
                result = await reclassify_memory_sector(
                    source_name="A",
                    target_name="B",
                    relation="KNOWS",
                    new_sector="emotional",
                    actor="I/O"
                )

        # THEN: Should return success
        assert result["status"] == ReclassifyStatus.SUCCESS
        assert result["old_sector"] == "semantic"
        assert result["new_sector"] == "emotional"
        assert result["edge_id"] == "uuid-123"


class TestReclassifyMemorySectorHandler:
    """Test cases for the MCP tool handler wrapper"""

    @pytest.mark.asyncio
    async def test_handler_extracts_parameters_correctly(self):
        """
        [P0] Handler should correctly extract parameters from arguments dict

        Bug Fix Verification: The handler was previously missing, causing
        'missing 3 required positional arguments' error
        """
        # Mock the underlying function
        with patch('mcp_server.tools.reclassify_memory_sector.reclassify_memory_sector',
                   new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = {"status": ReclassifyStatus.SUCCESS}

            # WHEN: Calling handler with arguments dict
            arguments = {
                "source_name": "NodeA",
                "target_name": "NodeB",
                "relation": "KNOWS",
                "new_sector": "emotional",
                "actor": "ethr"
            }
            result = await handle_reclassify_memory_sector(arguments)

        # THEN: Function should be called with extracted parameters
        mock_fn.assert_called_once_with(
            source_name="NodeA",
            target_name="NodeB",
            relation="KNOWS",
            new_sector="emotional",
            edge_id=None,
            actor="ethr"
        )

    @pytest.mark.asyncio
    async def test_handler_provides_defaults(self):
        """
        [P1] Handler should provide default values for optional parameters
        """
        with patch('mcp_server.tools.reclassify_memory_sector.reclassify_memory_sector',
                   new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = {"status": ReclassifyStatus.INVALID_SECTOR}

            # WHEN: Calling with minimal arguments
            arguments = {
                "source_name": "A",
                "target_name": "B",
                "relation": "R",
                "new_sector": "invalid"
            }
            await handle_reclassify_memory_sector(arguments)

        # THEN: Should use default actor "I/O"
        call_args = mock_fn.call_args
        assert call_args.kwargs["actor"] == "I/O"
        assert call_args.kwargs["edge_id"] is None

    @pytest.mark.asyncio
    async def test_handler_passes_edge_id(self):
        """
        [P1] Handler should pass edge_id when provided
        """
        with patch('mcp_server.tools.reclassify_memory_sector.reclassify_memory_sector',
                   new_callable=AsyncMock) as mock_fn:
            mock_fn.return_value = {"status": ReclassifyStatus.SUCCESS}

            # WHEN: Calling with edge_id
            arguments = {
                "source_name": "A",
                "target_name": "B",
                "relation": "R",
                "new_sector": "emotional",
                "edge_id": "specific-uuid"
            }
            await handle_reclassify_memory_sector(arguments)

        # THEN: Should pass edge_id
        call_args = mock_fn.call_args
        assert call_args.kwargs["edge_id"] == "specific-uuid"
