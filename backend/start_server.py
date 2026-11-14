#!/usr/bin/env python3
"""Start the backend server properly"""
import uvicorn
import os
import sys
from dotenv import load_dotenv

if __name__ == "__main__":
    # Make sure we're in the backend directory
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(backend_dir)
    
    # Load environment variables from .env file
    env_path = os.path.join(backend_dir, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
        print(f"Loaded .env from {env_path}")
    else:
        print(f"WARNING: .env file not found at {env_path}")
    
    # Add backend to Python path
    sys.path.insert(0, backend_dir)
    
    
    print("Starting IOFlow backend on http://localhost:7001")
    print("Press Ctrl+C to stop")
    
    # Run the server
    uvicorn.run("main:app", host="0.0.0.0", port=7001, reload=False)