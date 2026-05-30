"""
Tests for insights.py database functions (CRUD + History).

Tests L2 Insight database operations including:
- execute_update_with_history: Update with atomic history write
- execute_delete_with_history: Soft-delete with atomic history write
- list_insights: Filtering and pagination
- write_insight_history: History entry helper

Story 9.2.2: list_insights MCP Tool
Story 26.2: UPDATE Operation with history
EP-3: History-on-Mutation Pattern
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from mcp_server.db.insights import (
    execute_update_with_history,
    execute_delete_with_history,
    list_insights,
    write_insight_history,
)


def _create_async_connection_mock(
    fetchone_result=None,
    fetchall_result=None,
    return_value=None
):
    """
    Helper to create a properly mocked async connection.

    psycopg2 connection is SYNC, but context manager is ASYNC.
    """
    # Sync psycopg2 cursor (DictCursor)
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_result
    mock_cursor.fetchall.return_value = fetchall_result or []
    if return_value is not None:
        mock_cursor.fetchone.return_value = return_value

    # Sync psycopg2 connection
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.commit.return_value = None

    # Async context manager wrapper
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = mock_conn
    async_cm.__aexit__.return_value = None

    return async_cm, mock_cursor


class TestExecuteUpdateWithHistory:
    """Test suite for execute_update_with_history function."""

    @patch("mcp_server.middleware.context.get_current_project", return_value="test-project")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_update_content_success(self, mock_get_conn, mock_project):
        """Test successful insight update with history."""
        # Arrange
        # First fetchone: Get current state (for history)
        # Second fetchone: History INSERT returning id
        mock_cursor = MagicMock()
        call_count = 0

        def fetchone_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": "old content",
                    "memory_strength": 0.5,
                    "project_id": "test-project",
                }
            return [123]  # history_id

        mock_cursor.fetchone.side_effect = fetchone_side_effect
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit.return_value = None

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        # Act
        result = await execute_update_with_history(
            insight_id=1,
            new_content="new content",
            actor="I/O",
            reason="Test update"
        )

        # Assert
        assert result["success"] is True
        assert result["insight_id"] == 1
        assert result["history_id"] == 123
        assert result["updated_fields"]["content"] is True
        assert result["updated_fields"]["memory_strength"] is False

    @patch("mcp_server.middleware.context.get_current_project", return_value="test-project")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_update_memory_strength_success(self, mock_get_conn, mock_project):
        """Test successful memory_strength update with history."""
        # Arrange
        mock_cursor = MagicMock()
        call_count = 0

        def fetchone_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": "test content",
                    "memory_strength": 0.5,
                    "project_id": "test-project",
                }
            return [456]  # history_id

        mock_cursor.fetchone.side_effect = fetchone_side_effect
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit.return_value = None

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        # Act
        result = await execute_update_with_history(
            insight_id=1,
            new_memory_strength=0.9,
            actor="ethr",
            reason="Improved relevance"
        )

        # Assert
        assert result["success"] is True
        assert result["updated_fields"]["content"] is False
        assert result["updated_fields"]["memory_strength"] is True

    @patch("mcp_server.middleware.context.get_current_project", return_value="test-project")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_update_both_fields(self, mock_get_conn, mock_project):
        """Test updating both content and memory_strength."""
        # Arrange
        mock_cursor = MagicMock()
        call_count = 0

        def fetchone_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": "old content",
                    "memory_strength": 0.5,
                    "project_id": "test-project",
                }
            return [789]  # history_id

        mock_cursor.fetchone.side_effect = fetchone_side_effect
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit.return_value = None

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        # Act
        result = await execute_update_with_history(
            insight_id=1,
            new_content="updated content",
            new_memory_strength=0.8,
            actor="I/O",
            reason="Full update"
        )

        # Assert
        assert result["success"] is True
        assert result["updated_fields"]["content"] is True
        assert result["updated_fields"]["memory_strength"] is True

    async def test_update_no_changes_raises_error(self):
        """Test error when neither content nor memory_strength provided."""
        # Act & Assert
        with pytest.raises(ValueError, match="no changes provided"):
            await execute_update_with_history(
                insight_id=1,
                actor="I/O",
                reason="Test"
            )

    async def test_update_no_reason_raises_error(self):
        """Test error when reason is empty."""
        # Act & Assert
        with pytest.raises(ValueError, match="reason required"):
            await execute_update_with_history(
                insight_id=1,
                new_content="test",
                actor="I/O",
                reason=""
            )

    async def test_update_empty_content_raises_error(self):
        """Test error when new_content is only whitespace."""
        # Act & Assert
        with pytest.raises(ValueError, match="new_content cannot be empty"):
            await execute_update_with_history(
                insight_id=1,
                new_content="   ",
                actor="I/O",
                reason="Test"
            )

    @patch("mcp_server.middleware.context.get_current_project", return_value="test-project")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_update_insight_not_found(self, mock_get_conn, mock_project):
        """Test error when insight doesn't exist."""
        # Arrange
        async_cm, mock_cursor = _create_async_connection_mock(None)
        mock_get_conn.return_value = async_cm

        # Act & Assert
        with pytest.raises(ValueError, match="Insight 1 not found"):
            await execute_update_with_history(
                insight_id=1,
                new_content="test",
                actor="I/O",
                reason="Test"
            )


class TestExecuteDeleteWithHistory:
    """Test suite for execute_delete_with_history function."""

    @patch("mcp_server.middleware.context.get_current_project", return_value="test-project")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_soft_delete_success(self, mock_get_conn, mock_project):
        """Test successful soft-delete with history."""
        # Arrange
        mock_cursor = MagicMock()
        call_count = 0

        def fetchone_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {
                    "content": "test content",
                    "memory_strength": 0.5,
                    "is_deleted": False,
                    "project_id": "test-project",
                }
            return [999]  # history_id

        mock_cursor.fetchone.side_effect = fetchone_side_effect
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.commit.return_value = None

        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = mock_conn
        async_cm.__aexit__.return_value = None
        mock_get_conn.return_value = async_cm

        # Act
        result = await execute_delete_with_history(
            insight_id=1,
            actor="I/O",
            reason="Test deletion"
        )

        # Assert
        assert result["success"] is True
        assert result["insight_id"] == 1
        assert result["history_id"] == 999
        assert result["status"] == "deleted"
        assert result["recoverable"] is True

    async def test_delete_no_reason_raises_error(self):
        """Test error when reason is empty."""
        # Act & Assert
        with pytest.raises(ValueError, match="reason required"):
            await execute_delete_with_history(
                insight_id=1,
                actor="I/O",
                reason=""
            )

    @patch("mcp_server.middleware.context.get_current_project", return_value="test-project")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_delete_insight_not_found(self, mock_get_conn, mock_project):
        """Test error when insight doesn't exist."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(None)
        mock_get_conn.return_value = async_cm

        # Act & Assert
        with pytest.raises(ValueError, match="Insight 1 not found"):
            await execute_delete_with_history(
                insight_id=1,
                actor="I/O",
                reason="Test"
            )

    @patch("mcp_server.middleware.context.get_current_project", return_value="test-project")
    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_delete_already_deleted_raises_error(self, mock_get_conn, mock_project):
        """Test error when insight is already deleted."""
        # Arrange
        async_cm, _ = _create_async_connection_mock({
            "content": "test content",
            "memory_strength": 0.5,
            "is_deleted": True,  # Already deleted
            "project_id": "test-project",
        })
        mock_get_conn.return_value = async_cm

        # Act & Assert
        with pytest.raises(ValueError, match="already deleted"):
            await execute_delete_with_history(
                insight_id=1,
                actor="I/O",
                reason="Test"
            )


class TestListInsights:
    """Test suite for list_insights function."""

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_basic(self, mock_get_conn):
        """Test basic insight listing without filters."""
        # Arrange
        async_cm, mock_cursor = _create_async_connection_mock(
            fetchone_result=[10],  # total_count
            fetchall_result=[
                {
                    "id": 1,
                    "content": "Insight 1",
                    "io_category": "self",
                    "is_identity": True,
                    "tags": ["test"],
                    "metadata": {"memory_sector": "semantic"},
                    "memory_strength": 0.8,
                    "created_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 2,
                    "content": "Insight 2",
                    "io_category": "ethr",
                    "is_identity": False,
                    "tags": [],
                    "metadata": {},
                    "memory_strength": 0.5,
                    "created_at": datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
                },
            ]
        )
        mock_get_conn.return_value = async_cm

        # Act
        result = await list_insights()

        # Assert
        assert len(result["insights"]) == 2
        assert result["total_count"] == 10
        assert result["limit"] == 50
        assert result["offset"] == 0
        assert result["insights"][0]["content"] == "Insight 1"
        assert result["insights"][1]["io_category"] == "ethr"

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_with_tags_filter(self, mock_get_conn):
        """Test tag filtering (AND logic)."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(
            fetchone_result=[5],
            fetchall_result=[
                {
                    "id": 1,
                    "content": "Tagged insight",
                    "io_category": "shared",
                    "is_identity": False,
                    "tags": ["relationship", "ethr"],
                    "metadata": {},
                    "memory_strength": 0.7,
                    "created_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                },
            ]
        )
        mock_get_conn.return_value = async_cm

        # Act
        result = await list_insights(tags=["relationship", "ethr"])

        # Assert
        assert len(result["insights"]) == 1
        assert result["total_count"] == 5

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_with_date_range(self, mock_get_conn):
        """Test date range filtering."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(
            fetchone_result=[3],
            fetchall_result=[
                {
                    "id": 1,
                    "content": "Recent insight",
                    "io_category": "self",
                    "is_identity": False,
                    "tags": [],
                    "metadata": {},
                    "memory_strength": 0.6,
                    "created_at": datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                },
            ]
        )
        mock_get_conn.return_value = async_cm

        # Act
        result = await list_insights(
            date_from=datetime(2025, 1, 1),
            date_to=datetime(2025, 1, 31)
        )

        # Assert
        assert len(result["insights"]) == 1
        assert result["total_count"] == 3

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_with_pagination(self, mock_get_conn):
        """Test pagination (limit and offset)."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(
            fetchone_result=[100],  # total_count
            fetchall_result=[
                {
                    "id": i,
                    "content": f"Insight {i}",
                    "io_category": "self",
                    "is_identity": False,
                    "tags": [],
                    "metadata": {},
                    "memory_strength": 0.5,
                    "created_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                }
                for i in range(11, 21)  # 10 results
            ]
        )
        mock_get_conn.return_value = async_cm

        # Act
        result = await list_insights(limit=10, offset=10)

        # Assert
        assert len(result["insights"]) == 10
        assert result["total_count"] == 100
        assert result["limit"] == 10
        assert result["offset"] == 10

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_with_io_category_filter(self, mock_get_conn):
        """Test io_category filtering."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(
            fetchone_result=[1],
            fetchall_result=[
                {
                    "id": 1,
                    "content": "Relationship insight",
                    "io_category": "relationship",
                    "is_identity": False,
                    "tags": [],
                    "metadata": {},
                    "memory_strength": 0.7,
                    "created_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                },
            ]
        )
        mock_get_conn.return_value = async_cm

        # Act
        result = await list_insights(io_category="relationship")

        # Assert
        assert len(result["insights"]) == 1
        assert result["insights"][0]["io_category"] == "relationship"

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_with_is_identity_filter(self, mock_get_conn):
        """Test is_identity filtering."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(
            fetchone_result=[5],
            fetchall_result=[
                {
                    "id": 1,
                    "content": "Identity insight",
                    "io_category": "self",
                    "is_identity": True,
                    "tags": [],
                    "metadata": {},
                    "memory_strength": 0.9,
                    "created_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                },
            ]
        )
        mock_get_conn.return_value = async_cm

        # Act
        result = await list_insights(is_identity=True)

        # Assert
        assert len(result["insights"]) == 1
        assert result["insights"][0]["is_identity"] is True

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_with_memory_sector_filter(self, mock_get_conn):
        """Test memory_sector filtering (from metadata)."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(
            fetchone_result=[3],
            fetchall_result=[
                {
                    "id": 1,
                    "content": "Semantic insight",
                    "io_category": "self",
                    "is_identity": False,
                    "tags": [],
                    "metadata": {"memory_sector": "semantic"},
                    "memory_strength": 0.7,
                    "created_at": datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                },
            ]
        )
        mock_get_conn.return_value = async_cm

        # Act
        result = await list_insights(memory_sector="semantic")

        # Assert
        assert len(result["insights"]) == 1
        assert result["insights"][0]["memory_sector"] == "semantic"

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_list_insights_empty_results(self, mock_get_conn):
        """Test empty result set."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(
            fetchone_result=[0],  # total_count
            fetchall_result=[]
        )
        mock_get_conn.return_value = async_cm

        # Act
        result = await list_insights()

        # Assert
        assert len(result["insights"]) == 0
        assert result["total_count"] == 0


class TestWriteInsightHistory:
    """Test suite for write_insight_history helper function."""

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_write_history_success(self, mock_get_conn):
        """Test successful history entry creation."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(return_value=[42])
        mock_get_conn.return_value = async_cm

        # Act
        history_id = await write_insight_history(
            insight_id=1,
            action="UPDATE",
            actor="I/O",
            old_content="old",
            new_content="new",
            old_memory_strength=0.5,
            new_memory_strength=0.8,
            reason="Test",
            project_id="test-project"
        )

        # Assert
        assert history_id == 42

    @patch("mcp_server.db.insights.get_connection_with_project_context")
    async def test_write_history_delete_action(self, mock_get_conn):
        """Test history entry for DELETE action."""
        # Arrange
        async_cm, _ = _create_async_connection_mock(return_value=[99])
        mock_get_conn.return_value = async_cm

        # Act
        history_id = await write_insight_history(
            insight_id=1,
            action="DELETE",
            actor="ethr",
            old_content="deleted content",
            new_content=None,  # DELETE has no new_content
            old_memory_strength=0.5,
            new_memory_strength=None,
            reason="No longer relevant",
            project_id="test-project"
        )

        # Assert
        assert history_id == 99
