"""
Unit Tests for Query Expansion Utilities

Tests for deduplication and RRF fusion functions used in query expansion.
Part of () - RAG Pipeline & Hybrid Calibration.

Note: These tests verify the utility functions only. The actual query expansion
(generating 3 semantic variants) happens internally during Claude Code's reasoning
and cannot be unit-tested directly.
"""

import pytest

from mcp_server.utils.query_expansion import deduplicate_by_l2_id, merge_rrf_scores


class TestDeduplicateByL2ID:
    """Test suite for deduplicate_by_l2_id function."""

    def test_no_duplicates(self):
        """Test deduplication when there are no duplicates."""
        results = [
            {"id": "L2-001", "score": 0.9, "content": "Doc A"},
            {"id": "L2-002", "score": 0.8, "content": "Doc B"},
            {"id": "L2-003", "score": 0.7, "content": "Doc C"},
        ]
        deduped = deduplicate_by_l2_id(results)

        assert len(deduped) == 3
        assert deduped == results  # Order preserved (already sorted by score desc)

    def test_with_duplicates_keeps_highest_score(self):
        """Test deduplication keeps highest-scoring instance of each document."""
        results = [
            {"id": "L2-001", "score": 0.85, "content": "Doc A (v1)"},
            {"id": "L2-002", "score": 0.75, "content": "Doc B"},
            {"id": "L2-001", "score": 0.90, "content": "Doc A (v2)"},  # Higher score
            {"id": "L2-003", "score": 0.65, "content": "Doc C"},
            {"id": "L2-002", "score": 0.70, "content": "Doc B (v2)"},  # Lower score
        ]
        deduped = deduplicate_by_l2_id(results)

        assert len(deduped) == 3  # Only 3 unique IDs
        assert deduped[0]["id"] == "L2-001"
        assert deduped[0]["score"] == 0.90  # Highest score kept
        assert deduped[0]["content"] == "Doc A (v2)"
        assert deduped[1]["id"] == "L2-002"
        assert deduped[1]["score"] == 0.75  # Highest score kept
        assert deduped[2]["id"] == "L2-003"

    def test_empty_list(self):
        """Test deduplication with empty input."""
        results = []
        deduped = deduplicate_by_l2_id(results)
        assert deduped == []

    def test_single_document(self):
        """Test deduplication with single document."""
        results = [{"id": "L2-001", "score": 0.9, "content": "Doc A"}]
        deduped = deduplicate_by_l2_id(results)
        assert len(deduped) == 1
        assert deduped[0] == results[0]

    def test_all_duplicates(self):
        """Test deduplication when all results are duplicates of same document."""
        results = [
            {"id": "L2-001", "score": 0.85, "content": "Doc A (v1)"},
            {"id": "L2-001", "score": 0.90, "content": "Doc A (v2)"},
            {"id": "L2-001", "score": 0.80, "content": "Doc A (v3)"},
        ]
        deduped = deduplicate_by_l2_id(results)

        assert len(deduped) == 1
        assert deduped[0]["score"] == 0.90  # Highest score
        assert deduped[0]["content"] == "Doc A (v2)"

    def test_preserves_additional_fields(self):
        """Test that deduplication preserves all fields from results."""
        results = [
            {
                "id": "L2-001",
                "score": 0.9,
                "content": "Doc A",
                "source_ids": ["S1", "S2"],
                "metadata": {"type": "insight"},
            },
            {
                "id": "L2-002",
                "score": 0.8,
                "content": "Doc B",
                "source_ids": ["S3"],
                "metadata": {"type": "thought"},
            },
        ]
        deduped = deduplicate_by_l2_id(results)

        assert len(deduped) == 2
        assert "source_ids" in deduped[0]
        assert "metadata" in deduped[0]
        assert deduped[0]["source_ids"] == ["S1", "S2"]


class TestMergeRRFScores:
    """Test suite for merge_rrf_scores function."""

    def test_single_query_results(self):
        """Test RRF fusion with single query (should return original ranking)."""
        results = [
            {"id": "L2-001", "score": 0.9, "content": "Doc A"},
            {"id": "L2-002", "score": 0.8, "content": "Doc B"},
            {"id": "L2-003", "score": 0.7, "content": "Doc C"},
        ]
        merged = merge_rrf_scores([results], k=60)

        assert len(merged) == 3
        # RRF scores: rank 1 → 1/61, rank 2 → 1/62, rank 3 → 1/63
        assert merged[0]["id"] == "L2-001"
        assert merged[1]["id"] == "L2-002"
        assert merged[2]["id"] == "L2-003"
        assert merged[0]["score"] > merged[1]["score"] > merged[2]["score"]

    def test_two_queries_no_overlap(self):
        """Test RRF fusion with two queries and no overlapping documents."""
        query1_results = [
            {"id": "L2-001", "score": 0.9, "content": "Doc A"},
            {"id": "L2-002", "score": 0.8, "content": "Doc B"},
        ]
        query2_results = [
            {"id": "L2-003", "score": 0.85, "content": "Doc C"},
            {"id": "L2-004", "score": 0.75, "content": "Doc D"},
        ]
        merged = merge_rrf_scores([query1_results, query2_results], k=60)

        assert len(merged) == 4
        # All documents appear once, RRF scores based on single rank
        # Rank 1 in either query: 1/61 ≈ 0.0164
        # Rank 2 in either query: 1/62 ≈ 0.0161
        assert all(result["id"] in ["L2-001", "L2-002", "L2-003", "L2-004"] for result in merged)

    def test_two_queries_with_overlap(self):
        """Test RRF fusion with overlapping documents (most important test case)."""
        query1_results = [
            {"id": "L2-001", "score": 0.9, "content": "Doc A"},  # Rank 1
            {"id": "L2-002", "score": 0.8, "content": "Doc B"},  # Rank 2
            {"id": "L2-003", "score": 0.7, "content": "Doc C"},  # Rank 3
        ]
        query2_results = [
            {"id": "L2-002", "score": 0.95, "content": "Doc B"},  # Rank 1 (overlap!)
            {"id": "L2-004", "score": 0.85, "content": "Doc D"},  # Rank 2
            {"id": "L2-001", "score": 0.75, "content": "Doc A"},  # Rank 3 (overlap!)
        ]
        merged = merge_rrf_scores([query1_results, query2_results], k=60)

        assert len(merged) == 4  # 4 unique documents

        # Expected RRF scores:
        # L2-002: 1/62 (rank 2 in Q1) + 1/61 (rank 1 in Q2) ≈ 0.0161 + 0.0164 = 0.0325
        # L2-001: 1/61 (rank 1 in Q1) + 1/63 (rank 3 in Q2) ≈ 0.0164 + 0.0159 = 0.0323
        # L2-004: 1/62 (rank 2 in Q2) ≈ 0.0161
        # L2-003: 1/63 (rank 3 in Q1) ≈ 0.0159

        # L2-002 should rank highest (appears in both, high ranks)
        assert merged[0]["id"] == "L2-002"
        assert merged[1]["id"] == "L2-001"  # Also appears in both
        # L2-004 and L2-003 may vary in order (similar scores)

    def test_four_queries_query_expansion_scenario(self):
        """Test RRF fusion with 4 queries (realistic query expansion scenario)."""
        # Original query results
        q0_results = [{"id": "L2-001", "score": 0.9, "content": "Doc A"}]
        # Paraphrase variant results
        q1_results = [{"id": "L2-002", "score": 0.85, "content": "Doc B"}]
        # Perspective shift variant results
        q2_results = [{"id": "L2-001", "score": 0.88, "content": "Doc A"}]  # Overlap
        # Keyword focus variant results
        q3_results = [
            {"id": "L2-003", "score": 0.92, "content": "Doc C"},
            {"id": "L2-001", "score": 0.80, "content": "Doc A"},  # Overlap again
        ]

        merged = merge_rrf_scores([q0_results, q1_results, q2_results, q3_results], k=60)

        assert len(merged) == 3  # 3 unique documents (L2-001, L2-002, L2-003)

        # L2-001 appears 3 times (q0 rank 1, q2 rank 1, q3 rank 2)
        # Should have highest RRF score
        assert merged[0]["id"] == "L2-001"

    def test_custom_k_value(self):
        """Test RRF fusion with custom k value."""
        results = [
            {"id": "L2-001", "score": 0.9, "content": "Doc A"},
            {"id": "L2-002", "score": 0.8, "content": "Doc B"},
        ]

        # k=10 (smaller k gives more weight to rank differences)
        merged_k10 = merge_rrf_scores([results], k=10)
        assert merged_k10[0]["score"] == pytest.approx(1 / 11, rel=1e-5)
        assert merged_k10[1]["score"] == pytest.approx(1 / 12, rel=1e-5)

        # k=100 (larger k reduces impact of rank differences)
        merged_k100 = merge_rrf_scores([results], k=100)
        assert merged_k100[0]["score"] == pytest.approx(1 / 101, rel=1e-5)
        assert merged_k100[1]["score"] == pytest.approx(1 / 102, rel=1e-5)

    def test_empty_results_list(self):
        """Test RRF fusion with empty results list."""
        merged = merge_rrf_scores([], k=60)
        assert merged == []

    def test_empty_query_results(self):
        """Test RRF fusion when one query returns no results."""
        query1_results = [{"id": "L2-001", "score": 0.9, "content": "Doc A"}]
        query2_results = []  # Empty

        merged = merge_rrf_scores([query1_results, query2_results], k=60)
        assert len(merged) == 1
        assert merged[0]["id"] == "L2-001"

    def test_preserves_additional_fields(self):
        """Test that RRF fusion preserves all fields from results."""
        results = [
            {
                "id": "L2-001",
                "score": 0.9,
                "content": "Doc A",
                "source_ids": ["S1"],
                "metadata": {"type": "insight"},
            }
        ]
        merged = merge_rrf_scores([results], k=60)

        assert len(merged) == 1
        assert "source_ids" in merged[0]
        assert "metadata" in merged[0]
        assert merged[0]["content"] == "Doc A"

    def test_default_k_value(self):
        """Test that default k value is 60 (literature standard)."""
        results = [{"id": "L2-001", "score": 0.9, "content": "Doc A"}]

        # Call without k parameter (should use default k=60)
        merged = merge_rrf_scores([results])
        assert merged[0]["score"] == pytest.approx(1 / 61, rel=1e-5)


class TestQueryExpansionIntegration:
    """Integration tests for deduplication + RRF fusion pipeline."""

    def test_full_pipeline_four_queries(self):
        """Test complete pipeline: 4 queries → RRF fusion → deduplication → Top-5."""
        # Simulate 4 query results (original + 3 variants)
        query0_results = [
            {"id": "L2-001", "score": 0.90, "content": "Doc A"},
            {"id": "L2-002", "score": 0.85, "content": "Doc B"},
        ]
        query1_results = [
            {"id": "L2-003", "score": 0.88, "content": "Doc C"},
            {"id": "L2-001", "score": 0.82, "content": "Doc A"},  # Duplicate
        ]
        query2_results = [
            {"id": "L2-002", "score": 0.91, "content": "Doc B"},  # Duplicate
            {"id": "L2-004", "score": 0.80, "content": "Doc D"},
        ]
        query3_results = [
            {"id": "L2-005", "score": 0.87, "content": "Doc E"},
            {"id": "L2-001", "score": 0.78, "content": "Doc A"},  # Duplicate
        ]

        # Step 1: RRF Fusion
        merged = merge_rrf_scores(
            [query0_results, query1_results, query2_results, query3_results], k=60
        )

        # Step 2: Deduplication (RRF already handles duplicates, but verify)
        # RRF should have already merged duplicates by ID
        unique_ids = {result["id"] for result in merged}
        assert len(unique_ids) == 5  # 5 unique documents

        # Step 3: Top-5
        top_5 = merged[:5]
        assert len(top_5) <= 5

        # Documents appearing multiple times should rank higher
        # L2-001 appears 3 times, L2-002 appears 2 times
        top_ids = {result["id"] for result in top_5}
        assert "L2-001" in top_ids  # Should be in top 5 (appeared 3 times)
        assert "L2-002" in top_ids  # Should be in top 5 (appeared 2 times)

    def test_deduplication_after_rrf_is_redundant(self):
        """Verify RRF already handles duplicates (deduplication is redundant but safe)."""
        query1_results = [
            {"id": "L2-001", "score": 0.9, "content": "Doc A (Q1)"},
            {"id": "L2-002", "score": 0.8, "content": "Doc B"},
        ]
        query2_results = [
            {"id": "L2-001", "score": 0.85, "content": "Doc A (Q2)"},  # Duplicate ID
            {"id": "L2-003", "score": 0.75, "content": "Doc C"},
        ]

        # RRF fusion already merges by ID
        merged = merge_rrf_scores([query1_results, query2_results], k=60)
        assert len(merged) == 3  # Only 3 unique IDs

        # Deduplication should be no-op (but verify it doesn't break anything)
        deduped = deduplicate_by_l2_id(merged)
        assert len(deduped) == 3
        assert deduped == merged  # Should be identical
