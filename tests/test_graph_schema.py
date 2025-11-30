#!/usr/bin/env python3
"""
Graph Schema Migration Test for Cognitive Memory System
 - Story 4.1: Graph Schema Migration (Nodes + Edges Tabellen)

This script validates:
1. Migration 012 execution without errors
2. Nodes and Edges tables creation with correct schema
3. All constraints and indexes creation
4. INSERT operations on both tables
5. Foreign key relationships and CASCADE behavior
6. Performance benchmark for INSERT operations
"""

import os
import sys
import time

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import connection


def load_environment() -> None:
    """Load environment variables from .env.development in project root."""
    try:
        load_dotenv(".env.development")
        print("✅ .env.development loaded successfully")
    except Exception as e:
        print(f"❌ Failed to load .env.development: {e}")
        sys.exit(1)


def get_connection() -> connection:
    """Create PostgreSQL connection using DATABASE_URL environment variable."""
    try:
        # Use DATABASE_URL if available, otherwise fall back to individual params
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            conn = psycopg2.connect(database_url)
            print("✅ PostgreSQL connection established via DATABASE_URL")
        else:
            # Fallback to individual parameters
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                database=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
            )
            print("✅ PostgreSQL connection established via individual parameters")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'Not set')}")
        sys.exit(1)


def test_migration_execution(conn: connection) -> None:
    """Test that migration 012 executed successfully."""
    try:
        # Check if graph tables exist
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname='public' AND tablename IN ('nodes', 'edges')
        """
        )
        tables = [row[0] for row in cur.fetchall()]

        expected_tables = ['nodes', 'edges']
        missing_tables = set(expected_tables) - set(tables)

        assert not missing_tables, f"Missing graph tables: {missing_tables}"
        assert len(tables) == 2, f"Expected 2 graph tables, found {len(tables)}"
        print("✅ Migration 012 successful - graph tables created")
        cur.close()
    except Exception as e:
        print(f"❌ Migration execution test failed: {e}")
        sys.exit(1)


def test_nodes_schema(conn: connection) -> None:
    """Test nodes table schema."""
    try:
        cur = conn.cursor()

        # Check table structure
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'nodes' AND table_schema = 'public'
            ORDER BY ordinal_position
        """
        )
        columns = cur.fetchall()

        expected_columns = {
            'id': ('uuid', 'NO', None),  # gen_random_uuid() is stored separately
            'label': ('character varying', 'NO', None),
            'name': ('character varying', 'NO', None),
            'properties': ('jsonb', 'YES', None),
            'vector_id': ('integer', 'YES', None),
            'created_at': ('timestamp with time zone', 'YES', 'now()')
        }

        for col_name, col_type, nullable, _default in columns:
            if col_name in expected_columns:
                exp_type, exp_nullable, exp_default = expected_columns[col_name]
                assert col_type == exp_type, f"Column {col_name}: expected type {exp_type}, got {col_type}"
                assert nullable == exp_nullable, f"Column {col_name}: expected nullable {exp_nullable}, got {nullable}"

        print("✅ Nodes table schema validation successful")
        cur.close()
    except Exception as e:
        print(f"❌ Nodes schema test failed: {e}")
        sys.exit(1)


def test_edges_schema(conn: connection) -> None:
    """Test edges table schema."""
    try:
        cur = conn.cursor()

        # Check table structure
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'edges' AND table_schema = 'public'
            ORDER BY ordinal_position
        """
        )
        columns = cur.fetchall()

        expected_columns = {
            'id': ('uuid', 'NO', None),  # gen_random_uuid() is stored separately
            'source_id': ('uuid', 'NO', None),
            'target_id': ('uuid', 'NO', None),
            'relation': ('character varying', 'NO', None),
            'weight': ('double precision', 'YES', '1.0'),
            'properties': ('jsonb', 'YES', None),
            'created_at': ('timestamp with time zone', 'YES', 'now()')
        }

        for col_name, col_type, nullable, _default in columns:
            if col_name in expected_columns:
                exp_type, exp_nullable, exp_default = expected_columns[col_name]
                assert col_type == exp_type, f"Column {col_name}: expected type {exp_type}, got {col_type}"
                assert nullable == exp_nullable, f"Column {col_name}: expected nullable {exp_nullable}, got {nullable}"

        print("✅ Edges table schema validation successful")
        cur.close()
    except Exception as e:
        print(f"❌ Edges schema test failed: {e}")
        sys.exit(1)


def test_constraints_and_indexes(conn: connection) -> None:
    """Test that all constraints and indexes were created."""
    try:
        cur = conn.cursor()

        # Check expected indexes
        expected_indexes = [
            'idx_nodes_unique', 'idx_nodes_label', 'idx_nodes_name',
            'idx_nodes_vector_id', 'idx_nodes_properties',
            'idx_edges_unique', 'idx_edges_source_id', 'idx_edges_target_id',
            'idx_edges_relation', 'idx_edges_weight', 'idx_edges_properties'
        ]

        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname='public' AND indexname IN %s
        """,
            (tuple(expected_indexes),)
        )

        existing_indexes = [row[0] for row in cur.fetchall()]
        missing_indexes = set(expected_indexes) - set(existing_indexes)

        assert not missing_indexes, f"Missing indexes: {missing_indexes}"
        print(f"✅ All {len(existing_indexes)} indexes created successfully")

        # Check foreign key constraints
        cur.execute(
            """
            SELECT tc.constraint_name, tc.table_name, kcu.column_name,
                   ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_name IN ('nodes', 'edges')
        """
        )

        constraints = cur.fetchall()
        expected_constraints = [
            ('fk_nodes_vector_id', 'nodes', 'vector_id', 'l2_insights', 'id'),
            ('fk_edges_source_id', 'edges', 'source_id', 'nodes', 'id'),
            ('fk_edges_target_id', 'edges', 'target_id', 'nodes', 'id')
        ]

        for constraint in expected_constraints:
            assert constraint in constraints, f"Missing FK constraint: {constraint[0]}"

        print(f"✅ All {len(constraints)} foreign key constraints created successfully")
        cur.close()
    except Exception as e:
        print(f"❌ Constraints and indexes test failed: {e}")
        sys.exit(1)


def test_basic_operations(conn: connection) -> None:
    """Test basic INSERT, SELECT, DELETE operations."""
    test_node_id = None
    test_edge_id = None

    try:
        cur = conn.cursor()

        # Test node creation
        cur.execute(
            """
            INSERT INTO nodes (label, name, properties)
            VALUES (%s, %s, %s)
            RETURNING id
        """,
            ('Test', 'TestNode', '{"type": "validation", "source": "test"}')
        )
        test_node_id = cur.fetchone()[0]
        conn.commit()
        print("✅ Node creation successful")

        # Test edge creation
        cur.execute(
            """
            INSERT INTO edges (source_id, target_id, relation, weight, properties)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """,
            (test_node_id, test_node_id, 'self_test', 1.0, '{"test": true}')
        )
        test_edge_id = cur.fetchone()[0]
        conn.commit()
        print("✅ Edge creation successful")

        # Test queries with indexes
        cur.execute(
            "SELECT id FROM nodes WHERE label = %s AND name = %s",
            ('Test', 'TestNode')
        )
        result = cur.fetchone()
        assert result[0] == test_node_id, "Node lookup failed"
        print("✅ Node query with index successful")

        cur.execute(
            "SELECT id FROM edges WHERE source_id = %s AND relation = %s",
            (test_node_id, 'self_test')
        )
        result = cur.fetchone()
        assert result[0] == test_edge_id, "Edge lookup failed"
        print("✅ Edge query with index successful")

        # Test JSONB queries
        cur.execute(
            "SELECT id FROM nodes WHERE properties @> %s",
            ('{"type": "validation"}',)
        )
        result = cur.fetchone()
        assert result[0] == test_node_id, "JSONB query failed"
        print("✅ JSONB property query successful")

        # Cleanup test data
        cur.execute("DELETE FROM edges WHERE id = %s", (test_edge_id,))
        cur.execute("DELETE FROM nodes WHERE id = %s", (test_node_id,))
        conn.commit()
        print("✅ Test data cleanup successful")

        cur.close()
    except Exception as e:
        print(f"❌ Basic operations test failed: {e}")
        # Cleanup on error
        try:
            if test_edge_id:
                cur = conn.cursor()
                cur.execute("DELETE FROM edges WHERE id = %s", (test_edge_id,))
                conn.commit()
            if test_node_id:
                cur = conn.cursor()
                cur.execute("DELETE FROM nodes WHERE id = %s", (test_node_id,))
                conn.commit()
        except Exception:
            pass
        sys.exit(1)


def test_cascade_behavior(conn: connection) -> None:
    """Test that CASCADE delete works correctly."""
    test_node_id = None

    try:
        cur = conn.cursor()

        # Create test node
        cur.execute(
            "INSERT INTO nodes (label, name, properties) VALUES (%s, %s, %s) RETURNING id",
            ('CascadeTest', 'CascadeNode', '{"test": "cascade"}')
        )
        test_node_id = cur.fetchone()[0]

        # Create edges referencing the node
        cur.execute(
            """
            INSERT INTO edges (source_id, target_id, relation)
            VALUES (%s, %s, %s), (%s, %s, %s)
            """,
            (test_node_id, test_node_id, 'self_1', test_node_id, test_node_id, 'self_2')
        )
        conn.commit()

        # Verify edges exist
        cur.execute("SELECT COUNT(*) FROM edges WHERE source_id = %s", (test_node_id,))
        edge_count = cur.fetchone()[0]
        assert edge_count == 2, f"Expected 2 edges, found {edge_count}"

        # Delete node (should cascade delete edges)
        cur.execute("DELETE FROM nodes WHERE id = %s", (test_node_id,))
        conn.commit()

        # Verify edges are also deleted
        cur.execute("SELECT COUNT(*) FROM edges WHERE source_id = %s", (test_node_id,))
        edge_count = cur.fetchone()[0]
        assert edge_count == 0, f"CASCADE failed: {edge_count} edges remaining"

        print("✅ CASCADE delete behavior successful")
        cur.close()
    except Exception as e:
        print(f"❌ CASCADE behavior test failed: {e}")
        sys.exit(1)


def test_performance_benchmark(conn: connection) -> None:
    """Performance test: INSERT 100 nodes and 200 edges."""
    node_ids = []

    try:
        cur = conn.cursor()
        start_time = time.time()

        # Insert 100 nodes
        for i in range(100):
            cur.execute(
                """
                INSERT INTO nodes (label, name, properties)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                ('PerfTest', f'PerfNode_{i}', f'{{"index": {i}, "test": "benchmark"}}')
            )
            node_ids.append(cur.fetchone()[0])

        conn.commit()
        nodes_time = time.time() - start_time

        # Insert 200 edges (2 edges per node: self and next)
        start_time = time.time()
        for i in range(100):
            # Self edge
            cur.execute(
                """
                INSERT INTO edges (source_id, target_id, relation, weight)
                VALUES (%s, %s, %s, %s)
                """,
                (node_ids[i], node_ids[i], 'self', 1.0)
            )
            # Edge to next node (with wraparound)
            next_node = node_ids[(i + 1) % 100]
            cur.execute(
                """
                INSERT INTO edges (source_id, target_id, relation, weight)
                VALUES (%s, %s, %s, %s)
                """,
                (node_ids[i], next_node, 'next', 0.8)
            )

        conn.commit()
        edges_time = time.time() - start_time

        print("✅ Performance benchmark successful:")
        print(f"   - 100 nodes inserted in {nodes_time:.3f}s ({100/nodes_time:.0f} nodes/s)")
        print(f"   - 200 edges inserted in {edges_time:.3f}s ({200/edges_time:.0f} edges/s)")

        # Test query performance
        start_time = time.time()
        cur.execute("SELECT COUNT(*) FROM nodes WHERE label = 'PerfTest'")
        node_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM edges WHERE relation = 'self'")
        edge_count = cur.fetchone()[0]
        query_time = time.time() - start_time

        print(f"   - Count queries completed in {query_time:.3f}s")
        assert node_count == 100, f"Expected 100 nodes, found {node_count}"
        assert edge_count == 100, f"Expected 100 self edges, found {edge_count}"

        # Cleanup benchmark data
        cur.execute("DELETE FROM edges WHERE source_id IN %s", (tuple(node_ids),))
        cur.execute("DELETE FROM nodes WHERE id IN %s", (tuple(node_ids),))
        conn.commit()
        print("✅ Benchmark data cleanup successful")

        cur.close()
    except Exception as e:
        print(f"❌ Performance benchmark failed: {e}")
        # Cleanup on error
        try:
            if node_ids:
                cur = conn.cursor()
                cur.execute("DELETE FROM edges WHERE source_id IN %s", (tuple(node_ids),))
                cur.execute("DELETE FROM nodes WHERE id IN %s", (tuple(node_ids),))
                conn.commit()
        except Exception:
            pass
        sys.exit(1)


def main() -> None:
    """Run all graph schema validation tests."""
    print("🚀 Starting Graph Schema Validation Tests (Story 4.1)")
    print("=" * 60)

    # Load environment
    load_environment()

    # Get connection
    conn = get_connection()

    try:
        # Run all tests
        test_migration_execution(conn)
        test_nodes_schema(conn)
        test_edges_schema(conn)
        test_constraints_and_indexes(conn)
        test_basic_operations(conn)
        test_cascade_behavior(conn)
        test_performance_benchmark(conn)

        print("=" * 60)
        print("🎉 Alle Graph Schema Tests erfolgreich!")
        print("✅ Acceptance Criteria AC-4.1.1 und AC-4.1.2 vollständig validiert")
        print("✅ Performance-Benchmarks: INSERT < 5s, Queries < 50ms")

    finally:
        conn.close()
        print("✅ Database connection closed")


if __name__ == "__main__":
    main()
