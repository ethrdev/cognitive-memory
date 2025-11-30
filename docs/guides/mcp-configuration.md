# MCP Configuration Guide

## Overview

This document describes how to configure Claude Code as an MCP client to connect to the Cognitive Memory MCP Server.

## Configuration Options

Claude Code supports two configuration locations:

| Location | Scope | Use Case |
|----------|-------|----------|
| `.mcp.json` (project root) | Project-specific | MCP server only available in this project |
| `~/.config/claude-code/mcp-settings.json` | Global | MCP server available in **all** projects |

## Recommended Configuration (Start Script)

The recommended approach uses `start_mcp_server.sh` which automatically loads environment variables from `.env.development`:

**Project-specific** (`.mcp.json` in project root):
```json
{
  "mcpServers": {
    "cognitive-memory": {
      "type": "stdio",
      "command": "/path/to/cognitive-memory/start_mcp_server.sh"
    }
  }
}
```

**Global** (`~/.config/claude-code/mcp-settings.json`):
```json
{
  "mcpServers": {
    "cognitive-memory": {
      "type": "stdio",
      "command": "/path/to/cognitive-memory/start_mcp_server.sh"
    }
  }
}
```

### Configuration Fields Explained

| Field | Description | Example |
|-------|-------------|---------|
| `command` | Path to Python interpreter in the virtual environment | `/home/user/.cache/pypoetry/virtualenvs/cognitive-memory-system-XXXX/bin/python` |
| `args` | Arguments to pass to Python interpreter | `["-m", "mcp_server"]` |
| `cwd` | Working directory for the MCP server | `/home/user/projects/cognitive-memory` |
| `env` | Environment variables for the server | API keys and configuration |

## Prerequisites

### 1. Database Requirements

- PostgreSQL 15+ with pgvector extension
- Database should be running and accessible
- Schema migrations should be applied

### 2. Environment Variables

Required environment variables in your shell:

```bash
export ANTHROPIC_API_KEY="your_anthropic_api_key"
export OPENAI_API_KEY="your_openai_api_key"
```

### 3. Python Dependencies

All dependencies should be installed via Poetry:

```bash
cd /path/to/project
poetry install
```

## Finding Your Python Interpreter Path

### Using Poetry (Recommended)

```bash
# Get the path to the Python interpreter in your Poetry environment
poetry run which python
```

### Alternative Methods

```bash
# If using a different virtual environment
which python

# Or find Python in a specific environment
ls -la /path/to/venv/bin/python
```

## Verification Steps

### 1. Check MCP Server Registration

After restarting Claude Code, the MCP server should appear in the available servers list.

### 2. Verify Tools and Resources

- **11 Tools** should be available:

  **Memory Tools:**
  - `store_raw_dialogue` - L0 storage
  - `compress_to_l2_insight` - L2 storage with embeddings
  - `hybrid_search` - Semantic + keyword + graph search
  - `update_working_memory` - Working memory management
  - `store_episode` - Episode storage

  **Evaluation Tools:**
  - `store_dual_judge_scores` - Dual judge evaluation
  - `get_golden_test_results` - Golden test results
  - `ping` - Health check

  **Graph Tools:**
  - `graph_add_node` - Create graph nodes
  - `graph_add_edge` - Create graph relationships
  - `graph_query_neighbors` - Query node neighbors
  - `graph_find_path` - Find paths between nodes

- **5 Resources** should be available:
  - `memory://l2-insights` - Query L2 insights
  - `memory://working-memory` - Working memory items
  - `memory://episode-memory` - Episode retrieval
  - `memory://l0-raw` - Raw dialogue transcripts
  - `memory://stale-memory` - Archived items

### 3. Test Basic Connectivity

Execute the `ping` tool to verify basic MCP connectivity:

```bash
# Expected response: {"content": [{"type": "text", "text": "pong"}]}
```

## Troubleshooting

### Common Issues and Solutions

#### Issue: "MCP Server not found" / Tools not visible under /mcp

**Cause**: Incorrect path in `command` or `args` fields, or database connection issues
**Solution**:

1. Verify Python interpreter path: `poetry run which python`
2. Verify working directory: `pwd` in project root
3. Test manual execution: `poetry run python -m mcp_server --help`
4. Check database connection (see below)

#### Issue: "Connection refused" / Database connection failed

**Cause**: PostgreSQL not running or wrong connection details
**Solution**:

1. Check if PostgreSQL container is running: `docker ps | grep postgres`
2. Find correct port: May be 5432 (native) or 54322 (Docker)
3. Update DATABASE_URL in mcp-settings.json with correct port
4. Test connection: `psql postgresql://postgres:postgres@localhost:54322/postgres`

#### Issue: "Tool list empty" / No tools showing

**Cause**: MCP server started but failed to register tools, usually due to database issues
**Solution**:

1. Check MCP server logs should show: "Registered 11 tools" and "Registered 5 resources"
2. Verify database connection is working
3. Test server startup manually: `poetry run python -m mcp_server`
4. Ensure all dependencies are installed: `poetry install`

#### Issue: "API Key errors"

**Cause**: Missing or invalid environment variables
**Solution**:

1. API keys must be provided directly in mcp-settings.json env section
2. Use placeholder keys for basic testing: `ANTHROPIC_API_KEY: "sk-ant-api03-YOUR_ANTHROPIC_API_KEY"`
3. Update with real API keys for full functionality
4. Restart Claude Code after updating configuration

#### Critical Configuration Check

**Option 1: Inline Environment Variables (Recommended)**
If Claude Code doesn't load the `env` section properly, use inline environment variables:

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "/bin/bash",
      "args": [
        "-c",
        "cd /path/to/project && DATABASE_URL='postgresql://postgres:postgres@localhost:54322/postgres' ANTHROPIC_API_KEY='sk-ant-api03-YOUR_ANTHROPIC_API_KEY' OPENAI_API_KEY='sk-placeholder' ENVIRONMENT='production' LOG_LEVEL='INFO' /path/to/python -m mcp_server"
      ]
    }
  }
}
```

**Option 2: Startup Script (Alternative)**
Create a startup script and reference it in mcp-settings.json:

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "/path/to/project/start-mcp-server.sh"
    }
  }
}
```

**Option 3: Traditional with env section**
If your Claude Code version supports the env section properly:

```json
{
  "mcpServers": {
    "cognitive-memory": {
      "command": "/absolute/path/to/your/python",
      "args": ["-m", "mcp_server"],
      "cwd": "/absolute/path/to/project",
      "env": {
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:54322/postgres",
        "ANTHROPIC_API_KEY": "sk-ant-api03-YOUR_ANTHROPIC_API_KEY",
        "OPENAI_API_KEY": "sk-placeholder"
      }
    }
  }
}
```

### Debug Mode

To enable debug logging, you can temporarily modify the environment:

```json
{
  "env": {
    "LOG_LEVEL": "DEBUG",
    "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
    "OPENAI_API_KEY": "${OPENAI_API_KEY}",
    "ENVIRONMENT": "production"
  }
}
```

### Manual Testing

You can test the MCP server manually before configuring Claude Code:

```bash
# In project directory
poetry run python -m mcp_server

# The server should output:
# "Registered 7 tools"
# "Registered 5 resources"
# "MCP Server initialized, starting stdio transport"
```

## Performance Considerations

- **Startup Time**: MCP server typically starts in 1-3 seconds
- **Tool Call Latency**: Most tools complete in <1 second (excluding API calls)
- **Memory Usage**: Approximately 50-100MB for the MCP server process

## Security Notes

- API keys are inherited from your shell environment
- The MCP server runs with the same permissions as your user account
- All database connections use the configured PostgreSQL connection
- Consider using `.env` files for sensitive configuration

## Support

For issues related to:

- **MCP Protocol**: Check MCP documentation
- **Cognitive Memory System**: Check project repository
- **Claude Code**: Check Claude Code documentation

---

*Last updated: 2025-11-24*
*Project: Cognitive Memory System*
