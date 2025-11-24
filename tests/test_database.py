#!/usr/bin/env python3
"""
Database Connection and Schema Test for Cognitive Memory System
 - PostgreSQL + pgvector Setup

This script validates:
1. PostgreSQL connection with .env credentials
2. pgvector extension availability
3. Schema migration success
4. WRITE operations on l0_raw table
5. Vector operations on l2_insights table
"""

import os
import sys
import uuid

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
    """Create PostgreSQL connection using environment variables."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
        )
        print("✅ PostgreSQL connection established")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        sys.exit(1)


def test_basic_query(conn: connection) -> None:
    """Test basic database connectivity."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        assert result[0] == 1, "Basic query test failed"
        print("✅ Basic Query Test successful")
        cur.close()
    except Exception as e:
        print(f"❌ Basic Query Test failed: {e}")
        sys.exit(1)


def test_pgvector_extension(conn: connection) -> None:
    """Test pgvector extension availability."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM pg_extension WHERE extname='vector';")
        result = cur.fetchall()
        assert (
            len(result) == 1
        ), f"pgvector extension not found. Found {len(result)} extensions"
        print("✅ pgvector Extension available")
        cur.close()
    except Exception as e:
        print(f"❌ pgvector Extension Test failed: {e}")
        sys.exit(1)


def test_schema_tables(conn: connection) -> None:
    """Test that all required tables exist."""
    required_tables = [
        "l0_raw",
        "l2_insights",
        "working_memory",
        "episode_memory",
        "stale_memory",
        "ground_truth",
    ]

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname='public' AND tablename IN %s
        """,
            (tuple(required_tables),),
        )

        existing_tables = [row[0] for row in cur.fetchall()]
        missing_tables = set(required_tables) - set(existing_tables)

        assert not missing_tables, f"Missing tables: {missing_tables}"
        assert (
            len(existing_tables) == 6
        ), f"Expected 6 tables, found {len(existing_tables)}"
        print(
            f"✅ Schema Validation successful - all {len(existing_tables)} tables present"
        )
        cur.close()
    except Exception as e:
        print(f"❌ Schema Validation Test failed: {e}")
        sys.exit(1)


def test_write_operations(conn: connection) -> None:
    """Test INSERT and DELETE operations on l0_raw table."""
    test_session_id: str | None = None

    try:
        cur = conn.cursor()

        # Generate test UUID
        test_session_id = str(uuid.uuid4())

        # INSERT test data
        cur.execute(
            "INSERT INTO l0_raw (session_id, speaker, content) VALUES (%s, %s, %s)",
            (test_session_id, "test", "test content"),
        )
        conn.commit()

        # Verify INSERT
        cur.execute("SELECT count(*) FROM l0_raw WHERE speaker='test'")
        count = cur.fetchone()[0]
        assert count == 1, f"Expected 1 test row, found {count}"
        print("✅ WRITE Test (INSERT) successful")

        # DELETE test data
        cur.execute("DELETE FROM l0_raw WHERE speaker='test'")
        conn.commit()

        # Verify DELETE
        cur.execute("SELECT count(*) FROM l0_raw WHERE speaker='test'")
        count = cur.fetchone()[0]
        assert count == 0, f"Expected 0 test rows after delete, found {count}"
        print("✅ WRITE Test (DELETE) successful")

        cur.close()
    except Exception as e:
        print(f"❌ WRITE Test failed: {e}")
        # Try to cleanup on error
        if test_session_id:
            try:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM l0_raw WHERE session_id = %s", (test_session_id,)
                )
                conn.commit()
                cur.close()
            except:
                pass
        sys.exit(1)


def test_vector_operations(conn: connection) -> None:
    """Test vector operations on l2_insights table."""
    try:
        cur = conn.cursor()

        # Create dummy vector (1536 dimensions with value 0.1)
        dummy_vector = [0.1] * 1536

        # INSERT test vector data
        cur.execute(
            "INSERT INTO l2_insights (content, embedding, source_ids) VALUES (%s, %s, %s)",
            ("test", dummy_vector, [1]),
        )
        conn.commit()

        # Test Cosine Similarity Query
        cur.execute(
            """
            SELECT content, embedding <=> %s::vector AS distance
            FROM l2_insights
            ORDER BY embedding <=> %s::vector
            LIMIT 1
        """,
            (dummy_vector, dummy_vector),
        )

        result = cur.fetchone()
        assert result[0] == "test", f"Expected 'test' content, got {result[0]}"
        assert result[1] < 0.01, f"Expected distance ~0, got {result[1]}"
        print("✅ Vector-Operation Test (Cosine Similarity) successful")

        # Cleanup test data
        cur.execute("DELETE FROM l2_insights WHERE content='test'")
        conn.commit()

        cur.close()
    except Exception as e:
        print(f"❌ Vector-Operation Test failed: {e}")
        # Try to cleanup on error
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM l2_insights WHERE content='test'")
            conn.commit()
            cur.close()
        except:
            pass
        sys.exit(1)


def test_indexes(conn: connection) -> None:
    """Test that non-IVFFlat indexes are created."""
    expected_indexes = ["idx_l0_session", "idx_l2_fts", "idx_wm_lru"]

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname='public' AND indexname IN %s
        """,
            (tuple(expected_indexes),),
        )

        existing_indexes = [row[0] for row in cur.fetchall()]
        missing_indexes = set(expected_indexes) - set(existing_indexes)

        assert not missing_indexes, f"Missing indexes: {missing_indexes}"
        assert (
            len(existing_indexes) == 3
        ), f"Expected 3 indexes, found {len(existing_indexes)}"
        print(
            f"✅ Index Validation successful - {len(existing_indexes)} indexes present (IVFFlat not built yet)"
        )
        cur.close()
    except Exception as e:
        print(f"❌ Index Validation Test failed: {e}")
        sys.exit(1)


def main() -> None:
    """Run all database tests."""
    print("🚀 Starting PostgreSQL + pgvector Tests")
    print("=" * 50)

    # Load environment
    load_environment()

    # Get connection
    conn = get_connection()

    try:
        # Run all tests
        test_basic_query(conn)
        test_pgvector_extension(conn)
        test_schema_tables(conn)
        test_indexes(conn)
        test_write_operations(conn)
        test_vector_operations(conn)

        print("=" * 50)
        print("🎉 Alle PostgreSQL + pgvector Tests erfolgreich!")
        print("✅  Acceptance Criteria 4 vollständig validiert")

    finally:
        conn.close()
        print("✅ Database connection closed")


if __name__ == "__main__":
    main()
