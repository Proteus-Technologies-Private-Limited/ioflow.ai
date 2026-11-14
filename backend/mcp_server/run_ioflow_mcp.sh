#!/bin/bash
# IOFlow MCP Server Runner - Final Version
set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$BACKEND_DIR")"

# Use virtual environment Python
PYTHON_EXEC="$PROJECT_ROOT/venv/bin/python3"

# Validate Python exists
if [ ! -f "$PYTHON_EXEC" ]; then
    echo "Error: Virtual environment Python not found at $PYTHON_EXEC" >&2
    exit 1
fi

# Set environment
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# Check for API key
if [ -z "$IOFLOW_API_KEY" ]; then
    echo "Error: IOFLOW_API_KEY not set" >&2
    exit 1
fi

# Check for base URL
if [ -z "$IOFLOW_BASE_URL" ]; then
    export IOFLOW_BASE_URL="http://localhost:7001"
fi

# Debug info to stderr only
echo "IOFlow MCP Server Starting..." >&2
echo "Python: $PYTHON_EXEC" >&2
echo "Backend: $IOFLOW_BASE_URL" >&2

# Run the server - no output to stdout except JSON-RPC
cd "$BACKEND_DIR"
exec "$PYTHON_EXEC" "$SCRIPT_DIR/ioflow_mcp.py"