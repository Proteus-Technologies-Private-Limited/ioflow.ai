"""
MCP Bridge API - Exposes MCP functionality over network via FastAPI

This module bridges the MCP server capabilities to make them accessible
over the network through FastAPI endpoints, allowing remote Claude Desktop
instances to access IOFlow's MCP functionality.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import contextvars
import json
import logging
import httpx
from sqlalchemy.orm import Session

from db.database import get_db
from api.auth import get_current_user
from db.models import User
from mcp_server.auth.mcp_auth import MCPAuthHandler
from mcp_server.auth.enhanced_mcp_auth import EnhancedMCPAuthHandler
from core.config import settings
from mcp_server.tools.exploration_tools import ExplorationTools
from mcp_server.tools.management_tools import ManagementTools
from mcp_server.tools.testing_tools import TestingTools
from mcp_server.tools.deployment_tools import DeploymentTools
from mcp_server.tools.documentation_tools import DocumentationTools
from mcp_server.tools.flow_design_tools import FLOW_DESIGN_TOOLS
from mcp_server.tools.flow_design_tools_v2 import FLOW_DESIGN_TOOLS_V2
from mcp_server.tools.flow_design_assistant import FLOW_DESIGN_ASSISTANT_TOOLS
from mcp_server.tools.flow_design_management import FlowDesignManagement
from services.json_seed_manager import JsonSeedManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request-scoped authentication
#
# One MCPBridgeService (and one instance of every tool class) serves every
# caller. Execution used to hand each request's auth handler to those shared
# objects by assignment (``tool.auth = handler``), so two concurrent requests
# could swap identities half way through a tool call — one tenant's agent
# acting as another. The handler now lives in a ContextVar, which asyncio gives
# every request task its own copy of; the ``auth`` / ``auth_handler``
# attributes of the shared objects read it from there. An assignment outside a
# request (construction) is kept as the fallback for code running with no
# request in progress, such as the stdio server.
# ---------------------------------------------------------------------------
_REQUEST_AUTH: contextvars.ContextVar = contextvars.ContextVar("mcp_bridge_request_auth", default=None)


class _RequestScopedAuth:
    """Data descriptor: the current request's auth handler, else the instance fallback."""

    def __init__(self, name: str):
        self.slot = f"_{name}_fallback"

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        current = _REQUEST_AUTH.get()
        return current if current is not None else obj.__dict__.get(self.slot)

    def __set__(self, obj, value):
        obj.__dict__[self.slot] = value


def _scope_auth_attributes(obj) -> None:
    """Route ``obj.auth`` / ``obj.auth_handler`` through the request ContextVar."""
    if obj is None:
        return
    cls = type(obj)
    for name in ("auth", "auth_handler"):
        if name not in obj.__dict__ and not isinstance(cls.__dict__.get(name), _RequestScopedAuth):
            continue
        if not isinstance(cls.__dict__.get(name), _RequestScopedAuth):
            setattr(cls, name, _RequestScopedAuth(name))
        if name in obj.__dict__:
            obj.__dict__[f"_{name}_fallback"] = obj.__dict__.pop(name)


# Tools that write the GLOBAL seed catalog (files every tenant shares) or
# install/remove global applications. The REST endpoints behind most of them
# already require an instance admin; the registry tools write the files
# in-process, so the bridge enforces the same rule for all of them. A tenant
# manages its own connectors with the *_tenant_seed_application tools.
GLOBAL_CATALOG_WRITE_TOOLS = frozenset({
    "create_seed_application",
    "edit_application_metadata",
    "add_service_to_application",
    "remove_service_from_application",
    "add_event_to_application",
    "update_auth_configuration",
    "delete_seed_application",
    "duplicate_application",
    "install_application",
    "uninstall_application",
    "update_installed_application",
    "rollback_application",
    "load_seed_application",
})


def _caller_role(auth_handler) -> str:
    info = getattr(auth_handler, "user_info", None) or {}
    role = info.get("role") or ""
    if hasattr(role, "value"):
        role = role.value
    role = str(role)
    return role.replace("UserRole.", "")


router = APIRouter(prefix="/api/mcp", tags=["MCP Bridge"])


# Request/Response Models
class MCPToolRequest(BaseModel):
    """Generic MCP tool request model"""
    tool: str = Field(..., description="The MCP tool name to execute")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class MCPToolResponse(BaseModel):
    """Generic MCP tool response model"""
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    tool: str
    execution_time: Optional[float] = None


class MCPResourceRequest(BaseModel):
    """MCP resource request model"""
    uri: str = Field(..., description="Resource URI to fetch")


class MCPResourceResponse(BaseModel):
    """MCP resource response model"""
    success: bool
    uri: str
    content: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MCPServerInfo(BaseModel):
    """MCP server information"""
    name: str = "ioflow-seed-manager"
    version: str = "1.0.0"
    description: str = "IOFlow MCP Server for Seed Application Management"
    capabilities: Dict[str, List[str]]
    tool_count: int
    authentication_required: bool = True


class MCPBridgeService:
    """Service class to handle MCP operations"""
    
    def __init__(self):
        self.seed_manager = JsonSeedManager()
        self._tool_registry = {}
        self._resource_registry = {}
        self._initialize_tools()
        self._scope_shared_auth()

    def _scope_shared_auth(self) -> None:
        """Make every shared object's auth attribute request-scoped (see _RequestScopedAuth)."""
        # The closures registered above read ``self.auth_handler``.
        if not isinstance(type(self).__dict__.get("auth_handler"), _RequestScopedAuth):
            type(self).auth_handler = _RequestScopedAuth("auth_handler")
        _scope_auth_attributes(self)
        seen = set()
        candidates = [getattr(f, "__self__", None) for f in self._tool_registry.values()]
        candidates += list(getattr(self, "flow_design_tools", []) or [])
        candidates += list(getattr(self, "flow_design_tools_v2", []) or [])
        candidates.append(getattr(self, "flow_wrapper", None))
        candidates.append(getattr(self, "exploration", None))
        for obj in candidates:
            if obj is None or id(obj) in seen or obj is self:
                continue
            seen.add(id(obj))
            _scope_auth_attributes(obj)
    
    def _initialize_tools(self):
        """Initialize and register all MCP tools"""
        # Store API wrapper tool names for dynamic creation
        self._api_wrapper_tools = [
            "validate_flow_design",
            "validate_flow_comprehensive",  # Handles base64-encoded JSON with proper error messages
            "list_applications",
            "search_applications",
            "search_services",
            "search_flows",
            "get_application_services_list",
            "get_service_information",
            "get_application_events_list",
            "get_event_information",
            "load_seed_application",
            "get_flow_design_structure",
            "get_flow_design_guideline",
            "get_condition_node_guide",
            "get_transform_node_guide",
            "get_loop_node_guide",
            "get_hitl_node_guide",
            "get_trigger_node_guide",
            "get_parameter_mapping_guide",
            "get_variable_reference_guide",
            "get_node_examples",
            "get_pdf_generation_guide",
            "validate_node_configuration",
            # Seed application tools
            "list_seed_applications",
            "create_seed_application",
            "get_all_seed_applications_raw",
            # Seed application guide tools
            "get_seed_application_guide",
            "get_service_guide",
            "get_event_guide",
            # Tenant seed application tools (a tenant's own connectors)
            "list_tenant_seed_applications",
            "get_tenant_seed_application",
            "validate_tenant_seed_application",
            "save_tenant_seed_application",
            "install_tenant_seed_application",
            "delete_tenant_seed_application",
        ]
        
        # Temporary auth handler - will be replaced per request
        temp_auth = MCPAuthHandler(settings.api_url, None)
        
        # Initialize tool classes and store exploration tools for later use
        self.exploration = ExplorationTools(self.seed_manager, temp_auth)
        exploration = self.exploration  # Keep local reference for backward compatibility
        management = ManagementTools(self.seed_manager, temp_auth)
        testing = TestingTools(self.seed_manager, temp_auth)
        deployment = DeploymentTools(self.seed_manager, temp_auth)
        documentation = DocumentationTools()
        
        # Register exploration tools
        self._tool_registry.update({
            "explore_seed_applications": exploration.list_seed_applications,
            "get_seed_application": exploration.get_application_details,
            "get_sample_application": exploration.get_sample_by_criteria,
            "explain_application_schema": exploration.explain_schema_field,
            "get_application_categories": exploration.get_categories,
        })
        
        # Register management tools
        self._tool_registry.update({
            "create_seed_application": management.create_seed_application,
            "edit_application_metadata": management.edit_application_metadata,
            "add_service_to_application": management.add_service_to_application,
            "remove_service_from_application": management.remove_service_from_application,
            "add_event_to_application": management.add_event_to_application,
            "update_auth_configuration": management.update_auth_configuration,
            "delete_seed_application": management.delete_seed_application,
            "duplicate_application": management.duplicate_application,
        })
        
        # Register testing tools
        self._tool_registry.update({
            "validate_application_schema": testing.validate_application_schema,
            "test_service_endpoint": testing.test_service_endpoint,
            "test_authentication": testing.test_authentication,
            "test_parameter_extraction": testing.test_parameter_extraction,
            "simulate_service_execution": testing.simulate_service_execution,
            "generate_test_report": testing.generate_test_report,
            "debug_failed_service": testing.debug_failed_service,
            "test_event_subscription": testing.test_event_subscription,
        })
        
        # Register deployment tools
        self._tool_registry.update({
            "install_application": deployment.install_application,
            "uninstall_application": deployment.uninstall_application,
            "update_installed_application": deployment.update_installed_application,
            "list_installed_applications": deployment.list_installed_applications,
            "verify_deployment": deployment.verify_deployment,
            "rollback_application": deployment.rollback_application,
            "create_application_subscription": deployment.create_application_subscription,
        })
        
        # Register documentation tools with proper method wrappers
        async def get_service_docs(service_type: Optional[str] = None):
            """Get documentation for creating IOFlow application services"""
            result = await documentation.handle_tool_call("ioflow_get_service_docs", {"service_type": service_type})
            return {"content": result[0].text if result else "No documentation found"}
        
        async def get_event_docs(event_type: Optional[str] = None):
            """Get documentation for creating IOFlow application events"""
            result = await documentation.handle_tool_call("ioflow_get_event_docs", {"event_type": event_type})
            return {"content": result[0].text if result else "No documentation found"}
        
        async def get_app_guide():
            """Get complete guide for creating IOFlow applications"""
            result = await documentation.handle_tool_call("ioflow_get_app_guide", {})
            return {"content": result[0].text if result else "No documentation found"}
        
        async def search_docs(query: str):
            """Search IOFlow documentation for specific terms"""
            result = await documentation.handle_tool_call("ioflow_search_docs", {"query": query})
            return {"content": result[0].text if result else "No results found"}
        
        self._tool_registry.update({
            "ioflow_get_service_docs": get_service_docs,
            "ioflow_get_event_docs": get_event_docs,
            "ioflow_get_app_guide": get_app_guide,
            "ioflow_search_docs": search_docs,
        })
        
        # Register flow design tools (with temporary auth handler - will be updated per request)
        flow_design_tools = []
        for tool_class in FLOW_DESIGN_TOOLS:
            tool_instance = tool_class(auth_handler=temp_auth)
            flow_design_tools.append(tool_instance)

        # Register flow design V2 tools (stateless, ADK-context aware)
        flow_design_tools_v2 = []
        for tool_class in FLOW_DESIGN_TOOLS_V2:
            tool_instance = tool_class(auth_handler=temp_auth)
            flow_design_tools_v2.append(tool_instance)

        # Store V2 tools for later use
        self.flow_design_tools_v2 = flow_design_tools_v2

        # Create wrapper functions for flow design V2 tools
        async def create_flow_session(name: str, description: str = "", ttl_minutes: int = 30):
            """Create a new flow design session for incremental building"""
            for tool in flow_design_tools_v2:
                if tool.name == "create_flow_session":
                    result = await tool.run(name=name, description=description, ttl_minutes=ttl_minutes)
                    return {"content": result.text}
            return {"error": "Tool not found"}

        async def add_trigger_node(session_id: str, trigger_type: str, config):
            """Add a trigger node to the flow session"""
            # Parse config if it's a string
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except json.JSONDecodeError:
                    return {"error": "Invalid config JSON"}

            for tool in flow_design_tools_v2:
                if tool.name == "add_trigger_node":
                    result = await tool.run(session_id=session_id, trigger_type=trigger_type, config=config)
                    return {"content": result.text}
            return {"error": "Tool not found"}

        async def add_action_node(session_id: str, app_id: str, service_id: str, parameters,
                                 app_name: str = "", service_name: str = "", node_count: int = 1):
            """Add an action node to the flow session"""
            # Parse parameters if it's a string
            if isinstance(parameters, str):
                try:
                    parameters = json.loads(parameters)
                except json.JSONDecodeError:
                    return {"error": "Invalid parameters JSON"}

            for tool in flow_design_tools_v2:
                if tool.name == "add_action_node":
                    result = await tool.run(
                        session_id=session_id,
                        app_id=app_id,
                        service_id=service_id,
                        parameters=parameters,
                        app_name=app_name,
                        service_name=service_name,
                        node_count=node_count
                    )
                    return {"content": result.text}
            return {"error": "Tool not found"}

        async def complete_flow_session(session_id: str, flow_name: str, nodes, edges, trigger_config):
            """Complete the session and generate final flow JSON"""
            # Parse JSON strings if needed
            if isinstance(nodes, str):
                nodes = json.loads(nodes)
            if isinstance(edges, str):
                edges = json.loads(edges)
            if isinstance(trigger_config, str):
                trigger_config = json.loads(trigger_config)

            for tool in flow_design_tools_v2:
                if tool.name == "complete_flow_session":
                    result = await tool.run(
                        session_id=session_id,
                        flow_name=flow_name,
                        nodes=nodes,
                        edges=edges,
                        trigger_config=trigger_config
                    )
                    return {"content": result.text}
            return {"error": "Tool not found"}

        async def get_lightweight_applications(category: str = "", search: str = ""):
            """Get lightweight, cached list of applications"""
            for tool in flow_design_tools_v2:
                if tool.name == "get_lightweight_applications":
                    result = await tool.run(category=category, search=search)
                    return {"content": result.text}
            return {"error": "Tool not found"}

        async def get_flow_design_overview():
            """Get minimalist flow design overview for V2"""
            return {
                "overview": "Flow Design Fundamentals for Incremental Building",
                "node_types": {
                    "trigger": {
                        "description": "Starting point of every flow",
                        "types": {
                            "manual": "User-initiated with input variables",
                            "webhook": "HTTP endpoint trigger",
                            "schedule": "Time-based trigger (cron)",
                            "application_event": "Event from connected application"
                        },
                        "key_concepts": [
                            "Every flow must have exactly ONE trigger",
                            "Trigger defines input variables available as {{input.variable_name}}",
                            "Trigger is always the source of the first edge"
                        ]
                    },
                    "action": {
                        "description": "Service execution nodes",
                        "purpose": "Call external services/APIs",
                        "configuration": {
                            "app_id": "UUID of the application",
                            "service_id": "UUID of the service",
                            "parameters": "Service parameters with variable mappings"
                        },
                        "parameter_mapping": [
                            "Use {{input.field}} for trigger variables",
                            "Use {{node_outputs.node_id.field}} for previous node outputs",
                            "Static values can be passed directly"
                        ]
                    },
                    "transform": {
                        "description": "Data transformation using Python code",
                        "purpose": "Process, modify, or transform data between nodes",
                        "key_features": [
                            "Write Python functions to transform data",
                            "Access input data via function parameters",
                            "Return transformed data as dict",
                            "Available modules: json, re, datetime, math, random, base64, hashlib, uuid"
                        ],
                        "function_structure": "def transform(input_data): return {'result': processed_data}",
                        "use_cases": [
                            "Parse and restructure JSON",
                            "Filter/map arrays",
                            "Calculate values",
                            "Format strings",
                            "Convert data types"
                        ]
                    },
                    "condition": {
                        "description": "Branching logic based on conditions",
                        "purpose": "Route flow execution based on true/false evaluation",
                        "expression_syntax": {
                            "operators": ["==", "!=", ">", "<", ">=", "<=", "and", "or", "not", "in"],
                            "examples": [
                                "{{input.status}} == 'active'",
                                "{{node_outputs.action_1.count}} > 10",
                                "{{input.type}} in ['admin', 'superuser']"
                            ]
                        },
                        "outputs": {
                            "true_handle": "Executes when condition is true",
                            "false_handle": "Executes when condition is false"
                        },
                        "use_cases": [
                            "Conditional workflow routing",
                            "Validation checks",
                            "Error handling branches"
                        ]
                    },
                    "loop": {
                        "description": "Iterate over collections",
                        "purpose": "Repeat actions for each item in an array/list",
                        "types": {
                            "for_each": "Iterate over array items",
                            "while": "Loop while condition is true",
                            "times": "Repeat N times"
                        },
                        "loop_variables": {
                            "loop.item": "Current item in iteration",
                            "loop.index": "Current iteration index (0-based)",
                            "loop.isFirst": "True if first iteration",
                            "loop.isLast": "True if last iteration"
                        },
                        "use_cases": [
                            "Process list of items",
                            "Batch operations",
                            "Repeated API calls"
                        ]
                    },
                    "response": {
                        "description": "Return data from flow execution",
                        "purpose": "Define what data to return when flow completes",
                        "configuration": {
                            "responseData": "Object/dict with response fields",
                            "statusCode": "HTTP status code (optional)",
                            "headers": "Response headers (optional)"
                        },
                        "use_cases": [
                            "Return results to API caller",
                            "Format final output",
                            "Synchronous flow responses"
                        ],
                        "note": "Typically the last node in synchronous flows"
                    }
                },
                "connectors": {
                    "edges": {
                        "description": "Connect nodes to define execution flow",
                        "structure": {
                            "source": "ID of source node",
                            "target": "ID of target node",
                            "sourceHandle": "Optional output handle",
                            "targetHandle": "Optional input handle"
                        },
                        "rules": [
                            "Trigger must connect to first action",
                            "Actions connect in sequence",
                            "Each action can have multiple outgoing edges",
                            "Linear flows: trigger → action1 → action2 → action3"
                        ]
                    }
                },
                "flow_structure": {
                    "required_fields": {
                        "name": "Flow name",
                        "nodes": "Array of node objects",
                        "edges": "Array of edge objects connecting nodes",
                        "trigger": "Trigger configuration object",
                        "synchronous": "Boolean (usually false)",
                        "created_at": "ISO timestamp"
                    },
                    "node_structure": {
                        "id": "Unique node identifier (e.g., 'trigger_1', 'action_1')",
                        "type": "'trigger' or 'action'",
                        "position": {"x": 250, "y": 100},
                        "data": "Node-specific configuration"
                    }
                },
                "best_practices": [
                    "Always start with trigger node",
                    "Connect nodes in logical execution order",
                    "Use descriptive node IDs",
                    "Map parameters from trigger or previous nodes",
                    "Test with simple flows first"
                ],
                "common_patterns": {
                    "simple_flow": "trigger → action → done",
                    "chain_flow": "trigger → action1 → action2 → action3",
                    "data_flow": "trigger (input) → action (processes) → uses {{input.field}} or {{node_outputs.action_1.result}}"
                }
            }

        # NOTE: there used to be a `flow_design_guidelines` wrapper here. It
        # searched the tool list for a tool of that name, and no such tool has
        # ever existed — every call returned {"error": "Tool not found"} while
        # the registry advertised it as available. It is removed rather than
        # repaired because `get_flow_design_guideline` (registered through
        # _api_wrapper_tools) already does exactly this job and works. Nothing
        # can be relying on the old name: it never once succeeded.
        
        async def get_application_details(
            app_name: Optional[str] = None,
            include_services: bool = True,
            include_events: bool = True,
            only_connected: bool = False
        ):
            """Get detailed information about applications for flow design"""
            for tool in flow_design_tools:
                if tool.name == "get_application_details":
                    result = await tool.run(
                        app_name=app_name,
                        include_services=include_services,
                        include_events=include_events,
                        only_connected=only_connected
                    )
                    return {"content": result.text}
            return {"error": "Tool not found"}
        
        async def create_flow_json(
            flow_name: str,
            trigger_type: str,
            nodes: List[Dict[str, Any]],
            description: Optional[str] = None
        ):
            """Create a complete flow JSON definition"""
            for tool in flow_design_tools:
                if tool.name == "create_flow_json":
                    result = await tool.run(
                        flow_name=flow_name,
                        trigger_type=trigger_type,
                        nodes=nodes,
                        description=description
                    )
                    return {"content": result.text}
            return {"error": "Tool not found"}
        
        async def analyze_flow_requirements(
            use_case: str,
            source_app: Optional[str] = None,
            target_app: Optional[str] = None,
            data_volume: Optional[str] = None,
            frequency: Optional[str] = None
        ):
            """Analyze requirements and provide flow design recommendations"""
            for tool in flow_design_tools:
                if tool.name == "analyze_flow_requirements":
                    result = await tool.run(
                        use_case=use_case,
                        source_app=source_app,
                        target_app=target_app,
                        data_volume=data_volume,
                        frequency=frequency
                    )
                    return {"content": result.text}
            return {"error": "Tool not found"}
        
        async def create_or_update_flow(
            flow_name: str,
            flow_definition: Dict[str, Any],
            description: Optional[str] = None,
            flow_id: Optional[str] = None,
            is_update: bool = False,
            activate: bool = False,
            is_synchronous: bool = False,
            sync_timeout: int = 30
        ):
            """Create or update a flow in IOFlow"""
            for tool in flow_design_tools:
                if tool.name == "create_or_update_flow":
                    result = await tool.run(
                        flow_name=flow_name,
                        flow_definition=flow_definition,
                        description=description,
                        flow_id=flow_id,
                        is_update=is_update,
                        activate=activate,
                        is_synchronous=is_synchronous,
                        sync_timeout=sync_timeout
                    )
                    # The tool answers with text on success AND failure; report
                    # {success, content, flow_id | error} so a failed save is a
                    # failure to the caller instead of a success with an error
                    # message inside it.
                    from mcp_server.tools.flow_design_tools import flow_save_verdict
                    verdict = flow_save_verdict(getattr(result, "text", "") or "")
                    if not verdict["success"]:
                        logger.warning(f"create_or_update_flow failed for '{flow_name}': "
                                       f"{str(verdict.get('error'))[:500]}")
                    return verdict
            return {"error": "Tool not found"}
        
        async def list_flows(
            search_name: Optional[str] = None,
            status: Optional[str] = None,
            trigger_type: Optional[str] = None,
            limit: int = 20
        ):
            """List flows with optional filtering"""
            for tool in flow_design_tools:
                if tool.name == "list_flows":
                    result = await tool.run(
                        search_name=search_name,
                        status=status,
                        trigger_type=trigger_type,
                        limit=limit
                    )
                    return {"content": result.text}
            return {"error": "Tool not found"}
        
        async def delete_flow(
            flow_id: Optional[str] = None,
            flow_name: Optional[str] = None,
            confirm: bool = False
        ):
            """Delete a flow from IOFlow"""
            for tool in flow_design_tools:
                if tool.name == "delete_flow":
                    result = await tool.run(
                        flow_id=flow_id,
                        flow_name=flow_name,
                        confirm=confirm
                    )
                    return {"content": result.text}
            return {"error": "Tool not found"}
        
        # Store flow design tools for later use
        self.flow_design_tools = flow_design_tools
        
        # Register non-API wrapper flow design tools
        self._tool_registry.update({
            # "flow_design_guidelines" intentionally absent — see the note
            # above; use "get_flow_design_guideline".
            "get_application_details": get_application_details,
            "create_flow_json": create_flow_json,
            "analyze_flow_requirements": analyze_flow_requirements,
            "create_or_update_flow": create_or_update_flow,
            "list_flows": list_flows,
            "delete_flow": delete_flow,
        })

        # Register flow design V2 tools (simplified, stateless)
        self._tool_registry.update({
            "get_flow_design_overview": get_flow_design_overview,
            "create_flow_session": create_flow_session,
            "add_trigger_node": add_trigger_node,
            "add_action_node": add_action_node,
            "complete_flow_session": complete_flow_session,
            "get_lightweight_applications": get_lightweight_applications,
        })

        # Register flow design assistant tools
        from mcp_server.tools.flow_design_assistant import FlowDesignAssistant
        
        # Wrapper functions for flow design assistant tools
        async def get_flow_node_template(
            node_type: str,
            example_data: Optional[Dict] = None
        ):
            """Get a properly structured template for a specific node type"""
            return FlowDesignAssistant.get_node_template(node_type, example_data)
        
        async def get_flow_edge_template(
            source_id: str,
            target_id: str,
            source_handle: str = "output",
            target_handle: str = "input"
        ):
            """Get a properly structured edge template for connecting nodes"""
            return FlowDesignAssistant.get_edge_template(source_id, target_id, source_handle, target_handle)
        
        async def get_common_flow_patterns():
            """Get examples of common flow patterns with proper structure"""
            return FlowDesignAssistant.get_common_patterns()
        
        async def validate_and_fix_flow(
            flow_definition: Dict[str, Any]
        ):
            """Validate a flow definition and automatically fix common issues"""
            return FlowDesignAssistant.validate_and_fix_flow(flow_definition)
        
        self._tool_registry.update({
            "get_flow_node_template": get_flow_node_template,
            "get_flow_edge_template": get_flow_edge_template,
            "get_common_flow_patterns": get_common_flow_patterns,
            "validate_and_fix_flow": validate_and_fix_flow,
        })
        
        # Register flow design management tools with auth context support
        class FlowDesignWrapper:
            """Wrapper to provide auth context to flow design tools"""
            def __init__(self):
                self.auth_handler = None
            
            async def create_flow_design(
                self,
                flow_name: str,
                flow_json: str,
                user_email: Optional[str] = None
            ):
                """Import a flow design directly into IOFlow via API"""
                from datetime import datetime

                logger.info(f"create_flow_design called with flow_name: {flow_name}")
                logger.debug(f"Flow JSON length: {len(flow_json) if flow_json else 0}")

                # Check if flow_json is base64 encoded
                import base64
                flow_json_str = flow_json
                if isinstance(flow_json, str) and not flow_json.strip().startswith('{'):
                    try:
                        # Try to decode base64
                        decoded = base64.b64decode(flow_json).decode('utf-8')
                        flow_json_str = decoded
                        logger.info("Detected and decoded base64-encoded flow JSON")
                    except Exception:
                        # Not base64, use as-is
                        pass

                try:
                    # Parse the JSON string if it's a string
                    if isinstance(flow_json_str, str):
                        flow_data = json.loads(flow_json_str)
                    else:
                        flow_data = flow_json_str
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Invalid JSON: {str(e)}"
                    }

                # Ensure flow is in import format
                if 'version' not in flow_data or 'flow' not in flow_data:
                    # Wrap in import format if not already
                    flow_data = {
                        "version": "1.0.0",
                        "export_timestamp": datetime.utcnow().isoformat() + "Z",
                        "flow": flow_data,
                        "metadata": {
                            "created_via": "mcp_bridge",
                            "source": "flow_agent"
                        }
                    }

                # Ensure flow_name is set in the flow data
                if 'flow' in flow_data:
                    if 'flow_name' not in flow_data['flow']:
                        flow_data['flow']['flow_name'] = flow_name
                    else:
                        # Update flow_name if different
                        flow_data['flow']['flow_name'] = flow_name

                # Import the flow via API
                if self.auth_handler:
                    try:
                        response = await self.auth_handler.make_authenticated_request(
                            "POST",
                            "/api/v1/flows/import",
                            json_data=flow_data
                        )

                        if response.get("error"):
                            error_msg = response.get("detail", response.get("error", "Import failed"))
                            logger.error(f"Flow import failed: {error_msg}")
                            return {
                                "success": False,
                                "error": error_msg,
                                "flow_id": None,
                                "flow_name": flow_name
                            }

                        # Extract flow_id from response
                        flow_id = response.get("flow_id")
                        if not flow_id:
                            logger.error(f"No flow_id in import response: {response}")
                            return {
                                "success": False,
                                "error": "Flow imported but no flow_id returned",
                                "flow_id": None,
                                "flow_name": flow_name
                            }

                        # Return success with flow details
                        logger.info(f"Flow imported successfully with ID: {flow_id}")
                        return {
                            "success": True,
                            "message": f"Flow '{flow_name}' imported successfully",
                            "flow_id": flow_id,
                            "flow_name": flow_name,
                            "status": "imported"
                        }
                    except Exception as e:
                        logger.error(f"Exception during flow import: {str(e)}", exc_info=True)
                        return {
                            "success": False,
                            "error": f"Failed to import flow: {str(e)}",
                            "flow_id": None,
                            "flow_name": flow_name
                        }
                else:
                    logger.error("Authentication handler not available for flow import")
                    return {
                        "success": False,
                        "error": "Authentication handler not available",
                        "flow_id": None,
                        "flow_name": flow_name
                    }
            
            async def replace_flow_design(
                self,
                flow_name: str,
                flow_json: str,
                original_filename: Optional[str] = None,
                user_email: Optional[str] = None
            ):
                """Replace an existing flow design by importing a new version via API"""
                # Just delegate to create_flow_design since we're now using API import
                # The API will handle creating new flows or updating existing ones with same name
                return await self.create_flow_design(
                    flow_name=flow_name,
                    flow_json=flow_json,
                    user_email=user_email
                )
            
            async def list_user_flow_designs(
                self,
                user_email: Optional[str] = None
            ):
                """List all flows for the authenticated user from IOFlow API"""
                # Get flows from API
                if self.auth_handler:
                    response = await self.auth_handler.make_authenticated_request(
                        "GET",
                        "/api/v1/flows/"
                    )

                    if response.get("error"):
                        return {
                            "success": False,
                            "error": response.get("detail", response.get("error", "Failed to list flows"))
                        }

                    # Format the response
                    flows = response if isinstance(response, list) else []

                    flow_list = []
                    for flow in flows:
                        flow_list.append({
                            "flow_id": flow.get("flow_id"),
                            "flow_name": flow.get("flow_name"),
                            "status": flow.get("status"),
                            "created_at": flow.get("created_at"),
                            "updated_at": flow.get("updated_at"),
                            "trigger_type": flow.get("trigger_config", {}).get("type") if flow.get("trigger_config") else None
                        })

                    return {
                        "success": True,
                        "flows": flow_list,
                        "count": len(flow_list)
                    }
                else:
                    return {
                        "success": False,
                        "error": "Authentication handler not available"
                    }

            async def validate_and_save_flow(
                self,
                flow_name: str = None,
                flow_json: str = None,
                functions_base64: str = None,
                functions: str = None
            ):
                """
                Validate and save flow design in a single operation.

                This is a thin wrapper that calls the validate-and-save API endpoint.

                Args:
                    flow_name: Name for the flow (optional - will be extracted from JSON by API)
                    flow_json: Flow JSON in export format (raw JSON or base64-encoded)
                    functions_base64: Optional base64-encoded Python functions
                    functions: Optional raw Python functions (alias for functions_base64)
                """
                import base64 as b64

                try:
                    if not self.auth_handler:
                        return {"error": "No auth handler available"}

                    # Auto-detect if flow_json is raw JSON or base64, encode if raw
                    encoded_flow_json = flow_json
                    if isinstance(flow_json, str) and flow_json.strip().startswith('{'):
                        # Raw JSON detected - base64 encode it
                        encoded_flow_json = b64.b64encode(flow_json.encode('utf-8')).decode('utf-8')
                        logger.info("validate_and_save_flow: auto-encoded raw JSON to base64")

                    # Accept 'functions' as alias for 'functions_base64'
                    raw_functions = functions_base64 or functions
                    encoded_functions = None
                    if raw_functions:
                        # Check if already base64 or raw text
                        try:
                            b64.b64decode(raw_functions).decode('utf-8')
                            # Already valid base64
                            encoded_functions = raw_functions
                        except Exception:
                            # Raw text - base64 encode it
                            encoded_functions = b64.b64encode(raw_functions.encode('utf-8')).decode('utf-8')
                            logger.info("validate_and_save_flow: auto-encoded raw functions to base64")

                    request_data = {
                        "flow_json": encoded_flow_json
                    }

                    if encoded_functions:
                        request_data["functions_base64"] = encoded_functions

                    response = await self.auth_handler.make_authenticated_request(
                        "POST",
                        "/api/v1/flow-design/validate-and-save",
                        json_data=request_data
                    )

                    return response

                except Exception as e:
                    logger.error(f"Error in validate_and_save_flow: {e}", exc_info=True)
                    return {"error": str(e)}

        # Create wrapper instance
        flow_wrapper = FlowDesignWrapper()
        
        # Store flow wrapper for auth handler updates
        self.flow_wrapper = flow_wrapper
        
        async def create_flow_design(
            flow_name: str,
            flow_json: str,
            user_email: Optional[str] = None
        ):
            """Create a new flow design file for a user"""
            return await flow_wrapper.create_flow_design(flow_name, flow_json, user_email)
        
        async def replace_flow_design(
            flow_name: str,
            flow_json: str,
            original_filename: Optional[str] = None,
            user_email: Optional[str] = None
        ):
            """Replace an existing flow design or create a new version"""
            return await flow_wrapper.replace_flow_design(flow_name, flow_json, original_filename, user_email)
        
        async def list_user_flow_designs(user_email: Optional[str] = None):
            """List all flow designs for a user"""
            return await flow_wrapper.list_user_flow_designs(user_email)

        async def validate_and_save_flow(flow_name: str = None, flow_json: str = None, functions_base64: str = None, functions: str = None):
            """Validate and save flow design in a single operation"""
            return await flow_wrapper.validate_and_save_flow(flow_name, flow_json, functions_base64, functions)

        self._tool_registry.update({
            "create_flow_design": create_flow_design,
            "replace_flow_design": replace_flow_design,
            "list_user_flow_designs": list_user_flow_designs,
            "validate_and_save_flow": validate_and_save_flow,
        })

        # ============================================================================
        # Flow Editor Tools - For editing existing flows
        # ============================================================================

        # Use configured API URL for internal API calls from MCP bridge
        base_url = settings.api_url

        async def get_flow_by_id(flow_id: str):
            """Get flow by ID"""
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = f"{base_url}/api/v1/flows/{flow_id}"
                    headers = self.auth_handler.get_auth_headers() if hasattr(self, 'auth_handler') and self.auth_handler else {}

                    response = await client.get(url, headers=headers)
                    response.raise_for_status()

                    flow_data = response.json()
                    return {
                        "success": True,
                        "flow": flow_data
                    }
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return {"success": False, "error": "Flow not found"}
                logger.error(f"Error getting flow by ID: {e}")
                return {"success": False, "error": str(e)}
            except Exception as e:
                logger.error(f"Error getting flow by ID: {e}")
                return {"success": False, "error": str(e)}

        async def get_flow_by_name(flow_name: str):
            """Get flow by name for the authenticated user"""
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    # Backend API automatically filters by authenticated user from JWT
                    url = f"{base_url}/api/v1/flows/by-name"
                    headers = self.auth_handler.get_auth_headers() if hasattr(self, 'auth_handler') and self.auth_handler else {}
                    params = {"flow_name": flow_name}

                    logger.info(f"get_flow_by_name calling {url} with flow_name='{flow_name}'")
                    logger.info(f"  Headers present: {bool(headers)}, has Authorization: {'Authorization' in headers}")
                    if headers and 'Authorization' in headers:
                        auth_val = headers['Authorization']
                        logger.info(f"  Authorization header length: {len(auth_val)}, starts with: {auth_val[:20]}...")

                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()

                    flow_data = response.json()
                    return {
                        "success": True,
                        "flow": flow_data
                    }
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return {"success": False, "error": f"Flow '{flow_name}' not found"}
                logger.error(f"Error getting flow by name: {e}")
                return {"success": False, "error": str(e)}
            except Exception as e:
                logger.error(f"Error getting flow by name: {e}")
                return {"success": False, "error": str(e)}

        async def replace_node_in_flow(flow_id: str, node_id: str, node_json: str):
            """Replace a specific node in a flow"""
            try:
                # Parse node_json if it's a string
                if isinstance(node_json, str):
                    node_data = json.loads(node_json)
                else:
                    node_data = node_json

                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = f"{base_url}/api/v1/flows/{flow_id}/nodes/{node_id}"
                    headers = self.auth_handler.get_auth_headers() if hasattr(self, 'auth_handler') and self.auth_handler else {}

                    response = await client.put(url, headers=headers, json=node_data)
                    response.raise_for_status()

                    result = response.json()
                    return result
            except Exception as e:
                logger.error(f"Error replacing node: {e}")
                return {"success": False, "error": str(e)}

        async def add_node_to_flow(flow_id: str, node_json: str, position: str = "after_last"):
            """Add a node to a flow"""
            try:
                # Parse node_json if it's a string
                if isinstance(node_json, str):
                    node_data = json.loads(node_json)
                else:
                    node_data = node_json

                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = f"{base_url}/api/v1/flows/{flow_id}/nodes"
                    headers = self.auth_handler.get_auth_headers() if hasattr(self, 'auth_handler') and self.auth_handler else {}
                    params = {"position": position}

                    response = await client.post(url, headers=headers, json=node_data, params=params)
                    response.raise_for_status()

                    result = response.json()
                    return result
            except Exception as e:
                logger.error(f"Error adding node: {e}")
                return {"success": False, "error": str(e)}

        async def remove_node_from_flow(flow_id: str, node_id: str, reconnect: bool = True):
            """Remove a node from a flow"""
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = f"{base_url}/api/v1/flows/{flow_id}/nodes/{node_id}"
                    headers = self.auth_handler.get_auth_headers() if hasattr(self, 'auth_handler') and self.auth_handler else {}
                    params = {"reconnect": reconnect}

                    response = await client.delete(url, headers=headers, params=params)
                    response.raise_for_status()

                    result = response.json()
                    return result
            except Exception as e:
                logger.error(f"Error removing node: {e}")
                return {"success": False, "error": str(e)}

        async def update_edge_in_flow(flow_id: str, edge_json: str):
            """Update or add an edge in a flow"""
            try:
                # Parse edge_json if it's a string
                if isinstance(edge_json, str):
                    edge_data = json.loads(edge_json)
                else:
                    edge_data = edge_json

                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = f"{base_url}/api/v1/flows/{flow_id}/edges"
                    headers = self.auth_handler.get_auth_headers() if hasattr(self, 'auth_handler') and self.auth_handler else {}

                    response = await client.put(url, headers=headers, json=edge_data)
                    response.raise_for_status()

                    result = response.json()
                    return result
            except Exception as e:
                logger.error(f"Error updating edge: {e}")
                return {"success": False, "error": str(e)}

        async def get_execution_logs(execution_id: str, include_data: bool = True, limit: int = 500):
            """Get execution logs for debugging"""
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = f"{base_url}/api/v1/executions/{execution_id}/logs"
                    headers = self.auth_handler.get_auth_headers() if hasattr(self, 'auth_handler') and self.auth_handler else {}
                    params = {"include_data": include_data, "limit": limit}

                    response = await client.get(url, headers=headers, params=params)
                    response.raise_for_status()

                    logs_data = response.json()
                    return {
                        "success": True,
                        "logs": logs_data.get("logs", []),
                        "total": logs_data.get("total", 0)
                    }
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return {"success": False, "error": "Execution not found"}
                logger.error(f"Error getting execution logs: {e}")
                return {"success": False, "error": str(e)}
            except Exception as e:
                logger.error(f"Error getting execution logs: {e}")
                return {"success": False, "error": str(e)}

        async def get_execution_details(execution_id: str):
            """Get execution details including status and result"""
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    url = f"{base_url}/api/v1/executions/{execution_id}"
                    headers = self.auth_handler.get_auth_headers() if hasattr(self, 'auth_handler') and self.auth_handler else {}

                    response = await client.get(url, headers=headers)
                    response.raise_for_status()

                    execution_data = response.json()
                    return {
                        "success": True,
                        "execution": execution_data
                    }
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return {"success": False, "error": "Execution not found"}
                logger.error(f"Error getting execution details: {e}")
                return {"success": False, "error": str(e)}
            except Exception as e:
                logger.error(f"Error getting execution details: {e}")
                return {"success": False, "error": str(e)}

        # Register flow editor tools
        self._tool_registry.update({
            "get_flow_by_id": get_flow_by_id,
            "get_flow_by_name": get_flow_by_name,
            "replace_node_in_flow": replace_node_in_flow,
            "add_node_to_flow": add_node_to_flow,
            "remove_node_from_flow": remove_node_from_flow,
            "update_edge_in_flow": update_edge_in_flow,
            "get_execution_logs": get_execution_logs,
            "get_execution_details": get_execution_details,
        })

        # Register resources
        self._resource_registry = {
            "seed-apps://catalog": self._get_catalog_resource,
            "seed-apps://schema": self._get_schema_resource,
            "seed-apps://docs": self._get_docs_resource,
        }
    
    def _normalize_tool_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize parameters for backward compatibility and different calling patterns"""
        normalized = parameters.copy()
        
        # Handle create_flow_json with different parameter names
        if tool_name == "create_flow_json":
            # Map common alternative parameter names
            if "name" in normalized and "flow_name" not in normalized:
                normalized["flow_name"] = normalized.pop("name")
            
            if "requirements" in normalized and "description" not in normalized:
                normalized["description"] = f"Generated from: {normalized['requirements'][:200]}"
            
            if "inputs" in normalized and "trigger_config" not in normalized:
                # Convert inputs to trigger config
                normalized["trigger_config"] = {
                    "type": normalized.get("trigger_type", "manual"),
                    "manual_variables": normalized.pop("inputs")
                }
            
            if "services" in normalized and "nodes_config" not in normalized:
                # Convert services to nodes config
                nodes = []
                for service in normalized.pop("services"):
                    nodes.append({
                        "type": "action",
                        "data": {
                            "label": service.get("label", "Service"),
                            "appId": service.get("application"),
                            "service": service.get("service_name"),
                            "parameters": service.get("inputs", {})
                        }
                    })
                normalized["nodes_config"] = nodes
        
        # Handle create_or_update_flow parameter variations
        elif tool_name == "create_or_update_flow":
            if "flow_definition" in normalized:
                # Extract flow_name if it's in the definition
                if "flow_name" not in normalized:
                    flow_def = normalized["flow_definition"]
                    if isinstance(flow_def, dict):
                        normalized["flow_name"] = flow_def.get("name", "Untitled")
                        
        # Handle analyze_flow_requirements parameter variations
        elif tool_name == "analyze_flow_requirements":
            if "requirements" in normalized and "use_case" not in normalized:
                # Convert simple requirements string to expected format
                normalized["use_case"] = normalized.pop("requirements")
        
        # validate_and_save_flow: wrapper handles 'functions' alias and raw JSON auto-detection

        # Handle validate_and_fix_flow static method call
        elif tool_name == "validate_and_fix_flow":
            if "flow_definition" not in normalized and "nodes" in normalized:
                # Wrap bare flow definition
                normalized = {"flow_definition": normalized}

        # Handle create_seed_application parameter normalization
        # Claude Code may send 'key' instead of 'app_key', or nest fields in 'application' object
        elif tool_name == "create_seed_application":
            # Map 'key' to 'app_key'
            if "key" in normalized and "app_key" not in normalized:
                normalized["app_key"] = normalized.pop("key")

            # If an 'application' dict is passed, extract fields from it
            if "application" in normalized and isinstance(normalized["application"], dict):
                app_obj = normalized.pop("application")
                for field in ["app_name", "app_type", "app_scope", "category",
                              "auth_type", "description", "base_url", "version",
                              "auth_config", "icon_url"]:
                    if field in app_obj and field not in normalized:
                        normalized[field] = app_obj[field]

            # Strip 'metadata' and 'icon_url' - not accepted by the function
            normalized.pop("metadata", None)
            normalized.pop("icon_url", None)

        # Handle add_service_to_application parameter normalization
        # Claude Code agents often send flat parameters (from guide docs) instead of
        # wrapping them in a 'configuration' dict as the function expects
        elif tool_name == "add_service_to_application":
            # Strip display_name - not accepted by the function
            normalized.pop("display_name", None)

            # If 'configuration' is missing but individual config fields are present,
            # bundle them into a configuration dict
            if "configuration" not in normalized:
                config_fields = [
                    "endpoint_template", "request_config", "parameter_schema",
                    "output_schema", "response_config", "service_config",
                    "body_template", "headers_template", "method", "http_method",
                    "parameter_method", "query_params_template"
                ]
                configuration = {}
                for field in config_fields:
                    if field in normalized:
                        configuration[field] = normalized.pop(field)
                if configuration:
                    normalized["configuration"] = configuration

        # Handle add_event_to_application parameter normalization
        elif tool_name == "add_event_to_application":
            # Strip display_name - not accepted by the function
            normalized.pop("display_name", None)

            # If 'configuration' is missing but event_configuration is present
            if "configuration" not in normalized and "event_configuration" in normalized:
                normalized["configuration"] = normalized.pop("event_configuration")

        return normalized
    
    def _get_auth_headers(self, auth_handler) -> Dict[str, str]:
        """Get auth headers from either MCPAuthHandler or EnhancedMCPAuthHandler"""
        if hasattr(auth_handler, 'get_auth_headers'):
            # EnhancedMCPAuthHandler has this method
            return auth_handler.get_auth_headers()
        elif hasattr(auth_handler, 'api_key') and auth_handler.api_key:
            # Fallback for MCPAuthHandler
            return {"Authorization": f"Bearer {auth_handler.api_key}"}
        elif hasattr(auth_handler, '_headers'):
            # Get from _headers if available
            auth_header = auth_handler._headers.get("Authorization")
            if auth_header:
                return {"Authorization": auth_header}
        return {}

    def _create_api_wrapper_functions(self, auth_handler) -> Dict[str, Any]:
        """Create API wrapper functions with proper authentication"""
        import httpx
        from core.config import settings as app_settings

        # Use configured API URL for internal API calls from MCP bridge
        base_url = settings.api_url

        # Helper function to get auth headers
        def get_auth_headers():
            """Get auth headers from either MCPAuthHandler or EnhancedMCPAuthHandler"""
            if hasattr(auth_handler, 'get_auth_headers'):
                # EnhancedMCPAuthHandler has this method
                return auth_handler.get_auth_headers()
            elif hasattr(auth_handler, 'api_key') and auth_handler.api_key:
                # Fallback for MCPAuthHandler
                return {"Authorization": f"Bearer {auth_handler.api_key}"}
            elif hasattr(auth_handler, '_headers'):
                # Get from _headers if available
                auth_header = auth_handler._headers.get("Authorization")
                if auth_header:
                    return {"Authorization": auth_header}
            return {}
        
        async def validate_flow_comprehensive(**kwargs):
            """Validate flow design using comprehensive validator - returns agent-friendly format

            The agent always sends flow JSON as base64-encoded to avoid escaping issues.
            This function handles base64 decoding automatically.
            """
            import json
            import base64

            # Initialize variables
            flow_definition = None
            functions = None

            # MCP bridge is only called by agent, so always handle flow_json parameter
            if 'flow_json' in kwargs and isinstance(kwargs['flow_json'], str):
                flow_json_str = kwargs['flow_json']

                # Agent always sends base64-encoded JSON to avoid escaping issues
                # Check if it's base64 encoded (doesn't start with '{')
                if not flow_json_str.strip().startswith('{'):
                    # Decode from base64
                    try:
                        decoded = base64.b64decode(flow_json_str).decode('utf-8')
                        flow_json_str = decoded
                        logger.info("Decoded base64-encoded flow JSON from agent")
                    except Exception as e:
                        logger.error(f"Failed to decode base64: {e}")
                        return {
                            "valid": False,
                            "message": "Invalid base64-encoded JSON",
                            "errors": ["Failed to decode base64-encoded JSON from agent"],
                            "warnings": [],
                            "suggestions": ["Ensure the flow JSON is properly base64-encoded"]
                        }

                # Parse the JSON using tolerant parser that handles literal newlines
                try:
                    from services.json_parser import parse_tolerant_json
                    flow_definition = parse_tolerant_json(flow_json_str)
                    logger.debug("JSON parsed successfully using tolerant parser")
                except Exception as e:
                    logger.error(f"JSON parse error: {e}")
                    # Check if it's likely a control character issue from multiline scripts
                    error_msg = str(e).lower()
                    if "control character" in error_msg or "unterminated string" in error_msg:
                        return {
                            "valid": False,
                            "message": f"JSON formatting error: {str(e)}",
                            "errors": [
                                f"JSON parse error: {str(e)}",
                                "This error typically occurs when transform nodes contain inline multiline scripts with unescaped newlines."
                            ],
                            "warnings": [],
                            "suggestions": [
                                "Use external functions for transform nodes instead of inline multiline scripts",
                                "Define your logic in the 'functions' parameter and call it with a single line: output = your_function(input)",
                                "See get_transform_node_guide for the correct pattern"
                            ]
                        }
                    else:
                        return {
                            "valid": False,
                            "message": f"Invalid JSON: {str(e)}",
                            "errors": [f"JSON parse error: {str(e)}"],
                            "warnings": [],
                            "suggestions": ["Ensure the JSON is properly formatted"]
                        }
            else:
                # Fallback for direct dict input
                flow_definition = kwargs.copy()
                # Remove functions from flow_definition since it's a separate parameter
                flow_definition.pop('functions', None)

            # Handle functions parameter separately (ALWAYS sent as base64-encoded JSON by agent)
            if 'functions' in kwargs and isinstance(kwargs['functions'], str):
                functions_str = kwargs['functions']
                # Agent MUST send functions as base64 to avoid JSON escaping issues
                # Check if it's base64 encoded
                if not functions_str.strip().startswith('{'):
                    try:
                        decoded_functions = base64.b64decode(functions_str).decode('utf-8')
                        functions = json.loads(decoded_functions)
                        logger.info("Decoded base64-encoded functions from agent")
                    except Exception as e:
                        logger.error(f"Failed to decode functions: {e}")
                        # Functions are optional, so just log the error
                        functions = None
                else:
                    # If plain JSON received, log error - agent should use base64
                    logger.error("WARNING: Agent sent plain JSON for functions instead of base64. This may fail with multiline scripts.")
                    try:
                        functions = json.loads(functions_str)
                        logger.info("Managed to parse plain JSON functions (but agent should use base64)")
                    except Exception as e:
                        logger.error(f"Failed to parse plain JSON functions: {e}")
                        logger.error("Agent MUST send functions as base64-encoded JSON to avoid escaping issues")
                        functions = None
            
            try:
                # Import the comprehensive validator
                from services.flow_validator import FlowValidator
                from db.database import get_db
                
                # Get database session
                db = next(get_db())
                try:
                    # Create validator with database context
                    validator = FlowValidator(db=db, tenant_id=None)
                    
                    # Determine flow format and extract flow_definition
                    flow_def = None
                    if "flow_definition" in flow_definition and "flow_name" in flow_definition:
                        # Standard format
                        flow_def = flow_definition["flow_definition"]
                    elif "flow" in flow_definition and isinstance(flow_definition["flow"], dict):
                        # Export format
                        if "flow_definition" in flow_definition["flow"]:
                            flow_def = flow_definition["flow"]["flow_definition"]
                    elif "nodes" in flow_definition and "edges" in flow_definition:
                        # Direct flow definition
                        flow_def = flow_definition
                    else:
                        # Assume it's the complete structure
                        flow_def = flow_definition.get("flow_definition", flow_definition)
                    
                    # Validate using comprehensive validator
                    is_valid, errors = validator.validate_flow_comprehensive(flow_def, functions)
                    
                    # Always format for agent - simple strings (MCP bridge is only used by agent)
                    error_strings = []
                    warning_strings = []
                    suggestions = []

                    for error in errors:
                        # Create a simple string message
                        msg_parts = []
                        if hasattr(error, 'node_id') and error.node_id:
                            msg_parts.append(f"Node '{error.node_id}':")
                        msg_parts.append(error.message)
                        if hasattr(error, 'field') and error.field:
                            msg_parts.append(f"(field: {error.field})")

                        full_msg = " ".join(msg_parts)

                        if error.error_type == "error":
                            error_strings.append(full_msg)
                        else:
                            warning_strings.append(full_msg)

                        if hasattr(error, 'suggestion') and error.suggestion:
                            suggestions.append(error.suggestion)

                    # Create summary message for agent
                    if is_valid:
                        message = "✓ Flow validation PASSED"
                    else:
                        message = "✗ Flow validation FAILED"
                        if error_strings:
                            message += f" - {len(error_strings)} error(s) found"

                    return {
                        "valid": is_valid,
                        "message": message,
                        "errors": error_strings,
                        "warnings": warning_strings,
                        "suggestions": suggestions
                    }
                    
                finally:
                    db.close()
                    
            except Exception as e:
                logger.error(f"Error in comprehensive validation: {str(e)}")
                # Always return agent-friendly format (MCP bridge is only used by agent)
                return {
                    "valid": False,
                    "message": f"Validation error: {str(e)}",
                    "errors": [f"Validation error: {str(e)}"],
                    "warnings": [],
                    "suggestions": []
                }
        
        async def validate_flow_design(**kwargs):
            """Validate flow design via API endpoint (basic validation)"""
            # Check if flow_json parameter contains base64-encoded JSON
            if 'flow_json' in kwargs:
                import base64
                import json

                flow_json = kwargs.pop('flow_json')
                functions_param = kwargs.pop('functions', None)

                # Decode base64-encoded flow JSON
                try:
                    decoded_flow = base64.b64decode(flow_json).decode('utf-8')
                    flow_definition = json.loads(decoded_flow)
                    logger.info("Decoded base64-encoded flow JSON in validate_flow_design")
                except Exception as e:
                    logger.error(f"Failed to decode flow_json: {e}")
                    return {
                        "valid": False,
                        "message": f"Failed to decode flow JSON: {str(e)}",
                        "errors": [f"Invalid base64 or JSON format: {str(e)}"]
                    }

                # Handle functions_base64 parameter if provided
                # Functions are passed as base64-encoded string to preserve formatting
                functions_base64 = kwargs.pop('functions_base64', None)
                if functions_base64:
                    logger.info(f"Received functions_base64, length: {len(functions_base64)}")
            else:
                # kwargs contains the flow definition directly
                flow_definition = kwargs.copy()
                # Extract functions_base64 if provided
                functions_base64 = flow_definition.pop('functions_base64', None)
                # The advertised schema is {"flow_definition": <...>}: a caller
                # following it sends EITHER the bare {nodes, edges} OR the whole
                # flow body under that one key. Unwrap it so the format branches
                # below see what was meant (it used to reach the API as-is and
                # fail with "flow_name / trigger_config required").
                inner = flow_definition.get("flow_definition")
                if (isinstance(inner, dict) and "flow_name" not in flow_definition
                        and "trigger_config" not in flow_definition):
                    extra = {k: v for k, v in flow_definition.items() if k != "flow_definition"}
                    flow_definition = {**inner, **{k: v for k, v in extra.items() if k not in inner}}

            # Check if this flow is missing export format wrapper
            import_format_warning = None
            if "flow_name" in flow_definition and "flow_definition" in flow_definition:
                # It's a direct flow format - check if it's NOT wrapped in export format
                if not ("version" in flow_definition and "export_timestamp" in flow_definition):
                    import_format_warning = {
                        "message": "Flow validates but needs export format wrapper for import. Wrap with: {\"version\": \"1.0\", \"export_timestamp\": \"<timestamp>\", \"flow\": <your_flow>, \"metadata\": {}}",
                        "severity": "warning"
                    }

            # Handle different input formats
            if "flow_definition" in flow_definition and "flow_name" in flow_definition:
                # Already in correct format
                flow_data = flow_definition
                # Add functions_base64 if provided
                if functions_base64:
                    flow_data['functions_base64'] = functions_base64
            elif "flow" in flow_definition and isinstance(flow_definition["flow"], dict):
                # Export format, extract the flow for validation
                flow_data = flow_definition["flow"]
                # Add functions_base64 if provided
                if functions_base64:
                    flow_data['functions_base64'] = functions_base64
                    logger.info(f"Including base64 functions in validation for export format flow")
                # Clear the warning since it's already in export format
                import_format_warning = None
            elif "nodes" in flow_definition and "edges" in flow_definition:
                # Just the definition, wrap it with trigger config from nodes
                # Extract trigger config from nodes if present
                trigger_config = {
                    "type": "manual",
                    "manual_variables": []
                }
                
                # Find trigger node to get manual variables
                for node in flow_definition.get("nodes", []):
                    if node.get("type") == "trigger":
                        data = node.get("data", {})
                        if data.get("triggerType") == "manual":
                            manual_vars = data.get("manualVariables", [])
                            # Ensure proper structure
                            trigger_config["manual_variables"] = [
                                {
                                    "id": var.get("id", var.get("name", "")),
                                    "name": var.get("name", ""),
                                    "displayName": var.get("displayName", var.get("name", "")),
                                    "dataType": var.get("dataType", "string"),
                                    "uiControl": var.get("uiControl", "text"),
                                    "required": var.get("required", True),
                                    "defaultValue": var.get("defaultValue", "")
                                }
                                for var in manual_vars
                            ]
                        break
                
                flow_data = {
                    "flow_name": flow_definition.get("flow_name", flow_definition.get("name", "Untitled")),
                    "description": flow_definition.get("description", ""),
                    "trigger_config": trigger_config,
                    "flow_definition": {
                        "nodes": flow_definition["nodes"],
                        "edges": flow_definition["edges"]
                    }
                }
                # This format also needs export wrapper
                import_format_warning = {
                    "message": "Flow validates but needs export format wrapper for import. Wrap with: {\"version\": \"1.0\", \"export_timestamp\": \"<timestamp>\", \"flow\": <your_flow>, \"metadata\": {}}",
                    "severity": "warning"
                }
            else:
                # Assume it's the complete structure
                flow_data = flow_definition

            # Add functions_base64 to flow_data if provided
            if functions_base64:
                flow_data['functions_base64'] = functions_base64
                logger.info(f"Including base64 functions in validation")

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{base_url}/api/v1/flow-design/validate",
                        json=flow_data,
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        result = response.json()
                        # Add import format warning if needed
                        if import_format_warning:
                            if "warnings" not in result:
                                result["warnings"] = []
                            result["warnings"].append(import_format_warning)
                            if "suggestions" not in result:
                                result["suggestions"] = []
                            result["suggestions"].append("To make this flow importable, wrap it in export format with version and timestamp")
                        return result
                    else:
                        error_msg = response.text
                        try:
                            error_json = response.json()
                            if "detail" in error_json:
                                error_msg = error_json["detail"]
                        except:
                            pass
                        return {"valid": False, "errors": [{"message": f"API error: {error_msg}"}]}
            except Exception as e:
                return {"valid": False, "errors": [{"message": f"Validation failed: {str(e)}"}]}
        
        async def search_applications(query: str, **kwargs):
            """Search for applications by name or description with wildcard support.
            Falls back to list_applications if no matches found."""
            try:
                logger.info(f"Searching applications with query: {query}")
                
                # First get all applications
                headers = get_auth_headers()
                
                async with httpx.AsyncClient() as client:
                    # Get all applications
                    response = await client.get(
                        f"{base_url}/api/v1/applications/",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        apps = response.json()
                        
                        # Search with wildcard support
                        query_lower = query.lower()
                        matched_apps = []
                        
                        for app in apps:
                            # Check name and description for matches
                            name_match = query_lower in app.get("name", "").lower()
                            desc_match = query_lower in app.get("description", "").lower()
                            key_match = query_lower in app.get("app_key", "").lower()
                            
                            # Also check for wildcard patterns
                            if "*" in query:
                                import fnmatch
                                pattern = query.lower()
                                name_wildcard = fnmatch.fnmatch(app.get("name", "").lower(), pattern)
                                desc_wildcard = fnmatch.fnmatch(app.get("description", "").lower(), pattern)
                                key_wildcard = fnmatch.fnmatch(app.get("app_key", "").lower(), pattern)
                                
                                if name_wildcard or desc_wildcard or key_wildcard:
                                    matched_apps.append(app)
                            elif name_match or desc_match or key_match:
                                matched_apps.append(app)
                        
                        if matched_apps:
                            logger.info(f"Found {len(matched_apps)} matching applications")
                            return {"applications": matched_apps, "query": query, "match_count": len(matched_apps)}
                        else:
                            logger.info(f"No matches found for '{query}', returning all applications")
                            # Fallback to all applications
                            return {"applications": apps, "query": query, "match_count": 0, "fallback": True}
                    else:
                        return {"error": f"Failed to get applications: {response.status_code}"}
                        
            except Exception as e:
                logger.error(f"Error in search_applications: {e}")
                return {"error": str(e)}
        
        async def search_services(query: str, application_id: Optional[str] = None, **kwargs):
            """Search for services across all or specific applications with wildcard support."""
            try:
                logger.info(f"Searching services with query: {query}, app_id: {application_id}")
                
                headers = get_auth_headers()
                
                async with httpx.AsyncClient() as client:
                    # Get all applications or specific one
                    if application_id:
                        app_response = await client.get(
                            f"{base_url}/api/v1/applications/{application_id}",
                            headers=headers
                        )
                        if app_response.status_code == 200:
                            apps = [app_response.json()]
                        else:
                            return {"error": f"Application not found: {application_id}"}
                    else:
                        app_response = await client.get(
                            f"{base_url}/api/v1/applications/",
                            headers=headers
                        )
                        if app_response.status_code == 200:
                            apps = app_response.json()
                        else:
                            return {"error": "Failed to get applications"}
                    
                    # Search services
                    query_lower = query.lower()
                    matched_services = []
                    
                    for app in apps:
                        app_id = app.get("app_id")
                        
                        # Get services for this app
                        services_response = await client.get(
                            f"{base_url}/api/v1/applications/{app_id}/services",
                            headers=headers
                        )
                        
                        if services_response.status_code == 200:
                            services = services_response.json()
                            
                            for service in services:
                                # Check service name and description
                                name_match = query_lower in service.get("service_name", "").lower()
                                desc_match = query_lower in service.get("description", "").lower()
                                
                                # Wildcard support
                                if "*" in query:
                                    import fnmatch
                                    pattern = query.lower()
                                    name_wildcard = fnmatch.fnmatch(service.get("service_name", "").lower(), pattern)
                                    desc_wildcard = fnmatch.fnmatch(service.get("description", "").lower(), pattern)
                                    
                                    if name_wildcard or desc_wildcard:
                                        service["application_name"] = app.get("name")
                                        service["application_id"] = app_id
                                        matched_services.append(service)
                                elif name_match or desc_match:
                                    service["application_name"] = app.get("name")
                                    service["application_id"] = app_id
                                    matched_services.append(service)
                    
                    return {
                        "services": matched_services,
                        "query": query,
                        "match_count": len(matched_services),
                        "application_filter": application_id
                    }
                    
            except Exception as e:
                logger.error(f"Error in search_services: {e}")
                return {"error": str(e)}
        
        async def search_flows(query: str, **kwargs):
            """Search for flows by name or description with wildcard support."""
            try:
                logger.info(f"Searching flows with query: {query}")
                
                headers = get_auth_headers()
                
                async with httpx.AsyncClient() as client:
                    # Get all flows
                    response = await client.get(
                        f"{base_url}/api/v1/flows/",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        flows = response.json()
                        
                        # Search with wildcard support
                        query_lower = query.lower()
                        matched_flows = []
                        
                        for flow in flows:
                            # Check name and description - handle None values
                            flow_name = flow.get("flow_name") or ""
                            flow_desc = flow.get("description") or ""

                            name_match = query_lower in flow_name.lower()
                            desc_match = query_lower in flow_desc.lower()

                            # Wildcard support
                            if "*" in query:
                                import fnmatch
                                pattern = query.lower()
                                name_wildcard = fnmatch.fnmatch(flow_name.lower(), pattern)
                                desc_wildcard = fnmatch.fnmatch(flow_desc.lower(), pattern)

                                if name_wildcard or desc_wildcard:
                                    matched_flows.append(flow)
                            elif name_match or desc_match:
                                matched_flows.append(flow)
                        
                        return {
                            "flows": matched_flows,
                            "query": query,
                            "match_count": len(matched_flows)
                        }
                    else:
                        return {"error": f"Failed to get flows: {response.status_code}"}
                        
            except Exception as e:
                logger.error(f"Error in search_flows: {e}")
                return {"error": str(e)}
        
        async def list_applications(**kwargs):
            """List subscribed applications via API - only returns applications the tenant has subscribed to

            Args:
                app_names: Optional comma-separated list of application names for fuzzy matching
                          (e.g., "gmail,slack,email" matches "Gmail API", "Slack Webhook", "SMTP Email Service")
            """
            try:
                # Debug logging
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"list_applications auth_handler: {auth_handler}")
                logger.info(f"list_applications api_key: {auth_handler.api_key if auth_handler else 'None'}")

                # Extract app_names if provided
                app_names = kwargs.get("app_names")
                if app_names:
                    logger.info(f"list_applications with app_names filter: {app_names}")

                headers = get_auth_headers()
                logger.info(f"list_applications headers: {headers}")

                # Get only subscribed applications
                url = f"{base_url}/api/v1/applications/subscribed"
                logger.info(f"list_applications URL: {url}")

                async with httpx.AsyncClient() as client:
                    # Get subscribed applications
                    response = await client.get(
                        url,
                        params=kwargs,
                        headers=headers
                    )
                    logger.info(f"list_applications response status: {response.status_code}")

                    if response.status_code != 200:
                        return {"applications": [], "error": f"API error: {response.text}"}

                    apps = response.json()
                    
                    # Get subscriptions to enhance application info
                    sub_url = f"{base_url}/api/v1/applications/subscriptions/"
                    logger.info(f"Getting subscriptions from: {sub_url}")
                    
                    sub_response = await client.get(sub_url, headers=headers)
                    
                    if sub_response.status_code == 200:
                        subscriptions = sub_response.json()
                        logger.info(f"Found {len(subscriptions)} subscriptions")
                        
                        # Group subscriptions by app_id
                        subs_by_app = {}
                        for sub in subscriptions:
                            app_id = sub.get("app_id")
                            if app_id:
                                if app_id not in subs_by_app:
                                    subs_by_app[app_id] = []
                                subs_by_app[app_id].append({
                                    "subscription_id": sub.get("subscription_id"),
                                    "status": sub.get("status"),
                                    "has_credentials": bool(sub.get("auth_credentials")),
                                    "instance_name": sub.get("application", {}).get("instance_name"),
                                    "instance_number": sub.get("application", {}).get("instance_number", 1)
                                })
                        
                        # Enhance apps with subscription info
                        for app in apps:
                            app_id = app.get("app_id")
                            if app_id and app_id in subs_by_app:
                                app_subs = subs_by_app[app_id]
                                app["subscriptions"] = app_subs
                                app["subscription_count"] = len(app_subs)
                                app["has_active_subscription"] = any(s["status"] == "active" for s in app_subs)
                                app["active_subscription_count"] = sum(1 for s in app_subs if s["status"] == "active")
                                
                                # If only one subscription, add convenience field
                                if len(app_subs) == 1:
                                    app["subscription_id"] = app_subs[0]["subscription_id"]
                            else:
                                app["subscriptions"] = []
                                app["subscription_count"] = 0
                                app["has_active_subscription"] = False
                                app["requires_subscription"] = True
                    
                    logger.info(f"Returning {len(apps)} applications with subscription info")
                    # Return dual-format: minimal summary + full data
                    return {
                        "summary": f"Found {len(apps)} subscribed application(s)",
                        "data": {"applications": apps}
                    }
                    
            except Exception as e:
                logger.error(f"Error in list_applications: {e}")
                return {"applications": [], "error": str(e)}
        
        async def get_service_information(**kwargs):
            """Get detailed service information including parameter schemas"""
            # Support both old and new parameter names for backward compatibility
            app_id = kwargs.get("app_id") or kwargs.get("app_key") or ""
            service_id = kwargs.get("service_id") or kwargs.get("service_name") or ""
            
            if not app_id or not service_id:
                return {"error": "app_id and service_id parameters are required"}
            
            try:
                async with httpx.AsyncClient() as client:
                    # Call the API endpoint for service information
                    # The endpoint accepts both service_id and service_name
                    response = await client.get(
                        f"{base_url}/api/v1/flow-design/service-information/{app_id}/{service_id}",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 404:
                        error_detail = response.json().get("detail", "Not found")
                        return {"error": error_detail}
                    else:
                        return {"error": f"Failed to get service information: {response.text}"}
            except Exception as e:
                logger.error(f"Error getting service information: {e}")
                return {"error": str(e)}
        
        async def load_seed_application(seed_key: str):
            """Load seed application and return complete details with ID"""
            try:
                async with httpx.AsyncClient() as client:
                    # Install/load the seed application
                    install_response = await client.post(
                        f"{base_url}/api/v1/seed-applications/install",
                        json={"application_key": seed_key},
                        headers=get_auth_headers()
                    )
                    
                    if install_response.status_code == 200:
                        result = install_response.json()
                        return {
                            "success": True,
                            "application_id": result.get("app_id"),
                            "application": result
                        }
                    else:
                        return {"success": False, "error": f"Failed to load: {install_response.text}"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        async def get_flow_design_structure():
            """Get flow design template in importable export format"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/flow-design/structure",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        # Return the structure directly - it's already in export format
                        return response.json()
                    else:
                        return {"error": f"Failed to get structure: {response.text}"}
            except Exception as e:
                return {"error": str(e)}
        
        async def get_flow_design_guideline():
            """Get comprehensive flow design guidelines with structure template and detailed explanations"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/flow-design/guidelines",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        guidelines = response.json()
                        # Return dual-format: concise summary + full guidelines
                        return {
                            "summary": "Flow design guidelines, templates, and best practices retrieved successfully",
                            "data": guidelines
                        }
                    else:
                        return {"error": f"Failed to get guidelines: {response.text}"}
            except Exception as e:
                return {"error": str(e)}
        
        async def get_condition_node_guide():
            """Get comprehensive guide for condition nodes including expression syntax and examples"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/flow-design/condition-guide",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get condition guide: {response.text}"}
            except Exception as e:
                return {"error": str(e)}
        
        async def get_loop_node_guide():
            """Get comprehensive guide for loop nodes including all loop types, variables, and examples"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/flow-design/loop-guide",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get loop guide: {response.text}"}
            except Exception as e:
                return {"error": str(e)}

        async def get_hitl_node_guide():
            """Get comprehensive guide for Human-in-the-Loop (HITL) nodes - task types, assignment, data mapping, timeout/escalation, and output references"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/flow-design/hitl-guide",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get HITL guide: {response.text}"}
            except Exception as e:
                return {"error": str(e)}

        async def get_trigger_node_guide(trigger_type: str = None):
            """Get comprehensive guide for trigger node configurations including manual, schedule, webhook, and event triggers"""
            try:
                async with httpx.AsyncClient() as client:
                    url = f"{base_url}/api/v1/flow-design/trigger-guide"
                    if trigger_type:
                        url += f"?type={trigger_type}"
                    response = await client.get(
                        url,
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get trigger guide: {response.text}"}
            except Exception as e:
                return {"error": str(e)}

        async def get_transform_node_guide():
            """Get comprehensive guide for transform nodes including available modules and examples"""
            try:
                # Import the markdown formatter
                from services.transform_guide_formatter import format_transform_guide_as_markdown

                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/flow-design/transform-guide",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        guide = response.json()

                        # Convert to structured format for better LLM comprehension
                        from services.transform_guide_formatter import format_transform_guide_as_markdown
                        structured_guide = format_transform_guide_as_markdown(guide)
                        # Return the structured guide - no markdown escaping issues
                        return structured_guide
                    else:
                        return {"error": f"Failed to get transform guide: {response.text}"}
            except Exception as e:
                return {"error": str(e)}
        
        async def get_parameter_mapping_guide():
            """Get comprehensive guide for parameter mapping in action nodes"""
            return {
                "description": "How to map parameters in action nodes using parameterMapping",
                "required_format": {
                    "structure": {
                        "parameterMapping": {
                            "fieldName": {
                                "source": "static or variable",
                                "value": "actual value or path"
                            }
                        }
                    },
                    "example": {
                        "parameterMapping": {
                            "message": {"source": "static", "value": "Hello World"},
                            "userId": {"source": "variable", "value": "input.userId"},
                            "data": {"source": "variable", "value": "node_outputs.transform_1.result"}
                        }
                    }
                },
                "variable_paths": {
                    "simple": "input.fieldName",
                    "nested": "node_outputs.nodeId.data.field.subfield",
                    "array": "node_outputs.nodeId.items[0].name",
                    "loop": "loop.item.id"
                },
                "advanced_examples": {
                    "array_mapping": {
                        "description": "Mapping arrays to parameters",
                        "example": {
                            "parameterMapping": {
                                "items": {
                                    "source": "variable",
                                    "value": "node_outputs.transform_1.processed_items"
                                }
                            }
                        }
                    },
                    "conditional_mapping": {
                        "description": "Using conditional values",
                        "example": {
                            "parameterMapping": {
                                "status": {
                                    "source": "variable",
                                    "value": "loop.isLast ? 'complete' : 'processing'"
                                }
                            }
                        }
                    },
                    "nested_object": {
                        "description": "Creating nested parameter structures",
                        "example": {
                            "parameterMapping": {
                                "user": {
                                    "source": "static",
                                    "value": {
                                        "name": "{{input.userName}}",
                                        "email": "{{input.userEmail}}"
                                    }
                                }
                            }
                        }
                    }
                },
                "common_patterns": [
                    "Use static source for literal values",
                    "Use variable source for dynamic values",
                    "Variable paths don't need {{ }} in parameterMapping",
                    "Legacy format uses {{ }} directly in parameters"
                ]
            }
        
        async def get_variable_reference_guide():
            """Get comprehensive guide for variable references and scopes"""
            return {
                "scopes": {
                    "input": {
                        "description": "Variables from manual trigger or webhook",
                        "syntax": "{{input.variable_name}}",
                        "examples": [
                            "{{input.userName}}",
                            "{{input.email}}",
                            "{{input.config.apiKey}}"
                        ]
                    },
                    "node_outputs": {
                        "description": "Outputs from previous nodes",
                        "syntax": "{{node_outputs.node_id.field_name}}",
                        "examples": [
                            "{{node_outputs.api_1.data}}",
                            "{{node_outputs.transform_1.result.items[0]}}",
                            "{{node_outputs.action_2.response.status}}"
                        ]
                    },
                    "global_vars": {
                        "description": "Global variables set by transform nodes",
                        "syntax": "{{global_vars.variable_name}}",
                        "examples": [
                            "{{global_vars.counter}}",
                            "{{global_vars.config.settings}}"
                        ]
                    },
                    "loop": {
                        "description": "Variables available inside loop nodes",
                        "syntax": "{{loop.item}}, {{loop.index}}, {{loop.total}}",
                        "examples": [
                            "{{loop.item}}",
                            "{{loop.index}}",
                            "{{loop.total}}",
                            "{{loop.isFirst}}",
                            "{{loop.isLast}}"
                        ]
                    },
                    "hitl_outputs": {
                        "description": "Outputs from human_in_loop nodes after task completion",
                        "syntax": "{{node_outputs.hitl_node_id.field}}",
                        "examples": [
                            "{{node_outputs.hitl_1.response_action}}",
                            "{{node_outputs.hitl_1.response_data}}",
                            "{{node_outputs.hitl_1.response_data.field_name}}",
                            "{{node_outputs.hitl_1.input_data}}",
                            "{{node_outputs.hitl_1.completed_by}}",
                            "{{node_outputs.hitl_1.task_type}}"
                        ],
                        "response_action_values": ["approved", "rejected", "edited", "reviewed"]
                    }
                },
                "path_resolution": {
                    "simple": "{{variable.field}}",
                    "nested": "{{variable.field.subfield.value}}",
                    "array_index": "{{variable.items[0]}}",
                    "array_property": "{{variable.items[0].name}}",
                    "mixed": "{{node_outputs.api_1.data.users[0].profile.email}}"
                },
                "special_cases": {
                    "undefined_handling": "Returns null if path doesn't exist",
                    "type_coercion": "Automatic conversion between compatible types",
                    "template_literals": "Can embed in strings: 'Hello {{input.name}}'",
                    "json_parsing": "JSON strings are automatically parsed"
                }
            }
        
        async def get_node_examples():
            """Get working examples for each node type"""
            return {
                "action_node": {
                    "description": "API call with dynamic parameters",
                    "example": {
                        "id": "api_1",
                        "type": "action",
                        "position": {"x": 250, "y": 250},
                        "data": {
                            "label": "Call API",
                            "appId": "app_123",
                            "service": "create_user",
                            "parameterMapping": {
                                "name": {"source": "variable", "value": "input.userName"},
                                "email": {"source": "variable", "value": "input.email"},
                                "role": {"source": "static", "value": "user"}
                            }
                        }
                    }
                },
                "transform_node": {
                    "description": "Data processing with Python",
                    "example": {
                        "id": "transform_1",
                        "type": "transform",
                        "position": {"x": 250, "y": 400},
                        "data": {
                            "label": "Process Data",
                            "script": """import json
import datetime

# Get API response
api_data = node_outputs.get('api_1', {})
items = api_data.get('data', {}).get('items', [])

# Process items
processed = []
for idx, item in enumerate(items):
    processed.append({
                                'id': item.get('id'),
        'index': idx,
        'name': item.get('name', '').upper(),
        'processed_at': datetime.datetime.now().isoformat()
    })

# Set output
output = {
    'count': len(processed),
    'items': processed
}"""
                        }
                    }
                },
                "loop_node": {
                    "description": "Iterate over array from API",
                    "example": {
                        "id": "loop_1",
                        "type": "loop",
                        "position": {"x": 250, "y": 400},
                        "data": {
                            "label": "Process Each Item",
                            "loopType": "forEach",
                            "arrayPath": "node_outputs.api_1.data.items",
                            "iteratorName": "item",
                            "maxIterations": 100
                        }
                    }
                },
                "condition_node": {
                    "description": "Conditional branching",
                    "example": {
                        "id": "condition_1",
                        "type": "condition",
                        "position": {"x": 250, "y": 400},
                        "data": {
                            "label": "Check Status",
                            "condition": "{{node_outputs.api_1.status}} == 'success' && {{node_outputs.api_1.data.count}} > 0"
                        }
                    }
                },
                "response_node": {
                    "description": "Return formatted response",
                    "example": {
                        "id": "response_1",
                        "type": "response",
                        "position": {"x": 250, "y": 600},
                        "data": {
                            "label": "Return Result",
                            "variable": "{{node_outputs.transform_1.result}}",
                            "statusCode": 200,
                            "headers": {
                                "Content-Type": "application/json"
                            }
                        }
                    }
                }
            }
        
        async def get_pdf_generation_guide():
            """Get comprehensive guide for PDF generation using ReportLab"""
            return {
                "overview": "Generate PDFs using ReportLab library in transform nodes",
                "basic_example": """# Basic PDF generation
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from io import BytesIO
import base64

# Create PDF in memory
buffer = BytesIO()
c = canvas.Canvas(buffer, pagesize=A4)

# Add content
c.drawString(100, 750, "Hello World")
c.drawString(100, 730, f"Generated for: {input.get('userName', 'User')}")

# Save PDF
c.save()
pdf_bytes = buffer.getvalue()
buffer.close()

# Return base64 encoded
output = {
    'pdf': base64.b64encode(pdf_bytes).decode('utf-8'),
    'filename': 'document.pdf',
    'content_type': 'application/pdf'
}""",
                "advanced_example": """# Advanced PDF with tables and styling
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from io import BytesIO
import base64

# Setup
buffer = BytesIO()
doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1*inch)
styles = getSampleStyleSheet()
story = []

# Title
title_style = ParagraphStyle(
    'CustomTitle',
    parent=styles['Heading1'],
    fontSize=24,
    textColor=colors.HexColor('#003366'),
    alignment=1  # Center
)
story.append(Paragraph("Sales Report", title_style))
story.append(Spacer(1, 0.3*inch))

# Table data from API
api_data = node_outputs.get('api_1', {}).get('data', [])
table_data = [['Product', 'Quantity', 'Price', 'Total']]

for item in api_data:
    row = [
        item.get('product_name', ''),
        str(item.get('quantity', 0)),
        f"${item.get('price', 0):.2f}",
        f"${item.get('total', 0):.2f}"
    ]
    table_data.append(row)

# Create table
table = Table(table_data, colWidths=[2*inch, 1*inch, 1*inch, 1.5*inch])
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 14),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black)
]))
story.append(table)

# Build PDF
doc.build(story)
pdf_bytes = buffer.getvalue()
buffer.close()

# Output
output = {
    'pdf': base64.b64encode(pdf_bytes).decode('utf-8'),
    'filename': 'sales_report.pdf'
}""",
                "available_components": {
                    "page_sizes": ["A4", "Letter", "Legal", "A3", "A5"],
                    "flowables": ["Paragraph", "Table", "Spacer", "PageBreak", "Image"],
                    "styles": ["Normal", "Title", "Heading1-6", "Code", "BodyText"],
                    "colors": ["colors.black", "colors.red", "colors.blue", "colors.HexColor('#RRGGBB')"],
                    "units": ["inch", "cm", "mm", "pica"]
                },
                "tips": [
                    "Always use BytesIO for in-memory PDF generation",
                    "Return base64 encoded PDF for easy transmission",
                    "Include filename and content_type in output",
                    "Use SimpleDocTemplate for multi-page documents",
                    "Use Canvas for low-level drawing operations"
                ]
            }
        
        async def validate_node_configuration(**kwargs):
            """Validate individual node configuration"""
            node = kwargs.get("node", {})
            node_type = node.get("type", "")
            
            errors = []
            warnings = []
            
            # Validate based on node type
            if node_type == "action":
                data = node.get("data", {})
                if not data.get("appId"):
                    errors.append("Action node missing appId")
                if not data.get("service"):
                    errors.append("Action node missing service")
                    
                # Check parameter mapping
                param_mapping = data.get("parameterMapping", {})
                for key, value in param_mapping.items():
                    if isinstance(value, dict):
                        if "source" not in value:
                            warnings.append(f"Parameter {key} missing source field")
                        if "value" not in value:
                            warnings.append(f"Parameter {key} missing value field")
                            
            elif node_type == "transform":
                data = node.get("data", {})
                script = data.get("script", "")
                if not script:
                    errors.append("Transform node has empty script")
                if "output =" not in script and "output=" not in script:
                    warnings.append("Transform script may not set output variable")
                    
            elif node_type == "loop":
                data = node.get("data", {})
                if data.get("loopType") == "forEach":
                    if not data.get("arrayPath"):
                        errors.append("forEach loop missing arrayPath")
                        
            elif node_type == "condition":
                data = node.get("data", {})
                if not data.get("condition"):
                    errors.append("Condition node missing condition expression")
                    
            elif node_type == "response":
                data = node.get("data", {})
                if not data.get("variable"):
                    warnings.append("Response node has no variable to return")
            
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "node_type": node_type
            }
        
        async def get_application_services_list(**kwargs):
            """Get basic service information for a specific application"""
            # Extract app_id from kwargs (handle different parameter names for compatibility)
            app_id = kwargs.get("app_id") or kwargs.get("app_name") or kwargs.get("application_id") or ""
            
            if not app_id:
                return {"error": "app_id parameter is required", "received_params": kwargs}
            
            try:
                async with httpx.AsyncClient() as client:
                    # Call the simplified services list endpoint for better performance
                    # The backend will handle resolving UUID, seed_key, or app_name
                    services_response = await client.get(
                        f"{base_url}/api/v1/applications/{app_id}/services_list",
                        headers=get_auth_headers()
                    )
                    
                    if services_response.status_code == 200:
                        services = services_response.json()
                        
                        # Return the services directly with only basic info
                        return {
                            "services": services,
                            "service_count": len(services),
                            "note": "For detailed parameter information, use get_service_information(app_id, service_id)"
                        }
                    else:
                        return {"error": f"Failed to get services: {services_response.text}"}
            except Exception as e:
                return {"error": str(e)}
        
        async def get_application_events_list(**kwargs):
            """Get basic event information for a specific application"""
            # Extract app_id from kwargs (handle different parameter names for compatibility)
            app_id = kwargs.get("app_id") or kwargs.get("app_name") or kwargs.get("application_id") or ""
            
            if not app_id:
                return {"error": "app_id parameter is required", "received_params": kwargs}
            
            try:
                async with httpx.AsyncClient() as client:
                    # Call the simplified events list endpoint for better performance
                    # The backend will handle resolving UUID, seed_key, or app_name
                    events_response = await client.get(
                        f"{base_url}/api/v1/applications/{app_id}/events_list",
                        headers=get_auth_headers()
                    )
                    
                    if events_response.status_code == 200:
                        events = events_response.json()
                        
                        # Return the events directly with only basic info
                        return {
                            "events": events,
                            "event_count": len(events),
                            "note": "For detailed parameter information and output schema, use get_event_information(app_id, event_id)"
                        }
                    else:
                        return {"error": f"Failed to get events: {events_response.text}"}
            except Exception as e:
                return {"error": str(e)}
        
        async def get_event_information(**kwargs):
            """Get detailed event information including output schema and parameters"""
            # Support both old and new parameter names for backward compatibility
            app_id = kwargs.get("app_id") or kwargs.get("app_key") or ""
            event_id = kwargs.get("event_id") or kwargs.get("event_name") or ""
            
            if not app_id or not event_id:
                return {"error": "app_id and event_id parameters are required"}
            
            try:
                async with httpx.AsyncClient() as client:
                    # Call the API endpoint for event information
                    # The endpoint accepts both event_id and event_name
                    response = await client.get(
                        f"{base_url}/api/v1/flow-design/event-information/{app_id}/{event_id}",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    elif response.status_code == 404:
                        error_detail = response.json().get("detail", "Not found")
                        return {"error": error_detail}
                    else:
                        return {"error": f"Failed to get event information: {response.text}"}
            except Exception as e:
                logger.error(f"Error getting event information: {e}")
                return {"error": str(e)}
        
        async def fix_flow_json(**kwargs):
            """Fix common issues in flow JSON via API endpoint"""
            # kwargs contains the flow json, could be in different formats
            flow_json = kwargs
            
            # Handle different input formats like validate_flow_design
            if "flow_definition" in flow_json and "flow_name" in flow_json:
                # Already in correct format
                flow_data = flow_json
            elif "flow" in flow_json and isinstance(flow_json["flow"], dict):
                # Export format, extract the flow
                flow_data = flow_json["flow"]
            elif "nodes" in flow_json and "edges" in flow_json:
                # Just the definition, wrap it with trigger config from nodes
                # Extract trigger config from nodes if present
                trigger_config = {
                    "type": "manual",
                    "manual_variables": []
                }
                
                # Find trigger node to get manual variables
                for node in flow_json.get("nodes", []):
                    if node.get("type") == "trigger":
                        data = node.get("data", {})
                        if data.get("triggerType") == "manual":
                            manual_vars = data.get("manualVariables", [])
                            # Ensure proper structure
                            trigger_config["manual_variables"] = [
                                {
                                    "id": var.get("id", var.get("name", "")),
                                    "name": var.get("name", ""),
                                    "displayName": var.get("displayName", var.get("name", "")),
                                    "dataType": var.get("dataType", "string"),
                                    "uiControl": var.get("uiControl", "text"),
                                    "required": var.get("required", True),
                                    "defaultValue": var.get("defaultValue", "")
                                }
                                for var in manual_vars
                            ]
                        break
                
                flow_data = {
                    "flow_name": flow_json.get("flow_name", flow_json.get("name", "Untitled")),
                    "description": flow_json.get("description", ""),
                    "trigger_config": trigger_config,
                    "flow_definition": {
                        "nodes": flow_json["nodes"],
                        "edges": flow_json["edges"]
                    }
                }
            else:
                # Assume it's the complete structure
                flow_data = flow_json
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{base_url}/api/v1/flow-design/fix",
                        json=flow_data,
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        result = response.json()
                        # Return the fixed flow in a format the agent can use
                        if "fixed_flow" in result:
                            return {
                                "success": True,
                                "fixed_flow": result["fixed_flow"],
                                "changes": result.get("changes", []),
                                "validation": result.get("validation", {})
                            }
                        return result
                    else:
                        error_msg = response.text
                        try:
                            error_json = response.json()
                            if "detail" in error_json:
                                error_msg = error_json["detail"]
                        except:
                            pass
                        return {"success": False, "error": f"API error: {error_msg}"}
            except Exception as e:
                return {"success": False, "error": f"Fix failed: {str(e)}"}
        
        # Seed application wrapper functions
        async def list_seed_applications(**kwargs):
            """List all available seed applications"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/seed-applications/",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to list seed applications: {response.text}"}
            except Exception as e:
                return {"error": f"Error listing seed applications: {str(e)}"}
        
        async def create_seed_application(app_key: str, app_name: str, category: str = "Integration",
                                         description: str = "", **kwargs):
            """Create a new seed application"""
            try:
                request_data = {
                    "app_key": app_key,
                    "app_name": app_name,
                    "app_type": kwargs.get("app_type", "api"),
                    "app_scope": kwargs.get("app_scope", "global"),
                    "category": category,
                    "auth_type": kwargs.get("auth_type", "api_key"),
                    "description": description,
                    "base_url": kwargs.get("base_url", ""),
                    "version": kwargs.get("version", "1.0.0"),
                    "services": kwargs.get("services", []),
                    "events": kwargs.get("events", [])
                }
                if isinstance(kwargs.get("auth_config"), dict):
                    request_data["auth_config"] = kwargs["auth_config"]
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{base_url}/api/v1/seed-applications/create",
                        json=request_data,
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to create seed application: {response.text}"}
            except Exception as e:
                return {"error": f"Error creating seed application: {str(e)}"}
        
        async def get_all_seed_applications_raw(**kwargs):
            """Get all seed applications as raw JSON data for testing and deployment tools"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/seed-applications/raw/all",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get raw seed applications: {response.text}"}
            except Exception as e:
                return {"error": f"Error getting raw seed applications: {str(e)}"}
        
        async def get_seed_application_guide(**kwargs):
            """Get comprehensive guide for creating seed applications with all valid values and structure"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/seed-applications/guides/application",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get seed application guide: {response.text}"}
            except Exception as e:
                return {"error": f"Error getting seed application guide: {str(e)}"}

        async def get_service_guide(**kwargs):
            """Get comprehensive guide for creating application services with all valid values"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/seed-applications/guides/service",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get service guide: {response.text}"}
            except Exception as e:
                return {"error": f"Error getting service guide: {str(e)}"}

        async def get_event_guide(**kwargs):
            """Get comprehensive guide for creating application events/webhooks with all valid values"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}/api/v1/seed-applications/guides/event",
                        headers=get_auth_headers()
                    )
                    if response.status_code == 200:
                        return response.json()
                    else:
                        return {"error": f"Failed to get event guide: {response.text}"}
            except Exception as e:
                return {"error": f"Error getting event guide: {str(e)}"}


        # ---- Tenant seed applications (a tenant's own connectors) ----------
        # Thin routes onto /api/v1/tenant-seed-applications; the API decides
        # who may do what and which tenant it is (always the caller's).
        async def _tenant_seed_call(method: str, path: str = "", body: Optional[Dict[str, Any]] = None,
                                    params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.request(
                        method, f"{base_url}/api/v1/tenant-seed-applications{path}",
                        json=body, params=params, headers=get_auth_headers())
                try:
                    data = response.json()
                except ValueError:
                    data = {"detail": response.text}
                if response.status_code >= 400:
                    detail = data.get("detail") if isinstance(data, dict) else data
                    return {"success": False, "status_code": response.status_code, "error": detail}
                return data if isinstance(data, dict) else {"result": data}
            except Exception as e:
                return {"success": False, "error": f"Tenant seed application request failed: {e}"}

        def _seed_arg(seed):
            if isinstance(seed, str):
                try:
                    seed = json.loads(seed)
                except json.JSONDecodeError as e:
                    return None, {"success": False, "error": f"seed is not valid JSON: {e}"}
            if not isinstance(seed, dict):
                return None, {"success": False, "error": "seed must be the full seed application JSON object"}
            return seed, None

        async def list_tenant_seed_applications(**kwargs):
            """List YOUR tenant's own seed applications with install status"""
            return await _tenant_seed_call("GET", "/")

        async def get_tenant_seed_application(app_key: str, **kwargs):
            """Get the full JSON of one of your tenant's seed applications"""
            return await _tenant_seed_call("GET", f"/{app_key}")

        async def validate_tenant_seed_application(seed, **kwargs):
            """Validate a full seed application JSON without saving it"""
            seed, err = _seed_arg(seed)
            if err:
                return err
            return await _tenant_seed_call("POST", "/validate", body={"seed": seed})

        async def save_tenant_seed_application(seed, install: bool = False, **kwargs):
            """Create or replace one of your tenant's seed applications from its FULL JSON (optionally install it)"""
            seed, err = _seed_arg(seed)
            if err:
                return err
            key = str(seed.get("key") or "")
            if not key:
                return {"success": False, "error": "seed.key is required"}
            if isinstance(install, str):
                install = install.strip().lower() in ("1", "true", "yes")
            return await _tenant_seed_call("PUT", f"/{key}", body={"seed": seed, "install": bool(install)})

        async def install_tenant_seed_application(app_key: str, **kwargs):
            """Install (or update in place, keeping ids and subscriptions) one of your tenant's seed applications"""
            return await _tenant_seed_call("POST", f"/{app_key}/install")

        async def delete_tenant_seed_application(app_key: str, **kwargs):
            """Delete one of your tenant's seed applications (refused while it is still subscribed)"""
            return await _tenant_seed_call("DELETE", f"/{app_key}")

        return {
            "validate_flow_design": validate_flow_design,
            "validate_flow_comprehensive": validate_flow_comprehensive,  # Handles base64 and returns proper error messages
            "list_applications": list_applications,
            "search_applications": search_applications,
            "search_services": search_services,
            "search_flows": search_flows,
            "get_application_services_list": get_application_services_list,
            "get_service_information": get_service_information,
            "get_application_events_list": get_application_events_list,
            "get_event_information": get_event_information,
            "load_seed_application": load_seed_application,
            "get_flow_design_structure": get_flow_design_structure,
            "get_flow_design_guideline": get_flow_design_guideline,
            "get_condition_node_guide": get_condition_node_guide,
            "get_transform_node_guide": get_transform_node_guide,
            "get_loop_node_guide": get_loop_node_guide,
            "get_hitl_node_guide": get_hitl_node_guide,
            "get_trigger_node_guide": get_trigger_node_guide,
            "get_parameter_mapping_guide": get_parameter_mapping_guide,
            "get_variable_reference_guide": get_variable_reference_guide,
            "get_node_examples": get_node_examples,
            "get_pdf_generation_guide": get_pdf_generation_guide,
            "validate_node_configuration": validate_node_configuration,
            # Seed application tools
            "list_seed_applications": list_seed_applications,
            "create_seed_application": create_seed_application,
            "get_all_seed_applications_raw": get_all_seed_applications_raw,
            # Seed application guide tools
            "get_seed_application_guide": get_seed_application_guide,
            "get_service_guide": get_service_guide,
            "get_event_guide": get_event_guide,
            # Tenant seed application tools
            "list_tenant_seed_applications": list_tenant_seed_applications,
            "get_tenant_seed_application": get_tenant_seed_application,
            "validate_tenant_seed_application": validate_tenant_seed_application,
            "save_tenant_seed_application": save_tenant_seed_application,
            "install_tenant_seed_application": install_tenant_seed_application,
            "delete_tenant_seed_application": delete_tenant_seed_application,
        }
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any],
                          auth_handler: MCPAuthHandler) -> Dict[str, Any]:
        """Execute an MCP tool with given parameters"""
        logger.info(f"🔧 MCP Bridge executing tool: {tool_name} with params: {list(parameters.keys()) if parameters else 'none'}")

        # This request's identity, for every shared tool object (see _RequestScopedAuth).
        _REQUEST_AUTH.set(auth_handler)

        if tool_name in GLOBAL_CATALOG_WRITE_TOOLS and _caller_role(auth_handler) != "INSTANCE_ADMIN":
            raise ValueError(
                f"'{tool_name}' changes the GLOBAL seed catalog shared by every tenant and needs an "
                "instance admin. To create or change your own tenant's connector use "
                "save_tenant_seed_application (full seed JSON) and install_tenant_seed_application."
            )

        # Check if this is an API wrapper tool that needs dynamic creation
        if tool_name in self._api_wrapper_tools:
            logger.info(f"  └─ Using API wrapper for {tool_name}")
            # Create API wrapper functions with proper auth
            api_wrappers = self._create_api_wrapper_functions(auth_handler)
            if tool_name in api_wrappers:
                # Normalize parameters for backward compatibility
                normalized_params = self._normalize_tool_parameters(tool_name, parameters)
                # Execute the dynamically created function
                result = await api_wrappers[tool_name](**normalized_params)
                logger.info(f"  └─ Tool {tool_name} returned: {str(result)[:200] if result else 'None'}...")

                # Clear local seed_manager cache after seed app creation/modification
                # so subsequent registry tool calls (like add_service_to_application)
                # can find newly created applications
                if tool_name in ("create_seed_application", "load_seed_application"):
                    self.seed_manager.refresh_cache()
                    logger.info(f"  └─ Refreshed seed_manager cache after {tool_name}")

                return result
        
        if tool_name not in self._tool_registry:
            logger.error(f"  └─ ❌ Unknown tool: {tool_name}")
            raise ValueError(f"Unknown tool: {tool_name}")

        logger.info(f"  └─ Using registry tool for {tool_name}")

        # The auth handler reaches the closures (self.auth_handler) and the shared
        # tool instances (.auth / .auth_handler) through _REQUEST_AUTH, set above —
        # never by assigning to those shared objects.

        # Normalize parameters for backward compatibility
        normalized_params = self._normalize_tool_parameters(tool_name, parameters)

        # Get the tool function
        tool_func = self._tool_registry[tool_name]

        # Execute the tool with normalized parameters
        result = await tool_func(**normalized_params)
        logger.info(f"  └─ Tool {tool_name} returned: {str(result)[:200] if result else 'None'}...")
        return result
    
    async def get_resource(self, uri: str) -> Dict[str, Any]:
        """Get an MCP resource by URI"""
        # Parse URI to get base and parameters
        base_uri = uri.split('?')[0]
        
        # Check for catalog with specific app
        if base_uri.startswith("seed-apps://catalog/"):
            app_key = base_uri.replace("seed-apps://catalog/", "")
            return await self._get_app_resource(app_key)
        
        # Check for template resources
        if base_uri.startswith("seed-apps://templates/"):
            category = base_uri.replace("seed-apps://templates/", "")
            return await self._get_template_resource(category)
        
        # Check base resources
        if base_uri in self._resource_registry:
            return await self._resource_registry[base_uri]()
        
        raise ValueError(f"Unknown resource: {uri}")
    
    async def _get_catalog_resource(self) -> Dict[str, Any]:
        """Get the complete seed applications catalog"""
        applications = self.seed_manager.list_applications()
        return {
            "type": "catalog",
            "total": len(applications),
            "applications": applications
        }
    
    async def _get_app_resource(self, app_key: str) -> Dict[str, Any]:
        """Get details for a specific application"""
        app = self.seed_manager.get_application(app_key)
        if not app:
            raise ValueError(f"Application not found: {app_key}")
        return {
            "type": "application",
            "key": app_key,
            "data": app
        }
    
    async def _get_schema_resource(self) -> Dict[str, Any]:
        """Get the seed application JSON schema"""
        return {
            "type": "schema",
            "schema": self.seed_manager.get_schema()
        }
    
    async def _get_template_resource(self, category: str) -> Dict[str, Any]:
        """Get templates for a specific category"""
        applications = self.seed_manager.list_applications(category=category)
        templates = [app for app in applications if app.get('is_template', False)]
        return {
            "type": "templates",
            "category": category,
            "templates": templates
        }
    
    async def _get_docs_resource(self) -> Dict[str, Any]:
        """Get documentation resource"""
        return {
            "type": "documentation",
            "sections": {
                "overview": "IOFlow MCP Server enables management of seed applications",
                "tools": {
                    "exploration": "Tools for discovering and exploring seed applications",
                    "management": "Tools for creating and editing applications",
                    "testing": "Tools for validating and testing applications",
                    "deployment": "Tools for installing and managing deployments"
                },
                "authentication": "Uses IOFlow API keys with role-based permissions",
                "resources": "Access catalog, schemas, and templates via resource URIs"
            }
        }
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools with descriptions and schemas"""
        tools = []
        
        # Add API wrapper tools with predefined schemas
        api_tool_schemas = {
            "list_tenant_seed_applications": {
                "description": "List YOUR tenant's own seed applications (connectors only your tenant sees) with install status",
                "properties": {},
                "required": []
            },
            "get_tenant_seed_application": {
                "description": "Get the full JSON of one of your tenant's seed applications",
                "properties": {"app_key": {"type": "string", "description": "Seed application key"}},
                "required": ["app_key"]
            },
            "validate_tenant_seed_application": {
                "description": "Validate a FULL seed application JSON (key, application, services, events) exactly as a save would, without writing",
                "properties": {"seed": {"type": "object", "description": "The full seed application JSON"}},
                "required": ["seed"]
            },
            "save_tenant_seed_application": {
                "description": "Create or replace one of your tenant's seed applications from its FULL JSON (key, application, services, events). Read get_seed_application_guide / get_service_guide / get_event_guide first. Invalid JSON is refused with its errors. install=true installs it (or updates the install in place, keeping ids and subscriptions).",
                "properties": {
                    "seed": {"type": "object", "description": "The full seed application JSON"},
                    "install": {"type": "boolean", "description": "Install / update the tenant application after saving"}
                },
                "required": ["seed"]
            },
            "install_tenant_seed_application": {
                "description": "Install one of your tenant's seed applications, or update its install in place (ids and subscriptions are kept)",
                "properties": {"app_key": {"type": "string", "description": "Seed application key"}},
                "required": ["app_key"]
            },
            "delete_tenant_seed_application": {
                "description": "Delete one of your tenant's seed applications and its install (refused while it is still subscribed)",
                "properties": {"app_key": {"type": "string", "description": "Seed application key"}},
                "required": ["app_key"]
            },
            "create_seed_application": {
                "description": "Create a GLOBAL seed application shared by every tenant (instance admins only). Tenants create their own connectors with save_tenant_seed_application.",
                "properties": {
                    "app_key": {"type": "string"}, "app_name": {"type": "string"},
                    "description": {"type": "string"}, "category": {"type": "string"},
                    "auth_type": {"type": "string"}, "app_type": {"type": "string"},
                    "base_url": {"type": "string"}, "version": {"type": "string"},
                    "services": {"type": "array"}, "events": {"type": "array"},
                    "auth_config": {"type": "object"}
                },
                "required": ["app_key", "app_name"]
            },
            "validate_flow_design": {
                "description": "Validate a flow design without saving it. Pass the flow body's fields at the top level (flow_name, trigger_config, flow_definition {nodes, edges}, …), or just flow_definition — either the bare {nodes, edges} (the trigger is read from the trigger node) or the whole flow body.",
                "properties": {
                    "flow_name": {"type": "string", "description": "The flow's name"},
                    "description": {"type": "string"},
                    "trigger_config": {"type": "object", "description": "The flow's trigger configuration"},
                    "flow_definition": {
                        "type": "object",
                        "description": "{nodes, edges}, or the whole flow body (flow_name, trigger_config, flow_definition, …)"
                    },
                    "functions_base64": {"type": "string", "description": "Base64 Python for transform functions_used"}
                },
                "required": ["flow_definition"]
            },
            "list_applications": {
                "description": "List installed applications with subscription information",
                "properties": {},
                "required": []
            },
            "get_service_information": {
                "description": "Get detailed service information including parameter schemas",
                "properties": {
                    "app_id": {
                        "type": "string",
                        "description": "Application ID (UUID) from list_applications()"
                    },
                    "service_id": {
                        "type": "string",
                        "description": "Service ID (UUID) from get_application_services()"
                    }
                },
                "required": ["app_id", "service_id"]
            },
            "load_seed_application": {
                "description": "Load seed application and return complete details with ID",
                "properties": {
                    "seed_key": {
                        "type": "string",
                        "description": "Seed application key to load"
                    }
                },
                "required": ["seed_key"]
            },
            "get_flow_design_structure": {
                "description": "Get flow design JSON schema and structure",
                "properties": {},
                "required": []
            },
            "get_flow_design_guideline": {
                "description": "Get comprehensive flow design guidelines with structure template, detailed explanations, examples, and best practices for creating flows in IOFlow",
                "properties": {},
                "required": []
            },
            "get_condition_node_guide": {
                "description": "Get comprehensive guide for condition nodes including expression syntax, operators, variable access patterns, common patterns, and troubleshooting tips",
                "properties": {},
                "required": []
            },
            "get_loop_node_guide": {
                "description": "Get comprehensive guide for loop nodes including forEach, while, and for loops with configuration, variables, breaking conditions, and examples",
                "properties": {},
                "required": []
            },
            "get_trigger_node_guide": {
                "description": "Get comprehensive guide for trigger node configurations including manual, schedule, webhook, and event triggers with configuration schemas, examples, and best practices",
                "properties": {
                    "trigger_type": {
                        "type": "string",
                        "description": "Optional filter for specific trigger type: 'manual', 'schedule', 'webhook', or 'event'. If not provided, returns all trigger guides."
                    }
                },
                "required": []
            },
            "get_application_services_list": {
                "description": "Get detailed service information for a specific application",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application (e.g., 'OpenAI', 'Google Gemini')"
                    }
                },
                "required": ["app_name"]
            },
            "get_application_events_list": {
                "description": "Get list of events for a specific application",
                "properties": {
                    "app_id": {
                        "type": "string",
                        "description": "Application ID (UUID), seed_key, or app_name"
                    }
                },
                "required": ["app_id"]
            },
            "get_event_information": {
                "description": "Get detailed event information including output schema and parameters",
                "properties": {
                    "app_id": {
                        "type": "string",
                        "description": "Application ID (UUID) from list_applications()"
                    },
                    "event_id": {
                        "type": "string",
                        "description": "Event ID (UUID) from get_application_events()"
                    }
                },
                "required": ["app_id", "event_id"]
            }
        }
        
        # Add API wrapper tools.
        #
        # EVERY declared wrapper is listed, whether or not somebody wrote it an
        # entry in `api_tool_schemas` above. They were all executable already;
        # only the LIST skipped the ones without a hand-written schema, so 17
        # working tools — most of the node guides among them — were invisible
        # to any client that discovers tools the documented way (GET
        # /api/mcp/tools). A remote agent cannot call what it cannot see, and
        # nothing told it they existed.
        for tool_name in self._api_wrapper_tools:
            schema_info = api_tool_schemas.get(tool_name)
            if schema_info:
                input_schema = {
                    "type": "object",
                    "properties": schema_info["properties"],
                    "required": schema_info.get("required", [])
                }
                description = schema_info["description"]
            else:
                # Undocumented parameters: say so rather than advertising an
                # empty object, which would read as "takes no arguments" and
                # send callers into a required-parameter error.
                input_schema = {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": True
                }
                description = (
                    f"{tool_name.replace('_', ' ').capitalize()}. "
                    "Parameters are not declared for this tool — call it with "
                    "no arguments to discover its usage, or consult the "
                    "matching guide tool."
                )
            tools.append({
                "name": tool_name,
                "description": description,
                "category": self._get_tool_category(tool_name),
                "input_schema": input_schema
            })
        
        # Add registry tools
        for name, func in self._tool_registry.items():
            # Generate input schema from function signature
            import inspect
            sig = inspect.signature(func)
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                    
                # Determine type
                param_type = "string"  # default
                if param.annotation != inspect.Parameter.empty:
                    if param.annotation == bool:
                        param_type = "boolean"
                    elif param.annotation == int:
                        param_type = "integer"
                    elif param.annotation == float:
                        param_type = "number"
                    elif hasattr(param.annotation, '__origin__'):
                        # Handle Optional, List, Dict etc
                        if param.annotation.__origin__ == list:
                            param_type = "array"
                        elif param.annotation.__origin__ == dict:
                            param_type = "object"
                
                properties[param_name] = {
                    "type": param_type,
                    "description": f"Parameter: {param_name}"
                }
                
                # Check if required
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
            
            input_schema = {
                "type": "object",
                "properties": properties
            }
            if required:
                input_schema["required"] = required
            
            tools.append({
                "name": name,
                "description": func.__doc__.strip() if func.__doc__ else "No description available",
                "category": self._get_tool_category(name),
                "input_schema": input_schema
            })
        return tools
    
    def _get_tool_category(self, tool_name: str) -> str:
        """Determine tool category from name"""
        if any(prefix in tool_name for prefix in ['explore_', 'get_', 'search_', 'compare_']):
            return "exploration"
        elif any(prefix in tool_name for prefix in ['create_', 'edit_', 'add_', 'remove_', 'update_', 'delete_', 'clone_', 'import_', 'export_']):
            return "management"
        elif any(prefix in tool_name for prefix in ['validate_', 'test_', 'simulate_', 'debug_', 'generate_']):
            return "testing"
        elif any(prefix in tool_name for prefix in ['install_', 'uninstall_', 'list_', 'verify_', 'rollback_', 'schedule_']):
            return "deployment"
        return "other"


# Initialize service
mcp_service = MCPBridgeService()


@router.get("/info", response_model=MCPServerInfo)
async def get_mcp_info(current_user: User = Depends(get_current_user)):
    """Get MCP server information and capabilities"""
    tools = mcp_service.get_available_tools()
    
    # Group tools by category
    capabilities = {}
    for tool in tools:
        category = tool["category"]
        if category not in capabilities:
            capabilities[category] = []
        capabilities[category].append(tool["name"])
    
    return MCPServerInfo(
        capabilities=capabilities,
        tool_count=len(tools)
    )


@router.post("/tools/execute", response_model=MCPToolResponse)
async def execute_mcp_tool(
    request: MCPToolRequest,
    auth_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute an MCP tool with dual authentication support"""
    import time
    start_time = time.time()

    try:
        # Import enhanced auth handler for dual authentication support
        from mcp_server.auth.enhanced_mcp_auth import EnhancedMCPAuthHandler

        # Initialize enhanced auth handler
        auth_handler = EnhancedMCPAuthHandler(
            base_url=settings.api_url  # Use configured API URL
        )

        # Extract authentication from request
        auth_header = auth_request.headers.get("authorization", "") if auth_request else ""

        # Determine authentication type and authenticate accordingly
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix

            # Check if it's an API key (starts with "ioflow_") or JWT session token
            if token.startswith("ioflow_"):
                # External agent using API key
                await auth_handler.authenticate(api_key=token)
            else:
                # Frontend user with JWT session token
                await auth_handler.authenticate(session_token=token)
        else:
            # No auth header or non-Bearer auth, use current_user from session (frontend user)
            # Extract the enum value if role is an enum
            user_role = current_user.role
            if hasattr(user_role, 'value'):
                user_role = user_role.value
            elif isinstance(user_role, str) and user_role.startswith('UserRole.'):
                user_role = user_role.replace('UserRole.', '')

            # Set user context directly from authenticated user
            auth_handler.user_info = {
                "id": current_user.user_id,
                "email": current_user.email,
                "role": user_role,
                "tenant_id": current_user.tenant_id
            }
            auth_handler.auth_type = "session"

            # Generate a JWT token for the current user to use in internal API calls
            # This ensures proper authentication when MCP tools make internal API requests
            from core.security import AuthService
            from datetime import timedelta

            internal_token = AuthService.create_access_token(
                data={
                    "sub": current_user.user_id,
                    "tenant_id": current_user.tenant_id,
                    "email": current_user.email
                },
                expires_delta=timedelta(minutes=5)  # Short-lived token for internal use
            )

            # Set session_token so get_auth_headers() returns proper Authorization header
            # This ensures all MCP tools get valid auth regardless of which fallback path they use
            auth_handler.session_token = internal_token

            # Set headers for API calls to include user context
            auth_handler._headers = {
                "Authorization": f"Bearer {internal_token}",
                "Content-Type": "application/json",
                "X-User-Id": str(current_user.user_id),
                "X-Auth-Type": "session"
            }

        # Execute the tool
        result = await mcp_service.execute_tool(
            tool_name=request.tool,
            parameters=request.parameters,
            auth_handler=auth_handler
        )

        execution_time = time.time() - start_time

        # Extract actual data from result if it's a dict (avoid double-wrapping)
        # The result from API wrappers is already a plain dict, return it directly
        actual_result = result

        return MCPToolResponse(
            success=True,
            result=actual_result,
            tool=request.tool,
            execution_time=execution_time
        )
    
    except ValueError as e:
        return MCPToolResponse(
            success=False,
            error=str(e),
            tool=request.tool,
            execution_time=time.time() - start_time
        )
    except Exception as e:
        logger.error(f"Error executing MCP tool {request.tool}: {str(e)}")
        return MCPToolResponse(
            success=False,
            error=f"Internal error: {str(e)}",
            tool=request.tool,
            execution_time=time.time() - start_time
        )


@router.get("/agent-pack")
async def get_agent_pack(
    agent: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """IOFlow's design agents — the ONE definition every surface runs.

    Returns ``{schema, version, tool_surface, agents: [{name, adk_id,
    description, tools, prompt}]}`` from ``backend/agent_pack``. The IOFlow
    Assistant and the Claude Code plugin use the same files, so an external
    agent (Twasta's Ask-AI) that loads its IOFlow sub-agents from here runs
    exactly the prompts IOFlow's own assistant runs. ``version`` changes
    whenever any agent changes — cache on it. Every tool listed is a tool of
    this bridge. ``?agent=<name>`` returns one agent.
    """
    from agent_pack import load_pack, get_agent
    pack = load_pack()
    if agent:
        found = get_agent(agent)
        if not found:
            raise HTTPException(status_code=404, detail=f"No IOFlow agent named '{agent}'")
        return {**{k: v for k, v in pack.items() if k != "agents"}, "agents": [found]}
    return pack


@router.get("/tools", response_model=List[Dict[str, Any]])
async def list_mcp_tools(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """List all available MCP tools"""
    tools = mcp_service.get_available_tools()
    
    if category:
        tools = [t for t in tools if t["category"] == category]
    
    return tools


@router.post("/resources/get", response_model=MCPResourceResponse)
async def get_mcp_resource(
    request: MCPResourceRequest,
    current_user: User = Depends(get_current_user)
):
    """Get an MCP resource by URI"""
    try:
        content = await mcp_service.get_resource(request.uri)
        
        return MCPResourceResponse(
            success=True,
            uri=request.uri,
            content=content
        )
    
    except ValueError as e:
        return MCPResourceResponse(
            success=False,
            uri=request.uri,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting MCP resource {request.uri}: {str(e)}")
        return MCPResourceResponse(
            success=False,
            uri=request.uri,
            error=f"Internal error: {str(e)}"
        )


@router.get("/resources", response_model=List[Dict[str, str]])
async def list_mcp_resources(current_user: User = Depends(get_current_user)):
    """List all available MCP resources"""
    return [
        {
            "uri": "seed-apps://catalog",
            "description": "Complete catalog of seed applications",
            "type": "catalog"
        },
        {
            "uri": "seed-apps://catalog/{app_key}",
            "description": "Details for a specific application",
            "type": "application"
        },
        {
            "uri": "seed-apps://schema",
            "description": "JSON schema for seed applications",
            "type": "schema"
        },
        {
            "uri": "seed-apps://templates/{category}",
            "description": "Template applications for a category",
            "type": "templates"
        },
        {
            "uri": "seed-apps://docs",
            "description": "MCP server documentation",
            "type": "documentation"
        }
    ]


# Health check endpoint
@router.get("/health")
async def mcp_health_check():
    """Check MCP bridge health status"""
    return {
        "status": "healthy",
        "service": "mcp-bridge",
        "tools_count": len(mcp_service._tool_registry),
        "resources_count": len(mcp_service._resource_registry)
    }