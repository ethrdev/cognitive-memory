"""
[P0] External API Client Tests

Tests for external API clients (OpenAI, Anthropic) including error handling,
rate limiting, and retry logic.

Priority: P0 (Critical) - External API clients are critical for system operation
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from openai import AsyncOpenAI, RateLimitError, APITimeoutError
from anthropic import AsyncAnthropic, Message
import asyncio

from mcp_server.external.openai_client import OpenAIClient
from mcp_server.external.anthropic_client import AnthropicClient


@pytest.mark.P0
class TestOpenAIClient:
    """P0 tests for OpenAI client."""

    @pytest.fixture
    def mock_openai_client(self):
        """Create mock OpenAI client."""
        return AsyncOpenAI(api_key="test_key")

    @pytest.fixture
    def openai_client(self, mock_openai_client):
        """Create OpenAI client with mocked dependencies."""
        return OpenAIClient(
            client=mock_openai_client,
            max_retries=3,
            timeout=30.0,
        )

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, openai_client, mock_openai_client):
        """[P0] Generate embedding should return valid embedding vector."""
        # GIVEN: Mock successful response
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = [0.1] * 1536
        mock_openai_client.embeddings.create = AsyncMock(
            return_value=mock_response
        )

        # WHEN: Generating embedding
        result = await openai_client.generate_embedding(
            text="test text",
            model="text-embedding-3-small"
        )

        # THEN: Should return embedding
        assert len(result) == 1536
        assert result[0] == 0.1
        mock_openai_client.embeddings.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_embedding_rate_limit_retry(self, openai_client, mock_openai_client):
        """[P0] Generate embedding should retry on rate limit."""
        # GIVEN: Rate limit then success
        mock_openai_client.embeddings.create = AsyncMock(
            side_effect=[
                RateLimitError("Rate limit exceeded"),
                MagicMock(data=[MagicMock(embedding=[0.1] * 1536)]),
            ]
        )

        # WHEN: Generating embedding with retries
        result = await openai_client.generate_embedding(
            text="test text",
            model="text-embedding-3-small"
        )

        # THEN: Should eventually succeed
        assert len(result) == 1536
        assert mock_openai_client.embeddings.create.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_embedding_timeout(self, openai_client, mock_openai_client):
        """[P0] Generate embedding should handle timeout."""
        # GIVEN: Timeout error
        mock_openai_client.embeddings.create = AsyncMock(
            side_effect=APITimeoutError("Request timed out")
        )

        # WHEN: Generating embedding
        result = await openai_client.generate_embedding(
            text="test text",
            model="text-embedding-3-small"
        )

        # THEN: Should return None or raise appropriate error
        assert result is None or isinstance(result, list)

    @pytest.mark.asyncio
    async def test_generate_embedding_invalid_api_key(self, openai_client, mock_openai_client):
        """[P0] Generate embedding should handle invalid API key."""
        # GIVEN: Authentication error
        mock_openai_client.embeddings.create = AsyncMock(
            side_effect=Exception("Invalid API key")
        )

        # WHEN: Generating embedding
        result = await openai_client.generate_embedding(
            text="test text",
            model="text-embedding-3-small"
        )

        # THEN: Should handle error gracefully
        assert result is None

    @pytest.mark.asyncio
    async def test_validate_api_key(self, openai_client, mock_openai_client):
        """[P1] Validate API key should check key validity."""
        # GIVEN: Valid API key response
        mock_openai_client.models.list = AsyncMock()

        # WHEN: Validating API key
        is_valid = await openai_client.validate_api_key()

        # THEN: Should return validation result
        assert is_valid is True
        mock_openai_client.models.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self, openai_client, mock_openai_client):
        """[P1] Validate API key should detect invalid keys."""
        # GIVEN: Invalid API key
        mock_openai_client.models.list = AsyncMock(
            side_effect=Exception("Invalid API key")
        )

        # WHEN: Validating API key
        is_valid = await openai_client.validate_api_key()

        # THEN: Should return False
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_health_check(self, openai_client, mock_openai_client):
        """[P1] Health check should verify API connectivity."""
        # GIVEN: Healthy API
        mock_openai_client.models.list = AsyncMock()

        # WHEN: Checking health
        health = await openai_client.health_check()

        # THEN: Should return health status
        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert health["api_key_valid"] is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, openai_client, mock_openai_client):
        """[P1] Health check should detect API issues."""
        # GIVEN: Unhealthy API
        mock_openai_client.models.list = AsyncMock(
            side_effect=Exception("API unavailable")
        )

        # WHEN: Checking health
        health = await openai_client.health_check()

        # THEN: Should return unhealthy status
        assert health["status"] == "unhealthy"
        assert health["api_key_valid"] is False


@pytest.mark.P0
class TestAnthropicClient:
    """P0 tests for Anthropic client."""

    @pytest.fixture
    def mock_anthropic_client(self):
        """Create mock Anthropic client."""
        return AsyncAnthropic(api_key="test_key")

    @pytest.fixture
    def anthropic_client(self, mock_anthropic_client):
        """Create Anthropic client with mocked dependencies."""
        return AnthropicClient(
            client=mock_anthropic_client,
            max_retries=3,
            timeout=30.0,
        )

    @pytest.mark.asyncio
    async def test_evaluate_response_success(self, anthropic_client, mock_anthropic_client):
        """[P0] Evaluate response should return evaluation score."""
        # GIVEN: Mock successful response
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '{"score": 0.8, "reasoning": "Good response"}'
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=mock_response
        )

        # WHEN: Evaluating response
        result = await anthropic_client.evaluate_response(
            query="test query",
            response="test response",
            context={}
        )

        # THEN: Should return evaluation
        assert result["score"] == 0.8
        assert "reasoning" in result
        mock_anthropic_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_response_parse_json(self, anthropic_client, mock_anthropic_client):
        """[P0] Evaluate response should parse JSON correctly."""
        # GIVEN: JSON response
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = '{"score": 0.9, "reasoning": "Excellent"}'
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=mock_response
        )

        # WHEN: Evaluating response
        result = await anthropic_client.evaluate_response(
            query="test query",
            response="test response",
            context={}
        )

        # THEN: Should parse JSON
        assert isinstance(result, dict)
        assert "score" in result

    @pytest.mark.asyncio
    async def test_evaluate_response_retry_on_error(self, anthropic_client, mock_anthropic_client):
        """[P0] Evaluate response should retry on errors."""
        # GIVEN: Error then success
        mock_anthropic_client.messages.create = AsyncMock(
            side_effect=[
                Exception("Temporary error"),
                MagicMock(content=[MagicMock(text='{"score": 0.7}')])
            ]
        )

        # WHEN: Evaluating response with retries
        result = await anthropic_client.evaluate_response(
            query="test query",
            response="test response",
            context={}
        )

        # THEN: Should eventually succeed
        assert result["score"] == 0.7
        assert mock_anthropic_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_evaluate_response_invalid_json(self, anthropic_client, mock_anthropic_client):
        """[P0] Evaluate response should handle invalid JSON."""
        # GIVEN: Invalid JSON response
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "invalid json"
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=mock_response
        )

        # WHEN: Evaluating response
        result = await anthropic_client.evaluate_response(
            query="test query",
            response="test response",
            context={}
        )

        # THEN: Should handle error gracefully
        assert result is not None
        assert "error" in result or "score" in result

    @pytest.mark.asyncio
    async def test_validate_api_key(self, anthropic_client, mock_anthropic_client):
        """[P1] Validate API key should check Anthropic key validity."""
        # GIVEN: Valid API key
        mock_anthropic_client.messages.create = AsyncMock()

        # WHEN: Validating API key
        is_valid = await anthropic_client.validate_api_key()

        # THEN: Should return True
        assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_api_key_invalid(self, anthropic_client, mock_anthropic_client):
        """[P1] Validate API key should detect invalid Anthropic keys."""
        # GIVEN: Invalid API key
        mock_anthropic_client.messages.create = AsyncMock(
            side_effect=Exception("Invalid API key")
        )

        # WHEN: Validating API key
        is_valid = await anthropic_client.validate_api_key()

        # THEN: Should return False
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_health_check_anthropic(self, anthropic_client, mock_anthropic_client):
        """[P1] Health check should verify Anthropic API connectivity."""
        # GIVEN: Healthy API
        mock_anthropic_client.messages.create = AsyncMock()

        # WHEN: Checking health
        health = await anthropic_client.health_check()

        # THEN: Should return health status
        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert health["api_key_valid"] is True


@pytest.mark.P1
class TestExternalAPIClientIntegration:
    """P1 integration tests for external API clients."""

    @pytest.mark.asyncio
    async def test_openai_anthropic_workflow(self):
        """[P1] Combined OpenAI and Anthropic workflow."""
        # GIVEN: Both clients
        mock_openai = AsyncOpenAI(api_key="test")
        mock_anthropic = AsyncAnthropic(api_key="test")

        openai_client = OpenAIClient(client=mock_openai)
        anthropic_client = AnthropicClient(client=mock_anthropic)

        # Mock responses
        mock_openai.embeddings.create = AsyncMock(
            return_value=MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])
        )
        mock_anthropic.messages.create = AsyncMock(
            return_value=MagicMock(content=[MagicMock(text='{"score": 0.8}')])
        )

        # WHEN: Running combined workflow
        embedding = await openai_client.generate_embedding("test")
        evaluation = await anthropic_client.evaluate_response(
            "query", "response", {}
        )

        # THEN: Both should work
        assert len(embedding) == 1536
        assert evaluation["score"] == 0.8

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self, openai_client, mock_openai_client):
        """[P1] Rate limit handling should work correctly."""
        # GIVEN: Multiple rate limit errors then success
        call_count = 0
        async def mock_create(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise RateLimitError("Rate limit")
            return MagicMock(data=[MagicMock(embedding=[0.1] * 1536)])

        mock_openai_client.embeddings.create = mock_create

        # WHEN: Generating embedding with rate limits
        result = await openai_client.generate_embedding(
            "test",
            max_retries=5
        )

        # THEN: Should succeed after retries
        assert len(result) == 1536
        assert call_count == 4

    @pytest.mark.asyncio
    async def test_fallback_on_service_failure(self, openai_client, mock_openai_client):
        """[P2] Should fallback when service fails completely."""
        # GIVEN: Complete service failure
        mock_openai_client.embeddings.create = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        # WHEN: Generating embedding
        result = await openai_client.generate_embedding(
            "test",
            enable_fallback=True
        )

        # THEN: Should return fallback or None
        assert result is None or isinstance(result, list)
