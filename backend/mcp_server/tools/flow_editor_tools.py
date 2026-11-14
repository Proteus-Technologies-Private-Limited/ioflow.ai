"""
Flow Editor Tools for MCP Server

This module contains MCP tools for editing existing flow designs.
These tools enable the flow editor agent to load, modify, and debug flows.
All tools call the MCP bridge API to ensure consistent architecture.
"""

import json
import logging
import httpx
from typing import Dict, Any, Optional

from mcp_server.tools.base_tool import BaseMCPTool, AuthenticationError

logger = logging.getLogger(__name__)


# ============================================================================
# Flow Editor MCP Tools
# ============================================================================

class GetFlowByIdTool(BaseMCPTool):
    """Get flow by ID"""
    name = "get_flow_by_id"
    description = """Get complete flow configuration by flow ID.

    Args:
        flow_id: Flow ID (UUID)

    Returns:
        Complete flow JSON including definition, trigger config, and metadata
    """

    async def run(self, flow_id: str) -> str:
        """Get flow by ID via MCP Bridge API"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "get_flow_by_id",
                    "parameters": {"flow_id": flow_id}
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting flow by ID: {e}")
            return json.dumps({"error": str(e)})


class GetFlowByNameTool(BaseMCPTool):
    """Get flow by name"""
    name = "get_flow_by_name"
    description = """Get flow by name for the authenticated user.

    Args:
        flow_name: Name of the flow

    Returns:
        Complete flow JSON
    """

    async def run(self, flow_name: str) -> str:
        """Get flow by name via MCP Bridge API"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "get_flow_by_name",
                    "parameters": {"flow_name": flow_name}
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting flow by name: {e}")
            return json.dumps({"error": str(e)})


class ReplaceNodeInFlowTool(BaseMCPTool):
    """Replace a specific node in an existing flow"""
    name = "replace_node_in_flow"
    description = """Replace a specific node in an existing flow.

    Pass the complete node JSON with all required fields.
    This operation modifies the flow in the database.

    Args:
        flow_id: Flow ID (UUID)
        node_id: Node ID to replace (e.g., "action_1", "trigger_1")
        node_json: Complete node JSON as string or dict

    Returns:
        Updated flow definition
    """

    async def run(self, flow_id: str, node_id: str, node_json: str) -> str:
        """Replace node via MCP Bridge API"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "replace_node_in_flow",
                    "parameters": {
                        "flow_id": flow_id,
                        "node_id": node_id,
                        "node_json": node_json
                    }
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error replacing node: {e}")
            return json.dumps({"error": str(e)})


class AddNodeToFlowTool(BaseMCPTool):
    """Add a new node to an existing flow"""
    name = "add_node_to_flow"
    description = """Add a new node to an existing flow with auto-connection.

    Args:
        flow_id: Flow ID (UUID)
        node_json: Complete node JSON as string or dict
        position: Where to add - "after_last", "after_trigger", or a specific node_id

    Returns:
        Updated flow definition with new node and edges
    """

    async def run(self, flow_id: str, node_json: str, position: str = "after_last") -> str:
        """Add node via MCP Bridge API"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "add_node_to_flow",
                    "parameters": {
                        "flow_id": flow_id,
                        "node_json": node_json,
                        "position": position
                    }
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error adding node: {e}")
            return json.dumps({"error": str(e)})


class RemoveNodeFromFlowTool(BaseMCPTool):
    """Remove a node from an existing flow"""
    name = "remove_node_from_flow"
    description = """Remove a node from an existing flow.

    Args:
        flow_id: Flow ID (UUID)
        node_id: Node ID to remove
        reconnect: Auto-reconnect edges after removal (default: True)

    Returns:
        Updated flow definition
    """

    async def run(self, flow_id: str, node_id: str, reconnect: bool = True) -> str:
        """Remove node via MCP Bridge API"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "remove_node_from_flow",
                    "parameters": {
                        "flow_id": flow_id,
                        "node_id": node_id,
                        "reconnect": reconnect
                    }
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error removing node: {e}")
            return json.dumps({"error": str(e)})


class UpdateEdgeInFlowTool(BaseMCPTool):
    """Update or add an edge connection in a flow"""
    name = "update_edge_in_flow"
    description = """Update or add an edge connection in a flow.

    Args:
        flow_id: Flow ID (UUID)
        edge_json: Edge JSON with source, target, sourceHandle, targetHandle

    Returns:
        Updated flow definition
    """

    async def run(self, flow_id: str, edge_json: str) -> str:
        """Update edge via MCP Bridge API"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "update_edge_in_flow",
                    "parameters": {
                        "flow_id": flow_id,
                        "edge_json": edge_json
                    }
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error updating edge: {e}")
            return json.dumps({"error": str(e)})


class GetExecutionLogsTool(BaseMCPTool):
    """Get execution logs for debugging failed flows"""
    name = "get_execution_logs"
    description = """Get execution logs for debugging failed executions.

    Logs include timestamps, levels (INFO, ERROR, etc.), messages, and data.
    Use this to identify which nodes failed and why.

    Args:
        execution_id: Execution ID (UUID)
        include_data: Include full log data (default: True)
        limit: Maximum number of logs to return (default: 500)

    Returns:
        List of log entries with details
    """

    async def run(self, execution_id: str, include_data: bool = True, limit: int = 500) -> str:
        """Get execution logs via MCP Bridge API"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "get_execution_logs",
                    "parameters": {
                        "execution_id": execution_id,
                        "include_data": include_data,
                        "limit": limit
                    }
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting execution logs: {e}")
            return json.dumps({"error": str(e)})


class GetExecutionDetailsTool(BaseMCPTool):
    """Get execution details including status and results"""
    name = "get_execution_details"
    description = """Get execution details including status, results, and metadata.

    Args:
        execution_id: Execution ID (UUID)

    Returns:
        Execution details with status, trigger data, results, and flow info
    """

    async def run(self, execution_id: str) -> str:
        """Get execution details via MCP Bridge API"""
        try:
            await self.ensure_authenticated()

            async with httpx.AsyncClient(timeout=60.0) as client:
                url = f"{self.base_url}/api/mcp/tools/execute"
                payload = {
                    "tool": "get_execution_details",
                    "parameters": {"execution_id": execution_id}
                }

                response = await client.post(url, json=payload, headers=self.get_headers())
                response.raise_for_status()

                result = response.json()
                if result.get("success"):
                    return json.dumps(result.get("result", {}))
                else:
                    return json.dumps({"error": result.get("error", "Tool execution failed")})
        except Exception as e:
            logger.error(f"Error getting execution details: {e}")
            return json.dumps({"error": str(e)})


# ============================================================================
# Export all tool classes
# ============================================================================

FLOW_EDITOR_TOOLS = [
    GetFlowByIdTool,
    GetFlowByNameTool,
    ReplaceNodeInFlowTool,
    AddNodeToFlowTool,
    RemoveNodeFromFlowTool,
    UpdateEdgeInFlowTool,
    GetExecutionLogsTool,
    GetExecutionDetailsTool,
]
