"""
Flow Design Tools for IOFlow MCP Server

This module provides comprehensive tools for designing, analyzing, and creating flows
with detailed guidelines and ID lookup capabilities.
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pathlib import Path
import json
import logging
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_

# Import MCP classes - required, no fallbacks
from mcp.types import TextContent

from services.flow_handles import edge_handle_errors

# Tool base class for flow design tools
class Tool:
    """Base class for flow design tools"""
    def __init__(self, auth_handler=None):
        # Subclasses declare their MCP tool name as a CLASS attribute
        # (e.g. `name = "create_or_update_flow"`). Unconditionally assigning
        # the Python class name here SHADOWED every one of them, so the bridge
        # wrappers that dispatch on `tool.name == "<snake_case>"` never matched
        # and answered "Tool not found" — for tools the bridge's own tool LIST
        # advertised. Same guard the other tool base classes already use.
        if not hasattr(self.__class__, 'name') or self.__class__.name is None:
            self.name = self.__class__.__name__
        self.auth_handler = auth_handler

    async def run(self, **kwargs):
        """Override in subclasses"""
        raise NotImplementedError

    # -- who is calling ---------------------------------------------------
    # A flow belongs to the tenant of the user who saved it — the user signed
    # in to IOFlow (directly, through single sign-on, or by an API key bound to
    # them). The tools below read and write ``flows`` directly, so they apply
    # that rule themselves: the caller must be a known user in a known tenant,
    # and only that tenant's flows are listed, changed or deleted. There is no
    # fallback tenant — a flow is never stored under "default".

    def _caller(self) -> Dict[str, Any]:
        """The authenticated caller: ``{id, tenant_id, role}`` (values None
        when the tool runs with no identity)."""
        info = getattr(self.auth_handler, "user_info", None) if self.auth_handler else None
        info = info if isinstance(info, dict) else {}
        tenant = info.get("tenant") if isinstance(info.get("tenant"), dict) else {}
        role = info.get("role") or ""
        role = str(getattr(role, "value", role)).replace("UserRole.", "")
        return {"id": info.get("id") or info.get("user_id"),
                "tenant_id": info.get("tenant_id") or tenant.get("tenant_id"),
                "role": role}

    @staticmethod
    def _identified(caller: Dict[str, Any]) -> bool:
        return bool(caller.get("id")) and bool(caller.get("tenant_id"))

    @staticmethod
    def _unidentified() -> "TextContent":
        return TextContent(
            type="text",
            text=("Error: IOFlow could not tell which user and organization this "
                  "request comes from, so nothing was read or changed. Sign in "
                  "again, or use an API key that belongs to a user.")
        )

    @staticmethod
    def _may_write_flow(flow, caller: Dict[str, Any]) -> bool:
        """The caller's own tenant's flow (an instance admin may change any)."""
        if caller.get("role") == "INSTANCE_ADMIN":
            return True
        return bool(caller.get("tenant_id")) and flow.tenant_id == caller["tenant_id"]

from db.database import get_db_context
from core.config import settings
import re

# Import models - PostgreSQL Only
from db.application_models import (
    Application, ApplicationService, ApplicationEvent,
    ApplicationSubscription, AuthType, TriggerType
)
from db.models import Flow, User, Tenant, FlowStatus

logger = logging.getLogger(__name__)


_FLOW_ID_IN_TEXT = re.compile(r"Flow ID:\s*([0-9a-fA-F-]{36})")


def flow_save_verdict(text: str) -> Dict[str, Any]:
    """Structured verdict for CreateOrUpdateFlowTool's human-readable answer.

    The tool answers with text on every path — "✅ Flow created/updated
    successfully! … Flow ID: <uuid>" or "Error …" / "# Flow Validation Failed" —
    and wrappers used to hand that back as a success. This is the one place
    that decides: success only for the tool's own success message that names a
    flow id; anything else is a failure carrying the text as its error.
    """
    body = (text or "").strip()
    match = _FLOW_ID_IN_TEXT.search(body)
    ok = body.startswith("✅") and match is not None
    verdict: Dict[str, Any] = {"success": ok, "content": text}
    if ok:
        verdict["flow_id"] = match.group(1)
    else:
        verdict["error"] = body or "create_or_update_flow returned no answer"
    return verdict


class FlowValidator:
    """
    Validates flow definitions to ensure they meet IOFlow requirements
    """
    
    @staticmethod
    def validate_complete_flow(flow_json: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        """
        Validate a complete flow including trigger configuration synchronization
        
        Args:
            flow_json: Complete flow JSON with version, flow, and metadata
            
        Returns:
            Tuple of (is_valid, list of errors, list of warnings)
        """
        errors = []
        warnings = []
        
        # Check if it's in import format
        if "version" in flow_json and "flow" in flow_json:
            flow = flow_json["flow"]
            flow_def = flow.get("flow_definition", {})
            trigger_config = flow.get("trigger_config", {})
        else:
            # Direct flow definition
            flow_def = flow_json
            trigger_config = None
            warnings.append("Flow is not in import format - trigger_config may be missing")
        
        # Validate flow definition
        is_valid, def_errors = FlowValidator.validate_flow_definition(flow_def, trigger_config)
        errors.extend(def_errors)
        
        # Special validation for manual triggers - check dual configuration
        if trigger_config and trigger_config.get("type") == "manual":
            flow_manual_vars = trigger_config.get("manual_variables", [])
            
            # Find trigger node
            trigger_node = None
            for node in flow_def.get("nodes", []):
                if node.get("type") == "trigger":
                    trigger_node = node
                    break
            
            if trigger_node:
                node_data = trigger_node.get("data", {})
                node_manual_vars = node_data.get("manualVariables", [])
                
                # Check if both are configured
                if not flow_manual_vars:
                    errors.append("CRITICAL: trigger_config.manual_variables is empty - flow won't accept inputs")
                if not node_manual_vars:
                    errors.append("CRITICAL: trigger node manualVariables is empty - UI won't show input fields")
                
                # Check synchronization
                if flow_manual_vars and node_manual_vars:
                    flow_var_names = {v.get("name") for v in flow_manual_vars}
                    node_var_names = {v.get("name") for v in node_manual_vars}
                    
                    # Check for mismatches
                    only_in_config = flow_var_names - node_var_names
                    only_in_node = node_var_names - flow_var_names
                    
                    if only_in_config:
                        errors.append(f"Variables in trigger_config but not in node: {only_in_config}")
                    if only_in_node:
                        errors.append(f"Variables in node but not in trigger_config: {only_in_node}")
                    
                    # Check outputs mapping
                    outputs = node_data.get("outputs", {})
                    for var_name in flow_var_names:
                        if var_name not in outputs:
                            warnings.append(f"Variable '{var_name}' not mapped in trigger outputs")
        
        return len(errors) == 0, errors, warnings
    
    @staticmethod
    def validate_flow_definition(flow_definition: Dict[str, Any], trigger_config: Optional[Dict] = None) -> tuple[bool, List[str]]:
        """
        Validate a flow definition for structural and logical correctness
        
        Args:
            flow_definition: The flow definition dictionary to validate
            trigger_config: Optional trigger configuration from flow level
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        
        # Basic structure validation
        if not isinstance(flow_definition, dict):
            errors.append("Flow definition must be a dictionary")
            return False, errors
        
        # Check required keys
        if 'nodes' not in flow_definition:
            errors.append("Flow definition must contain 'nodes' key")
        if 'edges' not in flow_definition:
            errors.append("Flow definition must contain 'edges' key")
        
        if errors:
            return False, errors
        
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        
        # Validate nodes
        node_errors = FlowValidator._validate_nodes(nodes)
        errors.extend(node_errors)
        
        # Validate edges
        edge_errors = FlowValidator._validate_edges(edges, nodes)
        errors.extend(edge_errors)
        
        # Validate flow logic
        logic_errors = FlowValidator._validate_flow_logic(nodes, edges)
        errors.extend(logic_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_nodes(nodes: List[Dict]) -> List[str]:
        """Validate node structure and content"""
        errors = []
        node_ids = set()
        trigger_count = 0
        response_count = 0
        
        for i, node in enumerate(nodes):
            # Check node structure
            if not isinstance(node, dict):
                errors.append(f"Node at index {i} must be a dictionary")
                continue
            
            # Check required fields
            if 'id' not in node:
                errors.append(f"Node at index {i} missing 'id' field")
            else:
                node_id = node['id']
                if node_id in node_ids:
                    errors.append(f"Duplicate node ID: {node_id}")
                node_ids.add(node_id)
            
            if 'type' not in node:
                errors.append(f"Node {node.get('id', f'at index {i}')} missing 'type' field")
                continue
            
            node_type = node['type']
            
            # Validate node types
            valid_types = ['trigger', 'action', 'transform', 'condition', 'loop', 'response', 'human_in_loop']
            if node_type not in valid_types:
                errors.append(f"Node {node.get('id', f'at index {i}')} has invalid type: {node_type}. Valid types: {valid_types}")
            
            # Count special nodes
            if node_type == 'trigger':
                trigger_count += 1
            elif node_type == 'response':
                response_count += 1
            
            # Check position
            if 'position' not in node:
                errors.append(f"Node {node.get('id', f'at index {i}')} missing 'position' field")
            elif not isinstance(node.get('position'), dict) or 'x' not in node['position'] or 'y' not in node['position']:
                errors.append(f"Node {node.get('id', f'at index {i}')} has invalid position format")
            
            # Check data field
            if 'data' not in node:
                errors.append(f"Node {node.get('id', f'at index {i}')} missing 'data' field")
            else:
                # Validate node-specific data
                data_errors = FlowValidator._validate_node_data(node)
                errors.extend(data_errors)
        
        # Check trigger requirement
        if trigger_count == 0:
            errors.append("Flow must have exactly one trigger node")
        elif trigger_count > 1:
            errors.append(f"Flow has {trigger_count} trigger nodes, but only one is allowed")
        
        # Check response nodes for synchronous flows
        # (This is a warning, not an error)
        
        return errors
    
    @staticmethod
    def _validate_node_data(node: Dict) -> List[str]:
        """Validate node-specific data fields"""
        errors = []
        node_id = node.get('id', 'unknown')
        node_type = node.get('type')
        data = node.get('data', {})
        
        if node_type == 'trigger':
            # Check both 'type' and 'triggerType' fields
            trigger_type = data.get('type') or data.get('triggerType')
            if not trigger_type:
                errors.append(f"Trigger node {node_id} missing 'type' or 'triggerType' in data")
            else:
                valid_trigger_types = ['manual', 'webhook', 'schedule', 'application_event', 'event', 'api_call']
                if trigger_type not in valid_trigger_types:
                    errors.append(f"Trigger node {node_id} has invalid triggerType: {trigger_type}. Valid types: {valid_trigger_types}")
                
                # Validate trigger-specific fields
                if trigger_type == 'manual':
                    # Manual triggers MUST have manualVariables
                    if 'manualVariables' not in data:
                        errors.append(f"Manual trigger {node_id} missing 'manualVariables' array - required to define input parameters")
                    else:
                        node_manual_vars = data.get('manualVariables', [])
                        for var in node_manual_vars:
                            if not isinstance(var, dict):
                                errors.append(f"Manual variable in trigger {node_id} must be a dictionary")
                            elif 'name' not in var or 'dataType' not in var:
                                errors.append(f"Manual variable in trigger {node_id} missing required fields (name, dataType)")
                            else:
                                # Validate file type arguments
                                data_type = var.get('dataType')
                                if data_type == 'file':
                                    validation_errors = FlowValidator._validate_file_argument(var, node_id)
                                    errors.extend(validation_errors)
                    
                    # Check outputs field for proper mapping
                    if 'outputs' not in data:
                        errors.append(f"Manual trigger {node_id} missing 'outputs' field - required to map inputs to variables")
                
                elif trigger_type == 'schedule':
                    if 'schedule' not in data:
                        errors.append(f"Schedule trigger {node_id} missing 'schedule' field")
                
                elif trigger_type == 'application_event' or trigger_type == 'event':
                    if 'appId' not in data or 'eventId' not in data:
                        errors.append(f"Application event trigger {node_id} missing appId or eventId")
        
        elif node_type == 'action':
            # Required fields for backend
            if 'appId' not in data and 'appName' not in data:
                errors.append(f"Action node {node_id} missing appId or appName")
            if 'serviceId' not in data and 'service' not in data:
                errors.append(f"Action node {node_id} missing serviceId or service")
            
            # Required fields for UI display
            if 'label' not in data:
                errors.append(f"Action node {node_id} missing 'label' field required for UI display")
            if 'appId' in data and 'appName' not in data:
                errors.append(f"Action node {node_id} has appId but missing appName for UI display")
            if 'serviceId' in data and 'serviceDisplayName' not in data and 'serviceName' not in data:
                errors.append(f"Action node {node_id} has serviceId but missing serviceDisplayName or serviceName for UI display")
            
            # Validate parameters using the dedicated method
            param_errors, param_warnings = FlowValidator.validate_action_parameters(node_id, data)
            errors.extend(param_errors)
            # This validator returns errors only; there was no `warnings` list
            # in scope here (NameError on every flow with an action node).
            # Parameter warnings are advisory — log them, never block.
            for warning in param_warnings or []:
                logger.warning(f"Flow validation warning: {warning}")
        
        elif node_type == 'transform':
            if 'script' not in data:
                errors.append(f"Transform node {node_id} missing 'script' field. Scripts must use restrictive Python (no file system, network, or system access)")
            else:
                # Validate Python script syntax
                script = data['script']
                try:
                    compile(script, '<string>', 'exec')
                except SyntaxError as e:
                    errors.append(f"Transform node {node_id} has invalid Python syntax: {str(e)}. Scripts must use restrictive Python (no imports, file I/O, network calls, or system commands)")
        
        elif node_type == 'condition':
            if 'expression' not in data:
                errors.append(f"Condition node {node_id} missing 'expression' field")
        
        elif node_type == 'loop':
            if 'loopType' not in data:
                errors.append(f"Loop node {node_id} missing 'loopType' field")
            else:
                loop_type = data['loopType']
                valid_loop_types = ['forEach', 'for', 'while']
                if loop_type not in valid_loop_types:
                    errors.append(f"Loop node {node_id} has invalid loopType: {loop_type}. Valid types: {valid_loop_types}")
                
                if loop_type == 'forEach':
                    if 'arrayPath' not in data:
                        errors.append(f"ForEach loop {node_id} missing 'arrayPath' field")
                elif loop_type == 'for':
                    if 'count' not in data:
                        errors.append(f"For loop {node_id} missing 'count' field")
                elif loop_type == 'while':
                    if 'condition' not in data:
                        errors.append(f"While loop {node_id} missing 'condition' field")
        
        elif node_type == 'response':
            if 'variable' not in data and 'body' not in data:
                errors.append(f"Response node {node_id} missing 'variable' or 'body' field")
        
        return errors
    
    @staticmethod
    def _validate_edges(edges: List[Dict], nodes: List[Dict]) -> List[str]:
        """Validate edge structure and connections"""
        errors = []
        node_ids = {node['id'] for node in nodes if 'id' in node}
        node_types = {node['id']: node.get('type') for node in nodes
                      if isinstance(node, dict) and 'id' in node}
        edge_ids = set()

        for i, edge in enumerate(edges):
            if not isinstance(edge, dict):
                errors.append(f"Edge at index {i} must be a dictionary")
                continue
            
            # Check required fields
            if 'id' not in edge:
                errors.append(f"Edge at index {i} missing 'id' field")
            else:
                edge_id = edge['id']
                if edge_id in edge_ids:
                    errors.append(f"Duplicate edge ID: {edge_id}")
                edge_ids.add(edge_id)
            
            if 'source' not in edge:
                errors.append(f"Edge {edge.get('id', f'at index {i}')} missing 'source' field")
            elif edge['source'] not in node_ids:
                errors.append(f"Edge {edge.get('id', f'at index {i}')} has invalid source node: {edge['source']}")
            
            if 'target' not in edge:
                errors.append(f"Edge {edge.get('id', f'at index {i}')} missing 'target' field")
            elif edge['target'] not in node_ids:
                errors.append(f"Edge {edge.get('id', f'at index {i}')} has invalid target node: {edge['target']}")
            
            # Handles: optional (the designer uses the node's default), but a
            # handle the node does not have leaves the connection undrawn.
            errors.extend(edge_handle_errors(edge, node_types))

        return errors
    
    @staticmethod
    def _validate_flow_logic(nodes: List[Dict], edges: List[Dict]) -> List[str]:
        """Validate flow logic and connectivity"""
        errors = []
        
        # Build adjacency lists
        outgoing = {}
        incoming = {}
        for node in nodes:
            if 'id' in node:
                outgoing[node['id']] = []
                incoming[node['id']] = []
        
        for edge in edges:
            if 'source' in edge and 'target' in edge:
                source = edge['source']
                target = edge['target']
                if source in outgoing:
                    outgoing[source].append(target)
                if target in incoming:
                    incoming[target].append(source)
        
        # Find trigger nodes
        trigger_nodes = [n for n in nodes if n.get('type') == 'trigger']
        
        # Check trigger has outgoing edges
        for trigger in trigger_nodes:
            trigger_id = trigger.get('id')
            if trigger_id and len(outgoing.get(trigger_id, [])) == 0:
                errors.append(f"Trigger node {trigger_id} has no outgoing connections")
        
        # Check for orphaned nodes (except trigger)
        for node in nodes:
            node_id = node.get('id')
            node_type = node.get('type')
            if node_id and node_type != 'trigger':
                if len(incoming.get(node_id, [])) == 0:
                    errors.append(f"Node {node_id} ({node_type}) is not connected to any incoming edge")
        
        # Check condition nodes have proper branches
        for node in nodes:
            if node.get('type') == 'condition':
                node_id = node.get('id')
                if node_id:
                    # Get edges from this condition
                    condition_edges = [e for e in edges if e.get('source') == node_id]
                    
                    # Check for true/false branches
                    has_true = any(e.get('sourceHandle') == 'true' for e in condition_edges)
                    has_false = any(e.get('sourceHandle') == 'false' for e in condition_edges)
                    
                    if len(condition_edges) > 0 and not (has_true or has_false):
                        # If sourceHandle is not specified, it's okay (legacy support)
                        pass
                    elif has_true and not has_false:
                        errors.append(f"Condition node {node_id} missing false branch")
                    elif has_false and not has_true:
                        errors.append(f"Condition node {node_id} missing true branch")
        
        # Check loop nodes have loop body connection
        for node in nodes:
            if node.get('type') == 'loop':
                node_id = node.get('id')
                if node_id:
                    loop_edges = [e for e in edges if e.get('source') == node_id]
                    if len(loop_edges) == 0:
                        errors.append(f"Loop node {node_id} has no loop body connection")
        
        # Check for cycles (excluding intentional loop cycles)
        cycles = FlowValidator._detect_cycles(nodes, edges)
        if cycles:
            for cycle in cycles:
                errors.append(f"Detected cycle in flow: {' -> '.join(cycle)}")
        
        return errors
    
    @staticmethod
    def _detect_cycles(nodes: List[Dict], edges: List[Dict]) -> List[List[str]]:
        """Detect cycles in the flow graph (excluding loop nodes)"""
        cycles = []
        
        # Build adjacency list excluding loop back-edges
        adj = {}
        for node in nodes:
            if 'id' in node:
                adj[node['id']] = []
        
        for edge in edges:
            if 'source' in edge and 'target' in edge:
                source = edge['source']
                target = edge['target']
                
                if source in adj:
                    adj[source].append(target)
        
        # DFS to detect cycles
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
                    return False
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        # Check all components
        for node_id in adj:
            if node_id not in visited:
                dfs(node_id)
        
        return cycles
    
    @staticmethod
    def _validate_file_argument(var: Dict[str, Any], node_id: str) -> List[str]:
        """
        Validate file type argument configuration
        
        Args:
            var: File variable configuration dictionary
            node_id: Node ID for error reporting
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check UI control for file type
        ui_control = var.get('uiControl')
        if ui_control not in ['file', 'file-multiple']:
            errors.append(f"File argument '{var.get('name', 'unknown')}' in node {node_id} should use 'file' or 'file-multiple' uiControl, found: {ui_control}")
        
        # Validate file validation options
        validation = var.get('validation', {})
        if validation:
            # Check accepted file types
            if 'acceptedFileTypes' in validation:
                accepted_types = validation['acceptedFileTypes']
                if not isinstance(accepted_types, str):
                    errors.append(f"File argument '{var.get('name', 'unknown')}' in node {node_id} acceptedFileTypes must be a string")
                elif not accepted_types.strip():
                    errors.append(f"File argument '{var.get('name', 'unknown')}' in node {node_id} acceptedFileTypes cannot be empty")
                else:
                    # Validate file extension format
                    types = [t.strip() for t in accepted_types.split(',')]
                    for file_type in types:
                        if not file_type.startswith('.'):
                            errors.append(f"File argument '{var.get('name', 'unknown')}' in node {node_id} file type '{file_type}' should start with '.' (e.g., '.pdf', '.txt')")
            
            # Check max file size
            if 'maxFileSize' in validation:
                max_size = validation['maxFileSize']
                if not isinstance(max_size, (int, float)) or max_size <= 0:
                    errors.append(f"File argument '{var.get('name', 'unknown')}' in node {node_id} maxFileSize must be a positive number")
                elif max_size > 100 * 1024 * 1024:  # 100MB limit
                    errors.append(f"File argument '{var.get('name', 'unknown')}' in node {node_id} maxFileSize exceeds 100MB limit")
            
            # Check max files for multiple uploads
            if ui_control == 'file-multiple' and 'maxFiles' in validation:
                max_files = validation['maxFiles']
                if not isinstance(max_files, int) or max_files <= 0:
                    errors.append(f"File argument '{var.get('name', 'unknown')}' in node {node_id} maxFiles must be a positive integer")
                elif max_files > 20:  # Reasonable limit
                    errors.append(f"File argument '{var.get('name', 'unknown')}' in node {node_id} maxFiles should not exceed 20")
        
        return errors
    
    @staticmethod
    def validate_variable_references(flow_definition: Dict[str, Any]) -> List[str]:
        """
        Validate variable references in the flow
        
        Args:
            flow_definition: The flow definition to validate
            
        Returns:
            List of warnings about variable references
        """
        warnings = []
        nodes = flow_definition.get('nodes', [])
        
        # Track available variables
        available_vars = {
            'input': 'Trigger/input variables',
            'trigger': 'Trigger variables',
            'flow': 'Flow metadata',
            'global': 'Global variables'
        }
        
        # Variable reference pattern
        var_pattern = re.compile(r'\{\{([^}]+)\}\}')
        
        # Process nodes in order (simplified - actual execution order may vary)
        for node in nodes:
            node_id = node.get('id', 'unknown')
            node_type = node.get('type')
            data = node.get('data', {})
            
            # Add node output to available variables
            if node_type in ['action', 'transform']:
                available_vars[f'node_outputs.{node_id}'] = f"Output from {node_type} node {node_id}"
                available_vars[f'{node_id}'] = f"Output from {node_type} node {node_id} (shorthand)"
            
            # Check variable references in node data
            if node_type == 'action' and 'parameterMapping' in data:
                for param, value in data['parameterMapping'].items():
                    if isinstance(value, str):
                        matches = var_pattern.findall(value)
                        for match in matches:
                            var_path = match.strip().split('.')[0]
                            if var_path not in available_vars and not var_path.startswith('node_outputs'):
                                warnings.append(f"Action node {node_id}: Possible undefined variable reference '{{{{{match}}}}}'")            
            elif node_type == 'condition' and 'expression' in data:
                # Check JavaScript expression for variable references
                expression = data['expression']
                # Simple check for common patterns
                for var_prefix in ['node_outputs', 'input', 'trigger', 'loop']:
                    if var_prefix in expression:
                        # Check if it's accessing a valid node
                        if var_prefix == 'node_outputs':
                            # Extract node references
                            node_refs = re.findall(r'node_outputs\.(\w+)', expression)
                            for ref in node_refs:
                                if ref not in [n.get('id') for n in nodes]:
                                    warnings.append(f"Condition node {node_id}: Reference to unknown node 'node_outputs.{ref}'")
            
            elif node_type == 'loop' and 'arrayPath' in data:
                value = data['arrayPath']
                if isinstance(value, str):
                    matches = var_pattern.findall(value)
                    for match in matches:
                        var_path = match.strip()
                        # Check if it's a valid reference
                        if not any(var_path.startswith(prefix) for prefix in available_vars.keys()):
                            warnings.append(f"Loop node {node_id}: Possible undefined array reference '{{{{{match}}}}}'")
            
            elif node_type == 'response' and 'variable' in data:
                value = data['variable']
                if isinstance(value, str):
                    matches = var_pattern.findall(value)
                    for match in matches:
                        var_path = match.strip()
                        if not any(var_path.startswith(prefix) for prefix in available_vars.keys()):
                            warnings.append(f"Response node {node_id}: Possible undefined variable reference '{{{{{match}}}}}'")
        
        return warnings
    
    @staticmethod
    def validate_export_format(export_flow: Dict[str, Any]) -> tuple[bool, List[str], List[str]]:
        """
        Validate a flow in export/import format
        
        Args:
            export_flow: Flow in export format (with version, flow, metadata)
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check top-level structure
        if not isinstance(export_flow, dict):
            errors.append("Export flow must be a dictionary")
            return False, errors, warnings
            
        # Check required top-level fields
        if "version" not in export_flow:
            errors.append("Missing 'version' field in export format")
        if "flow" not in export_flow:
            errors.append("Missing 'flow' field in export format")
            return False, errors, warnings
            
        flow = export_flow.get("flow", {})
        
        # Check flow-level fields
        if "flow_name" not in flow:
            warnings.append("Missing 'flow_name' in flow")
        if "trigger_config" not in flow:
            errors.append("Missing 'trigger_config' in flow")
        if "flow_definition" not in flow:
            errors.append("Missing 'flow_definition' in flow")
            return False, errors, warnings
            
        # Validate trigger_config
        trigger_config = flow.get("trigger_config", {})
        if trigger_config.get("type") == "manual":
            if "manual_variables" not in trigger_config:
                errors.append("Manual trigger requires 'manual_variables' in trigger_config")
            elif not trigger_config["manual_variables"]:
                warnings.append("trigger_config.manual_variables is empty")
                
        # Validate flow_definition
        flow_def = flow.get("flow_definition", {})
        if "nodes" not in flow_def:
            errors.append("Missing 'nodes' in flow_definition")
        if "edges" not in flow_def:
            errors.append("Missing 'edges' in flow_definition")
            
        # Validate nodes in export format
        nodes = flow_def.get("nodes", [])
        trigger_found = False
        response_found = False
        
        for node in nodes:
            node_id = node.get("id", "unknown")
            node_type = node.get("type")
            data = node.get("data", {})
            
            if node_type == "trigger":
                trigger_found = True
                if data.get("triggerType") == "manual":
                    if "manualVariables" not in data:
                        errors.append(f"Trigger node {node_id}: Missing 'manualVariables' in data")
                    elif not data["manualVariables"]:
                        warnings.append(f"Trigger node {node_id}: manualVariables is empty")
                        
                    # Check synchronization with trigger_config
                    config_vars = {v.get("name") for v in trigger_config.get("manual_variables", [])}
                    node_vars = {v.get("name") for v in data.get("manualVariables", [])}
                    
                    if config_vars != node_vars:
                        errors.append(f"Trigger variables mismatch: config has {config_vars}, node has {node_vars}")
                        
            elif node_type == "action":
                # Check action node requirements for export format
                if "width" not in data or "height" not in data:
                    warnings.append(f"Action node {node_id}: Missing width/height for UI rendering")
                    
                # Validate parameters using the dedicated method
                param_errors, param_warnings = FlowValidator.validate_action_parameters(node_id, data)
                errors.extend(param_errors)
                warnings.extend(param_warnings)
                    
            elif node_type == "response":
                response_found = True
                # Check for correct field in export format
                if "variable" not in data and "responseBody" not in data:
                    errors.append(f"Response node {node_id}: Must have 'variable' field in export format")
                if "responseBody" in data:
                    warnings.append(f"Response node {node_id}: Using 'responseBody' - should use 'variable' for export format")
                    
        if not trigger_found:
            errors.append("No trigger node found in flow")
        if not response_found:
            warnings.append("No response node found - flow may not return output")
            
        # Validate edges in export format
        edges = flow_def.get("edges", [])
        for edge in edges:
            edge_id = edge.get("id", "unknown")
            
            # Check that handles are null or missing for export format
            if edge.get("sourceHandle") not in [None, ""] or edge.get("targetHandle") not in [None, ""]:
                if edge.get("sourceHandle") or edge.get("targetHandle"):
                    warnings.append(f"Edge {edge_id}: Should use null handles in export format")
                    
        # Check metadata
        metadata = export_flow.get("metadata", {})
        if "required_applications" not in metadata:
            warnings.append("Missing 'required_applications' in metadata")
            
        return len(errors) == 0, errors, warnings
    
    @staticmethod
    def validate_action_parameters(
        node_id: str,
        node_data: Dict[str, Any],
        service_schema: Optional[Dict[str, Any]] = None
    ) -> tuple[List[str], List[str]]:
        """
        Validate action node parameters against service schema
        
        Args:
            node_id: The node identifier
            node_data: The action node data
            service_schema: Optional service parameter schema
            
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        # Get the parameterMapping from the node
        parameter_mapping = node_data.get("parameterMapping", {})
        
        # Extract actual parameters from nested structure
        actual_params = {}
        for key, value in parameter_mapping.items():
            # Handle nested structure with source and value
            if isinstance(value, dict) and 'source' in value and 'value' in value:
                # This is the new format with source type
                actual_params[key] = value.get('value')
            elif isinstance(value, dict) and 'value' in value:
                # Old format with just value key
                actual_params[key] = value.get('value')
            else:
                # Direct value
                actual_params[key] = value
        
        if not actual_params:
            warnings.append(f"Action node {node_id}: No parameters defined")
            return errors, warnings
            
        # If we have a service schema, validate against it
        if service_schema:
            schema_properties = service_schema.get("properties", {})
            required_params = service_schema.get("required", [])
            
            # Check for missing required parameters
            for required_param in required_params:
                if required_param not in actual_params:
                    errors.append(f"Action node {node_id}: Missing required parameter '{required_param}'")
                elif actual_params[required_param] in [None, "", {}]:
                    warnings.append(f"Action node {node_id}: Required parameter '{required_param}' appears to be empty")
            
            # Check for unknown parameters
            for param_name in actual_params:
                if param_name not in schema_properties:
                    warnings.append(f"Action node {node_id}: Unknown parameter '{param_name}' not in service schema")
                    
            # Validate parameter types if specified
            for param_name, param_value in actual_params.items():
                if param_name in schema_properties:
                    param_schema = schema_properties[param_name]
                    param_type = param_schema.get("type")
                    
                    # Check for variable references (both template {{...}} and direct references)
                    if isinstance(param_value, str):
                        # Check for template syntax
                        if "{{" in param_value:
                            # This is a template variable reference, skip type checking
                            continue
                        
                        # Check for direct variable references (node_outputs, input, variables, etc.)
                        # These are valid dynamic references that will be resolved at runtime
                        dynamic_prefixes = ['node_outputs.', 'input.', 'variables.', 'loop.', 'trigger.', 'global_vars.']
                        if any(param_value.startswith(prefix) for prefix in dynamic_prefixes):
                            # This is a dynamic reference, skip type checking
                            continue
                        
                        # Also check if entire value might be a reference without dot notation
                        if param_value in ['node_outputs', 'input', 'variables', 'loop', 'trigger', 'global_vars']:
                            # This might be referencing the entire object, skip type checking
                            continue
                        
                    # Basic type validation
                    if param_type == "string" and not isinstance(param_value, str):
                        warnings.append(f"Action node {node_id}: Parameter '{param_name}' should be string")
                    elif param_type == "number" and not isinstance(param_value, (int, float)):
                        warnings.append(f"Action node {node_id}: Parameter '{param_name}' should be number")
                    elif param_type == "boolean" and not isinstance(param_value, bool):
                        warnings.append(f"Action node {node_id}: Parameter '{param_name}' should be boolean")
                    elif param_type == "array" and not isinstance(param_value, list):
                        warnings.append(f"Action node {node_id}: Parameter '{param_name}' should be array")
                    elif param_type == "object" and not isinstance(param_value, dict):
                        warnings.append(f"Action node {node_id}: Parameter '{param_name}' should be object")
        else:
            # No schema available, just do basic checks
            if not parameter_mapping:
                warnings.append(f"Action node {node_id}: No parameterMapping defined")
            
        return errors, warnings
    
    @staticmethod
    def detect_flow_format(flow_data: Dict[str, Any]) -> str:
        """
        Detect whether a flow is in export format or simple/view-source format
        
        Args:
            flow_data: The flow data to analyze
            
        Returns:
            "export" or "simple" or "unknown"
        """
        if not isinstance(flow_data, dict):
            return "unknown"
            
        # Export format has version and flow wrapper
        if "version" in flow_data and "flow" in flow_data:
            if isinstance(flow_data.get("flow"), dict):
                if "flow_definition" in flow_data["flow"]:
                    return "export"
                    
        # Simple format has nodes/edges at top level
        if "nodes" in flow_data and "edges" in flow_data:
            # But not if it also has export format markers
            if "version" not in flow_data and "flow" not in flow_data:
                return "simple"
                
        return "unknown"


# FlowDesignGuidelines class removed - consolidated into API endpoint at /api/v1/flow-design/guidelines
# Access via MCP bridge tool get_flow_design_guideline for remote access
class GetApplicationDetails(Tool):
    """
    Fetches detailed information about applications, including their IDs, services, and events.
    """
    
    name = "get_application_details"
    description = """Get detailed information about applications in IOFlow.
    
    Args:
        app_name (str, optional): Name of specific application to get details for
        include_services (bool): Include service details (default: True)
        include_events (bool): Include event details (default: True)
        only_connected (bool): Only show connected applications (default: False)
    
    Returns:
        Detailed application information including IDs, services, and events
    """
    
    async def run(
        self, 
        app_name: Optional[str] = None,
        include_services: bool = True,
        include_events: bool = True,
        only_connected: bool = False
    ) -> str:
        """Run the tool"""
        logger.info(f"Fetching application details - app_name: {app_name}, only_connected: {only_connected}")
        
        try:
            with get_db_context() as db:
                # Build query
                query = db.query(Application)
                
                if app_name:
                    query = query.filter(Application.name.ilike(f"%{app_name}%"))
                
                # Get applications
                applications = query.all()
                
                if not applications:
                    return f"No applications found{' matching ' + app_name if app_name else ''}"
                
                result = []
                for app in applications:
                    # Check if connected (has active subscriptions)
                    if only_connected:
                        active_subs = db.query(ApplicationSubscription).filter(
                            ApplicationSubscription.app_id == app.id,
                            ApplicationSubscription.status == 'active'
                        ).count()
                        
                        if active_subs == 0:
                            continue
                    
                    app_info = {
                        "id": str(app.id),
                        "name": app.name,
                        "display_name": app.display_name,
                        "description": app.description,
                        "type": app.type,
                        "auth_type": app.auth_type,
                        "category": app.category,
                        "base_url": app.base_url
                    }
                    
                    # Include services
                    if include_services:
                        services = db.query(ApplicationService).filter(
                            ApplicationService.app_id == app.id
                        ).all()
                        
                        app_info["services"] = [
                            {
                                "id": str(service.id),
                                "name": service.name,
                                "display_name": service.display_name,
                                "description": service.description,
                                "type": service.type,
                                "endpoint": service.endpoint,
                                "method": service.method,
                                "parameters": service.parameters
                            }
                            for service in services
                        ]
                    
                    # Include events
                    if include_events:
                        events = db.query(ApplicationEvent).filter(
                            ApplicationEvent.app_id == app.id
                        ).all()
                        
                        app_info["events"] = [
                            {
                                "id": str(event.id),
                                "name": event.name,
                                "display_name": event.display_name,
                                "description": event.description,
                                "event_type": event.event_type,
                                "sample_payload": event.sample_payload
                            }
                            for event in events
                        ]
                    
                    result.append(app_info)
                
                if not result:
                    return "No connected applications found" if only_connected else "No applications found"
                
                # Format output
                output = f"# Application Details\n\n"
                output += f"Found {len(result)} application(s)\n\n"
                
                for app in result:
                    output += f"## {app['name']}\n"
                    output += f"- **ID**: `{app['id']}`\n"
                    output += f"- **Display Name**: {app['display_name']}\n"
                    output += f"- **Type**: {app['type']}\n"
                    output += f"- **Auth Type**: {app['auth_type']}\n"
                    output += f"- **Category**: {app['category']}\n"
                    if app.get('base_url'):
                        output += f"- **Base URL**: {app['base_url']}\n"
                    output += f"- **Description**: {app['description']}\n"
                    
                    if include_services and app.get('services'):
                        output += f"\n### Services ({len(app['services'])})\n"
                        for service in app['services']:
                            output += f"\n#### {service['name']}\n"
                            output += f"- **ID**: `{service['id']}`\n"
                            output += f"- **Display Name**: {service['display_name']}\n"
                            output += f"- **Type**: {service['type']}\n"
                            output += f"- **Method**: {service['method']}\n"
                            output += f"- **Endpoint**: `{service['endpoint']}`\n"
                            if service.get('description'):
                                output += f"- **Description**: {service['description']}\n"
                            if service.get('parameters'):
                                output += f"- **Parameters**: {len(service['parameters'])} parameter(s)\n"
                    
                    if include_events and app.get('events'):
                        output += f"\n### Events ({len(app['events'])})\n"
                        for event in app['events']:
                            output += f"\n#### {event['name']}\n"
                            output += f"- **ID**: `{event['id']}`\n"
                            output += f"- **Display Name**: {event['display_name']}\n"
                            output += f"- **Event Type**: {event['event_type']}\n"
                            if event.get('description'):
                                output += f"- **Description**: {event['description']}\n"
                    
                    output += "\n---\n\n"
                
                return output
                
        except Exception as e:
            logger.error(f"Error fetching application details: {str(e)}")
            return f"Error fetching application details: {str(e)}"


class CreateFlowJSON(Tool):
    """
    Creates a complete flow JSON structure with proper IDs and configurations.
    """
    
    name = "create_flow_json"
    description = """Create a complete flow JSON structure for IOFlow.
    
    Args:
        flow_name (str): Name of the flow
        description (str): Flow description
        trigger_type (str): Type of trigger (manual, webhook, schedule, application_event)
        trigger_config (dict): Trigger configuration
        nodes_config (list): List of node configurations
        
    Returns:
        Complete flow JSON ready for import
    """
    
    async def run(
        self,
        flow_name: str,
        description: str,
        trigger_type: str,
        trigger_config: dict,
        nodes_config: list
    ) -> str:
        """Run the tool"""
        logger.info(f"Creating flow JSON for: {flow_name}")
        
        try:
            # Generate flow structure
            flow = {
                "name": flow_name,
                "description": description,
                "nodes": [],
                "edges": []
            }
            
            # Create trigger node
            trigger_node = {
                "id": "1",
                "type": "trigger",
                "position": {"x": 250, "y": 50},
                "width": 200,
                "height": 80,
                "data": {
                    "label": "Trigger",
                    "triggerType": trigger_type,
                    **trigger_config
                }
            }
            flow["nodes"].append(trigger_node)
            
            # Process nodes and create edges
            prev_node_id = "1"
            node_counter = 2
            
            for node_config in nodes_config:
                node_id = str(node_counter)
                node_type = node_config.get("type", "action")
                
                # Calculate position
                x = 250 + (node_counter - 1) * 200
                y = 50
                
                node = {
                    "id": node_id,
                    "type": node_type,
                    "position": {"x": x, "y": y},
                    "width": 200,
                    "height": 80,
                    "data": node_config.get("data", {})
                }
                
                # Handle special node types
                if node_type == "loop":
                    node["data"]["loopType"] = node_config.get("loopType", "forEach")
                    node["data"]["iteratorName"] = node_config.get("iteratorName", "item")
                
                flow["nodes"].append(node)
                
                # Create edge from previous node
                edge = {
                    "id": f"e{len(flow['edges']) + 1}",
                    "source": prev_node_id,
                    "target": node_id,
                    "markerEnd": {"type": "ArrowClosed"}
                }
                
                # Handle loop edges
                if prev_node_id.endswith("_loop"):
                    edge["sourceHandle"] = "loop-body"
                
                flow["edges"].append(edge)
                prev_node_id = node_id
                
                node_counter += 1
            
            # Return formatted JSON
            return json.dumps(flow, indent=2)
            
        except Exception as e:
            logger.error(f"Error creating flow JSON: {str(e)}")
            return f"Error creating flow JSON: {str(e)}"


class AnalyzeFlowRequirements(Tool):
    """
    Analyzes requirements for a specific flow use case and suggests the best approach.
    """
    
    name = "analyze_flow_requirements"
    description = """Analyze requirements for a specific flow use case.
    
    Args:
        use_case (str): Description of what the flow should accomplish
        source_app (str, optional): Source application name
        target_app (str, optional): Target application name
        data_volume (str, optional): Expected data volume (low, medium, high)
        frequency (str, optional): How often the flow should run
        
    Returns:
        Detailed analysis with recommendations for flow design
    """
    
    async def run(
        self,
        use_case: str,
        source_app: Optional[str] = None,
        target_app: Optional[str] = None,
        data_volume: str = "medium",
        frequency: Optional[str] = None
    ) -> str:
        """Run the tool"""
        logger.info(f"Analyzing flow requirements for: {use_case}")
        
        analysis = f"# Flow Requirements Analysis\n\n"
        analysis += f"**Use Case**: {use_case}\n\n"
        
        # Determine trigger type
        trigger_recommendation = self._recommend_trigger(use_case, frequency)
        analysis += f"## Recommended Trigger\n{trigger_recommendation}\n\n"
        
        # Check applications
        if source_app or target_app:
            with get_db_context() as db:
                apps_analysis = "## Application Analysis\n\n"
                
                for app_name in [source_app, target_app]:
                    if app_name:
                        app = db.query(Application).filter(
                            Application.name.ilike(f"%{app_name}%")
                        ).first()
                        
                        if app:
                            apps_analysis += f"### {app.name}\n"
                            apps_analysis += f"- **Auth Type**: {app.auth_type}\n"
                            apps_analysis += f"- **Available Services**: {db.query(ApplicationService).filter(ApplicationService.app_id == app.id).count()}\n"
                            apps_analysis += f"- **Available Events**: {db.query(ApplicationEvent).filter(ApplicationEvent.app_id == app.id).count()}\n\n"
                        else:
                            apps_analysis += f"### {app_name}\n"
                            apps_analysis += f"- ⚠️ Application not found in system\n\n"
                
                analysis += apps_analysis
        
        # Performance recommendations
        analysis += f"## Performance Recommendations\n\n"
        if data_volume == "high":
            analysis += "- Use batch processing with loops\n"
            analysis += "- Implement pagination for large datasets\n"
            analysis += "- Consider parallel processing where possible\n"
            analysis += "- Add progress tracking and error recovery\n"
        elif data_volume == "medium":
            analysis += "- Process data in reasonable chunks\n"
            analysis += "- Implement basic error handling\n"
            analysis += "- Consider caching for repeated operations\n"
        else:
            analysis += "- Simple sequential processing should suffice\n"
            analysis += "- Basic error handling recommended\n"
        
        # Suggest flow pattern
        pattern = self._suggest_pattern(use_case)
        analysis += f"\n## Suggested Flow Pattern\n{pattern}\n"
        
        # Best practices for use case
        analysis += f"\n## Best Practices for This Use Case\n"
        analysis += self._get_best_practices(use_case)
        
        return analysis
    
    def _recommend_trigger(self, use_case: str, frequency: Optional[str]) -> str:
        """Recommend trigger type based on use case"""
        use_case_lower = use_case.lower()
        
        if frequency:
            if any(word in frequency.lower() for word in ["daily", "hourly", "weekly", "monthly"]):
                return "**Schedule Trigger** - Use cron expression for regular execution"
        
        if any(word in use_case_lower for word in ["webhook", "notification", "real-time", "instant"]):
            return "**Webhook Trigger** - For real-time event processing"
        
        if any(word in use_case_lower for word in ["sync", "update", "refresh", "import", "export"]):
            return "**Schedule Trigger** - For periodic synchronization"
        
        if any(word in use_case_lower for word in ["manual", "on-demand", "ad-hoc"]):
            return "**Manual Trigger** - For user-initiated processes"
        
        return "**Manual Trigger** - Recommended for testing and on-demand execution"
    
    def _suggest_pattern(self, use_case: str) -> str:
        """Suggest flow pattern based on use case"""
        use_case_lower = use_case.lower()
        
        if "sync" in use_case_lower:
            return """
```
[Trigger] → [Fetch Source Data] → [Transform/Map Fields] → 
[Loop Through Records] → [Check Exists in Target] → 
[Update/Create in Target] → [Log Results] → [Send Summary]
```
"""
        
        if "process" in use_case_lower and "file" in use_case_lower:
            return """
```
[File Trigger] → [Validate File] → [Parse Content] → 
[Transform Data] → [Validate Records] → [Process Batch] → 
[Generate Report] → [Send Notification]
```
"""
        
        if "verify" in use_case_lower or "validate" in use_case_lower:
            return """
```
[Trigger] → [Get Input Data] → [Loop Through Items] → 
[Verify/Validate Item] → [Collect Results] → 
[Update Source] → [Generate Summary] → [Return Response]
```
"""
        
        return """
```
[Trigger] → [Get/Prepare Data] → [Process/Transform] → 
[Perform Action] → [Handle Response] → [Return Result]
```
"""
    
    def _get_best_practices(self, use_case: str) -> str:
        """Get best practices for specific use case"""
        practices = []
        use_case_lower = use_case.lower()
        
        if any(word in use_case_lower for word in ["batch", "bulk", "multiple"]):
            practices.append("- Process in batches to avoid timeouts")
            practices.append("- Implement progress tracking")
            practices.append("- Add retry logic for failed items")
        
        if any(word in use_case_lower for word in ["api", "external", "third-party"]):
            practices.append("- Handle rate limiting appropriately")
            practices.append("- Implement exponential backoff for retries")
            practices.append("- Cache responses when possible")
        
        if any(word in use_case_lower for word in ["verify", "validate", "check"]):
            practices.append("- Validate input data format first")
            practices.append("- Handle invalid data gracefully")
            practices.append("- Provide detailed error messages")
        
        if any(word in use_case_lower for word in ["sync", "update", "refresh"]):
            practices.append("- Track last sync timestamp")
            practices.append("- Handle duplicates appropriately")
            practices.append("- Log all changes for audit")
        
        # Always include these
        practices.extend([
            "- Test with small datasets first",
            "- Add comprehensive error handling",
            "- Monitor execution times",
            "- Document expected inputs/outputs"
        ])
        
        return "\n".join(practices)


class CreateOrUpdateFlow(Tool):
    """
    Create a new flow or update an existing flow in IOFlow
    
    This tool allows creating new flows or updating existing flows
    by providing the complete flow definition including nodes and edges.
    """
    
    name = "create_or_update_flow"
    description = "Create a new flow or update an existing flow with complete definition"
    
    def __init__(self, auth_handler=None):
        super().__init__(auth_handler)

    async def run(
        self,
        flow_name: str,
        flow_definition: Dict[str, Any],
        description: Optional[str] = None,
        flow_id: Optional[str] = None,
        is_update: bool = False,
        activate: bool = False,
        is_synchronous: bool = False,
        sync_timeout: int = 30,
        skip_validation: bool = False
    ) -> TextContent:
        """
        Create or update a flow in IOFlow
        
        Args:
            flow_name: Name of the flow
            flow_definition: Complete flow definition with nodes and edges
            description: Optional description of the flow
            flow_id: ID of existing flow (required for updates)
            is_update: If True, update existing flow; if False, create new
            activate: If True, activate the flow after creation/update
            is_synchronous: If True, flow will run synchronously
            sync_timeout: Timeout in seconds for synchronous flows
            skip_validation: If True, skip flow validation (not recommended)
        
        Returns:
            Success message with flow ID or error details
        """
        try:
            # Whose flow this is comes first: nothing is checked or saved for a
            # caller who cannot be placed in a tenant.
            caller = self._caller()
            if not self._identified(caller):
                return self._unidentified()

            # Perform comprehensive flow validation unless explicitly skipped
            if not skip_validation:
                is_valid, errors = FlowValidator.validate_flow_definition(flow_definition)
                
                if not is_valid:
                    error_message = "# Flow Validation Failed\n\n"
                    error_message += "**Important:** Transform nodes must use restrictive Python code only. This means:\n"
                    error_message += "- No imports or external libraries\n"
                    error_message += "- No file system access (open, read, write)\n"
                    error_message += "- No network calls or system commands\n"
                    error_message += "- Only data manipulation using standard Python syntax\n\n"
                    error_message += "The flow definition contains the following errors:\n\n"
                    for i, error in enumerate(errors, 1):
                        error_message += f"{i}. {error}\n"
                    error_message += "\n**Please fix these errors before creating/updating the flow.**"
                    
                    return TextContent(
                        type="text",
                        text=error_message
                    )
                
                # Check for warnings about variable references
                warnings = FlowValidator.validate_variable_references(flow_definition)
                if warnings:
                    logger.warning(f"Flow '{flow_name}' has variable reference warnings: {warnings}")
            
            # Basic structure validation (kept for backward compatibility)
            if not isinstance(flow_definition, dict):
                return TextContent(
                    type="text",
                    text="Error: flow_definition must be a dictionary with 'nodes' and 'edges' keys"
                )
            
            if 'nodes' not in flow_definition or 'edges' not in flow_definition:
                return TextContent(
                    type="text",
                    text="Error: flow_definition must contain 'nodes' and 'edges' keys"
                )
            
            # Extract trigger configuration from nodes
            trigger_node = None
            for node in flow_definition.get('nodes', []):
                if node.get('type') == 'trigger':
                    trigger_node = node
                    break
            
            if not trigger_node:
                return TextContent(
                    type="text",
                    text="Error: No trigger node found in flow definition"
                )
            
            # Build trigger config from trigger node
            trigger_data = trigger_node.get('data', {})
            # Normalize trigger type - convert 'application_event' to 'event' for consistency
            trigger_type = trigger_data.get('triggerType', 'manual')
            if trigger_type == 'application_event':
                trigger_type = 'event'
            trigger_config = {
                'type': trigger_type
            }
            
            # Add trigger-specific configuration
            if trigger_config['type'] == 'manual':
                trigger_config['manual_variables'] = trigger_data.get('manualVariables', [])
            elif trigger_config['type'] == 'application_event' or trigger_config['type'] == 'event':
                trigger_config['app_id'] = trigger_data.get('appId')
                trigger_config['event_name'] = trigger_data.get('eventName')
            elif trigger_config['type'] == 'schedule':
                trigger_config['schedule'] = trigger_data.get('schedule', {})
            elif trigger_config['type'] == 'webhook':
                trigger_config['webhook_path'] = trigger_data.get('webhookPath')

            with get_db_context() as db:
                # Inherit synchronous mode from application event if not explicitly set
                final_is_synchronous = is_synchronous
                if ((trigger_config.get('type') == 'application_event' or trigger_config.get('type') == 'event') and 
                    trigger_config.get('app_id') and trigger_config.get('event_name') and 
                    not is_synchronous):  # Only inherit if not explicitly set to True
                    
                    try:
                        # Look up the application event to get its sync_mode
                        app_event = db.query(ApplicationEvent).filter(
                            ApplicationEvent.app_id == trigger_config.get('app_id'),
                            ApplicationEvent.event_name == trigger_config.get('event_name')
                        ).first()
                        
                        if app_event and app_event.sync_mode and app_event.sync_mode != 'optional':
                            # Inherit synchronous mode from the application event (only if not optional)
                            final_is_synchronous = app_event.sync_mode == 'synchronous'
                            logger.info(f"MCP Flow inheriting sync_mode '{app_event.sync_mode}' from application event '{app_event.event_name}' - setting is_synchronous to {final_is_synchronous}")
                    except Exception as e:
                        logger.warning(f"Could not lookup application event for sync mode inheritance: {e}")
                        # Continue with the original is_synchronous value
                if is_update:
                    # Update existing flow
                    if not flow_id:
                        return TextContent(
                            type="text",
                            text="Error: flow_id is required for updating a flow"
                        )
                    
                    # Find existing flow — the caller's own. Tenants can share
                    # a schema, so the id alone would let one tenant's agent
                    # overwrite another's flow.
                    flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
                    if flow is not None and not self._may_write_flow(flow, caller):
                        flow = None

                    if not flow:
                        return TextContent(
                            type="text",
                            text=f"Error: Flow with ID {flow_id} not found"
                        )
                    
                    # Update flow fields
                    flow.flow_name = flow_name
                    if description:
                        flow.description = description
                    flow.flow_definition = flow_definition
                    flow.trigger_config = trigger_config
                    flow.is_synchronous = final_is_synchronous
                    flow.sync_timeout = sync_timeout
                    flow.updated_at = datetime.utcnow()
                    
                    if activate:
                        flow.status = FlowStatus.ACTIVE
                    
                    db.commit()
                    
                    return TextContent(
                        type="text",
                        text=f"""✅ Flow updated successfully!

**Flow Details:**
- Flow ID: {flow.flow_id}
- Flow Name: {flow.flow_name}
- Status: {flow.status}
- Nodes: {len(flow_definition.get('nodes', []))}
- Edges: {len(flow_definition.get('edges', []))}
- Trigger Type: {trigger_config['type']}
- Synchronous: {final_is_synchronous}

The flow has been updated and is ready to use."""
                    )
                    
                else:
                    # Create new flow
                    # Check if flow with same name exists
                    existing_flow = db.query(Flow).filter(
                        Flow.flow_name == flow_name,
                        Flow.tenant_id == caller["tenant_id"]
                    ).first()
                    
                    if existing_flow:
                        return TextContent(
                            type="text",
                            text=f"Error: A flow with name '{flow_name}' already exists. Use a different name or update the existing flow."
                        )
                    
                    # Create new flow
                    from uuid import uuid4

                    created_by_user = caller["id"]
                    tenant_id = caller["tenant_id"]
                    logger.info(f"Creating flow for user {created_by_user} in tenant {tenant_id} "
                                f"(auth_type: {getattr(self.auth_handler, 'auth_type', 'unknown')})")

                    new_flow = Flow(
                        flow_id=str(uuid4()),
                        flow_name=flow_name,
                        description=description or f"Flow created via MCP: {flow_name}",
                        trigger_config=trigger_config,
                        flow_definition=flow_definition,
                        status=FlowStatus.ACTIVE if activate else FlowStatus.INACTIVE,
                        is_synchronous=final_is_synchronous,
                        sync_timeout=sync_timeout,
                        created_by=created_by_user,
                        tenant_id=tenant_id
                    )
                    
                    db.add(new_flow)
                    db.commit()
                    
                    return TextContent(
                        type="text",
                        text=f"""✅ Flow created successfully!

**Flow Details:**
- Flow ID: {new_flow.flow_id}
- Flow Name: {new_flow.flow_name}
- Status: {new_flow.status}
- Nodes: {len(flow_definition.get('nodes', []))}
- Edges: {len(flow_definition.get('edges', []))}
- Trigger Type: {trigger_config['type']}
- Synchronous: {final_is_synchronous}

The flow has been created and is ready to use. {'It has been activated and will respond to triggers.' if activate else 'Activate it when ready to start processing.'}"""
                    )
                    
        except Exception as e:
            logger.error(f"Error creating/updating flow: {str(e)}")
            return TextContent(
                type="text",
                text=f"Error creating/updating flow: {str(e)}"
            )


class ListFlows(Tool):
    """
    List all flows or search for specific flows
    
    This tool retrieves information about existing flows in IOFlow,
    with optional filtering by name, status, or trigger type.
    """
    
    name = "list_flows"
    description = "List all flows or search for specific flows by criteria"
    
    def __init__(self, auth_handler=None):
        super().__init__(auth_handler)
    
    async def run(
        self,
        search_name: Optional[str] = None,
        status: Optional[str] = None,
        trigger_type: Optional[str] = None,
        limit: int = 20
    ) -> TextContent:
        """
        List flows with optional filtering
        
        Args:
            search_name: Optional partial flow name to search for
            status: Optional status filter (active, inactive, draft)
            trigger_type: Optional trigger type filter (manual, schedule, webhook, etc.)
            limit: Maximum number of flows to return
        
        Returns:
            List of flows with their details
        """
        try:
            caller = self._caller()
            if not self._identified(caller):
                return self._unidentified()
            with get_db_context() as db:
                # The caller's own tenant's flows only.
                query = db.query(Flow).filter(Flow.tenant_id == caller["tenant_id"])
                
                # Apply filters
                if search_name:
                    query = query.filter(Flow.flow_name.ilike(f"%{search_name}%"))
                
                if status:
                    query = query.filter(Flow.status == status)
                
                if trigger_type:
                    # PostgreSQL JSONB extraction
                    query = query.filter(
                        Flow.trigger_config['type'].astext == trigger_type
                    )
                
                # Apply limit and get results
                flows = query.limit(limit).all()
                
                if not flows:
                    return TextContent(
                        type="text",
                        text="No flows found matching the criteria."
                    )
                
                # Format results
                result_lines = ["# Flows Found\n"]
                
                for flow in flows:
                    trigger_info = flow.trigger_config or {}
                    node_count = len(flow.flow_definition.get('nodes', []))
                    edge_count = len(flow.flow_definition.get('edges', []))
                    
                    result_lines.append(f"""
## {flow.flow_name}
- **ID:** {flow.flow_id}
- **Status:** {flow.status}
- **Description:** {flow.description or 'No description'}
- **Trigger Type:** {trigger_info.get('type', 'Unknown')}
- **Nodes:** {node_count}, **Edges:** {edge_count}
- **Synchronous:** {flow.is_synchronous}
- **Created:** {flow.created_at.strftime('%Y-%m-%d %H:%M')}
---""")
                
                result_lines.append(f"\nTotal flows found: {len(flows)}")
                
                return TextContent(
                    type="text",
                    text="\n".join(result_lines)
                )
                
        except Exception as e:
            logger.error(f"Error listing flows: {str(e)}")
            return TextContent(
                type="text",
                text=f"Error listing flows: {str(e)}"
            )


class DeleteFlow(Tool):
    """
    Delete a flow from IOFlow
    
    This tool permanently deletes a flow from the system.
    Use with caution as this action cannot be undone.
    """
    
    name = "delete_flow"
    description = "Delete a flow from IOFlow (permanent action)"
    
    def __init__(self, auth_handler=None):
        super().__init__(auth_handler)
    
    async def run(
        self,
        flow_id: Optional[str] = None,
        flow_name: Optional[str] = None,
        confirm: bool = False
    ) -> TextContent:
        """
        Delete a flow by ID or name
        
        Args:
            flow_id: ID of the flow to delete
            flow_name: Name of the flow to delete (if ID not provided)
            confirm: Must be True to confirm deletion
        
        Returns:
            Confirmation message or error
        """
        try:
            if not confirm:
                return TextContent(
                    type="text",
                    text="Error: Set confirm=True to delete the flow. This action cannot be undone."
                )
            
            if not flow_id and not flow_name:
                return TextContent(
                    type="text",
                    text="Error: Either flow_id or flow_name must be provided"
                )
            
            caller = self._caller()
            if not self._identified(caller):
                return self._unidentified()

            with get_db_context() as db:
                # Find the flow — the caller's own tenant's (by name, only theirs
                # is ever considered; by id, another tenant's counts as absent).
                if flow_id:
                    flow = db.query(Flow).filter(Flow.flow_id == flow_id).first()
                    if flow is not None and not self._may_write_flow(flow, caller):
                        flow = None
                else:
                    flow = db.query(Flow).filter(
                        Flow.flow_name == flow_name,
                        Flow.tenant_id == caller["tenant_id"]
                    ).first()

                if not flow:
                    return TextContent(
                        type="text",
                        text=f"Error: Flow not found with {'ID: ' + flow_id if flow_id else 'name: ' + flow_name}"
                    )
                
                # Store flow details before deletion
                deleted_flow_name = flow.flow_name
                deleted_flow_id = flow.flow_id
                
                # Delete the flow
                db.delete(flow)
                db.commit()
                
                return TextContent(
                    type="text",
                    text=f"""✅ Flow deleted successfully!

**Deleted Flow:**
- Flow ID: {deleted_flow_id}
- Flow Name: {deleted_flow_name}

The flow has been permanently removed from the system."""
                )
                
        except Exception as e:
            logger.error(f"Error deleting flow: {str(e)}")
            return TextContent(
                type="text",
                text=f"Error deleting flow: {str(e)}"
            )


class ValidateFlowDefinition(Tool):
    """
    Validate a flow definition before creating or updating
    
    This tool validates a flow definition for structural correctness,
    logical consistency, and best practices compliance.
    """
    
    name = "validate_flow_definition"
    description = "Validate a flow definition for correctness and best practices"
    
    def __init__(self, auth_handler=None):
        super().__init__(auth_handler)
    
    async def run(
        self,
        flow_definition: Dict[str, Any],
        check_warnings: bool = True,
        check_best_practices: bool = True
    ) -> TextContent:
        """
        Validate a flow definition
        
        Args:
            flow_definition: The flow definition to validate
            check_warnings: If True, also check for warnings (variable references)
            check_best_practices: If True, check against best practices
        
        Returns:
            Validation report with errors, warnings, and recommendations
        """
        try:
            report_lines = ["# Flow Validation Report\n"]
            
            # Perform structural validation
            is_valid, errors = FlowValidator.validate_flow_definition(flow_definition)
            
            # Add validation status
            if is_valid:
                report_lines.append("✅ **Validation Status**: PASSED\n")
            else:
                report_lines.append("❌ **Validation Status**: FAILED\n")
            
            # Add errors if any
            if errors:
                report_lines.append("## Errors\n")
                report_lines.append("The following errors must be fixed:\n")
                for i, error in enumerate(errors, 1):
                    report_lines.append(f"{i}. {error}")
                report_lines.append("")
            
            # Check for warnings
            if check_warnings:
                warnings = FlowValidator.validate_variable_references(flow_definition)
                if warnings:
                    report_lines.append("## Warnings\n")
                    report_lines.append("The following warnings should be reviewed:\n")
                    for i, warning in enumerate(warnings, 1):
                        report_lines.append(f"{i}. {warning}")
                    report_lines.append("")
            
            # Check best practices
            if check_best_practices:
                best_practice_issues = self._check_best_practices(flow_definition)
                if best_practice_issues:
                    report_lines.append("## Best Practice Recommendations\n")
                    for i, issue in enumerate(best_practice_issues, 1):
                        report_lines.append(f"{i}. {issue}")
                    report_lines.append("")
            
            # Add flow statistics
            nodes = flow_definition.get('nodes', [])
            edges = flow_definition.get('edges', [])
            
            report_lines.append("## Flow Statistics\n")
            report_lines.append(f"- **Total Nodes**: {len(nodes)}")
            report_lines.append(f"- **Total Edges**: {len(edges)}")
            
            # Count node types
            node_types = {}
            for node in nodes:
                node_type = node.get('type', 'unknown')
                node_types[node_type] = node_types.get(node_type, 0) + 1
            
            report_lines.append("\n### Node Type Distribution:")
            for node_type, count in sorted(node_types.items()):
                report_lines.append(f"- {node_type}: {count}")
            
            # Add recommendations
            if not is_valid:
                report_lines.append("\n## Next Steps\n")
                report_lines.append("1. Fix all errors listed above")
                report_lines.append("2. Re-validate the flow definition")
                report_lines.append("3. Review and address any warnings")
                report_lines.append("4. Consider implementing best practice recommendations")
            elif warnings or (check_best_practices and best_practice_issues):
                report_lines.append("\n## Next Steps\n")
                report_lines.append("✅ The flow is structurally valid and can be created/updated.")
                report_lines.append("Consider addressing the warnings and recommendations for improved reliability.")
            else:
                report_lines.append("\n## Summary\n")
                report_lines.append("✅ The flow definition is valid and follows best practices!")
            
            return TextContent(
                type="text",
                text="\n".join(report_lines)
            )
            
        except Exception as e:
            logger.error(f"Error validating flow definition: {str(e)}")
            return TextContent(
                type="text",
                text=f"Error validating flow definition: {str(e)}"
            )
    
    def _check_best_practices(self, flow_definition: Dict[str, Any]) -> List[str]:
        """Check flow against best practices"""
        issues = []
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        
        # Check for descriptive labels
        for node in nodes:
            data = node.get('data', {})
            label = data.get('label', '')
            if not label or label == node.get('type', ''):
                issues.append(f"Node {node.get('id')} should have a descriptive label")
        
        # Check for error handling
        has_error_handling = False
        for node in nodes:
            if node.get('type') == 'condition':
                expression = node.get('data', {}).get('expression', '')
                if 'error' in expression.lower() or 'status' in expression.lower():
                    has_error_handling = True
                    break
        
        if not has_error_handling and len(nodes) > 5:
            issues.append("Consider adding error handling conditions for complex flows")
        
        # Check for very long scripts
        for node in nodes:
            if node.get('type') == 'transform':
                script = node.get('data', {}).get('script', '')
                if len(script.split('\n')) > 50:
                    issues.append(f"Transform node {node.get('id')} has a very long script. Consider breaking it into multiple transforms")
        
        # Check for isolated nodes
        node_connections = {node['id']: {'in': 0, 'out': 0} for node in nodes if 'id' in node}
        for edge in edges:
            if edge.get('source') in node_connections:
                node_connections[edge['source']]['out'] += 1
            if edge.get('target') in node_connections:
                node_connections[edge['target']]['in'] += 1
        
        # Note: We don't check for nodes without outgoing connections as IOFlow allows natural termination
        
        # Check for excessive complexity
        if len(nodes) > 50:
            issues.append("Flow has more than 50 nodes. Consider breaking it into smaller sub-flows")
        
        # Check for missing response in synchronous flows
        has_response = any(n.get('type') == 'response' for n in nodes)
        if not has_response and len(nodes) > 3:
            issues.append("Consider adding a response node if this is meant to be a synchronous flow")
        
        # Check file type configurations in manual triggers
        for node in nodes:
            if node.get('type') == 'trigger':
                trigger_data = node.get('data', {})
                if trigger_data.get('triggerType') == 'manual':
                    manual_vars = trigger_data.get('manualVariables', [])
                    for var in manual_vars:
                        if var.get('dataType') == 'file':
                            validation = var.get('validation', {})
                            if not validation.get('acceptedFileTypes'):
                                issues.append(f"File argument '{var.get('name', 'unknown')}' in trigger should specify accepted file types for better user experience")
                            if not validation.get('maxFileSize'):
                                issues.append(f"File argument '{var.get('name', 'unknown')}' in trigger should specify maximum file size limit")
        
        return issues


class ParameterMappingGuidelines(Tool):
    """
    Provides comprehensive guidelines for parameter mapping in action nodes.
    """
    
    name = "get_parameter_mapping_guide"
    description = """Get comprehensive guide for parameter mapping in action nodes.
    
    This tool provides:
    - Correct parameter mapping structure and patterns
    - Service-specific examples (Google Sheets, Gemini, etc.)
    - Common mistakes and how to avoid them
    - Variable reference patterns
    
    Args:
        service_name (str, optional): Specific service to get examples for (e.g., 'google_sheets', 'gemini')
        
    Returns:
        Detailed parameter mapping guidelines with examples
    """
    
    async def run(self, service_name: str = None) -> str:
        """Run the tool"""
        logger.info(f"Getting parameter mapping guidelines for: {service_name or 'general'}")
        
        if service_name:
            return self._get_service_specific_guide(service_name)
        else:
            return self._get_general_guide()
    
    def _get_general_guide(self) -> str:
        """Get general parameter mapping guidelines"""
        return """
# Parameter Mapping Guidelines for Action Nodes

## CRITICAL RULES

### 1. ALWAYS Use parameterMapping (Never parameters)
```json
{
  "type": "action",
  "data": {
    "parameterMapping": {  // ✅ CORRECT
      "field1": "value1"
    }
    // "parameters": {}  // ❌ NEVER USE THIS
  }
}
```

### 2. Direct Parameter Mapping (No Unnecessary Nesting)
Parameters should be mapped directly at the root level of parameterMapping:

**❌ INCORRECT - Unnecessary nesting:**
```json
"parameterMapping": {
  "properties": {
    "title": "My Title"  // WRONG - nested in properties
  }
}
```

**✅ CORRECT - Direct mapping:**
```json
"parameterMapping": {
  "title": "My Title"  // RIGHT - directly at root
}
```

### 3. Variable Reference Patterns

#### Input Variables
```json
"parameterMapping": {
  "name": "{{input.customer_name}}",
  "email": "{{input.email_address}}"
}
```

#### Previous Node Outputs
```json
"parameterMapping": {
  "data": "{{node_outputs.transform_1.result}}",
  "id": "{{node_outputs.fetch_data.record_id}}"
}
```

#### Loop Variables
```json
"parameterMapping": {
  "item_id": "{{loop.item.id}}",
  "index": "{{loop.index}}"
}
```

#### Mixed Static and Dynamic
```json
"parameterMapping": {
  "api_version": "v2",  // Static value
  "user_id": "{{input.user_id}}",  // Dynamic from input
  "timestamp": "{{node_outputs.get_time.value}}"  // From previous node
}
```

## Common Mistakes to Avoid

### 1. Nesting in Wrapper Objects
**❌ WRONG:**
```json
"parameterMapping": {
  "body": {
    "properties": {
      "title": "value"
    }
  }
}
```

**✅ CORRECT:**
```json
"parameterMapping": {
  "title": "value"
}
```

### 2. Using Wrong Case Convention
**❌ WRONG:**
```json
"parameterMapping": {
  "file_data": {  // Snake case - incorrect for Gemini
    "mime_type": "image/png"
  }
}
```

**✅ CORRECT:**
```json
"parameterMapping": {
  "fileData": {  // Camel case - correct for Gemini
    "mimeType": "image/png"
  }
}
```

### 3. Incorrect Array Handling
**❌ WRONG:**
```json
"parameterMapping": {
  "values": "{{node_outputs.transform.array}}"  // If this returns nested array
}
```

**✅ CORRECT:**
```json
"parameterMapping": {
  "values": "{{node_outputs.transform.values}}"  // Ensure correct array structure
}
```

## Parameter Schema Validation

Parameters MUST match the service's parameter_schema exactly:

1. **Required parameters** - Must be present
2. **Parameter types** - Must match schema type (string, number, array, etc.)
3. **Parameter names** - Must match exactly (case-sensitive)
4. **Nested structures** - Must follow schema structure

## Best Practices

1. **Check Service Schema First**
   - Look at the service's parameter_schema
   - Use exact parameter names
   - Follow the expected structure

2. **Use Variable References Correctly**
   - Always wrap in double curly braces: `{{}}`
   - Use dot notation for nested access
   - Validate the path exists

3. **Test with Simple Values First**
   - Start with static values
   - Then add variable references
   - Validate each step

4. **Handle Optional Parameters**
   - Only include if needed
   - Use null or empty string if required but not used
   - Check default values in schema

## Debugging Tips

1. **Check Execution Logs**
   - Look for parameter mapping errors
   - Check resolved values
   - Verify structure matches schema

2. **Validate Against Schema**
   - Compare your parameters with service schema
   - Check required fields
   - Verify data types

3. **Common Error Messages**
   - "Missing required parameter" → Add the parameter
   - "Invalid parameter type" → Check data type
   - "Unknown parameter" → Check spelling/case
   - "Invalid structure" → Remove unnecessary nesting
"""
    
    def _get_service_specific_guide(self, service_name: str) -> str:
        """Get service-specific parameter mapping guidelines"""
        
        guides = {
            "google_sheets": """
# Google Sheets Parameter Mapping Guide

## Service: create_spreadsheet
**✅ CORRECT:**
```json
"parameterMapping": {
  "title": "{{input.spreadsheet_name}}",
  "locale": "en_US",
  "timeZone": "America/New_York"
}
```

**❌ INCORRECT:**
```json
"parameterMapping": {
  "properties": {  // WRONG - unnecessary nesting
    "title": "{{input.spreadsheet_name}}"
  }
}
```

## Service: append_values
**✅ CORRECT:**
```json
"parameterMapping": {
  "spreadsheetId": "{{node_outputs.create_sheet.spreadsheetId}}",
  "range": "Sheet1!A1",
  "valueInputOption": "USER_ENTERED",
  "values": "{{node_outputs.prepare_data.rows}}"  // Must be 2D array
}
```

**Important:** The `values` parameter must be a 2D array:
```json
[
  ["Header1", "Header2", "Header3"],
  ["Value1", "Value2", "Value3"],
  ["Value4", "Value5", "Value6"]
]
```

## Service: update_values
**✅ CORRECT:**
```json
"parameterMapping": {
  "spreadsheetId": "{{input.sheet_id}}",
  "range": "A1:C10",
  "valueInputOption": "RAW",
  "values": "{{node_outputs.transform.data}}"
}
```

## Service: get_values
**✅ CORRECT:**
```json
"parameterMapping": {
  "spreadsheetId": "{{input.sheet_id}}",
  "range": "Sheet1!A1:Z1000",
  "majorDimension": "ROWS",
  "valueRenderOption": "FORMATTED_VALUE"
}
```
""",
            
            "gemini": """
# Google Gemini Parameter Mapping Guide

## Service: generate_content

### Text-Only Generation
**✅ CORRECT:**
```json
"parameterMapping": {
  "model": "gemini-2.5-flash",
  "contents": [
    {
      "parts": [
        {
          "text": "{{input.prompt}}"
        }
      ]
    }
  ],
  "generationConfig": {
    "temperature": 0.9,
    "maxOutputTokens": 2048
  }
}
```

### With File Input (Image/PDF)
**✅ CORRECT - Note the camelCase:**
```json
"parameterMapping": {
  "model": "gemini-2.5-flash",
  "contents": [
    {
      "parts": [
        {
          "text": "{{node_outputs.prepare_prompt.text}}"
        },
        {
          "fileData": {  // ✅ camelCase, not file_data
            "mimeType": "{{node_outputs.prepare_file.mime_type}}",
            "fileUri": "{{node_outputs.prepare_file.uri}}"
          }
        }
      ]
    }
  ]
}
```

**❌ INCORRECT - Wrong case:**
```json
{
  "file_data": {  // ❌ WRONG - should be fileData
    "mime_type": "image/png",  // ❌ WRONG - should be mimeType
    "file_uri": "..."  // ❌ WRONG - should be fileUri
  }
}
```

### With System Instructions
**✅ CORRECT:**
```json
"parameterMapping": {
  "model": "gemini-2.5-pro",
  "contents": [
    {
      "parts": [
        {
          "text": "{{input.user_message}}"
        }
      ]
    }
  ],
  "systemInstruction": {
    "parts": [
      {
        "text": "You are a helpful assistant specialized in data analysis."
      }
    ]
  }
}
```

### With Safety Settings
**✅ CORRECT:**
```json
"parameterMapping": {
  "model": "gemini-2.5-flash",
  "contents": "{{node_outputs.prepare_content.value}}",
  "safetySettings": [
    {
      "category": "HARM_CATEGORY_HATE_SPEECH",
      "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    }
  ]
}
```
""",
            
            "openai": """
# OpenAI Parameter Mapping Guide

## Service: chat_completion
**✅ CORRECT:**
```json
"parameterMapping": {
  "model": "gpt-4",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "{{input.user_message}}"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

## Service: create_image
**✅ CORRECT:**
```json
"parameterMapping": {
  "prompt": "{{input.image_description}}",
  "n": 1,
  "size": "1024x1024",
  "quality": "standard",
  "style": "natural"
}
```
""",
            
            "slack": """
# Slack Parameter Mapping Guide

## Service: post_message
**✅ CORRECT:**
```json
"parameterMapping": {
  "channel": "{{input.channel_id}}",
  "text": "{{node_outputs.format_message.text}}",
  "blocks": "{{node_outputs.format_message.blocks}}",
  "thread_ts": "{{input.thread_timestamp}}"
}
```

## Service: upload_file
**✅ CORRECT:**
```json
"parameterMapping": {
  "channels": "{{input.channel_id}}",
  "filename": "{{input.file.name}}",
  "file": "{{input.file.content}}",
  "initial_comment": "Here's the report you requested"
}
```
"""
        }
        
        if service_name.lower() in guides:
            return guides[service_name.lower()]
        else:
            available = ", ".join(guides.keys())
            return f"""
# Service-Specific Guide Not Found

No specific guide available for '{service_name}'.

Available guides: {available}

Use the general parameter mapping guide for this service.

{self._get_general_guide()}
"""


# Export all tools
FLOW_DESIGN_TOOLS = [
    GetApplicationDetails,
    CreateFlowJSON,
    AnalyzeFlowRequirements,
    CreateOrUpdateFlow,
    ListFlows,
    DeleteFlow,
    ValidateFlowDefinition,
    ParameterMappingGuidelines  # Added new tool
]

__all__ = ['FLOW_DESIGN_TOOLS']