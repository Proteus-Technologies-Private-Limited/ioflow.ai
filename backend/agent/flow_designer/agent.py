#!/usr/bin/env python3
"""
Flow Designer Agent for ADK Web Interface - Simplified with MCPToolset

This agent creates, modifies, and saves flow designs for IOFlow.
It uses MCPToolset to connect directly to the MCP server, which handles
all data processing and business logic.
"""

import os
import logging
import warnings
import asyncio
from pathlib import Path
from google import adk
from google.adk.tools.mcp_tool import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from dotenv import load_dotenv

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/
from agent_pack import agent_prompt  # noqa: E402
from agent_pack.runtime import bridge_server_params  # noqa: E402

# Suppress known asyncio warnings from MCP stdio cleanup
warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*cancel scope.*')

# Custom asyncio exception handler to suppress MCP stdio cleanup errors
def asyncio_exception_handler(loop, context):
    """Custom handler to suppress known MCP stdio cleanup exceptions"""
    exception = context.get('exception')
    if exception and isinstance(exception, RuntimeError):
        error_msg = str(exception)
        # Suppress the known MCP stdio cancel scope error
        if 'cancel scope' in error_msg or 'TaskGroup' in error_msg:
            # This is a known cleanup issue in MCP stdio client, safe to ignore
            return

    # For other exceptions, use default handler
    loop.default_exception_handler(context)

# Load environment variables from .env file
env_path = Path(__file__).resolve().parents[3] / '.env'  # Goes up to IOFlow root
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()  # Load from current directory if root .env doesn't exist

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get configuration from environment
api_key = os.getenv("IOFLOW_API_KEY", "")
base_url = os.getenv("IOFLOW_BASE_URL", "http://localhost:7001")
model_name = os.getenv("FLOW_DESIGNER_MODEL") or os.getenv("FLOW_AGENT_MODEL") or os.getenv("AGENT_MODEL") or os.getenv("FLOW_DESIGN_MODEL") or "gemini-2.5-pro"

# Log environment configuration
logger.info(f"Creating Flow Designer agent with API_KEY present: {bool(api_key)}, BASE_URL: {base_url}")
logger.info(f"Using model: {model_name}")

# MCP Server path - go up to backend directory, then to mcp_server
mcp_server_path = Path(__file__).parent.parent.parent / "mcp_server" / "ioflow_mcp_server.py"

# Verify the MCP server exists
if not mcp_server_path.exists():
    logger.error(f"MCP server not found at: {mcp_server_path}")
    logger.error(f"Resolved path: {mcp_server_path.resolve()}")
    raise FileNotFoundError(f"MCP server not found: {mcp_server_path}")
else:
    logger.info(f"MCP server found at: {mcp_server_path}")

# Use the same Python interpreter that's running this script
# This ensures we use the venv Python with all required packages
import sys
python_executable = sys.executable
logger.info(f"Using Python executable: {python_executable}")

# Create MCPToolset with stdio connection to MCP server
# The MCP server will handle all data processing and connect to IOFlow API via HTTP
mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        # The MCP bridge's tools (the one tool surface every IOFlow agent
        # surface shares), limited to this agent's agent-pack tools and
        # authenticated as the CURRENT request's caller (agent_pack.runtime).
        server_params=StdioServerParameters(**bridge_server_params("flow-designer"))
    )
    # Note: tool_filter can be added here if we want to limit which tools are exposed
    # For now, we expose all tools from the MCP server
)

# Create the agent with MCP integration
root_agent = adk.Agent(
    model=model_name,
    name="flow_designer",
    description="Flow Designer - creates and validates/saves IOFlow JSON configurations.",
    # single source: backend/agent_pack/agents/flow-designer.md
    instruction=agent_prompt("flow-designer"),
    tools=[mcp_toolset]  # All tools are provided by the MCP server
)

# Also expose as 'agent' for compatibility
agent = root_agent

# Set custom exception handler for asyncio to suppress MCP stdio cleanup errors
try:
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(asyncio_exception_handler)
    logger.info("Custom asyncio exception handler registered")
except RuntimeError:
    # Event loop not running yet, handler will be set when loop starts
    logger.debug("Event loop not available yet, exception handler will be set later")

logger.info("Flow Designer Agent created with MCPToolset and exposed successfully")
logger.info(f"Agent connects to MCP server at: {mcp_server_path}")
logger.info(f"MCP server connects to IOFlow API at: {base_url}")