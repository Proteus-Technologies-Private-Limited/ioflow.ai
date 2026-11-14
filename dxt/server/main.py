#!/usr/bin/env python3
"""
IOFlow MCP Server Remote Client for Claude Desktop DXT
Lightweight version using system Python and auto-installing dependencies

This client allows Claude Desktop to connect to IOFlow's MCP functionality
over the network via DXT package. It acts as a bridge between the MCP protocol
expected by Claude Desktop and the HTTP API exposed by IOFlow.
"""

import os
import sys
import json
import logging
import asyncio
import subprocess
from typing import Dict, Any, Optional, List
from pathlib import Path

def install_dependencies():
    """Install required packages if not available"""
    required_packages = ['mcp', 'httpx']
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            # Try to install packages - if this fails, we'll catch it in the import check below
            try:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--user', package], 
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                try:
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except subprocess.CalledProcessError:
                    # Installation failed - continue and let the import check catch it
                    pass

# Install dependencies on first run
install_dependencies()

try:
    import httpx
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.server.models import InitializationOptions
    from mcp.server import NotificationOptions
    from mcp.types import TextContent, Tool, Resource
    MCP_AVAILABLE = True
except ImportError as e:
    # Log the import error to a file for debugging
    error_log = Path.home() / ".ioflow-mcp-error.log"
    with open(error_log, 'w') as f:
        f.write(f"Import error: {e}\n")
        f.write(f"Python executable: {sys.executable}\n")
        f.write(f"Python version: {sys.version}\n")
        f.write(f"Python path: {sys.path}\n")
    sys.exit(1)

# Configure logging to a file to avoid stdout/stderr pollution
log_file = Path.home() / ".ioflow-mcp.log"
logging.basicConfig(
    level=logging.WARNING,  # Reduced logging level
    filename=str(log_file),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IOFlowRemoteMCPClient:
    """Remote MCP client that connects to IOFlow server over network (DXT version)"""
    
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
        self._initialized = False
        
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
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize remote MCP client: {e}")
            raise
    
    def _register_handlers(self):
        """Register MCP handlers"""
        # Register list_tools handler
        @self.server.list_tools()
        async def handle_list_tools() -> List[Dict[str, Any]]:
            """Return list of available tools"""
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
            
            response = await self.client.post("/api/mcp/tools/execute", json=request_data)
            response.raise_for_status()
            
            result = response.json()
            
            # Return result as TextContent
            if isinstance(result, dict):
                return TextContent(type="text", text=json.dumps(result, indent=2))
            else:
                return TextContent(type="text", text=str(result))
                
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            error_result = {
                "error": str(e),
                "tool": tool_name,
                "parameters": parameters
            }
            return TextContent(type="text", text=json.dumps(error_result, indent=2))
    
    async def _get_remote_resource(self, uri: str) -> TextContent:
        """Get a resource from the remote server"""
        try:
            response = await self.client.get(f"/api/mcp/resources/read?uri={uri}")
            response.raise_for_status()
            
            result = response.json()
            return TextContent(
                type="text", 
                text=result.get("content", "")
            )
            
        except Exception as e:
            logger.error(f"Error reading resource {uri}: {e}")
            return TextContent(type="text", text=f"Error reading resource: {e}")
    
    async def run(self):
        """Run the MCP server using stdio"""
        try:
            # Initialize connection to IOFlow first
            await self.initialize()
            
            # Run the server using stdio with proper initialization
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
            logger.error(f"Server error: {e}")
            raise
        finally:
            await self.client.aclose()


async def main():
    """Main entry point"""
    # Get configuration from environment variables
    server_url = os.getenv("IOFLOW_BASE_URL", "http://localhost:7001")
    api_key = os.getenv("IOFLOW_API_KEY")
    
    if not api_key:
        sys.exit(1)
    
    if not server_url:
        sys.exit(1)
    
    # Create and run the client
    client = IOFlowRemoteMCPClient(server_url, api_key)
    
    try:
        await client.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())