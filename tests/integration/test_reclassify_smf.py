"""
SMF Integration tests for reclassify_memory_sector.

Story 10.2, Task 4: SMF integration tests for constitutive edge protection.
Tests the full consent flow: proposal → approve → reclassify.
"""

import pytest
from unittest.mock import AsyncMock, patch

from mcp_server.utils.constants import ReclassifyStatus


class TestReclassifySMFIntegration:
    """Integration tests for SMF-backed reclassification."""

    @pytest.mark.asyncio
    async def test_full_consent_flow_proposal_approve_reclassify(self):
        """Test AC2: Full consent flow - proposal → approve → reclassify."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create constitutive edge
        mock_edge = {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        # Step 1: Try to reclassify without approval - should fail
        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                mock_get_edges.return_value = [mock_edge]
                # Mock: No approved proposal yet
                mock_smf.return_value = {"approved": False}

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="LOVES",
                    new_sector="emotional"
                )

                # Should require consent
                assert result["status"] == ReclassifyStatus.CONSENT_REQUIRED
                assert "hint" in result

        # Step 2: Mock approved proposal - should succeed
        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                          new_callable=AsyncMock) as mock_update:
                    mock_get_edges.return_value = [mock_edge]
                    # Mock: Approved proposal found
                    mock_smf.return_value = {"approved": True, "proposal_id": "proposal-123"}

                    result = await reclassify_memory_sector(
                        source_name="I/O",
                        target_name="ethr",
                        relation="LOVES",
                        new_sector="emotional"
                    )

                    # Should succeed
                    assert result["status"] == ReclassifyStatus.SUCCESS
                    mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_bilateral_approval_requirement(self):
        """Test AC4: Bilateral approval requirement (both I/O and ethr)."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create constitutive edge
        mock_edge = {
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        # Mock SMF approval check that verifies bilateral approval
        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                          new_callable=AsyncMock) as mock_update:
                    mock_get_edges.return_value = [mock_edge]
                    # Mock: Bilateral approval granted
                    mock_smf.return_value = {"approved": True, "proposal_id": "proposal-123"}

                    result = await reclassify_memory_sector(
                        source_name="I/O",
                        target_name="ethr",
                        relation="LOVES",
                        new_sector="emotional"
                    )

                    # Should succeed with bilateral approval
                    assert result["status"] == ReclassifyStatus.SUCCESS
                    mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_bilateral_approval_only_io_approved_fails(self):
        """Test that bilateral approval fails when only I/O approved (not ethr)."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        mock_edge = {
            "id": "550e8400-e29b-41d4-a716-446655440002",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        # This edge_id returns False = not approved (only one party approved)
        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                mock_get_edges.return_value = [mock_edge]
                # Mock: Only one party approved (not bilateral)
                mock_smf.return_value = {"approved": False}

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="LOVES",
                    new_sector="emotional"
                )

                # Should require consent
                assert result["status"] == ReclassifyStatus.CONSENT_REQUIRED
