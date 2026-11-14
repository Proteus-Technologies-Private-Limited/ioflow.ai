"""
Flow Design API - Provides validation, fixing, and generation of flow designs

This module provides REST API endpoints for flow design operations including:
- Validation of flow structures
- Auto-fixing common flow issues
- Generation from requirements
- Template provisioning
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import json
import logging

from db.database import get_db, get_tenant_db
from core.auth_utils import get_current_user_required as get_current_user
from core.config import settings
from services.flow_validator import FlowValidator
from api.applications import deserialize_json_field

# Import models - PostgreSQL Only
from db.models import User, Flow
from db.application_models import (
    Application, ApplicationSubscription,
    ApplicationService, ApplicationEvent
)

router = APIRouter(prefix="/api/v1/flow-design", tags=["flow-design"])
logger = logging.getLogger(__name__)


# Request/Response Models
class ManualVariable(BaseModel):
    id: str
    name: str
    displayName: str
    dataType: str = "string"
    uiControl: str = "text"
    required: bool = True
    defaultValue: Optional[Any] = None


class TriggerConfig(BaseModel):
    type: str = Field(..., description="Trigger type: manual, event, schedule, webhook, etc.")
    app_id: Optional[str] = None
    event_name: Optional[str] = None
    schedule: Optional[Dict[str, Any]] = None
    manual_variables: Optional[List[ManualVariable]] = None
    execute_immediately: Optional[bool] = None
    folder_path: Optional[str] = None
    listener_type: Optional[List[str]] = None
    file_pattern: Optional[str] = None
    recursive: Optional[bool] = None
    debounce_seconds: Optional[int] = None


class NodeData(BaseModel):
    label: str
    triggerType: Optional[str] = None
    manualVariables: Optional[List[ManualVariable]] = None
    appId: Optional[str] = None
    appName: Optional[str] = None
    serviceId: Optional[str] = None
    service: Optional[str] = None
    serviceDisplayName: Optional[str] = None
    parameterMapping: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None
    parametersRaw: Optional[str] = None  # JSON string of parameters
    script: Optional[str] = None
    functions_used: Optional[List[str]] = None  # List of external functions used by transform node
    variable: Optional[str] = None
    statusCode: Optional[int] = None
    width: Optional[float] = 200
    height: Optional[float] = 100
    # Reference fields for seed applications - use alias for underscore fields
    app_reference: Optional[str] = Field(None, alias="_app_reference")
    original_appId: Optional[str] = Field(None, alias="_original_appId")
    service_reference: Optional[str] = Field(None, alias="_service_reference")
    original_serviceId: Optional[str] = Field(None, alias="_original_serviceId")
    instance_number: Optional[int] = Field(None, alias="_instance_number")
    instance_name: Optional[str] = Field(None, alias="_instance_name")

    class Config:
        allow_population_by_field_name = True  # Allow both field name and alias


class FlowNode(BaseModel):
    id: Optional[str] = None  # Make ID optional for fix endpoint
    type: str  # trigger, action, transform, response, condition, parallel
    position: Dict[str, float]
    data: NodeData


class FlowEdge(BaseModel):
    id: Optional[str] = None  # Make ID optional for fix endpoint
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    label: Optional[str] = None


class FlowDefinition(BaseModel):
    nodes: List[FlowNode]
    edges: List[FlowEdge]


class FlowDesignRequest(BaseModel):
    flow_name: str
    description: Optional[str] = None
    category: Optional[str] = None
    flow_scope: Optional[str] = 'user'  # 'global', 'tenant', 'user'
    trigger_config: TriggerConfig
    flow_definition: FlowDefinition
    functions: Optional[Dict[str, str]] = None  # External Python functions - extracted from code block
    functions_base64: Optional[str] = None  # Base64-encoded Python code block with function definitions
    is_synchronous: bool = False
    sync_timeout: int = 30


class ValidationError(BaseModel):
    node_id: Optional[str] = None
    field: Optional[str] = None
    message: str
    severity: str = "error"  # error, warning, info


class ValidationResponse(BaseModel):
    valid: bool
    import_compatible: bool = False  # Whether the flow can be imported in UI
    structure_type: str = "unknown"  # export, direct, hybrid, or invalid
    errors: List[ValidationError]
    warnings: List[ValidationError]
    suggestions: List[str]


class FixFlowResponse(BaseModel):
    fixed_flow: Dict[str, Any]
    changes: List[str]
    validation: ValidationResponse


class FlowFromRequirementsRequest(BaseModel):
    requirements: str = Field(..., description="Natural language description of flow requirements")
    inputs: Optional[List[ManualVariable]] = Field(None, description="Input variables for the flow")
    application_hints: Optional[List[str]] = Field(None, description="Preferred applications to use")
    output_format: Optional[str] = Field("json", description="Expected output format")


class FlowExportFormat(BaseModel):
    """Model for export format validation"""
    version: str
    export_timestamp: str
    flow: FlowDesignRequest
    metadata: Optional[Dict[str, Any]] = None


def _check_action_node(db: Session, node: "FlowNode", user: User,
                       warnings: List["ValidationError"]) -> List["ValidationError"]:
    """The application, service and required parameters an action node names.

    Returns the errors; appends to ``warnings`` what will only matter at run
    time (the application is not connected for the caller's tenant yet — a
    flow may be designed before the connection is made).
    """
    from services.application_lookup import find_by_seed_key, visible_to

    errors: List[ValidationError] = []
    app_ref = node.data.appId
    label = node.data.appName or app_ref

    app = db.query(Application).filter(Application.app_id == app_ref).first()
    if app is not None and not visible_to(app, user):
        app = None
    if app is None:
        app = find_by_seed_key(db, app_ref, user)

    subscription = None
    if app is not None:
        subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app.app_id,
            ApplicationSubscription.tenant_id == user.tenant_id,
            ApplicationSubscription.status == "active"
        ).first()
    else:
        subscription = db.query(ApplicationSubscription).filter(
            ApplicationSubscription.app_id == app_ref,
            ApplicationSubscription.tenant_id == user.tenant_id,
            ApplicationSubscription.status == "active"
        ).first()
        if subscription is None:
            errors.append(ValidationError(
                node_id=node.id,
                field="appId",
                message=f"Application {label} not found or not subscribed",
                severity="error"
            ))
            return errors

    app_id = app.app_id if app is not None else app_ref

    if subscription is None and app is not None and app.app_name != "Debug":
        from db.application_models import PublishedApplication
        published = db.query(PublishedApplication).filter(
            PublishedApplication.app_id == app_id,
            PublishedApplication.status == "active"
        ).first()
        if published is None:
            warnings.append(ValidationError(
                node_id=node.id,
                field="appId",
                message=(f"Application {label} is not connected for your "
                         f"organization yet — the flow will fail when it runs "
                         f"until it is"),
                severity="warning"
            ))

    if not node.data.serviceId:
        return errors  # reported by the node structure check

    service = db.query(ApplicationService).filter(
        ApplicationService.app_id == app_id,
        ApplicationService.service_id == node.data.serviceId
    ).first()
    if service is None:
        errors.append(ValidationError(
            node_id=node.id,
            field="serviceId",
            message=(f"Service {node.data.service or node.data.serviceId} "
                     f"not found in application {label}"),
            severity="error"
        ))
        return errors

    # input_schema is JSONB (a dict) on PostgreSQL and a JSON string on
    # SQLite; json.loads on the dict raised and the check never ran.
    schema = deserialize_json_field(service.input_schema)
    required = schema.get("required", []) if isinstance(schema, dict) else []
    provided = set((node.data.parameters or {}).keys())
    provided.update((node.data.parameterMapping or {}).keys())
    missing = [p for p in required if p not in provided]
    if missing:
        errors.append(ValidationError(
            node_id=node.id,
            field="parameters",
            message=f"Missing required parameters: {', '.join(missing)}",
            severity="error"
        ))
    return errors


@router.post("/validate", response_model=ValidationResponse)
async def validate_flow_design(
    request: FlowDesignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate a flow design for correctness and completeness.

    Checks:
    - Export format wrapper requirement for import
    - Dual trigger configuration consistency (manual triggers)
    - Node structure validity
    - Edge connectivity
    - Variable references
    - Application/service availability
    """
    errors = []
    warnings = []
    suggestions = []

    # Handle base64-encoded functions if provided
    if request.functions_base64 and not request.functions:
        import base64
        from services.functions_parser import parse_python_functions_dict

        try:
            logger.info(f"Decoding functions_base64 of length: {len(request.functions_base64)}")
            # Decode the base64 string
            decoded = base64.b64decode(request.functions_base64).decode('utf-8')
            logger.info(f"Decoded functions string length: {len(decoded)}")
            logger.info(f"Decoded preview (first 500 chars): {decoded[:500]}...")
            logger.info(f"Decoded last 100 chars: ...{decoded[-100:]}")

            # Log format detection
            first_line = decoded.split('\n')[0].strip() if decoded else ""
            if first_line.startswith('def '):
                logger.info("Detected plain Python code block format (starts with 'def')")
            elif decoded.strip().startswith('{'):
                logger.info("Detected dictionary format (legacy)")

            # Debug: Check what format we actually received
            if decoded.strip().startswith('{'):
                # Try to identify the first key
                import re
                key_match = re.match(r'^[{\s]*["\']([^"\']+)["\']', decoded.strip())
                if key_match:
                    first_key = key_match.group(1)
                    logger.info(f"First key in decoded string appears to be: '{first_key}'")
                    if first_key == 'raw':
                        logger.warning("ISSUE: Functions dict has 'raw' as key instead of function name!")
                        logger.warning(f"Full decoded string for debugging: {decoded}")

            # Parse Python functions from the code block
            # The decoded string should be plain Python code with function definitions
            # The parser will only accept plain Python code blocks now
            functions_dict = parse_python_functions_dict(decoded)

            # Check if parser returned an error
            if '__error__' in functions_dict:
                error_message = functions_dict['__error__']
                logger.error(f"Parser rejected functions format: {error_message}")
                raise ValueError(error_message)

            if not functions_dict:
                # If parser returns empty, check what format we received
                logger.error(f"Parser returned empty dict.")
                if decoded.strip().startswith('{'):
                    logger.error("Received dictionary format but couldn't parse it")
                    logger.error(f"Full decoded string:\n{decoded}")
                    raise ValueError("Functions must be provided as plain Python code block, not as dictionary or JSON format")
                else:
                    logger.error(f"Could not extract functions from Python code block")
                    logger.error(f"First 200 chars: {decoded[:200]}")
                raise ValueError("No functions could be parsed from the provided Python code")

            request.functions = functions_dict
            logger.info(f"Successfully parsed {len(functions_dict)} functions: {list(functions_dict.keys())}")

            # Log first few lines of each function for debugging
            for func_name, func_code in functions_dict.items():
                lines = func_code.split('\n')
                logger.debug(f"Function '{func_name}': {len(lines)} lines")
                if lines:
                    logger.debug(f"  First line: {lines[0]}")

        except base64.binascii.Error as e:
            logger.error(f"Failed to decode base64 functions: {e}")
            errors.append(ValidationError(
                message=f"Invalid base64 encoding for functions: {str(e)}",
                severity="error"
            ))
        except ValueError as e:
            logger.error(f"Failed to parse Python functions: {e}")
            errors.append(ValidationError(
                message=f"Could not parse Python functions: {str(e)}. Expected plain Python code with function definitions.",
                severity="error"
            ))
        except Exception as e:
            logger.error(f"Unexpected error processing functions: {e}", exc_info=True)
            errors.append(ValidationError(
                message=f"Failed to process functions: {str(e)}",
                severity="error"
            ))

    # Log if functions are provided
    if request.functions:
        logger.info(f"Validation request includes functions: {list(request.functions.keys())}")
    else:
        logger.info("Validation request has no functions parameter")
    
    try:
        # Collect all missing functions across all transform nodes
        all_missing_functions = set()
        nodes_with_missing_functions = []

        if not request.functions:
            for node in request.flow_definition.nodes:
                if node.type == "transform" and node.data.functions_used:
                    all_missing_functions.update(node.data.functions_used)
                    nodes_with_missing_functions.append(node.id)

        # If there are missing functions, add a comprehensive error at the top
        if all_missing_functions:
            functions_list = ", ".join(sorted(all_missing_functions))
            example_functions = list(all_missing_functions)[:2]

            comprehensive_error = (
                f"MISSING FUNCTIONS: Flow requires {len(all_missing_functions)} function(s): {functions_list}. "
                f"Nodes affected: {', '.join(nodes_with_missing_functions)}. "
                f"TO FIX: Create Python code with ALL these functions and retry validation:\n"
                f"```python\n"
                f"functions_code = '''"
            )

            for func in sorted(all_missing_functions):
                comprehensive_error += f"\ndef {func}(input):\n    # TODO: Implement {func}\n    return {{'result': 'processed'}}\n"

            comprehensive_error += (
                f"'''\n"
                f"# Then call: validate_flow_json(flow_json, functions=functions_code)\n"
                f"```"
            )

            errors.append(ValidationError(
                field="functions",
                message=comprehensive_error,
                severity="error"
            ))

        # 1. Validate trigger configuration consistency
        if request.trigger_config.type == "manual":
            trigger_node = next(
                (n for n in request.flow_definition.nodes if n.type == "trigger"),
                None
            )
            
            if not trigger_node:
                errors.append(ValidationError(
                    message="Manual trigger flow missing trigger node",
                    severity="error"
                ))
            else:
                # Check dual configuration
                ui_vars = trigger_node.data.manualVariables or []
                backend_vars = request.trigger_config.manual_variables or []
                
                ui_var_names = {v.name for v in ui_vars}
                backend_var_names = {v.name for v in backend_vars}
                
                if ui_var_names != backend_var_names:
                    missing_in_ui = backend_var_names - ui_var_names
                    missing_in_backend = ui_var_names - backend_var_names
                    
                    if missing_in_ui:
                        errors.append(ValidationError(
                            node_id=trigger_node.id,
                            field="manualVariables",
                            message=f"Variables missing in UI config: {', '.join(missing_in_ui)}",
                            severity="error"
                        ))
                    
                    if missing_in_backend:
                        errors.append(ValidationError(
                            field="trigger_config.manual_variables",
                            message=f"Variables missing in backend config: {', '.join(missing_in_backend)}",
                            severity="error"
                        ))
                
                # Check variable properties match
                for ui_var in ui_vars:
                    backend_var = next((v for v in backend_vars if v.name == ui_var.name), None)
                    if backend_var and ui_var.dataType != backend_var.dataType:
                        warnings.append(ValidationError(
                            node_id=trigger_node.id,
                            field=f"variable.{ui_var.name}",
                            message=f"Data type mismatch for {ui_var.name}: UI={ui_var.dataType}, Backend={backend_var.dataType}",
                            severity="warning"
                        ))
        
        # 2. Validate node structure
        node_ids = set()
        for node in request.flow_definition.nodes:
            if node.id in node_ids:
                errors.append(ValidationError(
                    node_id=node.id,
                    message=f"Duplicate node ID: {node.id}",
                    severity="error"
                ))
            node_ids.add(node.id)
            
            # Validate node type specific fields
            if node.type == "action":
                logger.info(f"Validating action node {node.id}: appId={node.data.appId}, serviceId={repr(node.data.serviceId)}, service={node.data.service}")

                if not node.data.appId:
                    errors.append(ValidationError(
                        node_id=node.id,
                        field="appId",
                        message="Action node missing application ID",
                        severity="error"
                    ))
                if not node.data.appName:
                    errors.append(ValidationError(
                        node_id=node.id,
                        field="appName",
                        message="Action node missing application name",
                        severity="error"
                    ))
                if not node.data.service and not node.data.serviceId:
                    logger.info(f"Action node {node.id}: Both service and serviceId are missing - adding service reference error")
                    errors.append(ValidationError(
                        node_id=node.id,
                        field="service",
                        message="Action node missing service reference",
                        severity="error"
                    ))
                if not node.data.serviceId:
                    logger.info(f"Action node {node.id}: serviceId is falsy (value={repr(node.data.serviceId)}) - adding serviceId error")
                    errors.append(ValidationError(
                        node_id=node.id,
                        field="serviceId",
                        message="Action node missing service ID",
                        severity="error"
                    ))
                else:
                    logger.info(f"Action node {node.id}: serviceId is truthy (value={repr(node.data.serviceId)}) - no error added")
                # Check for parametersRaw if parameters exist
                if node.data.parameters and not node.data.parametersRaw:
                    warnings.append(ValidationError(
                        node_id=node.id,
                        field="parametersRaw",
                        message="Action node has parameters but missing parametersRaw (JSON string)",
                        severity="warning"
                    ))
            
            elif node.type == "transform":
                if not node.data.script:
                    errors.append(ValidationError(
                        node_id=node.id,
                        field="script",
                        message="Transform node missing script",
                        severity="error"
                    ))

                # Validate external functions if specified
                if node.data.functions_used and request.functions:
                    from services.transform_function_manager import TransformFunctionManager

                    for func_name in node.data.functions_used:
                        if func_name not in request.functions:
                            errors.append(ValidationError(
                                node_id=node.id,
                                field="functions_used",
                                message=f"Function '{func_name}' is referenced but not provided in functions dictionary",
                                severity="error"
                            ))
                        else:
                            # Validate the function syntax
                            is_valid, error_msg = TransformFunctionManager.validate_function(
                                func_name, request.functions[func_name]
                            )
                            if not is_valid:
                                errors.append(ValidationError(
                                    node_id=node.id,
                                    field="functions",
                                    message=error_msg,
                                    severity="error"
                                ))

                # Check if functions are provided but not referenced
                # (Individual node error is now covered by comprehensive error above)
                elif node.data.functions_used and not request.functions:
                    # Skip individual errors since we have a comprehensive error above
                    pass
            
            elif node.type == "response":
                if not node.data.variable and not node.data.statusCode:
                    warnings.append(ValidationError(
                        node_id=node.id,
                        message="Response node has no variable or status code",
                        severity="warning"
                    ))
        
        # 3. Validate edges
        from services.flow_handles import edge_handle_errors
        node_types = {n.id: n.type for n in request.flow_definition.nodes if n.id}
        for edge in request.flow_definition.edges:
            for message in edge_handle_errors(edge.dict(), node_types):
                errors.append(ValidationError(
                    field=f"edge.{edge.id}",
                    message=message,
                    severity="error"
                ))
        for edge in request.flow_definition.edges:
            if edge.source not in node_ids:
                errors.append(ValidationError(
                    field=f"edge.{edge.id}",
                    message=f"Edge source '{edge.source}' not found in nodes",
                    severity="error"
                ))
            
            if edge.target not in node_ids:
                errors.append(ValidationError(
                    field=f"edge.{edge.id}",
                    message=f"Edge target '{edge.target}' not found in nodes",
                    severity="error"
                ))
        
        # 4. Check for orphaned nodes
        connected_nodes = set()
        for edge in request.flow_definition.edges:
            connected_nodes.add(edge.source)
            connected_nodes.add(edge.target)
        
        orphaned = node_ids - connected_nodes
        if orphaned and len(node_ids) > 1:  # Single node flows are ok
            for node_id in orphaned:
                warnings.append(ValidationError(
                    node_id=node_id,
                    message=f"Node '{node_id}' is not connected to any other node",
                    severity="warning"
                ))
        
        # 5. Validate variable references
        # This would require parsing all parameter values for {{variable}} patterns
        # and checking if they exist
        
        # 6. Check application availability and services.
        # Every action node is resolved to the application it names, and its
        # service and required parameters are checked against THAT
        # application. The service checks used to run only when the app was
        # reached through a subscription, so the usual case — an app found by
        # its id — passed with a wrong service or missing parameters and failed
        # only when the flow ran.
        action_nodes = [n for n in request.flow_definition.nodes if n.type == "action"]
        for node in action_nodes:
            if node.data.appId:
                errors.extend(_check_action_node(db, node, current_user, warnings))

        # Add suggestions
        if not errors:
            suggestions.append("Flow structure looks good!")
        
        if request.is_synchronous and not request.flow_definition.nodes:
            suggestions.append("Consider adding nodes to your synchronous flow")
        
    except Exception as e:
        logger.error(f"Error validating flow design: {str(e)}")
        errors.append(ValidationError(
            message=f"Validation error: {str(e)}",
            severity="error"
        ))
    
    return ValidationResponse(
        valid=len(errors) == 0,
        import_compatible=True,  # Standard format is always importable
        structure_type="standard",
        errors=errors,
        warnings=warnings,
        suggestions=suggestions
    )


class ValidateAndSaveRequest(BaseModel):
    """Request model for combined validate and save - accepts base64 encoded parameters"""
    flow_json: str  # Base64-encoded flow JSON in export format
    functions_base64: Optional[str] = None  # Base64-encoded Python functions
    # Re-saving a design under a name that already exists UPDATES that flow by
    # default. This endpoint is "save my flow design", not "import a file I was
    # sent": an agent or script re-running the same save means "this is the
    # current version", and creating a copy instead is invisible in the
    # response, so it silently leaves two flows on the same trigger. Pass False
    # to get the copy-under-a-suffixed-name behaviour of /flows/import.
    overwrite_existing: bool = True


@router.post("/validate-and-save", response_model=Dict[str, Any])
async def validate_and_save_flow(
    request: ValidateAndSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate and save a flow design in one operation.

    This endpoint accepts base64-encoded flow JSON and functions (same signature as old validate/save).
    It:
    1. Decodes the flow JSON
    2. Injects functions into transform nodes if provided
    3. Validates the flow
    4. If valid, imports/saves the flow
    5. If invalid, returns errors without saving

    Args:
        flow_json: Base64-encoded flow JSON in export format
        functions_base64: Optional base64-encoded Python functions to inject

    Returns:
        Combined validation and save result
    """
    import base64
    from services.transform_function_manager import TransformFunctionManager
    from services.functions_parser import parse_python_functions_dict
    from api.flows import import_flow

    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit designing or saving flows"
        )

    try:
        # Decode flow JSON from base64
        logger.info(f"Decoding flow JSON from base64, length: {len(request.flow_json)}")
        flow_json_str = base64.b64decode(request.flow_json).decode('utf-8')
        flow_data = json.loads(flow_json_str)

        # Extract flow name
        flow_name = flow_data.get('flow', {}).get('flow_name', 'Untitled Flow')

        # Inject functions if provided (same as save_flow_design did)
        if request.functions_base64:
            logger.info(f"Decoding and injecting functions from base64")
            functions_str = base64.b64decode(request.functions_base64).decode('utf-8')
            functions_dict = parse_python_functions_dict(functions_str)

            if functions_dict:
                logger.info(f"Parsed {len(functions_dict)} functions, injecting into flow")
                # Inject into flow definition (export format)
                if 'flow' in flow_data and 'flow_definition' in flow_data['flow']:
                    flow_data['flow']['flow_definition'] = TransformFunctionManager.inject_functions_into_flow(
                        flow_data['flow']['flow_definition'],
                        functions_dict
                    )
                    logger.info("Successfully injected functions into transform nodes")

        # Now validate the flow
        # Convert flow data to FlowDesignRequest format for validation
        flow_content = flow_data.get('flow', {})
        validation_request = FlowDesignRequest(
            flow_name=flow_content.get('flow_name', flow_name),
            description=flow_content.get('description', ''),
            category=flow_content.get('category', 'general'),
            trigger_config=flow_content.get('trigger_config', {}),
            flow_definition=flow_content.get('flow_definition', {}),
            is_synchronous=flow_content.get('is_synchronous', False),
            sync_timeout=flow_content.get('sync_timeout', 30)
        )

        # Validate using existing validation endpoint logic
        validation_response = await validate_flow_design(validation_request, current_user, db)

        logger.info(f"Validation complete: valid={validation_response.valid}, errors={len(validation_response.errors)}, warnings={len(validation_response.warnings)}")
        if validation_response.errors:
            logger.info(f"Validation errors: {[{'node': e.node_id, 'field': e.field, 'msg': e.message} for e in validation_response.errors]}")

        # Check if validation passed
        if not validation_response.valid:
            # Validation failed - return errors without saving
            logger.info(f"Validation failed for flow: {flow_name}")
            return {
                "success": False,
                "valid": False,
                "saved": False,
                "errors": [{"message": e.message, "node_id": e.node_id, "field": e.field} for e in validation_response.errors],
                "warnings": [{"message": w.message, "node_id": w.node_id} for w in validation_response.warnings],
                "suggestions": validation_response.suggestions,
                "message": "Flow validation failed - not saved"
            }

        # Validation passed - save the flow by calling import_flow
        logger.info(f"Validation passed, importing flow: {flow_name}")

        try:
            # Call import_flow with the flow data (already has functions injected)
            import_result = await import_flow(
                import_data=flow_data,
                current_user=current_user,
                db=db,
                overwrite_existing=request.overwrite_existing
            )

            # Check if import was successful
            if not import_result.get("flow_id"):
                # Import failed
                error_detail = import_result.get("detail", import_result)
                logger.error(f"Flow import failed: {error_detail}")
                return {
                    "success": False,
                    "valid": True,
                    "saved": False,
                    "error": str(error_detail),
                    "message": f"Validation passed but save failed: {error_detail}"
                }

            # Report what was actually PERSISTED, not what was requested.
            # These differ whenever the name collided, and echoing the
            # requested name made that undetectable: the caller was told its
            # flow saved under the name it chose while a differently-named
            # copy sat in the database.
            saved_name = import_result.get("flow_name") or flow_name
            was_updated = bool(import_result.get("updated"))
            was_renamed = bool(import_result.get("renamed")) or saved_name != flow_name
            logger.info(
                f"Flow validated and saved: requested={flow_name!r} "
                f"saved={saved_name!r} updated={was_updated} "
                f"ID={import_result.get('flow_id')}")
            return {
                "success": True,
                "valid": True,
                "saved": True,
                "flow_id": import_result.get("flow_id"),
                "flow_name": saved_name,
                "requested_flow_name": flow_name,
                "updated": was_updated,
                "renamed": was_renamed,
                "warnings": [{"message": w.message, "node_id": w.node_id} for w in validation_response.warnings],
                "message": ("Flow validated and updated successfully"
                            if was_updated else
                            "Flow validated and saved successfully"),
                "edit_link": f"/flow-designer?flowId={import_result.get('flow_id')}"
            }
        except HTTPException as he:
            # Service resolution or other import validation failed
            detail = he.detail if isinstance(he.detail, dict) else {"message": str(he.detail)}
            logger.error(f"Flow import validation failed: {detail.get('message', detail)}")
            return {
                "success": False,
                "valid": False,
                "saved": False,
                "errors": [detail],
                "message": detail.get("message", str(he.detail))
            }

    except Exception as e:
        logger.error(f"Error in validate_and_save_flow: {e}", exc_info=True)
        return {
            "success": False,
            "valid": False,
            "saved": False,
            "error": str(e),
            "message": f"Error validating/saving flow: {str(e)}"
        }

@router.post("/validate-json", response_model=ValidationResponse)
async def validate_raw_json(
    json_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate raw JSON flow data and check import compatibility.
    
    This endpoint accepts any JSON structure and:
    - Detects the structure type (export, direct, hybrid, invalid)
    - Validates if it can be imported in Flow Designer UI
    - Provides detailed suggestions for fixing structure issues
    - Performs standard flow validation if structure is valid
    """
    errors = []
    warnings = []
    suggestions = []
    import_compatible = False
    structure_type = "unknown"
    
    try:
        # Initialize validator
        validator = FlowValidator(db=db, tenant_id=current_user.tenant_id)
        
        # Check import structure
        import_compatible, structure_errors, structure_suggestions = validator.validate_import_structure(json_data)
        structure_type, structure_desc, _ = validator.detect_json_structure(json_data)
        
        # Add structure errors - all structure issues should be errors, not warnings
        for error in structure_errors:
            errors.append(ValidationError(
                node_id=error.node_id,
                field=error.field,
                message=error.message,
                severity="error"  # Always error for structure issues
            ))
        
        # Add structure suggestions
        suggestions.extend(structure_suggestions)
        
        # If structure is valid enough, extract flow data and validate
        flow_data = None
        flow_definition = None
        
        if structure_type == validator.STRUCTURE_EXPORT:
            # Extract from export format
            flow_data = json_data.get("flow", {})
            flow_definition = flow_data.get("flow_definition", {})
        elif structure_type == validator.STRUCTURE_DIRECT:
            # Direct format - nodes and edges at root
            flow_definition = json_data
        elif structure_type == validator.STRUCTURE_HYBRID:
            # Hybrid format - has flow_definition
            flow_definition = json_data.get("flow_definition", {})
            flow_data = json_data  # The whole thing is flow data
        
        # Validate flow definition if we have one
        if flow_definition and isinstance(flow_definition, dict):
            # Use the validator's comprehensive validation
            is_valid, validation_errors = validator.validate_flow_comprehensive(flow_definition)
            
            for error in validation_errors:
                if error.error_type == "error":
                    errors.append(ValidationError(
                        node_id=error.node_id,
                        field=error.field,
                        message=error.message,
                        severity="error"
                    ))
                else:
                    warnings.append(ValidationError(
                        node_id=error.node_id,
                        field=error.field,
                        message=error.message,
                        severity="warning"
                    ))
            
            # Additional validation for trigger config if present
            if flow_data and "trigger_config" in flow_data:
                trigger_config = flow_data["trigger_config"]
                if trigger_config.get("type") == "manual":
                    # Check dual configuration
                    trigger_node = next(
                        (n for n in flow_definition.get("nodes", []) 
                         if n.get("type") == "trigger"),
                        None
                    )
                    
                    if trigger_node:
                        node_data = trigger_node.get("data", {})
                        ui_vars = node_data.get("manualVariables", [])
                        backend_vars = trigger_config.get("manual_variables", [])
                        
                        if not ui_vars and not backend_vars:
                            errors.append(ValidationError(
                                message="Manual trigger has no variables defined",
                                severity="error"
                            ))
                        elif not ui_vars:
                            errors.append(ValidationError(
                                node_id=trigger_node.get("id"),
                                field="manualVariables",
                                message="Trigger node missing manual variables (UI won't show inputs)",
                                severity="error"
                            ))
                        elif not backend_vars:
                            errors.append(ValidationError(
                                field="trigger_config.manual_variables",
                                message="Trigger config missing manual variables (flow won't accept inputs)",
                                severity="error"
                            ))
        
        # Add final status based on results
        if not errors and import_compatible:
            suggestions.insert(0, "✅ Flow is valid")
        elif errors:
            suggestions.insert(0, "❌ Flow has validation errors")
            
    except Exception as e:
        logger.error(f"Error validating raw JSON: {str(e)}")
        errors.append(ValidationError(
            message=f"Validation error: {str(e)}",
            severity="error"
        ))
        structure_type = "invalid"
    
    return ValidationResponse(
        valid=len(errors) == 0,
        import_compatible=import_compatible,
        structure_type=structure_type,
        errors=errors,
        warnings=warnings,
        suggestions=suggestions
    )


@router.post("/fix", response_model=FixFlowResponse)
async def fix_flow_design(
    request: FlowDesignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Auto-fix common issues in flow design.
    
    Fixes:
    - Synchronize dual trigger configuration
    - Add missing node IDs
    - Fix invalid edge references
    - Add missing required fields
    - Normalize data types
    """
    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit designing flows"
        )

    fixed_flow = request.dict()
    changes = []
    
    try:
        # 1. Fix dual trigger configuration for manual triggers
        if fixed_flow["trigger_config"]["type"] == "manual":
            trigger_node = next(
                (n for n in fixed_flow["flow_definition"]["nodes"] if n["type"] == "trigger"),
                None
            )
            
            if trigger_node:
                # Synchronize variables between trigger_config and trigger node
                backend_vars = fixed_flow["trigger_config"].get("manual_variables", [])
                
                # Update trigger node with the same variables
                if not trigger_node.get("data"):
                    trigger_node["data"] = {}
                
                trigger_node["data"]["manualVariables"] = backend_vars
                trigger_node["data"]["triggerType"] = "manual"
                changes.append("Synchronized manual trigger variables")
                
                # Add outputs mapping if missing
                if backend_vars and "outputs" not in trigger_node["data"]:
                    trigger_node["data"]["outputs"] = {}
                    for var in backend_vars:
                        var_name = var["name"]
                        trigger_node["data"]["outputs"][var_name] = f"{{{{input.{var_name}}}}}"
                    changes.append("Added outputs mapping to trigger node")
        
        # 2. Add missing node IDs
        for i, node in enumerate(fixed_flow["flow_definition"]["nodes"]):
            if not node.get("id"):
                node_type = node.get("type", "node")
                node["id"] = f"{node_type}_{i+1}"
                changes.append(f"Added missing ID for {node_type} node")
        
        # 3. Add missing edge IDs
        for i, edge in enumerate(fixed_flow["flow_definition"]["edges"]):
            if not edge.get("id"):
                edge["id"] = f"edge_{i+1}"
                changes.append(f"Added missing ID for edge")
        
        # 4. Fix invalid edge references
        node_ids = {n["id"] for n in fixed_flow["flow_definition"]["nodes"]}
        edges_to_remove = []
        
        for edge in fixed_flow["flow_definition"]["edges"]:
            if edge["source"] not in node_ids or edge["target"] not in node_ids:
                edges_to_remove.append(edge)
        
        for edge in edges_to_remove:
            fixed_flow["flow_definition"]["edges"].remove(edge)
            changes.append(f"Removed invalid edge: {edge.get('id', 'unknown')}")
        
        # 5. Add default positions for nodes without positions
        default_y = 100
        for node in fixed_flow["flow_definition"]["nodes"]:
            if not node.get("position"):
                node["position"] = {"x": 250, "y": default_y}
                default_y += 150
                changes.append(f"Added default position for node {node['id']}")
        
        # 6. Add default data for nodes without data
        for node in fixed_flow["flow_definition"]["nodes"]:
            if not node.get("data"):
                node["data"] = {"label": node.get("type", "Node")}
                changes.append(f"Added default data for node {node['id']}")
        
        # Validate the fixed flow
        validation_request = FlowDesignRequest(**fixed_flow)
        validation_response = await validate_flow_design(validation_request, current_user, db)
        
    except Exception as e:
        logger.error(f"Error fixing flow design: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fix flow: {str(e)}"
        )
    
    return FixFlowResponse(
        fixed_flow=fixed_flow,
        changes=changes,
        validation=validation_response
    )


@router.get("/structure", response_model=Dict[str, Any])
async def get_flow_design_structure(
    current_user: User = Depends(get_current_user)
):
    """
    Get the flow design structure template in the proper export format.
    
    Returns a complete flow template that can be imported directly into Flow Designer.
    """
    from datetime import datetime
    
    # Return a proper export format template
    return {
        "version": "1.0",
        "export_timestamp": datetime.utcnow().isoformat(),
        "flow": {
            "flow_name": "Template Flow",
            "description": "Modify this template for your use case",
            "category": "general",
            "trigger_config": {
                "type": "manual",
                "manual_variables": [
                    {
                        "id": "input_data",
                        "name": "input_data",
                        "displayName": "Input Data",
                        "dataType": "string",
                        "uiControl": "text",
                        "required": True,
                        "defaultValue": "",
                        "description": "Simple string input"
                    },
                    {
                        "id": "contacts_example",
                        "name": "contacts_example",
                        "displayName": "Contact List (Array Example)",
                        "dataType": "array",
                        "uiControl": "json",
                        "required": False,
                        "defaultValue": "[{\"name\": \"John Doe\", \"email\": \"john@example.com\"}]",
                        "description": "Example of array with nested objects",
                        "itemType": "object",
                        "properties": [
                            {
                                "id": "name",
                                "name": "name",
                                "displayName": "Name",
                                "dataType": "string",
                                "required": True
                            },
                            {
                                "id": "email",
                                "name": "email",
                                "displayName": "Email",
                                "dataType": "string",
                                "required": False
                            }
                        ]
                    }
                ]
            },
            "flow_definition": {
                "nodes": [
                    {
                        "id": "trigger_1",
                        "type": "trigger",
                        "position": {"x": 250, "y": 100},
                        "data": {
                            "label": "Manual Trigger",
                            "triggerType": "manual",
                            "manualVariables": [
                                {
                                    "id": "input_data",
                                    "name": "input_data",
                                    "displayName": "Input Data",
                                    "dataType": "string",
                                    "uiControl": "text",
                                    "required": True,
                                    "description": "Simple string input"
                                },
                                {
                                    "id": "contacts_example",
                                    "name": "contacts_example",
                                    "displayName": "Contact List (Array Example)",
                                    "dataType": "array",
                                    "uiControl": "json",
                                    "required": False,
                                    "defaultValue": "[{\"name\": \"John Doe\", \"email\": \"john@example.com\"}]",
                                    "description": "Example of array with nested objects",
                                    "itemType": "object",
                                    "properties": [
                                        {
                                            "id": "name",
                                            "name": "name",
                                            "displayName": "Name",
                                            "dataType": "string",
                                            "required": True
                                        },
                                        {
                                            "id": "email",
                                            "name": "email",
                                            "displayName": "Email",
                                            "dataType": "string",
                                            "required": False
                                        }
                                    ]
                                }
                            ],
                            "outputs": {
                                "input_data": "{{input.input_data}}"
                            }
                        }
                    },
                    {
                        "id": "action_1",
                        "type": "action",
                        "position": {"x": 250, "y": 250},
                        "data": {
                            "label": "Process Data",
                            "appId": "app_id_here",
                            "appName": "Application Name",
                            "serviceId": "service_id_here",
                            "service": "service_name",
                            "serviceDisplayName": "Service Display Name",
                            "parameterMapping": {
                                "input": {
                                    "source": "variable",
                                    "value": "node_outputs.trigger_1.input_data"
                                }
                            }
                        }
                    },
                    {
                        "id": "response_1",
                        "type": "response",
                        "position": {"x": 250, "y": 400},
                        "data": {
                            "label": "Return Result",
                            "variable": "{{node_outputs.action_1}}",
                            "statusCode": 200
                        }
                    }
                ],
                "edges": [
                    {
                        "id": "edge_1",
                        "source": "trigger_1",
                        "target": "action_1"
                    },
                    {
                        "id": "edge_2",
                        "source": "action_1",
                        "target": "response_1"
                    }
                ]
            },
            "is_synchronous": False,
            "sync_timeout": 30
        },
        "metadata": {
            "required_applications": [],
            "source_instance": {
                "tenant_id": "",
                "user_email": ""
            },
            "warnings": []
        }
    }


@router.get("/guidelines", response_model=Dict[str, Any])
async def get_flow_design_guidelines(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive flow design guidelines with structure template and detailed explanations.
    
    This endpoint provides everything needed to understand and create flows in IOFlow,
    including the complete structure template, explanations for each field, examples,
    and best practices.
    """
    from datetime import datetime
    
    return {
        "json_format_guidance": {
            "title": "JSON Output Format for Flow Designers",
            "description": "AI models should output flow JSON in code blocks for better handling",
            "recommended_approach": {
                "instruction": "Output your flow JSON in a JSON code block with natural formatting",
                "format": "Use triple backticks with 'json' language identifier",
                "benefits": [
                    "No need to escape quotes or newlines within the code block",
                    "Transform scripts can use natural Python formatting",
                    "Validation tools automatically extract and process code blocks"
                ]
            },
            "code_block_example": {
                "description": "When outputting in a code block, use natural formatting:",
                "note": "Inside a JSON code block, strings can span multiple lines naturally"
            },
            "transform_scripts": {
                "key_point": "Transform scripts are Python code stored as strings in JSON",
                "in_code_blocks": "When JSON is in a code block, scripts can have literal newlines",
                "in_json_strings": "When JSON is a string, use \\n for newlines in scripts",
                "example_structure": {
                    "type": "transform",
                    "data": {
                        "label": "Process Data",
                        "script": "[Python code as a string - format depends on context]"
                    }
                },
                "best_practice": "Use JSON code blocks to avoid escaping complexity"
            }
        },
        "flow_name_requirement": {
            "CRITICAL": "flow_name is MANDATORY - save_flow_design() will FAIL without it",
            "instruction": "Generate a descriptive flow_name based on the user's request"
        },
        "structure_template": {
            "version": "1.0",
            "export_timestamp": datetime.utcnow().isoformat(),
            "flow": {
                "flow_name": "MUST_BE_REPLACED_WITH_DESCRIPTIVE_NAME",
                "description": "Modify this template for your use case",
                "category": "general",
                "trigger_config": {
                    "type": "manual",
                    "manual_variables": [
                        {
                            "id": "input_data",
                            "name": "input_data",
                            "displayName": "Input Data",
                            "dataType": "string",
                            "uiControl": "text",
                            "required": True,
                            "defaultValue": ""
                        }
                    ]
                },
                "flow_definition": {
                    "nodes": [
                        {
                            "id": "trigger_1",
                            "type": "trigger",
                            "position": {"x": 250, "y": 100},
                            "data": {
                                "label": "Manual Trigger",
                                "triggerType": "manual",
                                "manualVariables": [
                                    {
                                        "id": "input_data",
                                        "name": "input_data",
                                        "displayName": "Input Data",
                                        "dataType": "string",
                                        "uiControl": "text",
                                        "required": True
                                    }
                                ]
                            }
                        },
                        {
                            "id": "action_1",
                            "type": "action",
                            "position": {"x": 250, "y": 250},
                            "data": {
                                "label": "Process Data",
                                "appId": "app_id_here",
                                "appName": "Application Name",
                                "serviceId": "service_id_here",
                                "service": "service_name",
                                "serviceDisplayName": "Service Display Name",
                                "parameterMapping": {
                                    "input": {
                                        "source": "variable",
                                        "value": "node_outputs.trigger_1.input_data"
                                    }
                                }
                            }
                        },
                        {
                            "id": "response_1",
                            "type": "response",
                            "position": {"x": 250, "y": 400},
                            "data": {
                                "label": "Return Result",
                                "variable": "{{node_outputs.action_1}}",
                                "statusCode": 200
                            }
                        }
                    ],
                    "edges": [
                        {
                            "id": "edge_1",
                            "source": "trigger_1",
                            "target": "action_1"
                        },
                        {
                            "id": "edge_2",
                            "source": "action_1",
                            "target": "response_1"
                        }
                    ]
                },
                "is_synchronous": False,
                "sync_timeout": 30
            },
            "metadata": {
                "required_applications": [],
                "source_instance": {
                    "tenant_id": "",
                    "user_email": ""
                },
                "warnings": []
            }
        },
        "explanations": {
            "overview": """
Flow design in IOFlow follows a specific structure for import/export compatibility.
A flow consists of nodes (tasks) connected by edges (execution paths).

KEY CONCEPTS:
- Applications have BOTH services (actions you can call) AND events (triggers that start flows)
- Use get_application_services_list() to list services, get_service_information() for service details
- Use get_application_events_list() to list events, get_event_information() for event details
- Services are used in ACTION nodes, Events are used in TRIGGER nodes

Each flow must have exactly one trigger node and can have multiple action, transform,
condition, loop, and human_in_loop nodes. Synchronous flows must have exactly ONE response node - all
condition branches must converge to this single response node. Use transform nodes to
build conditional response data if different branches need different responses. Flows
terminate naturally when there are no more nodes to execute - there is no explicit
'end node' concept.
""",
            "applications_structure": """
UNDERSTANDING APPLICATIONS IN IOFLOW:

Applications are integrations that provide TWO types of functionality:

1. EVENTS (Used in Trigger Nodes):
   - Things that can START a flow (e.g., "record_created", "file_uploaded", "webhook_received")
   - Query with: get_application_events_list(app_id="app_name_or_id")
   - Get details with: get_event_information(app_key="app_key", event_name="event_name")
   - Events provide input variables to the flow

2. SERVICES (Used in Action Nodes):
   - Actions the flow can PERFORM (e.g., "create_record", "send_email", "update_data")
   - Query with: get_application_services_list(app_id="app_name_or_id")
   - Get details with: get_service_information(app_key="app_key", service_name="service_name")
   - Services require parameters that you map from flow variables

WORKFLOW FOR AGENTS:
1. First, list applications with list_applications()
2. For TRIGGER nodes: Use get_trigger_node_guide() MCP to get essential configuration for specific trigger type.
3. For EVENT type Triggers: Use get_application_events_list() then get_event_information()
4. For ACTION nodes: Use get_application_services_list() then get_service_information()
5. Never mix events and services - they serve different purposes!
""",
            "export_format": """
The export format is REQUIRED for importing flows. It wraps the flow definition with:
- version: Format version for compatibility
- export_timestamp: When the flow was exported
- flow: Contains all flow configuration
- metadata: Additional information about the flow

This format ensures flows can be shared and imported correctly between instances.
""",
            "nodes": {
                "trigger": """
Trigger nodes start the flow execution. Types include:
- manual: User-triggered with input variables
- schedule: Time-based execution (cron, interval, daily, weekly, monthly)
- webhook: HTTP request triggered
- file_change: When a file changes in a specific folder.
- event: Application event triggered

CRITICAL: ALL trigger types require configuration in TWO places:
1. flow.trigger_config - Backend execution (type-specific fields)
2. trigger node data - UI validation and display (type-specific fields)
Both configurations must match exactly or the flow won't work properly!

NESTED STRUCTURES:
Manual triggers and event outputs support complex nested data structures using:
- itemType: Specifies the type of elements in an array ("string", "number", "object", "array")
- properties: Defines the structure of object fields (array of property definitions)

Trigger variables are automatically accessible via {{trigger.variableName}} or {{input.variableName}} in subsequent nodes.
Access nested data: {{input.contacts_example[0].name}} or {{input.contacts_example[0].email}}
""",
                "action": """
Action nodes call SERVICES from connected applications (not events - events are for triggers!).
Configuration requires:
- appId: The application's UUID (get from list_applications)
- serviceId: The service's UUID (get from get_application_services_list - NOT events!)
- service: The service name (get from get_application_services_list)
- parameterMapping: Maps service parameters to flow variables
  Format: { "param_name": { "source": "variable", "value": "path.to.value" } }
  
IMPORTANT: 
- Use get_application_services_list() to list available services
- Use get_service_information() to get service parameter details
- Do NOT confuse with events (which are for triggers only)
""",
                "transform": """
Transform nodes execute Python scripts to process data:
- RestrictedPython environment with 5-second timeout
- MUST set 'output' variable with results
- Access trigger variables via 'input' dictionary
- Access node outputs via 'node_outputs' dictionary

SCRIPT FORMAT:
- The 'script' field contains Python code as a string
- In JSON code blocks: Use natural Python with real newlines
- In JSON strings: Use \\n for newlines
- The validation system handles both formats automatically

For complete details including:
- Available modules and libraries
- Variable access patterns
- File handling examples
- Debugging with print statements
Call the get_transform_node_guide() MCP tool or use GET /api/v1/flow-design/transform-guide
""",
                "condition": """
Condition nodes create branching logic based on expressions. Configuration:
- expression: JavaScript-like expression to evaluate (e.g., "input.value > 10")
- Two output branches: 'true' and 'false' based on evaluation
- Both branches are optional - flow can terminate on either path

For comprehensive condition node documentation including:
- Expression syntax and operators
- Variable access patterns
- Common patterns and examples
- Troubleshooting tips
Call the get_condition_node_guide() MCP tool or use GET /api/v1/flow-design/condition-guide
""",
                "loop": """
Loop nodes iterate over collections. Configuration:
- items: Array or variable reference to iterate over
- itemVariable: Name for current item in iteration
- body: Nodes to execute for each item
Loop context available in transform nodes via 'loop' variable.
""",
                "human_in_loop": """
Human-in-the-Loop (HITL) nodes pause flow execution and create a task for human review/approval.
When the execution engine reaches this node, it:
1. Pauses the flow execution (status = PAUSED)
2. Creates a HITL task assigned to specified users or roles
3. Notifies assigned users via WebSocket and email
4. Waits for a human to complete the task (review, edit, approve/reject)
5. After completion, the flow resumes with the human's response available as node output

Configuration:
- taskType: "review" (view only), "edit" (modify data), or "approve_reject" (approve or reject)
- title: Task title (supports {{variable}} templates)
- description: Instructions for the reviewer (optional, supports {{variable}} templates)
- priority: "low", "medium", "high", or "critical"
- assignmentConfig: Who should perform the task
  - type: "user" (assign to specific users) or "role" (assign to HITL role)
  - users: Array of user_id strings (when type="user")
  - roles: Array of hitl_role_id strings (when type="role")
- displayConfig: How to render the data for the reviewer
  - format: "form" (editable fields), "table", "json", or "text"
- inputDataMapping: Map flow context variables to data presented to the reviewer
  - Keys are field names, values are variable references like "{{node_outputs.transform_1.field}}"
  - If empty, all previous node outputs are included
- timeoutMinutes: Timeout in minutes (0 = no timeout)
- escalationConfig: What to do when timeout expires
  - on_timeout: "fail", "auto_approve", "auto_reject", or "escalate"
  - escalate_to: { "type": "user" or "hitl_role", "id": "uuid" }
  - max_escalations: Maximum escalation levels (default 3)
  - escalation_timeout_minutes: Timeout per escalation level

After completion, the HITL node output is available as:
- {{node_outputs.hitl_node_id.response_action}} - "approved", "rejected", "edited", or "reviewed"
- {{node_outputs.hitl_node_id.response_data}} - The human's response/edits (dict)
- {{node_outputs.hitl_node_id.input_data}} - The original data presented
- {{node_outputs.hitl_node_id.completed_by}} - User ID who completed the task
- {{node_outputs.hitl_node_id.task_type}} - The task type

Use a condition node after the HITL node to branch on response_action if needed:
  hitl_node → condition (node_outputs.hitl_1.response_action == "approved") → approved_path / rejected_path

Node JSON example:
{
  "id": "hitl_1",
  "type": "human_in_loop",
  "position": {"x": 400, "y": 200},
  "data": {
    "label": "Review Extracted Data",
    "taskType": "edit",
    "title": "Review and correct the extracted data",
    "description": "Please verify the data is correct and fix any errors.",
    "priority": "medium",
    "assignmentConfig": {"type": "role", "roles": ["role-uuid"]},
    "displayConfig": {"format": "form"},
    "inputDataMapping": {
      "name": "{{node_outputs.transform_1.name}}",
      "email": "{{node_outputs.transform_1.email}}"
    },
    "timeoutMinutes": 60,
    "escalationConfig": {"on_timeout": "escalate", "escalate_to": {"type": "user", "id": "user-uuid"}}
  }
}
""",
                "response": """
Response nodes return data from synchronous flows. Configuration:
- variable: MUST be a STRING containing either a variable reference or a fixed string value
  The variable field itself must be a string, but it can reference complex data structures.

  ✅ CORRECT Examples:
  - Variable reference: "{{node_outputs.some_node.result}}" (references any data type - object, array, string, etc.)
  - Variable reference: "{{node_outputs.transform_1.output}}" (can be complex nested JSON or array)
  - Fixed string value: "Success" or "Operation completed"
  - JSON string: "{\\"name\\": \\"{{input.name}}\\", \\"address\\": \\"{{input.address}}\\"}"

  ❌ WRONG Examples:
  - {"name": "{{input.name}}", "address": "{{input.address}}"} ← Object/dictionary will cause validation error
  - {"result": "data"} ← Direct object not allowed

  IMPORTANT: The 'variable' field must be a STRING, but the referenced data can be any type.
  Use a transform node if you need to construct complex response structures, then reference it.

- statusCode: HTTP status code (default 200)

Only used when flow is called as an API or GraphQL endpoint.

CRITICAL - SINGLE RESPONSE NODE RULE:
- Synchronous flows MUST have exactly ONE response node
- All condition branches MUST converge to this single response node
- DO NOT create separate response nodes for true/false branches

If different branches need different response data:
1. Use a transform node before the response to build conditional output
2. Store the result in a variable
3. Reference that variable in the single response node

Example pattern for conditional responses:
  condition_node
    → true branch → action_a → transform_build_response ─┐
                                                          ├→ response_node
    → false branch → action_b → transform_build_response ─┘

The transform node can set different output based on which path was taken.
"""
            },
            "variable_patterns": """
Variable references use double curly braces {{}} with these patterns:

CRITICAL: Understanding Variable Scopes
========================================
- 'input' namespace = ONLY trigger variables (read-only, available throughout entire flow)
- 'node_outputs' = Outputs from previously executed nodes (must specify node ID)
- 'loop' = Available ONLY inside loop body nodes
- 'global' = Available after being set via set_global() in transform nodes

Input Variables (ONLY from Trigger - Not from other nodes!):
- ALL trigger variables are accessed using {{input.variableName}}
- Manual trigger variables: {{input.user_input}}, {{input.file_upload}}
- event trigger variables: Event parameters like {{input.record_id}}, {{input.timestamp}}, {{input.data}}
- Webhook variables: {{input.webhook_payload}}, {{input.headers}}
- Schedule trigger variables: {{input.scheduled_time}}, {{input.cron_expression}}

Node Outputs (Must specify node ID):
- {{node_outputs.node_id.field_name}} - Access output from specific node
- {{node_outputs.api_1.data.items[0].name}} - Nested property access
- Available only from nodes that have already executed

Loop Variables:
- {{loop.item}} - Current loop item
- {{loop.index}} - Current iteration index
- Only accessible inside loop body nodes

Global Variables:
- {{global.variable_name}} - Flow-level global variables
- Must be set using set_global() in transform nodes first

Variable Access by Context:
- In parameter mapping: use without curly braces
  { "source": "variable", "value": "input.user_input" }
  { "source": "variable", "value": "node_outputs.api_call_1.data" }
- In transform nodes: use Python dict access (no curly braces)
  input.get('user_input')  # Gets trigger variable
  node_outputs['api_call_1']['data']  # Gets specific node output
- In conditions: use dot notation (no curly braces)
  input.user_input > 10
  node_outputs.api_call_1.status == "success"
""",
            "trigger_configuration": """
CRITICAL: Trigger configuration varies by type:

MANUAL TRIGGERS require DUAL configuration:
1. At flow level (flow.trigger_config.manual_variables):
   - Defines variables the backend expects
   - Used for flow execution and validation
   
2. At node level (trigger node data.manualVariables):
   - Defines variables shown in the UI
   - Used for the input form display

BOTH must be identical! Missing either causes failures.

EVENT TRIGGERS configuration:
For flow.trigger_config:
{
  "type": "event",
  "app_id": "app-uuid-here",
  "app_name": "app-name-here",  // Include for information
  "event_id": "event-uuid-here",
  "event_name": "record_created"
}

For trigger node data:
{
  "triggerType": "event",
  "app_id": "app-uuid-here",
  "app_name": "app-name-here",  // Same as other application nodes
  "event_id": "event-uuid-here",
  "event_name": "record_created",
  "outputs": {
    "record_id": "{{input.record_id}}",
    "timestamp": "{{input.timestamp}}",
    "data": "{{input.data}}"
  }
}

IMPORTANT: The outputs section must explicitly map event parameters based on get_event_information().
Event parameters do not automatically become available - they must be mapped in outputs.
""",
            "parameter_mapping": """
Action nodes use parameterMapping to connect service parameters to flow data:

Structure:
{
  "parameterMapping": {
    "param_name": {
      "source": "variable|static",
      "value": "path.to.value|literal_value"
    }
  }
}

Examples:
- Static value: { "source": "static", "value": "Hello World" }
- Variable: { "source": "variable", "value": "input.message" }
- Node output: { "source": "variable", "value": "node_outputs.api_1.result" }

Always validate required parameters with get_service_information()!
""",
            "common_patterns": """
Common flow patterns to follow:

1. API Chain: Trigger → API Call 1 → Transform → API Call 2 → Response
2. Data Processing: Trigger → Fetch Data → Loop → Transform → Store → Response
3. Conditional Logic: Trigger → Check Condition → (True: Action A | False: Action B)
4. Error Handling: Use transform nodes to check results and handle errors
5. File Processing: Trigger (file upload) → Transform (process) → Action (store)
6. Event-Driven: Event Trigger (e.g., record_created) → Transform → Action (e.g., send_notification)

EXAMPLE - Event-triggered flow:
- Trigger: Event from "CRM" app, event "lead_created" (maps input.lead_id, input.email in outputs)
- Action 1: Service from "Email" app, service "send_welcome_email" (uses input.email)
- Action 2: Service from "CRM" app, service "update_lead_status" (uses input.lead_id)

Remember: 
- Events START flows (triggers), Services PERFORM actions (action nodes)
- Event parameters must be explicitly mapped in the trigger node's outputs section
- Flows end naturally - no need for an explicit end node!
"""
        },
        "examples": {
            "file_upload_processing": {
                "description": "Process uploaded file (e.g., Excel to CSV)",
                "key_points": [
                    "File uploads create dictionary objects with metadata",
                    "Extract base64 data from the 'data' field",
                    "Use proper error handling for missing fields"
                ],
                "transform_script_example": """
# Example: Excel to CSV conversion
import pandas as pd
import base64
import io

# Get file upload dictionary
excel_file = input.get('excel_file', {})

# Extract base64 data from dictionary
if isinstance(excel_file, dict):
    excel_base64 = excel_file.get('data', '')
    filename = excel_file.get('name', 'unknown.xlsx')
else:
    # Handle case where it might be a string directly
    excel_base64 = excel_file
    filename = 'file.xlsx'

if excel_base64:
    # Decode and process
    excel_data = base64.b64decode(excel_base64)
    df = pd.read_excel(io.BytesIO(excel_data))
    csv_content = df.to_csv(index=False)
    
    output = {
        'csv_content': csv_content,
        'filename': filename.replace('.xlsx', '.csv'),
        'rows': len(df),
        'columns': len(df.columns)
    }
else:
    output = {'error': 'No file data found'}
"""
            },
            "simple_api_call": {
                "description": "Call an API and return the result",
                "key_points": [
                    "Single action node between trigger and response",
                    "Direct parameter mapping from input",
                    "Simple variable pass-through in response"
                ]
            },
            "data_transformation": {
                "description": "Fetch data, transform it, and send results",
                "key_points": [
                    "Action node to fetch data",
                    "Transform node to process results",
                    "Another action to send processed data",
                    "Chaining node outputs through the flow"
                ]
            },
            "conditional_logic": {
                "description": "Different actions based on input conditions",
                "key_points": [
                    "Condition node after trigger",
                    "Separate branches for true/false",
                    "Each branch can have different node chains",
                    "Branches can converge or end separately"
                ]
            },
            "application_event_trigger": {
                "description": "Complete flow with application event trigger",
                "key_points": [
                    "trigger_config at flow level with type: event",
                    "Event parameters must be explicitly mapped in outputs section"
                ],
                "complete_structure": {
                    "flow": {
                        "flow_name": "Process New Lead",
                        "trigger_config": {
                            "type": "event",
                            "app_id": "13112f81-971d-41bf-8ce2-7f89f8a52c5a",
                            "app_name": "proteus-vision-crm",
                            "event_id": "89e178cc-0fb2-46ce-8626-cc949f249578",
                            "event_name": "new_lead"
                        },
                        "flow_definition": {
                            "nodes": [
                                {
                                    "id": "trigger_new_lead",
                                    "type": "trigger",
                                    "data": {
                                        "label": "New Lead Event",
                                        "triggerType": "event",
                                        "appId": "13112f81-971d-41bf-8ce2-7f89f8a52c5a",
                                        "appName": "proteus-vision-crm",
                                        "eventId": "89e178cc-0fb2-46ce-8626-cc949f249578",
                                        "eventName": "new_lead",
                                        "eventDisplayName":"New Lead Created",
                                        "outputs": {
                                            "contact_name": "{{input.contact_name}}",
                                            "phone_no": "{{input.phone_no}}",
                                            "address": "{{input.address}}"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                },
                "important_notes": [
                    "Both trigger_config.type and node.triggerType use 'event' value",
                    "Note the way tag names such app id and event id specified in trigger_config and node are different. trigger_config is app_id and event_id where as node is appId and eventId ",
                    "Event parameters must be explicitly mapped in outputs section based on get_event_information()",
                    "Outputs section is required to make event parameters available as input variables"
                ]
            }
        },
        "best_practices": [
            "Always validate subscription status before using applications",
            "Call get_service_information() for each service to understand parameters",
            "Include both trigger_config and node manualVariables for manual triggers",
            "Use descriptive node IDs (e.g., 'fetch_user_data' not 'action_1')",
            "Validate flows before saving with validate_flow_json()",
            "Set meaningful labels for nodes to improve readability",
            "Handle errors with transform nodes when needed",
            "Test with small datasets before processing large volumes",
            "Use proper data types in manual variables (string, number, boolean, file, array, object)",
            "Configure response nodes for synchronous flows that need to return data",
            "Define itemType for arrays to specify element types",
            "Use properties array to define structure of nested objects",
            "Keep nested structures reasonable (max 3-4 levels) for maintainability"
        ],
        "common_mistakes": [
            "Missing trigger_config.manual_variables for manual triggers (flow won't accept inputs)",
            "Missing node data.manualVariables for manual triggers (UI won't show fields)",
            "Mismatch between trigger_config and node manual variables",
            "Incorrect variable reference syntax (missing {{}} or wrong path)",
            "Not setting 'output' variable in transform nodes",
            "Missing required parameters in action nodes",
            "Using disconnected nodes (no edges connecting them)",
            "Circular dependencies in node connections",
            "Not checking application subscription status",
            "Using wrong data types for service parameters",
            "Forgetting to map trigger outputs for manual variables",
            "Not mapping event parameters in outputs section for event triggers",
            "Not validating the flow before attempting import",
            "Trying to decode file upload directly without extracting 'data' field from dictionary",
            "Not handling file upload dictionary structure (name, type, size, data, lastModified)",
            "Missing itemType for arrays or properties for objects in nested structures",
            "Creating multiple response nodes for condition branches (synchronous flows must have exactly ONE response node - use transform nodes to build conditional response data)"
        ],
        "error_handling": {
            "title": "Node error handling (retry, continue, error branch)",
            "description": "Any node except the trigger may carry an 'errorHandling' block in its data. Without it, a node failure fails the whole execution.",
            "node_data_field": {
                "errorHandling": {
                    "onError": "stop | continue | error_branch",
                    "retry": {
                        "enabled": True,
                        "maxAttempts": 3,
                        "initialDelayMs": 1000,
                        "backoff": "exponential | fixed",
                        "maxDelayMs": 30000,
                        "jitter": True,
                        "retryOn": ["connection", "timeout", "rate_limit", "server"]
                    },
                    "continueOutput": {"items": []},
                    "failOnUnsuccessfulResponse": False
                }
            },
            "on_error_modes": {
                "stop": "Default. The failure fails the execution.",
                "continue": "The node outputs {success: false, error: {...}} merged with continueOutput, and its normal edges run. A failing condition takes its false branch; a failing loop runs its continue output.",
                "error_branch": "Only edges with sourceHandle 'error' leaving this node run; its normal edges are skipped. Error branches may rejoin the normal path (e.g. at the single response node of a synchronous flow)."
            },
            "error_edge_example": {"id": "e-call_api-notify-error", "source": "call_api", "target": "notify", "sourceHandle": "error", "targetHandle": "top"},
            "error_types": ["connection", "timeout", "rate_limit", "auth", "not_found", "validation", "client", "server", "unknown"],
            "retry_notes": [
                "maxAttempts counts the first try (1-10). retryOn defaults to transient types; use ['any'] to retry every error.",
                "Retry is ignored on loop, parallel, human_in_loop and wait_for_event nodes.",
                "Billing errors (insufficient balance) are never retried or handled."
            ],
            "error_variables": {
                "{{<node_id>.error.message}}": "Error message of that node's handled failure",
                "{{<node_id>.error.type}}": "Error type (see error_types)",
                "{{<node_id>.error.status_code}}": "HTTP status when known",
                "{{<node_id>.error.attempts}}": "Attempts made, including retries",
                "{{<node_id>.error.response}}": "Error response body when available",
                "{{error.message}}": "The most recent handled error (also the 'error' object inside transform scripts)"
            },
            "failOnUnsuccessfulResponse": "Action nodes only: treat a result with success: false as a failure.",
            "flow_level_error_handler": {
                "setting": "flow_definition.settings.error_handler_flow_id",
                "description": "Flow started when this flow fails with an unhandled error. It receives {{input.error.message}}, {{input.error.type}}, {{input.error.node_id}}, {{input.execution.execution_id}} and {{input.flow.flow_name}}."
            }
        },
        "validation_requirements": """
A valid flow must have:
1. Exactly one trigger node
2. All nodes connected via edges (no orphaned nodes)
3. No circular dependencies
4. Valid node types and configurations
5. Matching manual variables (for manual triggers)
6. Required parameters for all action nodes
7. Proper variable reference syntax
8. Export format wrapper for import
9. Exactly one response node for synchronous flows (all branches must converge to it)

Use validate_flow_json() to check all requirements before saving!
"""
    }


@router.get("/transform-guide", response_model=Dict[str, Any])
async def get_transform_guide(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive guide for transform nodes including available modules and examples.
    """
    return {
        "overview": "Transform nodes execute Python scripts in a RestrictedPython environment",
        "recommended_approach": {
            "title": "🎯 RECOMMENDED: Use External Functions for Complex Logic",
            "description": "For complex logic, define functions separately as plain Python text",
            "quick_example": {
                "benefit": "Cleaner code organization and better reusability",
                "do_this": "Write functions as plain Python, reference them in the node",
                "flow_structure": {
                    "flow_definition": {
                        "nodes": [{
                            "type": "transform",
                            "data": {
                                "script": "result = process_data(input)",
                                "functions_used": ["process_data"]
                            }
                        }]
                    },
                    "functions": {
                        "process_data": "def process_data(data):\n    # Plain Python text\n    return data.upper()"
                    }
                }
            },
            "key_point": "The functions dictionary contains PLAIN PYTHON TEXT"
        },
        "script_format": {
            "description": "Transform node scripts are Python code stored as strings",
            "json_code_blocks": {
                "instruction": "When outputting in JSON code blocks, use natural Python formatting",
                "benefit": "Scripts can have real newlines and quotes without escaping",
                "note": "The validation system automatically handles extraction from code blocks"
            },
            "json_strings": {
                "instruction": "When outputting as JSON strings (not in code blocks), use standard JSON escaping",
                "note": "This is only needed when NOT using code blocks",
                "recommendation": "Always use JSON code blocks instead to avoid escaping complexity"
            },
            "guidelines": [
                {
                    "guideline": "Write Natural Python",
                    "description": "In code blocks, write Python with natural formatting",
                    "example": "Use normal Python syntax with real newlines and indentation"
                },
                {
                    "guideline": "Set Output Variable",
                    "description": "Always set the 'output' variable with your results",
                    "example": "output = {'result': processed_data}"
                },
                {
                    "guideline": "Use Print for Debugging",
                    "description": "Use print() statements to debug - they appear in logs",
                    "example": "print(f'Processing {len(items)} items')"
                }
            ],
            "best_practice": "Use JSON code blocks to avoid escaping complexity"
        },
        "restrictions": {
            "max_execution_time": "5 seconds",
            "max_output_size": "50MB (configurable via TRANSFORM_MAX_OUTPUT_SIZE)",
            "max_iterations": 10000,
            "forbidden_operations": [
                "exec", "eval", "compile", "open", "file",
                "input", "raw_input", "__import__ (except allowed modules)",
                "__subclasses__", "__bases__", "__globals__", "__code__"
            ]
        },
        "available_modules": {
            "base64": "Base64 encoding/decoding",
            "json": "JSON parsing and serialization",
            "datetime": "Date and time operations",
            "re": "Regular expressions",
            "urllib.parse": "URL parsing",
            "math": "Mathematical functions",
            "random": "Random number generation",
            "collections": "Counter, defaultdict, etc.",
            "itertools": "Iterator functions",
            "hashlib": "Cryptographic hashing",
            "io": "BytesIO, StringIO for in-memory file operations",
            "csv": "CSV file operations",
            "pandas (pd)": "Data manipulation, Excel/CSV operations",
            "openpyxl": "Excel file reading and writing",
            "docx": "Word document processing",
            "pypdf": "PDF text extraction",
            "pptx": "PowerPoint presentation handling",
            "reportlab": "PDF generation (full library)"
        },
        "context_variables": {
            "input": "Input variables from trigger or previous nodes",
            "node_outputs": "Dictionary of outputs from all previous nodes",
            "global_vars": "Global variables accessible across the flow",
            "loop": "Loop context when inside a loop",
            "output": "Required variable to set for node output"
        },
        "variable_access_details": {
            "input": {
                "description": "Access trigger variables ONLY (not from previous nodes)",
                "examples": [
                    "user_email = input.get('user_email')",
                    "file_data = input.get('uploaded_file', {})",
                    "items = input.get('items', [])"
                ]
            },
            "node_outputs": {
                "description": "Access outputs from specific nodes that have already executed",
                "examples": [
                    "api_data = node_outputs['api_call_1']['data']",
                    "status = node_outputs.get('action_1', {}).get('status')",
                    "# Note: node_outputs is a dict, access by node ID"
                ],
                "important": "Transform nodes output to node_outputs just like any other node - there is no special 'transform_1.variable' syntax"
            },
            "loop": {
                "description": "Available only inside loop body nodes",
                "examples": [
                    "current_item = loop.item",
                    "index = loop.index",
                    "is_first = loop.first",
                    "is_last = loop.last"
                ]
            },
            "global_vars": {
                "description": "Flow-level variables accessible across nodes",
                "examples": [
                    "counter = global_vars.get('counter', 0)",
                    "set_global('counter', counter + 1)",
                    "flag = global_vars.get('processing_complete', False)"
                ]
            }
        },
        "file_handling": {
            "uploaded_files": {
                "description": "Files uploaded via trigger come as dictionaries",
                "structure": {
                    "name": "filename.xlsx",
                    "type": "application/vnd.ms-excel", 
                    "size": 11061,
                    "data": "base64_encoded_content",
                    "lastModified": 1757496413603
                },
                "example_note": "In JSON code blocks, write this naturally with real newlines",
                "example_structure": {
                    "description": "The script field contains Python code",
                    "in_code_blocks": "Use natural Python formatting",
                    "in_json_strings": "Use \\n for newlines if not in a code block"
                }
            },
            "debugging": {
                "description": "Use print() for debugging - appears in execution logs",
                "examples": [
                    "print('Debug: Starting processing')",
                    "print(f'Input keys: {list(input.keys())}')",
                    "print(f'Node outputs available: {list(node_outputs.keys())}')"
                ]
            }
        },
        "complete_example": {
            "description": "Transform node processing API data",
            "note": "In JSON code blocks, this script would have natural newlines",
            "script_description": "Python code that processes API data and sets output"
        },
        "complete_transform_node_example": {
            "description": "A complete, working transform node exactly as it should appear in a flow JSON",
            "node": {
                "id": "transform_data",
                "type": "transform",
                "position": {"x": 250, "y": 400},
                "data": {
                    "label": "Process File Data",
                    "script": "import json\nimport base64\n\n# Get input from trigger\nfile_info = input.get('file_upload', {})\nfile_name = file_info.get('name', '')\nfile_data = file_info.get('data', '')\n\n# Process the file\nif file_data:\n    # Decode if base64\n    try:\n        decoded = base64.b64decode(file_data)\n        content = decoded.decode('utf-8')\n    except:\n        content = file_data\nelse:\n    content = ''\n\n# Create output\noutput = {\n    'file_name': file_name,\n    'content_length': len(content),\n    'processed': True,\n    'timestamp': str(datetime.now())\n}",
                    "width": 200,
                    "height": 100
                }
            },
            "how_to_create": [
                "Write your Python script with normal formatting",
                "Create your node object with the script as a string value",
                "Include the node in your flow definition",
                "The backend will parse and execute your Python code"
            ]
        },
        "validation_self_check": {
            "description": "Before submitting, verify your transform node",
            "checks": [
                "Can json.loads() parse your entire flow JSON without errors?",
                "Does the script field contain valid Python when newlines are restored?",
                "Are you using json.dumps() for serialization, not manual string construction?",
                "Have you tested that output variable is set in your script?"
            ]
        },
        "external_functions": {
            "overview": "✨ Define reusable functions as plain Python text separately",
            "critical_understanding": {
                "message": "External functions are NOT part of the flow JSON!",
                "explanation": "Functions are sent as a SEPARATE parameter with PLAIN PYTHON TEXT",
                "benefit": "Write functions exactly as you would in a .py file"
            },
            "simple_steps": [
                "1. Write your Python function as normal text",
                "2. Add 'functions_used': ['function_name'] to the transform node",
                "3. Call the function in your script",
                "4. Pass functions as a separate parameter to the API"
            ],
            "conceptual_structure": {
                "what_you_send": {
                    "parameter_1_flow": "The flow_definition JSON (nodes, edges, etc.)",
                    "parameter_2_functions": "A dictionary of function_name -> python_code_as_plain_text"
                },
                "not_this": "DO NOT put functions inside the flow JSON",
                "but_this": "Send functions as a SEPARATE parameter alongside the flow"
            },
            "actual_api_call": {
                "endpoint": "POST /api/v1/flow-design/validate",
                "body_structure": {
                    "flow_definition": {"_comment": "your flow JSON here"},
                    "functions": {
                        "_comment": "Functions as PLAIN TEXT, not escaped",
                        "example": "Each function value is plain Python text with real newlines"
                    }
                }
            },
            "when_to_use": {
                "use_external_functions": [
                    "Complex multi-line logic",
                    "Functions with quotes or special characters",
                    "Reusable code across nodes",
                    "When JSON escaping becomes difficult"
                ],
                "use_inline_script": [
                    "Simple one-line operations",
                    "Quick variable assignments"
                ]
            },
            "explicit_difference": {
                "inline_approach": {
                    "description": "For simple inline scripts",
                    "node": {
                        "script": "def process(data):\n    return data.upper()\noutput = process(input)",
                        "note": "Simple scripts can be written inline"
                    }
                },
                "external_approach": {
                    "description": "For reusable functions",
                    "node": {
                        "script": "output = process(input)",
                        "functions_used": ["process"]
                    },
                    "functions_parameter": {
                        "process": "def process(data):\n    return data.upper()"
                    },
                    "key_insight": "The function is sent SEPARATELY, not inside the JSON"
                }
            },
            "complete_mcp_tool_call": {
                "tool": "validate_flow_design",
                "parameters": {
                    "flow_definition": {
                        "nodes": [{
                            "type": "transform",
                            "data": {
                                "script": "result = my_function(input)",
                                "functions_used": ["my_function"]
                            }
                        }]
                    },
                    "functions": {
                        "my_function": "def my_function(data):\n    # This is plain Python\n    # Natural formatting\n    return data"
                    }
                },
                "critical": "Pass TWO parameters: flow_definition AND functions"
            },
            "best_practices": [
                "Use external functions for complex multi-line logic",
                "Keep function names descriptive and unique",
                "Each function should have a single responsibility",
                "Include docstrings for clarity",
                "Test functions independently before using in flows",
                "Validate that all functions in 'functions_used' are provided"
            ],
            "limitations": [
                "Functions must follow RestrictedPython rules (no file I/O, no imports of os/sys)",
                "Functions are injected at script execution time",
                "Function names must be valid Python identifiers",
                "Recursive functions are allowed but subject to execution time limits"
            ],
            "comparison": {
                "inline_script": {
                    "pros": "Simple for short scripts, self-contained",
                    "cons": "Can become hard to read for complex logic"
                },
                "external_functions": {
                    "pros": "Clean Python text, readable, reusable, testable",
                    "cons": "Requires separate functions parameter"
                }
            }
        }
    }


@router.get("/condition-guide", response_model=Dict[str, Any])
async def get_condition_guide(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive guide for condition nodes including expression syntax and examples.
    
    This endpoint provides everything needed to understand and use condition nodes in flows,
    including expression syntax, operators, variable references, and common patterns.
    """
    return {
        "overview": """
Condition nodes enable branching logic in flows based on expressions that evaluate to true or false.
Each condition node has two output branches: 'true' (executed when condition is met) and 'false' (executed when not met).

⚠️⚠️⚠️ CRITICAL - EDGE CONNECTION SYNTAX ⚠️⚠️⚠️

You MUST use 'sourceHandle' property on edges to connect condition branches.
DO NOT use 'condition' property - that is WRONG and will not work!

✅ CORRECT - Use sourceHandle:
  {"id": "e1", "source": "condition_1", "target": "action_true", "sourceHandle": "true"}
  {"id": "e2", "source": "condition_1", "target": "action_false", "sourceHandle": "false"}

❌ WRONG - Do NOT use condition property:
  {"id": "e1", "source": "condition_1", "target": "action_true", "condition": "true"}  ← WRONG!
  {"id": "e2", "source": "condition_1", "target": "action_false", "condition": "false"} ← WRONG!

HOW TO CONNECT BRANCHES:
- True Branch: Edge with sourceHandle="true" connects to nodes executed when condition is met
- False Branch: Edge with sourceHandle="false" connects to nodes executed when condition fails
- Both branches are optional - you can have only a true branch, only a false branch, or both

⚠️ CRITICAL: Expressions use RESTRICTED PYTHON with limited functionality for security.
""",
        "evaluation_engine": {
            "type": "Restricted Python Evaluator",
            "security": "Sandboxed environment - no imports, I/O, or system access allowed",
            "syntax": "Python expression syntax (NOT JavaScript)"
        },
        "supported_functions": {
            "builtin_functions": [
                "len(object) - Get length of strings, lists, or dictionaries",
                "any(iterable) - Return True if any element is true",
                "all(iterable) - Return True if all elements are true",
                "next(iterator, default) - Get next item from iterator with optional default",
                "str(object) - Convert to string",
                "int(object) - Convert to integer",
                "float(object) - Convert to float"
            ],
            "string_methods": [
                "string.startswith(prefix) - Check if string starts with prefix",
                "string.endswith(suffix) - Check if string ends with suffix",
                "string.lower() - Convert to lowercase",
                "string.upper() - Convert to uppercase",
                "string.strip() - Remove leading/trailing whitespace",
                "string.split(separator) - Split string into list",
                "string.join(iterable) - Join list elements into string"
            ],
            "list_methods": [
                "list.append(item) - Add item to list",
                "list.extend(iterable) - Add multiple items",
                "list.pop(index) - Remove and return item",
                "list.remove(value) - Remove first occurrence"
            ],
            "dict_methods": [
                "dict.get(key, default) - Get value with optional default",
                "dict.keys() - Get all keys",
                "dict.values() - Get all values",
                "dict.items() - Get key-value pairs"
            ]
        },
        "supported_operators": {
            "comparison": ["==", "!=", ">", "<", ">=", "<="],
            "logical": ["and", "or", "not"],
            "membership": ["in", "not in"],
            "identity": ["is", "is not"]
        },
        "supported_constructs": {
            "list_comprehensions": "[x for x in iterable if condition]",
            "generator_expressions": "(x for x in iterable if condition)",
            "conditional_expressions": "value_if_true if condition else value_if_false",
            "subscript_access": "object[key] or object[index]",
            "attribute_access": "object.attribute",
            "method_calls": "object.method(args)"
        },
        "variable_access": {
            "input_variables": {
                "pattern": "input.variableName",
                "example": "input.age >= 18",
                "description": "Access variables from trigger or input"
            },
            "node_outputs": {
                "pattern": "node_outputs.nodeId.property",
                "example": "node_outputs.fetch_user.status == 'active'",
                "description": "Access outputs from previous nodes"
            },
            "loop_variables": {
                "pattern": "loop.property",
                "examples": [
                    "loop.index < 10",
                    "loop.item.price > 100",
                    "loop.first or loop.last"
                ],
                "description": "Access loop iteration variables inside loops"
            },
            "global_variables": {
                "pattern": "global.variableName",
                "example": "global.maxRetries > 0",
                "description": "Access global variables set by transform nodes"
            }
        },
        "common_patterns": {
            "simple_comparison": {
                "expression": "input.age >= 18",
                "description": "Check if user is adult"
            },
            "string_check": {
                "expression": "'@gmail.com' in input.email",
                "description": "Check if email is Gmail"
            },
            "status_validation": {
                "expression": "node_outputs.api_call.status == 200",
                "description": "Check if API call was successful"
            },
            "multiple_conditions": {
                "expression": "(input.amount > 1000 and input.currency == 'USD') or input.isVIP",
                "description": "Complex condition with AND/OR logic"
            },
            "null_check": {
                "expression": "input.data is not None and len(input.data) > 0",
                "description": "Check for non-null and non-empty data"
            },
            "array_validation": {
                "expression": "len(node_outputs.fetch_items.results) > 0",
                "description": "Check if array has items"
            },
            "error_handling": {
                "expression": "node_outputs.previous.error is None",
                "description": "Check if previous node succeeded"
            },
            "loop_control": {
                "expression": "loop.count <= 10 and not global.stopProcessing",
                "description": "Control loop execution"
            }
        },
        "best_practices": [
            "Always validate data exists before accessing nested properties",
            "Use parentheses to clarify complex conditions with multiple operators",
            "Consider null/undefined cases in your conditions",
            "Test both true and false branches during flow development",
            "Use descriptive variable names for clarity",
            "Add comments in transform nodes before complex conditions to explain logic"
        ],
        "common_mistakes": {
            "single_equals": {
                "wrong": "input.status = 'active'",
                "correct": "input.status == 'active'",
                "explanation": "Use == for comparison, not assignment operator ="
            },
            "missing_quotes": {
                "wrong": "input.type == number",
                "correct": "input.type == 'number'",
                "explanation": "String literals require quotes"
            },
            "template_syntax": {
                "wrong": "{{node_outputs.fetch.data}}",
                "correct": "node_outputs.fetch.data",
                "explanation": "No template brackets in expressions - use direct variable access"
            },
            "type_mismatch": {
                "wrong": "input.count == '5'",
                "correct": "input.count == 5",
                "explanation": "Match data types - compare numbers to numbers, strings to strings"
            },
            "null_comparison": {
                "wrong": "input.value == null or input.value == NULL",
                "correct": "input.value is None",
                "explanation": "Python uses None, not null or NULL"
            },
            "unsupported_functions": {
                "wrong": "eval(input.code) or exec(input.script)",
                "correct": "Use only supported functions listed above",
                "explanation": "eval(), exec(), and other potentially unsafe functions are blocked"
            },
            "wrong_edge_property": {
                "wrong": '{"source": "condition_1", "target": "action_1", "condition": "true"}',
                "correct": '{"source": "condition_1", "target": "action_1", "sourceHandle": "true"}',
                "explanation": "CRITICAL: Use 'sourceHandle' property on edges, NOT 'condition'. The 'condition' property does not work for routing!"
            }
        },
        "integration_examples": {
            "complete_branching_flow": {
                "description": "Full example showing how to connect condition nodes to different branches",
                "nodes": [
                    {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {"label": "Start", "triggerType": "manual"}
                    },
                    {
                        "id": "check_age",
                        "type": "condition",
                        "data": {
                            "label": "Check if Adult",
                            "expression": "input.age >= 18"
                        }
                    },
                    {
                        "id": "adult_action",
                        "type": "action",
                        "data": {"label": "Process Adult Registration"}
                    },
                    {
                        "id": "minor_action",
                        "type": "action",
                        "data": {"label": "Process Minor Registration (Needs Guardian)"}
                    }
                ],
                "edges": [
                    {
                        "id": "e1",
                        "source": "trigger_1",
                        "target": "check_age"
                    },
                    {
                        "id": "e2_true",
                        "source": "check_age",
                        "target": "adult_action",
                        "sourceHandle": "true",
                        "comment": "This edge is taken when age >= 18"
                    },
                    {
                        "id": "e3_false",
                        "source": "check_age",
                        "target": "minor_action",
                        "sourceHandle": "false",
                        "comment": "This edge is taken when age < 18"
                    }
                ],
                "key_points": [
                    "The sourceHandle='true' connects to nodes that execute when condition is met",
                    "The sourceHandle='false' connects to nodes that execute when condition fails",
                    "Both branches are optional - you can have only one or both"
                ]
            },
            "after_api_call": {
                "description": "Check API response and branch accordingly",
                "condition": "node_outputs.api_call.status == 200 and node_outputs.api_call.data is not None",
                "true_branch": "Process successful response",
                "false_branch": "Handle error or retry"
            },
            "validation_chain": {
                "description": "Multiple validation checks",
                "flow": "Trigger → Condition(Valid Email?) → Condition(Valid Token?) → Process",
                "conditions": [
                    "'@' in input.email and len(input.email) > 5",
                    "input.token is not None and len(input.token) == 32"
                ]
            },
            "loop_with_condition": {
                "description": "Conditional processing inside loops",
                "condition": "loop.item.status == 'pending' and loop.item.priority > 5",
                "use_case": "Process only high-priority pending items"
            },
            "advanced_patterns": {
                "description": "Complex expressions using supported Python constructs",
                "find_in_nested_array": {
                    "condition": "'urgent' in ''.join([item['subject'] for item in node_outputs.api_call.messages if item.get('subject')])",
                    "explanation": "Search text in nested array using list comprehension + join"
                },
                "check_any_match": {
                    "condition": "any(item['status'] == 'active' for item in node_outputs.fetch_data.results)",
                    "explanation": "Check if any item matches condition using any()"
                },
                "check_all_valid": {
                    "condition": "all(item['price'] > 0 for item in node_outputs.products.items)",
                    "explanation": "Verify all items meet criteria using all()"
                },
                "find_first_match": {
                    "condition": "next((item for item in node_outputs.api_response.data if item['type'] == 'primary'), None) is not None",
                    "explanation": "Find first matching item using next() with default"
                },
                "complex_nested_check": {
                    "condition": "len([h for h in node_outputs.response.headers if h.get('name') == 'Authorization']) > 0",
                    "explanation": "Check existence in nested structure using list comprehension + len"
                }
            }
        },
        "node_structure": {
            "description": "CRITICAL: Correct structure for condition nodes in flows",
            "important": "For proper rendering, width and height should be at the NODE level, not only in data",
            "correct_structure": {
                "id": "check_condition",
                "type": "condition",
                "position": {"x": 100, "y": 400},
                "width": 200,
                "height": 100,
                "data": {
                    "label": "Check Condition",
                    "expression": "input.value > 10"
                }
            },
            "incorrect_structure": {
                "id": "check_condition",
                "type": "condition",
                "position": {"x": 100, "y": 400},
                "data": {
                    "label": "Check Condition",
                    "expression": "input.value > 10",
                    "width": 200,
                    "height": 100
                }
            },
            "explanation": "If width/height are ONLY in data (incorrect), the node won't render properly. The frontend will normalize this on load, but for new flows, put width/height at the node level.",
            "note": "The style property with pixel values is optional - the frontend will add it automatically based on the width/height values"
        },
        "troubleshooting": {
            "condition_always_false": [
                "Check variable paths are correct",
                "Verify data types match (string vs number)",
                "Use transform node to log values before condition",
                "Check for null/undefined values"
            ],
            "unexpected_branching": [
                "Add logging in transform nodes to trace values",
                "Verify operator precedence with parentheses",
                "Check for type coercion issues",
                "Test with simplified conditions first"
            ],
            "node_not_rendering": [
                "Ensure width/height are at node level, not in data",
                "Verify style object has width/height in pixels",
                "Check that position object has x and y coordinates",
                "Confirm node has unique id"
            ]
        }
    }


@router.get("/loop-guide", response_model=Dict[str, Any])
async def get_loop_guide(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive guide for loop nodes including all loop types, variables, and examples.

    This endpoint provides everything needed to understand and use loop nodes in flows,
    including forEach, while, and for loops, breaking conditions, and nested loops.
    """
    return {
        "overview": """
Loop nodes enable iterative processing in flows, allowing you to repeat operations over collections,
continue until conditions are met, or execute a fixed number of times. IOFlow supports three types
of loops: forEach (iterate collections), while (condition-based), and for (numeric range).

Loop nodes work by creating a loop body - the set of nodes connected within the loop that execute
for each iteration. Variables from the current iteration are accessible throughout the loop body.
""",
        "loop_types": {
            "forEach": {
                "description": "Iterate over arrays, lists, or any collection of items",
                "configuration": {
                    "loopType": "forEach",
                    "arrayPath": "Path to array/collection to iterate (e.g., 'node_outputs.api_call.items')",
                    "iteratorName": "Variable name for current item (default: 'item')"
                },
                "available_variables": {
                    "loop.item": "Current item in the iteration",
                    "loop.index": "Current index (0-based)",
                    "loop.first": "True if first iteration",
                    "loop.last": "True if last iteration",
                    "loop.length": "Total number of items"
                },
                "example": {
                    "id": "loop_users",
                    "type": "loop",
                    "data": {
                        "label": "Process Each User",
                        "loopType": "forEach",
                        "arrayPath": "node_outputs.fetch_users.users",
                        "iteratorName": "user"
                    }
                },
                "use_cases": [
                    "Processing API response arrays",
                    "Iterating through file lists",
                    "Batch processing records",
                    "Sending notifications to multiple recipients"
                ]
            },
            "while": {
                "description": "Continue looping while a condition is true",
                "configuration": {
                    "loopType": "while",
                    "condition": "Expression that evaluates to true/false (e.g., 'global.retries < 5')",
                    "maxIterations": "Safety limit to prevent infinite loops (optional, default: 100)"
                },
                "available_variables": {
                    "loop.iteration": "Current iteration number (starts at 0)"
                },
                "example": {
                    "id": "retry_loop",
                    "type": "loop",
                    "data": {
                        "label": "Retry Until Success",
                        "loopType": "while",
                        "condition": "node_outputs.check_status.status != 'completed'",
                        "maxIterations": 10
                    }
                },
                "use_cases": [
                    "Retry logic with backoff",
                    "Polling for status changes",
                    "Waiting for external events",
                    "Processing queues until empty"
                ]
            },
            "for": {
                "description": "Loop a specific number of times with numeric counter",
                "configuration": {
                    "loopType": "for",
                    "startValue": "Starting number (e.g., 0 or 1)",
                    "endValue": "Ending number (exclusive, loop while index < endValue)",
                    "stepValue": "Increment for each iteration (optional, default: 1)"
                },
                "available_variables": {
                    "loop.index": "Current loop counter value",
                    "loop.iteration": "Iteration count (0-based)",
                    "loop.first": "True if first iteration",
                    "loop.last": "True if last iteration"
                },
                "example": {
                    "id": "generate_reports",
                    "type": "loop",
                    "data": {
                        "label": "Generate 7 Daily Reports",
                        "loopType": "for",
                        "startValue": 0,
                        "endValue": 7,
                        "stepValue": 1
                    }
                },
                "use_cases": [
                    "Fixed number of operations",
                    "Generating series of reports",
                    "Creating numbered items",
                    "Time-based iterations (days, hours)"
                ]
            }
        },
        "CRITICAL_loop_connection_structure": {
            "WARNING": "⚠️ INCORRECT LOOP CONNECTIONS ARE THE #1 CAUSE OF FLOW VALIDATION ERRORS!",
            "description": "Loop nodes have THREE specific handles that MUST be used correctly",
            "loop_node_handles": {
                "loop-body": {
                    "type": "output handle",
                    "purpose": "Connects FROM loop node TO first node in loop body",
                    "usage": "sourceHandle: 'loop-body'",
                    "example": {"source": "loop_1", "target": "transform_1", "sourceHandle": "loop-body"}
                },
                "loop-back": {
                    "type": "input handle",
                    "purpose": "Receives connection FROM last node in loop body back TO loop node",
                    "usage": "targetHandle: 'loop-back'",
                    "example": {"source": "action_1", "target": "loop_1", "targetHandle": "loop-back"}
                },
                "continue": {
                    "type": "output handle",
                    "purpose": "Connects FROM loop node TO next node AFTER loop completes",
                    "usage": "sourceHandle: 'continue'",
                    "example": {"source": "loop_1", "target": "response_1", "sourceHandle": "continue"}
                }
            },
            "CORRECT_edge_pattern": {
                "step1": "Loop to first body node: sourceHandle='loop-body'",
                "step2": "Nodes within loop body: standard edges (no special handles)",
                "step3": "Last body node back to loop: targetHandle='loop-back'",
                "step4": "Loop to next node after completion: sourceHandle='continue'"
            },
            "WRONG_patterns_to_avoid": [
                "❌ sourceHandle: 'loop.body' (should be 'loop-body' with hyphen)",
                "❌ sourceHandle: 'loop.complete' (should be 'continue')",
                "❌ sourceHandle: 'loop.continue' (should be just 'continue')",
                "❌ targetHandle: 'input' for loop-back (should be 'loop-back')",
                "❌ Missing loop-back edge (loop body won't iterate)"
            ],
            "visual_representation": """
            [Trigger] → [Loop Node] ─loop-body→ [Transform] → [Action] ─loop-back→ [Loop Node]
                                 ↓
                           continue
                                 ↓
                           [Response]
            """
        },
        "loop_structure": {
            "description": "How loops connect in the flow",
            "loop_body": {
                "definition": "Nodes connected from the loop node that execute each iteration",
                "entry": "Loop node connects to first node in loop body via 'loop-body' handle",
                "execution": "All connected nodes within loop execute sequentially",
                "iteration_end": "Last node connects back to loop via 'loop-back' handle"
            },
            "loop_exit": {
                "normal_completion": "After all iterations complete, flow continues from loop node's 'continue' output",
                "break_condition": "Use a condition node inside loop to break early",
                "connecting_outside": "Connect condition node's branch to a node outside the loop to exit"
            },
            "edge_configuration": {
                "loop_to_body": "Edge with sourceHandle='loop-body' from loop to first body node",
                "within_body": "Normal edges between nodes in loop body (no special handles)",
                "loop_back": "Edge with targetHandle='loop-back' from last body node to loop",
                "exit_edge": "Edge with sourceHandle='continue' from loop to next node after loop"
            }
        },
        "variable_access": {
            "in_transform_nodes": {
                "description": "Access loop variables in transform node scripts",
                "examples": [
                    "current_user = loop.get('item')  # Current item in forEach",
                    "index = loop.get('index')  # Current index",
                    "is_first = loop.get('first')  # Check if first iteration",
                    "iteration = loop.get('iteration')  # While loop counter"
                ]
            },
            "in_condition_nodes": {
                "description": "Use loop variables in condition expressions",
                "examples": [
                    "loop.index < 10",
                    "loop.item.status == 'pending'",
                    "loop.iteration > 0 && node_outputs.api_call.success",
                    "loop.last == true"
                ]
            },
            "in_action_parameters": {
                "description": "Reference loop variables in action node parameters",
                "examples": [
                    "{{loop.item.id}}",
                    "{{loop.item.email}}",
                    "{{loop.index}}",
                    "Processing item {{loop.index}} of {{loop.length}}"
                ]
            }
        },
        "breaking_loops": {
            "description": "How to exit loops early",
            "method": "Use condition node inside loop with edge to outside node",
            "example_scenario": "Stop processing when error found",
            "implementation": {
                "step1": "Add condition node inside loop body",
                "step2": "Set condition like: node_outputs.process.error != null",
                "step3": "Connect 'true' branch to a node outside the loop",
                "step4": "Connect 'false' branch to continue loop normally"
            },
            "break_patterns": [
                "Break on error: condition checks for error state",
                "Break on success: exit when desired result found",
                "Break on limit: exit after N successful operations",
                "Break on timeout: check elapsed time"
            ]
        },
        "nested_loops": {
            "description": "Loops can contain other loops for multi-dimensional iteration",
            "configuration": "Place loop node inside another loop's body",
            "variable_access": "Inner loops can access outer loop variables",
            "example": {
                "outer_loop": {
                    "type": "forEach",
                    "arrayPath": "input.departments",
                    "iteratorName": "department"
                },
                "inner_loop": {
                    "type": "forEach",
                    "arrayPath": "loop.department.employees",
                    "iteratorName": "employee"
                },
                "access_pattern": "Inner loop accesses both loop.employee and parent loop.department"
            },
            "use_cases": [
                "Processing hierarchical data",
                "Matrix operations",
                "Cross-product iterations",
                "Department/Employee processing"
            ]
        },
        "complete_examples": {
            "CORRECT_loop_structure_example": {
                "description": "⚠️ CRITICAL: This shows the EXACT edge structure required for loops to work",
                "important": "Pay attention to sourceHandle and targetHandle values!",
                "nodes": [
                    {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {"label": "Start"}
                    },
                    {
                        "id": "loop_1",
                        "type": "loop",
                        "data": {
                            "label": "Process Items",
                            "loopType": "forEach",
                            "arrayPath": "input.items"
                        }
                    },
                    {
                        "id": "transform_1",
                        "type": "transform",
                        "data": {
                            "label": "Process Item",
                            "script": "# This node is INSIDE the loop because it's connected via loop-body\\nitem = loop.get('item')  # loop variables are available here\\nindex = loop.get('index')\\noutput = {'processed': item}"
                        }
                    },
                    {
                        "id": "action_1",
                        "type": "action",
                        "data": {
                            "label": "Save Item",
                            "parameterMapping": {
                                "data": {"source": "variable", "value": "node_outputs.transform_1.processed"}
                            }
                        }
                    },
                    {
                        "id": "response_1",
                        "type": "response",
                        "data": {"label": "Done"}
                    }
                ],
                "edges": [
                    {
                        "id": "e1",
                        "source": "trigger_1",
                        "target": "loop_1"
                    },
                    {
                        "id": "e2",
                        "source": "loop_1",
                        "target": "transform_1",
                        "sourceHandle": "loop-body"
                    },
                    {
                        "id": "e3",
                        "source": "transform_1",
                        "target": "action_1"
                    },
                    {
                        "id": "e4",
                        "source": "action_1",
                        "target": "loop_1",
                        "targetHandle": "loop-back"
                    },
                    {
                        "id": "e5",
                        "source": "loop_1",
                        "target": "response_1",
                        "sourceHandle": "continue"
                    }
                ]
            },
            "process_api_results": {
                "description": "Process each item from API response",
                "flow_snippet": {
                    "nodes": [
                        {
                            "id": "fetch_items",
                            "type": "action",
                            "data": {
                                "label": "Fetch Items",
                                "service": "list_items"
                            }
                        },
                        {
                            "id": "process_loop",
                            "type": "loop",
                            "data": {
                                "label": "Process Each Item",
                                "loopType": "forEach",
                                "arrayPath": "node_outputs.fetch_items.items"
                            }
                        },
                        {
                            "id": "transform_item",
                            "type": "transform",
                            "data": {
                                "label": "Transform Item",
                                "script": "item = loop.get('item')\\nprocessed = {\\n  'id': item.get('id'),\\n  'name': item.get('name').upper(),\\n  'index': loop.get('index')\\n}\\noutput = processed"
                            }
                        },
                        {
                            "id": "save_item",
                            "type": "action",
                            "data": {
                                "label": "Save Processed Item",
                                "parameterMapping": {
                                    "item_data": {"source": "variable", "value": "node_outputs.transform_item"}
                                }
                            }
                        }
                    ],
                    "edges": [
                        {"source": "fetch_items", "target": "process_loop"},
                        {"source": "process_loop", "target": "transform_item", "sourceHandle": "loop-body"},
                        {"source": "transform_item", "target": "save_item"},
                        {"source": "save_item", "target": "process_loop", "targetHandle": "loop-back"},
                        {"source": "process_loop", "target": "next_node", "sourceHandle": "continue"}
                    ]
                }
            },
            "retry_with_backoff": {
                "description": "Retry operation with exponential backoff",
                "flow_snippet": {
                    "nodes": [
                        {
                            "id": "init_retry",
                            "type": "transform",
                            "data": {
                                "script": "set_global('retry_count', 0)\\nset_global('wait_time', 1)\\noutput = {'initialized': True}"
                            }
                        },
                        {
                            "id": "retry_loop",
                            "type": "loop",
                            "data": {
                                "loopType": "while",
                                "condition": "global.retry_count < 5 && !global.success"
                            }
                        },
                        {
                            "id": "wait_backoff",
                            "type": "transform",
                            "data": {
                                "script": "import time\\nwait = global.get('wait_time', 1)\\ntime.sleep(wait)\\nset_global('wait_time', wait * 2)\\noutput = {'waited': wait}"
                            }
                        },
                        {
                            "id": "attempt_operation",
                            "type": "action",
                            "data": {
                                "label": "Try Operation"
                            }
                        },
                        {
                            "id": "check_success",
                            "type": "condition",
                            "data": {
                                "expression": "node_outputs.attempt_operation.status == 'success'"
                            }
                        },
                        {
                            "id": "mark_success",
                            "type": "transform",
                            "data": {
                                "script": "set_global('success', True)\\noutput = {'result': 'success'}"
                            }
                        },
                        {
                            "id": "increment_retry",
                            "type": "transform",
                            "data": {
                                "script": "count = global.get('retry_count', 0)\\nset_global('retry_count', count + 1)\\noutput = {'retry': count + 1}"
                            }
                        }
                    ]
                }
            }
        },
        "best_practices": [
            "Always set maxIterations for while loops to prevent infinite loops",
            "Use meaningful iterator names in forEach loops (e.g., 'user' not 'item')",
            "Add logging in transform nodes to track loop progress",
            "Break early when possible to improve performance",
            "Consider pagination for large datasets instead of loading all at once",
            "Test with small datasets first before processing large collections",
            "Use global variables to accumulate results across iterations",
            "Add error handling inside loops to prevent one failure from stopping all iterations"
        ],
        "common_mistakes": [
            "❌ CRITICAL: Using wrong handle names (e.g., 'loop.body' instead of 'loop-body')",
            "❌ CRITICAL: Missing targetHandle='loop-back' on edge from last body node to loop",
            "❌ CRITICAL: Using 'loop.complete' or 'loop.continue' instead of 'continue' handle",
            "❌ CRITICAL: Not using sourceHandle='loop-body' when connecting to first body node",
            "❌ Nodes referencing loop.item when they're not inside the loop body chain",
            "❌ Forgetting to connect loop body nodes back to the loop for continuation",
            "❌ Not handling empty arrays in forEach loops",
            "❌ Missing break conditions in while loops (infinite loop risk)",
            "❌ Incorrect arrayPath syntax (should not include {{}} brackets)",
            "❌ Trying to modify the array being iterated within forEach",
            "❌ Not initializing counters/accumulators before loop",
            "❌ Assuming loop variables persist after loop completion"
        ],
        "performance_tips": [
            "Batch operations when possible instead of one-by-one processing",
            "Use condition nodes to skip unnecessary iterations",
            "Limit nested loops depth for better performance",
            "Consider parallel processing for independent iterations (future feature)",
            "Cache repeated calculations outside the loop"
        ]
    }


@router.get("/hitl-guide", response_model=Dict[str, Any])
async def get_hitl_guide(
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive guide for Human-in-the-Loop (HITL) nodes including task types,
    assignment, data mapping, timeout/escalation, and output references.
    """
    return {
        "overview": """
Human-in-the-Loop (HITL) nodes pause flow execution and create a task for a human to review,
edit, or approve/reject data. When the execution engine reaches this node, it:
1. Pauses the flow execution (status = PAUSED)
2. Creates a HITL task assigned to specified users or roles
3. Notifies assigned users via WebSocket and email
4. Waits for a human to complete the task
5. After completion, the flow resumes with the human's response available as node output
""",
        "node_type": "human_in_loop",
        "task_types": {
            "review": {
                "description": "Human reviews data (read-only view). Flow resumes after review.",
                "response_action": "reviewed",
                "use_case": "Audit trail, compliance checks, data verification"
            },
            "edit": {
                "description": "Human can modify the presented data. Edited data is returned.",
                "response_action": "edited",
                "use_case": "Data correction, form filling, content editing"
            },
            "approve_reject": {
                "description": "Human approves or rejects. Use condition node after to branch.",
                "response_action": "approved or rejected",
                "use_case": "Approval workflows, quality gates, authorization"
            }
        },
        "configuration": {
            "taskType": {
                "type": "string",
                "required": True,
                "values": ["review", "edit", "approve_reject"],
                "description": "Determines what actions the human can take"
            },
            "title": {
                "type": "string",
                "required": True,
                "description": "Task title shown to the reviewer. Supports {{variable}} templates.",
                "example": "Review order #{{input.order_id}}"
            },
            "description": {
                "type": "string",
                "required": False,
                "description": "Instructions for the reviewer. Supports {{variable}} templates.",
                "example": "Please verify the customer details are correct and fix any errors."
            },
            "priority": {
                "type": "string",
                "required": False,
                "values": ["low", "medium", "high", "critical"],
                "default": "medium"
            },
            "assignmentConfig": {
                "description": "Who should perform the task",
                "type_user": {
                    "type": "user",
                    "users": ["user-email@example.com"],
                    "description": "Assign to specific users by email"
                },
                "type_role": {
                    "type": "role",
                    "roles": ["hitl-role-uuid"],
                    "description": "Assign to users with a specific HITL role"
                }
            },
            "displayConfig": {
                "description": "How to render the data for the reviewer",
                "format_options": ["form", "table", "json", "text"],
                "default": "form",
                "example": {"format": "form"}
            },
            "inputDataMapping": {
                "description": "Map flow context variables to data presented to the reviewer",
                "format": "Keys are field names, values are {{variable}} references",
                "example": {
                    "name": "{{input.name}}",
                    "email": "{{node_outputs.transform_1.email}}",
                    "address": "{{input.address}}"
                },
                "note": "If empty, all previous node outputs are included"
            },
            "timeoutMinutes": {
                "type": "integer",
                "default": 0,
                "description": "Timeout in minutes. 0 = no timeout (wait indefinitely)"
            },
            "escalationConfig": {
                "description": "What to do when timeout expires",
                "on_timeout_options": ["fail", "auto_approve", "auto_reject", "escalate"],
                "example": {
                    "on_timeout": "escalate",
                    "escalate_to": {"type": "user", "id": "manager-user-uuid"},
                    "max_escalations": 3,
                    "escalation_timeout_minutes": 30
                }
            }
        },
        "output_variables": {
            "description": "After completion, the HITL node output is available in subsequent nodes",
            "variables": {
                "{{node_outputs.HITL_NODE_ID.response_action}}": "String: 'approved', 'rejected', 'edited', or 'reviewed'",
                "{{node_outputs.HITL_NODE_ID.response_data}}": "Dict: The human's response/edits (for 'edit' tasks, contains modified fields)",
                "{{node_outputs.HITL_NODE_ID.input_data}}": "Dict: The original data presented to the reviewer",
                "{{node_outputs.HITL_NODE_ID.completed_by}}": "String: User ID who completed the task",
                "{{node_outputs.HITL_NODE_ID.task_type}}": "String: The task type (review/edit/approve_reject)"
            }
        },
        "examples": {
            "edit_task": {
                "description": "Human edits contact details before sending email",
                "node": {
                    "id": "hitl_edit",
                    "type": "human_in_loop",
                    "position": {"x": 400, "y": 200},
                    "data": {
                        "label": "Edit Contact Details",
                        "taskType": "edit",
                        "title": "Review and correct contact details",
                        "description": "Please verify the data is correct and fix any errors.",
                        "priority": "medium",
                        "assignmentConfig": {"type": "user", "users": ["reviewer@example.com"]},
                        "displayConfig": {"format": "form"},
                        "inputDataMapping": {
                            "name": "{{input.name}}",
                            "address": "{{input.address}}",
                            "phone": "{{input.phone}}"
                        },
                        "timeoutMinutes": 0,
                        "escalationConfig": {"on_timeout": "fail"}
                    }
                },
                "accessing_output": "node_outputs.hitl_edit.response_data contains the edited fields"
            },
            "approval_with_branching": {
                "description": "Approve/reject with condition node to branch on decision",
                "nodes": [
                    {
                        "id": "hitl_approve",
                        "type": "human_in_loop",
                        "data": {
                            "label": "Approve Order",
                            "taskType": "approve_reject",
                            "title": "Approve order #{{input.order_id}}",
                            "priority": "high",
                            "assignmentConfig": {"type": "role", "roles": ["approver-role-uuid"]},
                            "displayConfig": {"format": "form"},
                            "inputDataMapping": {
                                "order_id": "{{input.order_id}}",
                                "amount": "{{node_outputs.calc.total}}"
                            },
                            "timeoutMinutes": 60,
                            "escalationConfig": {"on_timeout": "escalate", "escalate_to": {"type": "user", "id": "manager-uuid"}}
                        }
                    },
                    {
                        "id": "check_approval",
                        "type": "condition",
                        "data": {
                            "label": "Approved?",
                            "expression": "node_outputs.hitl_approve.response_action == 'approved'"
                        }
                    }
                ],
                "edges": [
                    {"source": "hitl_approve", "target": "check_approval"},
                    {"source": "check_approval", "target": "process_order", "sourceHandle": "true"},
                    {"source": "check_approval", "target": "notify_rejection", "sourceHandle": "false"}
                ]
            }
        },
        "common_patterns": [
            "HITL → next_node: Simple review/edit, flow continues after human completes task",
            "HITL → condition → branch: Approve/reject with different paths based on decision",
            "transform → HITL → transform: Prepare data for review, then process edited data",
            "HITL → HITL: Multi-stage review (e.g., first edit, then approve)"
        ],
        "common_mistakes": [
            "Forgetting inputDataMapping — reviewer sees no data",
            "Using wrong variable syntax in inputDataMapping (must use {{}} templates)",
            "Not adding condition node after approve_reject to branch on the decision",
            "Setting timeoutMinutes=0 with escalationConfig — escalation never triggers without timeout",
            "Referencing response_data fields that don't exist (depends on what reviewer edited)"
        ]
    }


@router.get("/trigger-guide", response_model=Dict[str, Any])
async def get_trigger_guide(
    trigger_type: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive guide for trigger nodes including configuration for all trigger types.

    Args:
        trigger_type: Optional filter for specific trigger type (manual, schedule, webhook, event)

    Returns comprehensive configuration details for trigger nodes.
    """

    guides = {
        "manual": {
            "type": "manual",
            "description": "Manual triggers allow users to start flows on-demand with custom input variables",
            "configuration": {
                "manualVariables": {
                    "description": "Array of input variables that users provide when running the flow",
                    "required": True,
                    "structure": [
                        {
                            "field": "name",
                            "type": "string",
                            "required": True,
                            "description": "Variable name (used in expressions as input.{name})"
                        },
                        {
                            "field": "dataType",
                            "type": "string",
                            "required": True,
                            "description": "Data type: string, number, boolean, array, object, json, file, date, email, url"
                        },
                        {
                            "field": "description",
                            "type": "string",
                            "required": False,
                            "description": "Help text shown to user"
                        },
                        {
                            "field": "required",
                            "type": "boolean",
                            "required": False,
                            "default": True,
                            "description": "Whether this variable is required"
                        },
                        {
                            "field": "defaultValue",
                            "type": "any",
                            "required": False,
                            "description": "Default value if user doesn't provide one"
                        },
                        {
                            "field": "uiControl",
                            "type": "string",
                            "required": False,
                            "description": "UI control type: text, textarea, number, checkbox, select, file, date, email, url"
                        },
                        {
                            "field": "validation",
                            "type": "object",
                            "required": False,
                            "description": "Validation rules for the input"
                        }
                    ]
                },
                "outputs": {
                    "description": "Mapping of variable names to their references",
                    "required": True,
                    "pattern": "Variable name maps to {{input.{variable_name}}}"
                }
            },
            "examples": {
                "simple": {
                    "description": "Basic manual trigger with text input",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Manual Trigger",
                            "triggerType": "manual",
                            "manualVariables": [
                                {
                                    "name": "customer_name",
                                    "dataType": "string",
                                    "description": "Customer name to process",
                                    "required": True,
                                    "uiControl": "text"
                                }
                            ],
                            "outputs": {
                                "customer_name": "{{input.customer_name}}"
                            }
                        }
                    },
                    "trigger_config": {
                        "type": "manual",
                        "manual_variables": [
                            {
                                "name": "customer_name",
                                "dataType": "string",
                                "description": "Customer name to process",
                                "required": True
                            }
                        ]
                    }
                },
                "file_upload": {
                    "description": "Manual trigger with file upload",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Upload File",
                            "triggerType": "manual",
                            "manualVariables": [
                                {
                                    "name": "document",
                                    "dataType": "file",
                                    "description": "PDF document to process",
                                    "required": True,
                                    "uiControl": "file",
                                    "validation": {
                                        "acceptedFileTypes": ".pdf,.doc,.docx",
                                        "maxFileSize": 10485760
                                    }
                                }
                            ],
                            "outputs": {
                                "document": "{{input.document}}"
                            }
                        }
                    }
                },
                "complex": {
                    "description": "Manual trigger with multiple variable types",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Process Order",
                            "triggerType": "manual",
                            "manualVariables": [
                                {
                                    "name": "order_id",
                                    "dataType": "string",
                                    "required": True,
                                    "uiControl": "text"
                                },
                                {
                                    "name": "priority",
                                    "dataType": "boolean",
                                    "description": "Is this a priority order?",
                                    "required": False,
                                    "defaultValue": False,
                                    "uiControl": "checkbox"
                                },
                                {
                                    "name": "quantity",
                                    "dataType": "number",
                                    "required": True,
                                    "uiControl": "number"
                                }
                            ],
                            "outputs": {
                                "order_id": "{{input.order_id}}",
                                "priority": "{{input.priority}}",
                                "quantity": "{{input.quantity}}"
                            }
                        }
                    }
                }
            },
            "best_practices": [
                "Use descriptive variable names (e.g., customer_email not email)",
                "Provide helpful descriptions for each variable",
                "Set appropriate default values when possible",
                "Use validation rules for file uploads (acceptedFileTypes, maxFileSize)",
                "Choose appropriate uiControl types for better UX"
            ]
        },
        "schedule": {
            "type": "schedule",
            "description": "Schedule triggers execute flows at specific times or intervals",
            "dual_configuration_requirement": {
                "critical": "Schedule triggers require configuration in TWO places",
                "flow_level": "trigger_config.schedule - Required for backend execution",
                "node_level": "trigger node data.schedule - Required for UI validation",
                "must_match": "Both configurations must have identical structure with 'type' field",
                "note": "Missing either configuration will cause execution or validation failures"
            },
            "configuration": {
                "schedule": {
                    "description": "Schedule configuration object (REQUIRED with 'type' field)",
                    "required": True,
                    "schedule_types": {
                        "cron": {
                            "description": "Cron-based scheduling using cron expressions",
                            "fields": {
                                "type": "cron",
                                "cron_expression": "Cron expression (e.g., '0 9 * * *' for daily at 9am)",
                                "timezone": "Timezone (default: UTC)"
                            },
                            "examples": [
                                {"expression": "0 9 * * *", "description": "Daily at 9:00 AM"},
                                {"expression": "0 */2 * * *", "description": "Every 2 hours"},
                                {"expression": "0 0 * * 0", "description": "Every Sunday at midnight"},
                                {"expression": "30 14 1 * *", "description": "1st of every month at 2:30 PM"},
                                {"expression": "*/15 * * * *", "description": "Every 15 minutes"}
                            ]
                        },
                        "interval": {
                            "description": "Run at regular intervals",
                            "fields": {
                                "type": "interval",
                                "interval_value": "Numeric value for interval",
                                "interval_unit": "Unit: minutes, hours, days"
                            },
                            "examples": [
                                {"interval_value": 30, "interval_unit": "minutes", "description": "Every 30 minutes"},
                                {"interval_value": 2, "interval_unit": "hours", "description": "Every 2 hours"},
                                {"interval_value": 1, "interval_unit": "days", "description": "Once per day"}
                            ]
                        },
                        "daily": {
                            "description": "Run daily at specific time",
                            "fields": {
                                "type": "daily",
                                "time": "Time in HH:MM format (24-hour)"
                            },
                            "examples": [
                                {"time": "09:00", "description": "Daily at 9:00 AM"},
                                {"time": "14:30", "description": "Daily at 2:30 PM"},
                                {"time": "00:00", "description": "Daily at midnight"}
                            ]
                        },
                        "weekly": {
                            "description": "Run weekly on specific days",
                            "fields": {
                                "type": "weekly",
                                "days": "Array of day numbers (0=Sunday, 1=Monday, ..., 6=Saturday)",
                                "time": "Time in HH:MM format"
                            },
                            "examples": [
                                {"days": [1, 3, 5], "time": "09:00", "description": "Mon/Wed/Fri at 9:00 AM"},
                                {"days": [0], "time": "10:00", "description": "Sundays at 10:00 AM"}
                            ]
                        },
                        "monthly": {
                            "description": "Run monthly on specific day",
                            "fields": {
                                "type": "monthly",
                                "day": "Day of month (1-31) or 'last'",
                                "time": "Time in HH:MM format"
                            },
                            "examples": [
                                {"day": 1, "time": "09:00", "description": "1st of each month at 9:00 AM"},
                                {"day": 15, "time": "14:00", "description": "15th of each month at 2:00 PM"},
                                {"day": "last", "time": "17:00", "description": "Last day of month at 5:00 PM"}
                            ]
                        }
                    }
                },
                "timezone": {
                    "description": "Timezone for schedule execution",
                    "default": "UTC",
                    "examples": ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"]
                },
                "execute_immediately": {
                    "description": "Execute flow immediately when scheduled (in addition to scheduled runs)",
                    "location": "trigger_config.execute_immediately (NOT in node data)",
                    "default": True,
                    "note": "Only applies to cron and interval schedules, not time-specific schedules"
                }
            },
            "examples": {
                "cron": {
                    "description": "Cron-based schedule",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Daily Report",
                            "triggerType": "schedule",
                            "schedule": {
                                "type": "cron",
                                "cron_expression": "0 9 * * *",
                                "timezone": "America/New_York"
                            },
                            "outputs": {
                                "execution_time": "{{schedule.execution_time}}",
                                "next_run": "{{schedule.next_run}}"
                            }
                        }
                    },
                    "trigger_config": {
                        "type": "schedule",
                        "schedule": {
                            "type": "cron",
                            "cron_expression": "0 9 * * *",
                            "timezone": "America/New_York"
                        }
                    }
                },
                "interval": {
                    "description": "Interval-based schedule",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Sync Every 30 Minutes",
                            "triggerType": "schedule",
                            "schedule": {
                                "type": "interval",
                                "interval_value": 30,
                                "interval_unit": "minutes"
                            },
                            "outputs": {
                                "execution_time": "{{schedule.execution_time}}"
                            }
                        }
                    },
                    "trigger_config": {
                        "type": "schedule",
                        "schedule": {
                            "type": "interval",
                            "interval_value": 30,
                            "interval_unit": "minutes"
                        },
                        "execute_immediately": True
                    }
                },
                "weekly": {
                    "description": "Weekly schedule",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Weekly Report",
                            "triggerType": "schedule",
                            "schedule": {
                                "type": "weekly",
                                "days": [1, 3, 5],
                                "time": "09:00",
                                "timezone": "UTC"
                            },
                            "outputs": {
                                "execution_time": "{{schedule.execution_time}}"
                            }
                        }
                    },
                    "trigger_config": {
                        "type": "schedule",
                        "schedule": {
                            "type": "weekly",
                            "days": [1, 3, 5],
                            "time": "09:00",
                            "timezone": "UTC"
                        }
                    }
                }
            },
            "best_practices": [
                "Use cron expressions for complex scheduling needs",
                "Always specify timezone to avoid confusion",
                "For simple recurring tasks, use interval type",
                "Test schedule expressions before deploying",
                "Consider time zone differences for distributed teams"
            ],
            "cron_format_guide": {
                "format": "minute hour day_of_month month day_of_week",
                "fields": {
                    "minute": "0-59",
                    "hour": "0-23",
                    "day_of_month": "1-31",
                    "month": "1-12",
                    "day_of_week": "0-6 (0=Sunday)"
                },
                "special_characters": {
                    "*": "Any value",
                    ",": "List separator (e.g., 1,3,5)",
                    "-": "Range (e.g., 1-5)",
                    "/": "Step values (e.g., */15 = every 15 units)"
                }
            }
        },
        "webhook": {
            "type": "webhook",
            "description": "Webhook triggers receive HTTP requests and start flows",
            "configuration": {
                "webhookPath": {
                    "description": "URL path for the webhook (must start with /)",
                    "required": True,
                    "pattern": "/your-webhook-path",
                    "example": "/api/webhooks/order-created"
                },
                "method": {
                    "description": "HTTP method to accept",
                    "required": False,
                    "default": "POST",
                    "options": ["POST", "GET", "PUT", "PATCH", "DELETE"]
                },
                "authRequired": {
                    "description": "Whether authentication is required",
                    "required": False,
                    "default": False
                },
                "outputs": {
                    "description": "Webhook data available in flow",
                    "available_variables": {
                        "webhook.body": "Request body (JSON)",
                        "webhook.headers": "Request headers",
                        "webhook.query": "Query parameters",
                        "webhook.method": "HTTP method",
                        "webhook.path": "Request path"
                    }
                }
            },
            "examples": {
                "simple": {
                    "description": "Basic webhook trigger",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Webhook: Order Created",
                            "triggerType": "webhook",
                            "webhookPath": "/webhooks/order-created",
                            "method": "POST",
                            "authRequired": False,
                            "outputs": {
                                "body": "{{webhook.body}}",
                                "headers": "{{webhook.headers}}"
                            }
                        }
                    },
                    "trigger_config": {
                        "type": "webhook",
                        "webhook_path": "/webhooks/order-created",
                        "method": "POST",
                        "auth_required": False
                    }
                },
                "authenticated": {
                    "description": "Webhook with authentication",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Secure Webhook",
                            "triggerType": "webhook",
                            "webhookPath": "/webhooks/secure-endpoint",
                            "method": "POST",
                            "authRequired": True,
                            "outputs": {
                                "body": "{{webhook.body}}",
                                "headers": "{{webhook.headers}}",
                                "query": "{{webhook.query}}"
                            }
                        }
                    }
                }
            },
            "best_practices": [
                "Use descriptive webhook paths",
                "Enable authentication for sensitive data",
                "Validate webhook data in transform nodes",
                "Return appropriate HTTP status codes in response node",
                "Document expected webhook payload format"
            ],
            "usage": {
                "url_format": "https://your-domain.com{webhookPath}",
                "authentication": "Use API key or OAuth token in Authorization header when authRequired=true"
            }
        },
        "event": {
            "type": "event",
            "description": "Application event triggers start flows based on events from integrated applications",
            "configuration": {
                "appId": {
                    "description": "Application UUID",
                    "required": True,
                    "note": "Use list_applications() MCP tool to get app IDs"
                },
                "eventId": {
                    "description": "Event UUID or event name",
                    "required": True,
                    "note": "Use get_application_events_list() to get available events"
                },
                "appName": {
                    "description": "Application name (for display)",
                    "required": False,
                    "note": "Helps with UI display but not required for execution"
                },
                "eventName": {
                    "description": "Event name (for display)",
                    "required": False
                },
                "outputs": {
                    "description": "Event data available in flow",
                    "available_variables": {
                        "event.data": "Event payload data",
                        "event.type": "Event type",
                        "event.timestamp": "Event timestamp"
                    },
                    "note": "Actual available fields depend on the specific application event's output schema"
                }
            },
            "workflow": {
                "step_1": "Call list_applications() or list_applications(app_names='gmail,slack') to find applications",
                "step_2": "Call get_application_events_list(app_id) to see available events",
                "step_3": "Call get_event_information(app_id, event_id) to get event schema and parameters",
                "step_4": "Use appId and eventId in trigger configuration"
            },
            "examples": {
                "simple": {
                    "description": "Application event trigger",
                    "trigger_node": {
                        "id": "trigger_1",
                        "type": "trigger",
                        "data": {
                            "label": "Gmail: New Email",
                            "triggerType": "application_event",
                            "type": "event",
                            "appId": "32cb7d90-e8f4-4c3a-b5d2-8a1c9f3e6b7d",
                            "eventId": "new_email_received",
                            "appName": "Gmail API",
                            "eventName": "New Email Received",
                            "outputs": {
                                "event_data": "{{event.data}}",
                                "sender": "{{event.data.from}}",
                                "subject": "{{event.data.subject}}"
                            }
                        }
                    },
                    "trigger_config": {
                        "type": "event",
                        "app_id": "32cb7d90-e8f4-4c3a-b5d2-8a1c9f3e6b7d",
                        "event_id": "new_email_received",
                        "event_name": "New Email Received"
                    }
                }
            },
            "best_practices": [
                "Always use MCP tools to get correct app_id and event_id",
                "Check event schema to understand available data",
                "Handle missing fields in event data gracefully",
                "Use descriptive labels for better flow readability",
                "Test with actual application events before deployment"
            ],
            "note": "Event triggers may run synchronously or asynchronously depending on the application event configuration"
        }
    }

    # If specific trigger type requested, return just that guide
    if trigger_type:
        trigger_type_lower = trigger_type.lower()
        if trigger_type_lower in guides:
            return guides[trigger_type_lower]
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Trigger type '{trigger_type}' not found. Available types: manual, schedule, webhook, event"
            )

    # Return all guides with overview
    return {
        "overview": """
Trigger nodes are the starting point of every flow. They define how and when the flow executes.
IOFlow supports four types of triggers, each suited for different use cases.
        """,
        "trigger_types": {
            "manual": "User-initiated execution with custom inputs",
            "schedule": "Time-based execution (cron, interval, daily, weekly, monthly)",
            "webhook": "HTTP request triggered execution",
            "event": "Application event triggered execution"
        },
        "guides": guides,
        "usage": """
To get detailed configuration for a specific trigger type:
- Manual triggers: GET /api/v1/flow-design/trigger-guide?type=manual
- Schedule triggers: GET /api/v1/flow-design/trigger-guide?type=schedule
- Webhook triggers: GET /api/v1/flow-design/trigger-guide?type=webhook
- Event triggers: GET /api/v1/flow-design/trigger-guide?type=event

Or use the MCP tool: get_trigger_node_guide(trigger_type)
        """
    }


@router.get("/service-information/{app_id}/{service_name}", response_model=Dict[str, Any])
async def get_service_information(
    app_id: str,
    service_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get enhanced service information for AI agents.
    
    Provides detailed parameter information, mapping examples, and usage guidance
    for a specific service of an application. Works with both seed and user-created applications.
    
    Args:
        app_id: Application ID (UUID) or app_name for compatibility
        service_name: Name of the service
        
    Returns:
        Enhanced service information with parameters, examples, and guidance
    """
    from services.service_info_builder import ServiceInfoBuilder
    
    # app_id (UUID), else seed_key / app_name among the applications the
    # caller may see, their own tenant's first (services/application_lookup).
    from services.application_lookup import find_application
    application = find_application(db, app_id, current_user)
    
    if not application:
        # Log for debugging
        logger.error(f"Application not found for identifier: {app_id}")
        # Get list of available apps for better error message
        available_apps = db.query(Application).limit(5).all()
        app_info = [f"{app.app_name} (seed_key: {app.seed_key}, id: {app.app_id})" for app in available_apps]
        raise HTTPException(
            status_code=404,
            detail=f"Application '{app_id}' not found. Available apps: {app_info[:3]}"
        )
    
    # Find the service - try by service_id first (if it looks like a UUID), then by service_name
    service = None
    
    # Check if service_name looks like a UUID
    import re
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    if re.match(uuid_pattern, service_name, re.IGNORECASE):
        # Try to find by service_id
        service = db.query(ApplicationService).filter(
            ApplicationService.app_id == application.app_id,
            ApplicationService.service_id == service_name
        ).first()
    
    # If not found by ID or not a UUID, try by service_name
    if not service:
        service = db.query(ApplicationService).filter(
            ApplicationService.app_id == application.app_id,
            ApplicationService.service_name == service_name
        ).first()
    
    if not service:
        raise HTTPException(
            status_code=404,
            detail=f"Service '{service_name}' not found in application '{application.app_name}'"
        )
    
    # Build enhanced service information
    # ServiceInfoBuilder handles JSON deserialization internally
    service_info = ServiceInfoBuilder.build_enhanced_service_info(
        service=service,
        app_name=application.app_name
    )
    
    # Add subscription status if available
    subscription = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.app_id == application.app_id,
        ApplicationSubscription.tenant_id == current_user.tenant_id,
        ApplicationSubscription.status == "active"
    ).first()
    
    if subscription:
        service_info["subscription_id"] = str(subscription.subscription_id)
        service_info["is_available"] = True
    else:
        service_info["is_available"] = False
        service_info["availability_message"] = "Service requires active subscription to use"
    
    return service_info


@router.get("/event-information/{app_id}/{event_name}", response_model=Dict[str, Any])
async def get_event_information(
    app_id: str,
    event_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get enhanced event information for AI agents and flow design.
    
    Provides detailed parameter information, output schema, and usage guidance
    for a specific event of an application. Works with both seed and user-created applications.
    
    Args:
        app_id: Application ID (UUID), seed_key, or app_name for compatibility
        event_name: Name of the event
        
    Returns:
        Enhanced event information with output schema, examples, and guidance
    """
    # app_id (UUID), else seed_key / app_name among the applications the
    # caller may see, their own tenant's first (services/application_lookup).
    from services.application_lookup import find_application
    application = find_application(db, app_id, current_user)
    
    if not application:
        # Log for debugging
        logger.error(f"Application not found for identifier: {app_id}")
        # Get list of available apps for better error message
        available_apps = db.query(Application).limit(5).all()
        app_info = [f"{app.app_name} (seed_key: {app.seed_key}, id: {app.app_id})" for app in available_apps]
        raise HTTPException(
            status_code=404,
            detail=f"Application '{app_id}' not found. Available apps: {app_info[:3]}"
        )
    
    # Find the event - try by event_id first (if it looks like a UUID), then by event_name
    event = None
    
    # Check if event_name looks like a UUID
    import re
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    if re.match(uuid_pattern, event_name, re.IGNORECASE):
        # Try to find by event_id
        event = db.query(ApplicationEvent).filter(
            ApplicationEvent.app_id == application.app_id,
            ApplicationEvent.event_id == event_name
        ).first()
    
    # If not found by ID or not a UUID, try by event_name
    if not event:
        event = db.query(ApplicationEvent).filter(
            ApplicationEvent.app_id == application.app_id,
            ApplicationEvent.event_name == event_name
        ).first()
    
    if not event:
        # List available events for better error message
        available_events = db.query(ApplicationEvent).filter(
            ApplicationEvent.app_id == application.app_id
        ).limit(5).all()
        event_names = [evt.event_name for evt in available_events]
        raise HTTPException(
            status_code=404,
            detail=f"Event '{event_name}' not found in application '{application.app_name}'. Available events: {event_names}"
        )
    
    # Deserialize JSON fields for SQLite (don't modify the original object)
    if settings.database_url.startswith("sqlite"):
        event_config = deserialize_json_field(event.event_configuration)
        extraction_config = deserialize_json_field(event.extraction_configuration)
        output_schema = deserialize_json_field(event.output_schema)
        sample_payload = deserialize_json_field(event.sample_payload)
    else:
        event_config = event.event_configuration
        extraction_config = event.extraction_configuration
        output_schema = event.output_schema
        sample_payload = event.sample_payload
    
    # Build enhanced event information
    event_info = {
        "event_id": str(event.event_id),
        "event_name": event.event_name,
        "display_name": event.display_name or event.event_name,
        "description": event.description,
        "event_type": event.event_type,
        "application": {
            "app_id": str(application.app_id),
            "app_name": application.app_name,
            "app_key": application.seed_key,
            "display_name": application.app_name  # Application doesn't have display_name field
        },
        "output_schema": output_schema or {},
        "sample_payload": sample_payload or {},
        "event_configuration": event_config or {},
        "extraction_configuration": extraction_config or {},
        "trigger_usage": {
            "trigger_type": "event",
            "configuration": {
                "triggerType": "event",
                "app_id": str(application.app_id),
                "app_name": application.app_name,
                "event_id": str(event.event_id),
                "event_name": event.event_name
            },
            "available_variables": []
        },
        "parameter_mapping_example": {},
        "flow_integration_guide": ""
    }
    
    # Extract available variables from output schema
    if output_schema:
        variables = []
        schema = output_schema
        
        # Handle different schema formats
        if isinstance(schema, dict):
            if "properties" in schema:
                # JSON Schema format
                for prop_name, prop_def in schema.get("properties", {}).items():
                    variables.append({
                        "name": prop_name,
                        "path": f"input.{prop_name}",
                        "type": prop_def.get("type", "any"),
                        "description": prop_def.get("description", ""),
                        "required": prop_name in schema.get("required", [])
                    })
            elif "fields" in schema:
                # Alternative format with fields array
                for field in schema.get("fields", []):
                    variables.append({
                        "name": field.get("name", ""),
                        "path": f"input.{field.get('name', '')}",
                        "type": field.get("type", "any"),
                        "description": field.get("description", ""),
                        "required": field.get("required", False)
                    })
            else:
                # Direct key-value format
                for key in schema.keys():
                    variables.append({
                        "name": key,
                        "path": f"input.{key}",
                        "type": "any",
                        "description": "",
                        "required": False
                    })
        
        event_info["trigger_usage"]["available_variables"] = variables
        
        # Generate parameter mapping example
        if variables:
            example_mapping = {}
            for var in variables[:3]:  # Show first 3 as example
                example_mapping[var["name"]] = {
                    "source": "variable",
                    "value": var["path"]
                }
            event_info["parameter_mapping_example"] = {
                "description": "Example of using event data in an action node",
                "parameterMapping": example_mapping
            }
    
    # Add flow integration guide
    event_info["flow_integration_guide"] = f"""
To use this event as a trigger in your flow:

1. Set the trigger node configuration:
   - triggerType: "event"
   - app_id: "{application.app_id}"
   - event_id: "{event.event_id}"
   - event_name: "{event.event_name}"

2. Available variables in your flow:
   - Event data will be available under the 'input' namespace
   - Access using: {{{{input.variable_name}}}} in parameters
   - Or input.get('variable_name') in transform nodes

3. Example trigger node:
   {{
       "id": "trigger_1",
       "type": "trigger",
       "data": {{
           "label": "{event.display_name or event.event_name} Trigger",
           "triggerType": "event",
           "app_id": "{application.app_id}",
           "app_name": "{application.app_name}",
           "event_id": "{event.event_id}",
           "event_name": "{event.event_name}"
       }}
   }}
"""
    
    # Add subscription status if available
    subscription = db.query(ApplicationSubscription).filter(
        ApplicationSubscription.app_id == application.app_id,
        ApplicationSubscription.tenant_id == current_user.tenant_id,
        ApplicationSubscription.status == "active"
    ).first()
    
    if subscription:
        event_info["subscription_id"] = str(subscription.subscription_id)
        event_info["is_available"] = True
    else:
        event_info["is_available"] = False
        event_info["availability_message"] = "Event requires active subscription to use"
    
    return event_info


@router.post("/from-requirements", response_model=Dict[str, Any])
async def generate_flow_from_requirements(
    request: FlowFromRequirementsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a flow design from natural language requirements.
    
    Uses AI to create a complete flow based on the requirements description.
    """
    if current_user.role.value in ("EXECUTION_MONITOR", "FLOW_EXECUTOR"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not permit designing flows"
        )

    # This would integrate with an AI service to generate the flow
    # For now, return a template response
    return {
        "success": False,
        "message": "AI flow generation not yet implemented",
        "flow": None
    }