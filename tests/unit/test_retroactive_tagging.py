"""
Unit tests for retroactive_tagging script.

Story 9.4.1: Retroactive Tagging of Existing Data

Tests cover:
- Tag rule matching logic
- Dry-run mode behavior
- Idempotency (running twice doesn't duplicate tags)
"""

import pytest
from unittest.mock import MagicMock, patch, call
from mcp_server.scripts import retroactive_tagging


class TestTagRuleMatching:
    """Test tag rule matching logic."""

    def test_self_prefix_matching(self):
        """Test [self] prefix matches self tag."""
        query = "[self] What did I learn yesterday?"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert "self" in tags

    def test_ethr_prefix_matching(self):
        """Test [ethr] prefix matches ethr tag."""
        query = "[ethr] My preferences for coding"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert "ethr" in tags

    def test_shared_prefix_matching(self):
        """Test [shared] prefix matches shared tag."""
        query = "[shared] Team meeting notes"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert "shared" in tags

    def test_relationship_prefix_matching(self):
        """Test [relationship] prefix matches relationship tag."""
        query = "[relationship] Conversation with Kira"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert "relationship" in tags

    def test_dark_romance_keyword_matching(self):
        """Test Dark Romance keywords match dark-romance tag."""
        query = "Szene mit Kira und Jan im Dark Romance"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert "dark-romance" in tags

    def test_drift_keyword_matching(self):
        """Test Drift keywords match drift tag."""
        content = "The Layer concept in Drift story"
        tags = retroactive_tagging.apply_tag_rules(content, "insights")
        assert "drift" in tags

    def test_stil_keyword_matching(self):
        """Test Stil keywords match stil tag."""
        query = "Anti-Pattern im Stil aus-nicht-ueber"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert "stil" in tags

    def test_validation_pattern_matching(self):
        """Test validation keywords match pattern tag."""
        query = "Soll ich das machen? Validation needed"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert "pattern" in tags

    def test_cognitive_memory_keyword_matching(self):
        """Test cognitive-memory keywords match cognitive-memory tag."""
        content = "Using MCP hybrid_search for cognitive-memory project"
        tags = retroactive_tagging.apply_tag_rules(content, "insights")
        assert "cognitive-memory" in tags

    def test_multiple_tags_union(self):
        """Test multiple matching rules return union of all tags."""
        query = "[shared] Working on cognitive-memory project with MCP tools"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        # Should match: shared, cognitive-memory
        assert "shared" in tags
        assert "cognitive-memory" in tags
        assert len(tags) >= 2

    def test_case_insensitive_matching(self):
        """Test pattern matching is case-insensitive."""
        query = "DARK ROMANCE scene with KIRA"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert "dark-romance" in tags

    def test_no_match_returns_empty_list(self):
        """Test text with no matches returns empty list."""
        query = "Random text with no matching keywords"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        assert tags == []

    def test_episode_only_rules_dont_apply_to_insights(self):
        """Test episode-only prefix rules don't apply to insights."""
        # [self] is episodes-only rule
        content = "[self] My reflection"
        tags = retroactive_tagging.apply_tag_rules(content, "insights")
        assert "self" not in tags

    def test_both_rules_apply_to_both_types(self):
        """Test rules with target='both' apply to episodes and insights."""
        text = "cognitive-memory project development"
        episode_tags = retroactive_tagging.apply_tag_rules(text, "episodes")
        insight_tags = retroactive_tagging.apply_tag_rules(text, "insights")

        assert "cognitive-memory" in episode_tags
        assert "cognitive-memory" in insight_tags

    def test_tags_are_sorted(self):
        """Test returned tags are sorted alphabetically."""
        query = "[drift] About stil and Dark Romance"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        # Check if tags are in sorted order
        assert tags == sorted(tags)

    def test_tags_are_unique(self):
        """Test returned tags contain no duplicates."""
        query = "[drift] drift drift drift"
        tags = retroactive_tagging.apply_tag_rules(query, "episodes")
        # Should have 'drift' only once
        assert tags.count("drift") == 1


class TestTagEpisodes:
    """Test episode tagging function."""

    def test_empty_result_when_no_episodes_need_tagging(self):
        """Test stats show zero when no episodes with empty tags."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None

        stats = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )

        assert stats["total"] == 0
        assert stats["tagged"] == 0
        mock_cursor.execute.assert_called_once()

    def test_skips_episodes_with_existing_tags(self):
        """Test episodes with existing tags are skipped (idempotency)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock episode with existing tags
        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] Test", "tags": ["self"]}
        ]

        stats = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )

        assert stats["skipped"] == 1
        assert stats["tagged"] == 0
        # UPDATE should not be called for skipped entries
        assert not any(
            "UPDATE" in str(call) for call in mock_cursor.execute.call_args_list
        )

    def test_tags_matching_episodes(self):
        """Test episodes matching rules get tagged."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock episodes needing tagging
        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] Test query", "tags": []},
            {"id": 2, "query": "[ethr] Another query", "tags": []},
        ]

        stats = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )

        assert stats["tagged"] == 2
        assert mock_cursor.execute.call_count >= 3  # SELECT + 2 UPDATEs


class TestTagInsights:
    """Test insight tagging function."""

    def test_empty_result_when_no_insights_need_tagging(self):
        """Test stats show zero when no insights with empty tags."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        stats = retroactive_tagging.tag_insights(
            mock_conn, dry_run=False, verbose=False
        )

        assert stats["total"] == 0
        assert stats["tagged"] == 0

    def test_skips_insights_with_existing_tags(self):
        """Test insights with existing tags are skipped (idempotency)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock insight with existing tags
        mock_cursor.fetchall.return_value = [
            {"id": 1, "content": "cognitive-memory work", "tags": ["cognitive-memory"]}
        ]

        stats = retroactive_tagging.tag_insights(
            mock_conn, dry_run=False, verbose=False
        )

        assert stats["skipped"] == 1
        assert stats["tagged"] == 0

    def test_tags_matching_insights(self):
        """Test insights matching rules get tagged."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mock insights needing tagging
        mock_cursor.fetchall.return_value = [
            {"id": 1, "content": "Working on cognitive-memory", "tags": []},
            {"id": 2, "content": "Dark Romance scene", "tags": []},
        ]

        stats = retroactive_tagging.tag_insights(
            mock_conn, dry_run=False, verbose=False
        )

        assert stats["tagged"] == 2


class TestDryRunMode:
    """Test dry-run mode behavior."""

    def test_dry_run_does_not_commit_changes(self, capsys):
        """Test dry-run mode prints SQL but doesn't execute UPDATE."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] Test", "tags": []}
        ]

        retroactive_tagging.tag_episodes(
            mock_conn, dry_run=True, verbose=False
        )

        # Verify ONLY SELECT is called, no UPDATE statements
        # In dry-run mode, execute should be called exactly once (for SELECT)
        assert mock_cursor.execute.call_count == 1, "Dry-run should only execute SELECT query"

        # Verify the SELECT query (not UPDATE) was called
        select_call = mock_cursor.execute.call_args_list[0]
        assert "SELECT" in str(select_call) and "UPDATE" not in str(select_call), \
            "Dry-run should only SELECT, never UPDATE"

        # Verify conn.commit() was NOT called
        mock_conn.commit.assert_not_called()

        # Check output contains SQL preview
        captured = capsys.readouterr()
        assert "WOULD TAG" in captured.out or "WOULD TAG" in captured.out

    def test_dry_run_insights_does_not_commit_changes(self, capsys):
        """Test dry-run mode for insights doesn't execute UPDATE."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {"id": 1, "content": "cognitive-memory work", "tags": []}
        ]

        retroactive_tagging.tag_insights(
            mock_conn, dry_run=True, verbose=False
        )

        # Verify ONLY SELECT is called, no UPDATE statements
        assert mock_cursor.execute.call_count == 1, "Dry-run should only execute SELECT query for insights"

        # Verify the SELECT query (not UPDATE) was called
        select_call = mock_cursor.execute.call_args_list[0]
        assert "SELECT" in str(select_call) and "UPDATE" not in str(select_call), \
            "Dry-run for insights should only SELECT, never UPDATE"

        # Verify conn.commit() was NOT called
        mock_conn.commit.assert_not_called()

        # Check output contains SQL preview
        captured = capsys.readouterr()
        assert "WOULD TAG" in captured.out or "WOULD TAG" in captured.out

    def test_dry_run_includes_sql_preview(self, capsys):
        """Test dry-run mode shows exact SQL that would be executed."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] Test", "tags": []}
        ]

        retroactive_tagging.tag_episodes(
            mock_conn, dry_run=True, verbose=False
        )

        captured = capsys.readouterr()
        assert "UPDATE episode_memory SET tags" in captured.out
        assert "WHERE id = 1" in captured.out


class TestIdempotency:
    """Test idempotency - running twice doesn't duplicate tags."""

    def test_second_run_tags_zero_entries(self):
        """Test second run tags 0 entries because all already tagged."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # First run: episodes have no tags
        mock_cursor.fetchall.side_effect = [
            [{"id": 1, "query": "[self] Test", "tags": []}],
            [{"id": 1, "query": "[self] Test", "tags": ["self"]}],  # Second query
        ]

        # First run - should tag 1 entry
        stats1 = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )
        assert stats1["tagged"] == 1

        # Second run - should tag 0 entries (all skipped)
        stats2 = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )
        assert stats2["tagged"] == 0
        assert stats2["skipped"] == 1


class TestSummaryOutput:
    """Test summary output function."""

    def test_summary_prints_episode_stats(self, capsys):
        """Test summary includes episode statistics."""
        episode_stats = {
            "total": 100,
            "tagged": 80,
            "skipped": 10,
            "per_rule": {"self-reflection queries": 20, "ethr personal queries": 15}
        }
        insight_stats = {
            "total": 50,
            "tagged": 40,
            "skipped": 5,
            "per_rule": {"Cognitive Memory project content": 30}
        }

        retroactive_tagging.print_summary(
            episode_stats, insight_stats, dry_run=False
        )

        captured = capsys.readouterr()
        assert "Total entries with empty tags: 100" in captured.out
        assert "Successfully tagged: 80" in captured.out
        assert "Skipped (already tagged): 10" in captured.out

    def test_summary_calculates_coverage_percentage(self, capsys):
        """Test summary calculates coverage percentage correctly."""
        episode_stats = {"total": 100, "tagged": 80, "skipped": 10, "per_rule": {}}
        insight_stats = {"total": 50, "tagged": 40, "skipped": 5, "per_rule": {}}

        retroactive_tagging.print_summary(
            episode_stats, insight_stats, dry_run=False
        )

        captured = capsys.readouterr()
        # 120 tagged out of 150 total = 80%
        assert "80.0%" in captured.out or "80.0%" in captured.out

    def test_summary_includes_dry_run_notice(self, capsys):
        """Test dry-run mode includes warning in summary."""
        episode_stats = {"total": 10, "tagged": 8, "skipped": 0, "per_rule": {}}
        insight_stats = {"total": 5, "tagged": 4, "skipped": 0, "per_rule": {}}

        retroactive_tagging.print_summary(
            episode_stats, insight_stats, dry_run=True
        )

        captured = capsys.readouterr()
        assert "DRY-RUN MODE" in captured.out
        assert "No changes were written" in captured.out
        # Verify exact format from retroactive_tagging.py:400-403
        assert "=" * 60 in captured.out


class TestPerRuleStatistics:
    """Test per-rule statistics tracking."""

    def test_counts_matches_per_rule(self):
        """Test each matching rule increments its counter."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Two episodes matching different rules
        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] Test", "tags": []},
            {"id": 2, "query": "[shared] Another", "tags": []},
        ]

        stats = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )

        assert stats["tagged"] == 2
        # Verify per-rule counts
        assert stats["per_rule"]["self-reflection queries"] == 1
        assert stats["per_rule"]["shared context queries"] == 1

    def test_multiple_matches_same_rule_increments_once(self):
        """Test multiple episodes matching same rule count correctly."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Three episodes all matching [self] rule
        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] One", "tags": []},
            {"id": 2, "query": "[self] Two", "tags": []},
            {"id": 3, "query": "[self] Three", "tags": []},
        ]

        stats = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )

        assert stats["tagged"] == 3
        assert stats["per_rule"]["self-reflection queries"] == 3

    def test_rules_with_target_both_count_for_both_types(self):
        """Test rules with target='both' generate stats for both types."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Episode with cognitive-memory keyword
        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "cognitive-memory project", "tags": []},
        ]

        episode_stats = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )

        # Insight with same keyword
        mock_cursor.fetchall.return_value = [
            {"id": 1, "content": "cognitive-memory work", "tags": []},
        ]

        insight_stats = retroactive_tagging.tag_insights(
            mock_conn, dry_run=False, verbose=False
        )

        # Both should have the rule counted
        assert episode_stats["per_rule"]["Cognitive Memory project content"] == 1
        assert insight_stats["per_rule"]["Cognitive Memory project content"] == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_tags_array_vs_null(self):
        """Test both empty array '{}' and NULL are handled correctly."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # Mix of empty array and NULL
        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] Test", "tags": []},  # Empty array
            {"id": 2, "query": "[self] Test2", "tags": None},  # NULL
        ]

        stats = retroactive_tagging.tag_episodes(
            mock_conn, dry_run=False, verbose=False
        )

        # Both should be processed
        assert stats["total"] == 2
        assert stats["tagged"] == 2

    def test_regex_metacharacters_in_text_handled_safely(self):
        """Test regex metacharacters in text don't cause errors."""
        # Text containing regex special characters - with [self] prefix at START
        malicious_text = "[self] .*()[]{}|^$+?\\ test with brackets"
        tags = retroactive_tagging.apply_tag_rules(malicious_text, "episodes")
        # Should still match [self] prefix safely (pattern r"^\[self\]" matches at start)
        assert "self" in tags

    def test_very_long_text_does_not_crash(self):
        """Test very long query/content strings don't cause crashes."""
        long_text = "cognitive-memory " * 1000  # ~16000 chars
        tags = retroactive_tagging.apply_tag_rules(long_text, "episodes")
        # Should match and return cognitive-memory tag
        assert "cognitive-memory" in tags

    def test_unicode_text_handled_correctly(self):
        """Test unicode characters are handled correctly."""
        unicode_text = "Szene mit Kira und Jän - émojis 🎭"
        tags = retroactive_tagging.apply_tag_rules(unicode_text, "episodes")
        # Should match dark-romance pattern (case insensitive)
        assert "dark-romance" in tags

    def test_no_matches_returns_empty_list(self):
        """Test text with absolutely no matches returns empty list."""
        random_text = "xyz completely random unrelated text 12345"
        tags = retroactive_tagging.apply_tag_rules(random_text, "episodes")
        assert tags == []

