#!/usr/bin/env python3
"""IOFlow MCP Server - Simplified version"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

# Configure logging to stderr to avoid interfering with stdio
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
backend_path = str(Path(__file__).parent.parent)
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Import MCP SDK
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    logger.error("MCP SDK not installed. Install with: pip install mcp")
    sys.exit(1)

# Import IOFlow components
try:
    from api.seed_applications import SeedApplicationResponse
    from schemas.seed_schemas import CreateSeedApplicationRequest
    import httpx
except ImportError as e:
    logger.error(f"Failed to import IOFlow components: {e}")
    # Continue with limited functionality

# Create the MCP server
mcp = FastMCP("ioflow-seed-manager")

# Get configuration from environment
API_KEY = os.getenv("IOFLOW_API_KEY")
BASE_URL = os.getenv("IOFLOW_BASE_URL", "http://localhost:7001")

# Create HTTP client
client = httpx.AsyncClient(
    base_url=BASE_URL,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    } if API_KEY else {}
)

@mcp.tool()
async def list_seed_applications():
    """List all available seed applications from IOFlow backend"""
    try:
        logger.info("Fetching seed applications from IOFlow backend")
        response = await client.get("/api/seed-applications/list")
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "applications": data.get("applications", []),
                "total": data.get("total", 0)
            }
        else:
            logger.error(f"Failed to fetch applications: {response.status_code}")
            return {
                "success": False,
                "error": f"Failed to fetch applications: {response.text}"
            }
    except Exception as e:
        logger.error(f"Error listing applications: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def get_seed_application(application_key: str):
    """Get details of a specific seed application"""
    try:
        logger.info(f"Fetching seed application: {application_key}")
        response = await client.get(f"/api/seed-applications/{application_key}")
        
        if response.status_code == 200:
            return {
                "success": True,
                "application": response.json()
            }
        elif response.status_code == 404:
            return {
                "success": False,
                "error": f"Application '{application_key}' not found"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to fetch application: {response.text}"
            }
    except Exception as e:
        logger.error(f"Error fetching application {application_key}: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def create_seed_application(
    app_key: str,
    app_name: str,
    description: str = "",
    category: str = "Integration",
    auth_type: str = "api_key"
):
    """Create a new seed application in IOFlow"""
    try:
        logger.info(f"Creating seed application: {app_key}")
        
        # Create request payload
        payload = {
            "app_key": app_key,
            "app_name": app_name,
            "description": description,
            "category": category,
            "auth_type": auth_type,
            "app_type": "global",
            "version": "1.0.0"
        }
        
        response = await client.post("/api/seed-applications/create", json=payload)
        
        if response.status_code == 200:
            return {
                "success": True,
                "application": response.json()
            }
        else:
            return {
                "success": False,
                "error": f"Failed to create application: {response.text}"
            }
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@mcp.tool()
async def delete_seed_application(app_key: str):
    """Delete a seed application from IOFlow"""
    try:
        logger.info(f"Deleting seed application: {app_key}")
        response = await client.delete(f"/api/seed-applications/{app_key}")
        
        if response.status_code == 200:
            return {
                "success": True,
                "message": f"Application '{app_key}' deleted successfully"
            }
        else:
            return {
                "success": False,
                "error": f"Failed to delete application: {response.text}"
            }
    except Exception as e:
        logger.error(f"Error deleting application: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# Clean up client on shutdown
async def cleanup():
    """Clean up resources"""
    await client.aclose()

# Run the server
if __name__ == "__main__":
    logger.info("Starting IOFlow MCP Server")
    logger.info(f"Backend URL: {BASE_URL}")
    logger.info(f"API Key configured: {'Yes' if API_KEY else 'No'}")
    
    if not API_KEY:
        logger.warning("No API key configured. Some operations may fail.")
    
    try:
        # Run the server (default transport is stdio)
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
    finally:
        # Run cleanup
        asyncio.run(cleanup())