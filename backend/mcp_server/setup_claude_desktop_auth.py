#!/usr/bin/env python3
"""
Setup Claude Desktop Authentication for IOFlow MCP Server

This script helps configure Claude Desktop to work with IOFlow's MCP server
by setting up the proper authentication and configuration.
"""

import os
import json
import platform
from pathlib import Path

def get_claude_config_path():
    """Get the Claude Desktop configuration file path based on OS"""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        config_path = Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    else:  # Linux
        config_path = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    
    return config_path

def setup_claude_desktop():
    """Setup Claude Desktop configuration for IOFlow MCP server"""
    
    print("IOFlow MCP Server - Claude Desktop Setup")
    print("=" * 50)
    
    # Get API key
    api_key = input("\nEnter your IOFlow API key (should start with 'ioflow_'): ").strip()
    
    if not api_key.startswith("ioflow_"):
        print("\n⚠️  Warning: API key should start with 'ioflow_' prefix.")
        print("Please create an API key in IOFlow Settings → API Keys")
        return
    
    # Get backend URL
    backend_url = input("Enter IOFlow backend URL (default: http://localhost:8000): ").strip()
    if not backend_url:
        backend_url = "http://localhost:8000"
    
    # Get MCP server path
    default_server_path = str(Path(__file__).parent / "server.py")
    server_path = input(f"Enter MCP server path (default: {default_server_path}): ").strip()
    if not server_path:
        server_path = default_server_path
    
    # Create configuration
    config = {
        "mcpServers": {
            "ioflow": {
                "command": "python3",
                "args": [server_path],
                "env": {
                    "IOFLOW_API_KEY": api_key,
                    "IOFLOW_BASE_URL": backend_url,
                    "PYTHONPATH": str(Path(server_path).parent.parent)
                }
            }
        }
    }
    
    # Get config path
    config_path = get_claude_config_path()
    
    # Check if config already exists
    if config_path.exists():
        print(f"\n⚠️  Configuration file already exists at: {config_path}")
        
        # Load existing config
        with open(config_path, 'r') as f:
            existing_config = json.load(f)
        
        # Check if ioflow is already configured
        if "mcpServers" in existing_config and "ioflow" in existing_config["mcpServers"]:
            overwrite = input("IOFlow MCP server is already configured. Overwrite? (y/n): ").lower()
            if overwrite != 'y':
                print("Configuration cancelled.")
                return
        
        # Merge configurations
        if "mcpServers" not in existing_config:
            existing_config["mcpServers"] = {}
        existing_config["mcpServers"]["ioflow"] = config["mcpServers"]["ioflow"]
        config = existing_config
    
    # Create directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write configuration
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Configuration saved to: {config_path}")
    
    # Create a test script
    test_script_path = Path(__file__).parent / "test_mcp_connection.py"
    test_script = f'''#!/usr/bin/env python3
"""Test MCP connection to IOFlow"""
import os
import httpx
import asyncio

async def test_connection():
    api_key = "{api_key}"
    base_url = "{backend_url}"
    
    print("Testing IOFlow MCP connection...")
    print(f"Base URL: {{base_url}}")
    print(f"API Key: {{api_key[:20]}}...")
    
    async with httpx.AsyncClient() as client:
        headers = {{
            "Authorization": f"Bearer {{api_key}}",
            "Content-Type": "application/json"
        }}
        
        try:
            response = await client.get(f"{{base_url}}/api/v1/auth/me", headers=headers)
            if response.status_code == 200:
                user = response.json()
                print(f"\\n✅ Authentication successful!")
                print(f"User: {{user.get('email')}}")
                print(f"Role: {{user.get('role')}}")
            else:
                print(f"\\n❌ Authentication failed: {{response.status_code}}")
                print(f"Response: {{response.text}}")
        except Exception as e:
            print(f"\\n❌ Connection error: {{e}}")

if __name__ == "__main__":
    asyncio.run(test_connection())
'''
    
    with open(test_script_path, 'w') as f:
        f.write(test_script)
    
    os.chmod(test_script_path, 0o755)
    
    print(f"\n📝 Test script created: {test_script_path}")
    print("\nTo test the connection, run:")
    print(f"python3 {test_script_path}")
    
    print("\n🔄 Next steps:")
    print("1. Restart Claude Desktop")
    print("2. Look for 'ioflow' in the MCP connections")
    print("3. Try: 'List all seed applications in IOFlow'")
    
    print("\n💡 Troubleshooting:")
    print("- Ensure IOFlow backend is running")
    print("- Check Claude Desktop logs for errors")
    print("- Verify your API key has the correct permissions")

if __name__ == "__main__":
    setup_claude_desktop()