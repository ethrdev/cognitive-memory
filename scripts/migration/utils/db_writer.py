"""Database Writer for Migration Scripts."""

import json
import os
from contextlib import contextmanager
from datetime import date, datetime

import psycopg2
from psycopg2.extras import execute_values


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime and date objects."""

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def get_db_url() -> str:
    """Get database URL from environment."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set")
    return db_url


@contextmanager
def get_db_connection():
    """Get database connection as context manager."""
    conn = psycopg2.connect(get_db_url())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def truncate_tables(tables: list[str], dry_run: bool = True):
    """Truncate specified tables (with CASCADE).

    Args:
        tables: List of table names to truncate
        dry_run: If True, only print what would be done
    """
    if dry_run:
        print(f"[DRY RUN] Would truncate tables: {', '.join(tables)}")
        return

    with get_db_connection() as conn:
        cur = conn.cursor()
        for table in tables:
            cur.execute(f"TRUNCATE TABLE {table} CASCADE")
            print(f"Truncated table: {table}")


def write_l0_raw(
    session_id: str,
    timestamp: datetime,
    speaker: str,
    content: str,
    metadata: dict,
    dry_run: bool = True,
) -> int | None:
    """Write a single row to l0_raw table.

    Returns the inserted row ID, or None in dry_run mode.
    """
    if dry_run:
        print(
            f"[DRY RUN] l0_raw: session={session_id}, speaker={speaker}, "
            f"content_len={len(content)}"
        )
        return None

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO l0_raw (session_id, timestamp, speaker, content, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                session_id,
                timestamp,
                speaker,
                content,
                json.dumps(metadata, cls=DateTimeEncoder),
            ),
        )
        return cur.fetchone()[0]


def write_l0_raw_batch(rows: list[tuple], dry_run: bool = True) -> int:
    """Write multiple rows to l0_raw table.

    Args:
        rows: List of (session_id, timestamp, speaker, content, metadata_dict) tuples
        dry_run: If True, only print what would be done

    Returns:
        Number of rows inserted
    """
    if dry_run:
        print(f"[DRY RUN] Would insert {len(rows)} rows into l0_raw")
        return len(rows)

    with get_db_connection() as conn:
        cur = conn.cursor()

        # Convert metadata dicts to JSON strings
        prepared_rows = [
            (session_id, ts, speaker, content, json.dumps(meta, cls=DateTimeEncoder))
            for session_id, ts, speaker, content, meta in rows
        ]

        execute_values(
            cur,
            """
            INSERT INTO l0_raw (session_id, timestamp, speaker, content, metadata)
            VALUES %s
            """,
            prepared_rows,
            template="(%s, %s, %s, %s, %s)",
        )

        return len(rows)


def write_l2_insight(
    content: str,
    embedding: list[float],
    source_ids: list[int],
    metadata: dict,
    dry_run: bool = True,
) -> int | None:
    """Write a single row to l2_insights table.

    Returns the inserted row ID, or None in dry_run mode.
    """
    if dry_run:
        print(
            f"[DRY RUN] l2_insights: content_len={len(content)}, "
            f"has_embedding={len(embedding) > 0}, sources={len(source_ids)}"
        )
        return None

    with get_db_connection() as conn:
        cur = conn.cursor()

        # Convert embedding to pgvector format
        embedding_str = f"[{','.join(map(str, embedding))}]"

        cur.execute(
            """
            INSERT INTO l2_insights (content, embedding, source_ids, metadata)
            VALUES (%s, %s::vector, %s, %s)
            RETURNING id
            """,
            (
                content,
                embedding_str,
                source_ids,
                json.dumps(metadata, cls=DateTimeEncoder),
            ),
        )
        return cur.fetchone()[0]


def write_l2_insights_batch(rows: list[tuple], dry_run: bool = True) -> int:
    """Write multiple rows to l2_insights table.

    Args:
        rows: List of (content, embedding, source_ids, metadata_dict) tuples
        dry_run: If True, only print what would be done

    Returns:
        Number of rows inserted
    """
    if dry_run:
        print(f"[DRY RUN] Would insert {len(rows)} rows into l2_insights")
        return len(rows)

    with get_db_connection() as conn:
        cur = conn.cursor()

        inserted = 0
        for content, embedding, source_ids, metadata in rows:
            # Convert embedding to pgvector format
            embedding_str = f"[{','.join(map(str, embedding))}]"

            cur.execute(
                """
                INSERT INTO l2_insights (content, embedding, source_ids, metadata)
                VALUES (%s, %s::vector, %s, %s)
                """,
                (
                    content,
                    embedding_str,
                    source_ids,
                    json.dumps(metadata, cls=DateTimeEncoder),
                ),
            )
            inserted += 1

        return inserted


def get_row_counts() -> dict[str, int]:
    """Get current row counts for all tables."""
    tables = [
        "l0_raw",
        "l2_insights",
        "working_memory",
        "episode_memory",
        "ground_truth",
    ]

    with get_db_connection() as conn:
        cur = conn.cursor()
        counts = {}

        for table in tables:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cur.fetchone()[0]

        return counts


def verify_embeddings(table: str = "l2_insights", expected_dim: int = 1536) -> dict:
    """Verify embedding dimensions in a table."""
    with get_db_connection() as conn:
        cur = conn.cursor()

        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]

        cur.execute(
            f"SELECT COUNT(*) FROM {table} WHERE vector_dims(embedding) = %s",
            (expected_dim,),
        )
        valid = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM {table} WHERE embedding IS NULL")
        null_embeddings = cur.fetchone()[0]

        return {
            "total": total,
            "valid_dimensions": valid,
            "null_embeddings": null_embeddings,
            "invalid": total - valid - null_embeddings,
        }
