"""
Unit tests for mcp_server.utils.constants module.

Story 10.1, Task 1: Verify ReclassifyStatus constants.
"""

import pytest

from mcp_server.utils.constants import ReclassifyStatus


class TestReclassifyStatus:
    """Test ReclassifyStatus string constants."""

    def test_success_constant(self):
        """Test SUCCESS constant value."""
        assert ReclassifyStatus.SUCCESS == "success"
        assert isinstance(ReclassifyStatus.SUCCESS, str)

    def test_invalid_sector_constant(self):
        """Test INVALID_SECTOR constant value."""
        assert ReclassifyStatus.INVALID_SECTOR == "invalid_sector"
        assert isinstance(ReclassifyStatus.INVALID_SECTOR, str)

    def test_not_found_constant(self):
        """Test NOT_FOUND constant value."""
        assert ReclassifyStatus.NOT_FOUND == "not_found"
        assert isinstance(ReclassifyStatus.NOT_FOUND, str)

    def test_ambiguous_constant(self):
        """Test AMBIGUOUS constant value."""
        assert ReclassifyStatus.AMBIGUOUS == "ambiguous"
        assert isinstance(ReclassifyStatus.AMBIGUOUS, str)

    def test_consent_required_constant(self):
        """Test CONSENT_REQUIRED constant value (for Story 10-2)."""
        assert ReclassifyStatus.CONSENT_REQUIRED == "consent_required"
        assert isinstance(ReclassifyStatus.CONSENT_REQUIRED, str)

    def test_all_constants_unique(self):
        """Test that all status constants have unique values."""
        values = [
            ReclassifyStatus.SUCCESS,
            ReclassifyStatus.INVALID_SECTOR,
            ReclassifyStatus.NOT_FOUND,
            ReclassifyStatus.AMBIGUOUS,
            ReclassifyStatus.CONSENT_REQUIRED,
        ]
        assert len(values) == len(set(values)), "All status values must be unique"
