"""
Management Tools for IOFlow MCP Server

Provides tools for creating, editing, and managing seed applications.
"""

import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from ..validators.schema_validator import SchemaValidator

logger = logging.getLogger(__name__)

class ManagementTools:
    """Tools for managing seed applications"""
    
    def __init__(self, seed_manager, auth_handler):
        self.seed_manager = seed_manager
        self.auth = auth_handler
        # Get the correct path to seed-applications directory
        import os
        backend_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.seed_apps_path = Path(backend_path) / "seed-applications"
        # Initialize schema validator
        self.schema_validator = SchemaValidator()
    
    async def create_seed_application(
        self,
        app_key: str,
        app_name: str,
        app_type: str = "api",
        app_scope: str = "global",
        category: str = "Integration",
        auth_type: str = "api_key",
        description: str = "",
        base_url: str = "",
        version: str = "1.0.0"
    ) -> Dict[str, Any]:
        """
        Create a new seed application with basic configuration.
        NOTE: This tool is accessed through MCP bridge for remote compatibility.
        
        Args:
            app_key: Unique identifier (lowercase, underscore separated)
            app_name: Human-readable name
            app_type: Type of application (database, email, api, file_system, memory, flow)
            app_scope: Scope of application (global, tenant, or user)
            category: Application category
            auth_type: Authentication method
            description: Application description
            base_url: Base API URL
            version: Semantic version
            
        Returns:
            Created application structure or error
        """
        # This method is now accessed through MCP bridge
        return {"error": "This tool should be accessed through MCP bridge"}
    async def edit_application_metadata(
        self,
        app_key: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Edit metadata of an existing seed application.
        
        Args:
            app_key: Application key to edit
            updates: Dict of fields to update in the application section
            
        Returns:
            Updated application or error
        """
        try:
            # Parse JSON strings if they come from MCP
            if isinstance(updates, str):
                try:
                    updates = json.loads(updates)
                    logger.debug(f"Parsed updates from JSON string")
                except json.JSONDecodeError as e:
                    return {
                        "error": "Invalid JSON in updates",
                        "details": str(e),
                        "hint": "Updates should be a valid JSON object"
                    }
            
            # Validate permissions
            if not self.auth.has_permission("edit_seed_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "edit_seed_applications"
                }

            # Load single application directly from file (avoids full discovery)
            app_data = self.seed_manager.get_single_application(app_key)
            if app_data is None:
                return {"error": f"Seed application '{app_key}' not found"}

            # Update allowed fields
            allowed_fields = [
                "app_name", "app_type", "app_scope", "description", "category",
                "base_url", "icon_url", "auth_config", "version", "auth_type"
            ]
            
            # Validate specific fields before updating
            if "app_type" in updates:
                valid_app_types = ["database", "email", "api", "file_system", "memory", "flow"]
                if updates["app_type"] not in valid_app_types:
                    return {
                        "error": f"Invalid app_type: '{updates['app_type']}'",
                        "valid_values": valid_app_types,
                        "description": "Type of application functionality"
                    }
            
            if "app_scope" in updates:
                valid_app_scopes = ["global", "tenant", "user"]
                if updates["app_scope"] not in valid_app_scopes:
                    return {
                        "error": f"Invalid app_scope: '{updates['app_scope']}'",
                        "valid_values": valid_app_scopes,
                        "description": "global = available to all users, tenant = specific to organization, user = user-specific"
                    }
            
            if "category" in updates:
                valid_categories = ["AI/ML", "Communication", "Productivity", "Analytics", "Database",
                                  "Integration", "Development", "API Platform", "Email",
                                  "Messaging", "Automation", "Data Extraction", "Other"]
                if updates["category"] not in valid_categories:
                    return {
                        "error": f"Invalid category: '{updates['category']}'",
                        "valid_values": valid_categories
                    }
            
            if "auth_type" in updates:
                valid_auth_types = ["none", "api_key", "oauth2", "basic", "token_exchange", "custom"]
                if updates["auth_type"] not in valid_auth_types:
                    return {
                        "error": f"Invalid auth_type: '{updates['auth_type']}'",
                        "valid_values": valid_auth_types
                    }
            
            # Track if any changes were made
            original_data = json.loads(json.dumps(app_data))
            
            for field, value in updates.items():
                if field in allowed_fields:
                    app_data["application"][field] = value
            
            # Auto-increment version if content has changed (and version not explicitly provided)
            if "version" not in updates:
                # Compare the content (excluding version and metadata) to detect changes
                original_copy = json.loads(json.dumps(original_data))
                updated_copy = json.loads(json.dumps(app_data))
                
                # Remove version and metadata from comparison
                if 'application' in original_copy and 'version' in original_copy['application']:
                    del original_copy['application']['version']
                if 'application' in updated_copy and 'version' in updated_copy['application']:
                    del updated_copy['application']['version']
                if 'metadata' in original_copy:
                    del original_copy['metadata']
                if 'metadata' in updated_copy:
                    del updated_copy['metadata']
                
                # If content has changed, increment version
                if original_copy != updated_copy:
                    existing_version = original_data.get('application', {}).get('version', '1.0.0')
                    version_parts = existing_version.split('.')
                    try:
                        # Increment patch version
                        major = int(version_parts[0]) if len(version_parts) > 0 else 1
                        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                        patch = int(version_parts[2]) if len(version_parts) > 2 else 0
                        patch += 1
                        new_version = f"{major}.{minor}.{patch}"
                    except:
                        # If version format is invalid, use a default
                        new_version = "1.0.1"
                    
                    app_data["application"]["version"] = new_version
                    logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {app_key}")
            else:
                # Use the provided version
                app_data["application"]["version"] = updates["version"]
            
            # Update metadata
            if "metadata" not in app_data:
                app_data["metadata"] = {}
            
            app_data["metadata"]["last_modified"] = datetime.utcnow().isoformat()
            app_data["metadata"]["modified_by"] = self.auth.user_info.get("email") if self.auth.user_info else "unknown"
            
            # Validate the updated application before saving
            validation_result = self.schema_validator.validate_seed_application(app_data)
            
            if not validation_result["valid"]:
                return {
                    "error": "Updated seed application validation failed",
                    "validation_errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            
            # Save updated application
            file_path = self.seed_apps_path / f"{app_key}.json"
            try:
                with open(file_path, 'w') as f:
                    json.dump(app_data, f, indent=2)
            except PermissionError:
                logger.error(f"Permission denied writing to file: {file_path}")
                return {
                    "error": "Permission denied",
                    "details": f"Cannot write to file: {file_path}",
                    "suggestion": "Check file system permissions"
                }
            except IOError as e:
                logger.error(f"IO error writing file {file_path}: {str(e)}")
                return {
                    "error": "File write failed",
                    "details": str(e),
                    "file_path": str(file_path)
                }
            except (TypeError, ValueError) as e:
                logger.error(f"JSON encoding error: {str(e)}")
                return {
                    "error": "JSON encoding failed",
                    "details": str(e),
                    "suggestion": "Check that all values are JSON serializable"
                }
            except Exception as e:
                logger.error(f"Unexpected error writing file {file_path}: {str(e)}")
                return {
                    "error": "File write failed",
                    "details": str(e),
                    "file_path": str(file_path)
                }
            
            # Update just this entry in the cache instead of clearing everything
            try:
                self.seed_manager.update_cache_entry(app_key, app_data)
            except Exception as e:
                logger.warning(f"Error updating cache after editing {app_key}: {str(e)}")

            return {
                "success": True,
                "app_key": app_key,
                "updated_fields": list(updates.keys()),
                "application": app_data
            }

        except Exception as e:
            logger.error(f"Error editing application: {str(e)}")
            return {"error": str(e)}
    
    async def add_service_to_application(
        self,
        app_key: str,
        service_name: str,
        service_type: str,
        description: str,
        configuration: Dict[str, Any],
        parameters: Optional[List[Dict[str, Any]]] = None,
        sample_input: Optional[Dict[str, Any]] = None,
        sample_output: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a new service to a seed application.
        
        Args:
            app_key: Application to add service to
            service_name: Unique service name
            service_type: Type of service (api_call, webhook, etc.)
            description: Service description
            configuration: Service-specific configuration
            parameters: List of parameter definitions
            sample_input: Example input data
            sample_output: Example output data
            
        Returns:
            Updated application or error
        """
        try:
            # Parse JSON strings if they come from MCP
            if isinstance(configuration, str):
                try:
                    configuration = json.loads(configuration)
                    logger.debug(f"Parsed configuration from JSON string")
                except json.JSONDecodeError as e:
                    return {
                        "error": "Invalid JSON in configuration",
                        "details": str(e),
                        "hint": "Configuration should be a valid JSON object"
                    }
            
            if isinstance(parameters, str):
                try:
                    parameters = json.loads(parameters)
                    logger.debug(f"Parsed parameters from JSON string")
                except json.JSONDecodeError as e:
                    return {
                        "error": "Invalid JSON in parameters",
                        "details": str(e),
                        "hint": "Parameters should be a valid JSON array"
                    }
            
            if isinstance(sample_input, str):
                try:
                    sample_input = json.loads(sample_input)
                    logger.debug(f"Parsed sample_input from JSON string")
                except json.JSONDecodeError as e:
                    return {
                        "error": "Invalid JSON in sample_input",
                        "details": str(e),
                        "hint": "Sample input should be a valid JSON object"
                    }
            
            if isinstance(sample_output, str):
                try:
                    sample_output = json.loads(sample_output)
                    logger.debug(f"Parsed sample_output from JSON string")
                except json.JSONDecodeError as e:
                    return {
                        "error": "Invalid JSON in sample_output",
                        "details": str(e),
                        "hint": "Sample output should be a valid JSON object"
                    }
            # Validate permissions
            if not self.auth.has_permission("edit_seed_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "edit_seed_applications"
                }

            # Load single application directly from file (avoids full discovery of all ~46 apps)
            app_data = self.seed_manager.get_single_application(app_key)
            if app_data is None:
                return {"error": f"Seed application '{app_key}' not found"}

            # Validate service name uniqueness - check both old and new format
            existing_services = []
            for s in app_data.get("services", []):
                # Check both service_name (new format) and name (old format)
                existing_name = s.get("service_name") or s.get("name")
                if existing_name:
                    existing_services.append(existing_name)
            
            if service_name in existing_services:
                return {"error": f"Service '{service_name}' already exists"}
            
            # Validate service type - include ALL service types from ServiceTypeEnum
            valid_service_types = [
                "api_call", "webhook", "email_send", "smtp_send", 
                "pop3_receive", "imap_receive", "database_query",
                "llm_api_call", "mcp_call"
            ]
            if service_type not in valid_service_types:
                return {
                    "error": f"Invalid service_type: '{service_type}'",
                    "valid_values": valid_service_types,
                    "descriptions": {
                        "api_call": "HTTP API call to external service",
                        "webhook": "Receive HTTP callbacks from external services",
                        "email_send": "Send emails (generic email service)",
                        "smtp_send": "Send emails via SMTP protocol",
                        "pop3_receive": "Receive emails via POP3 protocol",
                        "imap_receive": "Receive emails via IMAP protocol",
                        "database_query": "Execute database operations (SQL queries)",
                        "llm_api_call": "Call LLM/AI APIs (OpenAI, Anthropic, etc.)",
                        "mcp_call": "Call another MCP (Model Context Protocol) service"
                    }
                }
            
            # Create service structure - use NEW format with service_name
            new_service = {
                "service_name": service_name,
                "description": description,
                "service_type": service_type
            }
            
            # Check if api_call service has configuration
            if service_type == "api_call" and not configuration:
                return {
                    "error": "API call services require configuration",
                    "missing_field": "configuration",
                    "correct_format_example": {
                        "configuration": {
                            "endpoint_template": "/api/v5/whatsapp/whatsapp-outbound-message/bulk/",  # Required: API endpoint path
                            "request_config": {       # Request configuration
                                "method": "POST",     # Required: HTTP method (GET, POST, PUT, DELETE, etc.)
                                "parameter_method": "body",  # Optional: How to send parameters (body, query, path)
                                "headers_template": {          # Optional: Request headers
                                    "Content-Type": "application/json",
                                    "authkey": "{{auth.api_key}}"  # Use {{auth.api_key}} for auth headers
                                },
                                "body_template": {           # Optional: Request body template
                                    "integrated_number": "{{integrated_number}}",
                                    "content_type": "template",
                                    "recipients": "{{recipients}}",
                                    "template": "{{template}}"
                                }
                            },
                            "parameter_schema": {        # Recommended: Define input parameters
                                "type": "object",
                                "properties": {
                                    "integrated_number": {"type": "string", "description": "WhatsApp Business number"},
                                    "recipients": {"type": "array", "description": "Array of recipient objects"},
                                    "template": {"type": "object", "description": "Template configuration"}
                                },
                                "required": ["integrated_number", "recipients", "template"]
                            },
                            "response_config": {         # Optional: Response handling
                                "success_check": {
                                    "type": "status_code",
                                    "value": [200, 201]
                                }
                            }
                        }
                    },
                    "usage_note": "Pass endpoint_template, request_config, parameter_schema, and response_config in the configuration object. They will be placed at the service level."
                }
            
            # Process configuration for api_call services
            if configuration and service_type == "api_call":
                logger.debug(f"Processing {service_type} configuration: {configuration}")
                
                # Configuration object should contain fields that go directly to service level
                # Extract endpoint_template and place at service level
                if "endpoint_template" in configuration:
                    new_service["endpoint_template"] = configuration["endpoint_template"]
                elif "endpoint_url" in configuration:
                    # Support old field name but use correct field
                    new_service["endpoint_template"] = configuration["endpoint_url"]
                elif "endpoint" in configuration:
                    new_service["endpoint_template"] = configuration["endpoint"]
                
                # If endpoint_template has ${base_url}, replace with {{base_url}}
                if "endpoint_template" in new_service:
                    endpoint = new_service["endpoint_template"]
                    if isinstance(endpoint, str) and "${base_url}" in endpoint:
                        new_service["endpoint_template"] = endpoint.replace("${base_url}", "{{base_url}}")
                        logger.debug(f"Fixed base_url syntax in endpoint_template")
                
                # Handle request_config - MUST be at service level
                if "request_config" in configuration:
                    request_config = configuration["request_config"].copy()
                    
                    # Ensure method is present
                    if "method" not in request_config and "method" in configuration:
                        request_config["method"] = configuration["method"]
                    elif "method" not in request_config and "http_method" in configuration:
                        request_config["method"] = configuration["http_method"]
                    
                    # Fix headers_template vs headers
                    if "headers_template" in request_config:
                        # Fix template syntax in headers
                        headers = request_config["headers_template"]
                        if isinstance(headers, dict):
                            for key, value in headers.items():
                                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                                    var_name = value[2:-1]
                                    headers[key] = f"{{{{{var_name}}}}}"
                    elif "headers" in request_config:
                        request_config["headers_template"] = request_config.pop("headers")
                    
                    # Fix common template syntax error from MCP in body_template
                    if "body_template" in request_config and isinstance(request_config["body_template"], dict):
                        body_template = request_config["body_template"]
                        for key, value in body_template.items():
                            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                                # Convert ${var} to {{var}}
                                var_name = value[2:-1]
                                body_template[key] = f"{{{{{var_name}}}}}"
                                logger.debug(f"Fixed template syntax: ${{{var_name}}} -> {{{{{var_name}}}}}")
                    
                    # Fix query_params_template
                    if "query_params_template" in request_config and isinstance(request_config["query_params_template"], dict):
                        query_template = request_config["query_params_template"]
                        for key, value in query_template.items():
                            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                                var_name = value[2:-1]
                                query_template[key] = f"{{{{{var_name}}}}}"
                    
                    new_service["request_config"] = request_config
                else:
                    # Build request_config from individual fields in configuration
                    request_config = {}
                    
                    if "method" in configuration:
                        request_config["method"] = configuration["method"]
                    elif "http_method" in configuration:
                        request_config["method"] = configuration["http_method"]
                    
                    if "parameter_method" in configuration:
                        request_config["parameter_method"] = configuration["parameter_method"]
                    
                    if "headers_template" in configuration:
                        headers = configuration["headers_template"]
                        # Fix template syntax in headers
                        if isinstance(headers, dict):
                            for key, value in headers.items():
                                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                                    var_name = value[2:-1]
                                    headers[key] = f"{{{{{var_name}}}}}"
                        request_config["headers_template"] = headers
                    elif "headers" in configuration:
                        request_config["headers_template"] = configuration["headers"]
                    
                    if "body_template" in configuration:
                        body_template = configuration["body_template"]
                        # Fix common template syntax error from MCP
                        if isinstance(body_template, dict):
                            for key, value in body_template.items():
                                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                                    # Convert ${var} to {{var}}
                                    var_name = value[2:-1]
                                    body_template[key] = f"{{{{{var_name}}}}}"
                                    logger.debug(f"Fixed template syntax: ${{{var_name}}} -> {{{{{var_name}}}}}")
                        request_config["body_template"] = body_template
                    
                    if "query_params_template" in configuration:
                        query_template = configuration["query_params_template"]
                        if isinstance(query_template, dict):
                            for key, value in query_template.items():
                                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                                    var_name = value[2:-1]
                                    query_template[key] = f"{{{{{var_name}}}}}"
                        request_config["query_params_template"] = query_template
                    elif "query_params" in configuration:
                        request_config["query_params_template"] = configuration["query_params"]
                    
                    if request_config:
                        new_service["request_config"] = request_config
                
                # Handle parameter_schema at service level
                if "parameter_schema" in configuration:
                    new_service["parameter_schema"] = configuration["parameter_schema"]
                
                # Handle response_config at service level
                if "response_config" in configuration:
                    new_service["response_config"] = configuration["response_config"]
                
                # Handle output_schema at service level
                if "output_schema" in configuration:
                    new_service["output_schema"] = configuration["output_schema"]
            
            elif configuration:
                # For non-api_call services, handle specific requirements
                config_copy = configuration.copy()
                
                # Extract schemas that should be at service level
                if "parameter_schema" in config_copy:
                    new_service["parameter_schema"] = config_copy.pop("parameter_schema")
                if "output_schema" in config_copy:
                    new_service["output_schema"] = config_copy.pop("output_schema")
                
                # Handle webhook-specific fields
                if service_type == "webhook":
                    # Webhook needs endpoint_template or webhook_url at service level
                    if "webhook_path" in config_copy:
                        new_service["endpoint_template"] = config_copy.pop("webhook_path")
                    elif "webhook_url" in config_copy:
                        new_service["webhook_url"] = config_copy.pop("webhook_url")
                    elif "endpoint_template" in config_copy:
                        new_service["endpoint_template"] = config_copy.pop("endpoint_template")
                
                # Rest goes into service_config
                new_service["service_config"] = config_copy
            
            # Handle parameters - convert to parameter_schema for ALL service types
            if parameters:
                # Create parameter_schema from parameters list for all service types
                # All service types can benefit from parameter validation
                param_schema = {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
                
                for param in parameters:
                    param_name = param.get("name")
                    if param_name:
                        # Build schema property
                        prop = {
                            "type": param.get("type", "string"),
                            "description": param.get("description", "")
                        }
                        
                        # Add example if present
                        if "example" in param:
                            prop["example"] = param["example"]
                        
                        # Add validation rules if present
                        if "pattern" in param:
                            prop["pattern"] = param["pattern"]
                        if "enum" in param:
                            prop["enum"] = param["enum"]
                        if "minimum" in param:
                            prop["minimum"] = param["minimum"]
                        if "maximum" in param:
                            prop["maximum"] = param["maximum"]
                        if "format" in param:
                            prop["format"] = param["format"]
                        if "minLength" in param:
                            prop["minLength"] = param["minLength"]
                        if "maxLength" in param:
                            prop["maxLength"] = param["maxLength"]
                        if "items" in param:
                            prop["items"] = param["items"]
                        if "properties" in param:
                            prop["properties"] = param["properties"]
                        
                        param_schema["properties"][param_name] = prop
                        
                        if param.get("required", False):
                            param_schema["required"].append(param_name)
                
                # Service-specific configurations for parameter schemas
                if service_type == "database_query":
                    # Database queries always allow additional properties for SQL parameters
                    param_schema["additionalProperties"] = True
                elif service_type in ["smtp_send", "email_send"]:
                    # Email services might need additional properties for custom headers
                    param_schema.setdefault("additionalProperties", {"type": "string"})
                elif service_type in ["api_call", "webhook"]:
                    # API calls might have dynamic parameters
                    if not param_schema.get("additionalProperties"):
                        param_schema["additionalProperties"] = False
                
                # Add parameter_schema to the service
                new_service["parameter_schema"] = param_schema
            
            if sample_input:
                new_service["sample_input"] = sample_input
            
            if sample_output:
                new_service["sample_output"] = sample_output
            
            # Add to services
            if "services" not in app_data:
                app_data["services"] = []
            
            app_data["services"].append(new_service)
            
            # Auto-increment version since we added a service
            existing_version = app_data.get('application', {}).get('version', '1.0.0')
            version_parts = existing_version.split('.')
            try:
                # Increment patch version
                major = int(version_parts[0]) if len(version_parts) > 0 else 1
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                patch = int(version_parts[2]) if len(version_parts) > 2 else 0
                patch += 1
                new_version = f"{major}.{minor}.{patch}"
            except:
                # If version format is invalid, use a default
                new_version = "1.0.1"
            
            app_data["application"]["version"] = new_version
            logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {app_key} after adding service")
            
            # Update metadata
            if "metadata" not in app_data:
                app_data["metadata"] = {}
            
            app_data["metadata"]["last_modified"] = datetime.utcnow().isoformat()
            app_data["metadata"]["services_count"] = len(app_data["services"])
            
            # Validate the updated application before saving
            validation_result = self.schema_validator.validate_seed_application(app_data)
            
            if not validation_result["valid"]:
                # Log validation details for debugging
                logger.error(f"Validation failed for service '{service_name}' in app '{app_key}'")
                logger.error(f"Validation errors: {json.dumps(validation_result['errors'], indent=2)}")
                
                # Remove the service we just added since validation failed
                app_data["services"].pop()
                
                # Parse the validation errors to provide specific, actionable feedback
                error_details = []
                specific_fixes = []
                
                for error in validation_result["errors"]:
                    msg = error.get("message", "Unknown error")
                    path = error.get("path", [])
                    
                    # Check for the common "not" validation error
                    if "should not be valid under" in msg and "anyOf" in msg:
                        # Extract which deprecated fields are present
                        deprecated_fields = []
                        if "configuration" in str(new_service):
                            deprecated_fields.append("configuration")
                            specific_fixes.append("Remove 'configuration' field. For api_call services, use 'endpoint_template', 'request_config', 'parameter_schema' at service level")
                        if "parameters" in str(new_service):
                            deprecated_fields.append("parameters")
                            specific_fixes.append("Remove 'parameters' field. Use 'parameter_schema' at service level instead")
                        if "name" in str(new_service) and "service_name" not in str(new_service):
                            deprecated_fields.append("name")
                            specific_fixes.append("Replace 'name' with 'service_name'")
                        if "http_method" in str(new_service):
                            deprecated_fields.append("http_method")
                            specific_fixes.append("Remove 'http_method'. Use 'method' inside 'request_config' instead")
                        if "headers_template" in str(new_service) and "request_config" not in str(new_service):
                            deprecated_fields.append("headers_template")
                            specific_fixes.append("Move 'headers_template' inside 'request_config'")
                        if "body_template" in str(new_service) and "request_config" not in str(new_service):
                            deprecated_fields.append("body_template")  
                            specific_fixes.append("Move 'body_template' inside 'request_config'")
                        
                        if deprecated_fields:
                            error_details.append(f"Service contains deprecated fields: {', '.join(deprecated_fields)}")
                        else:
                            error_details.append("Service structure validation failed")
                    else:
                        if path:
                            error_details.append(f"{msg} at {'.'.join(str(p) for p in path)}")
                        else:
                            error_details.append(msg)
                
                # Provide helpful hints for common issues
                hints = []
                error_str = str(validation_result["errors"])
                if "parameters" in error_str:
                    hints.append("Parameters should be a list of dictionaries, each with 'name', 'type', 'required', and 'description' fields")
                if "configuration" in error_str:
                    hints.append("For api_call services, use configuration with 'endpoint_template' and 'request_config' containing 'method', and optionally 'parameter_method', 'headers_template', 'body_template'")
                if "service_name" in error_str:
                    hints.append("Service must have a 'service_name' field (not 'name')")
                
                # Provide a helpful example for api_call services
                example_config = None
                if service_type == "api_call":
                    example_config = {
                        "correct_configuration_format": {
                            "endpoint_template": "/api/test",  # Use endpoint_template
                            "request_config": {
                                "method": "POST",
                                "parameter_method": "body",
                                "headers_template": {  # Use headers_template
                                    "Content-Type": "application/json"
                                },
                                "body_template": {
                                    "message": "{{message}}",
                                    "message_description": "{{message_description}}",
                                    "timestamp": "{{timestamp}}"
                                }
                            },
                            "parameter_schema": {
                                "type": "object",
                                "properties": {
                                    "message": {
                                        "type": "string",
                                        "description": "The test message to send"
                                    },
                                    "message_description": {
                                        "type": "string",
                                        "description": "Description of the message"
                                    },
                                    "timestamp": {
                                        "type": "string",
                                        "format": "date-time",
                                        "description": "ISO 8601 timestamp"
                                    }
                                },
                                "required": ["message", "message_description", "timestamp"]
                            },
                            "output_schema": {
                                "type": "object",
                                "properties": {
                                    "success": {
                                        "type": "boolean",
                                        "description": "Success status"
                                    },
                                    "message": {
                                        "type": "string",
                                        "description": "Response message"
                                    }
                                }
                            }
                        }
                    }
                
                response = {
                    "error": "Service validation failed",
                    "issues": error_details if error_details else ["Service structure validation failed"],
                    "fixes_required": specific_fixes if specific_fixes else hints,
                    "warnings": validation_result.get("warnings", [])
                }
                
                if service_type == "api_call" and not specific_fixes:
                    # If no specific fixes were identified, provide the correct structure
                    response["correct_api_call_structure"] = {
                        "service_name": "example_service",
                        "description": "Service description",
                        "service_type": "api_call",
                        "endpoint_template": "/api/endpoint/{{parameter}}",
                        "request_config": {
                            "method": "POST",
                            "parameter_method": "body",  # or "query_params", "json_payload", "url_pattern"
                            "headers_template": {
                                "Content-Type": "application/json",
                                "Authorization": "Bearer {{auth.access_token}}"  # for OAuth2
                            },
                            "body_template": {
                                "field1": "{{parameter1}}",
                                "field2": "{{parameter2}}"
                            }
                        },
                        "parameter_schema": {
                            "type": "object",
                            "properties": {
                                "parameter1": {"type": "string", "description": "Description"},
                                "parameter2": {"type": "number", "description": "Description"}
                            },
                            "required": ["parameter1"]
                        },
                        "sample_input": {"parameter1": "value1", "parameter2": 123},
                        "sample_output": {"success": True, "data": {}}
                    }
                    response["note"] = "For api_call services: endpoint_template, request_config, and parameter_schema must be at service level (not inside configuration or service_config)"
                
                return response
            
            # Save updated application
            file_path = self.seed_apps_path / f"{app_key}.json"
            with open(file_path, 'w') as f:
                json.dump(app_data, f, indent=2)

            # Update just this entry in the cache instead of clearing everything
            self.seed_manager.update_cache_entry(app_key, app_data)

            return {
                "success": True,
                "app_key": app_key,
                "service_name": service_name,
                "service": new_service,
                "total_services": len(app_data["services"])
            }

        except Exception as e:
            logger.error(f"Error adding service: {str(e)}")
            return {"error": str(e)}

    async def add_event_to_application(
        self,
        app_key: str,
        event_name: str,
        event_type: str,
        description: str,
        configuration: Dict[str, Any],
        sample_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a new event/trigger to a seed application.
        
        Args:
            app_key: Application to add event to
            event_name: Unique event name
            event_type: Type of event (webhook, schedule, etc.)
            description: Event description
            configuration: Event-specific configuration
            sample_payload: Example payload data
            
        Returns:
            Updated application or error
        """
        try:
            # Parse JSON strings if they come from MCP
            if isinstance(configuration, str):
                try:
                    configuration = json.loads(configuration)
                    logger.debug(f"Parsed configuration from JSON string")
                except json.JSONDecodeError as e:
                    return {
                        "error": "Invalid JSON in configuration",
                        "details": str(e),
                        "hint": "Configuration should be a valid JSON object"
                    }
            
            if isinstance(sample_payload, str):
                try:
                    sample_payload = json.loads(sample_payload)
                    logger.debug(f"Parsed sample_payload from JSON string")
                except json.JSONDecodeError as e:
                    return {
                        "error": "Invalid JSON in sample_payload",
                        "details": str(e),
                        "hint": "Sample payload should be a valid JSON object"
                    }
            
            # Validate permissions
            if not self.auth.has_permission("edit_seed_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "edit_seed_applications"
                }

            # Load single application directly from file (avoids full discovery)
            app_data = self.seed_manager.get_single_application(app_key)
            if app_data is None:
                return {"error": f"Seed application '{app_key}' not found"}

            # Validate event name uniqueness
            existing_events = [e.get("event_name", e.get("name", "")) for e in app_data.get("events", [])]
            if event_name in existing_events:
                return {"error": f"Event '{event_name}' already exists"}
            
            # Validate event type
            valid_event_types = [
                "webhook", "schedule", "polling", "manual", "email", "form", "mqtt"
            ]
            if event_type not in valid_event_types:
                return {
                    "error": f"Invalid event_type: '{event_type}'",
                    "valid_values": valid_event_types,
                    "descriptions": {
                        "webhook": "HTTP POST callback from external service",
                        "schedule": "Cron-based scheduled trigger",
                        "polling": "Poll at regular intervals",
                        "manual": "Manual trigger by user",
                        "email": "Triggered by incoming email",
                        "form": "Triggered by form submission",
                        "mqtt": "Triggered by a message published to an MQTT topic"
                    }
                }
            
            # Create event structure
            new_event = {
                "event_name": event_name,
                "description": description,
                "event_type": event_type,
                "event_configuration": configuration
            }
            
            if sample_payload:
                new_event["sample_payload"] = sample_payload
            
            # Add default extraction for webhooks
            if event_type == "webhook":
                new_event["extraction_configuration"] = {
                    "path_mappings": {
                        "event_id": "$.id",
                        "event_type": "$.type",
                        "data": "$.data"
                    }
                }
            
            # Add to events
            if "events" not in app_data:
                app_data["events"] = []
            
            app_data["events"].append(new_event)
            
            # Auto-increment version since we added an event
            existing_version = app_data.get('application', {}).get('version', '1.0.0')
            version_parts = existing_version.split('.')
            try:
                # Increment patch version
                major = int(version_parts[0]) if len(version_parts) > 0 else 1
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                patch = int(version_parts[2]) if len(version_parts) > 2 else 0
                patch += 1
                new_version = f"{major}.{minor}.{patch}"
            except:
                # If version format is invalid, use a default
                new_version = "1.0.1"
            
            app_data["application"]["version"] = new_version
            logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {app_key} after adding event")
            
            # Update metadata
            if "metadata" not in app_data:
                app_data["metadata"] = {}
            
            app_data["metadata"]["last_modified"] = datetime.utcnow().isoformat()
            app_data["metadata"]["events_count"] = len(app_data["events"])
            
            # Validate the updated application before saving
            validation_result = self.schema_validator.validate_seed_application(app_data)
            
            if not validation_result["valid"]:
                # Remove the event we just added since validation failed
                app_data["events"].pop()
                return {
                    "error": "Event addition failed validation",
                    "validation_errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            
            # Save updated application
            file_path = self.seed_apps_path / f"{app_key}.json"
            with open(file_path, 'w') as f:
                json.dump(app_data, f, indent=2)

            # Update just this entry in the cache
            self.seed_manager.update_cache_entry(app_key, app_data)

            return {
                "success": True,
                "app_key": app_key,
                "event_name": event_name,
                "event": new_event,
                "total_events": len(app_data["events"])
            }
            
        except Exception as e:
            logger.error(f"Error adding event: {str(e)}")
            return {"error": str(e)}
    
    async def remove_service_from_application(
        self,
        app_key: str,
        service_name: str
    ) -> Dict[str, Any]:
        """
        Remove a service from a seed application.
        
        Args:
            app_key: Application key
            service_name: Name of service to remove
            
        Returns:
            Success status or error
        """
        try:
            # Validate permissions
            if not self.auth.has_permission("edit_seed_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "edit_seed_applications"
                }
            
            # Load single application directly from file (avoids full discovery)
            app_data = self.seed_manager.get_single_application(app_key)
            if app_data is None:
                return {"error": f"Seed application '{app_key}' not found"}

            # Find and remove service - check both service_name and name fields
            services = app_data.get("services", [])
            original_count = len(services)
            
            app_data["services"] = [
                s for s in services 
                if (s.get("service_name") != service_name and s.get("name") != service_name)
            ]
            
            if len(app_data["services"]) == original_count:
                return {"error": f"Service '{service_name}' not found"}
            
            # Auto-increment version since we removed a service
            existing_version = app_data.get('application', {}).get('version', '1.0.0')
            version_parts = existing_version.split('.')
            try:
                # Increment patch version
                major = int(version_parts[0]) if len(version_parts) > 0 else 1
                minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                patch = int(version_parts[2]) if len(version_parts) > 2 else 0
                patch += 1
                new_version = f"{major}.{minor}.{patch}"
            except:
                # If version format is invalid, use a default
                new_version = "1.0.1"
            
            app_data["application"]["version"] = new_version
            logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {app_key} after removing service")
            
            # Update metadata
            app_data["metadata"]["last_modified"] = datetime.utcnow().isoformat()
            app_data["metadata"]["services_count"] = len(app_data["services"])
            
            # Save updated application
            file_path = self.seed_apps_path / f"{app_key}.json"
            with open(file_path, 'w') as f:
                json.dump(app_data, f, indent=2)

            # Update just this entry in the cache
            self.seed_manager.update_cache_entry(app_key, app_data)

            return {
                "success": True,
                "app_key": app_key,
                "removed_service": service_name,
                "remaining_services": len(app_data["services"])
            }
            
        except Exception as e:
            logger.error(f"Error removing service: {str(e)}")
            return {"error": str(e)}
    
    async def update_auth_configuration(
        self,
        app_key: str,
        auth_type: str,
        auth_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update authentication configuration for an application.
        
        Args:
            app_key: Application key
            auth_type: New authentication type
            auth_config: Authentication configuration
            
        Returns:
            Updated application or error
        """
        try:
            # Parse JSON strings if they come from MCP
            if isinstance(auth_config, str):
                try:
                    auth_config = json.loads(auth_config)
                    logger.debug(f"Parsed auth_config from JSON string")
                except json.JSONDecodeError as e:
                    return {
                        "error": "Invalid JSON in auth_config",
                        "details": str(e),
                        "hint": "Auth config should be a valid JSON object"
                    }
            
            # Validate permissions
            if not self.auth.has_permission("edit_seed_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "edit_seed_applications"
                }
            
            # Load single application directly from file (avoids full discovery)
            app_data = self.seed_manager.get_single_application(app_key)
            if app_data is None:
                return {"error": f"Seed application '{app_key}' not found"}

            # Validate auth type
            valid_auth_types = [
                "none", "api_key", "oauth2", "basic", "token_exchange", "custom"
            ]
            if auth_type not in valid_auth_types:
                return {
                    "error": f"Invalid auth_type: '{auth_type}'",
                    "valid_values": valid_auth_types,
                    "current_auth_type": app_data["application"].get("auth_type"),
                    "suggestion": f"Choose from: {', '.join(valid_auth_types)}"
                }
            
            # Store original auth config for comparison
            original_auth_type = app_data["application"].get("auth_type")
            original_auth_config = app_data["application"].get("auth_config")
            
            # Update auth configuration
            app_data["application"]["auth_type"] = auth_type
            app_data["application"]["auth_config"] = auth_config
            
            # Add auth examples based on type
            if auth_type == "oauth2":
                app_data["application"]["auth_example"] = {
                    "client_id": "your_client_id",
                    "client_secret": "your_client_secret",
                    "redirect_uri": "http://localhost:8000/api/v1/oauth/callback"
                }
            elif auth_type == "api_key":
                app_data["application"]["auth_example"] = {
                    "api_key": "your_api_key_here"
                }
            
            # Auto-increment version if auth config changed
            if original_auth_type != auth_type or original_auth_config != auth_config:
                existing_version = app_data.get('application', {}).get('version', '1.0.0')
                version_parts = existing_version.split('.')
                try:
                    # Increment patch version
                    major = int(version_parts[0]) if len(version_parts) > 0 else 1
                    minor = int(version_parts[1]) if len(version_parts) > 1 else 0
                    patch = int(version_parts[2]) if len(version_parts) > 2 else 0
                    patch += 1
                    new_version = f"{major}.{minor}.{patch}"
                except:
                    # If version format is invalid, use a default
                    new_version = "1.0.1"
                
                app_data["application"]["version"] = new_version
                logger.info(f"Auto-incremented version from {existing_version} to {new_version} for {app_key} after auth config update")
            
            # Update metadata
            app_data["metadata"]["last_modified"] = datetime.utcnow().isoformat()
            
            # Validate the updated application before saving
            validation_result = self.schema_validator.validate_seed_application(app_data)
            
            if not validation_result["valid"]:
                return {
                    "error": "Auth configuration update failed validation",
                    "validation_errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            
            # Save updated application
            file_path = self.seed_apps_path / f"{app_key}.json"
            with open(file_path, 'w') as f:
                json.dump(app_data, f, indent=2)

            # Update just this entry in the cache
            self.seed_manager.update_cache_entry(app_key, app_data)

            return {
                "success": True,
                "app_key": app_key,
                "auth_type": auth_type,
                "auth_config": auth_config,
                "auth_guide": self._get_auth_setup_guide(auth_type)
            }
            
        except Exception as e:
            logger.error(f"Error updating auth configuration: {str(e)}")
            return {"error": str(e)}
    
    async def delete_seed_application(
        self,
        app_key: str,
        confirm: bool = False
    ) -> Dict[str, Any]:
        """
        Delete a seed application (requires confirmation).
        
        Args:
            app_key: Application key to delete
            confirm: Must be True to confirm deletion
            
        Returns:
            Success status or error
        """
        try:
            # Validate permissions
            if not self.auth.has_permission("delete_seed_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "delete_seed_applications"
                }
            
            if not confirm:
                return {
                    "error": "Deletion not confirmed",
                    "message": "Set confirm=True to delete the application"
                }
            
            # Load single application directly from file (avoids full discovery)
            app_data = self.seed_manager.get_single_application(app_key)
            if app_data is None:
                return {"error": f"Seed application '{app_key}' not found"}

            # Check if installed
            if self.auth.user_info:
                app_info = app_data.get("application", {})
                app_name = app_info.get("app_name")
                app_type = app_info.get("app_type", "global")
                
                # Get all installed applications
                response = await self.auth.make_authenticated_request(
                    "GET",
                    "/api/v1/applications"
                )
                
                if not response.get("error") and isinstance(response, list):
                    # Check if this app is installed
                    for installed_app in response:
                        if (installed_app.get("app_name") == app_name and
                            installed_app.get("app_type") == app_type):
                            return {
                                "error": "Cannot delete installed application",
                                "message": "Uninstall the application first using uninstall_application",
                                "app_id": installed_app.get("app_id")
                            }
            
            # Delete file
            file_path = self.seed_apps_path / f"{app_key}.json"
            if file_path.exists():
                file_path.unlink()
            
            # Refresh cache
            self.seed_manager.refresh_cache()
            
            return {
                "success": True,
                "deleted": app_key,
                "message": f"Seed application '{app_key}' has been deleted"
            }
            
        except Exception as e:
            logger.error(f"Error deleting seed application: {str(e)}")
            return {"error": str(e)}
    
    async def duplicate_application(
        self,
        source_app_key: str,
        new_app_key: str,
        new_app_name: str
    ) -> Dict[str, Any]:
        """
        Create a copy of an existing seed application.
        
        Args:
            source_app_key: Application to copy from
            new_app_key: Key for the new application
            new_app_name: Name for the new application
            
        Returns:
            New application or error
        """
        try:
            # Validate permissions
            if not self.auth.has_permission("create_seed_applications"):
                return {
                    "error": "Permission denied",
                    "required_permission": "create_seed_applications"
                }
            
            # Validate new app_key
            if not self._validate_app_key(new_app_key):
                return {
                    "error": f"Invalid app_key format: '{new_app_key}'",
                    "valid_format": "lowercase letters, numbers, and underscores only",
                    "example": "my_app_key_123",
                    "pattern": "^[a-z0-9_]+$"
                }
            
            # Load source application
            seed_apps = self.seed_manager.discover_seed_applications()
            if source_app_key not in seed_apps:
                return {"error": f"Source application '{source_app_key}' not found"}
            
            if new_app_key in seed_apps:
                return {"error": f"Application '{new_app_key}' already exists"}
            
            # Copy application data
            source_data = seed_apps[source_app_key]
            new_data = json.loads(json.dumps(source_data))  # Deep copy
            
            # Update key and name
            new_data["key"] = new_app_key
            new_data["application"]["app_name"] = new_app_name
            
            # Update metadata
            new_data["metadata"] = {
                "created_at": datetime.utcnow().isoformat(),
                "created_by": self.auth.user_info.get("email") if self.auth.user_info else "unknown",
                "copied_from": source_app_key,
                "author": self.auth.user_info.get("email") if self.auth.user_info else "unknown"
            }
            
            # Validate the new application before saving
            validation_result = self.schema_validator.validate_seed_application(new_data)
            
            if not validation_result["valid"]:
                return {
                    "error": "Duplicated application failed validation",
                    "validation_errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            
            # Save new application
            file_path = self.seed_apps_path / f"{new_app_key}.json"
            with open(file_path, 'w') as f:
                json.dump(new_data, f, indent=2)
            
            # Refresh cache
            self.seed_manager.refresh_cache()
            
            return {
                "success": True,
                "app_key": new_app_key,
                "app_name": new_app_name,
                "copied_from": source_app_key,
                "file_path": str(file_path),
                "message": f"Successfully duplicated '{source_app_key}' as '{new_app_key}'"
            }
            
        except Exception as e:
            logger.error(f"Error duplicating application: {str(e)}")
            return {"error": str(e)}
    
    def _validate_app_key(self, app_key: str) -> bool:
        """Validate app key format"""
        import re
        return bool(re.match(r'^[a-z0-9_]+$', app_key))
    
    def _get_default_auth_config(self, auth_type: str) -> Dict[str, Any]:
        """Get default auth configuration for a type"""
        defaults = {
            "none": {},
            "api_key": {
                "header_name": "X-API-Key",
                "query_param": None
            },
            "oauth2": {
                "auth_url": "https://example.com/oauth/authorize",
                "token_url": "https://example.com/oauth/token",
                "scopes": [],
                "client_id_param": "client_id",
                "client_secret_param": "client_secret"
            },
            "basic": {
                "username_field": "username",
                "password_field": "password"
            },
            "token_exchange": {
                "exchange_url": "https://example.com/token/exchange",
                "token_field": "access_token"
            },
            "custom": {
                "description": "Custom authentication implementation"
            }
        }
        return defaults.get(auth_type, {})
    
    def _get_auth_setup_guide(self, auth_type: str) -> Dict[str, Any]:
        """Get setup guide for authentication type"""
        guides = {
            "api_key": {
                "steps": [
                    "Obtain API key from service provider",
                    "Store key securely in IOFlow",
                    "Key will be sent in specified header/query param"
                ],
                "security_note": "Never commit API keys to version control"
            },
            "oauth2": {
                "steps": [
                    "Register OAuth application with provider",
                    "Configure redirect URI in provider settings",
                    "Add client ID and secret to IOFlow",
                    "Users will authorize access on first use"
                ],
                "redirect_uri": "http://localhost:8000/api/v1/oauth/callback"
            },
            "basic": {
                "steps": [
                    "Users provide username and password",
                    "Credentials sent with each request",
                    "Consider using more secure auth methods"
                ],
                "security_note": "Basic auth should only be used over HTTPS"
            }
        }
        return guides.get(auth_type, {"steps": ["Configure authentication as needed"]})