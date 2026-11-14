#!/usr/bin/env python3
"""Start backend with verbose logging"""
import os
import sys
import logging

# Configure logging before any imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('debug.log')
    ]
)

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    # Import after logging is configured
    import uvicorn
    
    print("Starting backend with debug logging...")
    print("Log file: debug.log")
    print("Server: http://localhost:7001")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=7001,
        reload=False,
        log_level="info"
    )