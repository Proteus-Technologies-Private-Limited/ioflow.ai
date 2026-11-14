#!/bin/bash
# IOFlow MCP Server Runner
# This script ensures proper environment setup for the MCP server

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$BACKEND_DIR")"

# Check if virtual environment exists and use the python from it directly
if [ -d "$PROJECT_ROOT/venv" ]; then
    # Redirect diagnostic output to stderr so it doesn't interfere with MCP protocol
    echo "Using virtual environment Python..." >&2
    PYTHON_EXEC="$PROJECT_ROOT/venv/bin/python3"
elif [ -d "$BACKEND_DIR/venv" ]; then
    echo "Using backend virtual environment Python..." >&2
    PYTHON_EXEC="$BACKEND_DIR/venv/bin/python3"
else
    echo "No virtual environment found, using system Python..." >&2
    PYTHON_EXEC="python3"
fi

# Set Python path
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"

# Check for required environment variables
if [ -z "$IOFLOW_API_KEY" ]; then
    echo "ERROR: IOFLOW_API_KEY environment variable not set" >&2
    echo "Please set it in Claude Desktop configuration" >&2
    exit 1
fi

if [ -z "$IOFLOW_BASE_URL" ]; then
    echo "WARNING: IOFLOW_BASE_URL not set, using default http://localhost:8000" >&2
    export IOFLOW_BASE_URL="http://localhost:8000"
fi

# Log startup information to stderr
echo "Starting IOFlow MCP Server" >&2
echo "Backend URL: $IOFLOW_BASE_URL" >&2
echo "API Key: ${IOFLOW_API_KEY:0:20}..." >&2
echo "Python Path: $PYTHONPATH" >&2

# Run the MCP server
exec "$PYTHON_EXEC" "$SCRIPT_DIR/server.py"