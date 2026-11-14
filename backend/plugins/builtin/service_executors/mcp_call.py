"""MCP Call service executor plugin."""
from plugins.registry import PluginRegistry
from services.service_executors import MCPCallExecutor

PluginRegistry.register_service_executor("mcp_call", MCPCallExecutor)
