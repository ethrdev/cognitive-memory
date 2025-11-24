#!/usr/bin/env python3
"""
Minimal MCP Test Server
Tests if Claude Code can connect to a basic MCP server
"""

import asyncio
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server

app = Server("test-server")


@app.list_tools()
async def list_tools():
    """List available tools."""
    return [
        {
            "name": "ping",
            "description": "Simple ping tool for testing connectivity",
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls."""
    if name == "ping":
        return {"content": [{"type": "text", "text": "pong"}]}
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Main entry point."""
    try:
        async with stdio_server() as streams:
            await app.run(*streams)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
