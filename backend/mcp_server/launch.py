#!/usr/bin/env python3
"""
Launch script for IOFlow MCP Server

This script provides an easy way to start the MCP server with proper configuration.
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from mcp_server.server import IOFlowMCPServer

def setup_logging(verbose: bool):
    """Configure logging based on verbosity"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def check_environment():
    """Check required environment variables"""
    required_vars = ["IOFLOW_BASE_URL", "IOFLOW_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these environment variables before running the MCP server.")
        print("\nExample:")
        print("  export IOFLOW_BASE_URL='http://localhost:8000'")
        print("  export IOFLOW_API_KEY='your-api-key-here'")
        sys.exit(1)

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="IOFlow MCP Server for Seed Application Management"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--base-url",
        help="IOFlow base URL (overrides IOFLOW_BASE_URL env var)"
    )
    parser.add_argument(
        "--api-key",
        help="IOFlow API key (overrides IOFLOW_API_KEY env var)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Override environment variables if provided
    if args.base_url:
        os.environ["IOFLOW_BASE_URL"] = args.base_url
    if args.api_key:
        os.environ["IOFLOW_API_KEY"] = args.api_key
    
    # Check environment
    check_environment()
    
    # Create and run server
    print("Starting IOFlow MCP Server...")
    print(f"Base URL: {os.getenv('IOFLOW_BASE_URL')}")
    print(f"API Key: {'*' * 10}{os.getenv('IOFLOW_API_KEY')[-4:]}")
    print("\nThe server is ready to accept MCP connections.")
    print("Press Ctrl+C to stop.\n")
    
    server = IOFlowMCPServer()
    
    try:
        await server.run()
    except KeyboardInterrupt:
        print("\nShutting down MCP server...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())