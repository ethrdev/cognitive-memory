"""
Insights MCP Tools Package

MCP tools for managing L2 insights (get, update, delete).

Story 26.2: UPDATE Operation - update_insight tool
Story 26.3: DELETE Operation - delete_insight tool
"""

from __future__ import annotations

from mcp_server.tools.insights.delete import handle_delete_insight
from mcp_server.tools.insights.update import handle_update_insight

__all__ = ["handle_delete_insight", "handle_update_insight"]
