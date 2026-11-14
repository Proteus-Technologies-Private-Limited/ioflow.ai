#!/usr/bin/env python3
"""
Remote MCP Client for IOFlow

This client allows Claude Desktop to connect to IOFlow's MCP functionality
over the network. It acts as a bridge between the MCP protocol expected by
Claude Desktop and the HTTP API exposed by IOFlow.

Usage:
    python remote_client.py --server-url http://ioflow-server:8000 --api-key ioflow_xxx

Or set environment variables:
    IOFLOW_SERVER_URL=http://ioflow-server:8000
    IOFLOW_API_KEY=ioflow_xxx
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

# Add backend to path for imports
backend_path = str(Path(__file__).parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

try:
    from mcp.server import Server
    from mcp.types import TextContent, ImageContent
    MCP_AVAILABLE = True
except ImportError:
    print("Error: MCP package not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
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
            
            logger.info(f"Connected to IOFlow MCP server: {self._server_info['name']}")
            logger.info(f"Available tools: {len(self._tools_info)}")
            logger.info(f"Available resources: {len(self._resources_info)}")
            
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
                # Check if this is markdown content
                if isinstance(result['result'], dict) and result['result'].get('content_type') == 'text/markdown':
                    # Return markdown content directly without JSON serialization
                    return TextContent(
                        type="text",
                        text=result['result']['content']
                    )
                # Check if the result is already a string
                elif isinstance(result['result'], str):
                    # Return string content directly
                    return TextContent(
                        type="text",
                        text=result['result']
                    )
                else:
                    # Return JSON-serialized content for dictionaries/lists
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
            logger.info("Importing MCP modules...")
            from mcp.server.stdio import stdio_server
            from mcp.server.models import InitializationOptions
            from mcp.server import NotificationOptions
            
            logger.info("Creating stdio server...")
            async with stdio_server() as (read_stream, write_stream):
                logger.info("Running server...")
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
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.client.aclose()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Remote MCP Client for IOFlow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Connect using command line arguments
  python remote_client.py --server-url http://192.168.1.100:7001 --api-key ioflow_xxx
  
  # Connect using environment variables
  export IOFLOW_SERVER_URL=http://192.168.1.100:8000
  export IOFLOW_API_KEY=ioflow_xxx
  python remote_client.py
  
  # For Claude Desktop configuration, add to config.json:
  {
    "mcpServers": {
      "ioflow-remote": {
        "command": "python",
        "args": ["/path/to/remote_client.py"],
        "env": {
          "IOFLOW_SERVER_URL": "http://your-server:7001",
          "IOFLOW_API_KEY": "your_api_key"
        }
      }
    }
  }
"""
    )
    
    parser.add_argument(
        '--server-url',
        default=os.getenv('IOFLOW_SERVER_URL', 'http://localhost:7001'),
        help='IOFlow server URL (default: $IOFLOW_SERVER_URL or http://localhost:8000)'
    )
    
    parser.add_argument(
        '--api-key',
        default=os.getenv('IOFLOW_API_KEY'),
        help='IOFlow API key (default: $IOFLOW_API_KEY)'
    )
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("Error: API key is required. Set IOFLOW_API_KEY or use --api-key", file=sys.stderr)
        sys.exit(1)
    
    # Create and initialize client
    client = RemoteMCPClient(args.server_url, args.api_key)
    
    try:
        await client.initialize()
        logger.info(f"Remote MCP client connected to {args.server_url}")
        await client.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())