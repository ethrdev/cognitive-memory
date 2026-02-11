"""
Integration Tests for list_episodes Pagination

Tests for Story 9.2.3: pagination-validation.
Covers end-to-end pagination behavior with real database.

Author: Epic 9 Implementation
Story: 9.2.3 - pagination-validation
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest


class TestListEpisodesPaginationIntegration:
    """Integration tests for list_episodes pagination with real database."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_total_count_accuracy_with_filters(self):
        """AC-2: Count query includes all active filters."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"CountTest_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536
        test_tags = ["test-count-accuracy", "story-9-2-3"]

        try:
            await initialize_pool()

            # Insert 20 episodes with specific tags
            async with get_connection() as conn:
                cursor = conn.cursor()
                base_time = datetime.now(timezone.utc)

                # Insert 20 episodes, 10 with tags, 10 without
                for i in range(20):
                    tags = test_tags if i < 10 else []
                    query = f"{test_prefix}_Q{i}"
                    created_at = base_time + timedelta(hours=i)

                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (query, 0.5, "Test", fake_embedding, created_at, tags),
                    )
                conn.commit()

            # Test total_count with tags filter
            result = await handle_list_episodes({
                "tags": test_tags,
                "limit": 5,
                "offset": 0,
            })

            assert result["status"] == "success"
            # All 10 episodes with matching tags should be counted
            assert result["total_count"] == 10
            # Only 5 returned due to limit
            assert len(result["episodes"]) == 5

        finally:
            # Cleanup
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_offset_boundary_zero(self):
        """AC-3: offset = 0 returns first page."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"OffsetTest_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536

        try:
            await initialize_pool()

            # Insert 15 episodes
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(15):
                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        """,
                        (f"{test_prefix}_Q{i}", 0.5, "Test", fake_embedding, []),
                    )
                conn.commit()

            # Test offset = 0
            result = await handle_list_episodes({
                "limit": 10,
                "offset": 0,
            })

            assert result["status"] == "success"
            assert result["total_count"] == 15
            assert len(result["episodes"]) == 10
            assert result["offset"] == 0

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_offset_boundary_exceeds_total_count(self):
        """AC-3: offset >= total_count returns empty results (not error)."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"OffsetBoundary_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536

        try:
            await initialize_pool()

            # Insert 5 episodes
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        """,
                        (f"{test_prefix}_Q{i}", 0.5, "Test", fake_embedding, []),
                    )
                conn.commit()

            # Test offset == total_count (should return empty)
            result = await handle_list_episodes({
                "limit": 10,
                "offset": 5,
            })

            assert result["status"] == "success"
            assert result["total_count"] == 5
            assert len(result["episodes"]) == 0  # Empty results
            assert result["offset"] == 5

            # Test offset > total_count (should also return empty)
            result2 = await handle_list_episodes({
                "limit": 10,
                "offset": 100,
            })

            assert result2["status"] == "success"
            assert result2["total_count"] == 5
            assert len(result2["episodes"]) == 0

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_limit_boundary_conditions(self):
        """AC-3: Test limit boundary (0, 1, 100, > 100)."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"LimitTest_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536

        try:
            await initialize_pool()

            # Insert test data
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        """,
                        (f"{test_prefix}_Q{i}", 0.5, "Test", fake_embedding, []),
                    )
                conn.commit()

            # Test limit = 0 (should fail validation)
            result = await handle_list_episodes({"limit": 0})
            assert "error" in result
            assert "limit" in result["details"].lower()

            # Test limit = 1 (minimum valid)
            result = await handle_list_episodes({"limit": 1})
            assert result["status"] == "success"
            assert len(result["episodes"]) >= 1

            # Test limit = 100 (maximum valid)
            result = await handle_list_episodes({"limit": 100})
            assert result["status"] == "success"

            # Test limit > 100 (should fail validation)
            result = await handle_list_episodes({"limit": 101})
            assert "error" in result
            assert "limit" in result["details"].lower()

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_pagination_flow_multiple_pages(self):
        """AC-6: Test pagination flow: page 1 -> page 2 -> page 3."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"PageFlow_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536
        page_size = 10
        total_episodes = 25

        try:
            await initialize_pool()

            # Insert 25 episodes
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(total_episodes):
                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        """,
                        (f"{test_prefix}_Q{i}", 0.5, "Test", fake_embedding, []),
                    )
                conn.commit()

            # Page 1
            page1 = await handle_list_episodes({
                "limit": page_size,
                "offset": 0,
            })
            assert page1["status"] == "success"
            assert page1["total_count"] == total_episodes
            assert len(page1["episodes"]) == page_size

            # Page 2
            page2 = await handle_list_episodes({
                "limit": page_size,
                "offset": page_size,
            })
            assert page2["status"] == "success"
            assert page2["total_count"] == total_episodes
            assert len(page2["episodes"]) == page_size

            # Page 3 (partial page)
            page3 = await handle_list_episodes({
                "limit": page_size,
                "offset": page_size * 2,
            })
            assert page3["status"] == "success"
            assert page3["total_count"] == total_episodes
            assert len(page3["episodes"]) == 5  # Remaining 5

            # Page 4 (empty)
            page4 = await handle_list_episodes({
                "limit": page_size,
                "offset": page_size * 3,
            })
            assert page4["status"] == "success"
            assert len(page4["episodes"]) == 0

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_filters_combined_with_pagination(self):
        """AC-6: Test filters combined with pagination."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"FilterPage_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536
        tagged = ["test-filter-pagination", "story-9-2-3"]

        try:
            await initialize_pool()

            # Insert episodes with different tags and categories
            async with get_connection() as conn:
                cursor = conn.cursor()

                # 10 episodes with tags
                for i in range(10):
                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        """,
                        (f"{test_prefix}_tagged_{i}", 0.5, "Test", fake_embedding, tagged),
                    )

                # 10 episodes without tags but with category prefix
                for i in range(10):
                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        """,
                        (f"[{test_prefix}]_cat_{i}", 0.5, "Test", fake_embedding, []),
                    )
                conn.commit()

            # Test tags filter with pagination
            result = await handle_list_episodes({
                "tags": tagged,
                "limit": 5,
                "offset": 0,
            })
            assert result["status"] == "success"
            assert result["total_count"] == 10  # Only tagged episodes
            assert len(result["episodes"]) == 5

            # Test category filter with pagination
            result2 = await handle_list_episodes({
                "category": f"[{test_prefix}]",
                "limit": 5,
                "offset": 0,
            })
            assert result2["status"] == "success"
            assert result2["total_count"] == 10  # Only category matches

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"%{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_backward_compatibility_no_limit_offset(self):
        """AC-6: Test backward compatibility (calls without limit/offset)."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"BackCompat_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536

        try:
            await initialize_pool()

            # Insert test data
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(5):
                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        """,
                        (f"{test_prefix}_Q{i}", 0.5, "Test", fake_embedding, []),
                    )
                conn.commit()

            # Call without limit/offset (should use defaults)
            result = await handle_list_episodes({})

            assert result["status"] == "success"
            assert result["limit"] == 50  # Default
            assert result["offset"] == 0  # Default

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_empty_result_set_total_count_zero(self):
        """AC-3: Empty result set returns total_count = 0."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"EmptyResult_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536

        try:
            await initialize_pool()

            # Insert a few episodes (not matching our filter)
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO episode_memory
                    (query, reward, reflection, embedding, created_at, tags)
                    VALUES (%s, %s, %s, %s, NOW(), %s)
                    """,
                    (f"other_{test_prefix}", 0.5, "Test", fake_embedding, []),
                )
                conn.commit()

            # Filter with non-existent tags
            result = await handle_list_episodes({
                "tags": ["nonexistent-tag-xyz"],
                "limit": 10,
                "offset": 0,
            })

            assert result["status"] == "success"
            assert result["total_count"] == 0
            assert result["episodes"] == []

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"%{test_prefix}%",),
                )
                conn.commit()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_count_query_matches_actual_results(self):
        """AC-2: Count query matches actual data query results."""
        from mcp_server.db.connection import get_connection, initialize_pool
        from mcp_server.tools.list_episodes import handle_list_episodes

        test_prefix = f"CountMatch_{uuid.uuid4().hex[:8]}"
        fake_embedding = [0.1] * 1536

        try:
            await initialize_pool()

            # Insert specific number of episodes
            target_count = 37
            async with get_connection() as conn:
                cursor = conn.cursor()
                for i in range(target_count):
                    cursor.execute(
                        """
                        INSERT INTO episode_memory
                        (query, reward, reflection, embedding, created_at, tags)
                        VALUES (%s, %s, %s, %s, NOW(), %s)
                        """,
                        (f"{test_prefix}_Q{i}", 0.5, "Test", fake_embedding, []),
                    )
                conn.commit()

            # Get total_count
            result = await handle_list_episodes({"limit": 1})
            assert result["total_count"] == target_count

            # Verify by fetching all pages
            all_results = []
            offset = 0
            limit = 10

            while True:
                page = await handle_list_episodes({"limit": limit, "offset": offset})
                all_results.extend(page["episodes"])
                if len(page["episodes"]) < limit:
                    break
                offset += limit

            assert len(all_results) == target_count

        finally:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM episode_memory WHERE query LIKE %s",
                    (f"{test_prefix}%",),
                )
                conn.commit()
