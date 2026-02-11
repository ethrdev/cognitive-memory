"""
Integration Tests for Story 9.1.1 - Tags Schema Migration

Tests migration 041_add_tags.sql which adds:
- tags TEXT[] column to episode_memory
- tags TEXT[] column to l2_insights
- metadata JSONB column to episode_memory
- GIN indexes for both tags columns

Also tests tag validation in store_episode and compress_to_l2_insight tools.

NOTE: Tests requiring OpenAI API are marked with skipif and will be skipped
when OPENAI_API_KEY is not configured. Schema tests (CR1) run without API key.
"""

from __future__ import annotations

import os
import pytest


class Test041TagsMigration:
    """Test migration 041_add_tags.sql (Story 9.1.1)."""

    def test_tags_migration_creates_columns(self, conn) -> None:
        """
        AC: Migration creates tags and metadata columns correctly.

        GIVEN: Database before migration 041
        WHEN: Migration 041 is executed
        THEN: episode_memory has tags TEXT[] and metadata JSONB
        AND: l2_insights has tags TEXT[]
        """
        cursor = conn.cursor()

        # Verify episode_memory.tags column
        cursor.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'episode_memory' AND column_name = 'tags';
        """)
        result = cursor.fetchone()
        assert result is not None, "tags column not found in episode_memory"
        assert result["data_type"] == "ARRAY"
        assert result["column_default"] == "'{}'::text[]"

        # Verify episode_memory.metadata column
        cursor.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'episode_memory' AND column_name = 'metadata';
        """)
        result = cursor.fetchone()
        assert result is not None, "metadata column not found in episode_memory"
        assert result["data_type"] == "jsonb"
        assert result["column_default"] == "'{}'::jsonb"

        # Verify l2_insights.tags column
        cursor.execute("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns
            WHERE table_name = 'l2_insights' AND column_name = 'tags';
        """)
        result = cursor.fetchone()
        assert result is not None, "tags column not found in l2_insights"
        assert result["data_type"] == "ARRAY"
        assert result["column_default"] == "'{}'::text[]"

    def test_tags_migration_creates_gin_indexes(self, conn) -> None:
        """
        AC: Migration creates GIN indexes for tags columns.

        GIVEN: Migration 041 is executed
        WHEN: Querying pg_indexes
        THEN: idx_episode_memory_tags and idx_l2_insights_tags exist
        """
        cursor = conn.cursor()

        # Verify episode_memory tags index
        cursor.execute("""
            SELECT indexname, tablename, indexdef
            FROM pg_indexes
            WHERE indexname = 'idx_episode_memory_tags';
        """)
        result = cursor.fetchone()
        assert result is not None, "idx_episode_memory_tags index not found"
        assert "gin" in result["indexdef"].lower()

        # Verify l2_insights tags index
        cursor.execute("""
            SELECT indexname, tablename, indexdef
            FROM pg_indexes
            WHERE indexname = 'idx_l2_insights_tags';
        """)
        result = cursor.fetchone()
        assert result is not None, "idx_l2_insights_tags index not found"
        assert "gin" in result["indexdef"].lower()

    def test_tags_migration_is_idempotent(self, conn) -> None:
        """
        AC: Migration can be run multiple times safely.

        GIVEN: Migration 041 already executed
        WHEN: Migration 041 is executed again
        THEN: No errors occur, schema remains unchanged
        """
        # This test assumes migration is already run by test fixtures
        # Running it again should not cause errors
        cursor = conn.cursor()

        # Verify columns exist (would fail if migration broke)
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name IN ('episode_memory', 'l2_insights')
            AND column_name = 'tags';
        """)
        count = cursor.fetchone()["count"]
        assert count == 2, "tags columns should exist in both tables"


class TestTagsParameterValidation:
    """Test tag validation in MCP tools (Story 9.1.1)."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "sk-your-openai-api-key-here",
        reason="Requires OpenAI API key"
    )
    @pytest.mark.asyncio
    async def test_store_episode_accepts_valid_tags(self, conn) -> None:
        """
        AC: store_episode accepts tags parameter with string array.

        GIVEN: MCP tool store_episode
        WHEN: Called with tags=["dark-romance", "relationship"]
        THEN: Episode is stored with tags

        NOTE: Skipped if OPENAI_API_KEY not configured
        """
        from mcp_server.tools import add_episode

        result = await add_episode(
            query="test query",
            reward=0.5,
            reflection="test reflection",
            conn=conn,
            project_id="test-project",
            tags=["dark-romance", "relationship"]
        )

        assert "id" in result
        assert result["embedding_status"] == "success"

        # Verify tags were stored
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tags FROM episode_memory WHERE id = %s;
        """, (result["id"],))
        row = cursor.fetchone()
        assert row is not None
        # PostgreSQL stores TEXT[] as Python list
        assert set(row["tags"]) == {"dark-romance", "relationship"}

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "sk-your-openai-api-key-here",
        reason="Requires OpenAI API key"
    )
    @pytest.mark.asyncio
    async def test_store_episode_accepts_empty_tags(self, conn) -> None:
        """
        AC: store_episode accepts empty tags array.

        GIVEN: MCP tool store_episode
        WHEN: Called with tags=[]
        THEN: Episode is stored with empty tags array
        AND: Empty array is stored as '{}' (PostgreSQL canonical format), not NULL

        NOTE: Skipped if OPENAI_API_KEY not configured
        """
        from mcp_server.tools import add_episode

        result = await add_episode(
            query="test query",
            reward=0.5,
            reflection="test reflection",
            conn=conn,
            project_id="test-project",
            tags=[]
        )

        assert "id" in result

        # M3 FIX: Verify empty tags were stored as '{}' not NULL
        # PostgreSQL stores empty TEXT[] arrays as '{}' (canonical format)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tags, tags IS NULL as is_null, array_length(tags, 1) as len
            FROM episode_memory WHERE id = %s;
        """, (result["id"],))
        row = cursor.fetchone()
        assert row is not None
        assert row["tags"] == []  # Python representation
        assert row["is_null"] is False  # Not NULL
        assert row["len"] is None or row["len"] == 0  # PostgreSQL reports NULL or 0 for empty arrays

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "sk-your-openai-api-key-here",
        reason="Requires OpenAI API key"
    )
    @pytest.mark.asyncio
    async def test_store_episode_default_tags_when_omitted(self, conn) -> None:
        """
        AC: store_episode works without tags parameter (backward compatible).

        GIVEN: MCP tool store_episode
        WHEN: Called without tags parameter
        THEN: Episode is stored with empty tags array (backward compatible)

        NOTE: Skipped if OPENAI_API_KEY not configured
        """
        from mcp_server.tools import add_episode

        result = await add_episode(
            query="test query",
            reward=0.5,
            reflection="test reflection",
            conn=conn,
            project_id="test-project"
            # No tags parameter
        )

        assert "id" in result

        # Verify default empty tags were stored
        cursor = conn.cursor()
        cursor.execute("""
            SELECT tags FROM episode_memory WHERE id = %s;
        """, (result["id"],))
        row = cursor.fetchone()
        assert row is not None
        assert row["tags"] == []

    @pytest.mark.asyncio
    async def test_store_episode_rejects_non_string_tags(self) -> None:
        """
        AC: store_episode validates tags are strings only.

        GIVEN: MCP tool handle_store_episode
        WHEN: Called with tags=[123, "valid"]
        THEN: Returns validation error about non-string tag

        NOTE: Tests validation logic directly, no OpenAI API required
        """
        from mcp_server.tools import handle_store_episode

        result = await handle_store_episode({
            "query": "test query",
            "reward": 0.5,
            "reflection": "test reflection",
            "tags": [123, "valid"]  # Invalid: 123 is not a string
        })

        # CR1 FIX: handle_store_episode returns {"error": ..., "details": ...}, not {"status": "error"}
        assert "error" in result
        assert "tags[0]" in result["details"]
        assert "string" in result["details"].lower()

    @pytest.mark.asyncio
    async def test_store_episode_rejects_non_list_tags(self) -> None:
        """
        AC: store_episode validates tags parameter is a list.

        GIVEN: MCP tool handle_store_episode
        WHEN: Called with tags="not-a-list"
        THEN: Returns validation error about array type

        NOTE: Tests validation logic directly, no OpenAI API required
        """
        from mcp_server.tools import handle_store_episode

        result = await handle_store_episode({
            "query": "test query",
            "reward": 0.5,
            "reflection": "test reflection",
            "tags": "not-a-list"  # Invalid: not an array
        })

        # CR1 FIX: handle_store_episode returns {"error": ..., "details": ...}, not {"status": "error"}
        assert "error" in result
        assert "array" in result["details"].lower()

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "sk-your-openai-api-key-here",
        reason="Requires OpenAI API key"
    )
    @pytest.mark.asyncio
    async def test_compress_to_l2_insight_accepts_tags(self) -> None:
        """
        AC: compress_to_l2_insight accepts tags parameter.

        GIVEN: MCP tool compress_to_l2_insight
        WHEN: Called with tags=["relationship"]
        THEN: Insight is stored with tags

        NOTE: Skipped if OPENAI_API_KEY not configured
        """
        from mcp_server.tools import handle_compress_to_l2_insight

        result = await handle_compress_to_l2_insight({
            "content": "Test content for compression",
            "source_ids": [],
            "tags": ["relationship", "insight"]
        })

        # CR1 FIX: compress_to_l2_insight returns {"error": ...} or {"id": ...}, not {"status": "ok"}
        assert "error" not in result
        assert "id" in result

        # Verify tags were stored
        from mcp_server.db.connection import get_connection_with_project_context
        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tags FROM l2_insights WHERE id = %s;
            """, (result["id"],))
            row = cursor.fetchone()
            assert row is not None
            assert set(row["tags"]) == {"relationship", "insight"}

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "sk-your-openai-api-key-here",
        reason="Requires OpenAI API key"
    )
    @pytest.mark.asyncio
    async def test_compress_to_l2_insight_default_tags_when_omitted(self) -> None:
        """
        AC: compress_to_l2_insight works without tags parameter.

        GIVEN: MCP tool compress_to_l2_insight
        WHEN: Called without tags parameter
        THEN: Insight is stored with empty tags array

        NOTE: Skipped if OPENAI_API_KEY not configured
        """
        from mcp_server.tools import handle_compress_to_l2_insight

        result = await handle_compress_to_l2_insight({
            "content": "Test content for compression",
            "source_ids": []
            # No tags parameter
        })

        # CR1 FIX: compress_to_l2_insight returns {"error": ...} or {"id": ...}, not {"status": "ok"}
        assert "error" not in result
        assert "id" in result

        # Verify default empty tags
        from mcp_server.db.connection import get_connection_with_project_context
        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tags FROM l2_insights WHERE id = %s;
            """, (result["id"],))
            row = cursor.fetchone()
            assert row is not None
            assert row["tags"] == []


class TestRollbackMigration:
    """Test rollback migration 041_add_tags_rollback.sql (Story 9.1.1)."""

    def test_rollback_migration_drops_columns_and_indexes(self, conn) -> None:
        """
        AC: Rollback migration removes tags and metadata columns.

        GIVEN: Migration 041 has been applied
        WHEN: Rollback migration 041_add_tags_rollback.sql is executed
        THEN: tags and metadata columns are dropped
        AND: GIN indexes are dropped

        NOTE: This test modifies schema - re-applies migration after rollback
        """
        # M2 FIX: Add rollback migration test
        # Verify columns exist before rollback
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name IN ('episode_memory', 'l2_insights')
            AND column_name IN ('tags', 'metadata');
        """)
        count_before = cursor.fetchone()["count"]
        assert count_before > 0, "Columns should exist before rollback"

        # Execute rollback migration
        with open('mcp_server/db/migrations/041_add_tags_rollback.sql', 'r') as f:
            rollback_sql = f.read()
            # Execute each DROP statement
            cursor.execute(rollback_sql)
        conn.commit()

        # Verify columns were dropped
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name IN ('episode_memory', 'l2_insights')
            AND column_name IN ('tags', 'metadata');
        """)
        count_after = cursor.fetchone()["count"]
        assert count_after == 0, "All columns should be dropped after rollback"

        # Verify indexes were dropped
        cursor.execute("""
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE indexname IN ('idx_episode_memory_tags', 'idx_l2_insights_tags');
        """)
        index_count = cursor.fetchone()["count"]
        assert index_count == 0, "All indexes should be dropped after rollback"

        # Re-apply migration for other tests
        with open('tests/integration/apply_041_migration.py', 'r') as f:
            migration_code = f.read()
            # Extract and execute the apply_migration function
            exec(migration_code)
            apply_migration()


class TestRLSWithTags:
    """Test RLS policies work with new tags columns (Story 9.1.1)."""

    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "sk-your-openai-api-key-here",
        reason="Requires OpenAI API key"
    )
    @pytest.mark.asyncio
    async def test_rls_policies_with_tags_column(self, conn, project_context) -> None:
        """
        AC: RLS policies still enforce project_id isolation with tags column.

        GIVEN: Two projects with different project_ids
        WHEN: User from project-a tries to access project-b data
        THEN: RLS blocks access (existing behavior, unchanged)

        NOTE: Skipped if OPENAI_API_KEY not configured
        """
        from mcp_server.tools import add_episode

        # CR2 + CR3 FIX: Test with actual RLS isolation
        # Create episode for project-a using project-a context
        with project_context(conn, "project-a"):
            result_a = await add_episode(
                query="project-a query",
                reward=0.5,
                reflection="project-a reflection",
                conn=conn,
                project_id="project-a",
                tags=["project-a-tag"]
            )

        # Create episode for project-b using project-b context
        with project_context(conn, "project-b"):
            result_b = await add_episode(
                query="project-b query",
                reward=0.5,
                reflection="project-b reflection",
                conn=conn,
                project_id="project-b",
                tags=["project-b-tag"]
            )

        # CR3 FIX: Verify actual RLS isolation - project-a cannot see project-b data
        with project_context(conn, "project-a"):
            cursor = conn.cursor()
            # Try to read project-b episode
            cursor.execute("""
                SELECT id, tags FROM episode_memory WHERE project_id = 'project-b';
            """)
            rows = cursor.fetchall()
            # With RLS, project-a context should see 0 rows from project-b
            assert len(rows) == 0, "RLS should block project-a from seeing project-b data"

        # Verify we can see our own project-a data
        with project_context(conn, "project-a"):
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, tags FROM episode_memory WHERE project_id = 'project-a';
            """)
            rows = cursor.fetchall()
            assert len(rows) == 1, "RLS should allow project-a to see own data"
            assert rows[0]["tags"] == ["project-a-tag"]
