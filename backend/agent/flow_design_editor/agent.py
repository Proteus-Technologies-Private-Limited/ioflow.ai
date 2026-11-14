#!/usr/bin/env python3
"""
Flow Design Editor Agent for ADK Web Interface

Purpose: Edit and modify existing flow designs with intelligent error analysis.
This agent focuses on updating, refining, fixing, and improving already created flows.

Capabilities:
- Load existing flows by ID or name
- Analyze execution logs for debugging
- Modify nodes, connections, and parameters
- Replace problematic nodes
- Detect when redesign is needed
- Validate and save edited flows
"""

import os
import sys
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
        if 'cancel scope' in error_msg or 'TaskGroup' in error_msg:
            return
    loop.default_exception_handler(context)

# Load environment variables from .env file (but don't override existing ones)
# This is important because IOFLOW_API_KEY may be set at runtime by the executor
env_path = Path(__file__).resolve().parents[3] / '.env'
if env_path.exists():
    load_dotenv(env_path, override=False)  # Don't override runtime env vars
else:
    load_dotenv(override=False)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get configuration from environment
# NOTE: Don't cache api_key here - it may be set at runtime by the executor
base_url = os.getenv("IOFLOW_BASE_URL", "http://localhost:7001")
model_name = os.getenv("FLOW_EDITOR_MODEL") or os.getenv("AGENT_MODEL", "gemini-2.5-flash")

# Log environment configuration
logger.info(f"Creating Flow Editor agent, BASE_URL: {base_url}")
logger.info(f"[AGENT INIT] os.environ has IOFLOW_API_KEY: {bool('IOFLOW_API_KEY' in os.environ)}")
if 'IOFLOW_API_KEY' in os.environ:
    api_key_val = os.environ['IOFLOW_API_KEY']
    logger.info(f"  API_KEY length: {len(api_key_val)}, starts with: {api_key_val[:20]}...")
else:
    logger.warning("  ⚠️  NO API_KEY FOUND IN ENVIRONMENT!")
logger.info(f"Using model: {model_name}")

# MCP Server path
mcp_server_path = Path(__file__).parent.parent.parent / "mcp_server" / "ioflow_mcp_server.py"

# Verify the MCP server exists
if not mcp_server_path.exists():
    logger.error(f"MCP server not found at: {mcp_server_path}")
    raise FileNotFoundError(f"MCP server not found: {mcp_server_path}")
else:
    logger.info(f"MCP server found at: {mcp_server_path}")

# Use the same Python interpreter that's running this script
python_executable = sys.executable
logger.info(f"Using Python executable: {python_executable}")

# Create MCPToolset with stdio connection to MCP server
mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        # The MCP bridge's tools (the one tool surface every IOFlow agent
        # surface shares), limited to this agent's agent-pack tools and
        # authenticated as the CURRENT request's caller (agent_pack.runtime).
        server_params=StdioServerParameters(**bridge_server_params("flow-editor"))
    )
)

# Create the Flow Design Editor agent
root_agent = adk.Agent(
    name="flow_design_editor",
    model=model_name,
    description="Flow Design Editor - edits and debugs existing IOFlow configurations",

    # single source: backend/agent_pack/agents/flow-editor.md
    instruction=agent_prompt("flow-editor"),

    tools=[mcp_toolset]  # All tools from MCP server
)

# Export as both root_agent and agent for compatibility
agent = root_agent

# Set custom exception handler for asyncio
try:
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(asyncio_exception_handler)
    logger.info("Custom asyncio exception handler registered")
except RuntimeError:
    logger.debug("Event loop not available yet, exception handler will be set later")

logger.info("Flow Design Editor Agent created with MCPToolset successfully")
logger.info(f"Agent connects to MCP server at: {mcp_server_path}")
logger.info(f"MCP server connects to IOFlow API at: {base_url}")
