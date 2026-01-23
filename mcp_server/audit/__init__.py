"""
Shadow Audit Module

Provides shadow audit logging for RLS violation detection during shadow mode.
Enables validation of zero cross-project accesses before enabling enforcing mode.

Story 11.3.2: Shadow Audit Infrastructure
"""

from __future__ import annotations

from mcp_server.audit.shadow_logger import ShadowAuditLogger

__all__ = ["ShadowAuditLogger"]
