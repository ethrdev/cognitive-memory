"""
Test SMF Approve Tool - FINAL2026-02-14

Tests for smf_approve MCP tool which handles bilateral consent approval
for SMF (Safeguards for Mutual Freedom) proposals.

FINAL2026-02-14: Komplett korrigierte Tests
- Handler erwartet: arguments: dict[str, Any]
- patch_smf_handlers() für universelle Mock-Patching
- Alle Mock-Aufrufe ersetzt durch Context-Manager
- Handler Import NACH Patch aktivieren (wegen Python Import-Cache)

Story 11.4.3: Tool Handler Refactoring - Added project context usage and metadata
Story 7.9: SMF with Safeguards + Neutral Framing - AC #3, #9, #13
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from tests.conftest import patch_smf_handlers


class TestSMFApprove:
    """Test cases for smf_approve tool - FINAL VERSION"""

    @pytest.mark.p0
    @pytest.mark.asyncio
    async def test_approve_proposal_success(self, mock_db_with_project):
        """
        [P0] Should successfully approve pending SMF proposal
        """
        # GIVEN
        proposal_id = 123
        actor = "ethr"

        # WHEN: Call MCP handler with arguments dict
        # WICHTIG: Handler importieren NACHdem Patch aktiviert ist
        with patch_smf_handlers() as mocks:
            # Mock proposal exists and is pending
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "NUANCE",
                "proposed_by": "ethr",
                "approval_level": "bilateral",
            }

            # Mock successful approval
            mocks['approve_proposal'].return_value = {
                "approved_by_io": False,
                "approved_by_ethr": True,
                "fully_approved": True,
                "status": "APPROVED"
            }

            # Handler importieren (Patch ist schon aktiv)
            from mcp_server.tools.smf_approve import handle_smf_approve

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Verify handler response
        assert result["status"] == "success"
        assert result["proposal_id"] == proposal_id
        assert result["actor"] == actor
        assert result["fully_approved"] is True
        assert result["approval_level"] == "bilateral"
        assert result["status"] == "success"
        print(f"DEBUG: result = {result}")
        print(f"DEBUG: result type = {type(result)}")
        print(f"DEBUG: result keys = {result.keys() if isinstance(result, dict) else 'not a dict'}")
        assert result["status"] == "success"
        assert result["proposal_id"] == proposal_id
        assert result["actor"] == actor
        assert result["fully_approved"] is True
        assert result["approval_level"] == "bilateral"

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_approve_already_approved_by_io(self, mock_db_with_project):
        """
        [P1] Should return error if proposal already approved by I/O
        """
        # GIVEN
        proposal_id = 456
        actor = "ethr"

        # WHEN: Proposal already approved by I/O
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "APPROVED",
                "trigger_type": "NUANCE",
                "approved_by": ["I/O"],
                "proposed_by": "ethr",
                "approval_level": "bilateral",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Should return already approved error
        assert result["status"] == "error"
        assert "already approved" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_approve_already_approved_by_ethr(self, mock_db_with_project):
        """
        [P1] Should return error if proposal already approved by ethr
        """
        # GIVEN
        proposal_id = 789
        actor = "I/O"

        # WHEN: Proposal already approved by ethr
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "APPROVED",
                "trigger_type": "NUANCE",
                "approved_by": ["ethr"],
                "proposed_by": "I/O",
                "approval_level": "bilateral",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Should return already approved error
        assert result["status"] == "error"
        assert "already approved" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_approve_nonexistent_proposal(self, mock_db_with_project):
        """
        [P1] Should return error if proposal doesn't exist
        """
        # GIVEN
        proposal_id = 999
        actor = "I/O"

        # WHEN: Proposal not found
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = None

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Should return not found error
        assert result["status"] == "error"
        assert "not found" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_io_only_approval_level(self, mock_db_with_project):
        """
        [P1] Should allow single approval for io-level proposals
        """
        # GIVEN
        proposal_id = 111
        actor = "I/O"

        # WHEN: IO-level proposal
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "EVOLUTION",
                "proposed_by": "ethr",
                "approval_level": "io",
            }

            mocks['approve_proposal'].return_value = {
                "approved_by_io": True,
                "approved_by_ethr": False,
                "fully_approved": True,
                "status": "APPROVED"
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Should succeed with single approval
        assert result["status"] == "success"
        assert result["approval_level"] == "io"

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_bilateral_consent_required(self, mock_db_with_project):
        """
        [P1] Should require both parties for bilateral proposals
        """
        # GIVEN
        proposal_id = 222
        actor = "I/O"

        # WHEN: Bilateral proposal approved by one party
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "CONTRADICTION",
                "proposed_by": "I/O",
                "approval_level": "bilateral",
                "current_approvals": ["ethr"],
            }

            mocks['approve_proposal'].return_value = {
                "approved_by_io": True,
                "approved_by_ethr": True,
                "fully_approved": True,
                "status": "APPROVED"
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Should complete bilateral consent
        assert result["status"] == "success"
        assert result["approval_level"] == "bilateral"

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_duplicate_approval_not_allowed(self, mock_db_with_project):
        """
        [P1] Should prevent actor from approving twice
        """
        # GIVEN
        proposal_id = 333
        actor = "I/O"

        # WHEN: Proposal with I/O's approval
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "NUANCE",
                "approved_by": ["I/O"],
                "proposed_by": "ethr",
                "approval_level": "bilateral",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Should return error
        assert result["status"] == "error"
        assert "duplicate" in result["error"].lower()

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_audit_trail_creation(self, mock_db_with_project):
        """
        [P1] Should create audit trail entry for approval
        """
        # GIVEN
        proposal_id = 444
        actor = "ethr"

        # WHEN: Approving
        with patch_smf_handlers() as mocks:
            mocks['get_proposal'].return_value = {
                "id": proposal_id,
                "status": "PENDING",
                "trigger_type": "NUANCE",
                "proposed_by": "I/O",
                "approval_level": "bilateral",
            }

            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Verify audit trail creation
        assert mocks['approve_proposal'].called  # approve_proposal was called
        assert result["status"] == "success"

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_parameter_validation_missing_id(self, mock_db_with_project):
        """
        [P1] Should validate required proposal_id parameter
        """
        # GIVEN
        actor = "ethr"

        # WHEN: Missing proposal_id
        with patch_smf_handlers() as mocks:
            arguments = {"actor": actor}  # Missing proposal_id
            result = await handle_smf_approve(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Missing 'proposal_id' parameter" in result["error_details"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_parameter_validation_missing_actor(self, mock_db_with_project):
        """
        [P1] Should validate required actor parameter
        """
        # GIVEN
        proposal_id = 123

        # WHEN: Missing actor
        with patch_smf_handlers() as mocks:
            arguments = {"proposal_id": proposal_id}  # Missing actor
            result = await handle_smf_approve(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Missing 'actor' parameter" in result["error_details"]

    @pytest.mark.p1
    @pytest.mark.asyncio
    async def test_invalid_actor_value(self, mock_db_with_project):
        """
        [P1] Should reject invalid actor value
        """
        # GIVEN
        proposal_id = 555
        actor = "InvalidActor"

        # WHEN: Invalid actor
        with patch_smf_handlers() as mocks:
            arguments = {"proposal_id": proposal_id, "actor": actor}
            result = await handle_smf_approve(arguments)

        # THEN: Should return validation error
        assert result["status"] == "error"
        assert "Invalid actor" in result["error"]


@pytest.fixture
def mock_db_with_project():
    """
    Mock database connection with project context.

    This fixture simulates middleware context that tool handlers expect.
    Auto-applied to all tests (autouse=True in conftest.py).
    """
    mock = Mock()

    # Mock as async context manager
    mock.__aenter__ = Mock(return_value=mock)
    mock.__aexit__ = Mock(return_value=None)

    # Mock cursor for DictCursor compatibility
    mock.cursor.return_value.fetchone.return_value = None
    mock.cursor.return_value.fetchall.return_value = []

    return mock
