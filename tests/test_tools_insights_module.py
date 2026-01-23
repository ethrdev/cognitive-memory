"""
[P1] Tools - Insights Module Tests

Tests for insight tools including update, delete, feedback, and history.

Priority: P1 (High) - Insights tools are core functionality for memory management
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Import the insight tool modules
from mcp_server.tools.insights import update as insights_update
from mcp_server.tools.insights import delete as insights_delete
from mcp_server.tools.insights import feedback as insights_feedback
from mcp_server.tools.insights import history as insights_history


@pytest.mark.P1
class TestInsightsUpdate:
    """P1 tests for insight update functionality."""

    @pytest.mark.asyncio
    async def test_update_insight_success(self):
        """[P1] Update insight should successfully modify insight data."""
        # GIVEN: Valid update arguments
        arguments = {
            "insight_id": 123,
            "actor": "I/O",
            "new_content": "Updated insight content",
            "new_memory_strength": 0.8,
            "reason": "Content refinement",
        }

        # Mock the database operation
        with patch("mcp_server.tools.insights.update.get_insight_by_id") as mock_get:
            with patch("mcp_server.tools.insights.update.update_insight_db") as mock_update:
                # Setup mocks
                mock_get.return_value = {
                    "id": 123,
                    "content": "Original content",
                    "memory_strength": 0.5,
                }
                mock_update.return_value = {
                    "id": 123,
                    "content": "Updated insight content",
                    "memory_strength": 0.8,
                    "updated_at": "2024-01-14T10:00:00Z",
                }

                # WHEN: Updating insight
                result = await insights_update.handle_update_insight(arguments)

                # THEN: Should succeed
                assert result["status"] == "success"
                assert result["insight_id"] == 123
                assert result["updated_fields"] == ["content", "memory_strength"]
                mock_get.assert_called_once_with(123)
                mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_insight_not_found(self):
        """[P1] Update insight should handle non-existent insight."""
        # GIVEN: Non-existent insight ID
        arguments = {
            "insight_id": 999,
            "actor": "I/O",
            "new_content": "New content",
            "reason": "Update test",
        }

        # Mock database operation
        with patch("mcp_server.tools.insights.update.get_insight_by_id") as mock_get:
            mock_get.return_value = None

            # WHEN: Updating insight
            result = await insights_update.handle_update_insight(arguments)

            # THEN: Should return error
            assert result["status"] == "error"
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_update_insight_invalid_actor(self):
        """[P1] Update insight should validate actor."""
        # GIVEN: Invalid actor
        arguments = {
            "insight_id": 123,
            "actor": "InvalidActor",  # Not I/O or ethr
            "new_content": "New content",
            "reason": "Test",
        }

        # WHEN: Updating insight
        result = await insights_update.handle_update_insight(arguments)

        # THEN: Should reject invalid actor
        assert result["status"] == "error"
        assert "actor" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_update_insight_missing_reason(self):
        """[P1] Update insight should require reason."""
        # GIVEN: Missing reason
        arguments = {
            "insight_id": 123,
            "actor": "I/O",
            "new_content": "New content",
            # Missing reason
        }

        # WHEN: Updating insight
        result = await insights_update.handle_update_insight(arguments)

        # THEN: Should reject without reason
        assert result["status"] == "error"
        assert "reason" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_update_insight_only_strength(self):
        """[P1] Update insight should allow strength-only updates."""
        # GIVEN: Update only strength
        arguments = {
            "insight_id": 123,
            "actor": "ethr",
            "new_memory_strength": 0.9,
            "reason": "Strength adjustment",
        }

        with patch("mcp_server.tools.insights.update.get_insight_by_id") as mock_get:
            with patch("mcp_server.tools.insights.update.update_insight_db") as mock_update:
                mock_get.return_value = {"id": 123, "content": "Content"}
                mock_update.return_value = {"id": 123, "memory_strength": 0.9}

                # WHEN: Updating insight
                result = await insights_update.handle_update_insight(arguments)

                # THEN: Should succeed
                assert result["status"] == "success"
                assert result["updated_fields"] == ["memory_strength"]


@pytest.mark.P1
class TestInsightsDelete:
    """P1 tests for insight delete functionality."""

    @pytest.mark.asyncio
    async def test_delete_insight_success(self):
        """[P1] Delete insight should soft-delete insight."""
        # GIVEN: Valid delete arguments
        arguments = {
            "insight_id": 456,
            "actor": "I/O",
            "reason": "Outdated information",
        }

        with patch("mcp_server.tools.insights.delete.get_insight_by_id") as mock_get:
            with patch("mcp_server.tools.insights.delete.delete_insight_db") as mock_delete:
                mock_get.return_value = {"id": 456, "content": "Old insight"}
                mock_delete.return_value = {"deleted": True}

                # WHEN: Deleting insight
                result = await insights_delete.handle_delete_insight(arguments)

                # THEN: Should succeed
                assert result["status"] == "success"
                assert result["insight_id"] == 456
                assert result["deleted"] is True
                mock_delete.assert_called_once_with(456, "I/O", "Outdated information")

    @pytest.mark.asyncio
    async def test_delete_insight_not_found(self):
        """[P1] Delete insight should handle non-existent insight."""
        # GIVEN: Non-existent insight
        arguments = {
            "insight_id": 999,
            "actor": "ethr",
            "reason": "Test delete",
        }

        with patch("mcp_server.tools.insights.delete.get_insight_by_id") as mock_get:
            mock_get.return_value = None

            # WHEN: Deleting insight
            result = await insights_delete.handle_delete_insight(arguments)

            # THEN: Should return error
            assert result["status"] == "error"
            assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_delete_insight_requires_consent(self):
        """[P1] Delete insight should require consent for ethr actor."""
        # GIVEN: ethr actor attempting delete
        arguments = {
            "insight_id": 123,
            "actor": "ethr",
            "reason": "System cleanup",
        }

        with patch("mcp_server.tools.insights.delete.get_insight_by_id") as mock_get:
            mock_get.return_value = {"id": 123, "content": "Important insight"}

            # WHEN: Deleting insight
            result = await insights_delete.handle_delete_insight(arguments)

            # THEN: Should require consent
            assert result["status"] == "error"
            assert "consent" in result["error"].lower()


@pytest.mark.P1
class TestInsightsFeedback:
    """P1 tests for insight feedback functionality."""

    @pytest.mark.asyncio
    async def test_submit_feedback_helpful(self):
        """[P1] Submit feedback should record helpful feedback."""
        # GIVEN: Helpful feedback
        arguments = {
            "insight_id": 789,
            "feedback_type": "helpful",
            "context": "Solved my problem",
        }

        with patch("mcp_server.tools.insights.feedback.submit_feedback_db") as mock_submit:
            mock_submit.return_value = {"feedback_id": 1001, "recorded": True}

            # WHEN: Submitting feedback
            result = await insights_feedback.handle_submit_feedback(arguments)

            # THEN: Should record feedback
            assert result["status"] == "success"
            assert result["feedback_type"] == "helpful"
            assert "feedback_id" in result

    @pytest.mark.asyncio
    async def test_submit_feedback_not_relevant(self):
        """[P1] Submit feedback should record not relevant feedback."""
        # GIVEN: Not relevant feedback
        arguments = {
            "insight_id": 790,
            "feedback_type": "not_relevant",
            "context": "Not applicable to my query",
        }

        with patch("mcp_server.tools.insights.feedback.submit_feedback_db") as mock_submit:
            mock_submit.return_value = {"feedback_id": 1002, "recorded": True}

            # WHEN: Submitting feedback
            result = await insights_feedback.handle_submit_feedback(arguments)

            # THEN: Should record feedback
            assert result["status"] == "success"
            assert result["feedback_type"] == "not_relevant"

    @pytest.mark.asyncio
    async def test_submit_feedback_not_now(self):
        """[P1] Submit feedback should record not now feedback."""
        # GIVEN: Not now feedback
        arguments = {
            "insight_id": 791,
            "feedback_type": "not_now",
            "context": "Need this later",
        }

        with patch("mcp_server.tools.insights.feedback.submit_feedback_db") as mock_submit:
            mock_submit.return_value = {"feedback_id": 1003, "recorded": True}

            # WHEN: Submitting feedback
            result = await insights_feedback.handle_submit_feedback(arguments)

            # THEN: Should record feedback
            assert result["status"] == "success"
            assert result["feedback_type"] == "not_now"

    @pytest.mark.asyncio
    async def test_submit_feedback_invalid_type(self):
        """[P1] Submit feedback should reject invalid feedback types."""
        # GIVEN: Invalid feedback type
        arguments = {
            "insight_id": 792,
            "feedback_type": "invalid_type",
            "context": "Test",
        }

        # WHEN: Submitting feedback
        result = await insights_feedback.handle_submit_feedback(arguments)

        # THEN: Should reject
        assert result["status"] == "error"
        assert "feedback_type" in result["error"].lower()


@pytest.mark.P2
class TestInsightsHistory:
    """P2 tests for insight history functionality."""

    @pytest.mark.asyncio
    async def test_get_insight_history(self):
        """[P2] Get insight history should return revision history."""
        # GIVEN: Insight with history
        insight_id = 100

        with patch("mcp_server.tools.insights.history.get_insight_history_db") as mock_history:
            mock_history.return_value = [
                {
                    "version": 1,
                    "content": "Original content",
                    "memory_strength": 0.5,
                    "updated_at": "2024-01-01T10:00:00Z",
                    "actor": "I/O",
                },
                {
                    "version": 2,
                    "content": "Updated content",
                    "memory_strength": 0.7,
                    "updated_at": "2024-01-10T10:00:00Z",
                    "actor": "I/O",
                },
            ]

            # WHEN: Getting history
            result = await insights_history.handle_get_insight_history({"insight_id": insight_id})

            # THEN: Should return history
            assert result["status"] == "success"
            assert result["insight_id"] == insight_id
            assert len(result["history"]) == 2
            assert result["history"][0]["version"] == 1
            assert result["history"][1]["version"] == 2

    @pytest.mark.asyncio
    async def test_get_insight_history_not_found(self):
        """[P2] Get insight history should handle non-existent insight."""
        # GIVEN: Non-existent insight
        with patch("mcp_server.tools.insights.history.get_insight_history_db") as mock_history:
            mock_history.return_value = []

            # WHEN: Getting history
            result = await insights_history.handle_get_insight_history({"insight_id": 999})

            # THEN: Should return empty or error
            assert result["status"] == "success" or result["status"] == "error"
            assert "history" in result or "error" in result


@pytest.mark.P2
class TestInsightsIntegration:
    """P2 integration tests for insights module."""

    @pytest.mark.asyncio
    async def test_insight_lifecycle(self):
        """[P2] Complete insight lifecycle from create to delete."""
        insight_id = 500

        with patch("mcp_server.tools.insights.update.get_insight_by_id") as mock_get:
            with patch("mcp_server.tools.insights.update.update_insight_db") as mock_update:
                with patch("mcp_server.tools.insights.delete.get_insight_by_id") as mock_get_delete:
                    with patch("mcp_server.tools.insights.delete.delete_insight_db") as mock_delete:
                        # Setup mocks
                        mock_get.return_value = {"id": insight_id}
                        mock_update.return_value = {"id": insight_id, "updated": True}
                        mock_get_delete.return_value = {"id": insight_id}
                        mock_delete.return_value = {"deleted": True}

                        # WHEN: Running complete lifecycle
                        # 1. Update insight
                        update_result = await insights_update.handle_update_insight({
                            "insight_id": insight_id,
                            "actor": "I/O",
                            "new_content": "Updated",
                            "reason": "Lifecycle test",
                        })

                        # 2. Delete insight
                        delete_result = await insights_delete.handle_delete_insight({
                            "insight_id": insight_id,
                            "actor": "I/O",
                            "reason": "Lifecycle cleanup",
                        })

                        # THEN: Both should succeed
                        assert update_result["status"] == "success"
                        assert delete_result["status"] == "success"
