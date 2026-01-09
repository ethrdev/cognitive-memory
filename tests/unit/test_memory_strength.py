"""
Unit Tests for Memory Strength Feature (Story 26.1)

Tests the memory_strength parameter validation and backward compatibility
for compress_to_l2_insight tool.

Author: Epic 26 Implementation
Story: 26.1 - Memory Strength Field für I/O's Bedeutungszuweisung
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server.tools import handle_compress_to_l2_insight


class TestMemoryStrengthValidation:
    """Test memory_strength parameter validation."""

    @pytest.mark.asyncio
    async def test_memory_strength_valid_range(self):
        """Test that valid memory_strength values are accepted."""
        # Mock OpenAI client (module-level import)
        with patch("mcp_server.tools.OpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            # Mock embedding generation (module-level import)
            with patch(
                "mcp_server.tools.get_embedding_with_retry",
                return_value=[0.1] * 1536
            ):
                # Mock database connection (module-level import)
                with patch("mcp_server.tools.get_connection") as mock_get_conn, \
                     patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_conn.cursor.return_value = mock_cursor
                    mock_cursor.fetchone.return_value = {
                        "id": 1,
                        "created_at": MagicMock(isoformat=lambda: "2026-01-09T00:00:00Z"),
                        "memory_strength": 0.5  # Include in mock response
                    }
                    mock_get_conn.return_value.__enter__.return_value = mock_conn

                    # Test valid memory_strength values
                    for strength in [0.0, 0.5, 1.0, 0.3, 0.7, 0.99]:
                        result = await handle_compress_to_l2_insight({
                            "content": "Test insight",
                            "source_ids": [1, 2, 3],
                            "memory_strength": strength
                        })

                        assert "error" not in result, f"Valid strength {strength} should not error"
                        assert result["memory_strength"] == strength

    @pytest.mark.asyncio
    async def test_memory_strength_invalid_too_high(self):
        """Test that values > 1.0 are rejected."""
        result = await handle_compress_to_l2_insight({
            "content": "Test insight",
            "source_ids": [1, 2, 3],
            "memory_strength": 1.5  # INVALID
        })

        assert "error" in result
        assert "memory_strength must be between 0.0 and 1.0" in result["details"]

    @pytest.mark.asyncio
    async def test_memory_strength_invalid_too_low(self):
        """Test that values < 0.0 are rejected."""
        result = await handle_compress_to_l2_insight({
            "content": "Test insight",
            "source_ids": [1, 2, 3],
            "memory_strength": -0.1  # INVALID
        })

        assert "error" in result
        assert "memory_strength must be between 0.0 and 1.0" in result["details"]

    @pytest.mark.asyncio
    async def test_memory_strength_default_on_missing(self):
        """Test backward compatibility - missing parameter uses 0.5."""
        # Mock OpenAI client (module-level import)
        with patch("mcp_server.tools.OpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            # Mock embedding generation (module-level import)
            with patch(
                "mcp_server.tools.get_embedding_with_retry",
                return_value=[0.1] * 1536
            ):
                # Mock database connection (module-level import)
                with patch("mcp_server.tools.get_connection") as mock_get_conn, \
                     patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_conn.cursor.return_value = mock_cursor
                    mock_cursor.fetchone.return_value = {
                        "id": 1,
                        "created_at": MagicMock(isoformat=lambda: "2026-01-09T00:00:00Z"),
                        "memory_strength": 0.5  # Include in mock response
                    }
                    mock_get_conn.return_value.__enter__.return_value = mock_conn

                    # Call without memory_strength parameter
                    result = await handle_compress_to_l2_insight({
                        "content": "Test insight",
                        "source_ids": [1, 2, 3]
                    })

                    assert "error" not in result
                    assert result["memory_strength"] == 0.5  # Default value

    @pytest.mark.asyncio
    async def test_memory_strength_explicit_none_uses_default(self):
        """Test that explicit None uses default 0.5."""
        # Mock OpenAI client (module-level import)
        with patch("mcp_server.tools.OpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            # Mock embedding generation (module-level import)
            with patch(
                "mcp_server.tools.get_embedding_with_retry",
                return_value=[0.1] * 1536
            ):
                # Mock database connection (module-level import)
                with patch("mcp_server.tools.get_connection") as mock_get_conn, \
                     patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_conn.cursor.return_value = mock_cursor
                    mock_cursor.fetchone.return_value = {
                        "id": 1,
                        "created_at": MagicMock(isoformat=lambda: "2026-01-09T00:00:00Z"),
                        "memory_strength": 0.5  # Include in mock response
                    }
                    mock_get_conn.return_value.__enter__.return_value = mock_conn

                    # Call with memory_strength=None
                    result = await handle_compress_to_l2_insight({
                        "content": "Test insight",
                        "source_ids": [1, 2, 3],
                        "memory_strength": None
                    })

                    assert "error" not in result
                    assert result["memory_strength"] == 0.5  # Default value

    @pytest.mark.asyncio
    async def test_memory_strength_in_metadata(self):
        """Test that memory_strength is included in metadata."""
        # Mock OpenAI client (module-level import)
        with patch("mcp_server.tools.OpenAI") as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client

            # Mock embedding generation (module-level import)
            with patch(
                "mcp_server.tools.get_embedding_with_retry",
                return_value=[0.1] * 1536
            ):
                # Mock database connection (module-level import)
                with patch("mcp_server.tools.get_connection") as mock_get_conn, \
                     patch("mcp_server.tools.register_vector"):  # Mock pgvector registration
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_conn.cursor.return_value = mock_cursor
                    mock_cursor.fetchone.return_value = {
                        "id": 1,
                        "created_at": MagicMock(isoformat=lambda: "2026-01-09T00:00:00Z"),
                        "memory_strength": 0.8  # Match test input
                    }
                    mock_get_conn.return_value.__enter__.return_value = mock_conn

                    # Call with memory_strength=0.8
                    result = await handle_compress_to_l2_insight({
                        "content": "Test insight",
                        "source_ids": [1, 2, 3],
                        "memory_strength": 0.8
                    })

                    assert "error" not in result

                    # Verify INSERT was called with memory_strength
                    assert mock_cursor.execute.called
                    call_args = mock_cursor.execute.call_args
                    sql = call_args[0][0]
                    params = call_args[0][1]

                    # Verify SQL includes memory_strength column
                    assert "memory_strength" in sql
                    # Verify params includes memory_strength value
                    assert params[4] == 0.8  # 5th parameter (after content, embedding, source_ids, metadata)
