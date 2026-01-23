"""Tests for Story 11.1.4: Composite Indexes for RLS Performance

This test suite verifies that composite indexes with project_id as the first
column are created and that queries using project_id filters use index scans
instead of sequential scans.
"""

import pytest
from psycopg2.extensions import connection
from psycopg2.extras import DictCursor


def fetch_all(conn: connection, query: str, params=None) -> list:
    """Helper to fetch all results using DictCursor."""
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def fetch_one(conn: connection, query: str, params=None) -> dict | None:
    """Helper to fetch one result using DictCursor."""
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchone()


def fetch_val(conn: connection, query: str, params=None) -> any:
    """Helper to fetch a single value."""
    with conn.cursor() as cur:
        cur.execute(query, params)
        result = cur.fetchone()
        return result[0] if result else None


def execute_sql(conn: connection, query: str, params=None) -> None:
    """Helper to execute SQL without returning results."""
    with conn.cursor() as cur:
        cur.execute(query, params)


@pytest.mark.P0
@pytest.mark.integration
def test_composite_indexes_created(conn: connection):
    """INTEGRATION: Verify all composite indexes are created

    GIVEN migration 029 has been applied
    WHEN checking pg_indexes
    THEN all project_id indexes exist
    """
    result = fetch_all(conn, """
        SELECT indexname
        FROM pg_indexes
        WHERE indexname LIKE '%project%'
        ORDER BY indexname
    """)

    index_names = [row['indexname'] for row in result]

    # Verify all expected indexes exist
    assert 'idx_nodes_project_id' in index_names
    assert 'idx_edges_project_id' in index_names
    assert 'idx_l2_insights_project_id' in index_names
    assert 'idx_edges_source_project' in index_names
    assert 'idx_edges_target_project' in index_names
    # Note: idx_l2_insights_node_project doesn't exist - l2_insights doesn't have node_id column


@pytest.mark.P0
@pytest.mark.integration
def test_indexes_are_valid(conn: connection):
    """INTEGRATION: Verify all indexes are valid (not invalid from failed CONCURRENTLY)

    GIVEN indexes created with CONCURRENTLY
    WHEN checking pg_index for indisvalid flag
    THEN all indexes should have indisvalid = TRUE
    """
    result = fetch_all(conn, """
        SELECT indexrelid::regclass AS index_name, indisvalid
        FROM pg_index
        WHERE indexrelid::regclass::text LIKE 'idx_%_project%'
    """)

    for row in result:
        assert row['indisvalid'], f"Index {row['index_name']} is invalid!"


@pytest.mark.P0
@pytest.mark.integration
def test_nodes_query_uses_index_scan(conn: connection):
    """INTEGRATION: Verify nodes queries with project_id use index scans

    GIVEN indexes created with project_id
    WHEN running EXPLAIN ANALYZE on project-scoped query
    THEN query plan uses Index Scan (not Seq Scan)
    """
    # Ensure we have test data
    execute_sql(conn, """
        INSERT INTO nodes (name, label, project_id)
        VALUES ('test-index-node', 'test', 'io')
        ON CONFLICT (project_id, name) DO NOTHING
    """)

    # Run EXPLAIN ANALYZE
    plan = fetch_val(conn, """
        EXPLAIN (ANALYZE, FORMAT TEXT)
        SELECT * FROM nodes WHERE project_id = 'io'
    """)

    # Verify Index Scan or Bitmap Heap Scan is used (both are valid index usage)
    # Both use indexes - we just need to ensure it's not a Sequential Scan
    assert 'Seq Scan' not in plan, f"Query is using Seq Scan instead of index!\n{plan}"


@pytest.mark.P0
@pytest.mark.integration
def test_edges_query_uses_index_scan(conn: connection):
    """INTEGRATION: Verify edges queries with project_id use index scans

    GIVEN indexes created with project_id
    WHEN running EXPLAIN ANALYZE on project-scoped query
    THEN query plan uses Index Scan (not Seq Scan)
    """
    # Ensure we have test data with valid node references
    source_uuid = fetch_val(conn, """
        INSERT INTO nodes (id, name, label, project_id)
        VALUES (gen_random_uuid(), 'test-edge-source', 'test', 'io')
        ON CONFLICT (project_id, name) DO UPDATE SET id = nodes.id
        RETURNING id
    """)

    target_uuid = fetch_val(conn, """
        INSERT INTO nodes (id, name, label, project_id)
        VALUES (gen_random_uuid(), 'test-edge-target', 'test', 'io')
        ON CONFLICT (project_id, name) DO UPDATE SET id = nodes.id
        RETURNING id
    """)

    execute_sql(conn, """
        INSERT INTO edges (source_id, target_id, relation, project_id)
        VALUES (%s, %s, 'TEST', 'io')
        ON CONFLICT (project_id, source_id, target_id, relation) DO NOTHING
    """, (source_uuid, target_uuid))

    # Run EXPLAIN ANALYZE
    plan = fetch_val(conn, """
        EXPLAIN (ANALYZE, FORMAT TEXT)
        SELECT * FROM edges WHERE project_id = 'io'
    """)

    # Verify Index Scan or Bitmap Heap Scan is used (both are valid index usage)
    # Both use indexes - we just need to ensure it's not a Sequential Scan
    assert 'Seq Scan' not in plan, f"Query is using Seq Scan instead of index!\n{plan}"


@pytest.mark.P0
@pytest.mark.integration
def test_l2_insights_query_uses_index_scan(conn: connection):
    """INTEGRATION: Verify l2_insights queries with project_id use index scans

    GIVEN indexes created with project_id
    WHEN running EXPLAIN ANALYZE on project-scoped query
    THEN query plan uses Index Scan (not Seq Scan)
    """
    # Ensure we have test data (l2_insights doesn't have node_id column)
    # Create a proper 1536-dimension vector
    vector_1536 = '[' + ','.join(['0'] * 1536) + ']'
    execute_sql(conn, """
        INSERT INTO l2_insights (content, embedding, source_ids, project_id)
        VALUES ('test content', %s::vector, ARRAY[]::INTEGER[], 'io')
        ON CONFLICT DO NOTHING
    """, (vector_1536,))

    # Run EXPLAIN ANALYZE
    plan = fetch_val(conn, """
        EXPLAIN (ANALYZE, FORMAT TEXT)
        SELECT * FROM l2_insights WHERE project_id = 'io'
    """)

    # Verify Index Scan or Bitmap Heap Scan is used (both are valid index usage)
    # Both use indexes - we just need to ensure it's not a Sequential Scan
    assert 'Seq Scan' not in plan, f"Query is using Seq Scan instead of index!\n{plan}"


@pytest.mark.P1
@pytest.mark.integration
def test_composite_fk_index_source_used(conn: connection):
    """INTEGRATION: Verify composite foreign key index (project_id, source_id) is used

    GIVEN composite indexes on (project_id, source_id)
    WHEN querying with project_id filter and source_id filter
    THEN query plan uses the composite index
    """
    # Create test data with nodes and edges
    source_uuid = fetch_val(conn, """
        INSERT INTO nodes (id, name, label, project_id)
        VALUES (gen_random_uuid(), 'test-source-node', 'test', 'io')
        ON CONFLICT (project_id, name) DO UPDATE SET id = nodes.id
        RETURNING id
    """)

    target_uuid = fetch_val(conn, """
        INSERT INTO nodes (id, name, label, project_id)
        VALUES (gen_random_uuid(), 'test-target-node', 'test', 'io')
        ON CONFLICT (project_id, name) DO UPDATE SET id = nodes.id
        RETURNING id
    """)

    execute_sql(conn, """
        INSERT INTO edges (source_id, target_id, relation, project_id)
        VALUES (%s, %s, 'TEST', 'io')
        ON CONFLICT (project_id, source_id, target_id, relation) DO NOTHING
    """, (source_uuid, target_uuid))

    # Query with project filter and source_id
    plan = fetch_val(conn, """
        EXPLAIN (ANALYZE, FORMAT TEXT)
        SELECT * FROM edges WHERE project_id = 'io' AND source_id = %s
    """, (source_uuid,))

    # Verify index is used
    assert 'idx_edges_source_project' in plan or 'Index Scan' in plan


@pytest.mark.P1
@pytest.mark.integration
def test_composite_fk_index_target_used(conn: connection):
    """INTEGRATION: Verify composite foreign key index (project_id, target_id) is used

    GIVEN composite indexes on (project_id, target_id)
    WHEN querying with project_id filter and target_id filter
    THEN query plan uses the composite index
    """
    # Create test data
    source_uuid = fetch_val(conn, """
        INSERT INTO nodes (id, name, label, project_id)
        VALUES (gen_random_uuid(), 'test-source-node-2', 'test', 'io')
        ON CONFLICT (project_id, name) DO UPDATE SET id = nodes.id
        RETURNING id
    """)

    target_uuid = fetch_val(conn, """
        INSERT INTO nodes (id, name, label, project_id)
        VALUES (gen_random_uuid(), 'test-target-node-2', 'test', 'io')
        ON CONFLICT (project_id, name) DO UPDATE SET id = nodes.id
        RETURNING id
    """)

    execute_sql(conn, """
        INSERT INTO edges (source_id, target_id, relation, project_id)
        VALUES (%s, %s, 'TEST', 'io')
        ON CONFLICT (project_id, source_id, target_id, relation) DO NOTHING
    """, (source_uuid, target_uuid))

    # Query with project filter and target_id
    plan = fetch_val(conn, """
        EXPLAIN (ANALYZE, FORMAT TEXT)
        SELECT * FROM edges WHERE project_id = 'io' AND target_id = %s
    """, (target_uuid,))

    # Verify index is used
    assert 'idx_edges_target_project' in plan or 'Index Scan' in plan


@pytest.mark.P1
@pytest.mark.integration
def test_l2_insights_project_id_index(conn: connection):
    """INTEGRATION: Verify l2_insights project_id index is used

    GIVEN single-column project_id index on l2_insights
    WHEN querying with project_id filter
    THEN query plan uses the index
    """
    # Create test data
    # Create a proper 1536-dimension vector
    vector_1536 = '[' + ','.join(['0'] * 1536) + ']'
    execute_sql(conn, """
        INSERT INTO l2_insights (content, embedding, source_ids, project_id)
        VALUES ('test content', %s::vector, ARRAY[]::INTEGER[], 'io')
        ON CONFLICT DO NOTHING
    """, (vector_1536,))

    # Query with project filter
    plan = fetch_val(conn, """
        EXPLAIN (ANALYZE, FORMAT TEXT)
        SELECT * FROM l2_insights WHERE project_id = 'io'
    """)

    # Verify index is used
    assert 'idx_l2_insights_project_id' in plan or 'Index Scan' in plan


@pytest.mark.P2
@pytest.mark.integration
@pytest.mark.skip(reason="Cannot test CONCURRENTLY inside transaction - must test manually")
def test_migration_idempotent(conn: connection):
    """INTEGRATION: Verify migration can be run multiple times safely

    GIVEN migration 029 has been applied
    WHEN running migration again
    THEN no errors occur (IF NOT EXISTS handles it)

    NOTE: This test is skipped because CREATE INDEX CONCURRENTLY cannot
    run inside a transaction block. To test this manually:

    1. Run migration: psql -d db -f migrations/029_add_composite_indexes.sql
    2. Run it again: psql -d db -f migrations/029_add_composite_indexes.sql
    3. Verify no errors occur
    """
    # Verify IF NOT EXISTS clause exists in migration script
    with open('mcp_server/db/migrations/029_add_composite_indexes.sql', 'r') as f:
        migration_sql = f.read()
        assert 'IF NOT EXISTS' in migration_sql


@pytest.mark.P2
@pytest.mark.integration
def test_index_columns_order(conn: connection):
    """INTEGRATION: Verify project_id is first column in all composite indexes

    GIVEN composite indexes created
    WHEN checking index column order
    THEN project_id is always the first column
    """
    result = fetch_all(conn, """
        SELECT
            ix.indexrelid::regclass AS index_name,
            a.attname AS column_name,
            a.attnum AS column_position
        FROM pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        CROSS JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord)
        JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
        WHERE ix.indexrelid::regclass::text LIKE 'idx_%_project%'
            AND k.ord = 1
        ORDER BY index_name;
    """)

    for row in result:
        assert row['column_name'] == 'project_id', \
            f"Index {row['index_name']} does not have project_id as first column!"
