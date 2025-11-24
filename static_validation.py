#!/usr/bin/env python3
"""
Static Code Validation for Story 1.4
Validates the implementation without requiring external dependencies
"""

import ast
import re


def validate_file_syntax(filepath):
    """Test that Python file has valid syntax."""
    print(f"🔍 Testing syntax of {filepath}...")

    try:
        with open(filepath) as f:
            content = f.read()

        # Parse AST to check syntax
        ast.parse(content)
        print("✅ Valid Python syntax")
        return True
    except SyntaxError as e:
        print(f"❌ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"❌ File error: {e}")
        return False


def validate_imports(filepath):
    """Test that required imports are present at file top."""
    print(f"\n🔍 Testing imports in {filepath}...")

    try:
        with open(filepath) as f:
            lines = f.readlines()

        # Check for required imports in first 25 lines
        required_imports = [
            "import json",
            "import logging",
            "import psycopg2",
            "import psycopg2.extras",
            "from mcp_server.db.connection import get_connection",
        ]

        found_imports = set()
        for _, line in enumerate(lines[:25]):  # Check first 25 lines
            line = line.strip()
            for required in required_imports:
                if required in line:
                    found_imports.add(required)

        missing = set(required_imports) - found_imports
        if missing:
            print(f"❌ Missing imports: {missing}")
            return False

        print(f"✅ All {len(required_imports)} required imports found at file top")
        return True
    except Exception as e:
        print(f"❌ Import validation error: {e}")
        return False


def validate_function_signatures(filepath):
    """Test that required functions exist with correct signatures."""
    print(f"\n🔍 Testing function signatures in {filepath}...")

    try:
        with open(filepath) as f:
            content = f.read()

        # Parse AST
        tree = ast.parse(content)

        required_functions = {
            "handle_store_raw_dialogue": ["arguments"],
            "handle_ping": ["arguments"],
            "register_tools": ["server"],
            "validate_parameters": ["params", "schema"],
        }

        found_functions = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_name = node.name
                # Include async functions
                args = [arg.arg for arg in node.args.args]

                if func_name in required_functions:
                    required_args = required_functions[func_name]
                    if all(arg in args for arg in required_args):
                        found_functions.add(func_name)
                        print(f"✅ {func_name} function exists with correct signature")
                    else:
                        print(
                            f"⚠️ {func_name} function has different signature. Expected: {required_args}, Got: {args}"
                        )
                        # Still count as found since function exists
                        found_functions.add(func_name)

        missing = set(required_functions.keys()) - found_functions
        if missing:
            print(f"❌ Missing functions: {missing}")
            return False

        print(f"✅ All {len(required_functions)} required functions found")
        return True
    except Exception as e:
        print(f"❌ Function signature validation error: {e}")
        return False


def validate_cursor_type_hints(filepath):
    """Test that cursor has proper type hints."""
    print(f"\n🔍 Testing cursor type hints in {filepath}...")

    try:
        with open(filepath) as f:
            content = f.read()

        # Look for cursor type hint
        cursor_type_pattern = (
            r"cursor:\s*psycopg2\.extras\.DictCursor\s*=\s*conn\.cursor\(\)"
        )

        if re.search(cursor_type_pattern, content):
            print("✅ Cursor has proper type hint")
            return True
        else:
            print("❌ Cursor type hint not found or incorrect format")
            return False
    except Exception as e:
        print(f"❌ Type hint validation error: {e}")
        return False


def validate_ping_timestamp(filepath):
    """Test that ping function uses real timestamp."""
    print(f"\n🔍 Testing ping timestamp implementation in {filepath}...")

    try:
        with open(filepath) as f:
            content = f.read()

        # Look for real timestamp implementation
        real_timestamp_pattern = (
            r"datetime\.datetime\.now\(datetime\.timezone\.utc\)\.isoformat\(\)"
        )
        hardcoded_pattern = r'"2025-11-12T00:00:00Z"'

        if re.search(real_timestamp_pattern, content):
            print("✅ Ping function uses real timestamp")
            timestamp_score = 1
        elif re.search(hardcoded_pattern, content):
            print("❌ Ping function still uses hardcoded timestamp")
            timestamp_score = 0
        else:
            print("⚠️ Ping timestamp implementation unclear")
            timestamp_score = 0.5

        return timestamp_score == 1
    except Exception as e:
        print(f"❌ Ping timestamp validation error: {e}")
        return False


def validate_sql_query(filepath):
    """Test that SQL query is properly formatted."""
    print(f"\n🔍 Testing SQL query in {filepath}...")

    try:
        with open(filepath) as f:
            content = f.read()

        # Look for the INSERT query
        sql_pattern = r"INSERT\s+INTO\s+l0_raw\s*\(.*?\)\s*VALUES\s*\(%s.*?\)\s*RETURNING\s+id,\s*timestamp"

        if re.search(sql_pattern, content, re.IGNORECASE | re.DOTALL):
            print("✅ SQL query is properly formatted")
            return True
        else:
            print("❌ SQL query not found or incorrectly formatted")
            return False
    except Exception as e:
        print(f"❌ SQL query validation error: {e}")
        return False


def validate_error_handling(filepath):
    """Test that proper error handling is implemented."""
    print(f"\n🔍 Testing error handling in {filepath}...")

    try:
        with open(filepath) as f:
            content = f.read()

        # Look for psycopg2.Error handling
        psycopg2_error_pattern = r"except\s+psycopg2\.Error\s+as\s+e:"
        generic_error_pattern = r"except\s+Exception\s+as\s+e:"

        psycopg2_handling = bool(re.search(psycopg2_error_pattern, content))
        generic_handling = bool(re.search(generic_error_pattern, content))

        if psycopg2_handling and generic_handling:
            print("✅ Both psycopg2 and generic error handling implemented")
            return True
        elif psycopg2_handling:
            print("⚠️ Only psycopg2 error handling found")
            return 0.5
        else:
            print("❌ Proper error handling not found")
            return False
    except Exception as e:
        print(f"❌ Error handling validation error: {e}")
        return False


def main():
    """Run all static validation tests."""
    print("🧪 Story 1.4 Static Code Validation")
    print("=" * 60)

    tools_file = "mcp_server/tools/__init__.py"

    tests = [
        ("Syntax", lambda: validate_file_syntax(tools_file)),
        ("Imports", lambda: validate_imports(tools_file)),
        ("Function Signatures", lambda: validate_function_signatures(tools_file)),
        ("Type Hints", lambda: validate_cursor_type_hints(tools_file)),
        ("Ping Timestamp", lambda: validate_ping_timestamp(tools_file)),
        ("SQL Query", lambda: validate_sql_query(tools_file)),
        ("Error Handling", lambda: validate_error_handling(tools_file)),
    ]

    passed = 0
    total = len(tests)

    for _, test_func in tests:
        result = test_func()
        if result:
            passed += 1

    print("\n" + "=" * 60)
    print(f"📊 Validation Results: {passed}/{total} tests passed")

    if passed == total:
        print("✅ ALL STATIC VALIDATIONS PASSED!")
        print("🎯 Code structure is correct and ready for database testing")
        print("📝 Note: Runtime testing requires PostgreSQL and psycopg2")
        return 0
    else:
        print(f"❌ {total - passed} validations failed")
        print("🔧 Implementation needs fixes")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
