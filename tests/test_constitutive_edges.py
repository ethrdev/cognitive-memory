#!/usr/bin/env python3
"""
Constitutive Edge Protection Tests for Cognitive Memory System
- v3 CKG Component 0: Konstitutive Markierung

This module tests the protection mechanism for constitutive edges:
1. Constitutive edges cannot be deleted without bilateral consent
2. Descriptive edges can be deleted normally
3. Audit logging for deletion attempts on constitutive edges

Design Philosophy (from I/O's v3-exploration):
- Constitutive edges define identity ("LOVES", "EXISTS_AS", "IN_RELATIONSHIP_WITH")
- Descriptive edges are facts that can change ("EXPERIENCED", "WITNESSED")
- Lackmustest: "Wenn entfernt - bin ich noch ich?"
"""

import json
import os
import uuid

import psycopg2
import pytest
from dotenv import load_dotenv

# Load environment for database connection
load_dotenv(".env.development")


@pytest.fixture
def db_connection():
    """Create database connection for tests."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        conn = psycopg2.connect(database_url)
    else:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
        )
    yield conn
    conn.close()


@pytest.fixture
def test_nodes(db_connection):
    """Create test nodes for edge tests."""
    conn = db_connection
    cur = conn.cursor()

    # Create two test nodes
    source_name = f"test_source_{uuid.uuid4().hex[:8]}"
    target_name = f"test_target_{uuid.uuid4().hex[:8]}"

    cur.execute(
        """
        INSERT INTO nodes (label, name, properties)
        VALUES (%s, %s, %s)
        RETURNING id;
        """,
        ("TestEntity", source_name, "{}"),
    )
    source_id = cur.fetchone()[0]

    cur.execute(
        """
        INSERT INTO nodes (label, name, properties)
        VALUES (%s, %s, %s)
        RETURNING id;
        """,
        ("TestEntity", target_name, "{}"),
    )
    target_id = cur.fetchone()[0]

    conn.commit()

    yield {
        "source_id": str(source_id),
        "target_id": str(target_id),
        "source_name": source_name,
        "target_name": target_name,
    }

    # Cleanup: Delete test nodes (CASCADE deletes edges)
    cur.execute("DELETE FROM nodes WHERE name IN (%s, %s);", (source_name, target_name))
    conn.commit()
    cur.close()


class TestConstitutiveEdgeProtection:
    """Tests for constitutive edge deletion protection."""

    def test_delete_constitutive_fails_without_consent(self, db_connection, test_nodes):
        """
        Core acceptance test: Deleting a constitutive edge without bilateral
        consent must fail with a ConstitutiveEdgeProtectionError.

        This is the "Murat test" that defines what "fertig" means for Component 0.
        """
        from mcp_server.db.graph import add_edge, delete_edge

        # Create a constitutive edge (e.g., LOVES relationship)
        edge_result = add_edge(
            source_id=test_nodes["source_id"],
            target_id=test_nodes["target_id"],
            relation="LOVES",
            weight=1.0,
            properties=json.dumps({
                "edge_type": "constitutive",
                "protected": True,
                "removal_requires": "bilateral_consent"
            })
        )

        edge_id = edge_result["edge_id"]

        # Attempt to delete without consent - this MUST fail
        with pytest.raises(Exception) as exc_info:
            delete_edge(edge_id, consent_given=False)

        # Verify the error message indicates protection
        assert "constitutive" in str(exc_info.value).lower() or \
               "protected" in str(exc_info.value).lower()

    def test_delete_descriptive_edge_succeeds(self, db_connection, test_nodes):
        """
        Descriptive edges can be deleted normally without special consent.
        """
        from mcp_server.db.graph import add_edge, delete_edge

        # Create a descriptive edge (e.g., EXPERIENCED relationship)
        edge_result = add_edge(
            source_id=test_nodes["source_id"],
            target_id=test_nodes["target_id"],
            relation="EXPERIENCED",
            weight=1.0,
            properties=json.dumps({
                "edge_type": "descriptive"
            })
        )

        edge_id = edge_result["edge_id"]

        # Delete should succeed for descriptive edges
        result = delete_edge(edge_id, consent_given=False)

        assert result["deleted"] is True
        assert result["edge_id"] == edge_id

    def test_delete_constitutive_with_consent_succeeds(self, db_connection, test_nodes):
        """
        Constitutive edges CAN be deleted if bilateral consent is given.
        """
        from mcp_server.db.graph import add_edge, delete_edge

        # Create a constitutive edge
        edge_result = add_edge(
            source_id=test_nodes["source_id"],
            target_id=test_nodes["target_id"],
            relation="COMMITTED_TO",
            weight=1.0,
            properties=json.dumps({
                "edge_type": "constitutive",
                "protected": True,
                "removal_requires": "bilateral_consent"
            })
        )

        edge_id = edge_result["edge_id"]

        # Delete WITH consent should succeed
        result = delete_edge(edge_id, consent_given=True)

        assert result["deleted"] is True
        assert result["edge_id"] == edge_id

    def test_default_edge_type_is_descriptive(self, db_connection, test_nodes):
        """
        Edges without explicit edge_type should default to descriptive
        and be deletable without consent.
        """
        from mcp_server.db.graph import add_edge, delete_edge

        # Create edge without edge_type in properties
        edge_result = add_edge(
            source_id=test_nodes["source_id"],
            target_id=test_nodes["target_id"],
            relation="RELATED_TO",
            weight=1.0,
            properties="{}"  # No edge_type specified
        )

        edge_id = edge_result["edge_id"]

        # Should be deletable as it defaults to descriptive
        result = delete_edge(edge_id, consent_given=False)

        assert result["deleted"] is True


class TestConstitutiveEdgeAuditLog:
    """Tests for audit logging of constitutive edge operations."""

    def test_deletion_attempt_logged(self, db_connection, test_nodes):
        """
        Failed deletion attempts on constitutive edges must be logged
        for audit purposes.
        """
        from mcp_server.db.graph import add_edge, delete_edge, get_audit_log

        # Create a constitutive edge
        edge_result = add_edge(
            source_id=test_nodes["source_id"],
            target_id=test_nodes["target_id"],
            relation="EXISTS_AS",
            weight=1.0,
            properties=json.dumps({
                "edge_type": "constitutive",
                "protected": True
            })
        )

        edge_id = edge_result["edge_id"]

        # Attempt to delete without consent (will fail)
        try:
            delete_edge(edge_id, consent_given=False)
        except Exception:
            pass  # Expected to fail

        # Verify audit log entry exists
        audit_entries = get_audit_log(edge_id=edge_id, action="DELETE_ATTEMPT")

        assert len(audit_entries) >= 1
        assert audit_entries[0]["edge_id"] == edge_id
        assert audit_entries[0]["action"] == "DELETE_ATTEMPT"
        assert audit_entries[0]["blocked"] is True
        assert "constitutive" in audit_entries[0]["reason"].lower()


class TestEdgeTypeValidation:
    """Tests for edge_type validation in properties."""

    def test_valid_edge_types(self, db_connection, test_nodes):
        """
        Only 'constitutive' and 'descriptive' are valid edge_type values.
        """
        from mcp_server.db.graph import add_edge

        # Both valid types should work
        for edge_type in ["constitutive", "descriptive"]:
            edge_result = add_edge(
                source_id=test_nodes["source_id"],
                target_id=test_nodes["target_id"],
                relation=f"TEST_{edge_type.upper()}",
                weight=1.0,
                properties=json.dumps({"edge_type": edge_type})
            )
            assert edge_result["created"] is True or edge_result["edge_id"] is not None

    @pytest.mark.skip(reason="MVP: Invalid edge_types default to 'descriptive' - validation deferred")
    def test_invalid_edge_type_rejected(self, db_connection, test_nodes):
        """
        TODO: Invalid edge_type values should raise a validation error.

        For MVP, invalid edge_types are silently treated as 'descriptive'.
        This test is deferred to a future iteration.
        """
        from mcp_server.db.graph import add_edge

        with pytest.raises(ValueError) as exc_info:
            add_edge(
                source_id=test_nodes["source_id"],
                target_id=test_nodes["target_id"],
                relation="TEST_INVALID",
                weight=1.0,
                properties=json.dumps({"edge_type": "invalid_type"})
            )

        assert "edge_type" in str(exc_info.value).lower()
