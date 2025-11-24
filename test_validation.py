#!/usr/bin/env python3
"""
Test Validation Script for 
Validates the store_raw_dialogue implementation without requiring PostgreSQL
"""

import json
import sys


def validate_imports():
    """Test that all imports work correctly."""
    print("🔍 Testing imports...")

    try:
        # Test main imports
<<<<<<< Updated upstream
        import mcp_server.tools  # noqa: F401
=======
        import mcp_server.tools
>>>>>>> Stashed changes

        print("✅ mcp_server.tools module imports correctly")

        # Test specific functions exist
<<<<<<< Updated upstream
        import importlib.util

        if importlib.util.find_spec("mcp_server.tools.handle_ping") is None:
            raise ImportError("handle_ping not found")
        if (
            importlib.util.find_spec("mcp_server.tools.handle_store_raw_dialogue")
            is None
        ):
            raise ImportError("handle_store_raw_dialogue not found")
=======
        from mcp_server.tools import handle_ping, handle_store_raw_dialogue
>>>>>>> Stashed changes

        print("✅ handle_store_raw_dialogue and handle_ping functions available")

        # Test type hints imports
<<<<<<< Updated upstream
        import psycopg2.extras  # noqa: F401

        print("✅ psycopg2.extras imports correctly")

        from mcp_server.db.connection import get_connection  # noqa: F401
=======
        import psycopg2.extras

        print("✅ psycopg2.extras imports correctly")

        from mcp_server.db.connection import get_connection
>>>>>>> Stashed changes

        print("✅ get_connection import available")

        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def validate_json_schema():
    """Test JSON schema validation."""
    print("\n🔍 Testing JSON schema validation...")

    try:
        from mcp_server.tools import validate_parameters

        # Test valid parameters
        schema = {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "speaker": {"type": "string"},
                "content": {"type": "string"},
                "metadata": {"type": "object"},
            },
            "required": ["session_id", "speaker", "content"],
        }

        valid_params = {
            "session_id": "test-session",
            "speaker": "user",
            "content": "Hello world",
            "metadata": {"model": "claude"},
        }

        validate_parameters(valid_params, schema)
        print("✅ Valid parameters pass validation")

        # Test missing required parameter
        invalid_params = {
            "session_id": "test-session",
            "speaker": "user",
            # missing "content"
        }

        try:
            validate_parameters(invalid_params, schema)
            print("❌ Invalid parameters should have failed validation")
            return False
        except Exception:
            print("✅ Invalid parameters correctly rejected")

        return True
    except Exception as e:
        print(f"❌ Schema validation error: {e}")
        return False


def validate_ping_function():
    """Test ping function returns proper format."""
    print("\n🔍 Testing ping function...")

    try:
        import asyncio

        from mcp_server.tools import handle_ping

        # Run async function
        result = asyncio.run(handle_ping({}))

        # Check response format
        expected_keys = {"response", "timestamp", "tool", "status"}
        actual_keys = set(result.keys())

        if expected_keys == actual_keys:
            print("✅ Ping response has correct format")
            print(f"   Response: {result}")
            return True
        else:
            print(
                f"❌ Ping response missing keys. Expected: {expected_keys}, Got: {actual_keys}"
            )
            return False
    except Exception as e:
        print(f"❌ Ping function error: {e}")
        return False


def validate_metadata_json():
    """Test metadata JSON serialization."""
    print("\n🔍 Testing metadata JSON serialization...")

    try:
        # Test with metadata
        metadata = {
            "model": "claude-sonnet-4",
            "temperature": 0.7,
            "tags": ["test", "validation"],
        }
        json_str = json.dumps(metadata)

        # Parse back
        parsed = json.loads(json_str)

        if parsed == metadata:
            print("✅ Metadata JSON serialization works correctly")
            return True
        else:
            print(
                f"❌ JSON serialization failed. Original: {metadata}, Parsed: {parsed}"
            )
            return False
    except Exception as e:
        print(f"❌ JSON serialization error: {e}")
        return False


def validate_tool_registration():
    """Test tool registration structure."""
    print("\n🔍 Testing tool registration...")

    try:
        from mcp.server import Server

        from mcp_server.tools import register_tools

        # Create test server
        server = Server("test-server")

        # Register tools
        tools = register_tools(server)

        # Check we have the expected tools
        tool_names = {tool.name for tool in tools}
        expected_tools = {"store_raw_dialogue", "ping"}

        if expected_tools.issubset(tool_names):
            print("✅ Required tools registered correctly")
            print(f"   Available tools: {tool_names}")
            return True
        else:
            missing = expected_tools - tool_names
            print(f"❌ Missing tools: {missing}")
            return False
    except Exception as e:
        print(f"❌ Tool registration error: {e}")
        return False


def main():
    """Run all validation tests."""
    print("🧪  Implementation Validation")
    print("=" * 50)

    tests = [
        validate_imports,
        validate_json_schema,
        validate_ping_function,
        validate_metadata_json,
        validate_tool_registration,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1

    print("\n" + "=" * 50)
    print(f"📊 Validation Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ ALL VALIDATIONS PASSED!")
        print(
            "🎯 Implementation is structurally correct and ready for database testing"
        )
        return 0
    else:
        print(f"❌ {total - passed} validations failed")
        print("🔧 Implementation needs fixes before database testing")
        return 1


if __name__ == "__main__":
    sys.exit(main())
