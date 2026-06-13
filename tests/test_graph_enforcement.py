"""
Tests for the Graph-Enforcement-Schicht (2026-06-12).

Covers:
- Project-specific blocking vocabulary (labels + relations) for `tethr`.
- Warning-only behaviour preserved for projects without configured vocabulary.
- graph_add_edge endpoint-existence enforcement (no silent Entity nodes).
- graph_add_node auto-embedding (vector_id set on create).
- delete_edge / delete_node MCP tool handlers.

These tests set the project context synchronously inside each test, so they do
not depend on the async autouse `with_project_context` fixture (which is not
applied under this environment's pytest-asyncio version).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from mcp_server import graph_vocabulary as gv
from mcp_server.middleware.context import clear_context, set_project_id
from mcp_server.tools.delete_edge import handle_delete_edge
from mcp_server.tools.delete_node import handle_delete_node
from mcp_server.tools.graph_add_edge import handle_graph_add_edge
from mcp_server.tools.graph_add_node import handle_graph_add_node


@pytest.fixture
def tethr_ctx():
    set_project_id("tethr")
    yield
    clear_context()


@pytest.fixture
def io_ctx():
    set_project_id("io")
    yield
    clear_context()


# ---------------------------------------------------------------------------
# Vocabulary module
# ---------------------------------------------------------------------------

class TestVocabularyModule:
    def test_tethr_is_enforced(self):
        assert gv.is_vocabulary_enforced("tethr") is True

    def test_other_projects_not_enforced(self):
        for pid in ("io", "ab", "njord", "test-project", None):
            assert gv.is_vocabulary_enforced(pid) is False

    def test_tethr_label_set_matches_taxonomy(self):
        assert gv.get_allowed_labels("tethr") == frozenset({
            "Person", "Agent", "Commitment", "Pattern", "Framework",
            "Area", "Protocol", "Diagnosis", "Project",
        })

    def test_tethr_relation_set_matches_taxonomy(self):
        assert gv.get_allowed_relations("tethr") == frozenset({
            "COMMITTED_TO", "KNOWS", "PRACTICES", "PURSUES", "EXHIBITS",
            "COUNTERACTS", "LEADS_TO", "PART_OF", "REQUIRES", "IMPLEMENTS",
            "SUPPORTS", "DEVELOPS", "SIMILAR_TO", "EVIDENCED_BY", "RELATES_TO",
        })

    def test_validate_label_rejects_unknown_for_tethr(self):
        err = gv.validate_label("tethr", "Quatsch")
        assert err is not None and "Quatsch" in err and "Person" in err

    def test_validate_label_accepts_known_for_tethr(self):
        assert gv.validate_label("tethr", "Person") is None

    def test_validate_label_passthrough_for_unenforced(self):
        assert gv.validate_label("io", "Quatsch") is None

    def test_validate_relation_rejects_unknown_for_tethr(self):
        err = gv.validate_relation("tethr", "BOGUS_VERB")
        assert err is not None and "COMMITTED_TO" in err

    def test_validate_relation_passthrough_for_unenforced(self):
        assert gv.validate_relation("io", "BOGUS_VERB") is None


# ---------------------------------------------------------------------------
# graph_add_node — blocking label enforcement + auto-embedding
# ---------------------------------------------------------------------------

class TestAddNodeEnforcement:
    @pytest.mark.asyncio
    async def test_tethr_rejects_invalid_label(self, tethr_ctx):
        with patch("mcp_server.tools.graph_add_node.add_node") as mock_add, \
             patch("mcp_server.tools.graph_add_node.generate_node_embedding",
                   new=AsyncMock(return_value=999)):
            result = await handle_graph_add_node({"label": "Quatsch", "name": "X"})
        assert result["error"] == "Label not in project vocabulary"
        assert "Person" in result["details"]
        mock_add.assert_not_called()  # blocked before DB

    @pytest.mark.asyncio
    async def test_tethr_accepts_valid_label_and_autoembeds(self, tethr_ctx):
        with patch("mcp_server.tools.graph_add_node.add_node",
                   new=AsyncMock(return_value={
                       "node_id": "n1", "created": True,
                       "label": "Pattern", "name": "Test-Muster"})) as mock_add, \
             patch("mcp_server.tools.graph_add_node.generate_node_embedding",
                   new=AsyncMock(return_value=4242)) as mock_embed:
            result = await handle_graph_add_node({
                "label": "Pattern", "name": "Test-Muster",
                "properties": {"summary": "kurz"},
            })
        assert result["status"] == "success"
        assert result["vector_id"] == 4242  # auto-embedding ran
        mock_embed.assert_awaited_once()
        # vector_id passed through to add_node
        _, kwargs = mock_add.call_args
        assert kwargs["vector_id"] == 4242

    @pytest.mark.asyncio
    async def test_explicit_vector_id_skips_autoembed(self, tethr_ctx):
        with patch("mcp_server.tools.graph_add_node.add_node",
                   new=AsyncMock(return_value={
                       "node_id": "n1", "created": True,
                       "label": "Pattern", "name": "M"})), \
             patch("mcp_server.tools.graph_add_node.generate_node_embedding",
                   new=AsyncMock(return_value=4242)) as mock_embed:
            result = await handle_graph_add_node({
                "label": "Pattern", "name": "M", "vector_id": 7,
            })
        assert result["vector_id"] == 7
        mock_embed.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_io_invalid_label_warning_only_creates(self, io_ctx):
        with patch("mcp_server.tools.graph_add_node.add_node",
                   new=AsyncMock(return_value={
                       "node_id": "n2", "created": True,
                       "label": "Quatsch", "name": "Y"})) as mock_add, \
             patch("mcp_server.tools.graph_add_node.generate_node_embedding",
                   new=AsyncMock(return_value=None)):
            result = await handle_graph_add_node({"label": "Quatsch", "name": "Y"})
        assert result["status"] == "success"  # NOT rejected
        mock_add.assert_awaited_once()


# ---------------------------------------------------------------------------
# graph_add_edge — blocking relation + endpoint-existence enforcement
# ---------------------------------------------------------------------------

class TestAddEdgeEnforcement:
    @pytest.mark.asyncio
    async def test_tethr_rejects_invalid_relation(self, tethr_ctx):
        with patch("mcp_server.tools.graph_add_edge.get_or_create_node") as mock_node:
            result = await handle_graph_add_edge({
                "source_name": "Stefan", "target_name": "Laura",
                "relation": "BOGUS_VERB",
            })
        assert result["error"] == "Relation not in project vocabulary"
        assert "COMMITTED_TO" in result["details"]
        mock_node.assert_not_called()

    @pytest.mark.asyncio
    async def test_tethr_rejects_missing_endpoint(self, tethr_ctx):
        async def fake_get_node(name):
            return {"id": "s1", "name": name} if name == "Stefan" else None
        with patch("mcp_server.tools.graph_add_edge.get_node_by_name",
                   new=AsyncMock(side_effect=fake_get_node)), \
             patch("mcp_server.tools.graph_add_edge.get_or_create_node") as mock_create:
            result = await handle_graph_add_edge({
                "source_name": "Stefan", "target_name": "Nichtda",
                "relation": "KNOWS",
            })
        assert result["error"] == "Endpoint node does not exist"
        assert "Nichtda" in result["details"]
        mock_create.assert_not_called()  # no silent Entity node

    @pytest.mark.asyncio
    async def test_tethr_create_missing_nodes_optin(self, tethr_ctx):
        with patch("mcp_server.tools.graph_add_edge.get_node_by_name",
                   new=AsyncMock(return_value=None)), \
             patch("mcp_server.tools.graph_add_edge.get_or_create_node",
                   new=AsyncMock(return_value={"node_id": "x", "created": True})), \
             patch("mcp_server.tools.graph_add_edge.add_edge",
                   new=AsyncMock(return_value={
                       "edge_id": "e1", "created": True, "source_id": "x",
                       "target_id": "y", "relation": "KNOWS", "weight": 1.0,
                       "memory_sector": "semantic"})):
            result = await handle_graph_add_edge({
                "source_name": "A", "target_name": "B", "relation": "KNOWS",
                "create_missing_nodes": True,
            })
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_io_endpoint_autocreate_preserved(self, io_ctx):
        # Non-enforced project: endpoints auto-created as before, custom verb warns only.
        with patch("mcp_server.tools.graph_add_edge.get_node_by_name") as mock_get, \
             patch("mcp_server.tools.graph_add_edge.get_or_create_node",
                   new=AsyncMock(return_value={"node_id": "x", "created": True})) as mock_create, \
             patch("mcp_server.tools.graph_add_edge.add_edge",
                   new=AsyncMock(return_value={
                       "edge_id": "e1", "created": True, "source_id": "x",
                       "target_id": "y", "relation": "CUSTOM", "weight": 1.0,
                       "memory_sector": "semantic"})):
            result = await handle_graph_add_edge({
                "source_name": "A", "target_name": "B", "relation": "CUSTOM",
            })
        assert result["status"] == "success"
        mock_get.assert_not_called()  # existence pre-check skipped for unenforced
        assert mock_create.await_count == 2


# ---------------------------------------------------------------------------
# delete_edge / delete_node tool handlers
# ---------------------------------------------------------------------------

class TestDeleteTools:
    @pytest.mark.asyncio
    async def test_delete_edge_by_names(self, tethr_ctx):
        with patch("mcp_server.tools.delete_edge.get_edge_by_names",
                   new=AsyncMock(return_value={"id": "e1"})), \
             patch("mcp_server.tools.delete_edge.delete_edge",
                   new=AsyncMock(return_value={
                       "deleted": True, "edge_id": "e1",
                       "was_constitutive": False})) as mock_del:
            result = await handle_delete_edge({
                "source_name": "A", "target_name": "B", "relation": "SIMILAR_TO",
            })
        assert result["deleted"] is True
        mock_del.assert_awaited_once_with(edge_id="e1", consent_given=False)

    @pytest.mark.asyncio
    async def test_delete_edge_not_found(self, tethr_ctx):
        with patch("mcp_server.tools.delete_edge.get_edge_by_names",
                   new=AsyncMock(return_value=None)):
            result = await handle_delete_edge({
                "source_name": "A", "target_name": "B", "relation": "SIMILAR_TO",
            })
        assert result["status"] == "not_found"
        assert result["deleted"] is False

    @pytest.mark.asyncio
    async def test_delete_edge_constitutive_blocked(self, tethr_ctx):
        from mcp_server.db.graph import ConstitutiveEdgeProtectionError

        # Build the exception without calling its async __init__.
        exc = ConstitutiveEdgeProtectionError.__new__(ConstitutiveEdgeProtectionError)
        exc.message = "constitutive blocked"
        with patch("mcp_server.tools.delete_edge.delete_edge",
                   new=AsyncMock(side_effect=exc)):
            result = await handle_delete_edge({"edge_id": "e1"})
        assert result["status"] == "blocked"
        assert "consent_given" in result["hint"]

    @pytest.mark.asyncio
    async def test_delete_node_requires_confirm(self, tethr_ctx):
        with patch("mcp_server.tools.delete_node.delete_node") as mock_del:
            result = await handle_delete_node({"name": "SomeNode"})
        assert result["status"] == "confirmation_required"
        mock_del.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_node_by_name_with_confirm(self, tethr_ctx):
        with patch("mcp_server.tools.delete_node.get_node_by_name",
                   new=AsyncMock(return_value={"id": "n1"})), \
             patch("mcp_server.tools.delete_node.delete_node",
                   new=AsyncMock(return_value={
                       "deleted": True, "node_id": "n1",
                       "name": "SomeNode", "edges_deleted": 3})) as mock_del:
            result = await handle_delete_node({"name": "SomeNode", "confirm": True})
        assert result["deleted"] is True
        assert result["edges_deleted"] == 3
        mock_del.assert_awaited_once_with(node_id="n1")

    @pytest.mark.asyncio
    async def test_delete_node_not_found(self, tethr_ctx):
        with patch("mcp_server.tools.delete_node.get_node_by_name",
                   new=AsyncMock(return_value=None)):
            result = await handle_delete_node({"name": "Ghost", "confirm": True})
        assert result["status"] == "not_found"
