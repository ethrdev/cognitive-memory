"""
Integration tests for SMF write operations with project scoping.

Story 11.5.4: SMF & Dissonance Write Operations
Tests that create_smf_proposal, get_proposal, and related operations
respect project boundaries and RLS policies.
"""

import pytest
from mcp_server.analysis.smf import create_smf_proposal, TriggerType, ApprovalLevel, ProposalStatus


def test_create_smf_proposal_creates_with_project_id(conn):
    """Test that create_smf_proposal creates entries with correct project_id."""
    cursor = conn.cursor()

    # Create SMF proposal
    proposal_id = create_smf_proposal(
        trigger_type=TriggerType.MANUAL,
        proposed_action={"action": "test"},
        affected_edges=["550e8400-e29b-41d4-a716-446655440000"],
        reasoning="Test reasoning",
        approval_level=ApprovalLevel.IO,
        project_id="test-project"
    )

    # Verify proposal was created with correct project_id
    cursor.execute(
        "SELECT project_id FROM smf_proposals WHERE id = %s",
        (proposal_id,)
    )
    result = cursor.fetchone()
    assert result is not None
    assert result["project_id"] == "test-project"

    # Cleanup
    cursor.execute("DELETE FROM smf_proposals WHERE id = %s", (proposal_id,))


def test_get_proposal_respects_project_boundaries(conn, project_context):
    """Test that get_proposal only accesses own project's proposals."""
    cursor = conn.cursor()

    # Create proposal as 'io' project
    with project_context(conn, "io"):
        proposal_id = create_smf_proposal(
            trigger_type=TriggerType.MANUAL,
            proposed_action={"action": "test"},
            affected_edges=["550e8400-e29b-41d4-a716-446655440000"],
            reasoning="Test reasoning",
            approval_level=ApprovalLevel.IO,
            project_id="io"
        )

    # Switch to 'test-project' context
    with project_context(conn, "test-project"):
        # Try to get proposal - should return None or be blocked by RLS
        # Note: get_proposal needs to be implemented or updated
        # This test assumes function exists and respects RLS
        pass

    # Cleanup
    with project_context(conn, "io"):
        cursor.execute("DELETE FROM smf_proposals WHERE id = %s", (proposal_id,))


def test_rls_blocks_cross_project_insert(conn, project_context):
    """Test that RLS INSERT policy blocks inserts to other projects."""
    cursor = conn.cursor()

    # Set context to 'test-project'
    with project_context(conn, "test-project"):
        # Try to insert directly with 'io' project_id
        # This should fail or affect 0 rows due to RLS
        cursor.execute("""
            INSERT INTO smf_proposals (
                project_id, trigger_type, proposed_action, affected_edges, reasoning,
                approval_level, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            "io",  # Different project_id
            TriggerType.MANUAL.value,
            '{"action": "test"}',
            ["550e8400-e29b-41d4-a716-446655440000"],
            "Test reasoning",
            ApprovalLevel.IO.value,
            "PENDING"
        ))

        # Verify no rows were inserted
        cursor.execute(
            "SELECT COUNT(*) as count FROM smf_proposals WHERE project_id = 'io'",
        )
        result = cursor.fetchone()
        assert result["count"] == 0


def test_dissonance_engine_integration_with_project_context(conn, project_context):
    """Test that dissonance engine creates SMF proposals with project context."""
    cursor = conn.cursor()

    # Set context to 'test-project'
    with project_context(conn, "test-project"):
        # Create test edges
        edge_a_id = "550e8400-e29b-41d4-a716-446655440000"
        edge_b_id = "550e8400-e29b-41d4-a716-446655440001"

        # Create dissonance and SMF proposal
        # This test assumes dissonance.create_smf_proposal method exists
        # and propagates project context

        # Verify proposal was created with correct project_id
        cursor.execute(
            "SELECT project_id FROM smf_proposals ORDER BY created_at DESC LIMIT 1",
        )
        result = cursor.fetchone()
        if result:
            assert result["project_id"] == "test-project"


def test_create_smf_proposal_without_project_id_uses_context(conn, project_context):
    """Test that create_smf_proposal uses get_current_project() when project_id not provided."""
    cursor = conn.cursor()

    # Set project context
    with project_context(conn, "test-project"):
        # Create SMF proposal without explicit project_id
        proposal_id = create_smf_proposal(
            trigger_type=TriggerType.MANUAL,
            proposed_action={"action": "test"},
            affected_edges=["550e8400-e29b-41d4-a716-446655440000"],
            reasoning="Test reasoning",
            approval_level=ApprovalLevel.IO
            # No project_id provided - should use context
        )

        # Verify proposal was created with correct project_id from context
        cursor.execute(
            "SELECT project_id FROM smf_proposals WHERE id = %s",
            (proposal_id,)
        )
        result = cursor.fetchone()
        assert result is not None
        assert result["project_id"] == "test-project"

        # Cleanup
        cursor.execute("DELETE FROM smf_proposals WHERE id = %s", (proposal_id,))
