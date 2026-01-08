"""
Constants for MCP Server tools.

Story 10.1: Reclassify Memory Sector Tool - ReclassifyStatus and related constants.
"""


class ReclassifyStatus:
    """Status constants for memory sector reclassification operations."""

    SUCCESS = "success"
    INVALID_SECTOR = "invalid_sector"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    CONSENT_REQUIRED = "consent_required"
