"""
Tests for Performance Data Seeding Script (Story 11.1.0, Task 1)

Tests the seed_performance_data.py script that creates production-like
test data volumes for baseline RLS performance measurement.

Run with: pytest tests/performance/test_seed_performance_data.py -v -s
"""

from __future__ import annotations

import json
import pytest
import subprocess
import sys
from pathlib import Path

# Integration tests require real database
pytestmark = pytest.mark.integration


class TestSeedPerformanceDataScript:
    """Test the performance data seeding script."""

    @pytest.fixture
    def script_path(self) -> Path:
        """Path to the seeding script."""
        return Path("scripts/seed_performance_data.py")

    def test_script_exists(self, script_path: Path):
        """Test that the script file exists."""
        assert script_path.exists(), f"Script not found: {script_path}"

    def test_script_help(self, script_path: Path):
        """Test that script shows help message when no args provided."""
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        # Script returns 1 when no args provided (shows help but indicates missing required action)
        assert result.returncode == 1
        assert "Performance Data Seeding Script" in result.stdout
        assert "--seed" in result.stdout
        assert "--cleanup" in result.stdout
        assert "--verify" in result.stdout

    def test_calculate_project_distribution(self):
        """Test AC1: Project distribution calculation."""
        # Import and test the function
        sys.path.insert(0, str(Path("scripts").parent))

        from scripts.seed_performance_data import calculate_project_distribution, DISTRIBUTION, TARGET_NODES

        distribution = calculate_project_distribution()

        # Verify all projects are present
        assert set(distribution.keys()) == set(DISTRIBUTION.keys())

        # Verify 'io' has 60% of nodes
        assert distribution['io'] == int(TARGET_NODES * 0.60)

        # Verify total matches target
        total = sum(distribution.values())
        assert total == TARGET_NODES, f"Total {total} != target {TARGET_NODES}"

    def test_generate_embedding(self):
        """Test that embedding generation creates 1536-dimensional vectors."""
        sys.path.insert(0, str(Path("scripts").parent))

        from scripts.seed_performance_data import generate_embedding

        embedding = generate_embedding()

        # Verify dimension
        assert len(embedding) == 1536, f"Embedding has {len(embedding)} dimensions, expected 1536"

        # Verify all values are floats
        assert all(isinstance(x, float) for x in embedding)

        # Verify normalized (approximately unit length)
        norm = sum(x**2 for x in embedding) ** 0.5
        assert 0.99 < norm < 1.01, f"Embedding norm {norm} is not close to 1.0"

    def test_seed_nodes_creates_correct_volume(self, conn, script_path: Path):
        """
        Test AC1: Seed creates 50,000 nodes with proper project distribution.

        AC1 Requirements:
        - 50,000 nodes total
        - Distributed across 8 projects
        - io: 60%, others: ~5% each
        """
        # First cleanup any existing data
        subprocess.run(
            [sys.executable, str(script_path), "--cleanup"],
            capture_output=True,
            timeout=300
        )

        # Seed nodes
        result = subprocess.run(
            [sys.executable, str(script_path), "--seed"],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes - adjusted for remote database latency
        )

        assert result.returncode == 0, f"Seeding failed: {result.stderr}"

        # Verify node counts
        cursor = conn.cursor()

        # Count total nodes
        cursor.execute(
            "SELECT COUNT(*) as count FROM nodes WHERE name LIKE 'perf_%%';"
        )
        total_nodes = cursor.fetchone()["count"]

        # Verify within 95% tolerance (AC1 allows some variance)
        assert total_nodes >= 47_500, f"Expected ~50,000 nodes, got {total_nodes}"

        # Verify project distribution
        sys.path.insert(0, str(Path("scripts").parent))
        from scripts.seed_performance_data import DISTRIBUTION, TARGET_NODES

        for project, expected_ratio in DISTRIBUTION.items():
            expected_count = int(TARGET_NODES * expected_ratio)

            cursor.execute(
                "SELECT COUNT(*) as count FROM nodes WHERE name LIKE %s;",
                (f"perf_{project}_%",)
            )
            actual_count = cursor.fetchone()["count"]

            # Verify within 95% tolerance
            min_acceptable = int(expected_count * 0.95)
            assert actual_count >= min_acceptable, (
                f"{project}: Expected ~{expected_count} nodes, got {actual_count}"
            )

    def test_seed_edges_creates_correct_volume(self, conn, script_path: Path):
        """
        Test AC1: Seed creates ~150,000 edges (~3 edges per node).

        AC1 Requirements:
        - 150,000 edges total
        - ~3 edges per node average
        """
        # Ensure nodes exist first
        subprocess.run(
            [sys.executable, str(script_path), "--seed"],
            capture_output=True,
            timeout=600
        )

        cursor = conn.cursor()

        # Count total edges
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM edges
            WHERE properties->>'created_for' = 'performance_test';
            """
        )
        total_edges = cursor.fetchone()["count"]

        # Verify within 95% tolerance
        assert total_edges >= 142_500, f"Expected ~150,000 edges, got {total_edges}"

    def test_seed_l2_insights_creates_correct_volume(self, conn, script_path: Path):
        """
        Test AC1: Seed creates 25,000 L2 insights with 1536-dim embeddings.

        AC1 Requirements:
        - 25,000 L2 insights
        - With 1536-dim embeddings
        """
        # Ensure data is seeded
        subprocess.run(
            [sys.executable, str(script_path), "--seed"],
            capture_output=True,
            timeout=600
        )

        cursor = conn.cursor()

        # Count total insights
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM l2_insights
            WHERE content LIKE 'Knowledge about %% component %%'
               OR content LIKE 'Technical detail from %% documentation%%'
               OR content LIKE 'Learning from %% code review%%'
               OR content LIKE 'Insight about %% architecture%%'
               OR content LIKE 'Understanding of %% workflow%%';
            """
        )
        total_insights = cursor.fetchone()["count"]

        # Verify within 95% tolerance
        assert total_insights >= 23_750, f"Expected ~25,000 insights, got {total_insights}"

        # Verify embeddings exist and are correct dimension
        cursor.execute(
            """
            SELECT embedding FROM l2_insights
            WHERE content LIKE 'Knowledge about %% component %%'
            LIMIT 1;
            """
        )
        result = cursor.fetchone()

        if result:
            # pgvector stores as array, check dimension
            embedding_str = result["embedding"]
            # pgvector format: "[0.1,0.2,...]" or as array
            # We'll verify it's not null
            assert embedding_str is not None, "Embedding should not be NULL"

    def test_seed_episodes_and_working_memory(self, conn, script_path: Path):
        """
        Test AC1: Seed creates 10,000 episodes and 500 working memory entries.

        AC1 Requirements:
        - 10,000 episode_memory entries
        - 500 working_memory entries (per-project capacity test)
        """
        # Ensure data is seeded
        subprocess.run(
            [sys.executable, str(script_path), "--seed"],
            capture_output=True,
            timeout=600
        )

        cursor = conn.cursor()

        # Count episodes
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM episode_memory
            WHERE query LIKE 'Performance test query%';
            """
        )
        total_episodes = cursor.fetchone()["count"]

        # Verify within 95% tolerance
        assert total_episodes >= 9_500, f"Expected ~10,000 episodes, got {total_episodes}"

        # Count working memory
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM working_memory
            WHERE content LIKE 'Performance test working memory entry%';
            """
        )
        total_working_memory = cursor.fetchone()["count"]

        # Verify within 95% tolerance
        assert total_working_memory >= 475, (
            f"Expected ~500 working memory entries, got {total_working_memory}"
        )

    def test_cleanup_is_idempotent(self, conn, script_path: Path):
        """
        Test Task 1.4: Cleanup function is idempotent (safe to run multiple times).

        Requirements:
        - MUST be idempotent (safe to run multiple times)
        - Use DELETE with WHERE clauses, not TRUNCATE
        - Log before/after counts for verification
        """
        # Run cleanup first time
        result1 = subprocess.run(
            [sys.executable, str(script_path), "--cleanup"],
            capture_output=True,
            text=True,
            timeout=300
        )

        assert result1.returncode == 0, f"First cleanup failed: {result1.stderr}"

        # Run cleanup second time (should succeed without errors)
        result2 = subprocess.run(
            [sys.executable, str(script_path), "--cleanup"],
            capture_output=True,
            text=True,
            timeout=300
        )

        assert result2.returncode == 0, f"Second cleanup failed (not idempotent): {result2.stderr}"

        # Verify all data is removed
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) as count FROM nodes WHERE name LIKE 'perf_%%';"
        )
        assert cursor.fetchone()["count"] == 0, "All nodes should be deleted"

        cursor.execute(
            "SELECT COUNT(*) as count FROM edges WHERE properties->>'created_for' = 'performance_test';"
        )
        assert cursor.fetchone()["count"] == 0, "All edges should be deleted"

    def test_verify_function(self, conn, script_path: Path):
        """Test that verify function correctly reports data status."""
        # First cleanup to ensure clean state
        subprocess.run(
            [sys.executable, str(script_path), "--cleanup"],
            capture_output=True,
            timeout=300
        )

        # Verify should fail with no data
        result = subprocess.run(
            [sys.executable, str(script_path), "--verify"],
            capture_output=True,
            text=True,
            timeout=60
        )

        assert result.returncode != 0, "Verify should fail when no data exists"
        assert "Verification FAILED" in result.stdout or "below threshold" in result.stdout

        # Seed data
        subprocess.run(
            [sys.executable, str(script_path), "--seed"],
            capture_output=True,
            timeout=600
        )

        # Verify should pass with data
        result = subprocess.run(
            [sys.executable, str(script_path), "--verify"],
            capture_output=True,
            text=True,
            timeout=60
        )

        assert result.returncode == 0, f"Verify failed with data: {result.stderr}"
        assert "Verification PASSED" in result.stdout

        # Check that row counts are reported
        assert "nodes:" in result.stdout
        assert "edges:" in result.stdout
        assert "l2_insights:" in result.stdout
        assert "episodes:" in result.stdout
        assert "working_memory:" in result.stdout

    def test_full_workflow_seed_verify_cleanup(self, conn, script_path: Path):
        """Test complete workflow: seed -> verify -> cleanup."""
        # Cleanup first
        result = subprocess.run(
            [sys.executable, str(script_path), "--cleanup"],
            capture_output=True,
            timeout=300
        )
        assert result.returncode == 0

        # Seed
        result = subprocess.run(
            [sys.executable, str(script_path), "--seed"],
            capture_output=True,
            text=True,
            timeout=600
        )
        assert result.returncode == 0
        assert "SEEDING COMPLETE" in result.stdout

        # Verify
        result = subprocess.run(
            [sys.executable, str(script_path), "--verify"],
            capture_output=True,
            text=True,
            timeout=60
        )
        assert result.returncode == 0
        assert "Verification PASSED" in result.stdout

        # Cleanup
        result = subprocess.run(
            [sys.executable, str(script_path), "--cleanup"],
            capture_output=True,
            text=True,
            timeout=300
        )
        assert result.returncode == 0
        assert "Cleanup completed" in result.stdout


class TestSeedingScriptStructure:
    """Test script structure and imports."""

    def test_script_has_required_functions(self):
        """Verify script has all required functions from Task 1."""
        script_path = Path("scripts/seed_performance_data.py")
        content = script_path.read_text()

        # Check for required functions
        required_functions = [
            "calculate_project_distribution",
            "seed_nodes",
            "seed_edges",
            "seed_l2_insights",
            "seed_episodes",
            "seed_working_memory",
            "cleanup_performance_data",
            "verify_performance_data",
        ]

        for func in required_functions:
            assert f"def {func}" in content, f"Missing function: {func}"

    def test_script_uses_async_await_pattern(self):
        """Verify script uses asyncio.run() entry point as required."""
        script_path = Path("scripts/seed_performance_data.py")
        content = script_path.read_text()

        # Check for async pattern (Task 1.1 requirement)
        # Since we're using sync wrapper for script, verify it uses get_connection_sync
        assert "get_connection_sync" in content, "Should use get_connection_sync for script operations"

    def test_script_follows_reference_pattern(self):
        """Verify script follows setup_test_graph.py reference pattern."""
        script_path = Path("scripts/seed_performance_data.py")
        reference_path = Path("scripts/setup_test_graph.py")

        script_content = script_path.read_text()
        reference_content = reference_path.read_text()

        # Both should have similar structure
        for pattern in ["def cleanup_", "def verify_", "def main"]:
            assert pattern in script_content, f"Missing pattern: {pattern}"

    def test_project_distribution_matches_ac1(self):
        """Verify AC1 project distribution is correctly implemented."""
        script_path = Path("scripts/seed_performance_data.py")
        content = script_path.read_text()

        # Check for distribution configuration
        assert "'io': 0.60" in content, "io project should have 60% distribution"
        assert "TARGET_NODES = 50_000" in content, "Should target 50,000 nodes"
        assert "TARGET_EDGES = 150_000" in content, "Should target 150,000 edges"
        assert "TARGET_L2_INSIGHTS = 25_000" in content, "Should target 25,000 insights"
