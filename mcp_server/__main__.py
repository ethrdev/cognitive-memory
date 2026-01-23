#!/usr/bin/env python3
"""
MCP Server Main Entry Point

Cognitive Memory System v1.0.0
MCP Server with PostgreSQL + pgvector backend

Story 11.4.1: Migrated to FastMCP 3.x for middleware and HTTP transport support.
The server exposes 27 tools and 5 resources for cognitive memory management.

Note: FastMCP 3.0.0b1 uses CLI-based transport selection. This module creates
the FastMCP server instance with middleware for use by the fastmcp CLI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime

from fastmcp import FastMCP

# : Systemd watchdog support
try:
    from systemd import daemon as systemd_daemon

    SYSTEMD_AVAILABLE = True
except ImportError:
    SYSTEMD_AVAILABLE = False

# Load environment-specific configuration BEFORE local imports
# (development/production)
from mcp_server.config import load_environment  # noqa: E402

# Load environment (validates required vars, merges config, logs environment)
try:
    config = load_environment()
except Exception as e:
    print(f"FATAL: Configuration error: {e}", file=sys.stderr)
    sys.exit(1)

# Local imports (after environment is loaded)
from mcp_server.db.connection import (  # noqa: E402
    close_all_connections,
    get_connection,
    initialize_pool,
)
from mcp_server.health.haiku_health_check import periodic_health_check  # noqa: E402
from mcp_server.middleware import TenantMiddleware  # noqa: E402
from mcp_server.resources import register_resources  # noqa: E402
from mcp_server.tools import register_tools  # noqa: E402


# Configure structured JSON logging
class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        return json.dumps(log_data)


def setup_logging() -> None:
    """Setup structured JSON logging to stderr."""
    # Configure logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)  # Capture all levels, let handlers filter

    # Create stderr handler (not stdout - stdout is for MCP protocol)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())

    # Set log level from environment
    log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper())
    handler.setLevel(log_level)

    # Add handler to root logger
    logging.getLogger().handlers.clear()
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(log_level)


# : Systemd watchdog heartbeat thread
_watchdog_stop_event = threading.Event()


def watchdog_thread() -> None:
    """Background thread that sends periodic heartbeats to systemd watchdog.

    Runs every 30 seconds (half of the 60s WatchdogSec timeout) to ensure
    systemd knows the service is healthy. If heartbeats stop, systemd will
    automatically restart the service after WatchdogSec timeout.
    """
    logger = logging.getLogger(__name__)

    if not SYSTEMD_AVAILABLE:
        logger.warning("systemd-python not available, watchdog disabled")
        return

    logger.info("Watchdog thread started (heartbeat every 30s)")

    while not _watchdog_stop_event.is_set():
        try:
            # Send watchdog heartbeat to systemd
            systemd_daemon.notify("WATCHDOG=1")
            logger.debug("Watchdog heartbeat sent to systemd")
        except Exception as e:
            logger.error(f"Failed to send watchdog heartbeat: {e}")

        # Wait 30 seconds (or until stop event is set)
        _watchdog_stop_event.wait(timeout=30.0)

    logger.info("Watchdog thread stopped")


def start_watchdog() -> None:
    """Start the watchdog heartbeat background thread."""
    if SYSTEMD_AVAILABLE:
        thread = threading.Thread(target=watchdog_thread, daemon=True, name="watchdog")
        thread.start()


def notify_systemd_ready() -> None:
    """Notify systemd that the service is ready to handle requests."""
    if SYSTEMD_AVAILABLE:
        try:
            systemd_daemon.notify("READY=1")
            logging.getLogger(__name__).info("Notified systemd: service ready")
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to notify systemd ready: {e}")


def notify_systemd_stopping() -> None:
    """Notify systemd that the service is shutting down gracefully."""
    if SYSTEMD_AVAILABLE:
        try:
            systemd_daemon.notify("STOPPING=1")
            logging.getLogger(__name__).info("Notified systemd: service stopping")
        except Exception as e:
            logging.getLogger(__name__).error(
                f"Failed to notify systemd stopping: {e}"
            )

    # Stop the watchdog thread
    _watchdog_stop_event.set()


def create_server() -> FastMCP:
    """
    Create and configure the FastMCP server instance.

    This function is called by the fastmcp CLI or can be called directly
    for programmatic server creation.

    Returns:
        Configured FastMCP server instance
    """
    # Setup structured logging first
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Creating Cognitive Memory MCP Server v1.0.0 (FastMCP 3.x)")

    # Create FastMCP instance (Story 11.4.1: Migrated from official SDK)
    mcp = FastMCP("cognitive-memory")

    # Register TenantMiddleware (Story 11.4.1: Extract project_id)
    mcp.add_middleware(TenantMiddleware())
    logger.info("TenantMiddleware registered for project context extraction")

    # Register tools and resources
    tools = register_tools(mcp)
    resources = register_resources(mcp)

    logger.info(f"Registered {len(tools)} tools and {len(resources)} resources")

    # Start systemd watchdog heartbeat thread
    start_watchdog()

    # Notify systemd that server is ready
    notify_systemd_ready()

    return mcp


async def initialize_database() -> None:
    """Initialize database connection pool and test connection."""
    logger = logging.getLogger(__name__)

    # Initialize database connection pool
    try:
        await initialize_pool()
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Failed to initialize connection pool: {e}")
        logger.warning("Server will continue but database operations may fail")

    # Test database connection
    try:
        async with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
            logger.info(f"Database connected: {version}")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        logger.warning("Server will continue but database operations may fail")

    # Start background health check task
    asyncio.create_task(periodic_health_check())
    logger.info("Health check background task started (15-minute intervals)")


async def main() -> None:
    """
    Main entry point for programmatic server execution.

    For production use, the fastmcp CLI is recommended:
    $ fastmcp run mcp_server.__main__:mcp

    This function is provided for backward compatibility and testing.
    """
    logger = logging.getLogger(__name__)

    try:
        mcp = create_server()
        await initialize_database()

        # Run server with default (stdio) transport
        # Note: FastMCP 3.0.0b1 uses CLI for transport selection
        # For HTTP transport, use: fastmcp run --transport http mcp_server.__main__:mcp
        logger.info("Starting server with stdio transport (use CLI for HTTP: fastmcp run --transport http)")

        # FastMCP will handle the rest
        # The server needs to be run externally or via fastmcp CLI

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        # : Notify systemd we're stopping gracefully
        notify_systemd_stopping()

        # Graceful shutdown: close all database connections
        logger.info("Closing database connections")
        try:
            close_all_connections()
            logger.info("Graceful shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def handle_sigterm(signum, frame):
    """Handle SIGTERM gracefully (systemd stop command)."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, initiating graceful shutdown")
    # Notify systemd we're stopping
    notify_systemd_stopping()
    # Exit cleanly (will trigger finally block in main())
    sys.exit(0)


# Create the server instance for fastmcp CLI
# This is the main entry point when using: fastmcp run mcp_server.__main__:mcp
mcp = None


def _lazy_init():
    """Lazy initialization of the server instance."""
    global mcp
    if mcp is None:
        mcp = create_server()


# Lazy initialization when module is imported
# This allows fastmcp CLI to access the 'mcp' object
_lazy_init()


if __name__ == "__main__":
    # : Register SIGTERM handler for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)

    # For direct execution, initialize and run
    # For production, use: fastmcp run mcp_server.__main__:mcp --transport http
    asyncio.run(main())
