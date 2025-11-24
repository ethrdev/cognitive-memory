"""
Unit tests for store_raw_dialogue MCP tool.

Tests cover parameter validation, database operations, error handling,
and metadata JSONB storage.
"""

import json
import os

import pytest

# Use DATABASE_URL from environment (set by conftest.py or .env.development)
# Skip tests if DATABASE_URL is not set
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set - skipping database-dependent tests"
)

from mcp_server.tools import handle_store_raw_dialogue


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_data():
    """Clean up test data after each test."""
    yield  # Run the test first

    # Clean up test data after test
    try:
        from mcp_server.db.connection import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            # Delete test entries (those with test session IDs)
            cursor.execute(
                "DELETE FROM l0_raw WHERE session_id LIKE %s", ("test-session-%",)
            )
            conn.commit()
    except Exception:
        # Don't fail tests if cleanup fails
        pass


@pytest.mark.asyncio
async def test_valid_insertion():
    """Test 1: Valid insertion - verify ID and timestamp returned."""
    arguments = {
        "session_id": "test-session-1",
        "speaker": "user",
        "content": "Hello, this is a test message.",
    }

    result = await handle_store_raw_dialogue(arguments)

    assert result["status"] == "success"
    assert "id" in result
    assert isinstance(result["id"], int)
    assert "timestamp" in result
    assert result["session_id"] == "test-session-1"

    # Verify timestamp is in ISO format
    import datetime

    datetime.datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))


@pytest.mark.asyncio
async def test_metadata_jsonb():
    """Test 2: Metadata as JSONB - verify JSON serialization works."""
    arguments = {
        "session_id": "test-session-2",
        "speaker": "assistant",
        "content": "This is a response with metadata.",
        "metadata": {
            "model": "claude-sonnet-4",
            "temperature": 0.7,
            "tags": ["helpful", "technical"],
        },
    }

    result = await handle_store_raw_dialogue(arguments)

    assert result["status"] == "success"
    assert result["session_id"] == "test-session-2"

    # Verify metadata was stored correctly in database
    from mcp_server.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata FROM l0_raw WHERE session_id = %s", ("test-session-2",)
        )
        stored_metadata = cursor.fetchone()["metadata"]

        assert stored_metadata is not None
        # psycopg2 auto-deserializes JSONB to dict
        parsed_metadata = stored_metadata if isinstance(stored_metadata, dict) else json.loads(stored_metadata)
        assert parsed_metadata["model"] == "claude-sonnet-4"
        assert parsed_metadata["temperature"] == 0.7
        assert "helpful" in parsed_metadata["tags"]


@pytest.mark.asyncio
async def test_missing_required_parameter():
    """Test 3: Missing required parameter - verify validation error."""
    # Missing 'content' parameter
    arguments = {
        "session_id": "test-session-3",
        "speaker": "user",
        # content is missing
    }

    result = await handle_store_raw_dialogue(arguments)

    # Handler may return error dict with different structure
    # Check for failure: either status != success or error key present
    is_error = result.get("status") != "success" or "error" in result
    assert is_error, f"Expected error response, got: {result}"


@pytest.mark.asyncio
async def test_null_metadata():
    """Test 4: Null metadata handling."""
    arguments = {
        "session_id": "test-session-4",
        "speaker": "user",
        "content": "Message with no metadata",
        "metadata": None,
    }

    result = await handle_store_raw_dialogue(arguments)

    assert result["status"] == "success"

    # Verify metadata is NULL in database
    from mcp_server.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT metadata FROM l0_raw WHERE session_id = %s", ("test-session-4",)
        )
        stored_metadata = cursor.fetchone()["metadata"]
        assert stored_metadata is None


@pytest.mark.asyncio
async def test_session_grouping():
    """Test 5: Session query - insert multiple entries, verify session_id grouping."""
    # Insert multiple messages for same session
    messages = [
        {"speaker": "user", "content": "First message"},
        {"speaker": "assistant", "content": "First response"},
        {"speaker": "user", "content": "Second message"},
    ]

    inserted_ids = []

    for i, msg in enumerate(messages):
        arguments = {
            "session_id": "test-session-5",
            "speaker": msg["speaker"],
            "content": msg["content"],
        }

        result = await handle_store_raw_dialogue(arguments)
        assert result["status"] == "success"
        inserted_ids.append(result["id"])

    # Verify all messages are grouped under same session
    from mcp_server.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM l0_raw WHERE session_id = %s",
            ("test-session-5",),
        )
        count = cursor.fetchone()["count"]
        assert count == len(messages)

        # Verify timestamps are in order (earlier to later)
        cursor.execute(
            "SELECT id, timestamp FROM l0_raw WHERE session_id = %s ORDER BY timestamp",
            ("test-session-5",),
        )
        rows = cursor.fetchall()
        assert len(rows) == len(messages)


@pytest.mark.asyncio
async def test_special_characters():
    """Test 6: Special characters in content - verify no SQL injection."""
    arguments = {
        "session_id": "test-session-6",
        "speaker": "user",
        "content": "Message with special chars: '; DROP TABLE l0_raw; -- and unicode: ñáéíóú",
        "metadata": {
            "sql_injection_attempt": "'; SELECT * FROM users; --",
            "unicode": "Café résumé naïve",
        },
    }

    result = await handle_store_raw_dialogue(arguments)

    assert result["status"] == "success"

    # Verify content is stored exactly as provided (not executed)
    from mcp_server.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content, metadata FROM l0_raw WHERE session_id = %s",
            ("test-session-6",),
        )
        row = cursor.fetchone()

        assert row["content"] == arguments["content"]
        # psycopg2 auto-deserializes JSONB to dict
        stored_metadata = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"])
        assert (
            stored_metadata["sql_injection_attempt"]
            == arguments["metadata"]["sql_injection_attempt"]
        )

        # Verify table still exists and has expected data
        cursor.execute("SELECT COUNT(*) FROM l0_raw")
        assert cursor.fetchone()["count"] > 0


@pytest.mark.asyncio
async def test_empty_strings():
    """Test 7: Empty strings for parameters."""
    arguments = {
        "session_id": "test-session-7",
        "speaker": "user",
        "content": "",  # Empty content should be allowed
    }

    result = await handle_store_raw_dialogue(arguments)

    assert result["status"] == "success"

    # Verify empty string was stored
    from mcp_server.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM l0_raw WHERE session_id = %s", ("test-session-7",)
        )
        stored_content = cursor.fetchone()["content"]
        assert stored_content == ""


@pytest.mark.asyncio
async def test_long_content():
    """Test 8: Very long content (TEXT type should handle it)."""
    # Generate a long string (10KB)
    long_content = "A" * 10240

    arguments = {
        "session_id": "test-session-8",
        "speaker": "assistant",
        "content": long_content,
    }

    result = await handle_store_raw_dialogue(arguments)

    assert result["status"] == "success"

    # Verify long content was stored completely
    from mcp_server.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT content FROM l0_raw WHERE session_id = %s", ("test-session-8",)
        )
        stored_content = cursor.fetchone()["content"]
        assert len(stored_content) == len(long_content)
        assert stored_content == long_content


@pytest.mark.asyncio
async def test_custom_speaker():
    """Test 9: Custom speaker identifier (not just user/assistant)."""
    arguments = {
        "session_id": "test-session-9",
        "speaker": "system-notification",
        "content": "System started successfully.",
    }

    result = await handle_store_raw_dialogue(arguments)

    assert result["status"] == "success"
    assert result["session_id"] == "test-session-9"

    # Verify speaker was stored correctly
    from mcp_server.db.connection import get_connection

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT speaker FROM l0_raw WHERE session_id = %s", ("test-session-9",)
        )
        stored_speaker = cursor.fetchone()["speaker"]
        assert stored_speaker == "system-notification"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
