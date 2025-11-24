#!/usr/bin/env python3
"""
Debug MCP Server Issues
"""

import asyncio
import sys
import traceback

from mcp.server.stdio import stdio_server


async def debug_stdio():
    """Debug stdio_server issues."""
    try:
        print("About to create stdio_server...", file=sys.stderr)
        async with stdio_server() as streams:
            print("stdio_server created successfully", file=sys.stderr)
            print(f"Streams: {streams}", file=sys.stderr)
            # Just wait a moment then exit
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Error in stdio_server: {e}", file=sys.stderr)
        print("Full traceback:", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)


if __name__ == "__main__":
    print("Starting debug...", file=sys.stderr)
    try:
        asyncio.run(debug_stdio())
    except Exception as e:
        print(f"Error in asyncio.run: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
