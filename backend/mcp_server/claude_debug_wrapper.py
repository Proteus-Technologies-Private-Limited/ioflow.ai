#!/usr/bin/env python3
"""Debug wrapper for Claude Desktop MCP server"""

import sys
import os
import json
import logging
from datetime import datetime

# Set up logging to a file
log_file = os.path.expanduser("~/ioflow_mcp_debug.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 80)
    logger.info(f"MCP Debug Wrapper Started at {datetime.now()}")
    logger.info("=" * 80)
    
    # Log environment
    logger.info("Environment variables:")
    for key, value in os.environ.items():
        if key.startswith("IOFLOW") or key.startswith("MCP"):
            logger.info(f"  {key}={value}")
    
    # Log Python info
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    # Try to import and run the actual remote client
    try:
        logger.info("Attempting to import remote_client...")
        
        # Add the backend directory to Python path
        backend_dir = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(backend_dir)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
            logger.info(f"Added {parent_dir} to Python path")
        
        import asyncio
        from mcp_server.remote_client import main as remote_client_main
        
        logger.info("Successfully imported remote_client, starting...")
        
        # Check if there's already an event loop running
        try:
            loop = asyncio.get_running_loop()
            logger.info("Event loop already running, using existing loop")
            # Schedule the coroutine in the existing loop
            asyncio.create_task(remote_client_main())
            # Keep the wrapper running
            loop.run_forever()
        except RuntimeError:
            # No loop running, create a new one
            logger.info("No event loop running, creating new one")
            asyncio.run(remote_client_main())
        
    except Exception as e:
        logger.error(f"Error running remote client: {type(e).__name__}: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()