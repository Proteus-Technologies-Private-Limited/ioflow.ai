"""
Flow validation service for synchronous flows
"""
from typing import Dict, List, Set, Tuple, Optional, Any
import re
import json
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class FlowValidationError:
    """Represents a flow validation error"""
    def __init__(self, node_id: str, message: str, error_type: str = "error", field: str = None, suggestion: str = None, node_label: str = None, json_path: str = None):
        self.node_id = node_id
        self.message = message
        self.error_type = error_type  # "error" or "warning"
        self.field = field  # The specific field that has the error
        self.suggestion = suggestion  # How to fix the error
        self.node_label = node_label  # Human-readable node label
        self.json_path = json_path  # JSON path to the error location (e.g., "nodes[3].data.script")


class FlowValidator:
    """Validates flow structure for synchronous execution"""

    # Structure type constants
    STRUCTURE_EXPORT = "export"  # Has version + flow wrapper
    STRUCTURE_DIRECT = "direct"  # Has nodes + edges at root
    STRUCTURE_HYBRID = "hybrid"  # Has flow metadata but no wrapper
    STRUCTURE_INVALID = "invalid"  # Doesn't match any known format

    # Valid node types
    VALID_NODE_TYPES = {
        'trigger', 'action', 'condition', 'transform', 'loop', 'response', 'human_in_loop', 'wait_for_event'
    }
    
    def __init__(self, db: Optional[Session] = None, tenant_id: Optional[str] = None):
        """
        Initialize validator with database session for comprehensive checks.

        Args:
            db: Database session (REQUIRED for proper validation)
            tenant_id: Tenant ID for subscription validation (optional)

        Note: While db is technically optional for backward compatibility,
        comprehensive validation REQUIRES a database session and will fail without it.
        """
        self.db = db
        self.tenant_id = tenant_id
        self._app_cache = {}  # Cache for application lookups
        self._service_cache = {}  # Cache for service lookups
        self._subscription_cache = {}  # Cache for subscription lookups

        if not self.db:
            logger.warning("FlowValidator initialized without database session - comprehensive validation will not be available")
    
    def detect_json_structure(self, json_data: Dict[str, Any]) -> Tuple[str, str, List[str]]:
        """
        Detect the structure type of the JSON data.
        Returns (structure_type, description, suggestions)
        """
        suggestions = []
        
        # Check for export format (version + flow wrapper)
        if "version" in json_data and "flow" in json_data:
            if isinstance(json_data.get("flow"), dict):
                flow = json_data["flow"]
                if "flow_definition" in flow and isinstance(flow["flow_definition"], dict):
                    nodes = flow["flow_definition"].get("nodes")
                    edges = flow["flow_definition"].get("edges")
                    if isinstance(nodes, list) and isinstance(edges, list):
                        return self.STRUCTURE_EXPORT, "Valid export format with version wrapper", []
                    else:
                        return self.STRUCTURE_INVALID, "Export format but flow_definition missing nodes/edges", [
                            "Ensure flow.flow_definition contains 'nodes' and 'edges' arrays"
                        ]
                else:
                    return self.STRUCTURE_INVALID, "Export format but missing flow_definition", [
                        "Add flow_definition with nodes and edges to the flow object"
                    ]
            else:
                return self.STRUCTURE_INVALID, "Has version but 'flow' is not an object", [
                    "The 'flow' field must be an object containing the flow data"
                ]
        
        # Check for direct format (nodes + edges at root)
        elif "nodes" in json_data and "edges" in json_data:
            if isinstance(json_data["nodes"], list) and isinstance(json_data["edges"], list):
                # Check if it's actually a hybrid format
                if "flow_name" in json_data or "flow_definition" in json_data or "trigger_config" in json_data:
                    return self.STRUCTURE_HYBRID, "Hybrid format: has flow metadata but missing export wrapper", [
                        "This format cannot be imported in Flow Designer UI.",
                        "To fix, wrap your JSON in the export format:",
                        "{",
                        '  "version": "1.0",',
                        f'  "export_timestamp": "{json_data.get("export_timestamp", "2025-01-08T00:00:00.000000")}",',
                        '  "flow": {',
                        '    ...your current JSON here...',
                        '  },',
                        '  "metadata": {',
                        '    "required_applications": []',
                        '  }',
                        "}"
                    ]
                else:
                    return self.STRUCTURE_DIRECT, "Direct format with nodes and edges at root", []
            else:
                return self.STRUCTURE_INVALID, "Has nodes/edges but they are not arrays", [
                    "Both 'nodes' and 'edges' must be arrays"
                ]
        
        # Check for hybrid format (has flow structure but no wrapper)
        elif "flow_definition" in json_data and "flow_name" in json_data:
            if isinstance(json_data.get("flow_definition"), dict):
                flow_def = json_data["flow_definition"]
                if "nodes" in flow_def and "edges" in flow_def:
                    return self.STRUCTURE_HYBRID, "Hybrid format: has flow structure but missing export wrapper", [
                        "This format cannot be imported in Flow Designer UI.",
                        "To fix, wrap your JSON in the export format:",
                        "{",
                        '  "version": "1.0",',
                        '  "export_timestamp": "2025-01-08T00:00:00.000000",',
                        '  "flow": {',
                        '    ...your current JSON here...',
                        '  },',
                        '  "metadata": {',
                        '    "required_applications": []',
                        '  }',
                        "}",
                        "",
                        "Alternatively, extract just the flow_definition content:",
                        "{",
                        '  "nodes": [...],',
                        '  "edges": [...]',
                        "}"
                    ]
                else:
                    return self.STRUCTURE_INVALID, "Has flow_definition but missing nodes/edges", [
                        "The flow_definition must contain 'nodes' and 'edges' arrays"
                    ]
            else:
                return self.STRUCTURE_INVALID, "Has flow_name but flow_definition is not an object", [
                    "The flow_definition must be an object containing nodes and edges"
                ]
        
        # Invalid structure
        return self.STRUCTURE_INVALID, "Unrecognized JSON structure", [
            "Flow JSON must be in one of these formats:",
            "1. Export format: {\"version\": \"1.0\", \"flow\": {...}, \"metadata\": {...}}",
            "2. Direct format: {\"nodes\": [...], \"edges\": [...]}"
        ]
    
    def validate_json(self, flow_data: Any) -> Tuple[bool, Optional[Dict], List[FlowValidationError]]:
        """
        Public method to validate JSON structure of flow data.
        Returns (is_valid, parsed_data, errors)
        """
        is_valid, parsed_data, error_msg = self._validate_json_structure(flow_data)
        errors = []
        if not is_valid:
            errors.append(FlowValidationError(
                node_id="flow",
                message=error_msg,
                error_type="error",
                field="flow_definition"
            ))
        return is_valid, parsed_data, errors
    
    def _validate_json_structure(self, flow_data: Any) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate that the flow data is valid JSON/dict structure.
        Returns (is_valid, parsed_data, error_message)
        """
        # If it's a string, try to parse it as JSON
        if isinstance(flow_data, str):
            try:
                parsed_data = json.loads(flow_data)
                if not isinstance(parsed_data, dict):
                    return False, None, "Flow data must be a JSON object, not an array or primitive value"
                return True, parsed_data, None
            except json.JSONDecodeError as e:
                return False, None, f"Invalid JSON format: {str(e)}"
        
        # If it's already a dict, validate it has the required structure
        elif isinstance(flow_data, dict):
            # Check if it can be serialized to JSON (no invalid types)
            try:
                json.dumps(flow_data)
                return True, flow_data, None
            except (TypeError, ValueError) as e:
                return False, None, f"Flow data contains non-serializable values: {str(e)}"
        
        # If it's neither string nor dict
        else:
            return False, None, f"Flow data must be a JSON string or dictionary, got {type(flow_data).__name__}"
    
    def validate_import_structure(self, json_data: Dict[str, Any]) -> Tuple[bool, List[FlowValidationError], List[str]]:
        """
        Validate if the JSON structure is importable in Flow Designer UI.
        Returns (is_importable, errors/warnings, suggestions)
        """
        errors = []
        suggestions = []
        
        structure_type, description, structure_suggestions = self.detect_json_structure(json_data)
        
        # Export and Direct formats are importable
        if structure_type in [self.STRUCTURE_EXPORT, self.STRUCTURE_DIRECT]:
            return True, [], [f"✅ Structure is importable: {description}"]
        
        # Hybrid format is NOT importable - this should be an ERROR
        elif structure_type == self.STRUCTURE_HYBRID:
            errors.append(FlowValidationError(
                node_id="structure",
                message="Flow structure is not importable in UI - hybrid format detected",
                error_type="error",  # Changed from warning to error
                field="structure",
                suggestion="Wrap in export format or use direct format"
            ))
            return False, errors, structure_suggestions
        
        # Invalid format
        else:
            errors.append(FlowValidationError(
                node_id="structure",
                message=f"Invalid structure: {description}",
                error_type="error",
                field="structure"
            ))
            return False, errors, structure_suggestions
    
    def validate_flow_comprehensive(self, flow_definition: Any, functions: Optional[Dict[str, str]] = None) -> Tuple[bool, List[FlowValidationError]]:
        """
        Comprehensive validation of a flow including mandatory parameters and external functions.
        Returns (is_valid, errors)
        """
        errors = []

        # Database session is required for comprehensive validation
        if not self.db:
            errors.append(FlowValidationError(
                node_id="system",
                message="Database session is required for flow validation. Cannot perform comprehensive validation without database access.",
                error_type="error",
                field="database"
            ))
            return False, errors

        # First, validate JSON structure
        is_valid_json, parsed_data, json_error = self._validate_json_structure(flow_definition)
        if not is_valid_json:
            errors.append(FlowValidationError(
                node_id="flow",
                message=f"Invalid flow data: {json_error}",
                error_type="error",
                field="flow_definition"
            ))
            return False, errors

        # Use the parsed data for further validation
        flow_definition = parsed_data

        # Collect ALL missing functions across ALL transform nodes if no functions provided
        if not functions:
            all_missing_functions = set()
            nodes_with_missing = []

            nodes = flow_definition.get('nodes', [])
            for node in nodes:
                if node.get('type') == 'transform':
                    node_data = node.get('data', {})
                    functions_used = node_data.get('functions_used', [])
                    if functions_used:
                        all_missing_functions.update(functions_used)
                        nodes_with_missing.append(node.get('id', 'unknown'))

            # If missing functions found, add a comprehensive error at the beginning
            if all_missing_functions:
                func_list = ", ".join(sorted(all_missing_functions))
                node_list = ", ".join(nodes_with_missing)

                comprehensive_msg = (
                    f"MISSING FUNCTIONS: {len(all_missing_functions)} function(s) required: [{func_list}]. "
                    f"Nodes affected: {node_list}. "
                    f"TO FIX: Create Python implementations:\n"
                )

                # Add example implementations
                for func in sorted(all_missing_functions):
                    comprehensive_msg += f"def {func}(input):\n    # TODO: Implement {func}\n    return {{'result': 'processed'}}\n\n"

                comprehensive_msg += "Then call: validate_flow_json(flow_json, functions=python_code)"

                errors.append(FlowValidationError(
                    node_id="functions",
                    message=comprehensive_msg,
                    error_type="error",
                    field="functions_missing"
                ))

        # Check for required fields
        if 'nodes' not in flow_definition:
            errors.append(FlowValidationError(
                node_id="flow",
                message="Flow definition must contain 'nodes' field",
                error_type="error",
                field="nodes"
            ))
            return False, errors
            
        if 'edges' not in flow_definition:
            errors.append(FlowValidationError(
                node_id="flow",
                message="Flow definition must contain 'edges' field",
                error_type="error",
                field="edges"
            ))
            return False, errors
        
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        
        # Validate that nodes and edges are lists
        if not isinstance(nodes, list):
            errors.append(FlowValidationError(
                node_id="flow",
                message="'nodes' must be an array",
                error_type="error",
                field="nodes"
            ))
            return False, errors
            
        if not isinstance(edges, list):
            errors.append(FlowValidationError(
                node_id="flow",
                message="'edges' must be an array",
                error_type="error",
                field="edges"
            ))
            return False, errors
        
        # Validate each node for mandatory parameters
        for idx, node in enumerate(nodes):
            node_errors = self._validate_node_parameters(node, functions, node_index=idx)
            errors.extend(node_errors)
        
        # Build adjacency lists for structure validation
        adjacency = self._build_adjacency_list(edges)
        reverse_adjacency = self._build_reverse_adjacency_list(edges)
        
        # Check for disconnected nodes
        disconnected = self._find_disconnected_nodes(nodes, adjacency, reverse_adjacency)
        for node_id, node_label in disconnected:
            errors.append(FlowValidationError(
                node_id=node_id,
                message=f"Node '{node_label}' is disconnected from the flow",
                error_type="warning"
            ))
        
        # Check for missing trigger node
        trigger_nodes = [n for n in nodes if n.get('type') == 'trigger']
        if len(trigger_nodes) == 0:
            errors.append(FlowValidationError(
                node_id="flow",
                message="Flow must have at least one trigger node",
                error_type="error"
            ))
        elif len(trigger_nodes) > 1:
            errors.append(FlowValidationError(
                node_id="flow",
                message="Flow has multiple trigger nodes",
                error_type="warning"
            ))
        
        # Check for duplicate app+event combos in wait_for_event nodes
        wait_event_nodes = [n for n in nodes if n.get('type') == 'wait_for_event']
        if len(wait_event_nodes) > 1:
            # Group by (appId, eventName)
            event_groups = {}
            for n in wait_event_nodes:
                nd = n.get('data', {})
                app_id = nd.get('appId', '')
                event_name = nd.get('eventName', '') or nd.get('eventId', '')
                if app_id and event_name:
                    key = (app_id, event_name)
                    event_groups.setdefault(key, []).append(n)

            for key, group_nodes in event_groups.items():
                if len(group_nodes) > 1:
                    # Multiple nodes waiting for the same app+event
                    node_labels = [gn.get('data', {}).get('label', gn.get('id', '')) for gn in group_nodes]
                    for gn in group_nodes:
                        gn_data = gn.get('data', {})
                        gn_id = gn.get('id', 'unknown')
                        gn_label = gn_data.get('label', gn_id)
                        match_mode = gn_data.get('matchMode', 'token')
                        other_labels = [l for l in node_labels if l != gn_label]

                        if match_mode != 'correlation':
                            # Correlation is mandatory when same app+event appears multiple times
                            errors.append(FlowValidationError(
                                node_id=gn_id,
                                message=f"Correlation match mode is required because nodes [{', '.join(other_labels)}] wait for the same application event. Without correlation, the system cannot determine which node should receive the event.",
                                error_type="error",
                                field="matchMode",
                                suggestion="Switch to Correlation match mode and configure a unique correlation field to distinguish which event belongs to this node.",
                                node_label=gn_label,
                            ))
                        else:
                            # Correlation mode is set, but warn about potential conflicts
                            corr = gn_data.get('correlationConfig', {})
                            if not corr.get('eventField') or not corr.get('flowField'):
                                errors.append(FlowValidationError(
                                    node_id=gn_id,
                                    message=f"Correlation fields must be configured because nodes [{', '.join(other_labels)}] wait for the same application event.",
                                    error_type="error",
                                    field="correlationConfig",
                                    suggestion="Configure the Event Field and Flow Value to uniquely match events to this node.",
                                    node_label=gn_label,
                                ))

        # Validate variable and node references across the flow
        reference_errors = self._validate_references(nodes, edges)
        errors.extend(reference_errors)

        # Validate node error handling (retry / on-error / error branch edges)
        errors.extend(self._validate_error_handling(nodes, edges))
        
        is_valid = not any(e.error_type == "error" for e in errors)
        return is_valid, errors

    def _validate_error_handling(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[FlowValidationError]:
        """Check each node's errorHandling block against its error-branch edges."""
        from services.node_error_handling import (
            ERROR_HANDLE, ON_ERROR_MODES, ON_ERROR_BRANCH, ERROR_TYPES, RETRY_ON_ANY,
            NO_POLICY_NODE_TYPES, NON_RETRYABLE_NODE_TYPES, MAX_ATTEMPTS_LIMIT,
        )
        errors: List[FlowValidationError] = []
        error_edge_sources = {}
        for edge in edges:
            if isinstance(edge, dict) and edge.get('sourceHandle') == ERROR_HANDLE:
                error_edge_sources.setdefault(edge.get('source'), []).append(edge.get('target'))

        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = node.get('id', 'unknown')
            node_type = node.get('type', '')
            node_data = node.get('data') or {}
            if not isinstance(node_data, dict):
                continue
            label = node_data.get('label', node_id)
            config = node_data.get('errorHandling', node_data.get('error_handling'))
            has_error_edges = node_id in error_edge_sources

            if config is None:
                if has_error_edges:
                    errors.append(FlowValidationError(
                        node_id=node_id, node_label=label, error_type="warning", field="errorHandling",
                        message=f"Node '{label}' has an error-branch connection but no error handling configured, so the branch never runs",
                        suggestion="Set the node's On Error option to 'Route to error branch'."))
                continue
            if not isinstance(config, dict):
                errors.append(FlowValidationError(
                    node_id=node_id, node_label=label, error_type="error", field="errorHandling",
                    message=f"Node '{label}' has an invalid errorHandling configuration (expected an object)"))
                continue
            if node_type in NO_POLICY_NODE_TYPES:
                errors.append(FlowValidationError(
                    node_id=node_id, node_label=label, error_type="warning", field="errorHandling",
                    message=f"Error handling is not supported on {node_type} nodes and will be ignored"))
                continue

            on_error = config.get('onError', config.get('on_error', 'stop'))
            if on_error not in ON_ERROR_MODES:
                errors.append(FlowValidationError(
                    node_id=node_id, node_label=label, error_type="error", field="errorHandling.onError",
                    message=f"Node '{label}' has an unknown On Error mode '{on_error}'",
                    suggestion=f"Use one of: {', '.join(ON_ERROR_MODES)}"))
            elif on_error == ON_ERROR_BRANCH and not has_error_edges:
                errors.append(FlowValidationError(
                    node_id=node_id, node_label=label, error_type="warning", field="errorHandling.onError",
                    message=f"Node '{label}' routes errors to its error branch, but nothing is connected to its error output",
                    suggestion="Connect the red error handle to the node that should handle the failure."))
            elif on_error != ON_ERROR_BRANCH and has_error_edges:
                errors.append(FlowValidationError(
                    node_id=node_id, node_label=label, error_type="warning", field="errorHandling.onError",
                    message=f"Node '{label}' has an error-branch connection, but its On Error mode is '{on_error}', so the branch never runs",
                    suggestion="Set On Error to 'Route to error branch' or remove the error connection."))

            retry = config.get('retry')
            if isinstance(retry, dict) and retry.get('enabled'):
                if node_type in NON_RETRYABLE_NODE_TYPES:
                    errors.append(FlowValidationError(
                        node_id=node_id, node_label=label, error_type="warning", field="errorHandling.retry",
                        message=f"Retry is not supported on {node_type} nodes and will be ignored"))
                attempts = retry.get('maxAttempts', retry.get('max_attempts', 3))
                try:
                    attempts_ok = 1 <= int(attempts) <= MAX_ATTEMPTS_LIMIT
                except (TypeError, ValueError):
                    attempts_ok = False
                if not attempts_ok:
                    errors.append(FlowValidationError(
                        node_id=node_id, node_label=label, error_type="warning", field="errorHandling.retry.maxAttempts",
                        message=f"Retry max attempts must be between 1 and {MAX_ATTEMPTS_LIMIT} (got {attempts!r}); it will be clamped"))
                retry_on = retry.get('retryOn', retry.get('retry_on')) or []
                if isinstance(retry_on, str):
                    retry_on = [retry_on]
                unknown = [t for t in retry_on if t not in ERROR_TYPES and t != RETRY_ON_ANY] if isinstance(retry_on, list) else []
                if unknown:
                    errors.append(FlowValidationError(
                        node_id=node_id, node_label=label, error_type="warning", field="errorHandling.retry.retryOn",
                        message=f"Unknown retry error types {unknown} will be ignored",
                        suggestion=f"Valid types: {', '.join(ERROR_TYPES)}, or 'any'"))
        return errors
    
    def _validate_application_exists(self, app_id: str) -> bool:
        """Check if application exists and is accessible"""
        if not self.db:
            raise ValueError("Database session is required for application validation. Cannot validate flow without database access.")
        
        # Check cache first
        if app_id in self._app_cache:
            return self._app_cache[app_id]
        
        # Import models here to avoid circular imports
        from db.application_models import Application
        
        # Check if application exists
        app = self.db.query(Application).filter(Application.app_id == app_id).first()
        self._app_cache[app_id] = app is not None
        return app is not None
    
    def _validate_service_exists(self, app_id: str, service_id: str) -> bool:
        """Check if service exists for the given application"""
        if not self.db:
            raise ValueError("Database session is required for service validation. Cannot validate flow without database access.")
        
        cache_key = f"{app_id}:{service_id}"
        if cache_key in self._service_cache:
            return self._service_cache[cache_key]
        
        # Import models here to avoid circular imports
        from db.application_models import ApplicationService
        
        # Check if service exists for this application (by service_id only)
        service = self.db.query(ApplicationService).filter(
            ApplicationService.app_id == app_id,
            ApplicationService.service_id == service_id,
            ApplicationService.is_active == True
        ).first()
        self._service_cache[cache_key] = service is not None
        return service is not None
    
    def _find_service_by_name(self, app_id: str, service_name: str) -> Optional[str]:
        """Find service ID by service name"""
        if not self.db:
            raise ValueError("Database session is required for service lookup. Cannot validate flow without database access.")
        
        # Import models here to avoid circular imports
        from db.application_models import ApplicationService
        
        service = self.db.query(ApplicationService).filter(
            ApplicationService.app_id == app_id,
            ApplicationService.service_name == service_name,
            ApplicationService.is_active == True
        ).first()
        
        return str(service.service_id) if service else None
    
    def _validate_subscription_exists(self, app_id: str) -> bool:
        """Check if tenant has subscription to the application"""
        if not self.db:
            raise ValueError("Database session is required for subscription validation. Cannot validate flow without database access.")
        if not self.tenant_id:
            logger.warning("No tenant_id provided for subscription validation, skipping subscription check")
            return True  # For system-level operations, subscription check can be skipped
        
        if app_id in self._subscription_cache:
            return self._subscription_cache[app_id]
        
        # Import models here to avoid circular imports
        from db.application_models import ApplicationSubscription
        
        # Check if tenant has active subscription
        subscription = self.db.query(ApplicationSubscription).filter(
            ApplicationSubscription.tenant_id == self.tenant_id,
            ApplicationSubscription.app_id == app_id,
            ApplicationSubscription.status == 'active'
        ).first()
        self._subscription_cache[app_id] = subscription is not None
        return subscription is not None
    
    def _get_service_schema(self, app_id: str, service_id: str) -> Optional[Dict[str, Any]]:
        """Get the parameter schema for a service"""
        if not self.db:
            raise ValueError("Database session is required for service schema retrieval. Cannot validate flow without database access.")
        
        # Import models here to avoid circular imports
        from db.application_models import ApplicationService
        import json
        
        service = self.db.query(ApplicationService).filter(
            ApplicationService.app_id == app_id,
            ApplicationService.service_id == service_id
        ).first()
        
        if not service:
            return None
            
        # Try to get parameter_schema first, then fall back to input_schema
        if hasattr(service, 'parameter_schema') and service.parameter_schema:
            try:
                return json.loads(service.parameter_schema)
            except (json.JSONDecodeError, TypeError):
                pass
                
        if service.input_schema:
            try:
                return json.loads(service.input_schema)
            except (json.JSONDecodeError, TypeError):
                pass
                
        return None
    
    def _get_service_mandatory_parameters(self, app_id: str, service_id: str) -> List[str]:
        """Get mandatory parameters for a service"""
        if not self.db:
            raise ValueError("Database session is required for parameter validation. Cannot validate flow without database access.")
        
        # Import models here to avoid circular imports
        from db.application_models import ApplicationService
        import json
        
        service = self.db.query(ApplicationService).filter(
            ApplicationService.app_id == app_id,
            ApplicationService.service_id == service_id
        ).first()
        
        if not service or not service.input_schema:
            return []
        
        # Extract required parameters from input schema
        input_schema = service.input_schema
        
        # Handle both dict and JSON string formats
        if isinstance(input_schema, str):
            try:
                input_schema = json.loads(input_schema)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse input schema for service {service_id}")
                return []
        
        if isinstance(input_schema, dict):
            required = input_schema.get('required', [])
            logger.debug(f"Service {service_id} has required parameters: {required}")
            return required
        return []
    
    def _validate_node_parameters(self, node: Dict[str, Any], functions: Optional[Dict[str, str]] = None, node_index: int = -1) -> List[FlowValidationError]:
        """Validate mandatory parameters for a node"""
        errors = []
        node_id = node.get('id', 'unknown')
        node_type = node.get('type')
        data = node.get('data', {})
        node_label = data.get('label', node_id)
        json_path_prefix = f"nodes[{node_index}]" if node_index >= 0 else f"node({node_id})"

        # First, validate that the node type is valid
        if not node_type:
            errors.append(FlowValidationError(
                node_id=node_id,
                message="Node type is missing",
                error_type="error",
                field="type",
                suggestion="Every node must have a 'type' field",
                node_label=node_label,
                json_path=f"{json_path_prefix}.type"
            ))
            return errors

        if node_type not in self.VALID_NODE_TYPES:
            valid_types_str = ', '.join(sorted(self.VALID_NODE_TYPES))
            errors.append(FlowValidationError(
                node_id=node_id,
                message=f"Invalid node type '{node_type}'. Must be one of: {valid_types_str}",
                error_type="error",
                field="type",
                suggestion=f"Change the node type to one of the valid types: {valid_types_str}",
                node_label=node_label,
                json_path=f"{json_path_prefix}.type"
            ))
            return errors  # Return early since we can't validate parameters for unknown types

        # Validate based on node type
        if node_type == 'trigger':
            # Frontend sends triggerType, execution expects triggerType
            trigger_type = data.get('triggerType') or data.get('trigger_type')
            if not trigger_type:
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Trigger type is required. Please select a trigger type (Manual, Schedule, Application Event, etc.) from the trigger configuration.",
                    error_type="error",
                    field="triggerType",
                    suggestion="Click on the trigger node and select a trigger type from the dropdown menu."
                ))
            elif trigger_type == 'application_event' or trigger_type == 'event':
                if not data.get('appId'):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Application selection is required for application event triggers. Please select an application from the dropdown.",
                        error_type="error",
                        field="appId",
                        suggestion="In the trigger configuration, select an application from the 'Select Application' dropdown. Make sure you have applications subscribed."
                    ))
                if not data.get('eventId'):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Event selection is required. Please select an event from the chosen application.",
                        error_type="error",
                        field="eventId",
                        suggestion="After selecting an application, choose an event from the 'Select Event' dropdown. This determines when the flow will be triggered."
                    ))
            elif trigger_type == 'schedule':
                if not data.get('schedule'):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Schedule configuration is required. Please set up when this flow should run.",
                        error_type="error",
                        field="schedule",
                        suggestion="Configure the schedule by setting a cron expression (e.g., '0 9 * * *' for daily at 9 AM) or use the schedule builder in the trigger configuration."
                    ))
            elif trigger_type == 'manual':
                # Validate manual variables
                manual_vars = data.get('manualVariables', [])
                if manual_vars:
                    # Validate each manual variable
                    for var in manual_vars:
                        if not isinstance(var, dict):
                            errors.append(FlowValidationError(
                                node_id=node_id,
                                message="Manual variable must be a dictionary",
                                error_type="error",
                                field="manualVariables"
                            ))
                        elif 'name' not in var or 'dataType' not in var:
                            errors.append(FlowValidationError(
                                node_id=node_id,
                                message="Manual variable missing required fields (name, dataType)",
                                error_type="error",
                                field="manualVariables"
                            ))
                        else:
                            # Validate file type arguments
                            if var.get('dataType') == 'file':
                                file_errors = self._validate_file_argument(var, node_id)
                                errors.extend(file_errors)
            elif trigger_type == 'webhook':
                if not data.get('webhookPath'):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Webhook path is required. This defines the URL endpoint for this webhook.",
                        error_type="warning",
                        field="webhookPath",
                        suggestion="Enter a unique path for your webhook (e.g., 'customer-update' or 'payment-received'). This will be part of the webhook URL."
                    ))
        
        elif node_type == 'action':
            # CRITICAL: Frontend will show empty node without these fields
            app_id = data.get('appId')
            service_id = data.get('serviceId')
            
            if not app_id:
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Application ID (appId) is required for action nodes. Without it, the node will appear empty in the frontend.",
                    error_type="error",
                    field="appId",
                    suggestion="Click on the action node and select an application from the 'Select Application' dropdown. Only subscribed applications are available."
                ))
            else:
                # Validate application exists
                if not self._validate_application_exists(app_id):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message=f"Application with ID '{app_id}' does not exist in the system",
                        error_type="error",
                        field="appId",
                        suggestion="Select a valid application from the available list. The application may have been deleted or is not accessible."
                    ))
                # Validate subscription exists
                elif not self._validate_subscription_exists(app_id):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message=f"No active subscription found for application '{app_id}'",
                        error_type="error",
                        field="appId",
                        suggestion="Subscribe to the application before using it in flows. Go to Applications > Subscribe to add it."
                    ))
            
            if not service_id:
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Service ID (serviceId) is required for action nodes. Without it, the node will appear empty in the frontend.",
                    error_type="error",
                    field="serviceId",
                    suggestion="After selecting an application, choose a service from the 'Select Service' dropdown."
                ))
            elif app_id:
                # Validate service exists for this application
                if not self._validate_service_exists(app_id, service_id):
                    # Check if this might be a service_name instead of service_id
                    actual_service_id = self._find_service_by_name(app_id, service_id)
                    
                    if actual_service_id:
                        # User provided service_name instead of service_id
                        errors.append(FlowValidationError(
                            node_id=node_id,
                            message=f"Invalid serviceId: '{service_id}' appears to be a service name, not a service ID. Use the actual service ID: '{actual_service_id}'",
                            error_type="error",
                            field="serviceId",
                            suggestion=f"Replace serviceId: '{service_id}' with serviceId: '{actual_service_id}'. Flow execution requires the UUID service_id, not the service_name."
                        ))
                    else:
                        # Service doesn't exist at all
                        errors.append(FlowValidationError(
                            node_id=node_id,
                            message=f"Service with ID '{service_id}' does not exist for application '{app_id}'",
                            error_type="error",
                            field="serviceId",
                            suggestion="Select a valid service from the application's available services. The service may have been removed or deactivated."
                        ))
                else:
                    # Get service schema for enhanced validation
                    service_schema = self._get_service_schema(app_id, service_id)
                    
                    # Use the enhanced validate_action_parameters method
                    param_errors, param_warnings = self.validate_action_parameters(node_id, data, service_schema)
                    
                    # Convert errors to FlowValidationError objects
                    for error_msg in param_errors:
                        errors.append(FlowValidationError(
                            node_id=node_id,
                            message=error_msg,
                            error_type="error",
                            field="parameterMapping"
                        ))
                    
                    for warning_msg in param_warnings:
                        errors.append(FlowValidationError(
                            node_id=node_id,
                            message=warning_msg,
                            error_type="warning",
                            field="parameterMapping"
                        ))
                    
                    # Also check for deprecated parameter usage
                    if data.get('parameters') and not data.get('parameterMapping'):
                        errors.append(FlowValidationError(
                            node_id=node_id,
                            message="Using deprecated 'parameters' field. Must use 'parameterMapping' for all action nodes",
                            error_type="error",
                            field="parameters",
                            suggestion="Move all parameters from 'parameters' to 'parameterMapping' field"
                        ))
            
            # Additional validation for proper rendering
            if not data.get('appName') and app_id:
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Application name (appName) should be set for better UI display",
                    error_type="warning",
                    field="appName",
                    suggestion="Set the appName field to display the application name in the UI"
                ))
            if not data.get('serviceDisplayName') and service_id:
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Service display name (serviceDisplayName) should be set for better UI display",
                    error_type="warning",
                    field="serviceDisplayName",
                    suggestion="Set the serviceDisplayName field to display the service name in the UI"
                ))
        
        elif node_type == 'condition':
            if not data.get('expression'):
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Condition expression is required",
                    error_type="error"
                ))
        
        elif node_type == 'transform':
            if not data.get('script'):
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Transform script is required",
                    error_type="warning",
                    node_label=node_label,
                    field="script",
                    json_path=f"{json_path_prefix}.data.script"
                ))

            # Validate external functions if specified
            functions_used = data.get('functions_used', [])
            if functions_used and functions:
                from .transform_function_manager import TransformFunctionManager

                for func_name in functions_used:
                    if func_name not in functions:
                        errors.append(FlowValidationError(
                            node_id=node_id,
                            message=f"Function '{func_name}' is referenced but not provided",
                            error_type="error",
                            field="functions_used"
                        ))
                    else:
                        # Validate function syntax
                        is_valid, error_msg = TransformFunctionManager.validate_function(
                            func_name, functions[func_name]
                        )
                        if not is_valid:
                            errors.append(FlowValidationError(
                                node_id=node_id,
                                message=error_msg,
                                error_type="error",
                                field="functions"
                            ))
            elif functions_used and not functions:
                # Skip individual error since we have comprehensive error above
                # The comprehensive error lists ALL missing functions
                pass
        
        elif node_type == 'loop':
            # Execution engine (execution_engine.py line ~1830) expects:
            # - loopType: 'forEach' | 'while' | 'for'
            # - For forEach: arrayPath, iteratorName (optional, defaults to 'item')
            # - For while: condition
            # - For for: startValue/start, endValue/end, stepValue/step (optional)
            
            loop_type = data.get('loopType')
                
            if not loop_type:
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Loop type is required. Please select how you want to iterate.",
                    error_type="error",
                    field="loopType",
                    suggestion="Click on the loop node and select a loop type: 'For Each' (iterate over array), 'While' (condition-based), or 'For' (numeric range)."
                ))
            elif loop_type == 'forEach':
                # Execution engine looks for arrayPath (line 1882 in execution_engine.py)
                array_path = data.get('arrayPath') or data.get('dataSource')
                if not array_path:
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Array to iterate is required. Specify which array or list to loop through.",
                        error_type="error",
                        field="arrayPath",
                        suggestion="In the loop configuration, set 'Array to Iterate' to a variable containing an array (e.g., 'input.items' or 'node_1.result'). Use the variable selector to choose from available arrays."
                    ))
                # iteratorName is optional, defaults to 'item' (line 1883)
                
            elif loop_type == 'while':
                # Execution engine looks for 'condition' field
                condition = data.get('condition') or data.get('whileCondition')
                if not condition:
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Loop condition is required. Define when the loop should continue.",
                        error_type="error",
                        field="condition",
                        suggestion="Set a condition that evaluates to true/false (e.g., 'counter < 10' or 'status != \"complete\"'). The loop continues while the condition is true."
                    ))
                    
            elif loop_type == 'for':
                # Execution engine looks for: startValue/start, endValue/end, stepValue/step
                start = data.get('startValue') or data.get('start') or data.get('forStart')
                end = data.get('endValue') or data.get('end') or data.get('forEnd')
                # step is optional, defaults to 1
                
                if start is None and start != 0:  # Allow 0 as valid start
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Start value is required for numeric loop. Set where to begin counting.",
                        error_type="error",
                        field="startValue",
                        suggestion="Enter the starting number for the loop (e.g., '0' or '1'). This can be a number or a variable reference."
                    ))
                if end is None:
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="End value is required for numeric loop. Set where to stop counting.",
                        error_type="error",
                        field="endValue",
                        suggestion="Enter the ending number for the loop (e.g., '10' or 'input.count'). The loop runs while the counter is less than this value."
                    ))
                # stepValue/step is optional, defaults to 1
        
        elif node_type == 'response':
            # Response nodes don't have mandatory fields but check for basic structure
            if data.get('statusCode'):
                status_code = data.get('statusCode')
                try:
                    status_int = int(status_code)
                    if status_int < 100 or status_int > 599:
                        errors.append(FlowValidationError(
                            node_id=node_id,
                            message="Invalid HTTP status code",
                            error_type="warning"
                        ))
                except (ValueError, TypeError):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Status code must be a valid HTTP status code",
                        error_type="warning"
                    ))

        elif node_type == 'wait_for_event':
            if not data.get('appId'):
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Application is required for Wait for Event nodes.",
                    error_type="error",
                    field="appId",
                    suggestion="Select an application from the Application & Event selector.",
                    node_label=node_label,
                ))
            if not data.get('eventName') and not data.get('eventId'):
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message="Event is required for Wait for Event nodes.",
                    error_type="error",
                    field="eventName",
                    suggestion="Select an event from the Application & Event selector.",
                    node_label=node_label,
                ))
            # Correlation config validation when match mode is correlation
            match_mode = data.get('matchMode', 'token')
            if match_mode == 'correlation':
                corr = data.get('correlationConfig', {})
                if not corr.get('eventField'):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Event Field is required when using Correlation match mode.",
                        error_type="error",
                        field="correlationConfig.eventField",
                        suggestion="Specify the field path in the incoming event data (e.g., order_id).",
                        node_label=node_label,
                    ))
                if not corr.get('flowField'):
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message="Flow Value is required when using Correlation match mode.",
                        error_type="error",
                        field="correlationConfig.flowField",
                        suggestion="Specify the flow variable to match against (e.g., {{node_outputs.trigger.order_id}}).",
                        node_label=node_label,
                    ))

        return errors
    
    def _find_disconnected_nodes(self, nodes: List[Dict], adjacency: Dict[str, List[str]], 
                                 reverse_adjacency: Dict[str, List[str]]) -> List[Tuple[str, str]]:
        """Find nodes that are not connected to any other nodes"""
        disconnected = []
        for node in nodes:
            node_id = node['id']
            node_label = node.get('data', {}).get('label', node_id)
            
            # Check if node has any connections
            has_outgoing = node_id in adjacency and len(adjacency[node_id]) > 0
            has_incoming = node_id in reverse_adjacency and len(reverse_adjacency[node_id]) > 0
            
            # Trigger nodes don't need incoming connections
            if node.get('type') == 'trigger':
                if not has_outgoing:
                    disconnected.append((node_id, node_label))
            # Response nodes don't need outgoing connections  
            elif node.get('type') == 'response':
                if not has_incoming:
                    disconnected.append((node_id, node_label))
            # Other nodes should have both
            else:
                if not has_incoming or not has_outgoing:
                    disconnected.append((node_id, node_label))
        
        return disconnected
    
    def validate_synchronous_flow(self, flow_definition: Any) -> Tuple[bool, List[FlowValidationError]]:
        """
        Validate a synchronous flow.
        Returns (is_valid, errors)
        """
        errors = []
        
        # First, validate JSON structure
        is_valid_json, parsed_data, json_error = self._validate_json_structure(flow_definition)
        if not is_valid_json:
            errors.append(FlowValidationError(
                node_id="flow",
                message=f"Invalid flow data: {json_error}",
                error_type="error",
                field="flow_definition"
            ))
            return False, errors
        
        # Use the parsed data for further validation
        flow_definition = parsed_data
        
        # Check for required fields
        if 'nodes' not in flow_definition or 'edges' not in flow_definition:
            errors.append(FlowValidationError(
                node_id="flow",
                message="Flow definition must contain 'nodes' and 'edges' fields",
                error_type="error",
                field="flow_definition"
            ))
            return False, errors
        
        nodes = flow_definition.get('nodes', [])
        edges = flow_definition.get('edges', [])
        
        # Validate that nodes and edges are lists
        if not isinstance(nodes, list) or not isinstance(edges, list):
            errors.append(FlowValidationError(
                node_id="flow",
                message="'nodes' and 'edges' must be arrays",
                error_type="error",
                field="flow_definition"
            ))
            return False, errors
        
        # Build adjacency list
        adjacency = self._build_adjacency_list(edges)
        reverse_adjacency = self._build_reverse_adjacency_list(edges)
        
        # Check 1: Must have exactly one response node
        response_nodes = [n for n in nodes if n.get('type') == 'response']
        if len(response_nodes) == 0:
            errors.append(FlowValidationError(
                node_id="flow",
                message="Synchronous flow must have a response node",
                error_type="error"
            ))
        elif len(response_nodes) > 1:
            errors.append(FlowValidationError(
                node_id="flow",
                message="Flow can only have one response node",
                error_type="error"
            ))
        
        # Check 2: Response node should not have outgoing edges
        if response_nodes:
            response_node_id = response_nodes[0]['id']
            if response_node_id in adjacency and adjacency[response_node_id]:
                errors.append(FlowValidationError(
                    node_id=response_node_id,
                    message="Response node cannot have outgoing connections",
                    error_type="error"
                ))
        
        # Check 3: Find hanging nodes (nodes with no path to response)
        if response_nodes:
            response_node_id = response_nodes[0]['id']
            hanging_nodes = self._find_hanging_nodes(nodes, reverse_adjacency, response_node_id)
            
            for node_id, node_label in hanging_nodes:
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message=f"Node '{node_label}' has no path to response node",
                    error_type="error"
                ))
        
        # Check 4: Check for loops that don't reach response
        if response_nodes:
            response_node_id = response_nodes[0]['id']
            loop_nodes = self._find_infinite_loops(nodes, adjacency, response_node_id)
            
            for node_id, node_label in loop_nodes:
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message=f"Node '{node_label}' is part of a loop with no exit to response",
                    error_type="warning"
                ))
        
        is_valid = not any(e.error_type == "error" for e in errors)
        return is_valid, errors
    
    def _build_adjacency_list(self, edges: List[Dict]) -> Dict[str, List[str]]:
        """Build adjacency list from edges"""
        adjacency = {}
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if source not in adjacency:
                adjacency[source] = []
            adjacency[source].append(target)
        return adjacency
    
    def _build_reverse_adjacency_list(self, edges: List[Dict]) -> Dict[str, List[str]]:
        """Build reverse adjacency list (who points to each node)"""
        reverse_adjacency = {}
        for edge in edges:
            source = edge.get('source')
            target = edge.get('target')
            if target not in reverse_adjacency:
                reverse_adjacency[target] = []
            reverse_adjacency[target].append(source)
        return reverse_adjacency
    
    def _find_hanging_nodes(self, nodes: List[Dict], reverse_adjacency: Dict[str, List[str]], 
                           response_node_id: str) -> List[Tuple[str, str]]:
        """Find nodes that have no path to the response node"""
        # Use reverse BFS from response node to find all nodes that can reach it
        reachable_from_response = set()
        queue = [response_node_id]
        reachable_from_response.add(response_node_id)
        
        while queue:
            current = queue.pop(0)
            # Get nodes that point to current node
            predecessors = reverse_adjacency.get(current, [])
            for pred in predecessors:
                if pred not in reachable_from_response:
                    reachable_from_response.add(pred)
                    queue.append(pred)
        
        # Find nodes not reachable from response
        hanging_nodes = []
        for node in nodes:
            node_id = node['id']
            # Skip trigger nodes as they are entry points
            if node.get('type') == 'trigger':
                continue
            
            if node_id not in reachable_from_response:
                node_label = node.get('data', {}).get('label', node_id)
                hanging_nodes.append((node_id, node_label))
        
        return hanging_nodes
    
    def _find_infinite_loops(self, nodes: List[Dict], adjacency: Dict[str, List[str]], 
                            response_node_id: str) -> List[Tuple[str, str]]:
        """Find nodes that are part of loops with no exit to response"""
        # This is a simplified check - just warns about cycles
        visited = set()
        rec_stack = set()
        cycles = []
        
        def has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            
            for neighbor in adjacency.get(node_id, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    # Found a cycle
                    return True
            
            rec_stack.remove(node_id)
            return False
        
        # Check each node
        loop_nodes = []
        for node in nodes:
            node_id = node['id']
            if node_id not in visited:
                if has_cycle(node_id):
                    # This is a very simple check - in practice you'd want
                    # to verify the cycle doesn't have an exit to response
                    node_label = node.get('data', {}).get('label', node_id)
                    loop_nodes.append((node_id, node_label))
        
        return loop_nodes
    
    def _extract_variable_references(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract variable references from a string.
        Returns list of (variable_type, path) tuples.
        
        Recognizes patterns like:
        - {{node_outputs.node_id.field}}
        - {{input.field}}
        - {{variables.field}}
        - {{loop.field}}
        - {{trigger.field}}
        - node_outputs.node_id.field (in scripts)
        """
        references = []
        seen = set()  # Track unique references to avoid duplicates
        
        # Template-style references: {{prefix.path}}
        template_pattern = r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([^}]+?)\s*\}\}'
        matches = re.findall(template_pattern, text)
        for prefix, path in matches:
            ref_key = (prefix, path.strip())
            if ref_key not in seen:
                seen.add(ref_key)
                references.append(ref_key)
        
        # Direct references in scripts: prefix.path
        # Only match at word boundaries to avoid false positives
        # Exclude common Python dictionary methods like .get(), .keys(), .values(), etc.
        direct_patterns = [
            (r'\bnode_outputs\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)', 'node_outputs'),
            (r'\binput\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)', 'input'),
            (r'\bvariables\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)', 'variables'),
            (r'\bloop\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)', 'loop'),
            (r'\btrigger\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)', 'trigger'),
            (r'\bglobal_vars\.([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)', 'global_vars'),
        ]
        
        # Common Python dictionary/object methods to exclude
        python_methods = {
            'get', 'keys', 'values', 'items', 'pop', 'update', 'clear', 'copy',
            'setdefault', 'popitem', 'fromkeys', 'append', 'extend', 'insert',
            'remove', 'index', 'count', 'sort', 'reverse', 'join', 'split',
            'strip', 'replace', 'lower', 'upper', 'startswith', 'endswith',
            'find', 'format', 'encode', 'decode'
        }
        
        for pattern, prefix in direct_patterns:
            matches = re.findall(pattern, text)
            for path in matches:
                # Skip if the path starts with a Python method
                first_part = path.split('.')[0]
                if first_part in python_methods:
                    continue
                    
                ref_key = (prefix, path)
                if ref_key not in seen:
                    seen.add(ref_key)
                    references.append(ref_key)
        
        # Dictionary-style access: prefix['field'] or prefix["field"]
        dict_patterns = [
            (r'\bnode_outputs\[[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]\]', 'node_outputs'),
            (r'\binput\[[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]\]', 'input'),
            (r'\bvariables\[[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]\]', 'variables'),
            (r'\bloop\[[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]\]', 'loop'),
            (r'\btrigger\[[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]\]', 'trigger'),
        ]
        
        for pattern, prefix in dict_patterns:
            matches = re.findall(pattern, text)
            for field in matches:
                ref_key = (prefix, field)
                if ref_key not in seen:
                    seen.add(ref_key)
                    references.append(ref_key)
        
        return references
    
    def _validate_references(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]] = None) -> List[FlowValidationError]:
        """
        Validate that all variable and node references are correct.
        """
        errors = []

        # Store edges in instance for _is_inside_loop to use
        self._current_edges = edges

        # Build a map of valid node IDs and their labels
        node_map = {}
        for node in nodes:
            node_id = node.get('id')
            node_label = node.get('data', {}).get('label', node_id)
            node_map[node_id] = node_label
        
        # Check each node for variable references
        for node in nodes:
            node_id = node.get('id')
            node_type = node.get('type')
            node_data = node.get('data', {})
            node_label = node_data.get('label', node_id)
            
            # Collect all text that might contain references
            texts_to_check = []
            
            if node_type == 'action':
                # Check parameter mappings
                param_mapping = node_data.get('parameterMapping', {})
                for param_name, param_value in param_mapping.items():
                    if isinstance(param_value, dict):
                        # New format with source/value
                        if param_value.get('source') == 'variable':
                            value = param_value.get('value', '')
                            if value:
                                texts_to_check.append((value, f"parameter '{param_name}'"))
                    elif isinstance(param_value, str):
                        texts_to_check.append((param_value, f"parameter '{param_name}'"))
                
                # Also check old-style parameters
                parameters = node_data.get('parameters', {})
                for param_name, param_value in parameters.items():
                    if isinstance(param_value, str):
                        texts_to_check.append((param_value, f"parameter '{param_name}'"))
            
            elif node_type == 'condition':
                expression = node_data.get('expression', '')
                if expression:
                    texts_to_check.append((expression, 'condition expression'))
            
            elif node_type == 'transform':
                script = node_data.get('script', '') or node_data.get('code', '')
                if script:
                    texts_to_check.append((script, 'transform script'))
            
            elif node_type == 'response':
                # Check the response variable reference
                variable = node_data.get('variable', '')
                if variable:
                    texts_to_check.append((variable, 'response variable'))
                
                # Check headers if they contain variable references
                headers = node_data.get('headers', {})
                for header_name, header_value in headers.items():
                    if isinstance(header_value, str):
                        texts_to_check.append((header_value, f"header '{header_name}'"))
            
            elif node_type == 'loop':
                # Check loop configuration
                loop_type = node_data.get('loopType')
                if loop_type == 'forEach':
                    array_path = node_data.get('arrayPath') or node_data.get('dataSource')
                    if array_path:
                        texts_to_check.append((array_path, 'array path'))
                elif loop_type == 'while':
                    condition = node_data.get('condition') or node_data.get('whileCondition')
                    if condition:
                        texts_to_check.append((condition, 'loop condition'))
                elif loop_type == 'for':
                    # Check numeric loop values
                    for field in ['startValue', 'start', 'forStart', 'endValue', 'end', 'forEnd', 'stepValue', 'step']:
                        value = node_data.get(field)
                        if isinstance(value, str) and value:
                            texts_to_check.append((value, f"loop {field}"))
            
            # Validate all collected texts
            for text, context in texts_to_check:
                references = self._extract_variable_references(text)
                
                for prefix, path in references:
                    # Validate node_outputs references
                    if prefix == 'node_outputs':
                        # Extract the node ID from the path
                        parts = path.split('.')
                        if parts:
                            referenced_node_id = parts[0]
                            if referenced_node_id not in node_map:
                                # Try to find a similar node ID
                                similar = self._find_similar_node_id(referenced_node_id, list(node_map.keys()))
                                suggestion = f"Did you mean 'node_outputs.{similar}' instead?" if similar else "Check that the node ID exists and is spelled correctly."
                                
                                errors.append(FlowValidationError(
                                    node_id=node_id,
                                    message=f"Invalid node reference 'node_outputs.{referenced_node_id}' in {context}. Node '{referenced_node_id}' does not exist.",
                                    error_type="error",
                                    field=context,
                                    suggestion=suggestion
                                ))
                    
                    # Validate loop references (only valid inside loop nodes or their children)
                    elif prefix == 'loop':
                        # Check if this node is inside a loop
                        # This is a simplified check - in a real implementation, 
                        # you'd need to traverse the flow graph to determine if the node is inside a loop
                        if node_type != 'loop' and not self._is_inside_loop(node_id, nodes):
                            errors.append(FlowValidationError(
                                node_id=node_id,
                                message=f"Invalid loop reference '{prefix}.{path}' in {context}. Loop variables are only available inside loop nodes.",
                                error_type="error",
                                field=context,
                                suggestion="Remove the loop reference or place this node inside a loop."
                            ))
                    
                    # Validate trigger references
                    elif prefix == 'trigger':
                        # Trigger variables are available throughout the flow
                        # but warn if referencing fields that might not exist
                        if '.' in path:
                            field_path = path.split('.', 1)[1]
                            # Common trigger fields
                            common_fields = ['variables', 'data', 'headers', 'body', 'params', 'execution_id', 'trigger_type']
                            if not any(path.startswith(field) for field in common_fields):
                                errors.append(FlowValidationError(
                                    node_id=node_id,
                                    message=f"Suspicious trigger reference '{prefix}.{path}' in {context}. This field may not exist.",
                                    error_type="warning",
                                    field=context,
                                    suggestion="Common trigger fields are: trigger.variables, trigger.data, trigger.headers, trigger.body"
                                ))

        # Clear the stored edges
        self._current_edges = None

        return errors
    
    def _find_similar_node_id(self, target: str, node_ids: List[str]) -> Optional[str]:
        """
        Find a similar node ID using basic string similarity.
        Returns the most similar node ID if similarity is high enough.
        """
        if not node_ids:
            return None
        
        target_lower = target.lower()
        best_match = None
        best_score = 0
        
        for node_id in node_ids:
            node_lower = node_id.lower()
            
            # Check for exact match (case-insensitive)
            if target_lower == node_lower:
                return node_id
            
            # Check if one contains the other
            if target_lower in node_lower or node_lower in target_lower:
                score = len(target_lower) / max(len(target_lower), len(node_lower))
                if score > best_score:
                    best_score = score
                    best_match = node_id
            
            # Simple character overlap score
            common = sum(1 for c in target_lower if c in node_lower)
            score = common / max(len(target_lower), len(node_lower))
            if score > best_score:
                best_score = score
                best_match = node_id
        
        # Only return if similarity is high enough
        if best_score > 0.6:
            return best_match
        
        return None
    
    def _is_inside_loop(self, node_id: str, nodes: List[Dict[str, Any]]) -> bool:
        """
        Check if a node is inside a loop by traversing the flow graph.
        A node is inside a loop if it's reachable from a loop node's loop-body output
        and before any loop-back or continue edges.
        """
        # Get edges from the context if available, otherwise return False
        # This is a limitation - we need edges to properly determine loop boundaries
        # The proper fix would be to pass edges to this method
        edges = getattr(self, '_current_edges', None)
        if not edges:
            # Without edges, we can't determine loop boundaries properly
            # Return False to avoid false positives
            return False

        # Find all loop nodes
        loop_nodes = [n for n in nodes if n.get('type') == 'loop']

        for loop_node in loop_nodes:
            loop_node_id = loop_node['id']

            # Find nodes connected to the loop's loop-body output
            nodes_in_loop = set()
            nodes_to_check = []

            # Find the initial node connected to loop-body
            for edge in edges:
                if (edge.get('source') == loop_node_id and
                    edge.get('sourceHandle') == 'loop-body'):
                    nodes_to_check.append(edge.get('target'))
                    nodes_in_loop.add(edge.get('target'))

            # Traverse from loop-body nodes until we hit loop-back or continue
            visited = set()
            while nodes_to_check:
                current = nodes_to_check.pop(0)
                if current in visited:
                    continue
                visited.add(current)

                # Check if this is our target node
                if current == node_id:
                    return True

                # Find connected nodes
                for edge in edges:
                    if edge.get('source') == current:
                        target = edge.get('target')
                        target_handle = edge.get('targetHandle')

                        # Stop traversal if we hit loop-back (going back to loop)
                        if target == loop_node_id and target_handle == 'loop-back':
                            continue

                        # Stop traversal if we hit the continue output
                        # (this goes outside the loop)
                        if edge.get('sourceHandle') == 'continue':
                            continue

                        # Add to nodes to check if not visited
                        if target not in visited:
                            nodes_to_check.append(target)
                            nodes_in_loop.add(target)

        return False
    
    def detect_flow_format(self, flow_data: Dict[str, Any]) -> str:
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
    
    def validate_export_format(self, flow_json: Dict[str, Any]) -> Tuple[bool, List[FlowValidationError]]:
        """
        Validate flow in export/import format
        
        Args:
            flow_json: Complete flow JSON with version, flow, and metadata
            
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        # Check format
        format_type = self.detect_flow_format(flow_json)
        if format_type != "export":
            errors.append(FlowValidationError(
                node_id="flow",
                message="Flow is not in export format. Expected 'version' and 'flow' fields.",
                error_type="error",
                field="format"
            ))
            return False, errors
        
        # Extract flow definition
        flow = flow_json.get("flow", {})
        flow_def = flow.get("flow_definition", {})
        trigger_config = flow.get("trigger_config", {})
        
        # Validate flow definition
        is_valid, validation_errors = self.validate_flow_comprehensive(flow_def)
        errors.extend(validation_errors)
        
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
                    errors.append(FlowValidationError(
                        node_id="trigger",
                        message="trigger_config.manual_variables is empty - flow won't accept inputs",
                        error_type="error",
                        field="trigger_config.manual_variables"
                    ))
                if not node_manual_vars:
                    errors.append(FlowValidationError(
                        node_id="trigger",
                        message="trigger node manualVariables is empty - UI won't show input fields",
                        error_type="error",
                        field="manualVariables"
                    ))
                
                # Check synchronization
                if flow_manual_vars and node_manual_vars:
                    flow_var_names = {v.get("name") for v in flow_manual_vars}
                    node_var_names = {v.get("name") for v in node_manual_vars}
                    
                    # Check for mismatches
                    only_in_config = flow_var_names - node_var_names
                    only_in_node = node_var_names - flow_var_names
                    
                    if only_in_config:
                        errors.append(FlowValidationError(
                            node_id="trigger",
                            message=f"Variables in trigger_config but not in node: {only_in_config}",
                            error_type="error",
                            field="manual_variables"
                        ))
                    if only_in_node:
                        errors.append(FlowValidationError(
                            node_id="trigger",
                            message=f"Variables in node but not in trigger_config: {only_in_node}",
                            error_type="error",
                            field="manualVariables"
                        ))
                    
                    # Check outputs mapping
                    outputs = node_data.get("outputs", {})
                    for var_name in flow_var_names:
                        if var_name not in outputs:
                            errors.append(FlowValidationError(
                                node_id="trigger",
                                message=f"Variable '{var_name}' not mapped in trigger outputs",
                                error_type="warning",
                                field="outputs",
                                suggestion=f"Add '{var_name}' to trigger node outputs to map the input variable"
                            ))
        
        return len([e for e in errors if e.error_type == "error"]) == 0, errors
    
    def _validate_file_argument(self, variable: Dict[str, Any], node_id: str) -> List[FlowValidationError]:
        """
        Validate file type arguments in manual triggers
        
        Args:
            variable: The variable definition
            node_id: The node ID for error reporting
            
        Returns:
            List of validation errors
        """
        errors = []
        
        if variable.get('dataType') == 'file':
            validation = variable.get('validation', {})
            
            # Check accepted file types format
            accepted_types = validation.get('acceptedFileTypes')
            if accepted_types and not isinstance(accepted_types, str):
                errors.append(FlowValidationError(
                    node_id=node_id,
                    message=f"File variable '{variable.get('name')}' acceptedFileTypes must be a comma-separated string",
                    error_type="error",
                    field=f"manualVariables.{variable.get('name')}.validation.acceptedFileTypes"
                ))
            
            # Check max file size
            max_size = validation.get('maxFileSize')
            if max_size is not None:
                if not isinstance(max_size, (int, float)) or max_size <= 0:
                    errors.append(FlowValidationError(
                        node_id=node_id,
                        message=f"File variable '{variable.get('name')}' maxFileSize must be a positive number",
                        error_type="error",
                        field=f"manualVariables.{variable.get('name')}.validation.maxFileSize"
                    ))
        
        return errors
    
    def validate_action_parameters(self, node_id: str, node_data: Dict[str, Any], service_schema: Optional[Dict[str, Any]] = None) -> Tuple[List[str], List[str]]:
        """
        Validate action node parameters against service schema.
        This method is used by MCP server for parameter validation.
        
        Args:
            node_id: The node identifier
            node_data: The action node data
            service_schema: Optional service parameter schema
            
        Returns:
            Tuple of (errors, warnings) as string lists
        """
        errors = []
        warnings = []
        
        # Get parameter mapping
        parameter_mapping = node_data.get('parameterMapping', {})
        parameters = node_data.get('parameters', {})
        
        # Check if using deprecated parameters field
        if parameters:
            if not parameter_mapping:
                errors.append(f"Using deprecated 'parameters' field. Must use 'parameterMapping' instead")
            else:
                # Both fields present - this is an error
                errors.append(f"Both 'parameters' and 'parameterMapping' fields present. Use only 'parameterMapping'")
        
        # Detect incorrect nesting patterns and validate parameter names against schema
        if parameter_mapping and service_schema:
            schema_properties = service_schema.get('properties', {})
            
            # First, check if ANY of the top-level keys in parameterMapping are NOT in the schema
            # This catches cases where 'properties' or other invalid keys are used
            invalid_params = []
            for param_name in parameter_mapping.keys():
                if param_name not in schema_properties:
                    invalid_params.append(param_name)
            
            if invalid_params:
                # Provide detailed error message about which parameters are invalid
                valid_params = list(schema_properties.keys())
                errors.append(
                    f"Invalid parameter(s) in parameterMapping: {', '.join(invalid_params)}. "
                    f"Valid parameters for this service are: {', '.join(valid_params) if valid_params else 'none defined'}"
                )
                
                # Check for common incorrect nesting patterns to provide helpful guidance
                if 'properties' in invalid_params:
                    errors.append(
                        f"Incorrect nesting: 'properties' is not a valid parameter. "
                        f"Parameters should be placed directly in parameterMapping, not nested inside 'properties'."
                    )
                if 'body' in invalid_params and 'body' not in schema_properties:
                    errors.append(
                        f"Incorrect nesting: 'body' is not a valid parameter for this service. "
                        f"Parameters should be placed directly in parameterMapping."
                    )
        elif parameter_mapping and not service_schema:
            # If no schema available, still check for known incorrect patterns
            if 'properties' in parameter_mapping and isinstance(parameter_mapping['properties'], dict):
                errors.append(f"Incorrect parameter nesting detected: parameters should not be nested inside 'properties'. Place them directly in parameterMapping")
                
            if 'body' in parameter_mapping and isinstance(parameter_mapping['body'], dict):
                if 'properties' in parameter_mapping['body']:
                    errors.append(f"Incorrect parameter nesting detected: parameters should not be nested inside 'body.properties'. Place them directly in parameterMapping")
        
        # Extract actual parameters
        actual_params = {}
        if parameter_mapping:
            logger.info(f"RAW parameter_mapping received: {json.dumps(parameter_mapping, indent=2)}")
            for key, value in parameter_mapping.items():
                logger.info(f"Processing param {key}: type={type(value).__name__}, value={value}")
                # Handle nested structure with source and value
                if isinstance(value, dict):
                    logger.info(f"  Dict detected for {key}. Keys in dict: {list(value.keys())}")
                    # Check if it has 'source' and 'value' keys
                    if 'source' in value and 'value' in value:
                        # This is the new format with source type
                        extracted = value.get('value')
                        actual_params[key] = extracted
                        logger.info(f"  ✓ Extracted {key} from nested structure: {value} -> {extracted}")
                    elif 'value' in value:
                        # Old format with just value key
                        extracted = value.get('value')
                        actual_params[key] = extracted
                        logger.info(f"  ✓ Extracted {key} from value-only structure: {value} -> {extracted}")
                    else:
                        # Dict without source/value keys - this is likely the issue!
                        # This happens when the dict IS the value (e.g., for objects/arrays)
                        logger.warning(f"  ⚠️ Dict parameter {key} without source/value keys, using as-is: {value}")
                        actual_params[key] = value
                else:
                    # Direct value
                    actual_params[key] = value
                    logger.info(f"  Direct value for {key}: {value}")
        # Merge with old-style parameters (but this should generate an error above)
        # Only update if there's no parameterMapping (to avoid overwriting extracted values)
        if not parameter_mapping and parameters:
            actual_params.update(parameters)
            logger.info(f"Using deprecated parameters field")
        logger.info(f"Final actual_params for validation: {json.dumps(actual_params, indent=2, default=str)}")
        
        if service_schema:
            schema_properties = service_schema.get('properties', {})
            required_params = service_schema.get('required', [])
            
            # Check required parameters
            for required_param in required_params:
                if required_param not in actual_params:
                    errors.append(f"Missing required parameter '{required_param}'")
                elif actual_params[required_param] in [None, "", {}]:
                    errors.append(f"Required parameter '{required_param}' appears to be empty")
            
            # Check for unknown parameters (make this an error for strict validation)
            for param_name in actual_params:
                if param_name not in schema_properties:
                    # No special cases - all unknown parameters should be errors
                    # Get list of valid parameters for helpful error message
                    valid_params = list(schema_properties.keys())
                    errors.append(
                        f"Unknown parameter '{param_name}' not in service schema. "
                        f"Valid parameters are: {', '.join(valid_params) if valid_params else 'none defined'}. "
                        f"Check parameter name and case sensitivity."
                    )
                    
            # Validate parameter structure and types
            logger.debug(f"Validating actual_params types: {actual_params}")
            for param_name, param_value in actual_params.items():
                logger.debug(f"Checking param {param_name}: type={type(param_value).__name__}, value={param_value}")
                if param_name in schema_properties:
                    param_schema = schema_properties[param_name]
                    param_type = param_schema.get("type")
                    
                    # Check for variable references (both template {{...}} and direct references)
                    if isinstance(param_value, str):
                        # Check for template syntax
                        if "{{" in param_value:
                            # This is a template variable reference, skip deep type checking
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
                        
                    # Strict type validation (errors instead of warnings)
                    if param_type == "string" and not isinstance(param_value, str):
                        logger.error(f"Type validation failed for {param_name}: expected string, got {type(param_value).__name__}, value: {param_value}")
                        errors.append(f"Parameter '{param_name}' must be string type, got {type(param_value).__name__}")
                    elif param_type == "number" and not isinstance(param_value, (int, float)):
                        errors.append(f"Parameter '{param_name}' must be number type, got {type(param_value).__name__}")
                    elif param_type == "boolean" and not isinstance(param_value, bool):
                        errors.append(f"Parameter '{param_name}' must be boolean type, got {type(param_value).__name__}")
                    elif param_type == "array" and not isinstance(param_value, list):
                        errors.append(f"Parameter '{param_name}' must be array type, got {type(param_value).__name__}")
                    elif param_type == "object" and not isinstance(param_value, dict):
                        errors.append(f"Parameter '{param_name}' must be object type, got {type(param_value).__name__}")
                    
                    # Validate nested object structure if schema defines properties
                    if param_type == "object" and isinstance(param_value, dict):
                        nested_props = param_schema.get('properties', {})
                        if nested_props:
                            for nested_key, nested_value in param_value.items():
                                if nested_key not in nested_props:
                                    errors.append(f"Unknown nested parameter '{param_name}.{nested_key}' not in schema")
        else:
            # No schema available, still do strict checks
            if not parameter_mapping:
                errors.append(f"No parameterMapping defined for action node")
            if parameters:
                errors.append(f"Using deprecated 'parameters' field instead of 'parameterMapping'")
            
        return errors, warnings