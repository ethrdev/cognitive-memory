#!/usr/bin/env python3
"""
Simple Validation using regex instead of AST parsing
"""

import re


def validate_simple_functions(filepath):
    """Test that required functions exist using regex."""
    print(f"\n🔍 Testing function existence in {filepath}...")

    try:
        with open(filepath) as f:
            content = f.read()

        required_functions = [
            r"async def handle_store_raw_dialogue\(",
            r"async def handle_ping\(",
            r"def register_tools\(",
            r"def validate_parameters\(",
        ]

        found_functions = 0
        for func_pattern in required_functions:
            if re.search(func_pattern, content):
                print(
                    f"✅ {func_pattern.replace(' async def ', '').replace(' def ', '')} found"
                )
                found_functions += 1
            else:
                print(
                    f"❌ {func_pattern.replace(' async def ', '').replace(' def ', '')} NOT found"
                )

        if found_functions == len(required_functions):
            print(f"✅ All {len(required_functions)} required functions found")
            return True
        else:
            print(f"❌ {len(required_functions) - found_functions} functions missing")
            return False
    except Exception as e:
        print(f"❌ Function validation error: {e}")
        return False


def main():
    """Run simple validation."""
    print("🧪  Simple Function Validation")
    print("=" * 50)

    tools_file = "mcp_server/tools/__init__.py"
    result = validate_simple_functions(tools_file)

    if result:
        print("\n✅ FUNCTION VALIDATION PASSED!")
        return 0
    else:
        print("\n❌ FUNCTION VALIDATION FAILED!")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
