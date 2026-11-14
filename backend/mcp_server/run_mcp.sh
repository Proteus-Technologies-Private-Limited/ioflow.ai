#!/bin/bash

# IOFlow MCP Server Runner for Claude Desktop
# This script activates the virtual environment and runs the MCP server

# Change to backend directory
cd /path/to/ioflow/backend

# Activate virtual environment
source ../venv/bin/activate

# Set default environment variables if not provided
export IOFLOW_BASE_URL="${IOFLOW_BASE_URL:-http://localhost:7001}"

# Check if API key is set
if [ -z "$IOFLOW_API_KEY" ]; then
    echo "Error: IOFLOW_API_KEY environment variable is not set"
    echo "Please set it in your Claude Desktop configuration"
    exit 1
fi

# Run the MCP server
echo "Starting IOFlow MCP Server..."
echo "Base URL: $IOFLOW_BASE_URL"
echo "API Key: ${IOFLOW_API_KEY:0:12}..."

python -u mcp_server/server.py