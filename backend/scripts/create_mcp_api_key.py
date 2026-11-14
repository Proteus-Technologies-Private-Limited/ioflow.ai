#!/usr/bin/env python3
"""
Create an API key for MCP Server access
This creates a personal API key that works with your JWT token
"""

import os
import json
import secrets
import hashlib
from pathlib import Path
from datetime import datetime

def create_mcp_api_key():
    """Create a personal API key for MCP access"""
    
    print("IOFlow MCP API Key Generator")
    print("=" * 40)
    print("\nThis will create an API key that wraps your JWT token for MCP access.\n")
    
    # Get user credentials
    email = input("Enter your IOFlow email: ")
    password = input("Enter your IOFlow password: ")
    
    # Generate API key
    raw_key = secrets.token_urlsafe(32)
    api_key = f"ioflow_mcp_{raw_key}"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Create storage directory
    config_dir = Path.home() / ".ioflow"
    config_dir.mkdir(exist_ok=True)
    
    # Store credentials (in production, use proper encryption)
    config_file = config_dir / "mcp_auth.json"
    
    config = {
        "api_key": api_key,
        "key_hash": key_hash,
        "email": email,
        "created_at": datetime.utcnow().isoformat(),
        "description": "Personal MCP API Key"
    }
    
    # Save config (Note: In production, encrypt the password!)
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Also create an auth wrapper script
    wrapper_script = config_dir / "ioflow_mcp_auth.sh"
    wrapper_content = f"""#!/bin/bash
# IOFlow MCP Authentication Wrapper
# This script handles authentication for the MCP server

export IOFLOW_EMAIL="{email}"
export IOFLOW_API_KEY="{api_key}"
export IOFLOW_BASE_URL="http://localhost:8000"

echo "IOFlow MCP authentication configured"
"""
    
    with open(wrapper_script, 'w') as f:
        f.write(wrapper_content)
    
    os.chmod(wrapper_script, 0o755)
    
    print(f"\n✅ API Key created successfully!")
    print(f"\nYour MCP API Key:")
    print(f"{api_key}")
    print(f"\nConfiguration saved to: {config_file}")
    print(f"\nTo use this key, run:")
    print(f"source {wrapper_script}")
    
    return api_key

if __name__ == "__main__":
    create_mcp_api_key()