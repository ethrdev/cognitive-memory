#!/bin/bash

# MCP Server Startup Script
# This script sets up the environment and starts the Cognitive Memory MCP Server

cd /home/ethr/01-projects/ai-experiments/i-o

export DATABASE_URL="postgresql://postgres:postgres@localhost:54322/postgres"
export ANTHROPIC_API_KEY="sk-ant-api03-YOUR_ANTHROPIC_API_KEY"
export OPENAI_API_KEY="sk-placeholder"
export ENVIRONMENT="production"
export LOG_LEVEL="INFO"

exec /home/ethr/.cache/pypoetry/virtualenvs/cognitive-memory-system-HON7j2ab-py3.13/bin/python -m mcp_server
