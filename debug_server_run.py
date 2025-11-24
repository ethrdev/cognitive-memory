#!/usr/bin/env python3
"""
Debug server.run() specifically
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

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    from mcp_server.db.connection import initialize_pool
    from mcp_server.resources import register_resources
    from mcp_server.tools import register_tools

    # Setup server
    initialize_pool()
    server = Server("cognitive-memory")
    tools = register_tools(server)
    resources = register_resources(server)
    print(
        f"✅ Server setup complete: {len(tools)} tools, {len(resources)} resources",
        file=sys.stderr,
    )

except Exception as e:
    print(f"❌ Setup error: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)


async def main():
    try:
        print("About to call server.run()...", file=sys.stderr)

        async with stdio_server() as streams:
            print("Got streams, calling server.run()...", file=sys.stderr)
            # Try to call server.run() but catch any errors
            try:
                await server.run(*streams)
                print("server.run() completed", file=sys.stderr)
            except Exception as e:
                print(f"Error in server.run(): {e}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    except Exception as e:
        print(f"Error in stdio_server: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error in main: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
