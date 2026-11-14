#!/usr/bin/env python3
"""
Setup script for IOFlow MCP Server in Claude Desktop

This script helps configure the MCP server for Claude Desktop
by handling authentication and generating the correct configuration.
"""

import os
import json
import requests
import platform
from pathlib import Path

def get_jwt_token(base_url, email, password):
    """Get JWT token from IOFlow"""
    try:
        response = requests.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        data = response.json()
        return data.get("access_token"), data.get("user", {})
    except Exception as e:
        print(f"Error logging in: {e}")
        return None, None

def get_claude_config_path():
    """Get Claude Desktop config file path based on OS"""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    else:  # Linux
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"

def main():
    print("IOFlow MCP Server Setup for Claude Desktop")
    print("=" * 50)
    
    # Get IOFlow credentials
    print("\n1. Enter your IOFlow credentials:")
    base_url = input("IOFlow URL (default: http://localhost:8000): ").strip() or "http://localhost:8000"
    email = input("Your IOFlow email: ").strip()
    password = input("Your IOFlow password: ").strip()
    
    # Get JWT token
    print("\n2. Authenticating with IOFlow...")
    token, user_info = get_jwt_token(base_url, email, password)
    
    if not token:
        print("❌ Failed to authenticate. Please check your credentials.")
        return
    
    print(f"✅ Authenticated as: {user_info.get('email')} (Role: {user_info.get('role')})")
    
    # Create MCP auth configuration
    mcp_auth_dir = Path.home() / ".ioflow"
    mcp_auth_dir.mkdir(exist_ok=True)
    
    mcp_auth_file = mcp_auth_dir / "mcp_auth.json"
    with open(mcp_auth_file, 'w') as f:
        json.dump({
            "email": email,
            "jwt_token": token,
            "base_url": base_url,
            "user_role": user_info.get("role")
        }, f, indent=2)
    
    print(f"\n3. Authentication saved to: {mcp_auth_file}")
    
    # Generate Claude Desktop configuration
    ioflow_path = Path(__file__).parent.parent.parent  # Get to IOFlow root
    
    mcp_config = {
        "mcpServers": {
            "ioflow-seed-manager": {
                "command": "python3",
                "args": ["-m", "mcp_server"],
                "cwd": str(ioflow_path / "backend"),
                "env": {
                    "IOFLOW_BASE_URL": base_url,
                    "IOFLOW_JWT_TOKEN": token,
                    "IOFLOW_EMAIL": email,
                    "PYTHONPATH": str(ioflow_path / "backend"),
                    "PYTHONUNBUFFERED": "1"
                }
            }
        }
    }
    
    # Show configuration
    print("\n4. Claude Desktop Configuration:")
    print("-" * 50)
    print(json.dumps(mcp_config, indent=2))
    print("-" * 50)
    
    # Find Claude config file
    claude_config_path = get_claude_config_path()
    print(f"\n5. Claude Desktop config location: {claude_config_path}")
    
    if claude_config_path.exists():
        print("\n⚠️  Claude Desktop config already exists.")
        update = input("Do you want to update it? (y/n): ").lower() == 'y'
        
        if update:
            # Load existing config
            with open(claude_config_path, 'r') as f:
                existing_config = json.load(f)
            
            # Merge configurations
            if "mcpServers" not in existing_config:
                existing_config["mcpServers"] = {}
            
            existing_config["mcpServers"]["ioflow-seed-manager"] = mcp_config["mcpServers"]["ioflow-seed-manager"]
            
            # Save updated config
            with open(claude_config_path, 'w') as f:
                json.dump(existing_config, f, indent=2)
            
            print("✅ Claude Desktop configuration updated!")
    else:
        # Create new config
        claude_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(claude_config_path, 'w') as f:
            json.dump(mcp_config, f, indent=2)
        
        print("✅ Claude Desktop configuration created!")
    
    print("\n6. Next Steps:")
    print("   1. Restart Claude Desktop")
    print("   2. In Claude, try: 'Show me all IOFlow seed applications'")
    print("   3. Or try: 'Use explore_seed_applications to list applications'")
    
    print("\n✅ Setup complete!")

if __name__ == "__main__":
    main()