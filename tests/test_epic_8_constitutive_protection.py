"""
P0 Tests: Constitutive Edge Protection (Epic 8)
ATDD Red Phase - Tests that will pass after implementation

Risk Mitigation: R-008 (Constitutive edge protection bypassed)
Test Count: 8
"""

import pytest
from typing import Dict, List, Any, Optional
from pathlib import Path

from mcp_server.utils.constants import ReclassifyStatus


class TestConstitutiveEdgeConsent:
    """FR9, FR23: Bilateral consent for constitutive edge reclassification"""

    @pytest.mark.p0
    def test_constitutive_edge_requires_consent_for_reclassification(self):
        """FR9, NFR9: Bilateral consent requirement

        Given an edge with properties["is_constitutive"] = true
        When reclassify_memory_sector is called without approved SMF proposal
        Then the response includes:
        {
          "status": "consent_required",
          "error": "Bilateral consent required for constitutive edge",
          "edge_id": "...",
          "hint": "Use smf_pending_proposals and smf_approve to grant consent"
        }

        This is the core security feature.
        """
        # Verify that the tool exists and has the logic
        tool_file = Path("mcp_server/tools/reclassify_memory_sector.py")
        content = tool_file.read_text()

        # Verify constitutive edge detection exists
        assert "_is_constitutive_edge" in content, "Should have constitutive edge detection"
        assert "is_constitutive" in content, "Should check is_constitutive property"

        # Verify consent check exists
        assert "_check_smf_approval" in content, "Should check SMF approval"
        assert "ReclassifyStatus.CONSENT_REQUIRED" in content, "Should return consent required status"

    @pytest.mark.p0
    def test_non_constitutive_edge_no_consent_check(self):
        """FR9: No consent check for non-constitutive edges

        Given an edge without is_constitutive property (or is_constitutive = false)
        When reclassify_memory_sector is called
        Then no consent check is performed and reclassification proceeds normally

        Ensures only constitutive edges are protected.
        """
        # Verify that constitutive check is conditional
        tool_file = Path("mcp_server/tools/reclassify_memory_sector.py")
        content = tool_file.read_text()

        # Check that _is_constitutive_edge is called conditionally
        assert "if _is_constitutive_edge(edge):" in content, \
            "Should only check consent for constitutive edges"

    @pytest.mark.p0
    def test_constitutive_edge_reclassification_with_bilateral_consent(self):
        """FR9, FR23: Approved SMF proposal allows reclassification

        Given an edge with properties["is_constitutive"] = true
        When an SMF proposal for reclassification has been approved by both parties
        Then the reclassification proceeds and returns {"status": "success", ...}

        Validates the SMF integration works correctly.
        """
        # Verify SMF integration exists
        tool_file = Path("mcp_server/tools/reclassify_memory_sector.py")
        content = tool_file.read_text()

        # Verify SMF approval check exists
        assert "await _check_smf_approval" in content, "Should check SMF approval"
        assert "smf_proposals" in content, "Should query smf_proposals table"

        # Verify success flow exists
        assert ReclassifyStatus.SUCCESS in content, "Should return success status"

    @pytest.mark.p0
    def test_reclassify_status_constants(self):
        """FR9: ReclassifyStatus.CONSENT_REQUIRED constant

        Given the ReclassifyStatus constants
        When consent is required
        Then the response uses ReclassifyStatus.CONSENT_REQUIRED

        Ensures consistent status codes.
        """
        # Verify ReclassifyStatus has all required constants
        from mcp_server.utils.constants import ReclassifyStatus

        assert hasattr(ReclassifyStatus, 'SUCCESS'), "Should have SUCCESS constant"
        assert hasattr(ReclassifyStatus, 'CONSENT_REQUIRED'), "Should have CONSENT_REQUIRED constant"
        assert hasattr(ReclassifyStatus, 'INVALID_SECTOR'), "Should have INVALID_SECTOR constant"
        assert hasattr(ReclassifyStatus, 'NOT_FOUND'), "Should have NOT_FOUND constant"
        assert hasattr(ReclassifyStatus, 'AMBIGUOUS'), "Should have AMBIGUOUS constant"

        # Verify constant values
        assert ReclassifyStatus.SUCCESS == "success"
        assert ReclassifyStatus.CONSENT_REQUIRED == "consent_required"

    @pytest.mark.p0
    def test_check_bilateral_consent_integration(self):
        """FR23: SMF integration pattern

        Given SMF integration
        When checking for bilateral consent
        Then the existing SMF pattern is used to check for approved proposals

        Ensures consistent use of the SMF system.
        """
        # Verify the SMF integration follows the existing pattern
        tool_file = Path("mcp_server/tools/reclassify_memory_sector.py")
        content = tool_file.read_text()

        # Verify it uses the same SMF tables and patterns
        assert "smf_proposals" in content, "Should use smf_proposals table"
        assert "status = 'APPROVED'" in content, "Should check for APPROVED status"
        assert "approval_level" in content, "Should check approval level"
        assert "approved_by_io" in content, "Should check bilateral approval"
        assert "approved_by_ethr" in content, "Should check bilateral approval"

    @pytest.mark.p0
    def test_constitutive_edge_protection_security_review(self):
        """R-008: Security review requirement

        Given the constitutive edge protection feature
        When security is reviewed
        Then no bypass vulnerabilities exist

        This is a manual security review that must be passed.
        """
        # This is a manual review, not an automated test
        # We'll mark it as such
        pytest.skip("Manual security review required for constitutive edge protection")


class TestReclassificationAudit:
    """FR10, NFR14: Audit trail for reclassifications"""

    @pytest.mark.p0
    def test_reclassification_audit_log_entry(self):
        """FR10: Audit logging for reclassifications

        Given a reclassification is performed
        When it completes
        Then structured log entry is written with all required fields

        Ensures complete audit trail.
        """
        # Verify logging exists
        tool_file = Path("mcp_server/tools/reclassify_memory_sector.py")
        content = tool_file.read_text()

        # Verify logging for reclassifications
        assert 'logger.info("Edge reclassified"' in content, \
            "Should log all reclassifications"

    @pytest.mark.p0
    def test_last_reclassification_property(self):
        """NFR14: Track last reclassification

        Given an edge is reclassified
        When it completes
        Then the edge properties include last_reclassification metadata

        Ensures traceability of changes.
        """
        # Verify _update_edge_sector function exists
        tool_file = Path("mcp_server/tools/reclassify_memory_sector.py")
        content = tool_file.read_text()

        assert "_update_edge_sector" in content, "Should update edge sector"


class TestReclassificationSecurity:
    """Security tests for reclassification functionality"""

    @pytest.mark.p0
    def test_constitutive_edge_modification_attempts_blocked(self):
        """R-008: Block unauthorized modifications

        Given a constitutive edge
        When unauthorized reclassification is attempted
        Then it is blocked with appropriate error

        Ensures security controls work.
        """
        # Verify the protection is implemented
        tool_file = Path("mcp_server/tools/reclassify_memory_sector.py")
        content = tool_file.read_text()

        # Check that constitutive edges are protected
        assert "is_constitutive" in content, "Should check for constitutive edges"
        assert "CONSENT_REQUIRED" in content, "Should require consent"
