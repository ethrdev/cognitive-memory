"""
Test Dissonance Check Tool

Tests for the dissonance_check MCP tool which detects conflicts between edges.
Updated to test the actual async API with proper mocking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mcp_server.analysis.dissonance import DissonanceEngine, DissonanceType, DissonanceCheckResult


class TestDissonanceEngine:
    """Test cases for DissonanceEngine"""

    def test_init_is_synchronous(self):
        """
        [P0] DissonanceEngine.__init__ must be synchronous (not async)

        Bug Fix Verification: async def __init__ was causing
        '__init__() should return None, not coroutine' error
        """
        # WHEN: Creating DissonanceEngine instance
        with patch('mcp_server.analysis.dissonance.HaikuClient'):
            engine = DissonanceEngine()

        # THEN: Should return instance directly, not a coroutine
        assert isinstance(engine, DissonanceEngine)
        assert hasattr(engine, 'haiku_client')

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_status(self):
        """
        [P1] Should return insufficient_data status when < 2 edges found
        """
        # GIVEN: Engine with mocked dependencies
        with patch('mcp_server.analysis.dissonance.HaikuClient'):
            engine = DissonanceEngine()

        # Mock _fetch_edges to return only 1 edge
        engine._fetch_edges = MagicMock(return_value=[{"id": "edge-1"}])

        # Mock get_connection as async context manager
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": "node-uuid"}

        mock_conn_instance = MagicMock()
        mock_conn_instance.cursor.return_value = mock_cursor

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn_instance
        async_cm.__aexit__.return_value = None

        with patch('mcp_server.analysis.dissonance.get_connection', return_value=async_cm):
            # WHEN: Running dissonance check
            result = await engine.dissonance_check("TestNode", "recent")

        # THEN: Should return insufficient_data status
        assert result.status == "insufficient_data"
        assert result.edges_analyzed == 1
        assert result.conflicts_found == 0

    @pytest.mark.asyncio
    async def test_valid_scope_values(self):
        """
        [P1] Should accept 'recent' and 'full' scope values
        """
        with patch('mcp_server.analysis.dissonance.HaikuClient'):
            engine = DissonanceEngine()

        # Mock for valid scope check
        engine._fetch_edges = MagicMock(return_value=[])

        # Mock get_connection as async context manager
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        mock_conn_instance = MagicMock()
        mock_conn_instance.cursor.return_value = mock_cursor

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn_instance
        async_cm.__aexit__.return_value = None

        with patch('mcp_server.analysis.dissonance.get_connection', return_value=async_cm):
            # WHEN/THEN: 'recent' scope should work
            result = await engine.dissonance_check("Node", "recent")
            assert result.status == "insufficient_data"

            # WHEN/THEN: 'full' scope should work
            result = await engine.dissonance_check("Node", "full")
            assert result.status == "insufficient_data"

    @pytest.mark.asyncio
    async def test_invalid_scope_raises_error(self):
        """
        [P1] Should raise ValueError for invalid scope
        """
        with patch('mcp_server.analysis.dissonance.HaikuClient'):
            engine = DissonanceEngine()

        # WHEN/THEN: Invalid scope should raise ValueError
        with pytest.raises(ValueError, match="Invalid scope"):
            await engine.dissonance_check("Node", "invalid_scope")

    @pytest.mark.asyncio
    async def test_node_not_found_returns_insufficient_data(self):
        """
        [P1] Should return insufficient_data when node doesn't exist
        """
        with patch('mcp_server.analysis.dissonance.HaikuClient'):
            engine = DissonanceEngine()

        # Mock get_connection as async context manager
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # Node not found

        mock_conn_instance = MagicMock()
        mock_conn_instance.cursor.return_value = mock_cursor

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn_instance
        async_cm.__aexit__.return_value = None

        with patch('mcp_server.analysis.dissonance.get_connection', return_value=async_cm):
            # WHEN: Checking dissonance for non-existent node
            result = await engine.dissonance_check("NonExistentNode", "recent")

        # THEN: Should return insufficient_data
        assert result.status == "insufficient_data"
        assert result.edges_analyzed == 0


class TestDissonanceCheckHandler:
    """Test cases for the MCP tool handler"""

    @pytest.mark.asyncio
    async def test_handler_calls_engine_correctly(self):
        """
        [P1] Handler should correctly instantiate engine and call dissonance_check
        """
        from mcp_server.tools.dissonance_check import handle_dissonance_check

        # Mock the DissonanceEngine
        mock_result = DissonanceCheckResult(
            context_node="TestNode",
            scope="recent",
            edges_analyzed=0,
            conflicts_found=0,
            dissonances=[],
            pending_reviews=[],
            status="insufficient_data"
        )

        with patch('mcp_server.tools.dissonance_check.DissonanceEngine') as MockEngine:
            mock_engine_instance = MagicMock()
            mock_engine_instance.dissonance_check = AsyncMock(return_value=mock_result)
            MockEngine.return_value = mock_engine_instance

            # WHEN: Calling handler
            result = await handle_dissonance_check(
                server=MagicMock(),
                context_node="TestNode",
                scope="recent"
            )

        # THEN: Should return TextContent list
        assert len(result) == 1
        assert "insufficient_data" in result[0].text.lower() or "unzureichende" in result[0].text.lower()
