#!/usr/bin/env python3
"""Simplest possible MCP server for testing"""
import sys
import logging

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP
    
    # Create server
    mcp = FastMCP("test-server")
    
    @mcp.tool()
    def hello(name: str) -> str:
        """Say hello to someone"""
        return f"Hello, {name}!"
    
    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two numbers"""
        return a + b
    
    if __name__ == "__main__":
        logger.info("Starting test MCP server")
        mcp.run()
        
except Exception as e:
    logger.error(f"Error: {e}")
    import traceback
    traceback.print_exc(file=sys.stderr)