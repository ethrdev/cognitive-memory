#!/usr/bin/env python3
"""
MCP Server Main Entry Point

Cognitive Memory System v1.0.0
MCP Server with PostgreSQL + pgvector backend

This module provides the main entry point for the MCP Server using stdio transport.
The server exposes 7 tools and 5 resources for cognitive memory management.
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

from mcp.server import InitializationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, ServerCapabilities, Tool

# Story 3.8: Systemd watchdog support
try:
    from systemd import daemon as systemd_daemon

    SYSTEMD_AVAILABLE = True
except ImportError:
    SYSTEMD_AVAILABLE = False

# Load environment-specific configuration BEFORE local imports
# Story 3.7: Environment separation (development/production)
from mcp_server.config import load_environment  # noqa: E402

# Load environment (validates required vars, merges config, logs environment)
try:
    config = load_environment()
except Exception as e:
    print(f"FATAL: Configuration error: {e}", file=sys.stderr)
    sys.exit(1)

# Local imports (after environment is loaded)
from mcp_server.db.connection import close_all_connections, get_connection  # noqa: E402
from mcp_server.health.haiku_health_check import periodic_health_check  # noqa: E402
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


# Story 3.8: Systemd watchdog heartbeat thread
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


async def main() -> None:
    """Main MCP server entry point."""
    # Setup structured logging first
    setup_logging()
    logger = logging.getLogger(__name__)

    try:

        logger.info("Starting Cognitive Memory MCP Server v1.0.0")

        # Initialize MCP server
        server = Server("cognitive-memory")

        # Register tools and resources
        tools = register_tools(server)
        resources = register_resources(server)

        logger.info(f"Registered {len(tools)} tools and {len(resources)} resources")

        # Test database connection
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                logger.info(f"Database connected: {version}")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            logger.warning("Server will continue but database operations may fail")

        # Start background health check task (Story 3.4)
        # Monitors Haiku API availability and auto-recovers from fallback mode
        asyncio.create_task(periodic_health_check())
        logger.info("Health check background task started (15-minute intervals)")

        # Story 3.8: Start systemd watchdog heartbeat thread
        start_watchdog()

        # Setup server info for handshake
        @server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available MCP tools."""
            return tools

        @server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available MCP resources."""
            return resources

        logger.info("MCP Server initialized, starting stdio transport")

        # Create initialization options
        init_options = InitializationOptions(
            server_name="cognitive-memory",
            server_version="1.0.0",
            capabilities=ServerCapabilities(tools={}, resources={}, prompts={}),
        )

        # Story 3.8: Notify systemd that server is ready
        notify_systemd_ready()

        # Run the server with stdio transport
        async with stdio_server() as streams:
            await server.run(*streams, init_options)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
    finally:
        # Story 3.8: Notify systemd we're stopping gracefully
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


if __name__ == "__main__":
    # Story 3.8: Register SIGTERM handler for graceful shutdown
    signal.signal(signal.SIGTERM, handle_sigterm)

    # Environment variables already loaded at module import time
    # Run the server
    asyncio.run(main())
