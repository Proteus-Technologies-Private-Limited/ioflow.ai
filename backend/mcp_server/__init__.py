"""
IOFlow MCP Server

A comprehensive Model Context Protocol (MCP) server for managing IOFlow seed applications.
Enables external LLM applications to discover, create, edit, test, and deploy seed applications.

Main Components:
- Exploration Tools: Discover and explore seed applications
- Management Tools: Create and edit seed applications
- Testing Tools: Validate and test applications
- Deployment Tools: Install and manage deployments

Usage:
    python -m mcp_server
    
Or directly:
    python mcp_server/ioflow_mcp_server.py
"""

from .ioflow_mcp_server import IOFlowMCPServer

__version__ = "1.0.0"
__all__ = ["IOFlowMCPServer"]