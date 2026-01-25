#!/bin/bash
# MCP Server Startup Script
# Loads environment from .env.development and starts the MCP server

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Load environment variables from .env.development
if [ -f "$SCRIPT_DIR/.env.development" ]; then
    # Read and export variables
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ $key =~ ^#.*$ ]] && continue
        [[ -z $key ]] && continue

        # Remove leading/trailing whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)

        # Export the variable
        export "$key=$value"
    done < "$SCRIPT_DIR/.env.development"
fi

# Set additional environment variables
export ENVIRONMENT=development
export LOG_LEVEL=INFO

# Add project root to PYTHONPATH so mcp_server module can be found
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"

# Start the MCP server
exec "$SCRIPT_DIR/.venv/bin/python" -m mcp_server
