"""
Comprehensive tests for Dual Judge Implementation ().

Tests GPT-4o + Haiku independent evaluation and Cohen's Kappa calculation.
Uses mock clients for API testing and real database for integration testing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server.tools import handle_store_dual_judge_scores
from mcp_server.tools.dual_judge import DualJudgeEvaluator


class TestDualJudgeEvaluator:
    """Test suite for DualJudgeEvaluator class."""

    @pytest.fixture
    def evaluator(self):
        """Create DualJudgeEvaluator instance with mocked API clients."""
        with (
            patch("mcp_server.tools.dual_judge.AsyncOpenAI") as mock_openai,
            patch("mcp_server.tools.dual_judge.AsyncAnthropic") as mock_anthropic,
        ):

            # Mock API keys
            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "sk-test-openai-key",
                    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic-key",
                },
            ):
                evaluator = DualJudgeEvaluator()
                evaluator.gpt4o_client = mock_openai.return_value
                evaluator.haiku_client = mock_anthropic.return_value
                yield evaluator

    @pytest.mark.asyncio
    async def test_init_missing_openai_key(self):
        """Test initialization fails without OpenAI API key."""
        with patch.dict(
            "os.environ",
            {"OPENAI_API_KEY": "", "ANTHROPIC_API_KEY": "sk-ant-test"},
            clear=True,
        ):
            with pytest.raises(RuntimeError, match="OpenAI API key not configured"):
                DualJudgeEvaluator()

    @pytest.mark.asyncio
    async def test_init_missing_anthropic_key(self):
        """Test initialization fails without Anthropic API key."""
        with patch.dict(
            "os.environ",
            {"OPENAI_API_KEY": "sk-test", "ANTHROPIC_API_KEY": ""},
            clear=True,
        ):
            with pytest.raises(RuntimeError, match="Anthropic API key not configured"):
                DualJudgeEvaluator()

    @pytest.mark.asyncio
    async def test_prompt_creation(self, evaluator):
        """Test prompt creation for both judges."""
        query = "What is autonomy?"
        doc_content = "Autonomy is the capacity of an agent to act independently."

        system_prompt, user_prompt = evaluator._create_prompt(query, doc_content)

        assert "You are evaluating the relevance" in system_prompt
        assert "0.0 = Completely irrelevant" in system_prompt
        assert "1.0 = Perfectly relevant" in system_prompt
        assert "Return ONLY a float number" in system_prompt

        assert f"Query: {query}" in user_prompt
        assert f"Document: {doc_content}" in user_prompt
        assert "Relevance score (0.0-1.0):" in user_prompt

    @pytest.mark.asyncio
    async def test_gpt4o_judge_success(self, evaluator):
        """Test successful GPT-4o API call."""
        evaluator.gpt4o_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="0.85"))]
            )
        )

        score = await evaluator._call_gpt4o_judge("test query", "test document")

        assert score == 0.85
        evaluator.gpt4o_client.chat.completions.create.assert_called_once_with(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": evaluator._create_prompt("test query", "test document")[
                        0
                    ],
                },
                {
                    "role": "user",
                    "content": evaluator._create_prompt("test query", "test document")[
                        1
                    ],
                },
            ],
            temperature=0.0,
        )

    @pytest.mark.asyncio
    async def test_gpt4o_judge_rate_limit_retry(self, evaluator):
        """Test GPT-4o rate limit with exponential backoff retry."""
        from openai import RateLimitError

        # Create a mock response for RateLimitError
        mock_response = MagicMock()
        mock_response.status_code = 429

        # First 3 calls fail with rate limit, 4th succeeds
        evaluator.gpt4o_client.chat.completions.create = AsyncMock(
            side_effect=[
                RateLimitError(
                    message="Rate limit exceeded", response=mock_response, body=None
                ),
                RateLimitError(
                    message="Rate limit exceeded", response=mock_response, body=None
                ),
                RateLimitError(
                    message="Rate limit exceeded", response=mock_response, body=None
                ),
                MagicMock(choices=[MagicMock(message=MagicMock(content="0.75"))]),
            ]
        )

        with patch("asyncio.sleep") as mock_sleep:
            score = await evaluator._call_gpt4o_judge("test query", "test document")

        assert score == 0.75
        assert evaluator.gpt4o_client.chat.completions.create.call_count == 4
        assert mock_sleep.call_count == 3

    @pytest.mark.asyncio
    async def test_gpt4o_judge_invalid_score(self, evaluator):
        """Test GPT-4o returns invalid score (outside 0.0-1.0 range)."""
        evaluator.gpt4o_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="1.5"))]
            )
        )

        score = await evaluator._call_gpt4o_judge("test query", "test document")

        assert score == 0.5  # Should default to neutral score

    @pytest.mark.asyncio
    async def test_haiku_judge_success(self, evaluator):
        """Test successful Haiku API call."""
        mock_content = MagicMock()
        mock_content.text = "0.65"

        evaluator.haiku_client.messages.create = AsyncMock(
            return_value=MagicMock(content=[mock_content])
        )

        score = await evaluator._call_haiku_judge("test query", "test document")

        assert score == 0.65
        evaluator.haiku_client.messages.create.assert_called_once_with(
            model="claude-3-5-haiku-20241022",
            max_tokens=100,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": evaluator._create_prompt("test query", "test document")[
                        1
                    ],
                }
            ],
        )

    @pytest.mark.asyncio
    async def test_haiku_judge_rate_limit_retry(self, evaluator):
        """Test Haiku rate limit with exponential backoff retry."""

        # Name MUST be exactly "RateLimitError" for retry_logic to recognize it
        class RateLimitError(Exception):
            def __init__(self, message):
                self.status_code = 429
                super().__init__(message)

        # First 3 calls fail with rate limit, 4th succeeds
        mock_content = MagicMock()
        mock_content.text = "0.70"

        evaluator.haiku_client.messages.create = AsyncMock(
            side_effect=[
                RateLimitError("Rate limit exceeded"),
                RateLimitError("Rate limit exceeded"),
                RateLimitError("Rate limit exceeded"),
                MagicMock(content=[mock_content]),
            ]
        )

        with patch("asyncio.sleep") as mock_sleep:
            score = await evaluator._call_haiku_judge("test query", "test document")

        assert score == 0.70
        assert evaluator.haiku_client.messages.create.call_count == 4
        assert mock_sleep.call_count == 3

    def test_binarize_scores(self, evaluator):
        """Test score binarization (>0.5 = 1, ≤0.5 = 0)."""
        scores = [0.2, 0.5, 0.5, 0.501, 0.8, 1.0]
        expected = [0, 0, 0, 1, 1, 1]

        result = evaluator._binarize_scores(scores)
        assert result == expected

    def test_calculate_cohen_kappa_perfect_agreement(self, evaluator):
        """Test Cohen's Kappa with perfect agreement (should be 1.0)."""
        judge1_scores = [0.8, 0.6, 0.3, 0.9, 0.4]  # Binary: [1, 1, 0, 1, 0]
        judge2_scores = [0.7, 0.6, 0.2, 0.8, 0.4]  # Binary: [1, 1, 0, 1, 0]

        kappa = evaluator._calculate_cohen_kappa(judge1_scores, judge2_scores)
        assert abs(kappa - 1.0) < 1e-10

    def test_calculate_cohen_kappa_no_agreement(self, evaluator):
        """Test Cohen's Kappa with no agreement (should be 0.0 or negative)."""
        judge1_scores = [0.1, 0.1, 0.1, 0.1, 0.1]  # Binary: [0, 0, 0, 0, 0]
        judge2_scores = [0.9, 0.9, 0.9, 0.9, 0.9]  # Binary: [1, 1, 1, 1, 1]

        kappa = evaluator._calculate_cohen_kappa(judge1_scores, judge2_scores)
        assert kappa <= 0.0

    def test_calculate_cohen_kappa_empty_arrays(self, evaluator):
        """Test Cohen's Kappa with empty arrays (should raise ValueError)."""
        with pytest.raises(ValueError, match="Both score arrays must be non-empty"):
            evaluator._calculate_cohen_kappa([], [])

    def test_calculate_cohen_kappa_different_lengths(self, evaluator):
        """Test Cohen's Kappa with different length arrays (should raise ValueError)."""
        with pytest.raises(ValueError, match="Score arrays must have the same length"):
            evaluator._calculate_cohen_kappa([0.5, 0.6], [0.4])

    @pytest.mark.asyncio
    async def test_evaluate_documents_success(self, evaluator):
        """Test successful document evaluation with both judges."""
        # Mock API responses
        evaluator.gpt4o_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="0.8"))]
            )
        )

        mock_content = MagicMock()
        mock_content.text = "0.7"
        evaluator.haiku_client.messages.create = AsyncMock(
            return_value=MagicMock(content=[mock_content])
        )

        # Mock database operations (only _update_ground_truth exists)
        with patch.object(evaluator, "_update_ground_truth"):

            docs = [
                {"id": 1, "content": "Document 1 content"},
                {"id": 2, "content": "Document 2 content"},
            ]

            result = await evaluator.evaluate_documents(
                query_id=1, query="test query", docs=docs
            )

            assert result["status"] == "success"
            assert len(result["judge1_scores"]) == 2
            assert len(result["judge2_scores"]) == 2
            assert result["judge1_model"] == "gpt-4o"
            assert result["judge2_model"] == "claude-3-5-haiku-20241022"
            assert abs(result["kappa"] - 1.0) < 1e-10  # Perfect agreement
            assert result["successful_evaluations"] == 4  # 2 judges × 2 docs
            assert result["total_evaluations"] == 4
            assert "latency_seconds" in result
            assert "estimated_cost_eur" in result

    @pytest.mark.asyncio
    async def test_evaluate_documents_no_documents(self, evaluator):
        """Test evaluation with empty documents list."""
        result = await evaluator.evaluate_documents(
            query_id=1, query="test query", docs=[]
        )

        assert result["status"] == "failed"
        assert "No documents provided" in result["error"]
        assert result["judge1_scores"] == []
        assert result["judge2_scores"] == []

    @pytest.mark.asyncio
    async def test_evaluate_documents_partial_failure(self, evaluator):
        """Test evaluation with partial API failures."""
        # GPT-4o succeeds, Haiku fails
        evaluator.gpt4o_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="0.8"))]
            )
        )

        evaluator.haiku_client.messages.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        with patch.object(evaluator, "_update_ground_truth"):

            docs = [{"id": 1, "content": "Document 1"}]

            result = await evaluator.evaluate_documents(
                query_id=1, query="test query", docs=docs
            )

            assert result["status"] == "success"
            assert result["judge1_scores"] == [0.8]  # GPT-4o succeeded
            assert result["judge2_scores"] == [0.5]  # Haiku failed, neutral score
            assert result["successful_evaluations"] == 1  # Only GPT-4o succeeded

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="_log_api_cost method no longer exists in DualJudgeEvaluator")
    @patch("mcp_server.tools.dual_judge.get_connection")
    async def test_log_api_cost(self, mock_get_connection, evaluator):
        """Test API cost logging to database."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        await evaluator._log_api_cost(
            api_name="openai",
            model="gpt-4o",
            prompt_tokens=500,
            completion_tokens=5,
            cost_eur=0.0013,
            query_id=1,
        )

        mock_cursor.execute.assert_called_once_with(
            """
                    INSERT INTO api_cost_log
                    (api_name, model, prompt_tokens, completion_tokens, total_tokens, estimated_cost_eur, query_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
            ("openai", "gpt-4o", 500, 5, 505, 0.0013, 1),
        )
        mock_conn.commit.assert_called_once()


class TestStoreDualJudgeScoresTool:
    """Test suite for the MCP tool handler."""

    @pytest.mark.asyncio
    async def test_tool_success_with_mock_evaluator(self):
        """Test successful tool execution with mocked evaluator."""
        with (
            patch("mcp_server.tools.dual_judge.get_connection"),
            patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "sk-test-openai",
                    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic",
                },
            ),
        ):

            # Mock DualJudgeEvaluator
            mock_evaluator = MagicMock()
            mock_evaluator.evaluate_documents = AsyncMock(
                return_value={
                    "status": "success",
                    "judge1_scores": [0.8, 0.6],
                    "judge2_scores": [0.7, 0.5],
                    "judge1_model": "gpt-4o",
                    "judge2_model": "claude-3-5-haiku-20241022",
                    "kappa": 0.8,
                    "latency_seconds": 1.2,
                    "estimated_cost_eur": 0.0025,
                }
            )

            with patch(
                "mcp_server.tools.DualJudgeEvaluator", return_value=mock_evaluator
            ):
                arguments = {
                    "query_id": 1,
                    "query": "What is autonomy?",
                    "docs": [
                        {"id": 1, "content": "Autonomy means self-governance."},
                        {"id": 2, "content": "Independence in decision-making."},
                    ],
                }

                result = await handle_store_dual_judge_scores(arguments)

                assert result["status"] == "success"
                assert len(result["judge1_scores"]) == 2
                assert len(result["judge2_scores"]) == 2
                assert result["kappa"] == 0.8
                # Check that evaluate_documents was called with correct arguments
                mock_evaluator.evaluate_documents.assert_called_once()
                # The call was: evaluate_documents(1, 'What is autonomy?', [...])
                # So we need to check positional arguments
                call_args, call_kwargs = mock_evaluator.evaluate_documents.call_args
                assert call_args[0] == 1  # query_id
                assert call_args[1] == "What is autonomy?"  # query
                assert len(call_args[2]) == 2  # docs list length
                assert call_args[2][0]["id"] == 1
                assert "Autonomy means self-governance." in call_args[2][0]["content"]

    @pytest.mark.asyncio
    async def test_tool_invalid_query_id(self):
        """Test tool with invalid query_id parameter."""
        arguments = {
            "query_id": "invalid",  # Should be integer
            "query": "test query",
            "docs": [{"id": 1, "content": "test document"}],
        }

        result = await handle_store_dual_judge_scores(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "query_id must be a positive integer" in result["details"]

    @pytest.mark.asyncio
    async def test_tool_empty_query(self):
        """Test tool with empty query parameter."""
        arguments = {
            "query_id": 1,
            "query": "",  # Should be non-empty
            "docs": [{"id": 1, "content": "test document"}],
        }

        result = await handle_store_dual_judge_scores(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "query must be a non-empty string" in result["details"]

    @pytest.mark.asyncio
    async def test_tool_empty_docs(self):
        """Test tool with empty docs array."""
        arguments = {
            "query_id": 1,
            "query": "test query",
            "docs": [],  # Should be non-empty
        }

        result = await handle_store_dual_judge_scores(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "docs must be a non-empty array" in result["details"]

    @pytest.mark.asyncio
    async def test_tool_invalid_document_format(self):
        """Test tool with invalid document format."""
        arguments = {
            "query_id": 1,
            "query": "test query",
            "docs": [
                {"id": 1},  # Missing content
                {"content": "test content"},  # Missing id
            ],
        }

        result = await handle_store_dual_judge_scores(arguments)

        assert result["error"] == "Parameter validation failed"
        assert "missing required 'id' or 'content' keys" in result["details"]

    @pytest.mark.asyncio
    async def test_tool_missing_api_keys(self):
        """Test tool with missing API keys."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "",  # Missing
                "ANTHROPIC_API_KEY": "sk-ant-test",  # Present
            },
            clear=True,
        ):
            arguments = {
                "query_id": 1,
                "query": "test query",
                "docs": [{"id": 1, "content": "test document"}],
            }

            result = await handle_store_dual_judge_scores(arguments)

            assert result["error"] == "OpenAI API key not configured"

    @pytest.mark.asyncio
    async def test_tool_placeholder_api_keys(self):
        """Test tool with placeholder API keys."""
        with patch.dict(
            "os.environ",
            {
                "OPENAI_API_KEY": "sk-your-openai-api-key-here",  # Placeholder
                "ANTHROPIC_API_KEY": "sk-ant-test",  # Valid
            },
            clear=True,
        ):
            arguments = {
                "query_id": 1,
                "query": "test query",
                "docs": [{"id": 1, "content": "test document"}],
            }

            result = await handle_store_dual_judge_scores(arguments)

            assert result["error"] == "OpenAI API key not configured"
            assert "placeholder value" in result["details"]


class TestIntegration:
    """Integration tests with real database connections."""

    @pytest.fixture
    def evaluator(self):
        """Create DualJudgeEvaluator instance with mocked API clients for integration tests."""
        with (
            patch("mcp_server.tools.dual_judge.AsyncOpenAI") as mock_openai,
            patch("mcp_server.tools.dual_judge.AsyncAnthropic") as mock_anthropic,
        ):

            # Mock API keys
            with patch.dict(
                "os.environ",
                {
                    "OPENAI_API_KEY": "sk-test-openai-key",
                    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic-key",
                },
            ):
                evaluator = DualJudgeEvaluator()
                evaluator.gpt4o_client = mock_openai.return_value
                evaluator.haiku_client = mock_anthropic.return_value
                yield evaluator

    @pytest.mark.asyncio
    async def test_database_integration(self):
        """Test integration with real database (requires test database)."""
        # This test would require a test database setup
        # For now, we'll skip it as it needs proper database fixture
        pytest.skip("Integration test requires test database setup")

    @pytest.mark.asyncio
    async def test_latency_performance(self, evaluator):
        """Test that parallel execution completes within latency target."""
        # Mock fast API responses
        evaluator.gpt4o_client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="0.5"))]
            )
        )

        mock_content = MagicMock()
        mock_content.text = "0.5"
        evaluator.haiku_client.messages.create = AsyncMock(
            return_value=MagicMock(content=[mock_content])
        )

        with patch.object(evaluator, "_update_ground_truth"):

            docs = [{"id": i, "content": f"Document {i} content"} for i in range(5)]

            import time

            start_time = time.time()
            result = await evaluator.evaluate_documents(
                query_id=1, query="test query", docs=docs
            )
            latency = time.time() - start_time

            assert result["status"] == "success"
            assert latency < 2.0  # Target: <2s for 5 documents
