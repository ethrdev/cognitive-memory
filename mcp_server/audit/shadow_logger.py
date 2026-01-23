"""
Shadow Audit Logger Module

Provides shadow audit logging for RLS violation detection during shadow mode.
Logs cross-project data access violations without blocking responses.

Story 11.3.2: Shadow Audit Infrastructure
Application-Layer SELECT Audit (Python)
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)


class ShadowAuditLogger:
    """
    Shadow audit logger for detecting RLS violations during shadow mode.

    This class analyzes query results for cross-project data access and logs
    violations to rls_audit_log table without blocking the response.

    Key Features:
        - Async fire-and-forget logging (non-blocking)
        - Cross-project detection by comparing result.project_id with session
        - Only logs when get_rls_mode() = 'shadow'
        - Graceful error handling (never blocks response)

    Example:
        logger = ShadowAuditLogger()
        await logger.log_select_violations(results, project_id="aa")
    """

    async def log_select_violations(
        self,
        results: list[dict[str, Any]],
        project_id: str
    ) -> None:
        """
        Analyze and log SELECT violations for cross-project data access.

        Cross-project violations are detected when a result row contains
        a project_id different from the requesting project_id.

        Logging is async and fire-and-forget - does not block response.
        Errors are logged to stderr but never raised.

        Args:
            results: List of result dicts from SELECT operations
            project_id: The requesting project's session project_id

        Returns:
            None (fire-and-forget pattern)

        Story 11.3.2: Application-Layer SELECT Audit (AC: #5, #7)
        """
        # Check if we're in shadow mode before processing
        is_shadow = await self._check_shadow_mode()
        if not is_shadow:
            # Not in shadow mode - skip audit
            logger.debug("Skipping SELECT audit: not in shadow mode")
            return

        # Detect cross-project violations
        violations = self._detect_cross_project_violations(results, project_id)
        if not violations:
            # No violations found
            return

        # Log violations asynchronously (fire-and-forget)
        # Use asyncio.create_task() for true non-blocking execution
        asyncio.create_task(
            self._log_violations_async(violations, project_id)
        )

    async def _check_shadow_mode(self) -> bool:
        """
        Check if the current project is in shadow RLS mode.

        Returns:
            True if get_rls_mode() = 'shadow', False otherwise

        Raises:
            Never - errors return False (graceful degradation)
        """
        try:
            async with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT get_rls_mode() AS rls_mode")
                row = cursor.fetchone()
                if row:
                    return row.get("rls_mode") == "shadow"
                return False
        except Exception as e:
            # Never block response on shadow mode check errors
            logger.warning("Failed to check shadow mode", extra={"error": str(e)})
            return False

    def _detect_cross_project_violations(
        self,
        results: list[dict[str, Any]],
        project_id: str
    ) -> list[dict[str, Any]]:
        """
        Detect cross-project violations in query results.

        A violation occurs when a result row contains a project_id
        different from the requesting project_id.

        Args:
            results: List of result dicts from SELECT operations
            project_id: The requesting project's session project_id

        Returns:
            List of result dicts that are cross-project violations

        Story 11.3.2: Cross-project detection (AC: #5)
        """
        violations = []

        for result in results:
            # Check if result has project_id field
            result_project_id = result.get("project_id")
            if not result_project_id:
                # No project_id in result - skip
                continue

            # Check for cross-project access
            if str(result_project_id) != str(project_id):
                violations.append(result)

        return violations

    async def _log_violations_async(
        self,
        violations: list[dict[str, Any]],
        project_id: str
    ) -> None:
        """
        Async fire-and-forget logging of violations to rls_audit_log.

        This method runs as a background task and does not block the response.
        Errors are logged to stderr but never raised to the caller.

        Args:
            violations: List of result dicts that are cross-project violations
            project_id: The requesting project's session project_id

        Returns:
            None (fire-and-forget pattern)

        Story 11.3.2: Async logging doesn't block response (AC: #7)
        """
        if not violations:
            return

        try:
            async with get_connection() as conn:
                cursor = conn.cursor()

                # Bulk insert violations using executemany for better performance
                # Prepare data tuples: (project_id, row_project_id, violation_json)
                insert_data = [
                    (
                        project_id,
                        str(v.get("project_id", "unknown")),
                        json.dumps(v),  # Must serialize dict to JSON string for psycopg2
                    )
                    for v in violations
                ]

                cursor.executemany(
                    """
                    INSERT INTO rls_audit_log (
                        project_id,
                        table_name,
                        operation,
                        row_project_id,
                        would_be_denied,
                        old_data,
                        new_data,
                        session_user
                    ) VALUES (
                        %s,
                        'application_layer',
                        'SELECT',
                        %s,
                        TRUE,
                        NULL,
                        %s::jsonb,
                        current_user
                    )
                    """,
                    insert_data,
                )

                conn.commit()
                logger.info(
                    "Logged shadow audit SELECT violations",
                    extra={
                        "project_id": project_id,
                        "violation_count": len(violations),
                    }
                )

        except Exception as e:
            # CRITICAL: Never raise - this is fire-and-forget logging
            # Log to stderr so violations aren't silently lost
            logger.error(
                "Failed to log shadow audit violations (non-blocking)",
                extra={
                    "project_id": project_id,
                    "violation_count": len(violations),
                    "error": str(e),
                },
            )
