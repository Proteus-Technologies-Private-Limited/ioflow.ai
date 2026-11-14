#!/bin/bash

# IOFlow MCP Remote Installer
# Installs IOFlow MCP server on remote Claude Desktop instances

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
MCP_SERVER_DIR="$HOME/.ioflow-mcp"
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

log() { echo -e "${BLUE}ℹ️  $1${NC}"; }
success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║           IOFlow MCP Remote Installer            ║"
    echo "║        Connect Claude Desktop to IOFlow          ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if Claude Desktop is installed
    if [ ! -d "/Applications/Claude.app" ]; then
        error "Claude Desktop is not installed. Please install it first."
        echo "Download from: https://claude.ai/download"
        exit 1
    fi
    
    # Check for Python 3.10+
    PYTHON_CMD=""
    for py in python3.12 python3.11 python3.10; do
        if command -v "$py" >/dev/null 2>&1; then
            PYTHON_CMD="$py"
            PYTHON_VERSION=$("$py" --version | cut -d' ' -f2)
            break
        fi
    done
    
    if [ -z "$PYTHON_CMD" ]; then
        error "Python 3.10+ is required for IOFlow MCP."
        echo "Please install Python 3.10 or newer from:"
        echo "- https://www.python.org/downloads/"
        echo "- Or using Homebrew: brew install python@3.12"
        exit 1
    fi
    
    success "Prerequisites checked - Python $PYTHON_VERSION found"
}

get_server_config() {
    log "Getting IOFlow server configuration..."
    
    echo
    echo -e "${YELLOW}📋 IOFlow Server Information Needed:${NC}"
    echo "You need the URL and API key for your IOFlow server."
    echo
    
    # Get IOFlow server URL
    read -p "Enter IOFlow server URL (e.g., https://your-ioflow.com:7001): " IOFLOW_URL
    
    if [ -z "$IOFLOW_URL" ]; then
        error "IOFlow server URL is required."
        exit 1
    fi
    
    # Get API key
    read -p "Enter IOFlow API key (e.g., ioflow_xxx): " IOFLOW_API_KEY
    
    if [ -z "$IOFLOW_API_KEY" ]; then
        error "IOFlow API key is required."
        exit 1
    fi
    
    # Test connectivity
    log "Testing connection to IOFlow server..."
    
    HTTP_STATUS=$(curl -s -w "%{http_code}" -H "Authorization: Bearer $IOFLOW_API_KEY" \
                  "$IOFLOW_URL/api/mcp/info" -o /dev/null || echo "000")
    
    if [ "$HTTP_STATUS" = "200" ]; then
        success "Successfully connected to IOFlow server"
    elif [ "$HTTP_STATUS" = "401" ]; then
        error "Authentication failed. Please check your API key."
        exit 1
    elif [ "$HTTP_STATUS" = "000" ]; then
        error "Cannot reach IOFlow server. Please check the URL."
        exit 1
    else
        warning "Server responded with HTTP $HTTP_STATUS. Continuing anyway..."
    fi
    
    success "Configuration collected"
}

install_mcp_server() {
    log "Installing IOFlow MCP server..."
    
    # Clean previous installation
    if [ -d "$MCP_SERVER_DIR" ]; then
        warning "Removing previous installation..."
        rm -rf "$MCP_SERVER_DIR"
    fi
    
    # Create directory
    mkdir -p "$MCP_SERVER_DIR"
    
    # Create main.py
    cat > "$MCP_SERVER_DIR/main.py" << 'EOF'
#!/usr/bin/env python3
"""
IOFlow MCP Remote Client
Connects Claude Desktop to IOFlow server over network
"""

import os
import sys
import json
import logging
import argparse
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from pathlib import Path

try:
    from mcp.server import Server
    from mcp.types import TextContent, ImageContent
    MCP_AVAILABLE = True
except ImportError:
    print("Error: MCP package not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Configure logging to file to avoid stdout/stderr pollution
log_file = Path.home() / ".ioflow-mcp.log"
logging.basicConfig(
    level=logging.WARNING,  # Reduced logging level
    filename=str(log_file),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RemoteMCPClient:
    """Remote MCP client that connects to IOFlow server over network"""
    
    def __init__(self, server_url: str, api_key: str):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.server = Server("ioflow-remote")
        self.client = httpx.AsyncClient(
            base_url=self.server_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0
        )
        
        # Get server info to register tools dynamically
        self._server_info = None
        self._tools_info = []
        self._resources_info = []
        self._tools_map = {}  # Map tool names to their info
        
    async def initialize(self):
        """Initialize the client and fetch server capabilities"""
        try:
            # Get server info
            response = await self.client.get("/api/mcp/info")
            response.raise_for_status()
            self._server_info = response.json()
            
            # Get tools list
            response = await self.client.get("/api/mcp/tools")
            response.raise_for_status()
            self._tools_info = response.json()
            
            # Get resources list
            response = await self.client.get("/api/mcp/resources")
            response.raise_for_status()
            self._resources_info = response.json()
            
            # Build tools map
            for tool in self._tools_info:
                self._tools_map[tool['name']] = tool
            
            # Register handlers with the server
            self._register_handlers()
            
        except Exception as e:
            logger.error(f"Failed to initialize remote MCP client: {e}")
            raise
    
    def _register_handlers(self):
        """Register MCP handlers"""
        # Register list_tools handler
        @self.server.list_tools()
        async def handle_list_tools() -> List[Dict[str, Any]]:
            """Return list of available tools"""
            from mcp.types import Tool
            tools = []
            for tool_info in self._tools_info:
                tools.append(Tool(
                    name=tool_info['name'],
                    description=tool_info.get('description', ''),
                    inputSchema=tool_info.get('input_schema', {"type": "object", "properties": {}})
                ))
            return tools
        
        # Register call_tool handler
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> List[TextContent]:
            """Execute a tool and return results"""
            return [await self._execute_remote_tool(name, arguments or {})]
        
        # Register list_resources handler
        @self.server.list_resources()
        async def handle_list_resources() -> List[Dict[str, Any]]:
            """Return list of available resources"""
            from mcp.types import Resource
            resources = []
            for resource_info in self._resources_info:
                resources.append(Resource(
                    uri=resource_info['uri'],
                    name=resource_info.get('name', resource_info['uri']),
                    description=resource_info.get('description', ''),
                    mimeType=resource_info.get('mime_type', 'text/plain')
                ))
            return resources
        
        # Register read_resource handler
        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> TextContent:
            """Read a resource by URI"""
            return await self._get_remote_resource(uri)
    
    async def _execute_remote_tool(self, tool_name: str, parameters: Dict[str, Any]) -> TextContent:
        """Execute a tool on the remote server"""
        try:
            request_data = {
                "tool": tool_name,
                "parameters": parameters
            }
            
            response = await self.client.post(
                "/api/mcp/tools/execute",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result['success']:
                # Return the result as TextContent
                return TextContent(
                    type="text",
                    text=json.dumps(result['result'], indent=2)
                )
            else:
                # Return error as TextContent
                return TextContent(
                    type="text",
                    text=f"Error: {result['error']}"
                )
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error executing tool {tool_name}: {e}")
            return TextContent(
                type="text",
                text=f"HTTP Error {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )
    
    async def _get_remote_resource(self, uri: str) -> TextContent:
        """Get a resource from the remote server"""
        try:
            request_data = {"uri": uri}
            
            response = await self.client.post(
                "/api/mcp/resources/get",
                json=request_data
            )
            response.raise_for_status()
            
            result = response.json()
            
            if result['success']:
                # Return the content as TextContent
                return TextContent(
                    type="text",
                    text=json.dumps(result['content'], indent=2)
                )
            else:
                # Return error as TextContent
                return TextContent(
                    type="text",
                    text=f"Error: {result['error']}"
                )
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting resource {uri}: {e}")
            return TextContent(
                type="text",
                text=f"HTTP Error {e.response.status_code}: {e.response.text}"
            )
        except Exception as e:
            logger.error(f"Error getting resource {uri}: {e}")
            return TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )
    
    async def run(self):
        """Run the MCP server"""
        try:
            from mcp.server.stdio import stdio_server
            from mcp.server.models import InitializationOptions
            from mcp.server import NotificationOptions
            
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name="ioflow-remote",
                        server_version="1.0.0",
                        capabilities=self.server.get_capabilities(
                            notification_options=NotificationOptions(),
                            experimental_capabilities={}
                        )
                    )
                )
        except Exception as e:
            logger.error(f"Error in run method: {e}")
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.client.aclose()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Remote MCP Client for IOFlow")
    
    parser.add_argument(
        '--server-url',
        default=os.getenv('IOFLOW_BASE_URL', os.getenv('IOFLOW_SERVER_URL', 'http://localhost:7001')),
        help='IOFlow server URL (default: $IOFLOW_BASE_URL or http://localhost:7001)'
    )
    
    parser.add_argument(
        '--api-key',
        default=os.getenv('IOFLOW_API_KEY'),
        help='IOFlow API key (default: $IOFLOW_API_KEY)'
    )
    
    args = parser.parse_args()
    
    if not args.api_key:
        sys.exit(1)
    
    # Create and initialize client
    client = RemoteMCPClient(args.server_url, args.api_key)
    
    try:
        await client.initialize()
        await client.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
EOF
    
    # Create requirements.txt
    cat > "$MCP_SERVER_DIR/requirements.txt" << 'EOF'
mcp>=1.0.0
httpx>=0.25.0
typing-extensions>=4.8.0
EOF
    
    # Create virtual environment
    cd "$MCP_SERVER_DIR"
    log "Creating Python virtual environment with $PYTHON_CMD..."
    "$PYTHON_CMD" -m venv venv
    
    # Install dependencies
    log "Installing MCP dependencies..."
    source venv/bin/activate
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    
    success "IOFlow MCP server installed"
}

update_claude_config() {
    log "Updating Claude Desktop configuration..."
    
    # Create Claude support directory if needed
    mkdir -p "$(dirname "$CLAUDE_CONFIG")"
    
    # Backup existing config
    if [ -f "$CLAUDE_CONFIG" ]; then
        cp "$CLAUDE_CONFIG" "$CLAUDE_CONFIG.backup.$(date +%Y%m%d_%H%M%S)"
        log "Backed up existing Claude configuration"
    fi
    
    # Create or update configuration
    if [ -f "$CLAUDE_CONFIG" ]; then
        # Update existing config
        python3 -c "
import json
import sys

config_file = '$CLAUDE_CONFIG'
with open(config_file, 'r') as f:
    config = json.load(f)

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['ioflow'] = {
    'command': '$MCP_SERVER_DIR/venv/bin/python',
    'args': ['$MCP_SERVER_DIR/main.py'],
    'env': {
        'IOFLOW_BASE_URL': '$IOFLOW_URL',
        'IOFLOW_API_KEY': '$IOFLOW_API_KEY'
    }
}

with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print('Configuration updated successfully')
"
    else
        # Create new config
        cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "ioflow": {
      "command": "$MCP_SERVER_DIR/venv/bin/python",
      "args": ["$MCP_SERVER_DIR/main.py"],
      "env": {
        "IOFLOW_BASE_URL": "$IOFLOW_URL",
        "IOFLOW_API_KEY": "$IOFLOW_API_KEY"
      }
    }
  }
}
EOF
    fi
    
    success "Claude Desktop configuration updated"
}

test_installation() {
    log "Testing IOFlow MCP installation..."
    
    cd "$MCP_SERVER_DIR"
    
    log "Testing connection to $IOFLOW_URL with provided credentials..."
    
    # Test the server can start and connect using the user-provided URL and API key
    # We run it for 3 seconds - if it connects successfully, it will show connection logs
    # If it fails, it will exit with an error before that
    IOFLOW_BASE_URL="$IOFLOW_URL" \
    IOFLOW_API_KEY="$IOFLOW_API_KEY" \
    timeout 3s ./venv/bin/python main.py > /tmp/ioflow-test.log 2>&1 &
    
    SERVER_PID=$!
    sleep 2
    
    # Check if the process is still running (good sign) or if it logged successful connection
    if kill -0 $SERVER_PID 2>/dev/null || grep -q "Connected to IOFlow MCP server" /tmp/ioflow-test.log 2>/dev/null; then
        kill $SERVER_PID 2>/dev/null || true
        
        # Check for successful connection in logs
        if grep -q "Connected to IOFlow MCP server" /tmp/ioflow-test.log 2>/dev/null; then
            TOOL_COUNT=$(grep "Available tools:" /tmp/ioflow-test.log 2>/dev/null | sed 's/.*: //' || echo "unknown")
            success "IOFlow MCP server connected successfully to $IOFLOW_URL ($TOOL_COUNT tools available)"
        else
            success "IOFlow MCP server started successfully for $IOFLOW_URL"
        fi
        
        rm -f /tmp/ioflow-test.log
        return 0
    else
        # Check error logs
        if [ -f /tmp/ioflow-test.log ]; then
            if grep -q "nodename nor servname provided" /tmp/ioflow-test.log; then
                error "Invalid server URL: $IOFLOW_URL"
                log "Please check the URL format (e.g., https://your-server.com:7001)"
            elif grep -q "401" /tmp/ioflow-test.log; then
                error "Authentication failed - invalid API key"
            elif grep -q "Connection refused\|Network is unreachable" /tmp/ioflow-test.log; then
                error "Cannot reach server at $IOFLOW_URL"
                log "Please verify the server is running and accessible"
            else
                error "IOFlow MCP server failed to connect to $IOFLOW_URL"
                log "Error details:"
                tail -3 /tmp/ioflow-test.log | while read line; do log "  $line"; done
            fi
        else
            error "IOFlow MCP server failed to start"
        fi
        
        rm -f /tmp/ioflow-test.log
        return 1
    fi
}

print_success() {
    echo
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════╗"
    echo "║              INSTALLATION COMPLETE!             ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    success "IOFlow MCP is now connected to Claude Desktop!"
    echo
    echo -e "${BLUE}📋 What was installed:${NC}"
    echo "  • IOFlow MCP server at: $MCP_SERVER_DIR"
    echo "  • Python virtual environment with MCP packages"
    echo "  • Claude Desktop configuration updated"
    echo "  • Connected to: $IOFLOW_URL"
    echo
    echo -e "${BLUE}🚀 Next Steps:${NC}"
    echo "  1. Restart Claude Desktop for changes to take effect"
    echo "  2. IOFlow tools will appear in Claude Desktop"
    echo "  3. Ask Claude to use IOFlow functionality!"
    echo
    echo -e "${YELLOW}📝 Notes:${NC}"
    echo "  • Configuration backed up as: $CLAUDE_CONFIG.backup.*"
    echo "  • To uninstall: rm -rf $MCP_SERVER_DIR"
    echo "  • For support: Check IOFlow documentation"
    echo
    echo -e "${GREEN}🎉 You can now use IOFlow tools in Claude Desktop!${NC}"
    echo
}

main() {
    print_header
    
    check_prerequisites
    get_server_config
    install_mcp_server
    update_claude_config
    
    if test_installation; then
        print_success
    else
        error "Installation test failed for $IOFLOW_URL"
        echo
        echo -e "${YELLOW}🔧 Installation completed, but connection test failed.${NC}"
        echo "The MCP server is installed and configured, but cannot connect to your IOFlow server."
        echo
        echo -e "${BLUE}Possible solutions:${NC}"
        echo "  • Verify IOFlow server is running at: $IOFLOW_URL"
        echo "  • Check API key is correct: ${IOFLOW_API_KEY:0:12}..."
        echo "  • Ensure this machine can reach the IOFlow server"
        echo "  • Check firewall settings"
        echo "  • Try restarting Claude Desktop anyway - it might work"
        echo
        echo -e "${GREEN}Installation files are ready at: $MCP_SERVER_DIR${NC}"
        exit 1
    fi
}

# Run main function
main "$@"