"""
Integration Tests for list_insights Pagination

Tests for Story 9.2.3: pagination-validation.
Covers end-to-end pagination behavior with real database.

Author: Epic 9 Implementation
Story: 9.2.3 - pagination-validation
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

# Fake embedding for testing (1536 dimensions)
FAKE_EMBEDDING = [0.1] * 1536


class TestListInsightsPaginationIntegration:
    """Integration tests for list_insights pagination with real database."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_total_count_accuracy_with_filters(self):
        """AC-2: Count query includes all active filters for insights."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"InsightCount_{uuid.uuid4().hex[:8]}"
        test_tags = ["test-insight-count", "story-9-2-3"]

        try:
            await initialize_pool()

            # Insert insights with various filters
            async with get_connection() as conn:
                cursor = conn.cursor()

                # Insert 20 insights: 10 with specific tags and io_category
                for i in range(10):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            "io",
                            f"{test_prefix}_tagged_{i}",
                            FAKE_EMBEDDING,
                            [],
                            test_tags,
                            "ethr",
                            False,
                            json.dumps({"memory_sector": "emotional"}),
                        ),
                    )

                # Insert 10 insights without tags
                for i in range(10):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            "io",
                            f"{test_prefix}_untagged_{i}",
                            FAKE_EMBEDDING,
                            [],
                            [],
                            "self",
                            False,
                            json.dumps({"memory_sector": "semantic"}),
                        ),
                    )
                conn.commit()

            # Test total_count with tags filter
            result = await handle_list_insights({
                "tags": test_tags,
                "limit": 5,
                "offset": 0,
            })

            assert result["status"] == "success"
            assert result["total_count"] == 10
            assert len(result["insights"]) == 5

            # Test with io_category filter
            result2 = await handle_list_insights({
                "io_category": "ethr",
                "limit": 10,
                "offset": 0,
            })

            assert result2["status"] == "success"
            assert result2["total_count"] == 10

        finally:
            # Cleanup
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_offset_boundary_conditions(self):
        """AC-3: offset boundary conditions for insights."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"InsightOffset_{uuid.uuid4().hex[:8]}"

        try:
            await initialize_pool()

            # Insert 15 insights
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(15):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_{i}", FAKE_EMBEDDING, [], [], "self", False, None),
                    )
                conn.commit()

            # Test offset = 0
            result = await handle_list_insights({
                "limit": 10,
                "offset": 0,
            })
            assert result["status"] == "success"
            assert result["total_count"] == 15
            assert len(result["insights"]) == 10

            # Test offset >= total_count (empty results)
            result2 = await handle_list_insights({
                "limit": 10,
                "offset": 15,  # Exactly at total_count
            })
            assert result2["status"] == "success"
            assert len(result2["insights"]) == 0

            result3 = await handle_list_insights({
                "limit": 10,
                "offset": 100,  # Beyond total_count
            })
            assert result3["status"] == "success"
            assert len(result3["insights"]) == 0

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_limit_boundary_conditions(self):
        """AC-3: limit boundary conditions for insights."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"InsightLimit_{uuid.uuid4().hex[:8]}"

        try:
            await initialize_pool()

            # Insert test data
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_{i}", FAKE_EMBEDDING, [], [], "self", False, None),
                    )
                conn.commit()

            # Test limit = 0 (validation error)
            result = await handle_list_insights({"limit": 0})
            assert "error" in result

            # Test limit = 1 (minimum valid)
            result = await handle_list_insights({"limit": 1})
            assert result["status"] == "success"
            assert len(result["insights"]) >= 1

            # Test limit = 100 (maximum valid)
            result = await handle_list_insights({"limit": 100})
            assert result["status"] == "success"

            # Test limit > 100 (validation error)
            result = await handle_list_insights({"limit": 101})
            assert "error" in result

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_soft_deleted_items_excluded_from_count(self):
        """AC-2/AC-3: Soft-deleted items excluded from count and results."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"SoftDelete_{uuid.uuid4().hex[:8]}"

        try:
            await initialize_pool()

            # Insert active and soft-deleted insights
            async with get_connection() as conn:
                cursor = conn.cursor()

                # Insert 10 active insights
                for i in range(10):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_active_{i}", FAKE_EMBEDDING, [], [], "self", False, None),
                    )

                # Insert 5 soft-deleted insights
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata, is_deleted)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_deleted_{i}", FAKE_EMBEDDING, [], [], "self", False, None, True),
                    )
                conn.commit()

            # Count should only include active insights
            result = await handle_list_insights({
                "limit": 50,
                "offset": 0,
            })

            assert result["status"] == "success"
            assert result["total_count"] == 10  # Only active
            assert len(result["insights"]) == 10

            # Verify soft-deleted are not in results
            for insight in result["insights"]:
                assert "deleted" not in insight["content"]

        finally:
            # Cleanup both active and deleted
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_pagination_flow_multiple_pages(self):
        """AC-6: Test pagination flow through multiple pages."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"InsightFlow_{uuid.uuid4().hex[:8]}"
        page_size = 10
        total_insights = 25

        try:
            await initialize_pool()

            # Insert 25 insights
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(total_insights):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_{i}", FAKE_EMBEDDING, [], [], "self", False, None),
                    )
                conn.commit()

            # Page 1
            page1 = await handle_list_insights({
                "limit": page_size,
                "offset": 0,
            })
            assert page1["status"] == "success"
            assert page1["total_count"] == total_insights
            assert len(page1["insights"]) == page_size

            # Page 2
            page2 = await handle_list_insights({
                "limit": page_size,
                "offset": page_size,
            })
            assert page2["status"] == "success"
            assert len(page2["insights"]) == page_size

            # Page 3 (partial)
            page3 = await handle_list_insights({
                "limit": page_size,
                "offset": page_size * 2,
            })
            assert page3["status"] == "success"
            assert len(page3["insights"]) == 5

            # Page 4 (empty)
            page4 = await handle_list_insights({
                "limit": page_size,
                "offset": page_size * 3,
            })
            assert page4["status"] == "success"
            assert len(page4["insights"]) == 0

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_filters_combined_with_pagination(self):
        """AC-6: Test multiple filters combined with pagination."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"InsightFilter_{uuid.uuid4().hex[:8]}"
        test_tags = ["test-combo-filter", "story-9-2-3"]

        try:
            await initialize_pool()

            # Insert insights with various combinations
            async with get_connection() as conn:
                cursor = conn.cursor()

                # Tagged + ethr + emotional
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            "io",
                            f"{test_prefix}_combo1_{i}",
                            FAKE_EMBEDDING,
                            [],
                            test_tags,
                            "ethr",
                            False,
                            json.dumps({"memory_sector": "emotional"}),
                        ),
                    )

                # Tagged + self + semantic
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            "io",
                            f"{test_prefix}_combo2_{i}",
                            FAKE_EMBEDDING,
                            [],
                            test_tags,
                            "self",
                            False,
                            json.dumps({"memory_sector": "semantic"}),
                        ),
                    )
                conn.commit()

            # Test tags + io_category filter
            result = await handle_list_insights({
                "tags": test_tags,
                "io_category": "ethr",
                "limit": 3,
                "offset": 0,
            })
            assert result["status"] == "success"
            assert result["total_count"] == 5
            assert len(result["insights"]) == 3

            # Test tags + memory_sector filter
            result2 = await handle_list_insights({
                "tags": test_tags,
                "memory_sector": "emotional",
                "limit": 10,
                "offset": 0,
            })
            assert result2["status"] == "success"
            assert result2["total_count"] == 5

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_empty_result_set_count_zero(self):
        """AC-3: Empty result set returns total_count = 0."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"InsightEmpty_{uuid.uuid4().hex[:8]}"

        try:
            await initialize_pool()

            # Insert some insights (won't match our filter)
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO l2_insights
                    (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    ("io", f"other_{test_prefix}", FAKE_EMBEDDING, [], [], "self", False, None),
                )
                conn.commit()

            # Filter with non-existent tags
            result = await handle_list_insights({
                "tags": ["nonexistent-insight-tag"],
                "limit": 10,
                "offset": 0,
            })

            assert result["status"] == "success"
            assert result["total_count"] == 0
            assert result["insights"] == []

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"%{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_is_identity_filter_with_pagination(self):
        """Test is_identity filter combined with pagination."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"IdentityTest_{uuid.uuid4().hex[:8]}"

        try:
            await initialize_pool()

            # Insert insights with different is_identity values
            async with get_connection() as conn:
                cursor = conn.cursor()

                # 10 with is_identity = True
                for i in range(10):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_id_{i}", FAKE_EMBEDDING, [], [], "self", True, None),
                    )

                # 15 with is_identity = False
                for i in range(15):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_non_id_{i}", FAKE_EMBEDDING, [], [], "self", False, None),
                    )
                conn.commit()

            # Filter by is_identity = True
            result = await handle_list_insights({
                "is_identity": True,
                "limit": 5,
                "offset": 0,
            })
            assert result["status"] == "success"
            assert result["total_count"] == 10
            assert len(result["insights"]) == 5
            assert all(insight["is_identity"] is True for insight in result["insights"])

            # Filter by is_identity = False
            result2 = await handle_list_insights({
                "is_identity": False,
                "limit": 10,
                "offset": 0,
            })
            assert result2["status"] == "success"
            assert result2["total_count"] == 15
            assert all(insight["is_identity"] is False for insight in result2["insights"])

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_date_range_filter_with_pagination(self):
        """Test date range filter combined with pagination."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"DateTest_{uuid.uuid4().hex[:8]}"

        try:
            await initialize_pool()

            # Insert insights with specific dates
            async with get_connection() as conn:
                cursor = conn.cursor()
                base_time = datetime.now(timezone.utc)

                # 10 insights in the past
                for i in range(10):
                    past_time = base_time - timedelta(days=i + 1)
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_past_{i}", FAKE_EMBEDDING, [], [], "self", False, None, past_time),
                    )

                # 5 insights today
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_today_{i}", FAKE_EMBEDDING, [], [], "self", False, None),
                    )
                conn.commit()

            # Filter by date_from (last 24 hours)
            date_from = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            result = await handle_list_insights({
                "date_from": date_from,
                "limit": 10,
                "offset": 0,
            })
            assert result["status"] == "success"
            # Should include today's insights
            assert result["total_count"] >= 5

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_backward_compatibility_no_filters(self):
        """AC-6: Test backward compatibility - calls without filters work."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_insights import handle_list_insights

        test_prefix = f"InsightBackCompat_{uuid.uuid4().hex[:8]}"

        try:
            await initialize_pool()

            # Insert test data
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO l2_insights
                        (project_id, content, embedding, source_ids, tags, io_category, is_identity, metadata)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        ("io", f"{test_prefix}_{i}", FAKE_EMBEDDING, [], [], "self", False, None),
                    )
                conn.commit()

            # Call without filters (should use defaults)
            result = await handle_list_insights({})

            assert result["status"] == "success"
            assert result["limit"] == 50  # Default
            assert result["offset"] == 0  # Default

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM l2_insights WHERE content LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()
