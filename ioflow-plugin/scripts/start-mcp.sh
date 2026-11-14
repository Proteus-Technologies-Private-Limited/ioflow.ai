#!/bin/bash
# Start IOFlow MCP Server for Claude Code plugin
set -e

# IOFLOW_HOME must point to the IOFlow project root
if [ -z "$IOFLOW_HOME" ]; then
    echo "Error: IOFLOW_HOME not set." >&2
    echo "Set it with: export IOFLOW_HOME=/path/to/IOFlow" >&2
    exit 1
fi

BACKEND_DIR="$IOFLOW_HOME/backend"
PYTHON_EXEC="$IOFLOW_HOME/venv/bin/python3"

# Validate Python venv exists
if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Error: Virtual environment Python not found at $PYTHON_EXEC" >&2
    echo "Run: python3 -m venv $IOFLOW_HOME/venv && pip install -r $BACKEND_DIR/requirements.txt" >&2
    exit 1
fi

# Set environment
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# Check for API key
if [ -z "$IOFLOW_API_KEY" ]; then
    echo "Error: IOFLOW_API_KEY not set. Set it with: export IOFLOW_API_KEY=your_key" >&2
    exit 1
fi

# Default base URL to localhost
if [ -z "$IOFLOW_BASE_URL" ]; then
    export IOFLOW_BASE_URL="http://localhost:7001"
fi

# Debug info to stderr only (stdout is for MCP JSON-RPC)
echo "IOFlow MCP Server Starting for Claude Code..." >&2
echo "IOFLOW_HOME: $IOFLOW_HOME" >&2
echo "Backend: $IOFLOW_BASE_URL" >&2

# Run the comprehensive MCP server
cd "$BACKEND_DIR"
exec "$PYTHON_EXEC" "$BACKEND_DIR/mcp_server/ioflow_mcp_server.py"
