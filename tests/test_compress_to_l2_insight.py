"""
Unit tests for compress_to_l2_insight tool.

Tests OpenAI embeddings integration, semantic fidelity check, and database storage.
"""

import json
import os
from unittest.mock import Mock, patch

import pytest

from mcp_server.db.connection import get_connection
from mcp_server.tools import calculate_fidelity, handle_compress_to_l2_insight


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_data():
    """Clean up test data after each test."""
    yield
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Delete test insights created during tests
            cursor.execute("DELETE FROM l2_insights WHERE content LIKE 'test_%'")
            conn.commit()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.data = [Mock()]
    mock_response.data[0].embedding = [0.1] * 1536  # 1536-dimensional test embedding
    mock_client.embeddings.create.return_value = mock_response
    return mock_client


class TestCalculateFidelity:
    """Test semantic fidelity calculation."""

    def test_high_density_content(self):
        """Test content with high semantic density (>0.5)."""
        content = "Machine learning algorithms analyze complex mathematical patterns efficiently"
        fidelity = calculate_fidelity(content)
        assert fidelity > 0.5, f"Expected fidelity >0.5, got {fidelity}"
        assert fidelity <= 1.0, f"Fidelity should be <=1.0, got {fidelity}"

    def test_low_density_content(self):
        """Test content with low semantic density (<0.5)."""
        content = "this is a test that has many words but not much meaning at all"
        fidelity = calculate_fidelity(content)
        assert fidelity < 0.5, f"Expected fidelity <0.5, got {fidelity}"
        assert fidelity >= 0.0, f"Fidelity should be >=0.0, got {fidelity}"

    def test_empty_content(self):
        """Test empty content returns 0.0."""
        assert calculate_fidelity("") == 0.0
        assert calculate_fidelity("   ") == 0.0
        assert calculate_fidelity(None) == 0.0

    def test_single_word(self):
        """Test single semantic word."""
        content = "algorithm"
        fidelity = calculate_fidelity(content)
        assert fidelity == 1.0, f"Single word should have fidelity 1.0, got {fidelity}"

    def test_stop_words_filtering(self):
        """Test that stop words are properly filtered."""
        content = "the machine learning algorithm processes data"
        fidelity = calculate_fidelity(content)
        # Only "machine", "learning", "algorithm", "processes", "data" should count
        # 5 semantic words / 6 total words = 0.833...
        expected = 5 / 6
        assert (
            abs(fidelity - expected) < 0.1
        ), f"Expected ~{expected:.3f}, got {fidelity}"

    def test_german_stop_words(self):
        """Test that German stop words are properly filtered."""
        content = "der machine learning algorithm"
        fidelity = calculate_fidelity(content)
        # Only "machine", "learning", "algorithm" should count
        # 3 semantic words / 4 total words = 0.75
        expected = 3 / 4
        assert (
            abs(fidelity - expected) < 0.1
        ), f"Expected ~{expected:.3f}, got {fidelity}"


@pytest.mark.asyncio
class TestHandleCompressToL2Insight:
    """Test compress_to_l2_insight tool implementation."""

    @pytest.fixture
    def valid_args(self):
        """Valid tool arguments."""
        return {
            "content": "test_discussion about artificial intelligence and machine learning algorithms",
            "source_ids": [1, 2, 3],
        }

    async def test_valid_embedding_generation(self, mock_openai_client, valid_args):
        """Test successful embedding generation with valid inputs."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                with patch(
                    "mcp_server.tools.get_embedding_with_retry",
                    return_value=[0.1] * 1536,
                ):
                    result = await handle_compress_to_l2_insight(valid_args)

                    assert "error" not in result, f"Unexpected error: {result}"
                    assert "id" in result, "Response should contain insight ID"
                    assert (
                        "embedding_status" in result
                    ), "Response should contain embedding status"
                    assert (
                        "fidelity_score" in result
                    ), "Response should contain fidelity score"
                    assert "timestamp" in result, "Response should contain timestamp"

                    assert isinstance(result["id"], int), "ID should be integer"
                    assert result["embedding_status"] in [
                        "success",
                        "retried",
                    ], "Invalid embedding status"
                    assert (
                        0.0 <= result["fidelity_score"] <= 1.0
                    ), "Fidelity score out of range"

    async def test_missing_content_parameter(self):
        """Test error handling for missing content parameter."""
        args = {"source_ids": [1, 2, 3]}
        result = await handle_compress_to_l2_insight(args)

        assert "error" in result, "Should return error"
        assert "content" in result["details"], "Error should mention content parameter"
        assert result["tool"] == "compress_to_l2_insight"

    async def test_invalid_content_type(self):
        """Test error handling for invalid content type."""
        args = {"content": 123, "source_ids": [1, 2, 3]}
        result = await handle_compress_to_l2_insight(args)

        assert "error" in result, "Should return error"
        assert "content" in result["details"], "Error should mention content parameter"

    async def test_missing_source_ids_parameter(self):
        """Test error handling for missing source_ids parameter (None)."""
        args = {"content": "test content"}
        result = await handle_compress_to_l2_insight(args)

        assert "error" in result, "Should return error"
        assert (
            "source_ids" in result["details"]
        ), "Error should mention source_ids parameter"

    async def test_empty_source_ids_array_accepted(self, mock_openai_client):
        """Test that empty source_ids array [] is accepted (Bugfix: AC-1)."""
        args = {
            "content": "test_insight from external source without raw dialogue",
            "source_ids": [],  # Empty array - should be valid!
        }

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                with patch(
                    "mcp_server.tools.get_embedding_with_retry",
                    return_value=[0.1] * 1536,
                ):
                    result = await handle_compress_to_l2_insight(args)

                    # Should succeed - not return validation error
                    assert "error" not in result, f"Empty source_ids should be valid, got error: {result}"
                    assert "id" in result, "Response should contain insight ID"
                    assert "embedding_status" in result, "Response should contain embedding status"

    async def test_none_source_ids_rejected(self):
        """Test that source_ids=None is still rejected (Bugfix: AC-2)."""
        args = {"content": "test content", "source_ids": None}
        result = await handle_compress_to_l2_insight(args)

        assert "error" in result, "source_ids=None should return error"
        assert (
            "source_ids" in result["details"]
        ), "Error should mention source_ids parameter"
        assert result["tool"] == "compress_to_l2_insight"

    async def test_invalid_source_ids_type(self):
        """Test error handling for invalid source_ids type."""
        args = {"content": "test content", "source_ids": "not-array"}
        result = await handle_compress_to_l2_insight(args)

        assert "error" in result, "Should return error"
        assert (
            "source_ids" in result["details"]
        ), "Error should mention source_ids parameter"

    async def test_non_integer_source_ids(self):
        """Test error handling for non-integer source_ids."""
        args = {"content": "test content", "source_ids": [1, "two", 3]}
        result = await handle_compress_to_l2_insight(args)

        assert "error" in result, "Should return error"
        assert (
            "source_ids" in result["details"]
        ), "Error should mention source_ids parameter"

    async def test_missing_api_key(self, valid_args):
        """Test error handling when OpenAI API key is not configured."""
        with patch.dict(os.environ, {}, clear=True):
            result = await handle_compress_to_l2_insight(valid_args)

            assert "error" in result, "Should return error"
            assert "API key" in result["details"], "Error should mention API key"

    async def test_placeholder_api_key(self, valid_args):
        """Test error handling when API key contains placeholder value."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-your-openai-api-key-here"}):
            result = await handle_compress_to_l2_insight(valid_args)

            assert "error" in result, "Should return error"
            assert (
                "placeholder" in result["details"]
            ), "Error should mention placeholder"

    @patch("mcp_server.tools.get_embedding_with_retry")
    async def test_openai_rate_limit_retry(
        self, mock_retry, mock_openai_client, valid_args
    ):
        """Test rate limit retry logic."""
        # Configure retry to succeed on second attempt
        mock_retry.side_effect = [RuntimeError("rate limiting"), [0.1] * 1536]

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                result = await handle_compress_to_l2_insight(valid_args)

                assert "error" not in result, f"Should succeed after retry: {result}"
                assert (
                    result["embedding_status"] == "retried"
                ), "Should indicate retry occurred"

    @patch("mcp_server.tools.get_embedding_with_retry")
    async def test_openai_api_permanent_error(
        self, mock_retry, mock_openai_client, valid_args
    ):
        """Test handling of permanent OpenAI API errors."""
        mock_retry.side_effect = RuntimeError("API authentication failed")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                result = await handle_compress_to_l2_insight(valid_args)

                assert "error" in result, "Should return error for API failure"

    async def test_fidelity_score_in_response(self, mock_openai_client, valid_args):
        """Test that fidelity score is calculated and included in response."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                with patch(
                    "mcp_server.tools.get_embedding_with_retry",
                    return_value=[0.1] * 1536,
                ):
                    result = await handle_compress_to_l2_insight(valid_args)

                    assert (
                        "fidelity_score" in result
                    ), "Response should contain fidelity score"
                    assert isinstance(
                        result["fidelity_score"], float
                    ), "Fidelity score should be float"
                    assert (
                        0.0 <= result["fidelity_score"] <= 1.0
                    ), "Fidelity score should be in range"

    async def test_database_storage(self, mock_openai_client, valid_args):
        """Test that embedding and metadata are correctly stored in database."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                with patch(
                    "mcp_server.tools.get_embedding_with_retry",
                    return_value=[0.1] * 1536,
                ):
                    result = await handle_compress_to_l2_insight(valid_args)

                    assert "error" not in result, f"Unexpected error: {result}"

                    # Verify data was stored in database
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT content, embedding, source_ids, metadata FROM l2_insights WHERE id = %s",
                            (result["id"],),
                        )
                        row = cursor.fetchone()

                    assert row is not None, "Data should be stored in database"
                    assert row[0] == valid_args["content"], "Content should match"
                    assert row[2] == valid_args["source_ids"], "Source IDs should match"

                    # Check metadata contains fidelity score
                    metadata = json.loads(row[3]) if row[3] else {}
                    assert (
                        "fidelity_score" in metadata
                    ), "Metadata should contain fidelity score"
                    assert (
                        metadata["fidelity_score"] == result["fidelity_score"]
                    ), "Fidelity score should match"

    async def test_embedding_vector_dimensions(self, mock_openai_client, valid_args):
        """Test that 1536-dimensional embedding is stored correctly."""
        test_embedding = [0.123] * 1536

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                with patch(
                    "mcp_server.tools.get_embedding_with_retry",
                    return_value=test_embedding,
                ):
                    result = await handle_compress_to_l2_insight(valid_args)

                    assert "error" not in result, f"Unexpected error: {result}"

                    # Verify embedding was stored correctly
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT embedding FROM l2_insights WHERE id = %s",
                            (result["id"],),
                        )
                        row = cursor.fetchone()

                    assert row is not None, "Data should be stored in database"
                    stored_embedding = list(row[0])  # Convert vector to list
                    assert (
                        len(stored_embedding) == 1536
                    ), f"Expected 1536 dimensions, got {len(stored_embedding)}"
                    assert (
                        stored_embedding == test_embedding
                    ), "Stored embedding should match test embedding"

    async def test_fidelity_warning_below_threshold(
        self, mock_openai_client, valid_args
    ):
        """Test that low fidelity content triggers warning in metadata."""
        # Use low density content to trigger warning
        valid_args["content"] = "test content with many stop words but low density"

        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-key", "FIDELITY_THRESHOLD": "0.7"}
        ):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                with patch(
                    "mcp_server.tools.get_embedding_with_retry",
                    return_value=[0.1] * 1536,
                ):
                    result = await handle_compress_to_l2_insight(valid_args)

                    assert "error" not in result, f"Unexpected error: {result}"
                    assert (
                        result["fidelity_score"] < 0.7
                    ), "Fidelity should be below threshold"

                    # Check metadata contains warning
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT metadata FROM l2_insights WHERE id = %s",
                            (result["id"],),
                        )
                        row = cursor.fetchone()

                    metadata = json.loads(row[3]) if row[3] else {}
                    assert (
                        metadata.get("fidelity_warning") is True
                    ), "Metadata should contain fidelity warning"
                    assert (
                        "warning_message" in metadata
                    ), "Metadata should contain warning message"

    async def test_fidelity_no_warning_above_threshold(
        self, mock_openai_client, valid_args
    ):
        """Test that high fidelity content does not trigger warning."""
        # Use high density content
        valid_args["content"] = (
            "machine learning algorithms process mathematical computations efficiently"
        )

        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-key", "FIDELITY_THRESHOLD": "0.3"}
        ):
            with patch("mcp_server.tools.OpenAI", return_value=mock_openai_client):
                with patch(
                    "mcp_server.tools.get_embedding_with_retry",
                    return_value=[0.1] * 1536,
                ):
                    result = await handle_compress_to_l2_insight(valid_args)

                    assert "error" not in result, f"Unexpected error: {result}"
                    assert (
                        result["fidelity_score"] >= 0.3
                    ), "Fidelity should be above threshold"

                    # Check metadata does not contain warning
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT metadata FROM l2_insights WHERE id = %s",
                            (result["id"],),
                        )
                        row = cursor.fetchone()

                    metadata = json.loads(row[3]) if row[3] else {}
                    assert (
                        metadata.get("fidelity_warning") is False
                    ), "Metadata should not contain fidelity warning"
                    assert (
                        "warning_message" not in metadata
                    ), "Metadata should not contain warning message"
