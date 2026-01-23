#!/usr/bin/env python3
"""
Performance Data Seeding Script for Story 11.1.0

Seeds production-like data volumes for baseline RLS performance measurement:
- 50,000 nodes (distributed across 8 projects)
- 150,000 edges (~3 edges per node average)
- 25,000 L2 insights (with 1536-dim embeddings)
- 10,000 episode_memory entries
- 500 working_memory entries

Usage:
    python scripts/seed_performance_data.py --seed     # Create performance data
    python scripts/seed_performance_data.py --cleanup  # Remove performance data
    python scripts/seed_performance_data.py --verify   # Verify data exists

Story 11.1.0: Performance Baseline Capture (AC1: Test Data Volume Definition)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import statistics
import time

import numpy as np
from dotenv import load_dotenv

# Load environment before imports
load_dotenv(".env.development", override=True)

from mcp_server.db.connection import initialize_pool_sync, get_connection_sync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration (AC1: Production-Like Data Volumes)
# =============================================================================

# Project distribution for 50,000 nodes
PROJECTS = ['io', 'aa', 'ab', 'bap', 'ea', 'echo', 'motoko', 'sm']
DISTRIBUTION = {
    'io': 0.60,      # 30,000 nodes
    'aa': 0.05,      # 2,500 nodes
    'ab': 0.05,      # 2,500 nodes
    'bap': 0.05,     # 2,500 nodes
    'ea': 0.05,      # 2,500 nodes
    'echo': 0.05,    # 2,500 nodes
    'motoko': 0.05,  # 2,500 nodes
    'sm': 0.05,      # 2,500 nodes
}

# Target row counts (AC1)
TARGET_NODES = 50_000
TARGET_EDGES = 150_000
TARGET_L2_INSIGHTS = 25_000
TARGET_EPISODES = 10_000
TARGET_WORKING_MEMORY = 500

# Edge relations to simulate
RELATIONS = [
    "USES", "SOLVES", "CREATED_BY", "RELATED_TO", "DEPENDS_ON",
    "CONNECTS_TO", "REFERENCES", "INCLUDES", "EXTENDS", "IMPLEMENTS"
]

# Node labels to simulate
NODE_LABELS = [
    "Project", "Technology", "Concept", "Task", "Error", "Solution",
    "Requirement", "Design", "Module", "Component"
]

# =============================================================================
# Helper Functions
# =============================================================================

def calculate_project_distribution() -> dict[str, int]:
    """
    Calculate exact node counts per project based on distribution.

    AC1 requires: io=60%, others=~5% each (total must be 50,000)
    Note: DISTRIBUTION sums to 0.95, so remainder is distributed evenly
    across non-io projects to maintain io at exactly 60%.

    Returns:
        Dict mapping project name to node count
    """
    distribution = {}
    for project, ratio in DISTRIBUTION.items():
        distribution[project] = int(TARGET_NODES * ratio)

    # Adjust for rounding errors to ensure total matches TARGET_NODES
    # Distribute remainder evenly across non-io projects to keep io at 60%
    current_total = sum(distribution.values())
    remainder = TARGET_NODES - current_total

    if remainder > 0:
        non_io_projects = [p for p in PROJECTS if p != 'io']
        per_project = remainder // len(non_io_projects)
        extra = remainder % len(non_io_projects)

        for i, project in enumerate(non_io_projects):
            distribution[project] += per_project + (1 if i < extra else 0)

    return distribution


def generate_embedding() -> list[float]:
    """
    Generate a 1536-dimensional embedding vector.

    For production-like data, we use random values with proper normalization.
    This avoids calling OpenAI API 25,000 times during seeding.

    Returns:
        List of 1536 float values (normalized to unit length)
    """
    # Generate random values
    embedding = np.random.randn(1536).tolist()

    # Normalize to unit length (similar to OpenAI embeddings)
    norm = sum(x**2 for x in embedding) ** 0.5
    embedding = [x / norm for x in embedding]

    return embedding


def generate_sample_text(project: str, index: int) -> str:
    """Generate sample text for L2 insights based on project context."""
    templates = [
        f"Knowledge about {project} component {index}",
        f"Technical detail from {project} documentation section {index}",
        f"Learning from {project} code review session {index}",
        f"Insight about {project} architecture decision {index}",
        f"Understanding of {project} workflow pattern {index}",
    ]
    return random.choice(templates)


# =============================================================================
# Seeding Functions
# =============================================================================

def seed_nodes(distribution: dict[str, int]) -> dict[str, int]:
    """
    Seed performance test nodes across all projects.

    Args:
        distribution: Dict mapping project name to node count

    Returns:
        Dict with nodes_created count
    """
    logger.info("Seeding performance test nodes...")
    start_time = time.time()

    nodes_created = 0
    batch_size = 1000

    # Track creation times for reporting
    creation_times = []

    for project, count in distribution.items():
        logger.info(f"Seeding {count} nodes for project: {project}")

        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch_nodes = []

            batch_start_time = time.time()

            for i in range(batch_start, batch_end):
                node_name = f"perf_{project}_{i:05d}"
                label = random.choice(NODE_LABELS)
                properties = json.dumps({
                    "project": project,
                    "index": i,
                    "created_for": "performance_test",
                    "batch": batch_start // batch_size
                })

                # Use synchronous version for script
                batch_nodes.append((label, node_name, properties, None))

            # Insert batch using sync connection
            try:
                with get_connection_sync() as conn:
                    cursor = conn.cursor()

                    for label, name, props, vector_id in batch_nodes:
                        cursor.execute(
                            """
                            INSERT INTO nodes (label, name, properties, vector_id)
                            VALUES (%s, %s, %s::jsonb, %s)
                            ON CONFLICT (name) DO UPDATE SET
                                label = EXCLUDED.label,
                                properties = EXCLUDED.properties
                            RETURNING id;
                            """,
                            (label, name, props, vector_id)
                        )
                        nodes_created += 1

                    conn.commit()

            except Exception as e:
                logger.error(f"Failed to insert batch for {project}: {e}")
                continue

            batch_time = time.time() - batch_start_time
            creation_times.append(batch_time)

            if (batch_end // batch_size) % 10 == 0:
                avg_time = statistics.mean(creation_times[-10:]) if creation_times else 0
                logger.info(
                    f"  Progress: {batch_end}/{count} nodes for {project} "
                    f"(avg batch time: {avg_time:.2f}s)"
                )

    elapsed = time.time() - start_time
    rate = nodes_created / elapsed if elapsed > 0 else 0
    logger.info(
        f"Seeded {nodes_created} nodes in {elapsed:.2f}s "
        f"({rate:.0f} nodes/sec)"
    )

    return {"nodes_created": nodes_created}


def seed_edges(distribution: dict[str, int]) -> dict[str, int]:
    """
    Seed performance test edges.

    Creates ~3 edges per node on average across all projects.

    Args:
        distribution: Dict mapping project name to node count

    Returns:
        Dict with edges_created count
    """
    logger.info("Seeding performance test edges...")
    start_time = time.time()

    edges_created = 0
    batch_size = 1000

    # Track creation times for reporting
    creation_times = []

    # First, get all node IDs for each project
    project_node_ids = {}

    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            for project in PROJECTS:
                cursor.execute(
                    """
                    SELECT id, name
                    FROM nodes
                    WHERE name LIKE %s
                    ORDER BY name;
                    """,
                    (f"perf_{project}_%",)
                )

                results = cursor.fetchall()
                project_node_ids[project] = [
                    str(row["id"]) for row in results
                ]

                logger.info(f"Loaded {len(project_node_ids[project])} nodes for {project}")

    except Exception as e:
        logger.error(f"Failed to load node IDs: {e}")
        return {"edges_created": 0}

    # Create edges (mix of intra-project and inter-project)
    total_target_edges = sum(distinction * 3 for distinction in distribution.values())

    for batch_start in range(0, total_target_edges, batch_size):
        batch_end = min(batch_start + batch_size, total_target_edges)
        batch_start_time = time.time()

        try:
            with get_connection_sync() as conn:
                cursor = conn.cursor()

                for _ in range(batch_end - batch_start):
                    # Choose random source project (weighted by distribution)
                    source_project = random.choices(
                        PROJECTS,
                        weights=[DISTRIBUTION[p] for p in PROJECTS],
                        k=1
                    )[0]

                    # Choose target project (80% same project, 20% different)
                    if random.random() < 0.8:
                        target_project = source_project
                    else:
                        target_project = random.choice([p for p in PROJECTS if p != source_project])

                    # Get node IDs for chosen projects
                    source_ids = project_node_ids.get(source_project, [])
                    target_ids = project_node_ids.get(target_project, [])

                    if not source_ids or not target_ids:
                        continue

                    # Random source and target
                    source_id = random.choice(source_ids)
                    target_id = random.choice(target_ids)

                    # Skip if same node (no self-loops)
                    if source_id == target_id:
                        continue

                    relation = random.choice(RELATIONS)
                    weight = random.uniform(0.5, 1.0)
                    properties = json.dumps({
                        "created_for": "performance_test",
                        "batch": batch_start // batch_size
                    })

                    cursor.execute(
                        """
                        INSERT INTO edges (source_id, target_id, relation, weight, properties, memory_sector)
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, 'semantic')
                        ON CONFLICT (source_id, target_id, relation) DO UPDATE SET
                            weight = EXCLUDED.weight,
                            properties = EXCLUDED.properties
                        RETURNING id;
                        """,
                        (source_id, target_id, relation, weight, properties)
                    )

                    edges_created += 1

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to insert edge batch: {e}")
            continue

        batch_time = time.time() - batch_start_time
        creation_times.append(batch_time)

        if (batch_end // batch_size) % 10 == 0:
            avg_time = statistics.mean(creation_times[-10:]) if creation_times else 0
            logger.info(
                f"  Progress: {batch_end}/{total_target_edges} edges "
                f"(avg batch time: {avg_time:.2f}s)"
            )

    elapsed = time.time() - start_time
    rate = edges_created / elapsed if elapsed > 0 else 0
    logger.info(
        f"Seeded {edges_created} edges in {elapsed:.2f}s "
        f"({rate:.0f} edges/sec)"
    )

    return {"edges_created": edges_created}


def seed_l2_insights(distribution: dict[str, int]) -> dict[str, int]:
    """
    Seed L2 insights with 1536-dimensional embeddings.

    Args:
        distribution: Dict mapping project name to node count

    Returns:
        Dict with insights_created count
    """
    logger.info(f"Seeding {TARGET_L2_INSIGHTS} L2 insights...")
    start_time = time.time()

    insights_created = 0
    batch_size = 500

    creation_times = []

    # Calculate insights per project (proportional to node count)
    total_nodes = sum(distribution.values())

    for batch_start in range(0, TARGET_L2_INSIGHTS, batch_size):
        batch_end = min(batch_start + batch_size, TARGET_L2_INSIGHTS)
        batch_start_time = time.time()

        try:
            with get_connection_sync() as conn:
                cursor = conn.cursor()

                for i in range(batch_start, batch_end):
                    # Determine project based on distribution
                    rand_val = random.random() * total_nodes
                    cumulative = 0
                    selected_project = PROJECTS[0]

                    for project in PROJECTS:
                        cumulative += distribution[project]
                        if rand_val <= cumulative:
                            selected_project = project
                            break

                    # Generate insight content
                    content = generate_sample_text(selected_project, i)
                    embedding = generate_embedding()
                    memory_strength = random.uniform(0.3, 1.0)

                    # Convert embedding to pgvector format
                    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

                    cursor.execute(
                        """
                        INSERT INTO l2_insights (content, embedding, memory_strength)
                        VALUES (%s, %s::vector, %s)
                        RETURNING id;
                        """,
                        (content, embedding_str, memory_strength)
                    )

                    insights_created += 1

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to insert insight batch: {e}")
            continue

        batch_time = time.time() - batch_start_time
        creation_times.append(batch_time)

        if (batch_end // batch_size) % 10 == 0:
            avg_time = statistics.mean(creation_times[-10:]) if creation_times else 0
            logger.info(
                f"  Progress: {batch_end}/{TARGET_L2_INSIGHTS} insights "
                f"(avg batch time: {avg_time:.2f}s)"
            )

    elapsed = time.time() - start_time
    rate = insights_created / elapsed if elapsed > 0 else 0
    logger.info(
        f"Seeded {insights_created} L2 insights in {elapsed:.2f}s "
        f"({rate:.0f} insights/sec)"
    )

    return {"insights_created": insights_created}


def seed_episodes() -> dict[str, int]:
    """Seed episode memory entries for testing."""
    logger.info(f"Seeding {TARGET_EPISODES} episode memories...")
    start_time = time.time()

    episodes_created = 0
    batch_size = 1000

    for batch_start in range(0, TARGET_EPISODES, batch_size):
        batch_end = min(batch_start + batch_size, TARGET_EPISODES)

        try:
            with get_connection_sync() as conn:
                cursor = conn.cursor()

                for i in range(batch_start, batch_end):
                    query = f"Performance test query {i}"
                    reward = random.uniform(-0.5, 1.0)
                    reflection = f"Test reflection for episode {i}: Learning pattern observed"

                    cursor.execute(
                        """
                        INSERT INTO episode_memory (query, reward, reflection)
                        VALUES (%s, %s, %s)
                        RETURNING id;
                        """,
                        (query, reward, reflection)
                    )

                    episodes_created += 1

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to insert episode batch: {e}")
            continue

        if (batch_end // batch_size) % 10 == 0:
            logger.info(f"  Progress: {batch_end}/{TARGET_EPISODES} episodes")

    elapsed = time.time() - start_time
    rate = episodes_created / elapsed if elapsed > 0 else 0
    logger.info(
        f"Seeded {episodes_created} episodes in {elapsed:.2f}s "
        f"({rate:.0f} episodes/sec)"
    )

    return {"episodes_created": episodes_created}


def seed_working_memory() -> dict[str, int]:
    """Seed working memory entries for testing."""
    logger.info(f"Seeding {TARGET_WORKING_MEMORY} working memory entries...")
    start_time = time.time()

    working_memory_created = 0

    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            for i in range(TARGET_WORKING_MEMORY):
                content = f"Performance test working memory entry {i}"
                importance = random.uniform(0.3, 1.0)

                cursor.execute(
                    """
                    INSERT INTO working_memory (content, importance)
                    VALUES (%s, %s)
                    RETURNING id;
                    """,
                    (content, importance)
                )

                working_memory_created += 1

            conn.commit()

    except Exception as e:
        logger.error(f"Failed to seed working memory: {e}")

    elapsed = time.time() - start_time
    logger.info(
        f"Seeded {working_memory_created} working memory entries in {elapsed:.2f}s"
    )

    return {"working_memory_created": working_memory_created}


# =============================================================================
# Cleanup Function (Idempotent)
# =============================================================================

def cleanup_performance_data() -> dict[str, int]:
    """
    Remove all performance test data (idempotent - safe to run multiple times).

    Returns:
        Dict with counts of deleted items
    """
    logger.info("Cleaning up performance test data...")
    start_time = time.time()

    nodes_deleted = 0
    edges_deleted = 0
    insights_deleted = 0
    episodes_deleted = 0
    working_memory_deleted = 0

    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            # Delete working memory entries
            cursor.execute(
                """
                DELETE FROM working_memory
                WHERE content LIKE 'Performance test working memory entry%';
                """
            )
            working_memory_deleted = cursor.rowcount
            logger.info(f"Deleted {working_memory_deleted} working memory entries")

            # Delete episode memories
            cursor.execute(
                """
                DELETE FROM episode_memory
                WHERE query LIKE 'Performance test query%';
                """
            )
            episodes_deleted = cursor.rowcount
            logger.info(f"Deleted {episodes_deleted} episode memories")

            # Delete L2 insights
            cursor.execute(
                """
                DELETE FROM l2_insights
                WHERE content LIKE 'Knowledge about %% component %%'
                   OR content LIKE 'Technical detail from %% documentation%%'
                   OR content LIKE 'Learning from %% code review%%'
                   OR content LIKE 'Insight about %% architecture%%'
                   OR content LIKE 'Understanding of %% workflow%%';
                """
            )
            insights_deleted = cursor.rowcount
            logger.info(f"Deleted {insights_deleted} L2 insights")

            # Delete edges (will cascade)
            cursor.execute(
                """
                DELETE FROM edges
                WHERE properties->>'created_for' = 'performance_test';
                """
            )
            edges_deleted = cursor.rowcount
            logger.info(f"Deleted {edges_deleted} edges")

            # Delete nodes
            cursor.execute(
                """
                DELETE FROM nodes
                WHERE name LIKE 'perf_%%';
                """
            )
            nodes_deleted = cursor.rowcount
            logger.info(f"Deleted {nodes_deleted} nodes")

            conn.commit()

    except Exception as e:
        logger.error(f"Failed to cleanup performance data: {e}")
        raise

    elapsed = time.time() - start_time
    logger.info(f"Cleanup completed in {elapsed:.2f}s")

    return {
        "nodes_deleted": nodes_deleted,
        "edges_deleted": edges_deleted,
        "insights_deleted": insights_deleted,
        "episodes_deleted": episodes_deleted,
        "working_memory_deleted": working_memory_deleted,
    }


# =============================================================================
# Verification Function
# =============================================================================

def verify_performance_data() -> dict[str, Any]:
    """
    Verify that performance test data exists and meets volume requirements.

    Returns:
        Dict with verification results and row counts
    """
    logger.info("Verifying performance test data...")

    results = {
        "verification_passed": False,
        "row_counts": {},
        "expected": {
            "nodes": TARGET_NODES,
            "edges": TARGET_EDGES,
            "l2_insights": TARGET_L2_INSIGHTS,
            "episodes": TARGET_EPISODES,
            "working_memory": TARGET_WORKING_MEMORY,
        },
        "tolerance": 0.95  # 95% of target is acceptable
    }

    try:
        with get_connection_sync() as conn:
            cursor = conn.cursor()

            # Count nodes
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM nodes
                WHERE name LIKE 'perf_%%';
                """
            )
            results["row_counts"]["nodes"] = cursor.fetchone()["count"] or 0

            # Count edges
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM edges
                WHERE properties->>'created_for' = 'performance_test';
                """
            )
            results["row_counts"]["edges"] = cursor.fetchone()["count"] or 0

            # Count L2 insights
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
            results["row_counts"]["l2_insights"] = cursor.fetchone()["count"] or 0

            # Count episodes
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM episode_memory
                WHERE query LIKE 'Performance test query%';
                """
            )
            results["row_counts"]["episodes"] = cursor.fetchone()["count"] or 0

            # Count working memory
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM working_memory
                WHERE content LIKE 'Performance test working memory entry%';
                """
            )
            results["row_counts"]["working_memory"] = cursor.fetchone()["count"] or 0

    except Exception as e:
        logger.error(f"Failed to verify performance data: {e}")
        results["error"] = str(e)
        return results

    # Check if all counts meet tolerance threshold
    results["verification_passed"] = all(
        count >= results["expected"][table] * results["tolerance"]
        for table, count in results["row_counts"].items()
    )

    # Report results
    logger.info("Verification Results:")
    for table, count in results["row_counts"].items():
        expected = results["expected"][table]
        percentage = (count / expected * 100) if expected > 0 else 0
        status = "✓" if count >= expected * results["tolerance"] else "✗"
        logger.info(f"  {status} {table}: {count:,}/{expected:,} ({percentage:.1f}%)")

    if results["verification_passed"]:
        logger.info("✅ Verification PASSED")
    else:
        logger.warning("⚠️ Verification FAILED - Some tables below threshold")

    return results


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Performance Data Seeding Script for Story 11.1.0"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Create performance test data"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove performance test data"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify performance test data exists"
    )

    args = parser.parse_args()

    if not any([args.seed, args.cleanup, args.verify]):
        parser.print_help()
        return 1

    # Initialize connection pool
    try:
        initialize_pool_sync()
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        return 1

    # Calculate project distribution
    distribution = calculate_project_distribution()
    logger.info(f"Project distribution: {distribution}")

    if args.cleanup:
        cleanup_performance_data()

    if args.seed:
        logger.info("=" * 70)
        logger.info("PERFORMANCE DATA SEEDING - Story 11.1.0 AC1")
        logger.info("=" * 70)

        # Seed in order: nodes -> edges -> insights -> episodes -> working memory
        seed_nodes(distribution)
        seed_edges(distribution)
        seed_l2_insights(distribution)
        seed_episodes()
        seed_working_memory()

        logger.info("=" * 70)
        logger.info("SEEDING COMPLETE")
        logger.info("=" * 70)

        # Verify after seeding
        results = verify_performance_data()
        if not results["verification_passed"]:
            return 1

    if args.verify:
        results = verify_performance_data()
        if not results["verification_passed"]:
            return 1

    return 0


if __name__ == "__main__":
    exit(main())
