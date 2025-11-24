"""
Fallback Status Logger

Centralized logging utilities for fallback mode activation and recovery events.
Writes to fallback_status_log table for observability and degraded mode monitoring.

Story 3.4: Claude Code Fallback für Haiku API Ausfall (Degraded Mode)
"""

import json
import logging
from typing import Any, Dict, List, Optional

from mcp_server.db.connection import get_connection

logger = logging.getLogger(__name__)

# =============================================================================
# Public Interface
# =============================================================================


async def log_fallback_activation(
    service_name: str,
    reason: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log fallback mode activation to database.

    Inserts a record with status='active' indicating the service has entered
    degraded mode (external API unavailable, using Claude Code fallback).

    Args:
        service_name: Service identifier ('haiku_evaluation' | 'haiku_reflexion')
        reason: Reason for activation (e.g., 'haiku_api_unavailable')
        metadata: Additional context as dict (error_message, retry_count, etc.)

    Example:
        >>> await log_fallback_activation(
        ...     'haiku_evaluation',
        ...     'haiku_api_unavailable',
        ...     {'error_message': 'HTTP 503', 'retry_count': 4}
        ... )
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Convert metadata to JSONB
            metadata_json = json.dumps(metadata) if metadata else None

            cursor.execute(
                """
                INSERT INTO fallback_status_log
                (service_name, status, reason, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (service_name, "active", reason, metadata_json),
            )

            conn.commit()
            cursor.close()

            logger.warning(
                f"Fallback activated: service={service_name}, reason={reason}, "
                f"metadata={metadata}"
            )

    except Exception as e:
        # Graceful degradation: Log error but don't break the calling code
        logger.error(
            f"Failed to log fallback activation for {service_name}: {e}",
            exc_info=True,
        )
        # Don't re-raise - fallback logging failures should not break API calls


async def log_fallback_recovery(
    service_name: str,
    recovery_method: str = "health_check_success",
) -> None:
    """
    Log fallback mode recovery to database (normal operation restored).

    Inserts a record with status='recovered' indicating the external API is
    available again and degraded mode has been deactivated.

    Args:
        service_name: Service identifier ('haiku_evaluation' | 'haiku_reflexion')
        recovery_method: How recovery occurred ('health_check_success' | 'manual_recovery')

    Example:
        >>> await log_fallback_recovery('haiku_evaluation', 'health_check_success')
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Include recovery method in metadata
            metadata = json.dumps({"recovery_method": recovery_method})

            cursor.execute(
                """
                INSERT INTO fallback_status_log
                (service_name, status, reason, metadata)
                VALUES (%s, %s, %s, %s)
                """,
                (service_name, "recovered", "api_recovered", metadata),
            )

            conn.commit()
            cursor.close()

            logger.info(
                f"Fallback recovered: service={service_name}, "
                f"recovery_method={recovery_method}"
            )

    except Exception as e:
        # Graceful degradation: Log error but don't break the calling code
        logger.error(
            f"Failed to log fallback recovery for {service_name}: {e}",
            exc_info=True,
        )
        # Don't re-raise - fallback logging failures should not break API calls


async def get_current_fallback_status() -> List[Dict[str, Any]]:
    """
    Query active fallbacks from database.

    Returns the most recent status for each service. If a service's most recent
    event is 'active', it's currently in fallback mode.

    Returns:
        List of dicts with service fallback status:
        [
            {
                'service_name': 'haiku_evaluation',
                'status': 'active',
                'timestamp': '2025-11-18T10:30:00+00:00',
                'reason': 'haiku_api_unavailable',
                'metadata': {...}
            }
        ]

    Example:
        >>> statuses = await get_current_fallback_status()
        >>> for s in statuses:
        ...     print(f"{s['service_name']}: {s['status']}")
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Get most recent status for each service
            cursor.execute(
                """
                WITH latest_events AS (
                    SELECT service_name,
                           status,
                           timestamp,
                           reason,
                           metadata,
                           ROW_NUMBER() OVER (
                               PARTITION BY service_name
                               ORDER BY timestamp DESC
                           ) as rn
                    FROM fallback_status_log
                )
                SELECT service_name, status, timestamp, reason, metadata
                FROM latest_events
                WHERE rn = 1
                ORDER BY service_name
                """
            )

            results = cursor.fetchall()
            cursor.close()

            # Convert DictRow to regular dicts
            statuses = []
            for row in results:
                status_dict = {
                    "service_name": row["service_name"],
                    "status": row["status"],
                    "timestamp": row["timestamp"].isoformat(),
                    "reason": row["reason"],
                    "metadata": row["metadata"],  # Already parsed by psycopg2 JSONB
                }
                statuses.append(status_dict)

            return statuses

    except Exception as e:
        logger.error(f"Failed to query current fallback status: {e}", exc_info=True)
        return []


async def get_active_fallbacks() -> List[str]:
    """
    Get list of services currently in fallback mode.

    Returns:
        List of service names currently in 'active' status (degraded mode)
        Example: ['haiku_evaluation']

    Example:
        >>> active = await get_active_fallbacks()
        >>> if 'haiku_evaluation' in active:
        ...     print("⚠️ Haiku evaluation in degraded mode")
    """
    try:
        all_statuses = await get_current_fallback_status()
        active_services = [
            s["service_name"] for s in all_statuses if s["status"] == "active"
        ]
        return active_services

    except Exception as e:
        logger.error(f"Failed to get active fallbacks: {e}", exc_info=True)
        return []


async def get_fallback_history(
    service_name: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Query fallback event history from database.

    Args:
        service_name: Optional filter by service (None = all services)
        limit: Maximum number of events to return (default 50)

    Returns:
        List of fallback events in reverse chronological order (most recent first)

    Example:
        >>> history = await get_fallback_history('haiku_evaluation', limit=10)
        >>> for event in history:
        ...     print(f"{event['timestamp']}: {event['status']} - {event['reason']}")
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            if service_name:
                cursor.execute(
                    """
                    SELECT service_name, status, timestamp, reason, metadata
                    FROM fallback_status_log
                    WHERE service_name = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (service_name, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT service_name, status, timestamp, reason, metadata
                    FROM fallback_status_log
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (limit,),
                )

            results = cursor.fetchall()
            cursor.close()

            # Convert DictRow to regular dicts
            history = []
            for row in results:
                event_dict = {
                    "service_name": row["service_name"],
                    "status": row["status"],
                    "timestamp": row["timestamp"].isoformat(),
                    "reason": row["reason"],
                    "metadata": row["metadata"],
                }
                history.append(event_dict)

            return history

    except Exception as e:
        logger.error(
            f"Failed to query fallback history for {service_name}: {e}",
            exc_info=True,
        )
        return []
