"""
L2 Insights Database Operations Module

Provides database functions for retrieving and updating L2 insights by ID.

Story 6.5: get_insight_by_id MCP Tool
Story 26.2: UPDATE Operation - update_insight, write_insight_history
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server.db.connection import get_connection_with_project_context

logger = logging.getLogger(__name__)


async def get_insight_by_id(insight_id: int) -> dict[str, Any] | None:
    """
    Get an L2 insight by its ID.

    Args:
        insight_id: The ID of the insight to retrieve

    Returns:
        Dict with insight data (id, content, source_ids, metadata, created_at)
        if found, None if not found.
        Note: embedding is NOT returned (too large for response).

    Raises:
        Exception: If database operation fails
    """
    try:
        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()

            # Simple SELECT by ID - no embedding (too large)
            # Filter out soft-deleted insights (is_deleted = FALSE)
            # Consistent with execute_update_with_history behavior
            cursor.execute(
                """
                SELECT id, content, source_ids, metadata, created_at, memory_strength
                FROM l2_insights
                WHERE id = %s AND is_deleted = FALSE
                """,
                (insight_id,),
            )

            row = cursor.fetchone()

            if row is None:
                logger.debug(f"Insight not found: id={insight_id}")
                return None

            # Convert to dict with ISO 8601 datetime
            result = {
                "id": row["id"],
                "content": row["content"],
                "source_ids": row["source_ids"],
                "metadata": row["metadata"] or {},  # NULL -> empty dict
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "memory_strength": row.get("memory_strength", 0.5),  # Story 26.1 field
            }

            logger.debug(f"Retrieved insight: id={insight_id}")
            return result

    except Exception as e:
        logger.error(f"Failed to get insight by id: {e}")
        raise


async def update_insight_in_db(
    insight_id: int,
    new_content: str | None = None,
    new_memory_strength: float | None = None
) -> dict[str, Any]:
    """
    Update an L2 insight in the database (without history).

    EP-3: History-on-Mutation Pattern - This is the mutation part.
    History should be written BEFORE calling this function (in same transaction).

    Args:
        insight_id: The ID of the insight to update
        new_content: New content for the insight (optional)
        new_memory_strength: New memory strength (optional, 0.0-1.0)

    Returns:
        Dict with success status and updated fields

    Raises:
        ValueError: If insight_id not found or is_deleted=TRUE
        Exception: If database operation fails
    """
    try:
        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()

            # Check if insight exists and is not deleted (AC-6, AC-7)
            cursor.execute(
                """
                SELECT id, content, memory_strength
                FROM l2_insights
                WHERE id = %s AND is_deleted = FALSE
                """,
                (insight_id,),
            )

            row = cursor.fetchone()
            if row is None:
                raise ValueError(f"Insight {insight_id} not found")

            # Build UPDATE fields
            update_fields = []
            params = []  # Don't include insight_id here anymore

            if new_content is not None:
                update_fields.append("content = %s")
                params.append(new_content)

            if new_memory_strength is not None:
                update_fields.append("memory_strength = %s")
                params.append(new_memory_strength)

            if not update_fields:
                # AC-4: No changes provided
                raise ValueError("no changes provided")

            # Execute update (insight_id is last parameter)
            set_clause = ', '.join(update_fields)
            update_query = f"UPDATE l2_insights SET {set_clause} WHERE id = %s"
            cursor.execute(update_query, params + [insight_id])

            conn.commit()
            cursor.close()

            logger.info(f"Updated insight: id={insight_id}, fields={update_fields}")
            return {
                "success": True,
                "insight_id": insight_id,
                "updated_fields": {
                    "content": new_content is not None,
                    "memory_strength": new_memory_strength is not None
                }
            }

    except ValueError:
        # Re-raise validation errors (AC-6, AC-7)
        raise
    except Exception as e:
        logger.error(f"Failed to update insight: {e}")
        raise


async def write_insight_history(
    insight_id: int,
    action: str,
    actor: str,
    old_content: str,
    new_content: str | None,
    old_memory_strength: float | None,
    new_memory_strength: float | None,
    reason: str
) -> int:
    """
    Write a history entry for an insight mutation (EP-3).

    EP-3: History-on-Mutation Pattern - This should be called BEFORE the mutation,
    in the SAME transaction as the update.

    Args:
        insight_id: The ID of the insight being mutated
        action: "UPDATE" or "DELETE"
        actor: "I/O" or "ethr"
        old_content: Previous content (for rollback)
        new_content: New content (None for DELETE)
        old_memory_strength: Previous memory strength
        new_memory_strength: New memory strength
        reason: Reason for the mutation (required)

    Returns:
        history_id: The ID of the created history entry

    Raises:
        Exception: If database operation fails
    """
    try:
        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()

            # Insert history entry
            cursor.execute(
                """
                INSERT INTO l2_insight_history
                (insight_id, action, actor, old_content, new_content,
                 old_memory_strength, new_memory_strength, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (insight_id, action, actor, old_content, new_content,
                 old_memory_strength, new_memory_strength, reason),
            )

            row = cursor.fetchone()
            history_id = row[0] if row else None

            conn.commit()
            cursor.close()

            logger.info(f"Wrote history: insight_id={insight_id}, action={action}, history_id={history_id}")
            return history_id

    except Exception as e:
        logger.error(f"Failed to write insight history: {e}")
        raise


async def execute_update_with_history(
    insight_id: int,
    new_content: str | None = None,
    new_memory_strength: float | None = None,
    actor: str = "I/O",
    reason: str = ""
) -> dict[str, Any]:
    """
    Execute an insight update with atomic history write (EP-3).

    This combines the update and history write in a SINGLE transaction.
    If the update fails, the history is rolled back too (atomic).

    Args:
        insight_id: The ID of the insight to update
        new_content: New content (optional)
        new_memory_strength: New memory strength (optional)
        actor: Who is making the change ("I/O" or "ethr")
        reason: Reason for the change (required for audit)

    Returns:
        Dict with success status, insight_id, history_id, updated_fields

    Raises:
        ValueError: If validation fails (not found, no changes, empty content)
        Exception: If database operation fails
    """
    # AC-3: Reason required
    if not reason:
        raise ValueError("reason required")

    # AC-4: Changes required
    if new_content is None and new_memory_strength is None:
        raise ValueError("no changes provided")

    # AC-4: Empty content check
    if new_content is not None and len(new_content.strip()) == 0:
        raise ValueError("new_content cannot be empty")

    try:
        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()

            # Start transaction
            cursor.execute("BEGIN")

            try:
                # Get current state (for history)
                cursor.execute(
                    """
                    SELECT content, memory_strength
                    FROM l2_insights
                    WHERE id = %s AND is_deleted = FALSE
                    """,
                    (insight_id,),
                )

                row = cursor.fetchone()
                if row is None:
                    raise ValueError(f"Insight {insight_id} not found")

                old_content = row["content"]
                old_memory_strength = row.get("memory_strength", 0.5)

                # Step 1: Write history FIRST (EP-3)
                cursor.execute(
                    """
                    INSERT INTO l2_insight_history
                    (insight_id, action, actor, old_content, new_content,
                     old_memory_strength, new_memory_strength, reason)
                    VALUES (%s, 'UPDATE', %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (insight_id, actor, old_content, new_content,
                     old_memory_strength, new_memory_strength, reason),
                )

                history_row = cursor.fetchone()
                history_id = history_row[0] if history_row else None

                # Build UPDATE fields
                update_fields = []
                params = []  # Don't include insight_id here anymore

                if new_content is not None:
                    update_fields.append("content = %s")
                    params.append(new_content)

                if new_memory_strength is not None:
                    update_fields.append("memory_strength = %s")
                    params.append(new_memory_strength)

                # Execute update (insight_id is last parameter)
                set_clause = ', '.join(update_fields)
                update_query = f"UPDATE l2_insights SET {set_clause} WHERE id = %s"
                cursor.execute(update_query, params + [insight_id])

                # Commit transaction
                cursor.execute("COMMIT")
                conn.commit()

                logger.info(f"Executed update with history: insight_id={insight_id}, history_id={history_id}")
                return {
                    "success": True,
                    "insight_id": insight_id,
                    "history_id": history_id,
                    "updated_fields": {
                        "content": new_content is not None,
                        "memory_strength": new_memory_strength is not None
                    }
                }

            except Exception as e:
                # Rollback on any error
                cursor.execute("ROLLBACK")
                raise

            finally:
                cursor.close()

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Failed to execute update with history: {e}")
        raise


async def execute_delete_with_history(
    insight_id: int,
    actor: str = "I/O",
    reason: str = ""
) -> dict[str, Any]:
    """
    Execute an insight soft-delete with atomic history write (EP-3).

    This combines the soft-delete and history write in a SINGLE transaction.
    If either operation fails, both are rolled back (atomic).

    Args:
        insight_id: The ID of the insight to soft-delete
        actor: Who is making the change ("I/O" or "ethr")
        reason: Reason for the deletion (required for audit)

    Returns:
        Dict with success status, insight_id, history_id, deletion info

    Raises:
        ValueError: If validation fails (not found, already deleted, no reason)
        Exception: If database operation fails
    """
    # AC-6: Reason required
    if not reason:
        raise ValueError("reason required")

    try:
        async with get_connection_with_project_context() as conn:
            cursor = conn.cursor()

            # Start transaction
            cursor.execute("BEGIN")

            try:
                # Step 1: Get current state (for history)
                cursor.execute(
                    """
                    SELECT content, memory_strength, is_deleted
                    FROM l2_insights
                    WHERE id = %s
                    """,
                    (insight_id,),
                )

                row = cursor.fetchone()
                if row is None:
                    raise ValueError(f"Insight {insight_id} not found")

                if row["is_deleted"]:
                    raise ValueError("already deleted")

                old_content = row["content"]
                old_memory_strength = row.get("memory_strength", 0.5)

                # Step 2: Write history FIRST (EP-3)
                cursor.execute(
                    """
                    INSERT INTO l2_insight_history
                    (insight_id, action, actor, old_content, new_content,
                     old_memory_strength, new_memory_strength, reason)
                    VALUES (%s, 'DELETE', %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (insight_id, actor, old_content, None,
                     old_memory_strength, None, reason),
                )

                history_row = cursor.fetchone()
                history_id = history_row[0] if history_row else None

                # Step 3: Execute soft-delete (EP-2)
                cursor.execute(
                    """
                    UPDATE l2_insights
                    SET is_deleted = TRUE,
                        deleted_at = NOW(),
                        deleted_by = %s,
                        deleted_reason = %s
                    WHERE id = %s
                    """,
                    (actor, reason, insight_id),
                )

                # Commit transaction
                cursor.execute("COMMIT")
                conn.commit()

                logger.info(f"Executed soft-delete with history: insight_id={insight_id}, history_id={history_id}")
                return {
                    "success": True,
                    "insight_id": insight_id,
                    "history_id": history_id,
                    "status": "deleted",
                    "recoverable": True
                }

            except Exception as e:
                # Rollback on any error
                cursor.execute("ROLLBACK")
                raise

            finally:
                cursor.close()

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        logger.error(f"Failed to execute delete with history: {e}")
        raise

