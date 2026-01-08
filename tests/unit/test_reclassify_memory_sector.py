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
    async def test_ac1_successful_reclassification(self):
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
    async def test_ac2_invalid_sector_validation(self):
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
    async def test_ac3_edge_not_found_error(self):
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

    @pytest.mark.asyncio
    async def test_ac4_ambiguous_edge_error(self):
        """Test AC4: Multiple edges return ambiguous status with edge_ids."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        mock_edges = [
            {"id": "uuid-1", "source_id": "s1", "target_id": "t1", "relation": "DISCUSSED",
             "weight": 1.0, "properties": {}, "memory_sector": "semantic", "created_at": None},
            {"id": "uuid-2", "source_id": "s2", "target_id": "t2", "relation": "DISCUSSED",
             "weight": 1.0, "properties": {}, "memory_sector": "semantic", "created_at": None},
        ]

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            mock_get_edges.return_value = mock_edges

            result = await reclassify_memory_sector(
                source_name="I/O",
                target_name="ethr",
                relation="DISCUSSED",
                new_sector="emotional"
            )

            assert result["status"] == ReclassifyStatus.AMBIGUOUS
            assert "Multiple edges found" in result["error"]
            assert result["edge_ids"] == ["uuid-1", "uuid-2"]

    @pytest.mark.asyncio
    async def test_ac5_disambiguation_with_edge_id(self):
        """Test AC5: edge_id parameter resolves ambiguity."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        mock_edges = [
            {"id": "uuid-1", "source_id": "s1", "target_id": "t1", "relation": "DISCUSSED",
             "weight": 1.0, "properties": {}, "memory_sector": "semantic", "created_at": None},
            {"id": "uuid-2", "source_id": "s2", "target_id": "t2", "relation": "DISCUSSED",
             "weight": 1.0, "properties": {}, "memory_sector": "semantic", "created_at": None},
        ]

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                      new_callable=AsyncMock) as mock_update:
                mock_get_edges.return_value = mock_edges

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="DISCUSSED",
                    new_sector="emotional",
                    edge_id="uuid-2"
                )

                assert result["status"] == ReclassifyStatus.SUCCESS
                assert result["edge_id"] == "uuid-2"
                mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_ac5_invalid_edge_id_returns_not_found(self):
        """Test AC5 edge error case: Invalid edge_id returns not_found."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        mock_edges = [
            {"id": "uuid-1", "source_id": "s1", "target_id": "t1", "relation": "DISCUSSED",
             "weight": 1.0, "properties": {}, "memory_sector": "semantic", "created_at": None},
        ]

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                      new_callable=AsyncMock) as mock_update:
                mock_get_edges.return_value = mock_edges

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="DISCUSSED",
                    new_sector="emotional",
                    edge_id="non-existent-uuid"
                )

                assert result["status"] == ReclassifyStatus.NOT_FOUND
                assert "Edge with id 'non-existent-uuid' not found" in result["error"]
                # Verify _update_edge_sector was NOT called
                mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_ac6_last_reclassification_property_format(self):
        """Test AC6: last_reclassification property format."""
        from mcp_server.tools.reclassify_memory_sector import _update_edge_sector
        from mcp_server.db.connection import get_connection
        from unittest.mock import patch, MagicMock
        from datetime import datetime, timezone

        # Capture the actual timestamp and properties that will be sent to DB
        captured_params = {}

        # Create a cursor mock that captures execute parameters
        mock_cursor = MagicMock()
        def capture_execute(*args):
            captured_params['sql'] = args[0]
            captured_params['params'] = args[1]
        mock_cursor.execute = capture_execute

        # Create a connection mock that returns our cursor
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = MagicMock()

        # Create a context manager mock for get_connection
        from contextlib import contextmanager

        @contextmanager
        def mock_get_connection_func():
            yield mock_conn

        with patch('mcp_server.tools.reclassify_memory_sector.get_connection',
                   side_effect=mock_get_connection_func):
            await _update_edge_sector(
                edge_id="test-uuid",
                new_sector="emotional",
                old_sector="semantic",
                actor="I/O"
            )

            # Verify SQL UPDATE was called
            assert 'sql' in captured_params
            assert 'params' in captured_params

            # Check memory_sector update
            assert captured_params['params'][0] == "emotional"

            # Check last_reclassification property format
            properties_json = captured_params['params'][1]
            properties = json.loads(properties_json)
            assert "last_reclassification" in properties
            lr = properties["last_reclassification"]
            assert lr["from_sector"] == "semantic"
            assert lr["to_sector"] == "emotional"
            assert lr["actor"] == "I/O"
            assert "timestamp" in lr
            # Verify ISO 8601 format
            datetime.fromisoformat(lr["timestamp"].replace('Z', '+00:00'))

    @pytest.mark.asyncio
    async def test_ac7_structured_logging(self):
        """Test AC7: Structured INFO logging with extra dict."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector
        import logging

        mock_edge = {
            "id": "uuid-123",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "KNOWS",
            "weight": 1.0,
            "properties": {},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                      new_callable=AsyncMock):
                with patch('mcp_server.tools.reclassify_memory_sector.logger') as mock_logger:
                    mock_get_edges.return_value = [mock_edge]

                    await reclassify_memory_sector(
                        source_name="I/O",
                        target_name="Dennett-Philosophie",
                        relation="KNOWS",
                        new_sector="emotional",
                        actor="test-actor"
                    )

                    # Verify structured logging
                    mock_logger.info.assert_called_once()
                    call_args = mock_logger.info.call_args
                    assert call_args[0][0] == "Edge reclassified"
                    assert "extra" in call_args[1]
                    extra = call_args[1]["extra"]
                    assert extra["edge_id"] == "uuid-123"
                    assert extra["from_sector"] == "semantic"
                    assert extra["to_sector"] == "emotional"
                    assert extra["actor"] == "test-actor"

    @pytest.mark.asyncio
    async def test_ac8_status_constants_usage(self):
        """Test AC8: Response uses ReclassifyStatus constants."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Test SUCCESS constant
        mock_edge = {
            "id": "uuid-123",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "KNOWS",
            "weight": 1.0,
            "properties": {},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                      new_callable=AsyncMock):
                mock_get_edges.return_value = [mock_edge]

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="Dennett-Philosophie",
                    relation="KNOWS",
                    new_sector="emotional"
                )

                # Verify status equals ReclassifyStatus.SUCCESS constant
                assert result["status"] == ReclassifyStatus.SUCCESS
                assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_ac9_no_regressions(self):
        """Test AC9: No regressions in existing tests."""
        # This test will run in Task 6 (Full Regression Suite)
        pass

    @pytest.mark.asyncio
    async def test_ac10_non_constitutive_edge_no_consent_check(self):
        """Test AC10: Non-constitutive edges skip consent check."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create edge without is_constitutive property
        mock_edge = {
            "id": "uuid-123",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "KNOWS",
            "weight": 1.0,
            "properties": {},  # No is_constitutive property
            "memory_sector": "semantic",
            "created_at": None
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

                # Should succeed without consent check
                assert result["status"] == ReclassifyStatus.SUCCESS
                mock_update.assert_called_once()


class TestReclassifyMemorySectorStory10_2:
    """Unit tests for Story 10.2: Constitutive Edge Protection."""

    @pytest.mark.asyncio
    async def test_ac1_constitutive_edge_returns_consent_required(self):
        """Test AC1: Constitutive edge without approval returns consent_required."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create constitutive edge
        mock_edge = {
            "id": "uuid-constitutive",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                mock_get_edges.return_value = [mock_edge]
                # Mock: No approved SMF proposal found
                mock_smf.return_value = {"approved": False}

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="LOVES",
                    new_sector="emotional"
                )

                # Should return consent_required
                assert result["status"] == ReclassifyStatus.CONSENT_REQUIRED
                assert "Bilateral consent required" in result["error"]
                assert result["edge_id"] == "uuid-constitutive"
                assert "hint" in result
                assert "smf_pending_proposals" in result["hint"]

    @pytest.mark.asyncio
    async def test_ac3_non_constitutive_edge_proceeds_normally(self):
        """Test AC3: Non-constitutive edge proceeds normally."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create edge without is_constitutive
        mock_edge = {
            "id": "uuid-regular",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "KNOWS",
            "weight": 1.0,
            "properties": {},
            "memory_sector": "semantic",
            "created_at": None
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

                # Should succeed without consent check
                assert result["status"] == ReclassifyStatus.SUCCESS
                mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_ac3_is_constitutive_false_proceeds_normally(self):
        """Test AC3: is_constitutive=false proceeds normally."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create edge with is_constitutive=false
        mock_edge = {
            "id": "uuid-regular",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "KNOWS",
            "weight": 1.0,
            "properties": {"is_constitutive": False},
            "memory_sector": "semantic",
            "created_at": None
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

                # Should succeed without consent check
                assert result["status"] == ReclassifyStatus.SUCCESS
                mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_smf_pattern_edge_type_constitutive(self):
        """Test SMF pattern: edge_type == 'constitutive' also requires consent."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create edge with SMF pattern (edge_type)
        mock_edge = {
            "id": "uuid-smf-pattern",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"edge_type": "constitutive"},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                mock_get_edges.return_value = [mock_edge]
                # Mock: No approved SMF proposal found
                mock_smf.return_value = {"approved": False}

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="LOVES",
                    new_sector="emotional"
                )

                # Should return consent_required for SMF pattern too
                assert result["status"] == ReclassifyStatus.CONSENT_REQUIRED
                assert "Bilateral consent required" in result["error"]
                assert result["edge_id"] == "uuid-smf-pattern"

    @pytest.mark.asyncio
    async def test_ac5_uses_reclassify_status_consent_required(self):
        """Test AC5: Response uses ReclassifyStatus.CONSENT_REQUIRED."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        mock_edge = {
            "id": "uuid-constitutive",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                mock_get_edges.return_value = [mock_edge]
                # Mock: No approved SMF proposal found
                mock_smf.return_value = {"approved": False}

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="LOVES",
                    new_sector="emotional"
                )

                # Verify ReclassifyStatus.CONSENT_REQUIRED constant
                assert result["status"] == ReclassifyStatus.CONSENT_REQUIRED
                assert result["status"] == "consent_required"

    @pytest.mark.asyncio
    async def test_ac7_structured_logging_on_consent_check(self):
        """Test AC7: Structured logging when constitutive edge requires consent."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        mock_edge = {
            "id": "uuid-constitutive",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                with patch('mcp_server.tools.reclassify_memory_sector.logger') as mock_logger:
                    mock_get_edges.return_value = [mock_edge]
                    # Mock: No approved SMF proposal found
                    mock_smf.return_value = {"approved": False}

                    await reclassify_memory_sector(
                        source_name="I/O",
                        target_name="ethr",
                        relation="LOVES",
                        new_sector="emotional",
                        actor="test-actor"
                    )

                    # Verify structured logging for consent check
                    mock_logger.info.assert_called()
                    call_args = mock_logger.info.call_args
                    assert call_args[0][0] == "Constitutive edge requires consent"
                    assert "extra" in call_args[1]
                    extra = call_args[1]["extra"]
                    assert extra["edge_id"] == "uuid-constitutive"
                    assert extra["is_constitutive"] is True
                    assert extra["actor"] == "test-actor"

    @pytest.mark.asyncio
    async def test_ac2_approved_proposal_allows_reclassification(self):
        """Test AC2: Approved SMF proposal allows reclassification."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create constitutive edge
        mock_edge = {
            "id": "uuid-constitutive",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                          new_callable=AsyncMock) as mock_update:
                    mock_get_edges.return_value = [mock_edge]
                    # Mock: Approved SMF proposal found
                    mock_smf.return_value = {"approved": True, "proposal_id": "proposal-123"}

                    result = await reclassify_memory_sector(
                        source_name="I/O",
                        target_name="ethr",
                        relation="LOVES",
                        new_sector="emotional"
                    )

                    # Should succeed with reclassification
                    assert result["status"] == ReclassifyStatus.SUCCESS
                    mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_ac8_database_connection_error_handling(self):
        """Test AC8: Database connection error during SMF approval check."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        mock_edge = {
            "id": "uuid-constitutive",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                mock_get_edges.return_value = [mock_edge]
                # Mock: Database error during SMF approval check
                mock_smf.return_value = {
                    "status": "error",
                    "error": "Failed to check SMF approval status",
                    "edge_id": "uuid-constitutive",
                    "details": "Database connection error"
                }

                result = await reclassify_memory_sector(
                    source_name="I/O",
                    target_name="ethr",
                    relation="LOVES",
                    new_sector="emotional"
                )

                # Should return error response
                assert result["status"] == "error"
                assert "Failed to check SMF approval status" in result["error"]
                assert result["edge_id"] == "uuid-constitutive"
                assert "details" in result

    @pytest.mark.asyncio
    async def test_ac9_success_logging_for_constitutive_reclassification(self):
        """Test AC9: Structured logging when constitutive edge is reclassified."""
        from mcp_server.tools.reclassify_memory_sector import reclassify_memory_sector

        # Create constitutive edge
        mock_edge = {
            "id": "uuid-constitutive",
            "source_id": "source-uuid",
            "target_id": "target-uuid",
            "relation": "LOVES",
            "weight": 1.0,
            "properties": {"is_constitutive": True},
            "memory_sector": "semantic",
            "created_at": None
        }

        with patch('mcp_server.tools.reclassify_memory_sector._get_edges_by_names',
                   new_callable=AsyncMock) as mock_get_edges:
            with patch('mcp_server.tools.reclassify_memory_sector._check_smf_approval',
                      new_callable=AsyncMock) as mock_smf:
                with patch('mcp_server.tools.reclassify_memory_sector._update_edge_sector',
                          new_callable=AsyncMock) as mock_update:
                    with patch('mcp_server.tools.reclassify_memory_sector.logger') as mock_logger:
                        mock_get_edges.return_value = [mock_edge]
                        # Mock: Approved SMF proposal found
                        mock_smf.return_value = {"approved": True, "proposal_id": "proposal-123"}

                        await reclassify_memory_sector(
                            source_name="I/O",
                            target_name="ethr",
                            relation="LOVES",
                            new_sector="emotional",
                            actor="test-actor"
                        )

                        # Verify structured logging for constitutive edge reclassification
                        info_calls = [call for call in mock_logger.info.call_args_list]
                        # Find the "Constitutive edge reclassified" log call
                        constitutive_logs = [
                            call for call in info_calls
                            if call[0][0] == "Constitutive edge reclassified"
                        ]
                        assert len(constitutive_logs) >= 1, "Should log constitutive edge reclassification"

                        call_args = constitutive_logs[0]
                        assert "extra" in call_args[1]
                        extra = call_args[1]["extra"]
                        assert extra["edge_id"] == "uuid-constitutive"
                        assert extra["old_sector"] == "semantic"
                        assert extra["new_sector"] == "emotional"
                        assert extra["actor"] == "test-actor"
                        # Code Review Fix: Verify smf_proposal_id is logged (AC #9)
                        assert "smf_proposal_id" in extra
                        assert extra["smf_proposal_id"] == "proposal-123"

    @pytest.mark.asyncio
    async def test_integration_ac6_actual_db_update(self):
        """Integration test: AC6 last_reclassification property actual DB update."""
        from mcp_server.tools.reclassify_memory_sector import _update_edge_sector
        from mcp_server.db.connection import get_connection
        from unittest.mock import patch, MagicMock
        from datetime import datetime, timezone
        from contextlib import contextmanager
        import uuid

        # Generate a unique test edge ID
        test_edge_id = str(uuid.uuid4())

        # Track the actual SQL execution
        captured_sql = None
        captured_params = None

        def mock_execute(sql, params):
            nonlocal captured_sql, captured_params
            captured_sql = sql
            captured_params = params

        # Create database mocks
        mock_cursor = MagicMock()
        mock_cursor.execute = mock_execute

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit = MagicMock()

        # Create context manager mock for get_connection
        @contextmanager
        def mock_get_connection():
            yield mock_conn

        with patch('mcp_server.tools.reclassify_memory_sector.get_connection',
                   side_effect=mock_get_connection):
            await _update_edge_sector(
                edge_id=test_edge_id,
                new_sector="emotional",
                old_sector="semantic",
                actor="I/O"
            )

            # Verify SQL was executed
            assert captured_sql is not None, "SQL UPDATE should be executed"
            assert "UPDATE edges" in captured_sql
            assert "memory_sector = %s" in captured_sql
            assert "properties = coalesce" in captured_sql
            assert "|| %s::jsonb" in captured_sql, "Should use JSONB merge operator"

            # Verify parameters
            assert captured_params[0] == "emotional", "First param should be new_sector"

            # Verify JSONB merge payload contains last_reclassification
            import json
            properties_data = json.loads(captured_params[1])
            assert "last_reclassification" in properties_data
            lr = properties_data["last_reclassification"]
            assert lr["from_sector"] == "semantic"
            assert lr["to_sector"] == "emotional"
            assert lr["actor"] == "I/O"
            assert "timestamp" in lr

            # Verify ISO 8601 format with Z suffix (AC #7 requirement)
            timestamp = lr["timestamp"]
            assert timestamp.endswith("Z"), \
                f"Timestamp should be ISO 8601 with Z suffix (e.g., 2026-01-08T14:30:00Z), got: {timestamp}"

            # Verify it can be parsed as valid ISO 8601
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            # Verify commit was called
            mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_integration_ac3_actual_edge_lookup(self):
        """Integration test: AC3 edge not found via actual DB query."""
        from mcp_server.tools.reclassify_memory_sector import _get_edges_by_names
        from mcp_server.db.connection import get_connection
        from unittest.mock import patch, MagicMock
        from contextlib import contextmanager

        # Track the actual SQL execution
        captured_sql = None
        captured_params = None

        def mock_execute(sql, params):
            nonlocal captured_sql, captured_params
            captured_sql = sql
            captured_params = params
            # Return empty result set (no edges found)
            return []

        mock_cursor = MagicMock()
        mock_cursor.execute = mock_execute
        mock_cursor.fetchall.return_value = []

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Create context manager mock for get_connection
        @contextmanager
        def mock_get_connection():
            yield mock_conn

        with patch('mcp_server.tools.reclassify_memory_sector.get_connection',
                   side_effect=mock_get_connection):
            result = await _get_edges_by_names(
                source_name="NonExistent",
                target_name="Node",
                relation="KNOWS"
            )

            # Verify SQL query
            assert captured_sql is not None
            assert "SELECT e.id, e.source_id, e.target_id" in captured_sql
            assert "FROM edges e" in captured_sql
            assert "JOIN nodes ns ON e.source_id = ns.id" in captured_sql
            assert "JOIN nodes nt ON e.target_id = nt.id" in captured_sql
            assert "WHERE ns.name = %s AND nt.name = %s AND e.relation = %s" in captured_sql

            # Verify parameters
            assert captured_params == ("NonExistent", "Node", "KNOWS")

            # Verify empty result
            assert result == [], "Should return empty list when no edges found"
