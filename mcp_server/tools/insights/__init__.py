"""
Insights MCP Tools Package

MCP tools for managing L2 insights (get, update, delete, feedback, history).

Story 26.2: UPDATE Operation - update_insight tool
Story 26.3: DELETE Operation - delete_insight tool
Story 26.4: Context Critic - submit_insight_feedback tool
Story 26.7: Revision History - get_insight_history tool
"""

from __future__ import annotations

from mcp_server.tools.insights.delete import handle_delete_insight
from mcp_server.tools.insights.feedback import handle_submit_insight_feedback
from mcp_server.tools.insights.update import handle_update_insight
from mcp_server.tools.insights.history import handle_get_insight_history

__all__ = [
    "handle_delete_insight",
    "handle_submit_insight_feedback",
    "handle_update_insight",
    "handle_get_insight_history"
]
