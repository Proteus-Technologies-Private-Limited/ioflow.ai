"""
IOFlow MCP Server Entry Point

This module allows running the MCP server with:
    python -m mcp_server
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.ioflow_mcp_server import IOFlowMCPServer

def main():
    """Main entry point for the MCP server"""
    # Configure logging to stderr to not interfere with MCP protocol
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stderr
    )
    
    logger = logging.getLogger(__name__)
    
    # Check environment variables
    if not os.getenv("IOFLOW_API_KEY"):
        logger.warning("IOFLOW_API_KEY not set. Authentication will be required.")
    
    base_url = os.getenv("IOFLOW_BASE_URL", "http://localhost:8000")
    logger.info(f"Connecting to IOFlow at: {base_url}")
    
    # Create and run server
    try:
        server = IOFlowMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()