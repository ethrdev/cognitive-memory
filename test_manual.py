#!/usr/bin/env python3
"""
Manual test for store_raw_dialogue tool.
Run this to verify the implementation works without pytest.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, "/home/ethr/01-projects/ai-experiments/i-o")

# Set test database
os.environ["DATABASE_URL"] = (
    "postgresql://postgres:password@localhost:5432/cognitive_memory_test"
)


async def test_store_raw_dialogue():
    """Test the store_raw_dialogue tool manually."""
    try:
        from mcp_server.tools import handle_store_raw_dialogue

        print("Testing store_raw_dialogue tool...")

        # Test 1: Basic insertion
        print("\n1. Testing basic insertion...")
        args1 = {
            "session_id": "test-manual-1",
            "speaker": "user",
            "content": "This is a manual test message.",
        }

        result1 = await handle_store_raw_dialogue(args1)
        print(f"Result: {result1}")

        if result1.get("status") == "success":
            print("✅ Basic insertion test PASSED")
        else:
            print(f"❌ Basic insertion test FAILED: {result1}")
            return False

        # Test 2: With metadata
        print("\n2. Testing with metadata...")
        args2 = {
            "session_id": "test-manual-2",
            "speaker": "assistant",
            "content": "Response with metadata",
            "metadata": {
                "model": "claude-test",
                "temperature": 0.5,
                "tags": ["test", "manual"],
            },
        }

        result2 = await handle_store_raw_dialogue(args2)
        print(f"Result: {result2}")

        if result2.get("status") == "success":
            print("✅ Metadata test PASSED")
        else:
            print(f"❌ Metadata test FAILED: {result2}")
            return False

        # Test 3: Missing parameter (should fail validation)
        print("\n3. Testing parameter validation...")
        args3 = {
            "session_id": "test-manual-3",
            "speaker": "user",
            # Missing 'content'
        }

        result3 = await handle_store_raw_dialogue(args3)
        print(f"Result: {result3}")

        if result3.get("error"):
            print("✅ Parameter validation test PASSED")
        else:
            print("❌ Parameter validation test FAILED - should have errored")
            return False

        print("\n🎉 All manual tests PASSED!")
        return True

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_store_raw_dialogue())
    sys.exit(0 if success else 1)
