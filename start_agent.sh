#!/bin/bash

# Flow Design Agent Runner Script
# This script sets up the environment and runs the IOFlow Flow Design Agent

echo "🚀 Starting IOFlow Flow Design Agent"
echo "=================================="

# Load environment variables from .env file
if [ -f .env ]; then
    echo "📋 Loading environment variables from .env"
    set -a  # Automatically export all variables
    source .env
    set +a  # Turn off automatic export
else
    echo "⚠️  Warning: .env file not found. Please create one with the required API keys."
    echo "   Copy .env.example to .env and fill in your API keys."
    exit 1
fi

# Legacy/compatibility exports (automatically use AGENT_MODEL)
export FLOW_DESIGN_MODEL="$AGENT_MODEL"
export FLOW_AGENT_MODEL="$AGENT_MODEL"
export SEARCH_AGENT_MODEL="$AGENT_MODEL" 

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run from project root."
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Check if Google ADK is installed
if ! python3 -c "import google.adk" 2>/dev/null; then
    echo "📦 Installing Google ADK..."
    pip install google-adk
fi

# Check if httpx is installed (required for the agent)
if ! python3 -c "import httpx" 2>/dev/null; then
    echo "📦 Installing httpx..."
    pip install httpx
fi

# Check if IOFlow backend is running
echo "🔍 Checking IOFlow backend..."
if ! curl -s http://localhost:7001/api/health > /dev/null 2>&1; then
    echo "⚠️  Warning: IOFlow backend doesn't seem to be running on port 7001"
    echo "   Please start it with: ./start_backend.sh"
    echo "   Continue anyway? (y/n)"
    read -r response
    if [[ "$response" != "y" ]]; then
        echo "Exiting..."
        exit 1
    fi
fi

# Navigate to agent directory
cd backend/agent

# Display configuration
echo ""
echo "📋 Configuration:"
echo "   Model: $AGENT_MODEL"
echo "   Backend: $IOFLOW_BASE_URL"
echo ""

# Start in web mode by default
echo "🌐 Starting Web Interface..."
echo "   Open http://localhost:8000 in your browser"
echo "   Press Ctrl+C to stop"
echo ""
# ADK web expects to be run from the parent directory of agents
adk web . --port 8000

echo ""
echo "✅ Flow Design Agent session ended."