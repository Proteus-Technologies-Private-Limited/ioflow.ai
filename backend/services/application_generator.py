"""
Application Generator Service

Converts flow analysis results into seed application JSON format,
creating reusable applications from flows.
"""

import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .flow_analyzer import FlowAnalysis, FlowParameter, FlowOutput, NodeType, TriggerType

logger = logging.getLogger(__name__)


class ApplicationGenerator:
    """Generates seed application definitions from flow analysis"""
    
    def __init__(self):
        self.version = "1.0.0"
    
    def generate_application(self, analysis: FlowAnalysis, 
                           app_key: str,
                           app_name: str = None,
                           category: str = "Flow Applications",
                           description: str = None,
                           icon_url: str = None,
                           base_url: str = None) -> Dict[str, Any]:
        """
        Generate a complete seed application from flow analysis
        
        Args:
            analysis: FlowAnalysis object containing flow metadata
            app_key: Unique key for the application
            app_name: Display name for the application
            category: Application category
            description: Application description
            icon_url: URL to application icon
            base_url: Base URL for API calls (if applicable)
            
        Returns:
            Dictionary containing complete seed application definition
        """
        logger.info(f"Generating application from flow: {analysis.flow_name}")
        
        # Use flow information if not provided
        if not app_name:
            app_name = f"{analysis.flow_name} App"
        if not description:
            description = f"Auto-generated application from flow: {analysis.flow_name}"
        if not base_url:
            base_url = "http://localhost:7001"  # Default to IOFlow backend
        
        # Generate application definition
        application_def = {
            "app_name": app_name,
            "app_type": "flow",
            "description": description,
            "category": category,
            "auth_type": self._determine_auth_type(analysis),
            "auth_config": self._generate_auth_config(analysis),
            "version": self.version,
            "base_url": base_url,
            "icon_url": icon_url or self._get_default_icon_url(),
            "flow_based": True,
            "source_flow_id": analysis.flow_id,
            "created_at": datetime.now().isoformat(),
            "complexity_score": analysis.complexity_score,
            "estimated_execution_time": analysis.estimated_execution_time
        }
        
        # Generate services from flow
        services = self._generate_services(analysis)
        
        # Generate events if applicable
        events = self._generate_events(analysis)
        
        # Complete seed application structure
        seed_app = {
            "key": app_key,
            "application": application_def,
            "services": services,
            "events": events,
            "metadata": {
                "generated_from_flow": True,
                "flow_id": analysis.flow_id,
                "flow_name": analysis.flow_name,
                "generated_at": datetime.now().isoformat(),
                "dependencies": analysis.dependencies,
                "transformations_count": len(analysis.transformations),
                "error_handling_nodes": analysis.error_handling_nodes
            }
        }
        
        logger.info(f"Generated application with {len(services)} services and {len(events)} events")
        return seed_app
    
    def _determine_auth_type(self, analysis: FlowAnalysis) -> str:
        """Determine authentication type based on flow analysis"""
        # For flow-based applications, use no authentication for internal calls
        # The services within the flow will handle their own authentication
        return "none"
    
    def _generate_auth_config(self, analysis: FlowAnalysis) -> Dict[str, Any]:
        """Generate authentication configuration"""
        return {
            "description": "No authentication required for flow-based applications"
        }
    
    def _generate_services(self, analysis: FlowAnalysis) -> List[Dict[str, Any]]:
        """Generate services from flow analysis"""
        services = []
        
        # Primary service: Execute Flow
        primary_service = self._generate_primary_service(analysis)
        services.append(primary_service)
        
        # If the flow has specific transformations, create additional services
        for transformation in analysis.transformations:
            if self._should_create_transform_service(transformation):
                transform_service = self._generate_transform_service(analysis, transformation)
                services.append(transform_service)
        
        return services
    
    def _generate_primary_service(self, analysis: FlowAnalysis) -> Dict[str, Any]:
        """Generate the primary service for executing the flow"""
        service_name = f"execute_{analysis.flow_name.lower().replace(' ', '_')}"
        
        # Generate parameter schema from input parameters
        parameter_schema = self._generate_parameter_schema(analysis.input_parameters)
        
        # Generate output schema from output parameters
        output_schema = self._generate_output_schema(analysis.output_parameters)
        
        # Use internal sync endpoints for published flow applications to return actual results
        # Published applications should be synchronous to be useful as services in other flows
        endpoint_url = f"/api/v1/flows/{analysis.flow_id}/execute-internal-sync"
        sync_mode = "sync"
        
        # Generate request configuration (no authentication required)
        request_config = {
            "parameter_method": "json_payload",
            "method": "POST",
            "headers": {
                "Content-Type": "application/json"
            },
            "body_template": self._generate_body_template(analysis.input_parameters)
        }
        
        # Generate response configuration for sync execution that returns actual results
        response_config = {
            "success_check": {
                "type": "status_code",
                "value": 200
            },
            "data_path": "data",  # Extract the actual flow execution results
            "error_path": "error"
        }
        
        service = {
            "service_name": service_name,
            "display_name": f"Execute {analysis.flow_name}",
            "service_type": "api_call",
            "description": f"Execute the {analysis.flow_name} flow with provided parameters",
            "endpoint_template": endpoint_url,
            "request_config": request_config,
            "response_config": response_config,
            "parameter_schema": parameter_schema,
            "output_schema": output_schema,
            "sync_mode": sync_mode,
            "timeout_seconds": max(30, analysis.estimated_execution_time + 10),
            "flow_based": True,
            "source_flow_id": analysis.flow_id
        }
        
        return service
    
    def _generate_transform_service(self, analysis: FlowAnalysis, 
                                  transformation: Any) -> Dict[str, Any]:
        """Generate a service for a specific transformation"""
        service_name = f"transform_{transformation.node_id}"
        
        # Create parameters for transformation inputs
        transform_params = []
        for var_name in transformation.input_variables:
            param = {
                "name": var_name,
                "type": "string",
                "required": True,
                "description": f"Input variable {var_name} for transformation"
            }
            transform_params.append(param)
        
        parameter_schema = self._generate_parameter_schema_from_list(transform_params)
        
        # Create output schema for transformation outputs
        output_properties = {}
        for var_name in transformation.output_variables:
            output_properties[var_name] = {
                "type": "string",
                "description": f"Transformed output {var_name}"
            }
        
        output_schema = {
            "type": "object",
            "properties": output_properties
        }
        
        service = {
            "service_name": service_name,
            "display_name": f"Transform - {transformation.description or transformation.node_id}",
            "service_type": "api_call",
            "description": f"Execute transformation from node {transformation.node_id}",
            "endpoint_template": f"/api/v1/flows/{analysis.flow_id}/transform/{transformation.node_id}",
            "request_config": {
                "parameter_method": "json_payload",
                "method": "POST",
                "headers": {
                    "Content-Type": "application/json",
                    "X-API-Key": "{{auth.api_key}}"
                },
                "body_template": {var: f"{{{{{var}}}}}" for var in transformation.input_variables}
            },
            "response_config": {
                "success_check": {
                    "type": "status_code",
                    "value": 200
                },
                "data_path": "data"
            },
            "parameter_schema": parameter_schema,
            "output_schema": output_schema,
            "sync_mode": "sync",
            "timeout_seconds": 30,
            "flow_based": True,
            "transformation_node": transformation.node_id
        }
        
        return service
    
    def _generate_events(self, analysis: FlowAnalysis) -> List[Dict[str, Any]]:
        """Generate events from flow analysis"""
        events = []
        
        # If flow has webhook trigger, create webhook event
        if analysis.trigger_type == TriggerType.WEBHOOK:
            webhook_event = {
                "event_name": f"{analysis.flow_name.lower().replace(' ', '_')}_webhook",
                "display_name": f"{analysis.flow_name} Webhook",
                "trigger_type": "webhook",
                "description": f"Webhook trigger for {analysis.flow_name} flow",
                "trigger_config": {
                    "endpoint_path": f"/webhook/{analysis.flow_id}",
                    "method": "POST",
                    "verification": {
                        "type": "none"  # Can be enhanced based on requirements
                    }
                },
                "sync_mode": "sync" if analysis.is_synchronous else "async",
                "flow_based": True,
                "source_flow_id": analysis.flow_id
            }
            events.append(webhook_event)
        
        # If flow has schedule trigger, create schedule event
        elif analysis.trigger_type == TriggerType.SCHEDULE:
            schedule_event = {
                "event_name": f"{analysis.flow_name.lower().replace(' ', '_')}_schedule",
                "display_name": f"{analysis.flow_name} Schedule",
                "trigger_type": "schedule",
                "description": f"Scheduled trigger for {analysis.flow_name} flow",
                "trigger_config": {
                    "cron_expression": "0 0 * * *",  # Default daily
                    "timezone": "UTC"
                },
                "sync_mode": "async",
                "flow_based": True,
                "source_flow_id": analysis.flow_id
            }
            events.append(schedule_event)
        
        # Create completion event for async flows
        if not analysis.is_synchronous:
            completion_event = {
                "event_name": f"{analysis.flow_name.lower().replace(' ', '_')}_completed",
                "display_name": f"{analysis.flow_name} Completed",
                "trigger_type": "flow_completion",
                "description": f"Triggered when {analysis.flow_name} flow completes",
                "trigger_config": {
                    "flow_id": analysis.flow_id,
                    "status": "completed"
                },
                "sync_mode": "async",
                "flow_based": True,
                "source_flow_id": analysis.flow_id
            }
            events.append(completion_event)
        
        return events
    
    def _generate_parameter_schema(self, parameters: List[FlowParameter]) -> Dict[str, Any]:
        """Generate JSON schema for parameters"""
        properties = {}
        required = []
        
        for param in parameters:
            # Map flow parameter types to JSON schema types
            json_type = self._map_parameter_type(param.type)
            
            prop_def = {
                "type": json_type,
                "description": param.description or f"Parameter {param.name}"
            }
            
            # Add default value if provided
            if param.default_value is not None:
                prop_def["default"] = param.default_value
            
            # Add additional type-specific properties
            if json_type == "string":
                prop_def["minLength"] = 1
            elif json_type == "array":
                prop_def["items"] = {"type": "string"}
            
            properties[param.name] = prop_def
            
            if param.required:
                required.append(param.name)
        
        schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = required
        
        return schema
    
    def _generate_parameter_schema_from_list(self, params: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate parameter schema from a list of parameter definitions"""
        properties = {}
        required = []
        
        for param in params:
            properties[param["name"]] = {
                "type": param["type"],
                "description": param.get("description", "")
            }
            if param.get("required", False):
                required.append(param["name"])
        
        schema = {
            "type": "object",
            "properties": properties
        }
        
        if required:
            schema["required"] = required
        
        return schema
    
    def _generate_output_schema(self, outputs: List[FlowOutput]) -> Dict[str, Any]:
        """Generate JSON schema for outputs"""
        properties = {}
        
        for output in outputs:
            json_type = self._map_parameter_type(output.type)
            
            properties[output.name] = {
                "type": json_type,
                "description": output.description or f"Output {output.name}"
            }
        
        return {
            "type": "object",
            "properties": properties
        }
    
    def _generate_body_template(self, parameters: List[FlowParameter]) -> Dict[str, Any]:
        """Generate body template for API requests"""
        variables = {}
        
        for param in parameters:
            # Use parameter name as both key and template variable
            variables[param.name] = f"{{{{{param.name}}}}}"
        
        # Wrap variables in the expected ManualExecuteRequest structure
        return {
            "variables": variables
        }
    
    def _map_parameter_type(self, param_type: str) -> str:
        """Map flow parameter types to JSON schema types"""
        type_mapping = {
            "string": "string",
            "text": "string",
            "number": "number",
            "integer": "integer",
            "boolean": "boolean",
            "array": "array",
            "object": "object",
            "json": "object",
            "date": "string",
            "datetime": "string",
            "email": "string",
            "url": "string"
        }
        
        return type_mapping.get(param_type.lower(), "string")
    
    def _should_create_transform_service(self, transformation: Any) -> bool:
        """Determine if a transformation should have its own service"""
        # Create service for complex transformations
        code_length = len(transformation.transformation_code)
        variable_count = len(transformation.input_variables) + len(transformation.output_variables)
        
        # Create service if transformation is complex enough
        return code_length > 100 or variable_count > 3
    
    def _get_default_icon_url(self) -> str:
        """Get default icon URL for flow-based applications"""
        return "https://via.placeholder.com/64x64.png?text=Flow"
    
    def _generate_application_metadata(self, analysis: FlowAnalysis, 
                                     app_key: str, 
                                     app_name: str) -> Dict[str, Any]:
        """Generate application metadata section"""
        return {
            "app_name": app_name,
            "app_key": app_key,
            "app_type": "flow",
            "description": f"Auto-generated application from flow: {analysis.flow_name}",
            "category": "Flow Applications",
            "auth_type": self._determine_auth_type(analysis),
            "version": self.version,
            "flow_based": True,
            "source_flow_id": analysis.flow_id,
            "complexity_score": analysis.complexity_score,
            "estimated_execution_time": analysis.estimated_execution_time
        }
    
    def generate_application_preview(self, analysis: FlowAnalysis, 
                                   app_key: str,
                                   app_name: str = None) -> Dict[str, Any]:
        """Generate a preview of the application with full details"""
        if not app_name:
            app_name = f"{analysis.flow_name} App"
        
        # Generate the actual application structure for preview
        application = self._generate_application_metadata(analysis, app_key, app_name)
        services = self._generate_services(analysis)
        events = self._generate_events(analysis)
        
        # Create parameter mappings for preview
        parameter_mappings = []
        for param in analysis.input_parameters:
            parameter_mappings.append({
                "flow_variable_path": f"input.{param.name}",
                "service_parameter_name": param.name,
                "parameter_type": "input",
                "is_required": param.required,
                "description": f"Auto-mapped from flow parameter '{param.name}'"
            })
        
        preview = {
            "application": application,
            "services": services,
            "events": events,
            "parameter_mappings": parameter_mappings,
            "analysis": {
                "flow_name": analysis.flow_name,
                "flow_id": analysis.flow_id,
                "is_synchronous": analysis.is_synchronous,
                "trigger_type": analysis.trigger_type.value,
                "input_parameters": [p.to_dict() for p in analysis.input_parameters],
                "output_parameters": [o.to_dict() for o in analysis.output_parameters],
                "transformations": [t.to_dict() for t in analysis.transformations],
                "dependencies": analysis.dependencies,
                "complexity_score": analysis.complexity_score,
                "estimated_execution_time": analysis.estimated_execution_time
            }
        }
        
        return preview
    
    def validate_generated_application(self, seed_app: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the generated application structure"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # Check required top-level fields
            required_fields = ["key", "application", "services"]
            for field in required_fields:
                if field not in seed_app:
                    validation_result["errors"].append(f"Missing required field: {field}")
                    validation_result["valid"] = False
            
            # Validate application section
            if "application" in seed_app:
                app_section = seed_app["application"]
                required_app_fields = ["app_name", "app_type", "auth_type"]
                for field in required_app_fields:
                    if field not in app_section:
                        validation_result["errors"].append(f"Missing required application field: {field}")
                        validation_result["valid"] = False
            
            # Validate services
            if "services" in seed_app:
                services = seed_app["services"]
                if not isinstance(services, list):
                    validation_result["errors"].append("Services must be a list")
                    validation_result["valid"] = False
                elif len(services) == 0:
                    validation_result["warnings"].append("No services defined")
                else:
                    for i, service in enumerate(services):
                        if not isinstance(service, dict):
                            validation_result["errors"].append(f"Service {i} must be an object")
                            validation_result["valid"] = False
                        elif "service_name" not in service:
                            validation_result["errors"].append(f"Service {i} missing service_name")
                            validation_result["valid"] = False
            
            # Additional validations
            if validation_result["valid"]:
                # Check for circular dependencies
                if self._has_circular_dependencies(seed_app):
                    validation_result["warnings"].append("Potential circular dependencies detected")
                
                # Check for missing parameter schemas
                if self._has_missing_schemas(seed_app):
                    validation_result["warnings"].append("Some services missing parameter schemas")
        
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {str(e)}")
        
        return validation_result
    
    def _has_circular_dependencies(self, seed_app: Dict[str, Any]) -> bool:
        """Check for circular dependencies in the application"""
        # Simple check - in a real implementation, this would be more sophisticated
        return False
    
    def _has_missing_schemas(self, seed_app: Dict[str, Any]) -> bool:
        """Check if any services are missing parameter schemas"""
        services = seed_app.get("services", [])
        for service in services:
            if "parameter_schema" not in service:
                return True
        return False