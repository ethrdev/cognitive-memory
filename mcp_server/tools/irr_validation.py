"""
IRR Validation MCP Tool for 

MCP tool that provides IRR validation functionality using Cohen's Kappa
for dual judge scores across all ground truth queries.

This tool can be called to:
1. Run global IRR validation with kappa calculation
2. Trigger contingency plan if kappa < 0.70
3. Get validation results and recommendations
"""

import logging
from datetime import UTC, datetime
from typing import Any

from mcp_server.validation.contingency import ContingencyManager
from mcp_server.validation.irr_validator import run_irr_validation

logger = logging.getLogger(__name__)


async def handle_run_irr_validation(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Run complete IRR validation for all ground truth queries with dual judge scores.

    Args:
        arguments: Tool arguments containing:
            - kappa_threshold: float - Minimum acceptable kappa (default: 0.70)
            - include_contingency: bool - Whether to run contingency analysis if needed

    Returns:
        Dictionary with validation results, kappa values, and contingency recommendations
    """
    try:
        # Extract parameters
        kappa_threshold = arguments.get("kappa_threshold", 0.70)
        include_contingency = arguments.get("include_contingency", True)

        # Validate parameters
        if (
<<<<<<< Updated upstream
            not isinstance(kappa_threshold, int | float)
=======
            not isinstance(kappa_threshold, (int, float))
>>>>>>> Stashed changes
            or kappa_threshold <= 0
            or kappa_threshold > 1
        ):
            return {
                "error": "Parameter validation failed",
                "details": "kappa_threshold must be a number between 0.0 and 1.0",
                "tool": "run_irr_validation",
            }

        logger.info(f"Starting IRR validation with threshold {kappa_threshold}")

        # Run core validation
        results = run_irr_validation(kappa_threshold=kappa_threshold)

        # Add timestamp
        results["timestamp"] = datetime.now(UTC).isoformat()
        results["kappa_threshold_used"] = kappa_threshold

        # Run contingency analysis if needed and requested
        if results["status"] == "contingency_triggered" and include_contingency:
            logger.info("Running contingency analysis due to low kappa")
            try:
                from mcp_server.validation.irr_validator import IRRValidator

                validator = IRRValidator(kappa_threshold)
                queries = validator.load_all_queries()

                if queries:
                    manager = ContingencyManager()
                    contingency_results = manager.run_contingency_analysis(queries)
                    results["contingency_analysis"] = contingency_results

                    logger.info(
                        f"Contingency analysis completed: {len(contingency_results['actions'])} actions recommended"
                    )

            except Exception as e:
                logger.error(f"Contingency analysis failed: {e}")
                results["contingency_analysis_error"] = str(e)

        logger.info(f"IRR validation completed: {results['status']}")
        return results

    except Exception as e:
        logger.error(f"IRR validation failed: {e}")
        return {
            "error": "IRR validation failed",
            "details": str(e),
            "tool": "run_irr_validation",
            "status": "failed",
        }


async def handle_get_validation_summary(arguments: dict[str, Any]) -> dict[str, Any]:
    """
    Get summary of all IRR validation runs from database.

    Args:
        arguments: Empty dict (no parameters required)

    Returns:
        Dictionary with validation history and statistics
    """
    try:
        from mcp_server.db.connection import get_connection

        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Get all validation results
                cursor.execute(
                    """
                    SELECT
                        id,
                        timestamp,
                        kappa_macro,
                        kappa_micro,
                        status,
                        total_queries,
                        notes,
                        contingency_actions
                    FROM validation_results
                    ORDER BY timestamp DESC
                    LIMIT 10
                """
                )

                results = []
                for row in cursor.fetchall():
                    results.append(
                        {
                            "id": row[0],
                            "timestamp": row[1].isoformat(),
                            "kappa_macro": row[2],
                            "kappa_micro": row[3],
                            "status": row[4],
                            "total_queries": row[5],
                            "notes": row[6],
                            "contingency_actions": row[7] if row[7] else [],
                        }
                    )

                # Calculate statistics
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_runs,
                        COUNT(CASE WHEN status = 'passed' THEN 1 END) as passed_runs,
                        COUNT(CASE WHEN status = 'contingency_triggered' THEN 1 END) as contingency_runs,
                        AVG(kappa_macro) as avg_kappa_macro,
                        AVG(kappa_micro) as avg_kappa_micro,
                        MAX(kappa_macro) as max_kappa_macro,
                        MIN(kappa_macro) as min_kappa_macro
                    FROM validation_results
                """
                )

                stats_row = cursor.fetchone()

                statistics = {
                    "total_runs": stats_row[0],
                    "passed_runs": stats_row[1],
                    "contingency_runs": stats_row[2],
                    "avg_kappa_macro": float(stats_row[3]) if stats_row[3] else None,
                    "avg_kappa_micro": float(stats_row[4]) if stats_row[4] else None,
                    "max_kappa_macro": float(stats_row[5]) if stats_row[5] else None,
                    "min_kappa_macro": float(stats_row[6]) if stats_row[6] else None,
                }

                if statistics["total_runs"] > 0:
                    statistics["success_rate"] = (
                        statistics["passed_runs"] / statistics["total_runs"]
                    ) * 100
                else:
                    statistics["success_rate"] = 0

        return {
            "recent_results": results,
            "statistics": statistics,
            "status": "success",
        }

    except Exception as e:
        logger.error(f"Failed to get validation summary: {e}")
        return {
            "error": "Failed to get validation summary",
            "details": str(e),
            "tool": "get_validation_summary",
            "status": "failed",
        }


def register_irr_validation_tools(server) -> list[dict]:
    """
    Register IRR validation tools with the MCP server.

    Args:
        server: MCP server instance

    Returns:
        List of registered tool definitions
    """
    from mcp.types import Tool

    tools = [
        Tool(
            name="run_irr_validation",
            description="Run IRR validation using Cohen's Kappa for all ground truth queries with dual judge scores. Returns kappa values, status, and contingency recommendations if needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "kappa_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.70,
                        "description": "Minimum acceptable kappa value (default: 0.70 for substantial agreement)",
                    },
                    "include_contingency": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to run contingency analysis if kappa < threshold (recommended: True)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_validation_summary",
            description="Get summary of all IRR validation runs with statistics and recent results",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]

    # Tool handler mapping
    tool_handlers = {
        "run_irr_validation": handle_run_irr_validation,
        "get_validation_summary": handle_get_validation_summary,
    }

    # Register handlers
    for tool_name, handler in tool_handlers.items():
        # Store handler for later use in main tools registration
        if not hasattr(server, "_irr_validation_handlers"):
            server._irr_validation_handlers = {}
        server._irr_validation_handlers[tool_name] = handler

    logger.info(f"Registered {len(tools)} IRR validation tools")
    return tools, tool_handlers


if __name__ == "__main__":
    # Test the tools directly
    import asyncio

    async def test_irr_validation():
        print("Testing IRR validation...")

        # Test validation run
        result = await handle_run_irr_validation({"kappa_threshold": 0.70})
        print(f"Validation result: {result['status']}")
        if "kappa_macro" in result:
            print(f"Macro Kappa: {result['kappa_macro']:.3f}")

        # Test summary
        summary = await handle_get_validation_summary({})
        print(f"Summary: {summary['statistics']['total_runs']} total runs")

    asyncio.run(test_irr_validation())
