"""
Budget Monitoring CLI Main Entry Point

Allows running the budget CLI as a module:
    python -m mcp_server.budget [command] [options]
"""

from mcp_server.budget.cli import main

if __name__ == "__main__":
    main()
