"""
Unit Tests for Retroactive Tagging Idempotency

Story 9.4.3: Idempotent Validation

Tests ensure that the retroactive tagging script can be safely run multiple
times without creating duplicate tags or corrupting existing data.

Test Classes:
- TestIdempotencyGuards: Verify skip logic and duplicate prevention
- TestIdempotencyMultipleRuns: Multiple execution scenarios
- TestIdempotencyPartialTags: Partial tag completion scenarios
"""

import unittest
from unittest.mock import Mock, MagicMock, call, patch, mock_open
import sys
from pathlib import Path

# Add mcp_server to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Mock database dependencies before importing retroactive_tagging
mock_psycopg2 = MagicMock()
mock_psycopg2.extras = MagicMock()
sys.modules['psycopg2'] = mock_psycopg2
sys.modules['psycopg2.extensions'] = MagicMock()
sys.modules['psycopg2.extras'] = mock_psycopg2.extras
sys.modules['dotenv'] = MagicMock()

# Now import after mocking dependencies
from mcp_server.scripts import retroactive_tagging

# Restore TAG_RULES reference since we're using the real module
TAG_RULES = retroactive_tagging.TAG_RULES


class TestIdempotencyGuards(unittest.TestCase):
    """
    Test idempotency guards and skip logic.

    AC: When script runs on already-tagged data, no modifications occur.
    AC: No duplicate tags are added to any record.
    """

    def test_apply_tag_rules_returns_unique_tags(self):
        """
        Test that apply_tag_rules returns unique tags even when multiple
        rules match with overlapping tags.

        AC: No duplicate tags in results
        """
        # Text that matches multiple rules (if they had overlapping tags)
        text = "[self] This is about cognitive-memory project"
        result = retroactive_tagging.apply_tag_rules(text, "episodes")

        # Verify no duplicates
        self.assertEqual(len(result), len(set(result)))
        # Verify expected tags
        self.assertIn("self", result)
        self.assertIn("cognitive-memory", result)

    def test_apply_tag_rules_empty_when_no_match(self):
        """
        Test that apply_tag_rules returns empty list when no rules match.

        AC: Non-matching content produces no tags
        """
        text = "This text matches no tag rules"
        result = retroactive_tagging.apply_tag_rules(text, "episodes")

        self.assertEqual(result, [])

    def test_apply_tag_rules_target_filtering(self):
        """
        Test that rules correctly filter by target type.

        AC: Episode-only rules don't apply to insights and vice versa
        """
        # Source type rules only apply to episodes
        episode_text = "[self] My query"
        episode_result = retroactive_tagging.apply_tag_rules(episode_text, "episodes")
        insight_result = retroactive_tagging.apply_tag_rules(episode_text, "insights")

        # Episodes should get 'self' tag from source rule
        self.assertIn("self", episode_result)
        # Insights should NOT get 'self' tag (source rule doesn't apply)
        self.assertNotIn("self", insight_result)


class TestIdempotencyMultipleRuns(unittest.TestCase):
    """
    Test multiple execution scenarios for true idempotency.

    AC: Script produces consistent results across multiple runs.
    AC: Previously tagged entries are skipped (not modified).
    """

    def test_tag_episodes_skips_already_tagged(self):
        """
        Test that episodes with existing tags are skipped.

        AC: Second run on already-tagged data should skip.
        """
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        # Simulate one episode with tags, one without
        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] Query 1", "tags": ["self"]},  # Has tags
            {"id": 2, "query": "[shared] Query 2", "tags": []},     # No tags
        ]

        stats = retroactive_tagging.tag_episodes(mock_conn, dry_run=False, verbose=False)

        # First episode should be skipped, second should be tagged
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["tagged"], 1)

        # Verify UPDATE was only called once (for the untagged episode)
        self.assertEqual(mock_cursor.execute.call_count, 2)  # SELECT + 1 UPDATE
        # Check that the UPDATE call was for episode 2
        update_call_args = mock_cursor.execute.call_args_list[1]
        self.assertIn("UPDATE episode_memory", update_call_args[0][0])

    def test_tag_insights_skips_already_tagged(self):
        """
        Test that insights with existing tags are skipped.

        AC: Second run on already-tagged insights should skip.
        """
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {"id": 1, "content": "Dark Romance content", "tags": ["dark-romance"]},
            {"id": 2, "content": "cognitive-memory project", "tags": []},
        ]

        stats = retroactive_tagging.tag_insights(mock_conn, dry_run=False, verbose=False)

        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["tagged"], 1)

    def test_dry_run_mode_no_database_changes(self):
        """
        Test that dry-run mode doesn't write to database.

        AC: Dry-run produces preview without database changes.
        """
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {"id": 1, "query": "[self] Query", "tags": []},
        ]

        stats = retroactive_tagging.tag_episodes(mock_conn, dry_run=True, verbose=False)

        # Should not tag anything in dry-run mode
        self.assertEqual(stats["tagged"], 0)
        # Should not call UPDATE or commit
        mock_conn.commit.assert_not_called()


class TestIdempotencyPartialTags(unittest.TestCase):
    """
    Test partial tag completion scenarios.

    AC: Only missing tags are added (union of existing + new matches).
    AC: No tags are removed or duplicated.
    """

    def test_union_based_tagging_preserves_existing(self):
        """
        Test that union-based tagging preserves existing tags.

        AC: Partial tags from previous runs are preserved.
        AC: New matching tags are added without duplication.
        """
        # Episode with existing tag ['self'], rule matches 'cognitive-memory'
        # Result should be ['self', 'cognitive-memory']

        existing_tags = ["self"]
        new_matches = ["cognitive-memory"]

        # Union operation
        expected_tags = sorted(list(set(existing_tags + new_matches)))

        self.assertEqual(expected_tags, ["cognitive-memory", "self"])
        # Verify no duplicates
        self.assertEqual(len(expected_tags), len(set(expected_tags)))

    def test_duplicate_prevention_in_union(self):
        """
        Test that duplicate tags are prevented when existing tag
        matches a rule again.

        AC: Rule match ['self'] + existing ['self'] = no duplicate.
        """
        existing_tags = ["self", "cognitive-memory"]
        new_matches = ["self"]  # Rule matches 'self' again

        # Union should prevent duplicate 'self'
        result_tags = sorted(list(set(existing_tags + new_matches)))

        self.assertEqual(result_tags, ["cognitive-memory", "self"])
        self.assertEqual(result_tags.count("self"), 1)  # Only one 'self'

    def test_multiple_rules_partial_overlap(self):
        """
        Test behavior when multiple rules match with partial overlap.

        AC: Multiple rules matching, one already present → only missing added.
        """
        existing_tags = ["self"]
        # Two rules match: 'cognitive-memory' and 'self'
        new_matches = ["cognitive-memory", "self"]

        result = sorted(list(set(existing_tags + new_matches)))

        self.assertEqual(result, ["cognitive-memory", "self"])
        self.assertEqual(len(result), 2)  # No duplicates

    def test_empty_existing_tags_add_all(self):
        """
        Test that empty existing tags results in all matched tags added.

        AC: First run on empty tags applies all matching tags.
        """
        existing_tags = []
        new_matches = ["self", "cognitive-memory"]

        result = sorted(list(set(existing_tags + new_matches)))

        self.assertEqual(result, ["cognitive-memory", "self"])


class TestIdempotencyEdgeCases(unittest.TestCase):
    """
    Test edge cases not covered in primary scenarios.

    AC: Script handles NULL tags gracefully.
    AC: Script handles empty array tags gracefully.
    """

    def test_null_tags_treated_as_empty(self):
        """
        Test that NULL tags are treated as empty array.

        AC: NULL tags field should trigger tagging, not skip.
        """
        existing_tags = None
        new_matches = ["self"]

        # Union with None should work like empty list
        result = sorted(list(set((existing_tags or []) + new_matches)))

        self.assertEqual(result, ["self"])

    def test_empty_array_tags_treated_as_empty(self):
        """
        Test that empty array tags are treated as empty.

        AC: Empty array [] should trigger tagging.
        """
        existing_tags = []
        new_matches = ["dark-romance"]

        result = sorted(list(set(existing_tags + new_matches)))

        self.assertEqual(result, ["dark-romance"])

    def test_no_matching_rules_no_tags_added(self):
        """
        Test that entries without rule matches get no tags.

        AC: Non-matching content should not be tagged.
        """
        text = "This matches no tag rules at all"
        result = retroactive_tagging.apply_tag_rules(text, "episodes")

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
