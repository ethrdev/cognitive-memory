#!/usr/bin/env python3
"""
Debug Original MCP Server Step by Step
"""

import asyncio
import os
import sys
import traceback

# Load environment
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:54322/postgres"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-api03-YOUR_ANTHROPIC_API_KEY"
os.environ["OPENAI_API_KEY"] = "sk-placeholder"
os.environ["ENVIRONMENT"] = "production"
os.environ["LOG_LEVEL"] = "INFO"

# Change to project directory
os.chdir("/home/ethr/01-projects/ai-experiments/i-o")

print("Starting debug of original MCP server...", file=sys.stderr)

try:
    from mcp_server.db.connection import initialize_pool

    print("✅ Database module imported", file=sys.stderr)

    # Try to initialize database pool
    initialize_pool()
    print("✅ Database pool initialized", file=sys.stderr)

except Exception as e:
    print(f"❌ Database error: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

try:
    from mcp_server.resources import register_resources
    from mcp_server.tools import register_tools

    print("✅ Tools and resources imported", file=sys.stderr)
except Exception as e:
    print(f"❌ Import error: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    # Create server
    server = Server("cognitive-memory")
    print("✅ Server created", file=sys.stderr)

    # Register tools and resources
    tools = register_tools(server)
    resources = register_resources(server)
    print(
        f"✅ Registered {len(tools)} tools and {len(resources)} resources",
        file=sys.stderr,
    )

except Exception as e:
    print(f"❌ Server setup error: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


async def main():
    try:
        print("About to start stdio_server...", file=sys.stderr)

        # Just test stdio_server creation
        async with stdio_server() as _streams:  # noqa: F841
            print("✅ stdio_server created successfully", file=sys.stderr)
            print("Skipping server.run() to isolate the issue", file=sys.stderr)
            await asyncio.sleep(0.1)

    except Exception as e:
        print(f"❌ stdio_server error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    try:
        asyncio.run(main())
        print("✅ Debug completed successfully", file=sys.stderr)
    except Exception as e:
        print(f"❌ Main error: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
